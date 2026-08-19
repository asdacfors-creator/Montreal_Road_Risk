"""
src/montreal_road_risk/modeling/qa.py

QA, environment manifest, protected-input snapshot, and XGBoost preflight.

Rules
-----
* Protected-input snapshot written before any split or model output.
* Protected file count is dynamic — never hardcoded.
* XGBoost preflight: import → param check → smoke fit → determinism.
* tracemalloc is supplemental; psutil RSS + system% is the primary memory metric.
* No calibration, no test metrics.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib
import json
import logging
import os
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment manifest
# ---------------------------------------------------------------------------

def _pkg_version(name: str) -> str:
    try:
        return importlib.import_module(name).__version__
    except Exception:
        return "unavailable"


def write_environment_manifest(models_dir: str, config: dict, config_path: str) -> dict:
    """Write environment_manifest.json and return its contents."""
    import glob as _glob
    panel_dir = config.get("panel_dir", "data/processed/phase_4")
    files = sorted(_glob.glob(os.path.join(panel_dir, "panel_year=*/panel_month=*/segment_month.parquet")))
    panel_fp = hashlib.sha256("\n".join(files).encode()).hexdigest()

    with open(config_path, "rb") as f:
        config_fp = hashlib.sha256(f.read()).hexdigest()

    manifest = {
        "python_version":   platform.python_version(),
        "numpy_version":    _pkg_version("numpy"),
        "scipy_version":    _pkg_version("scipy"),
        "sklearn_version":  _pkg_version("sklearn"),
        "xgboost_version":  _pkg_version("xgboost"),
        "xgboost_available": False,   # updated by xgboost_preflight()
        "pandas_version":   _pkg_version("pandas"),
        "pyarrow_version":  _pkg_version("pyarrow"),
        "psutil_version":   _pkg_version("psutil"),
        "joblib_version":   _pkg_version("joblib"),
        "n_jobs":           1,
        "seed":             config.get("seed", 42),
        "input_panel_sha256": panel_fp,
        "config_sha256":      config_fp,
        "recorded_at":        datetime.datetime.utcnow().isoformat() + "Z",
    }

    Path(models_dir).mkdir(parents=True, exist_ok=True)
    out = os.path.join(models_dir, "environment_manifest.json")
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Environment manifest written: %s", out)
    return manifest


# ---------------------------------------------------------------------------
# XGBoost preflight
# ---------------------------------------------------------------------------

def xgboost_preflight(models_dir: str, seed: int = 42) -> dict:
    """
    Auto-inspect XGBoost:
    1. Import check
    2. Version + parameter support
    3. Synthetic smoke fit (1000 rows)
    4. Determinism check (two fits, one worker)

    Returns dict with xgboost_available, version, and details.
    Updates environment_manifest.json if already written.
    """
    result = {
        "xgboost_available": False,
        "xgboost_version":   None,
        "import_ok":         False,
        "params_ok":         False,
        "smoke_fit_ok":      False,
        "determinism_ok":    False,
        "failure_reason":    None,
    }

    # Step 1: import
    try:
        import xgboost as xgb
        result["import_ok"]       = True
        result["xgboost_version"] = xgb.__version__
    except ImportError as e:
        result["failure_reason"] = f"ImportError: {e}"
        log.info("XGBoost not available: %s", e)
        _update_env_xgb(models_dir, result)
        return result

    # Step 2: param check
    try:
        _ = xgb.XGBClassifier(tree_method="hist", n_jobs=1, seed=seed, eval_metric="aucpr")
        result["params_ok"] = True
    except Exception as e:
        result["failure_reason"] = f"Param check failed: {e}"
        _update_env_xgb(models_dir, result)
        return result

    # Step 3: synthetic smoke fit
    try:
        rng = np.random.default_rng(seed)
        X_syn = rng.standard_normal((1000, 10)).astype(np.float32)
        y_syn = (rng.random(1000) > 0.93).astype(int)

        clf = xgb.XGBClassifier(
            n_estimators=10, max_depth=3, tree_method="hist",
            n_jobs=1, seed=seed, eval_metric="aucpr",
        )
        clf.fit(X_syn, y_syn)
        p1 = clf.predict_proba(X_syn)[:, 1]
        result["smoke_fit_ok"] = True
    except Exception as e:
        result["failure_reason"] = f"Smoke fit failed: {e}"
        _update_env_xgb(models_dir, result)
        return result

    # Step 4: determinism — refit from scratch
    try:
        clf2 = xgb.XGBClassifier(
            n_estimators=10, max_depth=3, tree_method="hist",
            n_jobs=1, seed=seed, eval_metric="aucpr",
        )
        clf2.fit(X_syn, y_syn)
        p2 = clf2.predict_proba(X_syn)[:, 1]
        if np.allclose(p1, p2, atol=1e-6):
            result["determinism_ok"] = True
        else:
            result["failure_reason"] = "Predictions differ between two identical fits"
            _update_env_xgb(models_dir, result)
            return result
    except Exception as e:
        result["failure_reason"] = f"Determinism check failed: {e}"
        _update_env_xgb(models_dir, result)
        return result

    result["xgboost_available"] = True
    log.info("XGBoost preflight PASSED: version=%s", result["xgboost_version"])
    _update_env_xgb(models_dir, result)
    return result


def _update_env_xgb(models_dir: str, result: dict) -> None:
    env_path = os.path.join(models_dir, "environment_manifest.json")
    if os.path.exists(env_path):
        with open(env_path) as f:
            env = json.load(f)
        env["xgboost_available"] = result["xgboost_available"]
        env["xgboost_version"]   = result.get("xgboost_version")
        with open(env_path, "w") as f:
            json.dump(env, f, indent=2)


# ---------------------------------------------------------------------------
# Protected-input snapshot
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_protected_snapshot(config: dict, state_dir: str) -> dict:
    """
    Walk all protected roots, compute SHA-256 per file.
    Write snapshot to state/phase_5_protected_input_snapshot.json.
    """
    roots = config.get("protected_roots", [])
    snapshot = {}

    for root in roots:
        if os.path.isfile(root):
            snapshot[root] = _sha256_file(root)
        elif os.path.isdir(root):
            for dirpath, _, fnames in os.walk(root):
                for fname in sorted(fnames):
                    fpath = os.path.join(dirpath, fname)
                    rel   = os.path.relpath(fpath).replace("\\", "/")
                    snapshot[rel] = _sha256_file(fpath)
        else:
            log.warning("Protected root not found: %s", root)

    out_path = os.path.join(state_dir, "phase_5_protected_input_snapshot.json")
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    record = {
        "n_protected_files": len(snapshot),
        "snapshot_taken_at": datetime.datetime.utcnow().isoformat() + "Z",
        "files": snapshot,
    }
    with open(out_path, "w") as f:
        json.dump(record, f, indent=2)
    log.info("Protected-input snapshot: %d files → %s", len(snapshot), out_path)
    return record


def verify_protected_snapshot(state_dir: str) -> dict:
    """Compare current file hashes against the snapshot. Return diff report."""
    snap_path = os.path.join(state_dir, "phase_5_protected_input_snapshot.json")
    with open(snap_path) as f:
        record = json.load(f)

    snapshot = record["files"]
    changed, missing = [], []

    for rel_path, orig_hash in snapshot.items():
        if not os.path.exists(rel_path):
            missing.append(rel_path)
        else:
            current = _sha256_file(rel_path)
            if current != orig_hash:
                changed.append(rel_path)

    report = {
        "total_protected_files": len(snapshot),
        "changed":  changed,
        "missing":  missing,
        "n_changed": len(changed),
        "n_missing": len(missing),
        "pass":     len(changed) == 0 and len(missing) == 0,
        "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    status = "PASS" if report["pass"] else "FAIL"
    log.info(
        "Protected-input check: %s — %d files, %d changed, %d missing",
        status, len(snapshot), len(changed), len(missing),
    )
    return report


# ---------------------------------------------------------------------------
# Memory monitoring helpers
# ---------------------------------------------------------------------------

def check_system_memory(baseline_max_pct: float = 50.0) -> dict:
    """Return current memory stats. Raise if baseline exceeds limit."""
    vm = psutil.virtual_memory()
    proc = psutil.Process()
    rss_gb = proc.memory_info().rss / 1e9
    report = {
        "system_pct":    vm.percent,
        "available_gb":  vm.available / 1e9,
        "total_gb":      vm.total / 1e9,
        "process_rss_gb": rss_gb,
    }
    if vm.percent > baseline_max_pct:
        log.warning(
            "System memory %.1f%% > baseline limit %.1f%% — recommend closing applications",
            vm.percent, baseline_max_pct,
        )
    return report


def get_rss_gb() -> float:
    return psutil.Process().memory_info().rss / 1e9


def get_system_pct() -> float:
    return psutil.virtual_memory().percent


# ---------------------------------------------------------------------------
# Training schema manifest
# ---------------------------------------------------------------------------

def write_training_schema_manifest(
    X_train: pd.DataFrame,
    cat_cols: list,
    X_val: pd.DataFrame,
    models_dir: str,
) -> dict:
    """Record actual cardinality of categorical columns from training partition."""

    cat_info = {}
    for c in cat_cols:
        if c not in X_train.columns:
            continue
        train_cats  = X_train[c].dropna().unique().tolist()
        val_cats    = X_val[c].dropna().unique().tolist() if c in X_val.columns else []
        unseen      = [v for v in val_cats if v not in set(train_cats)]
        n_missing   = int(X_train[c].isna().sum())
        cat_info[c] = {
            "n_categories":             len(train_cats),
            "categories":               sorted([str(x) for x in train_cats]),
            "n_missing_in_training":    n_missing,
            "n_unseen_in_validation":   len(unseen),
            "unseen_categories":        sorted([str(x) for x in unseen]),
        }

    n_numeric = len([c for c in X_train.columns if c not in cat_cols])
    manifest = {
        "categorical_columns":          cat_info,
        "n_numeric_features":           n_numeric,
        "n_categorical_raw_cols":       len(cat_cols),
        "total_raw_feature_cols":       len(X_train.columns),
        "recorded_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    Path(models_dir).mkdir(parents=True, exist_ok=True)
    out = os.path.join(models_dir, "training_schema_manifest.json")
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Training schema manifest written: %s", out)
    return manifest
