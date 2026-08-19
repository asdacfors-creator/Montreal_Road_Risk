# ruff: noqa: E402
"""
scripts/phase_5_audit_xgb_early_stopping.py

Part 4 — Restore XGBoost early stopping using proper two-stage architecture:
  1. Fit preprocessor (ColumnTransformer) on training rows only.
  2. Transform train and val separately.
  3. Fit XGBClassifier on transformed train with val eval_set.
  4. Record best_iteration, best_score.
  5. Save serialized artifact: preprocessor.joblib + model.joblib
  6. Read-back prediction equality test.

This does NOT use the sealed test partition.
"""
from __future__ import annotations

import gc
import json
import logging
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

from montreal_road_risk.modeling.metrics import compute_validation_metrics
from montreal_road_risk.modeling.preprocessing import (
    build_tree_pipeline,
    prepare_Xy,
    resolve_feature_columns,
)

CFG_PATH   = "config/phase_5_modeling.json"
PHASE5_DIR = "data/processed/phase_5"
MODELS_DIR = "models/phase_5"
ARTIFACT_DIR = os.path.join(MODELS_DIR, "xgb_early_stop_artifact")
os.makedirs(ARTIFACT_DIR, exist_ok=True)

with open(CFG_PATH) as f:
    cfg = json.load(f)

SEED = cfg["seed"]
NE, MD, LR_RATE = 500, 4, 0.1   # higher n_estimators so early stopping can act
EARLY_STOP = 20
N_LIMIT    = 1_000_000

log.info("XGBoost version: %s", xgb.__version__)
log.info("Loading 90d partitions ...")
train_df = pd.read_parquet(os.path.join(PHASE5_DIR, "train_90d.parquet"))
val_df   = pd.read_parquet(os.path.join(PHASE5_DIR, "val_90d.parquet"))

elig = "target_eligible_90d"
if elig in train_df.columns:
    train_df = train_df[train_df[elig]==1]
    val_df   = val_df[val_df[elig]==1]

cat_cols = cfg["categorical_cols"]
X_full, y_full = prepare_Xy(train_df, "target_repair_90d", cfg, cat_cols)
X_val,  y_val  = prepare_Xy(val_df,   "target_repair_90d", cfg, cat_cols)
del train_df, val_df
gc.collect()

# Stratified subsample
from sklearn.model_selection import train_test_split as _tts

X_train, _, y_train, _ = _tts(
    X_full, y_full, train_size=N_LIMIT, stratify=y_full, random_state=SEED
)
del X_full, y_full
gc.collect()
log.info("Train sample: %d rows pos=%.4f | Val: %d rows pos=%.4f",
         len(X_train), float(y_train.mean()), len(X_val), float(y_val.mean()))

# ── STAGE 1: Fit preprocessor on training rows only ──
num_cols, cat_cols_r, bin_cols, _ = resolve_feature_columns(X_train, cfg)
log.info("Building pipeline: %d num | %d cat | %d bin", len(num_cols), len(cat_cols_r), len(bin_cols))

# Build a pipeline then extract the preprocessor (all steps except last)
dummy_est = xgb.XGBClassifier(n_estimators=1, verbosity=0)
full_pipeline = build_tree_pipeline(dummy_est, num_cols, cat_cols_r, bin_cols)
preprocessor = full_pipeline[:-1]   # ColumnTransformer

log.info("Fitting preprocessor on training rows ...")
t0 = time.time()
preprocessor.fit(X_train, y_train)
log.info("  Preprocessor fit: %.1fs", time.time() - t0)

# ── STAGE 2: Transform train and val separately ──
log.info("Transforming train and val ...")
X_train_t = preprocessor.transform(X_train)
X_val_t   = preprocessor.transform(X_val)
log.info("  X_train_t: %s | X_val_t: %s", X_train_t.shape, X_val_t.shape)

# ── STAGE 3: Fit XGBoost with eval_set ──
estimator = xgb.XGBClassifier(
    n_estimators=NE, max_depth=MD, learning_rate=LR_RATE,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", eval_metric="aucpr",
    early_stopping_rounds=EARLY_STOP,
    n_jobs=1, random_state=SEED, verbosity=0,
)
log.info("Fitting XGBClassifier with early stopping (max_estimators=%d, early_stop=%d)...", NE, EARLY_STOP)
t0 = time.time()
estimator.fit(
    X_train_t, y_train.values,
    eval_set=[(X_val_t, y_val.values)],
    verbose=False,
)
elapsed = time.time() - t0

best_iter  = estimator.best_iteration
best_score = estimator.best_score
log.info("  Training complete: %.1fs", elapsed)
log.info("  best_iteration: %d", best_iter)
log.info("  best_score (aucpr on val): %.6f", best_score)

# ── STAGE 4: Predict using best iteration ──
proba = estimator.predict_proba(X_val_t)[:, 1]
metrics = compute_validation_metrics(
    y_val.values, proba,
    k_pcts=cfg["metrics"]["at_k_percents"],
    model_name=f"XGB_ne{NE}_md{MD}_lr{LR_RATE}_es{EARLY_STOP}_90d",
)
metrics.update({
    "family": "XGBoost", "horizon": "90d", "early_stopping": True,
    "early_stopping_rounds": EARLY_STOP, "best_iteration": best_iter,
    "best_score_aucpr_val": best_score, "elapsed_s": round(elapsed, 1),
    "xgboost_version": xgb.__version__,
    "params": {"n_estimators": NE, "max_depth": MD, "learning_rate": LR_RATE,
               "subsample": 0.8, "colsample_bytree": 0.8, "seed": SEED},
    "note": "Provisional - model fitted on 1M stratified subsample",
})
log.info("  AP=%.4f  ROC=%.4f  Brier=%.4f", metrics["Average Precision (AP)"], metrics["ROC-AUC"], metrics["Brier"])

# ── STAGE 5: Serialize self-contained artifact ──
prep_path  = os.path.join(ARTIFACT_DIR, "preprocessor.joblib")
model_path = os.path.join(ARTIFACT_DIR, "model.joblib")
meta_path  = os.path.join(ARTIFACT_DIR, "metadata.json")

joblib.dump(preprocessor, prep_path, compress=3)
joblib.dump(estimator,    model_path, compress=3)
with open(meta_path, "w") as f:
    json.dump(metrics, f, indent=2, default=str)
log.info("Artifact written: %s", ARTIFACT_DIR)

# ── STAGE 6: Read-back prediction equality test ──
log.info("Read-back test ...")
prep2  = joblib.load(prep_path)
model2 = joblib.load(model_path)
X_val_t2 = prep2.transform(X_val)
proba2   = model2.predict_proba(X_val_t2)[:, 1]

allclose = np.allclose(proba, proba2, atol=1e-6)
max_diff = float(np.max(np.abs(proba - proba2)))
log.info("  Read-back np.allclose(atol=1e-6): %s", allclose)
log.info("  Max abs prediction diff: %.2e", max_diff)

metrics["readback_allclose"] = allclose
metrics["readback_max_diff"] = max_diff
with open(meta_path, "w") as f:
    json.dump(metrics, f, indent=2, default=str)

# ── PART 4 REPORT ──
print()
print("=" * 70)
print("PART 4 - XGB EARLY STOPPING REPORT")
print("=" * 70)
print(f"  XGBoost version:          {xgb.__version__}")
print(f"  n_estimators (max):       {NE}")
print(f"  max_depth:                {MD}")
print(f"  learning_rate:            {LR_RATE}")
print(f"  early_stopping_rounds:    {EARLY_STOP}")
print(f"  best_iteration:           {best_iter}")
print(f"  best_score (aucpr/val):   {best_score:.6f}")
print(f"  AP on val:                {metrics['Average Precision (AP)']:.4f}")
print(f"  ROC-AUC on val:           {metrics['ROC-AUC']:.4f}")
print(f"  Elapsed:                  {elapsed:.1f}s")
print("  Artifact format:          preprocessor.joblib + model.joblib + metadata.json")
print(f"  Artifact path:            {ARTIFACT_DIR}")
print(f"  Read-back allclose:       {allclose}")
print(f"  Read-back max diff:       {max_diff:.2e}")
print("  Sealed test used:         NO")

if __name__ == "__main__":
    pass
