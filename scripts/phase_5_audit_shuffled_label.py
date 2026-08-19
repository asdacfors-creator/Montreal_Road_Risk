# ruff: noqa: E402
"""
scripts/phase_5_audit_shuffled_label.py

Part 6B — Shuffled-label sanity test.
Shuffles training labels, fits XGBoost, checks that validation AP ~ prevalence.
Does NOT use the sealed test partition.
"""
from __future__ import annotations

import gc
import json
import logging
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

import xgboost as xgb
from sklearn.model_selection import train_test_split as _tts

from montreal_road_risk.modeling.metrics import compute_validation_metrics
from montreal_road_risk.modeling.preprocessing import (
    build_tree_pipeline,
    prepare_Xy,
    resolve_feature_columns,
)

CFG  = json.load(open("config/phase_5_modeling.json"))
P5   = "data/processed/phase_5"
SEED = CFG["seed"]
N_FIXTURE = 50_000   # bounded fixture as specified in audit

train_df = pd.read_parquet(f"{P5}/train_90d.parquet")
val_df   = pd.read_parquet(f"{P5}/val_90d.parquet")
if "target_eligible_90d" in train_df.columns:
    train_df = train_df[train_df["target_eligible_90d"]==1]
    val_df   = val_df[val_df["target_eligible_90d"]==1]

cat_cols = CFG["categorical_cols"]
X_full, y_full = prepare_Xy(train_df, "target_repair_90d", CFG, cat_cols)
X_val,  y_val  = prepare_Xy(val_df,   "target_repair_90d", CFG, cat_cols)
del train_df, val_df
gc.collect()

# Take bounded fixture
X_fix, _, y_fix, _ = _tts(
    X_full, y_full, train_size=N_FIXTURE, stratify=y_full, random_state=SEED
)
del X_full, y_full
gc.collect()

# Shuffle labels deterministically
rng = np.random.default_rng(seed=SEED)
y_shuffled = y_fix.values.copy()
rng.shuffle(y_shuffled)
prevalence = float(y_fix.mean())

log.info("Fixture: %d rows | prevalence=%.4f", N_FIXTURE, prevalence)
log.info("Shuffled label pos rate: %.4f", y_shuffled.mean())

num_cols, cat_cols_r, bin_cols, _ = resolve_feature_columns(X_fix, CFG)

estimator = xgb.XGBClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    tree_method="hist", n_jobs=1, random_state=SEED, verbosity=0,
)
pipeline = build_tree_pipeline(estimator, num_cols, cat_cols_r, bin_cols)
pipeline.fit(X_fix, y_shuffled)

proba_shuf = pipeline.predict_proba(X_val)[:, 1]
metrics_shuf = compute_validation_metrics(
    y_val.values, proba_shuf,
    k_pcts=CFG["metrics"]["at_k_percents"],
    model_name="shuffled_label_sanity",
)

val_prevalence = float(y_val.mean())
ap_shuf = metrics_shuf["Average Precision (AP)"]
ap_near_prev = abs(ap_shuf - val_prevalence) < 0.03

print()
print("=" * 70)
print("PART 6B - SHUFFLED-LABEL SANITY TEST")
print("=" * 70)
print(f"  Fixture size:             {N_FIXTURE:,} rows")
print(f"  Fixture prevalence:       {prevalence:.6f}")
print(f"  Shuffled label pos rate:  {y_shuffled.mean():.6f}")
print(f"  Val prevalence:           {val_prevalence:.6f}")
print(f"  Shuffled AP on val:       {ap_shuf:.6f}")
print(f"  Expected (near prev):     {val_prevalence:.6f}")
print(f"  |AP_shuf - prevalence|:   {abs(ap_shuf - val_prevalence):.6f}")
print(f"  AP collapses to prev:     {'PASS' if ap_near_prev else 'FAIL'}")
print("  Sealed test used:         NO")

result = {
    "fixture_n": N_FIXTURE, "fixture_prevalence": prevalence,
    "val_prevalence": val_prevalence, "shuffled_ap": ap_shuf,
    "ap_near_prevalence": bool(ap_near_prev), "threshold": 0.03,
    "verdict": "PASS" if ap_near_prev else "FAIL",
}
json.dump(result, open("models/phase_5/audit_shuffled_label.json","w"), indent=2)
print("Written: models/phase_5/audit_shuffled_label.json")
