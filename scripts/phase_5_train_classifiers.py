"""
scripts/phase_5_train_classifiers.py

Steps 11-13 — Sequential classifier grid, lean configuration.

Lean grid (estimated 20-40 min total):
  LR  — lbfgs solver, C in {0.01, 0.1, 1.0}, class_weight=None   → 3 runs
  XGB — max_depth in {4, 6}, lr=0.1, n_estimators=300             → 2 runs

Training on 1 M stratified-subsample rows (memory-safe).
Validation on full val_90d partition (479 K rows).
No test-set access. No calibration. One worker only.
"""

from __future__ import annotations

import gc
import json
import logging
import os
import sys
import time

import pandas as pd

sys.path.insert(0, "src")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _mem_gb() -> float:
    import psutil
    return psutil.Process().memory_info().rss / 1e9


def main() -> None:  # noqa: C901  # noqa: C901
    from sklearn.linear_model import LogisticRegression

    from montreal_road_risk.modeling.metrics import compute_validation_metrics
    from montreal_road_risk.modeling.preprocessing import (
        build_logistic_pipeline,
        build_tree_pipeline,
        prepare_Xy,
        resolve_feature_columns,
    )
    from montreal_road_risk.modeling.qa import check_system_memory
    from montreal_road_risk.modeling.training import (
        checkpoint_exists,
        save_checkpoint,
    )

    cfg_path = "config/phase_5_modeling.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    phase5_dir   = cfg["phase5_dir"]
    models_dir   = cfg["models_dir"]
    chk_dir      = os.path.join(models_dir, "checkpoints")
    results_path = os.path.join(models_dir, "classifier_validation_results.json")
    os.makedirs(chk_dir, exist_ok=True)
    SEED = cfg["seed"]

    # -------------------------------------------------------------------------
    # Load partitions
    # -------------------------------------------------------------------------
    log.info("Loading 90d train and val partitions ...")
    train_df = pd.read_parquet(os.path.join(phase5_dir, "train_90d.parquet"))
    val_df   = pd.read_parquet(os.path.join(phase5_dir, "val_90d.parquet"))
    log.info("  train: %d | val: %d | RSS=%.2f GB", len(train_df), len(val_df), _mem_gb())

    target_col = "target_repair_90d"
    elig_col   = "target_eligible_90d"
    cat_cols   = cfg["categorical_cols"]

    if elig_col in train_df.columns:
        train_df = train_df[train_df[elig_col] == 1]
        val_df   = val_df[val_df[elig_col] == 1]

    log.info("Preparing feature matrices ...")
    X_train, y_train = prepare_Xy(train_df, target_col, cfg, cat_cols)
    X_val,   y_val   = prepare_Xy(val_df,   target_col, cfg, cat_cols)
    del train_df, val_df
    gc.collect()
    log.info("  RSS after prepare_Xy: %.2f GB", _mem_gb())

    # Stratified subsample — keeps numpy alloc at ~700 MB (safe)
    N_LIMIT = 1_000_000
    if len(X_train) > N_LIMIT:
        from sklearn.model_selection import train_test_split as _tts
        X_train, _, y_train, _ = _tts(
            X_train, y_train, train_size=N_LIMIT,
            stratify=y_train, random_state=SEED,
        )
        gc.collect()
        log.info("  Subsampled train → %d rows | RSS=%.2f GB", len(X_train), _mem_gb())

    log.info(
        "  X_train %s pos=%.2f%% | X_val %s pos=%.2f%%",
        X_train.shape, 100 * float(y_train.mean()),
        X_val.shape,   100 * float(y_val.mean()),
    )

    num_cols, cat_cols_r, bin_cols, excl = resolve_feature_columns(X_train, cfg)
    if excl:
        log.warning("Excluded cols still in X_train: %s", excl)
    log.info("  %d numeric | %d categorical | %d binary", len(num_cols), len(cat_cols_r), len(bin_cols))

    # Save feature names for Phase 6
    with open(os.path.join(models_dir, "feature_names_90d.json"), "w") as f:
        json.dump(list(X_train.columns), f, indent=2)

    fp_dict = {"cfg_version": cfg.get("version", "unknown")}
    all_results = []

    def _chk_resume(model_name: str, config_id: str) -> bool:
        """Return True (and append metrics) if checkpoint exists."""
        if not checkpoint_exists(chk_dir, model_name, config_id):
            return False
        log.info("SKIP (checkpoint): %s", model_name)
        meta = os.path.join(chk_dir, f"{model_name}__{config_id}", "metadata.json")
        if os.path.exists(meta):
            with open(meta) as f:
                all_results.append(json.load(f))
        return True

    # -------------------------------------------------------------------------
    # LOGISTIC REGRESSION — lbfgs, 3 C values, no class_weight variants
    # -------------------------------------------------------------------------
    log.info("=== Logistic Regression Grid (lbfgs) ===")
    for C in [0.01, 0.1, 1.0]:
        model_name = f"LR_C{C}_90d"
        config_id  = f"lbfgs_C{C}_seed{SEED}"
        if _chk_resume(model_name, config_id):
            continue

        mem = check_system_memory(baseline_max_pct=95)
        log.info("PRE-TRAIN RSS=%.2f GB sys=%.1f%%", mem["process_rss_gb"], mem["system_pct"])
        log.info("TRAINING: %s", model_name)

        estimator = LogisticRegression(
            C=C, solver="lbfgs", max_iter=500,
            random_state=SEED,
        )
        pipeline = build_logistic_pipeline(estimator, num_cols, cat_cols_r, bin_cols)
        t0 = time.time()
        pipeline.fit(X_train, y_train)
        elapsed = time.time() - t0
        proba = pipeline.predict_proba(X_val)[:, 1]

        metrics = compute_validation_metrics(
            y_val.values, proba,
            k_pcts=cfg["metrics"]["at_k_percents"],
            model_name=model_name,
        )
        metrics.update({"family": "LogisticRegression", "horizon": "90d",
                        "params": {"C": C, "solver": "lbfgs"}, "elapsed_s": round(elapsed, 1)})
        log.info("  %s  AP=%.4f  ROC=%.4f  %.1fs",
                 model_name, metrics["Average Precision (AP)"], metrics["ROC-AUC"], elapsed)

        save_checkpoint(chk_dir, model_name, config_id, pipeline, metrics, fp_dict)
        all_results.append(metrics)
        del pipeline
        gc.collect()

    # -------------------------------------------------------------------------
    # XGBOOST — 2 configs (max_depth 4/6, lr=0.1, n_estimators=300)
    # -------------------------------------------------------------------------
    log.info("=== XGBoost Grid ===")
    try:
        import xgboost as xgb
    except ImportError:
        log.warning("XGBoost not available — skipping")
        xgb = None

    if xgb is not None:
        for md in [4, 6]:
            lr = 0.1
            ne = 300
            model_name = f"XGB_ne{ne}_md{md}_lr{lr}_90d"
            config_id  = f"ne{ne}_md{md}_lr{lr}_seed{SEED}"
            if _chk_resume(model_name, config_id):
                continue

            mem = check_system_memory(baseline_max_pct=95)
            log.info("PRE-TRAIN RSS=%.2f GB sys=%.1f%%", mem["process_rss_gb"], mem["system_pct"])
            log.info("TRAINING: %s", model_name)

            estimator = xgb.XGBClassifier(
                n_estimators=ne, max_depth=md, learning_rate=lr,
                subsample=0.8, colsample_bytree=0.8,
                tree_method="hist", eval_metric="aucpr",
                n_jobs=1, random_state=SEED, verbosity=0,
            )
            pipeline = build_tree_pipeline(estimator, num_cols, cat_cols_r, bin_cols)

            t0 = time.time()
            pipeline.fit(X_train, y_train)
            elapsed = time.time() - t0
            proba = pipeline.predict_proba(X_val)[:, 1]

            metrics = compute_validation_metrics(
                y_val.values, proba,
                k_pcts=cfg["metrics"]["at_k_percents"],
                model_name=model_name,
            )
            metrics.update({"family": "XGBoost", "horizon": "90d",
                            "params": {"n_estimators": ne, "max_depth": md, "learning_rate": lr},
                            "elapsed_s": round(elapsed, 1)})
            log.info("  %s  AP=%.4f  ROC=%.4f  %.1fs",
                     model_name, metrics["Average Precision (AP)"], metrics["ROC-AUC"], elapsed)

            save_checkpoint(chk_dir, model_name, config_id, pipeline, metrics, fp_dict)
            all_results.append(metrics)
            del pipeline
            gc.collect()

    # -------------------------------------------------------------------------
    # Save and print summary
    # -------------------------------------------------------------------------
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    log.info("Classifier results → %s", results_path)

    print("\n=== CLASSIFIER GRID VALIDATION SUMMARY (90d) ===")
    for r in sorted(all_results, key=lambda x: -x.get("Average Precision (AP)", 0)):
        mn = r.get("model") or r.get("model_name", "?")
        print(f"  {mn:<45s}  AP={r['Average Precision (AP)']:.4f}  "
              f"ROC={r['ROC-AUC']:.4f}  Brier={r['Brier']:.4f}")


if __name__ == "__main__":
    main()
