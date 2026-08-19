"""
scripts/phase_5_train_180d.py

Step 14 — Refit best 90d hyperparameters on the 180d partition.

Best 90d config: XGB_ne300_md4_lr0.1 (AP=0.8063 on val_90d)
Refit with identical hyperparameters on train_180d.
Score on val_180d. No test-set access. No calibration.
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


def main() -> None:  # noqa: C901
    import xgboost as xgb

    from montreal_road_risk.modeling.metrics import compute_validation_metrics
    from montreal_road_risk.modeling.preprocessing import (
        build_tree_pipeline,
        prepare_Xy,
        resolve_feature_columns,
    )
    from montreal_road_risk.modeling.training import checkpoint_exists, save_checkpoint

    cfg_path = "config/phase_5_modeling.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    phase5_dir   = cfg["phase5_dir"]
    models_dir   = cfg["models_dir"]
    chk_dir      = os.path.join(models_dir, "checkpoints")
    results_path = os.path.join(models_dir, "classifier_180d_results.json")
    os.makedirs(chk_dir, exist_ok=True)
    SEED = cfg["seed"]

    # Best 90d hyperparameters
    NE, MD, LR = 300, 4, 0.1
    model_name = f"XGB_ne{NE}_md{MD}_lr{LR}_180d"
    config_id  = f"ne{NE}_md{MD}_lr{LR}_seed{SEED}"
    fp_dict    = {"cfg_version": cfg.get("version", "unknown"), "horizon": "180d"}

    if checkpoint_exists(chk_dir, model_name, config_id):
        log.info("Checkpoint exists: %s — loading metrics", model_name)
        meta_path = os.path.join(chk_dir, f"{model_name}__{config_id}", "metadata.json")
        with open(meta_path) as f:
            result = json.load(f)
        print(json.dumps(result, indent=2, default=str))
        return

    # Load 180d partitions
    log.info("Loading 180d partitions ...")
    train_df = pd.read_parquet(os.path.join(phase5_dir, "train_180d.parquet"))
    val_df   = pd.read_parquet(os.path.join(phase5_dir, "val_180d.parquet"))
    log.info("  train: %d | val: %d | RSS=%.2f GB", len(train_df), len(val_df), _mem_gb())

    target_col = "target_repair_180d"
    elig_col   = "target_eligible_180d"
    cat_cols   = cfg["categorical_cols"]

    if elig_col in train_df.columns:
        train_df = train_df[train_df[elig_col] == 1]
        val_df   = val_df[val_df[elig_col] == 1]

    X_train, y_train = prepare_Xy(train_df, target_col, cfg, cat_cols)
    X_val,   y_val   = prepare_Xy(val_df,   target_col, cfg, cat_cols)
    del train_df, val_df
    gc.collect()
    log.info("  RSS after prepare_Xy: %.2f GB", _mem_gb())

    # Stratified subsample
    N_LIMIT = 1_000_000
    if len(X_train) > N_LIMIT:
        from sklearn.model_selection import train_test_split as _tts
        X_train, _, y_train, _ = _tts(
            X_train, y_train, train_size=N_LIMIT,
            stratify=y_train, random_state=SEED,
        )
        gc.collect()
        log.info("  Subsampled → %d rows | RSS=%.2f GB", len(X_train), _mem_gb())

    log.info(
        "  X_train %s pos=%.2f%% | X_val %s pos=%.2f%%",
        X_train.shape, 100 * float(y_train.mean()),
        X_val.shape,   100 * float(y_val.mean()),
    )

    num_cols, cat_cols_r, bin_cols, _ = resolve_feature_columns(X_train, cfg)

    # Save 180d feature names
    with open(os.path.join(models_dir, "feature_names_180d.json"), "w") as f:
        json.dump(list(X_train.columns), f, indent=2)

    # Fit
    estimator = xgb.XGBClassifier(
        n_estimators=NE, max_depth=MD, learning_rate=LR,
        subsample=0.8, colsample_bytree=0.8,
        tree_method="hist", eval_metric="aucpr",
        n_jobs=1, random_state=SEED, verbosity=0,
    )
    pipeline = build_tree_pipeline(estimator, num_cols, cat_cols_r, bin_cols)

    log.info("TRAINING: %s", model_name)
    t0 = time.time()
    pipeline.fit(X_train, y_train)
    elapsed = time.time() - t0
    proba = pipeline.predict_proba(X_val)[:, 1]

    metrics = compute_validation_metrics(
        y_val.values, proba,
        k_pcts=cfg["metrics"]["at_k_percents"],
        model_name=model_name,
    )
    metrics.update({
        "family": "XGBoost", "horizon": "180d",
        "params": {"n_estimators": NE, "max_depth": MD, "learning_rate": LR},
        "elapsed_s": round(elapsed, 1),
    })
    log.info("  %s  AP=%.4f  ROC=%.4f  %.1fs",
             model_name, metrics["Average Precision (AP)"], metrics["ROC-AUC"], elapsed)

    save_checkpoint(chk_dir, model_name, config_id, pipeline, metrics, fp_dict)

    with open(results_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    log.info("180d results → %s", results_path)
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == "__main__":
    main()
