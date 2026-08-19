# ruff: noqa: E402
"""
scripts/phase_5_audit_lr_convergence.py

Part 5 — LR convergence audit.

saga verdict: COMPUTATIONALLY INFEASIBLE on current hardware.
  - 1M rows x 201 features x 3000 epochs = ~3 billion SGD updates.
  - Killed after 48 minutes with no convergence progress.
  - saga is excluded from model promotion; documented as infeasible.

lbfgs at max_iter=2000, tol=1e-4: tested here.
  - Uses full gradient per iteration (O(n*d) per step).
  - ~2000 * 201M ops = ~0.4T ops; estimated 15-25 min.
"""
from __future__ import annotations

import gc
import json
import logging
import sys
import time
import warnings

import pandas as pd
import psutil

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split as _tts

from montreal_road_risk.modeling.metrics import compute_validation_metrics
from montreal_road_risk.modeling.preprocessing import (
    build_logistic_pipeline,
    prepare_Xy,
    resolve_feature_columns,
)

CFG = json.load(open("config/phase_5_modeling.json"))
P5 = "data/processed/phase_5"
SEED = CFG["seed"]
N_LIMIT = 1_000_000


def _mem_gb() -> float:
    return psutil.Process().memory_info().rss / 1e9


log.info("Loading 90d partitions ...")
train_df = pd.read_parquet(f"{P5}/train_90d.parquet")
val_df = pd.read_parquet(f"{P5}/val_90d.parquet")
if "target_eligible_90d" in train_df.columns:
    train_df = train_df[train_df["target_eligible_90d"] == 1]
    val_df = val_df[val_df["target_eligible_90d"] == 1]

cat_cols = CFG["categorical_cols"]
X_full, y_full = prepare_Xy(train_df, "target_repair_90d", CFG, cat_cols)
X_val, y_val = prepare_Xy(val_df, "target_repair_90d", CFG, cat_cols)
del train_df, val_df
gc.collect()

X_train, _, y_train, _ = _tts(
    X_full, y_full, train_size=N_LIMIT, stratify=y_full, random_state=SEED
)
del X_full, y_full
gc.collect()

num_cols, cat_cols_r, bin_cols, _ = resolve_feature_columns(X_train, CFG)
log.info("Train: %d | Val: %d | RSS=%.2f GB", len(X_train), len(X_val), _mem_gb())

results = []

# ── saga: documented as infeasible ──────────────────────────────────────────
saga_result = {
    "name": "LR_saga_C0.1_mi3000",
    "solver": "saga",
    "C": 0.1,
    "max_iter": 3000,
    "tol": 1e-4,
    "n_iter_": None,
    "converged": False,
    "convergence_warnings": None,
    "elapsed_s": ">2880 (killed at 48 min)",
    "rss_before_gb": 4.33,
    "rss_peak_gb": None,
    "AP": None,
    "ROC": None,
    "Brier": None,
    "promotion_eligible": False,
    "note": (
        "COMPUTATIONALLY INFEASIBLE — saga on 1M x 201 features x 3000 epochs "
        "requires ~3 billion SGD updates. Killed after 48 min with no convergence "
        "output. Excluded from model promotion."
    ),
}
results.append(saga_result)
log.info("saga: INFEASIBLE (documented, skipped)")

# ── lbfgs at 2000 iterations ─────────────────────────────────────────────────
name = "LR_lbfgs_C0.1_mi2000"
log.info("TRAINING: %s", name)
rss_before = _mem_gb()
t0 = time.time()

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    estimator = LogisticRegression(
        C=0.1,
        solver="lbfgs",
        max_iter=2000,
        tol=1e-4,
        random_state=SEED,
        penalty="l2",
    )
    pipeline = build_logistic_pipeline(estimator, num_cols, cat_cols_r, bin_cols)
    pipeline.fit(X_train, y_train)

elapsed = time.time() - t0
rss_peak = _mem_gb()

conv_warns = [w for w in caught if "ConvergenceWarning" in str(w.category)]
lr_est = pipeline[-1]
n_iter_val = int(getattr(lr_est, "n_iter_", [0])[0])
converged = n_iter_val < 2000

proba = pipeline.predict_proba(X_val)[:, 1]
metrics = compute_validation_metrics(
    y_val.values, proba,
    k_pcts=CFG["metrics"]["at_k_percents"],
    model_name=name,
)

lbfgs_result = {
    "name": name,
    "solver": "lbfgs",
    "C": 0.1,
    "max_iter": 2000,
    "tol": 1e-4,
    "n_iter_": n_iter_val,
    "converged": converged,
    "convergence_warnings": len(conv_warns),
    "elapsed_s": round(elapsed, 1),
    "rss_before_gb": round(rss_before, 2),
    "rss_peak_gb": round(rss_peak, 2),
    "AP": metrics["Average Precision (AP)"],
    "ROC": metrics["ROC-AUC"],
    "Brier": metrics["Brier"],
    "promotion_eligible": converged,
    "note": (
        "Converged — eligible for model comparison"
        if converged
        else "NON-CONVERGED DIAGNOSTIC RESULT — excluded from model promotion"
    ),
}
results.append(lbfgs_result)
log.info(
    "  n_iter=%d converged=%s AP=%.4f ROC=%.4f elapsed=%.1fs",
    n_iter_val, converged, lbfgs_result["AP"], lbfgs_result["ROC"], elapsed,
)

print()
print("=" * 70)
print("PART 5 - LOGISTIC REGRESSION CONVERGENCE REPORT")
print("=" * 70)

for r in results:
    print(f"\n  Config: {r['name']}")
    for k in [
        "solver", "max_iter", "tol", "n_iter_", "converged",
        "convergence_warnings", "elapsed_s", "rss_peak_gb",
        "AP", "ROC", "Brier", "promotion_eligible", "note",
    ]:
        print(f"    {k:<28s}: {r[k]}")

json.dump(
    results,
    open("models/phase_5/audit_lr_convergence.json", "w"),
    indent=2, default=str,
)
print("\nWritten: models/phase_5/audit_lr_convergence.json")
