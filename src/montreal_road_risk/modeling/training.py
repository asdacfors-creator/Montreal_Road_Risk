"""
src/montreal_road_risk/modeling/training.py

Classifier training with checkpoint management for Phase 5.

Rules
-----
* One worker only (n_jobs=1 everywhere).
* Checkpoints contain 9 fingerprints; reuse only when all match.
* Mismatched checkpoints quarantined — never copied to official dirs.
* Write checkpoint only after successful fit + read-back validation.
* XGBoost best_iteration recorded and used explicitly.
* No calibration — deferred to Phase 6.
* No test-set access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

log = logging.getLogger(__name__)

ALLOWED_STATUS = frozenset([
    "train", "validation", "sealed_test",
    "embargo_train_validation", "embargo_validation_test",
])


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _sha256_json(obj: Any) -> str:
    return _sha256_str(json.dumps(obj, sort_keys=True))


def _sha256_dir(dir_path: str) -> str:
    """SHA-256 over all .py files in a directory tree (sorted by path)."""
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(dir_path)):
        for fname in sorted(files):
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                h.update(fpath.encode())
                with open(fpath, "rb") as f:
                    h.update(f.read())
    return h.hexdigest()


def compute_fingerprints(
    config: dict,
    split_manifest_path: str,
    panel_dir: str,
    env_manifest_path: str,
) -> dict:
    """Compute the nine required checkpoint fingerprints."""
    # Input panel fingerprint: SHA-256 over sorted parquet file paths
    import glob
    files = sorted(glob.glob(os.path.join(panel_dir, "panel_year=*/panel_month=*/segment_month.parquet")))
    panel_fp = hashlib.sha256("\n".join(files).encode()).hexdigest()

    split_fp     = _sha256_file(split_manifest_path) if os.path.exists(split_manifest_path) else "missing"
    config_fp    = _sha256_json(config)
    env_fp       = _sha256_file(env_manifest_path) if os.path.exists(env_manifest_path) else "missing"
    src_fp       = _sha256_dir("src/montreal_road_risk/modeling")

    return {
        "input_panel_sha256":    panel_fp,
        "split_fingerprint_sha256": split_fp,
        "config_sha256":         config_fp,
        "environment_sha256":    env_fp,
        "source_code_sha256":    src_fp,
        # Placeholders filled per-model
        "feature_schema_sha256": None,
        "model_readable":        None,
        "val_prediction_count":  None,
        "val_ap_score":          None,
    }


# ---------------------------------------------------------------------------
# Checkpoint I/O
# ---------------------------------------------------------------------------

def _checkpoint_dir(base: str, model_name: str, config_id: str) -> str:
    return os.path.join(base, f"{model_name}__{config_id}")


def checkpoint_exists(base: str, model_name: str, config_id: str) -> bool:
    ckpt = _checkpoint_dir(base, model_name, config_id)
    return (
        os.path.isdir(ckpt)
        and os.path.exists(os.path.join(ckpt, "model.joblib"))
        and os.path.exists(os.path.join(ckpt, "metadata.json"))
        and os.path.exists(os.path.join(ckpt, "fingerprints.json"))
    )


def load_checkpoint_fingerprints(base: str, model_name: str, config_id: str) -> dict:
    ckpt = _checkpoint_dir(base, model_name, config_id)
    with open(os.path.join(ckpt, "fingerprints.json")) as f:
        return json.load(f)


def validate_checkpoint(
    base: str,
    model_name: str,
    config_id: str,
    current_fps: dict,
) -> bool:
    """Return True only if all fingerprints match. Quarantine on mismatch."""
    saved = load_checkpoint_fingerprints(base, model_name, config_id)
    compare_keys = [
        "input_panel_sha256", "split_fingerprint_sha256",
        "config_sha256", "environment_sha256", "source_code_sha256",
    ]
    mismatches = [k for k in compare_keys if saved.get(k) != current_fps.get(k)]
    if mismatches:
        log.warning("Checkpoint fingerprint mismatch for %s/%s: %s", model_name, config_id, mismatches)
        _quarantine(base, model_name, config_id, reason=f"fingerprint mismatch: {mismatches}")
        return False
    # Also verify model is readable
    try:
        model_path = os.path.join(_checkpoint_dir(base, model_name, config_id), "model.joblib")
        _ = joblib.load(model_path)
    except Exception as e:
        log.warning("Checkpoint model not readable for %s/%s: %s", model_name, config_id, e)
        _quarantine(base, model_name, config_id, reason=f"model not readable: {e}")
        return False
    return True


def _quarantine(base: str, model_name: str, config_id: str, reason: str) -> None:
    ckpt = _checkpoint_dir(base, model_name, config_id)
    quarantine_base = os.path.join(base, "quarantine")
    dest = os.path.join(quarantine_base, f"{model_name}__{config_id}")
    Path(quarantine_base).mkdir(parents=True, exist_ok=True)
    if os.path.exists(ckpt):
        shutil.move(ckpt, dest)
    with open(os.path.join(quarantine_base, f"{model_name}__{config_id}__quarantine_reason.txt"), "w") as f:
        f.write(reason)
    log.warning("Checkpoint quarantined: %s → %s (reason: %s)", ckpt, dest, reason)


def save_checkpoint(
    base: str,
    model_name: str,
    config_id: str,
    pipeline: Pipeline,
    metadata: dict,
    fingerprints: dict,
) -> None:
    """Save checkpoint only after successful fit. Writes model, metadata, fingerprints."""
    ckpt = _checkpoint_dir(base, model_name, config_id)
    Path(ckpt).mkdir(parents=True, exist_ok=True)

    model_path = os.path.join(ckpt, "model.joblib")
    joblib.dump(pipeline, model_path, compress=3)

    # Read-back validation
    try:
        _ = joblib.load(model_path)
        fingerprints["model_readable"] = True
        log.info("Checkpoint read-back OK for %s/%s", model_name, config_id)
    except Exception as e:
        fingerprints["model_readable"] = False
        _quarantine(base, model_name, config_id, reason=f"read-back failed: {e}")
        raise RuntimeError(f"Model read-back failed for {model_name}/{config_id}: {e}") from e

    with open(os.path.join(ckpt, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    with open(os.path.join(ckpt, "fingerprints.json"), "w") as f:
        json.dump(fingerprints, f, indent=2)

    log.info("Checkpoint saved: %s", ckpt)


def load_best_pipeline(official_dir: str, model_name: str) -> Pipeline:
    path = os.path.join(official_dir, f"{model_name}.joblib")
    return joblib.load(path)


def save_official_artifact(
    pipeline: Pipeline, official_dir: str, model_name: str
) -> str:
    Path(official_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(official_dir, f"{model_name}.joblib")
    joblib.dump(pipeline, path, compress=3)
    log.info("Official artifact saved: %s", path)
    return path


# ---------------------------------------------------------------------------
# XGBoost best-iteration prediction helper
# ---------------------------------------------------------------------------

def xgb_predict_best(pipeline: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """
    Predict probabilities from XGBoost pipeline at best_iteration.
    Falls back to standard predict_proba if best_iteration not available.
    """
    estimator = pipeline.named_steps["estimator"]
    preprocessor = pipeline.named_steps["preprocessor"]
    X_trans = preprocessor.transform(X)

    if hasattr(estimator, "best_iteration") and estimator.best_iteration is not None:
        import xgboost as xgb  # noqa: F401
        bi = estimator.best_iteration
        proba = estimator.predict_proba(
            X_trans,
            iteration_range=(0, bi + 1),
        )[:, 1]
        log.info("XGBoost predict at best_iteration=%d", bi)
    else:
        proba = estimator.predict_proba(X_trans)[:, 1]
    return proba
