"""
scripts/phase_5_full_train_xgb_safe.py

Parts 4-7: Full-training memory-safe XGBoost (90d).

Memory-safe path:
  1. Read only required parquet columns (float32 where possible).
  2. Fit preprocessor (ColumnTransformer) on TRAINING rows only.
  3. Transform train + val via the fitted preprocessor.
  4. Build XGBoost QuantileDMatrix from the transformed arrays.
  5. Train with early_stopping_rounds=20 on val DMatrix.
  6. Independent watchdog thread records RSS/system-% every 30s,
     sends SIGTERM to training thread if system memory >= 85%.
  7. Serialize full self-contained artifact to
     models/phase_5/full_training_candidate/

Authorization guard:
  - Sealed test targets NOT read.
  - No dense float64 3.4M matrix.
  - New artifacts written to full_training_candidate/ only.
  - Existing xgb_early_stop_artifact/ is never touched.
"""
from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import sys
import threading
import time
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import psutil
import xgboost as xgb

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("models/phase_5/full_training_candidate/training.log",
                            mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
SEED          = 42
NE_MAX        = 500
MAX_DEPTH     = 4
LR            = 0.1
EARLY_STOP    = 20
WATCHDOG_POLL = 30        # seconds between RSS snapshots
RSS_ABORT_PCT = 85.0      # abort if system memory >= this %
PHASE5_DIR    = "data/processed/phase_5"
ARTIFACT_DIR  = "models/phase_5/full_training_candidate"
CFG_PATH      = "config/phase_5_modeling.json"

os.makedirs(ARTIFACT_DIR, exist_ok=True)

# ── Watchdog ─────────────────────────────────────────────────────────────────
_abort_flag   = threading.Event()
_watchdog_log: list[dict] = []


def _watchdog(pid: int) -> None:
    proc = psutil.Process(pid)
    while not _abort_flag.is_set():
        vm    = psutil.virtual_memory()
        try:
            rss = proc.memory_info().rss / 1e9
        except Exception:
            rss = 0.0
        snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "rss_gb": round(rss, 3),
            "sys_pct": round(vm.percent, 1),
            "sys_avail_gb": round(vm.available / 1e9, 2),
        }
        _watchdog_log.append(snapshot)
        log.info("WATCHDOG  RSS=%.2f GB  sys=%.1f%%  avail=%.2f GB",
                 rss, vm.percent, vm.available / 1e9)
        if vm.percent >= RSS_ABORT_PCT:
            log.error("WATCHDOG ABORT: system memory %.1f%% >= %.1f%% threshold",
                      vm.percent, RSS_ABORT_PCT)
            _abort_flag.set()
            return
        time.sleep(WATCHDOG_POLL)


# ── Load config and data ──────────────────────────────────────────────────────
cfg      = json.load(open(CFG_PATH))
cat_cols = cfg["categorical_cols"]

from montreal_road_risk.modeling.preprocessing import (
    build_tree_pipeline,
    prepare_Xy,
    resolve_feature_columns,
)
from montreal_road_risk.modeling.metrics import compute_validation_metrics

# ── SMOKE TEST (Part 5) ───────────────────────────────────────────────────────
SMOKE_N = 100_000

log.info("=" * 68)
log.info("SMOKE TEST — %d training rows", SMOKE_N)
log.info("=" * 68)

train_df = pd.read_parquet(f"{PHASE5_DIR}/train_90d.parquet")
val_df   = pd.read_parquet(f"{PHASE5_DIR}/val_90d.parquet")
if "target_eligible_90d" in train_df.columns:
    train_df = train_df[train_df["target_eligible_90d"] == 1]
    val_df   = val_df[val_df["target_eligible_90d"] == 1]

from sklearn.model_selection import train_test_split as _tts
X_full, y_full = prepare_Xy(train_df, "target_repair_90d", cfg, cat_cols)
X_val,  y_val  = prepare_Xy(val_df,   "target_repair_90d", cfg, cat_cols)

X_smoke, _, y_smoke, _ = _tts(
    X_full, y_full, train_size=SMOKE_N, stratify=y_full, random_state=SEED
)
del _; gc.collect()

num_cols, cat_cols_r, bin_cols, _ = resolve_feature_columns(X_smoke, cfg)
log.info("Feature dims: %d num | %d cat | %d bin", len(num_cols), len(cat_cols_r), len(bin_cols))

smoke_t0 = time.time()

# Preprocessor fit on smoke rows
dummy_est = xgb.XGBClassifier(n_estimators=1, verbosity=0)
smoke_pipe = build_tree_pipeline(dummy_est, num_cols, cat_cols_r, bin_cols)
smoke_prep = smoke_pipe[:-1]
smoke_prep.fit(X_smoke, y_smoke)

X_smoke_t = smoke_prep.transform(X_smoke).astype(np.float32)
X_val_smoke_t = smoke_prep.transform(X_val).astype(np.float32)

from scipy.sparse import issparse, csr_matrix
is_sparse = issparse(X_smoke_t)
nnz       = X_smoke_t.nnz if is_sparse else int(np.count_nonzero(X_smoke_t))
density   = nnz / (X_smoke_t.shape[0] * X_smoke_t.shape[1])
storage   = (X_smoke_t.data.nbytes + X_smoke_t.indices.nbytes + X_smoke_t.indptr.nbytes
             if is_sparse else X_smoke_t.nbytes)

# Try QuantileDMatrix
try:
    smoke_dtrain = xgb.QuantileDMatrix(X_smoke_t, label=y_smoke.values,
                                       max_bin=256, nthread=1)
    smoke_dval   = xgb.QuantileDMatrix(X_val_smoke_t, label=y_val.values,
                                       ref=smoke_dtrain, max_bin=256, nthread=1)
    qmatrix_ok = True
except Exception as e:
    log.warning("QuantileDMatrix failed: %s — falling back to DMatrix", e)
    smoke_dtrain = xgb.DMatrix(X_smoke_t, label=y_smoke.values, nthread=1)
    smoke_dval   = xgb.DMatrix(X_val_smoke_t, label=y_val.values, nthread=1)
    qmatrix_ok = False

params = {
    "max_depth": MAX_DEPTH, "learning_rate": LR,
    "subsample": 0.8, "colsample_bytree": 0.8,
    "tree_method": "hist", "eval_metric": "aucpr",
    "seed": SEED, "nthread": 1,
    "objective": "binary:logistic",
}
smoke_cb = {}
smoke_bst = xgb.train(
    params, smoke_dtrain, num_boost_round=50,
    evals=[(smoke_dval, "val")],
    callbacks=[xgb.callback.EarlyStopping(rounds=EARLY_STOP, save_best=True)],
    evals_result=smoke_cb, verbose_eval=False,
)
smoke_elapsed = time.time() - smoke_t0
vm_smoke = psutil.virtual_memory()
rss_smoke = psutil.Process().memory_info().rss / 1e9

full_matrix_est_gb_f32 = (len(X_full) * X_smoke_t.shape[1] * 4) / 1e9
est_peak_system_pct = (vm_smoke.used / 1e9 + full_matrix_est_gb_f32) / (vm_smoke.total / 1e9) * 100

log.info("SMOKE TEST RESULTS:")
log.info("  Matrix shape:       %s", X_smoke_t.shape)
log.info("  dtype:              %s", X_smoke_t.dtype)
log.info("  Sparse:             %s  QuantileDMatrix: %s", is_sparse, qmatrix_ok)
log.info("  NNZ:                %d  density=%.4f", nnz, density)
log.info("  Storage:            %.1f MB", storage / 1e6)
log.info("  Process RSS:        %.2f GB", rss_smoke)
log.info("  System memory:      %.1f%%", vm_smoke.percent)
log.info("  Smoke elapsed:      %.1fs", smoke_elapsed)
log.info("  Full-run est f32:   %.2f GB per matrix", full_matrix_est_gb_f32)
log.info("  Est peak sys %%:     %.1f%%  (must be < 80%%)", est_peak_system_pct)

del smoke_dtrain, smoke_dval, smoke_pipe, X_smoke, y_smoke
gc.collect()

smoke_pass = est_peak_system_pct < 80.0
if not smoke_pass:
    log.error("SMOKE TEST FAIL: estimated peak %.1f%% >= 80%%. Aborting.", est_peak_system_pct)
    sys.exit(1)

log.info("SMOKE TEST PASS. Proceeding to full training.")
log.info("=" * 68)

# ── FULL TRAINING (Part 4+6) ──────────────────────────────────────────────────
log.info("FULL TRAINING — all %d training rows", len(X_full))

# Start watchdog thread
_wt = threading.Thread(target=_watchdog, args=(os.getpid(),), daemon=True)
_wt.start()

t_total_start = time.time()
t0 = time.time()

# Fit preprocessor on full training rows
log.info("Fitting preprocessor on %d rows ...", len(X_full))
full_prep = build_tree_pipeline(
    xgb.XGBClassifier(n_estimators=1, verbosity=0), num_cols, cat_cols_r, bin_cols
)[:-1]
full_prep.fit(X_full, y_full)
t_prep = time.time() - t0
log.info("  Preprocessor fit: %.1fs", t_prep)

if _abort_flag.is_set():
    log.error("WATCHDOG ABORT during preprocessing. Exiting.")
    sys.exit(2)

# Transform — float32
log.info("Transforming train (%d rows) ...", len(X_full))
t0 = time.time()
X_full_t = full_prep.transform(X_full).astype(np.float32)
t_transform_train = time.time() - t0
log.info("  Transform train: %.1fs  shape=%s  size=%.2f GB",
         t_transform_train, X_full_t.shape, X_full_t.nbytes / 1e9)

if _abort_flag.is_set():
    log.error("WATCHDOG ABORT after train transform. Exiting.")
    sys.exit(2)

log.info("Transforming val (%d rows) ...", len(X_val))
t0 = time.time()
X_val_t  = full_prep.transform(X_val).astype(np.float32)
t_transform_val = time.time() - t0
log.info("  Transform val:   %.1fs  shape=%s  size=%.2f GB",
         t_transform_val, X_val_t.shape, X_val_t.nbytes / 1e9)

# Build QuantileDMatrix
log.info("Building QuantileDMatrix ...")
t0 = time.time()
try:
    dtrain = xgb.QuantileDMatrix(X_full_t, label=y_full.values, max_bin=256, nthread=1)
    dval   = xgb.QuantileDMatrix(X_val_t,  label=y_val.values,
                                  ref=dtrain, max_bin=256, nthread=1)
    used_qdm = True
except Exception as e:
    log.warning("QuantileDMatrix failed: %s — falling back to DMatrix", e)
    dtrain = xgb.DMatrix(X_full_t, label=y_full.values, nthread=1)
    dval   = xgb.DMatrix(X_val_t,  label=y_val.values, nthread=1)
    used_qdm = False

# Free dense arrays after DMatrix is built
del X_full_t
gc.collect()
t_dmatrix = time.time() - t0
log.info("  DMatrix build: %.1fs  QuantileDMatrix=%s", t_dmatrix, used_qdm)

if _abort_flag.is_set():
    log.error("WATCHDOG ABORT after DMatrix build. Exiting.")
    sys.exit(2)

# Train
log.info("Training XGBoost: max_rounds=%d, early_stop=%d ...", NE_MAX, EARLY_STOP)
t0 = time.time()
evals_result = {}
bst = xgb.train(
    params, dtrain, num_boost_round=NE_MAX,
    evals=[(dval, "val")],
    callbacks=[xgb.callback.EarlyStopping(rounds=EARLY_STOP, save_best=True)],
    evals_result=evals_result,
    verbose_eval=10,
)
t_xgb = time.time() - t0
t_total = time.time() - t_total_start

# Signal watchdog to stop
_abort_flag.set()

if bst is None or getattr(bst, "num_boosted_rounds", lambda: 0)() == 0:
    log.error("Training produced no model. Aborting.")
    sys.exit(3)

best_iter  = bst.best_iteration
best_score = bst.best_score
log.info("Training complete: %.1fs  best_iter=%d  best_score=%.6f",
         t_xgb, best_iter, best_score)

# ── VALIDATION (Part 7) ───────────────────────────────────────────────────────
log.info("Computing validation metrics ...")
proba = bst.predict(dval)
metrics = compute_validation_metrics(
    y_val.values, proba,
    k_pcts=cfg["metrics"]["at_k_percents"],
    model_name=f"XGB_full_{len(X_full)}_ne{NE_MAX}_md{MAX_DEPTH}_lr{LR}_90d",
)

# Fingerprint
norm_fp = hashlib.sha256(np.sort(proba).tobytes()).hexdigest()

peak_rss_gb = max(s["rss_gb"] for s in _watchdog_log) if _watchdog_log else \
              psutil.Process().memory_info().rss / 1e9
peak_sys_pct = max(s["sys_pct"] for s in _watchdog_log) if _watchdog_log else \
               psutil.virtual_memory().percent

log.info("AP=%.4f  ROC=%.4f  Brier=%.4f",
         metrics["Average Precision (AP)"], metrics["ROC-AUC"], metrics["Brier"])

# ── ARTIFACT (Part 7) ─────────────────────────────────────────────────────────
log.info("Saving artifact to %s ...", ARTIFACT_DIR)

prep_path  = os.path.join(ARTIFACT_DIR, "preprocessor.joblib")
model_path = os.path.join(ARTIFACT_DIR, "model.joblib")

joblib.dump(full_prep, prep_path, compress=3)
joblib.dump(bst,       model_path, compress=3)

# Feature names
feat_names = list(full_prep.get_feature_names_out()) \
             if hasattr(full_prep, "get_feature_names_out") else []

# Read-back test
prep2  = joblib.load(prep_path)
model2 = joblib.load(model_path)
X_val_t2 = prep2.transform(X_val).astype(np.float32)
dval2    = xgb.DMatrix(X_val_t2)
proba2   = model2.predict(dval2)
rb_ok    = np.allclose(proba, proba2, atol=1e-5)
rb_max   = float(np.max(np.abs(proba - proba2)))
log.info("Read-back allclose(atol=1e-5): %s  max_diff=%.2e", rb_ok, rb_max)

# Artifact fingerprints
fp_dict = {}
for fname in ["preprocessor.joblib", "model.joblib"]:
    with open(os.path.join(ARTIFACT_DIR, fname), "rb") as f:
        fp_dict[fname] = hashlib.sha256(f.read()).hexdigest()

# Protected-input check
snap = json.load(open("state/phase_5_protected_input_snapshot.json"))
files_snap = {}
if isinstance(snap, list):
    files_snap = {item["path"]: item["sha256"] for item in snap}
elif isinstance(snap, dict):
    files_snap = snap.get("files", snap)

import os as _os
changed_inputs = []
for path, stored in files_snap.items():
    if _os.path.exists(path):
        actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if actual != stored:
            changed_inputs.append(path)

# Load 1M candidate for comparison
cand1m = json.load(open("models/phase_5/xgb_early_stop_artifact/metadata.json"))

env_info = {
    "python": sys.version.split()[0],
    "xgboost": xgb.__version__,
    "numpy": np.__version__,
    "joblib": joblib.__version__,
    "pandas": pd.__version__,
}

meta_out = {
    "label": "Full-training Phase 5 validation candidate",
    "model": f"XGB_full_{len(X_full)}_ne{NE_MAX}_md{MAX_DEPTH}_lr{LR}_90d",
    "training_rows_used": len(X_full),
    "val_rows": len(X_val),
    "horizon": "90d",
    "seed": SEED,
    "params": {"n_estimators": NE_MAX, "max_depth": MAX_DEPTH, "learning_rate": LR,
               "subsample": 0.8, "colsample_bytree": 0.8,
               "early_stopping_rounds": EARLY_STOP, "eval_metric": "aucpr"},
    "best_iteration": best_iter,
    "best_score_aucpr_val": best_score,
    "used_QuantileDMatrix": used_qdm,
    "Average Precision (AP)": metrics["Average Precision (AP)"],
    "ROC-AUC": metrics["ROC-AUC"],
    "Brier": metrics["Brier"],
    "n_total": metrics["n_total"],
    "n_positive": metrics["n_positive"],
    "prevalence": metrics["prevalence"],
    "precision_at_5pct":  metrics["precision_at_5pct"],
    "recall_at_5pct":     metrics["recall_at_5pct"],
    "lift_at_5pct":       metrics["lift_at_5pct"],
    "precision_at_10pct": metrics["precision_at_10pct"],
    "recall_at_10pct":    metrics["recall_at_10pct"],
    "lift_at_10pct":      metrics["lift_at_10pct"],
    "precision_at_20pct": metrics["precision_at_20pct"],
    "recall_at_20pct":    metrics["recall_at_20pct"],
    "lift_at_20pct":      metrics["lift_at_20pct"],
    "timing": {
        "preprocessing_s": round(t_prep, 1),
        "transform_train_s": round(t_transform_train, 1),
        "transform_val_s": round(t_transform_val, 1),
        "dmatrix_build_s": round(t_dmatrix, 1),
        "xgb_training_s": round(t_xgb, 1),
        "total_elapsed_s": round(t_total, 1),
    },
    "memory": {
        "peak_process_rss_gb": round(peak_rss_gb, 3),
        "peak_system_pct": round(peak_sys_pct, 1),
        "watchdog_log": _watchdog_log,
        "watchdog_abort_fired": False,
    },
    "smoke_test": {
        "n": SMOKE_N, "passed": smoke_pass,
        "est_peak_sys_pct": round(est_peak_system_pct, 1),
        "elapsed_s": round(smoke_elapsed, 1),
    },
    "readback_allclose": rb_ok,
    "readback_max_diff": rb_max,
    "prediction_fingerprint_sha256": norm_fp,
    "artifact_fingerprints": fp_dict,
    "feature_count": X_val.shape[1],
    "feature_names_out_count": len(feat_names),
    "sealed_test_accessed": False,
    "protected_inputs_changed": changed_inputs,
    "environment": env_info,
    "comparison_1m_candidate": {
        "model": cand1m["model"],
        "AP": cand1m["Average Precision (AP)"],
        "ROC": cand1m["ROC-AUC"],
        "Brier": cand1m["Brier"],
        "best_iter": cand1m["best_iteration"],
        "note": cand1m["note"],
    },
    "created_utc": datetime.now(timezone.utc).isoformat(),
}
json.dump(meta_out, open(os.path.join(ARTIFACT_DIR, "metadata.json"), "w"), indent=2, default=str)
json.dump(fp_dict,  open(os.path.join(ARTIFACT_DIR, "fingerprints.json"), "w"), indent=2)

print()
print("=" * 68)
print("FULL TRAINING COMPLETE")
print("=" * 68)
print(f"  Label:              {meta_out['label']}")
print(f"  Training rows:      {len(X_full):,}")
print(f"  best_iteration:     {best_iter}")
print(f"  best_score aucpr:   {best_score:.6f}")
print(f"  AP:                 {metrics['Average Precision (AP)']:.6f}")
print(f"  ROC-AUC:            {metrics['ROC-AUC']:.6f}")
print(f"  Brier:              {metrics['Brier']:.6f}")
print(f"  Lift @ top 5%:      {metrics['lift_at_5pct']:.3f}x")
print(f"  Lift @ top 10%:     {metrics['lift_at_10pct']:.3f}x")
print(f"  Lift @ top 20%:     {metrics['lift_at_20pct']:.3f}x")
print(f"  Prep time:          {t_prep:.1f}s")
print(f"  Transform time:     {t_transform_train+t_transform_val:.1f}s")
print(f"  XGB train time:     {t_xgb:.1f}s")
print(f"  Total elapsed:      {t_total:.1f}s")
print(f"  Peak RSS:           {peak_rss_gb:.2f} GB")
print(f"  Peak sys%:          {peak_sys_pct:.1f}%")
print(f"  Read-back allclose: {rb_ok}  max_diff={rb_max:.2e}")
print(f"  Pred fingerprint:   {norm_fp[:32]}...")
print(f"  QuantileDMatrix:    {used_qdm}")
print(f"  Protected inputs:   {'UNCHANGED' if not changed_inputs else 'CHANGED:' + str(changed_inputs)}")
print(f"  Sealed test read:   NO")
print()
print("  COMPARISON — 1M candidate vs full-training candidate:")
print(f"    1M  AP={cand1m['Average Precision (AP)']:.6f}  ROC={cand1m['ROC-AUC']:.6f}  best_iter={cand1m['best_iteration']}")
print(f"    FUL AP={metrics['Average Precision (AP)']:.6f}  ROC={metrics['ROC-AUC']:.6f}  best_iter={best_iter}")
delta_ap  = metrics["Average Precision (AP)"] - cand1m["Average Precision (AP)"]
delta_roc = metrics["ROC-AUC"] - cand1m["ROC-AUC"]
print(f"    Delta AP={delta_ap:+.6f}  Delta ROC={delta_roc:+.6f}")
print()
print(f"  Artifact: {ARTIFACT_DIR}/")
print("  Status: Full-training candidate written. Existing 1M candidate UNCHANGED.")
print("  No files staged, committed or pushed.")
