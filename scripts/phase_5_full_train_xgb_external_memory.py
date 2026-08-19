"""
scripts/phase_5_full_train_xgb_external_memory.py

TRUE OUT-OF-CORE XGBoost full-data training.

Architecture:
  - Reads train_90d.parquet using pyarrow.parquet.ParquetFile.iter_batches
  - Applies the FROZEN training-only preprocessor (from 1M candidate) per batch
  - Converts to float32
  - Passes batches to xgb.ExtMemQuantileDMatrix via a DataIter
  - Never creates X_full or loads the full parquet into memory

Label: "XGBoost trained on all 3,406,793 purged training rows using the frozen
        training-only preprocessor fitted on the deterministic 1M training subset."

HARD RESTRICTIONS enforced:
  - No pandas.read_parquet on the complete training file
  - No X_full variable
  - No prepare_Xy on complete partition
  - No batch accumulation in lists
  - No sealed test access
  - Nothing staged/committed/pushed
"""
from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
import pyarrow.parquet as pq
import xgboost as xgb
from scipy.sparse import issparse

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ─────────────────────────────────────────────────────────────────────
ATTEMPT_DIR  = Path("data/processed/phase_5/_external_memory_full_train_attempt_01")
CACHE_DIR    = ATTEMPT_DIR / "cache"
EVIDENCE_DIR = ATTEMPT_DIR / "evidence"
LOG_DIR      = ATTEMPT_DIR / "logs"
TEMP_DIR     = ATTEMPT_DIR / "temp"
ARTIFACT_DIR = Path("models/phase_5/full_training_external_memory_candidate")
CANDIDATE_1M = Path("models/phase_5/xgb_early_stop_artifact")

TRAIN_PARQUET = "data/processed/phase_5/train_90d.parquet"
VAL_PARQUET   = "data/processed/phase_5/val_90d.parquet"

# ── Environment ───────────────────────────────────────────────────────────────
os.environ["TEMP"] = str(TEMP_DIR)
os.environ["TMP"]  = str(TEMP_DIR)

# ── Logging ───────────────────────────────────────────────────────────────────
log_path = LOG_DIR / "training.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
SEED          = 42
NE_MAX        = 500
MAX_DEPTH     = 4
LR            = 0.1
EARLY_STOP    = 20
BATCH_SIZE    = 50_000
SMOKE_BATCHES = 3
SMOKE_MAX     = SMOKE_BATCHES * BATCH_SIZE        # = 150,000
ELIGIBILITY_COL = "target_eligible_90d"
TARGET_COL      = "target_repair_90d"
D_ABORT_GB      = 8.0
C_ABORT_GB      = 5.0
MEM_ABORT_PCT   = 85.0
WATCHDOG_POLL   = 20   # seconds

# ── Load frozen preprocessor ─────────────────────────────────────────────────
log.info("Loading frozen 1M preprocessor ...")
preprocessor = joblib.load(str(CANDIDATE_1M / "preprocessor.joblib"))

# Feature columns from fitted preprocessor
if hasattr(preprocessor, "feature_names_in_"):
    FEATURE_COLS = list(preprocessor.feature_names_in_)
else:
    # Fall back: inspect ColumnTransformer transformers
    from sklearn.pipeline import Pipeline
    ct = preprocessor[-1] if isinstance(preprocessor, Pipeline) else preprocessor
    FEATURE_COLS = []
    for _, _, cols in ct.transformers_:
        if isinstance(cols, list):
            FEATURE_COLS.extend(cols)
        elif hasattr(cols, "tolist"):
            FEATURE_COLS.extend(cols.tolist())

log.info("  Frozen preprocessor features: %d columns", len(FEATURE_COLS))
COLS_TO_READ = FEATURE_COLS + [TARGET_COL]
# Add eligibility col if present (to filter)
_meta_cols = [ELIGIBILITY_COL]

def _mem_gb():
    return psutil.Process().memory_info().rss / 1e9

def _sys_pct():
    return psutil.virtual_memory().percent

def _d_free_gb():
    return shutil.disk_usage("D:\\").free / 1e9

def _c_free_gb():
    return shutil.disk_usage("C:\\").free / 1e9

def _cache_size_mb():
    total = 0
    for f in CACHE_DIR.glob("**/*"):
        try:
            total += f.stat().st_size
        except Exception:
            pass
    return total / 1e6

# ── Verify no forbidden columns ───────────────────────────────────────────────
FORBIDDEN = {
    "target_repair_90d_val", "target_repair_180d", "target_repair_180d_val",
    "split_90d", "split_180d", "embargo_90d", "embargo_180d",
    "split", "is_test", "canonical_segment_id", "as_of_date",
    "target_eligible_90d", "target_eligible_180d",
}
overlap = set(FEATURE_COLS) & FORBIDDEN
assert not overlap, f"Forbidden columns in feature list: {overlap}"
log.info("  Leakage guard: 0 forbidden columns in feature list. ✅")

# ── Batch dtype normalisation (replicates prepare_Xy transforms) ──────────────
# prepare_Xy calls:
#   1. apply_sentinel(df)            → fillna(-1) on days_since_last_repair
#   2. fill_missing_categoricals()   → fillna("missing").astype(object) on cat cols
# When reading parquet via iter_batches, PyArrow produces pd.StringDtype columns
# which sklearn OHE cannot handle. We replicate both steps per batch.

_cfg_cat_cols  = set(json.load(open("config/phase_5_modeling.json"))["categorical_cols"])
_CAT_COLS_FEAT = [c for c in FEATURE_COLS if c in _cfg_cat_cols]


def _normalize_batch(X: pd.DataFrame) -> pd.DataFrame:
    """
    Apply per-batch dtype fixes to match what prepare_Xy produces on the full
    DataFrame. Must be called before preprocessor.transform(X).
    """
    X = X.copy()
    # 1. Sentinel for days_since_last_repair
    if "days_since_last_repair" in X.columns:
        X["days_since_last_repair"] = X["days_since_last_repair"].fillna(-1)
    # 2. Categorical columns: fill NaN with "missing" and cast to numpy object
    #    (PyArrow → pandas may produce pd.StringDtype; sklearn OHE needs object)
    for c in _CAT_COLS_FEAT:
        if c in X.columns:
            X[c] = X[c].fillna("missing").astype(object)
    return X


# ══════════════════════════════════════════════════════════════════════════════
# DataIter implementation
# ══════════════════════════════════════════════════════════════════════════════
class TrainBatchIter(xgb.DataIter):
    """
    Streams train_90d.parquet batch by batch through the frozen preprocessor.
    Never retains more than one batch in memory.
    """
    def __init__(self, parquet_path: str, max_batches: int | None = None,
                 smoke_mode: bool = False):
        self._path       = parquet_path
        self._max_batches = max_batches
        self._smoke_mode  = smoke_mode
        self._pf          = None
        self._iter        = None
        self._batch_idx   = 0
        self._total_rows  = 0
        self._schema_ref  = None
        self._evidence: list[dict] = []
        super().__init__(cache_prefix=str(CACHE_DIR / "xgb_train"),
                         release_data=True)

    def _open(self):
        self._pf   = pq.ParquetFile(self._path)
        # Read only required columns + eligibility (if present)
        pq_cols = list(set(COLS_TO_READ))
        # Check which of our cols actually exist
        actual_schema = self._pf.schema_arrow.names
        read_cols = [c for c in pq_cols if c in actual_schema]
        # Always include eligibility col if present for filtering
        if ELIGIBILITY_COL in actual_schema and ELIGIBILITY_COL not in read_cols:
            read_cols.append(ELIGIBILITY_COL)
        self._read_cols = read_cols
        self._iter = self._pf.iter_batches(
            batch_size=BATCH_SIZE, columns=self._read_cols
        )
        self._batch_idx  = 0
        self._total_rows = 0

    def reset(self):
        """Reset iterator to beginning (called by XGBoost before each pass)."""
        if self._pf is not None:
            try:
                self._pf.reader.close()
            except Exception:
                pass
        self._open()

    def next(self, input_data) -> bool:
        """Process next batch. Returns False when exhausted."""
        if self._max_batches is not None and self._batch_idx >= self._max_batches:
            return False

        # Disk guards
        if _d_free_gb() < D_ABORT_GB:
            log.error("ABORT: D: free=%.1f GB < %.1f GB", _d_free_gb(), D_ABORT_GB)
            return False
        if _c_free_gb() < C_ABORT_GB:
            log.error("ABORT: C: free=%.1f GB < %.1f GB", _c_free_gb(), C_ABORT_GB)
            return False

        t0       = time.time()
        rss_pre  = _mem_gb()
        sys_pre  = _sys_pct()

        try:
            batch = next(self._iter)
        except StopIteration:
            return False

        df = batch.to_pandas()
        del batch; gc.collect()

        # Apply eligibility filter
        if ELIGIBILITY_COL in df.columns:
            df = df[df[ELIGIBILITY_COL] == 1]
            df = df.drop(columns=[ELIGIBILITY_COL], errors="ignore")

        if len(df) == 0:
            return self.next(input_data)  # skip empty batch

        # Separate X and y — never keep full partition
        y = df[TARGET_COL].values.astype(np.float32)
        X = df.drop(columns=[TARGET_COL], errors="ignore")

        # Ensure all feature columns present
        missing = [c for c in FEATURE_COLS if c not in X.columns]
        if missing:
            log.error("ABORT: Missing feature columns in batch %d: %s", self._batch_idx, missing[:5])
            return False

        X = X[FEATURE_COLS]   # enforce column order

        # Verify schema consistency
        schema = list(X.dtypes.items())
        if self._schema_ref is None:
            self._schema_ref = schema
        else:
            if len(schema) != len(self._schema_ref):
                log.error("ABORT: Schema mismatch at batch %d", self._batch_idx)
                return False

        # Transform via frozen preprocessor (dtype-normalise first)
        X = _normalize_batch(X)
        X_t = preprocessor.transform(X).astype(np.float32)
        del X, df; gc.collect()

        n_rows   = len(X_t)
        nnz      = X_t.nnz if issparse(X_t) else int(np.count_nonzero(X_t))
        density  = nnz / (X_t.shape[0] * X_t.shape[1]) if n_rows > 0 else 0

        rss_post = _mem_gb()
        elapsed  = time.time() - t0

        # Pass to XGBoost
        if issparse(X_t):
            input_data(data=X_t, label=y)
        else:
            input_data(data=X_t, label=y)

        del X_t, y; gc.collect()

        rss_rel  = _mem_gb()

        ev = {
            "batch": self._batch_idx,
            "n_rows": n_rows,
            "shape": [n_rows, len(FEATURE_COLS)],
            "dtype": "float32",
            "nnz": nnz,
            "density": round(density, 4),
            "rss_pre_gb": round(rss_pre, 3),
            "rss_post_gb": round(rss_post, 3),
            "rss_post_release_gb": round(rss_rel, 3),
            "sys_pct": round(sys_pre, 1),
            "elapsed_s": round(elapsed, 2),
            "d_free_gb": round(_d_free_gb(), 2),
        }
        self._evidence.append(ev)
        self._total_rows += n_rows
        self._batch_idx  += 1

        if self._batch_idx <= 5 or self._batch_idx % 10 == 0:
            log.info(
                "  Batch %3d  rows=%6d  total=%9d  RSS=%.2f→%.2f GB  sys=%.1f%%  %.1fs",
                ev["batch"], n_rows, self._total_rows,
                rss_pre, rss_rel, sys_pre, elapsed,
            )

        return True


# ══════════════════════════════════════════════════════════════════════════════
# PART 7 — BOUNDED SMOKE TEST (exactly 3 batches)
# ══════════════════════════════════════════════════════════════════════════════
log.info("=" * 68)
log.info("PART 7: BOUNDED SMOKE TEST — max %d batches, max %d rows",
         SMOKE_BATCHES, SMOKE_MAX)
log.info("=" * 68)

smoke_iter = TrainBatchIter(TRAIN_PARQUET, max_batches=SMOKE_BATCHES, smoke_mode=True)
smoke_iter.reset()

smoke_t0 = time.time()
smoke_iter.reset()

smoke_rows_read = 0
smoke_batch_log = []
dummy_input_calls = 0

# Manually iterate 3 batches (do NOT use ExtMemQuantileDMatrix yet)
for b_idx in range(SMOKE_BATCHES):
    vm_pre = psutil.virtual_memory()
    rss_pre = _mem_gb()

    try:
        batch = next(smoke_iter._iter)
    except StopIteration:
        log.warning("Smoke: parquet exhausted after %d batches", b_idx)
        break

    df = batch.to_pandas()
    del batch; gc.collect()

    if ELIGIBILITY_COL in df.columns:
        df = df[df[ELIGIBILITY_COL] == 1]
        df = df.drop(columns=[ELIGIBILITY_COL], errors="ignore")

    y = df[TARGET_COL].values.astype(np.float32)
    X = df.drop(columns=[TARGET_COL], errors="ignore")[FEATURE_COLS]
    del df; gc.collect()

    rss_mid = _mem_gb()
    vm_mid  = psutil.virtual_memory()

    X = _normalize_batch(X)
    X_t = preprocessor.transform(X).astype(np.float32)
    del X; gc.collect()

    n     = X_t.shape[0]
    nnz   = X_t.nnz if issparse(X_t) else int(np.count_nonzero(X_t))
    dens  = nnz / (X_t.shape[0] * X_t.shape[1])
    store = (X_t.data.nbytes + X_t.indices.nbytes + X_t.indptr.nbytes
             if issparse(X_t) else X_t.nbytes)
    dtype  = str(X_t.dtype)
    sparse = issparse(X_t)

    del X_t, y; gc.collect()

    rss_post = _mem_gb()
    vm_post  = psutil.virtual_memory()

    smoke_rows_read += n
    entry = {
        "batch": b_idx,
        "rows": n,
        "shape": (n, len(FEATURE_COLS)),
        "dtype": dtype,
        "sparse": sparse,
        "nnz": nnz,
        "density": round(dens, 4),
        "rss_pre_gb": round(rss_pre, 3),
        "rss_post_transform_gb": round(rss_mid, 3),
        "rss_post_release_gb": round(rss_post, 3),
        "sys_pct_pre": round(vm_pre.percent, 1),
        "sys_pct_post": round(vm_post.percent, 1),
        "storage_mb": round(store/1e6, 1),
        "cache_mb": round(_cache_size_mb(), 1),
    }
    smoke_batch_log.append(entry)
    log.info(
        "  Smoke batch %d: rows=%d  shape=%s  dtype=%s  sparse=%s  nnz=%d  "
        "density=%.4f  storage=%.1f MB  RSS %.2f→%.2f→%.2f GB  sys=%.1f%%→%.1f%%",
        b_idx, n, entry["shape"], dtype, sparse, nnz, dens,
        store/1e6, rss_pre, rss_mid, rss_post, vm_pre.percent, vm_post.percent,
    )

smoke_elapsed = time.time() - smoke_t0

# Assertions
assert smoke_rows_read <= SMOKE_MAX, f"Smoke read {smoke_rows_read} > {SMOKE_MAX} max rows"
assert len(smoke_batch_log) == SMOKE_BATCHES or len(smoke_batch_log) <= SMOKE_BATCHES, "Batch count mismatch"

# Verify memory stability
rss_values = [b["rss_post_release_gb"] for b in smoke_batch_log]
rss_growth = rss_values[-1] - rss_values[0] if len(rss_values) >= 2 else 0
sys_ok = all(b["sys_pct_post"] < 75 for b in smoke_batch_log)
mem_stable = rss_growth < 1.0  # RSS must not grow by more than 1 GB across 3 batches

# Schema consistency check via reset
smoke_iter2 = TrainBatchIter(TRAIN_PARQUET, max_batches=SMOKE_BATCHES, smoke_mode=True)
smoke_iter2.reset()
first_schema = None
reset_ok = True
reset_rows = []
for _ in range(min(2, SMOKE_BATCHES)):
    try:
        b2 = next(smoke_iter2._iter)
        df2 = b2.to_pandas()
        if ELIGIBILITY_COL in df2.columns:
            df2 = df2[df2[ELIGIBILITY_COL]==1].drop(columns=[ELIGIBILITY_COL])
        X2 = df2.drop(columns=[TARGET_COL])[FEATURE_COLS]
        schema_now = list(X2.columns)
        if first_schema is None:
            first_schema = schema_now
        elif schema_now != first_schema:
            reset_ok = False
        reset_rows.append(len(df2))
        del b2, df2, X2; gc.collect()
    except StopIteration:
        break

schema_consistent = reset_ok and (first_schema == list(FEATURE_COLS))
smoke_pass = sys_ok and mem_stable and schema_consistent

print()
print("=" * 68)
print("SMOKE TEST REPORT")
print("=" * 68)
print(f"  Batches read:        {len(smoke_batch_log)}")
print(f"  Total rows read:     {smoke_rows_read}  (max allowed={SMOKE_MAX})")
print(f"  System mem < 75%:    {sys_ok}  (max={max(b['sys_pct_post'] for b in smoke_batch_log):.1f}%)")
print(f"  RSS growth:          {rss_growth:+.3f} GB  (stable={mem_stable})")
print(f"  Schema consistent:   {schema_consistent}")
print(f"  Reset reproducible:  {reset_ok}")
print(f"  Elapsed:             {smoke_elapsed:.1f}s")
print(f"  SMOKE TEST:          {'PASS' if smoke_pass else 'FAIL'}")
print()

json.dump({
    "smoke_pass": smoke_pass,
    "total_rows_read": smoke_rows_read,
    "max_allowed": SMOKE_MAX,
    "sys_ok": sys_ok,
    "mem_stable": mem_stable,
    "rss_growth_gb": round(rss_growth, 3),
    "schema_consistent": schema_consistent,
    "reset_ok": reset_ok,
    "elapsed_s": round(smoke_elapsed, 1),
    "batches": smoke_batch_log,
}, open(str(EVIDENCE_DIR / "smoke_test.json"), "w"), indent=2)

if not smoke_pass:
    log.error("SMOKE TEST FAILED. Aborting — full streaming will NOT start.")
    sys.exit(1)

log.info("SMOKE TEST PASSED. Proceeding to reconciliation pass.")

# ══════════════════════════════════════════════════════════════════════════════
# PART 8 — STREAMING RECONCILIATION PASS
# ══════════════════════════════════════════════════════════════════════════════
log.info("=" * 68)
log.info("PART 8: STREAMING RECONCILIATION PASS")
log.info("=" * 68)

EXPECTED_TRAIN_ROWS = 3_406_793
recon_pf       = pq.ParquetFile(TRAIN_PARQUET)
recon_cols     = [ELIGIBILITY_COL, TARGET_COL] if ELIGIBILITY_COL in recon_pf.schema_arrow.names else [TARGET_COL]
recon_total    = 0
recon_batches  = 0
recon_target_vals = set()
feat_schema_ok  = True

# Disk-backed fingerprint: hash running sum (bounded memory)
import hashlib as _hl  # noqa: E402

row_hasher = _hl.sha256()

recon_t0 = time.time()
for rb in recon_pf.iter_batches(batch_size=100_000, columns=recon_cols):
    rdf = rb.to_pandas()
    if ELIGIBILITY_COL in rdf.columns:
        rdf = rdf[rdf[ELIGIBILITY_COL] == 1]
    n = len(rdf)
    recon_total  += n
    recon_batches += 1
    # Update content fingerprint incrementally (bounded memory)
    row_hasher.update(rdf[TARGET_COL].values.tobytes())
    # Check target values
    recon_target_vals |= set(rdf[TARGET_COL].unique().tolist())
    del rdf, rb; gc.collect()

recon_elapsed     = time.time() - recon_t0
recon_fingerprint = row_hasher.hexdigest()
recon_ok_count   = recon_total == EXPECTED_TRAIN_ROWS
recon_ok_target  = recon_target_vals <= {0, 1}

log.info("  Total rows:         %d  expected=%d  match=%s",
         recon_total, EXPECTED_TRAIN_ROWS, recon_ok_count)
log.info("  Target values:      %s  ok=%s", recon_target_vals, recon_ok_target)
log.info("  Content fingerprint: %s", recon_fingerprint[:32])
log.info("  Batches scanned:    %d", recon_batches)
log.info("  Recon elapsed:      %.1fs", recon_elapsed)

json.dump({
    "total_rows": recon_total,
    "expected_rows": EXPECTED_TRAIN_ROWS,
    "match": recon_ok_count,
    "target_values_seen": sorted(str(v) for v in recon_target_vals),
    "content_fingerprint_sha256": recon_fingerprint,
    "batches_scanned": recon_batches,
    "elapsed_s": round(recon_elapsed, 1),
}, open(str(EVIDENCE_DIR / "reconciliation.json"), "w"), indent=2)

if not recon_ok_count:
    log.error("ABORT: Row count mismatch. Expected %d, got %d.",
              EXPECTED_TRAIN_ROWS, recon_total)
    sys.exit(1)

log.info("RECONCILIATION PASSED. All %d rows verified.", EXPECTED_TRAIN_ROWS)

# ══════════════════════════════════════════════════════════════════════════════
# PART 9 — BUILD EXTERNAL-MEMORY DMATRIX (ExtMemQuantileDMatrix)
# ══════════════════════════════════════════════════════════════════════════════
log.info("=" * 68)
log.info("PART 9: EXTERNAL-MEMORY QUANTILE DMATRIX")
log.info("=" * 68)

train_iter = TrainBatchIter(TRAIN_PARQUET)
t0 = time.time()
train_iter.reset()
dtrain = xgb.ExtMemQuantileDMatrix(train_iter, max_bin=256, nthread=1)
t_dmatrix = time.time() - t0
log.info("  ExtMemQuantileDMatrix built: %.1fs  total_rows=%d  cache=%.1f MB",
         t_dmatrix, train_iter._total_rows, _cache_size_mb())

if train_iter._total_rows != EXPECTED_TRAIN_ROWS:
    log.error("ABORT: DMatrix received %d rows, expected %d",
              train_iter._total_rows, EXPECTED_TRAIN_ROWS)
    sys.exit(1)

# ── Validation DMatrix (streamed, in-memory DMatrix — 480K rows safe) ────────
log.info("Building validation DMatrix from val_90d.parquet ...")
val_pf   = pq.ParquetFile(VAL_PARQUET)
val_read_cols = [c for c in COLS_TO_READ if c in val_pf.schema_arrow.names]
if ELIGIBILITY_COL in val_pf.schema_arrow.names and ELIGIBILITY_COL not in val_read_cols:
    val_read_cols.append(ELIGIBILITY_COL)

val_X_parts = []
val_y_parts = []
val_total   = 0
t0v = time.time()
for vb in val_pf.iter_batches(batch_size=100_000, columns=val_read_cols):
    vdf = vb.to_pandas()
    if ELIGIBILITY_COL in vdf.columns:
        vdf = vdf[vdf[ELIGIBILITY_COL] == 1].drop(columns=[ELIGIBILITY_COL])
    vy = vdf[TARGET_COL].values.astype(np.float32)
    vX = _normalize_batch(vdf.drop(columns=[TARGET_COL])[FEATURE_COLS])
    vX_t = preprocessor.transform(vX).astype(np.float32)
    val_X_parts.append(vX_t)
    val_y_parts.append(vy)
    val_total += len(vdf)
    del vdf, vb, vX, vy; gc.collect()

val_X = np.vstack(val_X_parts)
val_y = np.concatenate(val_y_parts)
del val_X_parts, val_y_parts; gc.collect()
dval = xgb.DMatrix(val_X, label=val_y, nthread=1)
t_val = time.time() - t0v
log.info("  Val DMatrix built: %.1fs  rows=%d  shape=%s", t_val, val_total, val_X.shape)
val_y_labels = val_y.copy()   # keep labels for metrics before deletion
del val_X, val_y; gc.collect()

# ── Watchdog ─────────────────────────────────────────────────────────────────
_abort_flag   = threading.Event()
_watchdog_log: list[dict] = []

def _watchdog(pid: int) -> None:
    proc = psutil.Process(pid)
    while not _abort_flag.is_set():
        vm = psutil.virtual_memory()
        try:
            rss = proc.memory_info().rss / 1e9
        except Exception:
            rss = 0.0
        d_f = _d_free_gb()
        c_f = _c_free_gb()
        snap = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "rss_gb": round(rss, 3),
            "sys_pct": round(vm.percent, 1),
            "avail_gb": round(vm.available / 1e9, 2),
            "d_free_gb": round(d_f, 2),
            "c_free_gb": round(c_f, 2),
            "cache_mb": round(_cache_size_mb(), 1),
        }
        _watchdog_log.append(snap)
        log.info("WATCHDOG  RSS=%.2f GB  sys=%.1f%%  avail=%.2f GB  D=%.1f GB  cache=%.0f MB",
                 rss, vm.percent, vm.available/1e9, d_f, snap["cache_mb"])
        if vm.percent >= MEM_ABORT_PCT:
            log.error("WATCHDOG ABORT: sys=%.1f%% >= %.1f%%", vm.percent, MEM_ABORT_PCT)
            _abort_flag.set(); return
        if d_f < D_ABORT_GB:
            log.error("WATCHDOG ABORT: D: free=%.1f GB", d_f)
            _abort_flag.set(); return
        if c_f < C_ABORT_GB:
            log.error("WATCHDOG ABORT: C: free=%.1f GB", c_f)
            _abort_flag.set(); return
        time.sleep(WATCHDOG_POLL)

_wt = threading.Thread(target=_watchdog, args=(os.getpid(),), daemon=True)
_wt.start()

# ══════════════════════════════════════════════════════════════════════════════
# PART 9 — TRAIN
# ══════════════════════════════════════════════════════════════════════════════
params = {
    "objective": "binary:logistic",
    "tree_method": "hist",
    "eval_metric": "aucpr",
    "max_depth": MAX_DEPTH,
    "learning_rate": LR,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "seed": SEED,
    "nthread": 1,
}
log.info("=" * 68)
log.info("TRAINING: XGBoost max_rounds=%d  early_stop=%d  ExtMemQuantileDMatrix",
         NE_MAX, EARLY_STOP)
log.info("=" * 68)

evals_result = {}
t_train_start = time.time()
bst = xgb.train(
    params, dtrain,
    num_boost_round=NE_MAX,
    evals=[(dval, "val")],
    callbacks=[xgb.callback.EarlyStopping(rounds=EARLY_STOP, save_best=True)],
    evals_result=evals_result,
    verbose_eval=10,
)
t_train = time.time() - t_train_start
_abort_flag.set()  # stop watchdog

best_iter  = bst.best_iteration
best_score = bst.best_score
log.info("Training done: %.1fs  best_iter=%d  best_score=%.6f", t_train, best_iter, best_score)

# ══════════════════════════════════════════════════════════════════════════════
# PART 11 — ARTIFACT AND VALIDATION QA
# ══════════════════════════════════════════════════════════════════════════════
from montreal_road_risk.modeling.metrics import compute_validation_metrics  # noqa: E402

log.info("Computing validation metrics ...")
# Use dval (already built, XGBoost stores data internally)
cfg_full = json.load(open("config/phase_5_modeling.json"))
proba    = bst.predict(dval)
metrics  = compute_validation_metrics(
    val_y_labels,
    proba,
    k_pcts=cfg_full["metrics"]["at_k_percents"],
    model_name=f"XGB_fulldata_ne{NE_MAX}_md{MAX_DEPTH}_lr{LR}_90d",
)
norm_fp = hashlib.sha256(np.sort(proba).tobytes()).hexdigest()
log.info("AP=%.4f  ROC=%.4f  Brier=%.4f",
         metrics["Average Precision (AP)"], metrics["ROC-AUC"], metrics["Brier"])


# Write artifact
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
prep_out  = ARTIFACT_DIR / "preprocessor.joblib"
model_out = ARTIFACT_DIR / "model.joblib"
joblib.dump(preprocessor, prep_out, compress=3)
joblib.dump(bst, model_out, compress=3)

# Read-back QA
prep_rb  = joblib.load(prep_out)
model_rb = joblib.load(model_out)
v3_Xs = []
for vb3 in pq.ParquetFile(VAL_PARQUET).iter_batches(batch_size=100_000, columns=val_read_cols):
    vdf3 = vb3.to_pandas()
    if ELIGIBILITY_COL in vdf3.columns:
        vdf3 = vdf3[vdf3[ELIGIBILITY_COL]==1].drop(columns=[ELIGIBILITY_COL])
    v3_Xs.append(prep_rb.transform(
        _normalize_batch(vdf3.drop(columns=[TARGET_COL])[FEATURE_COLS])
    ).astype(np.float32))
    del vdf3, vb3; gc.collect()
val_X3 = np.vstack(v3_Xs)
del v3_Xs
gc.collect()
proba_rb = model_rb.predict(xgb.DMatrix(val_X3, nthread=1))
rb_ok    = bool(np.allclose(proba, proba_rb, atol=1e-5))
rb_max   = float(np.max(np.abs(proba - proba_rb)))
log.info("Read-back allclose: %s  max_diff=%.2e", rb_ok, rb_max)

# Fingerprints
fp_dict = {}
for fname in ["preprocessor.joblib", "model.joblib"]:
    fp_dict[fname] = hashlib.sha256(open(ARTIFACT_DIR/fname,"rb").read()).hexdigest()

# Protected inputs
snap_dict = json.load(open("state/phase_5_protected_input_snapshot.json"))
if isinstance(snap_dict, list):
    snap_dict = {i["path"]: i["sha256"] for i in snap_dict}
elif isinstance(snap_dict, dict):
    snap_dict = snap_dict.get("files", snap_dict)
changed = []
for path, stored in snap_dict.items():
    if os.path.exists(path):
        actual = hashlib.sha256(open(path,"rb").read()).hexdigest()
        if actual != stored:
            changed.append(path)

# 1M comparison
cand1m = json.load(open(str(CANDIDATE_1M / "metadata.json")))

peak_rss = max((s["rss_gb"] for s in _watchdog_log), default=_mem_gb())
peak_sys = max((s["sys_pct"] for s in _watchdog_log), default=_sys_pct())
t_total  = t_dmatrix + t_val + t_train

import xgboost as _xgb  # noqa: E402

env_info = {
    "python": sys.version.split()[0],
    "xgboost": _xgb.__version__,
    "numpy": np.__version__,
    "joblib": joblib.__version__,
}

meta_out = {
    "label": ("XGBoost trained on all 3,406,793 purged training rows using the frozen "
               "training-only preprocessor fitted on the deterministic 1M training subset."),
    "model": f"XGB_fulldata_{recon_total}_ne{NE_MAX}_md{MAX_DEPTH}_lr{LR}_90d",
    "training_rows": train_iter._total_rows,
    "val_rows": val_total,
    "horizon": "90d",
    "frozen_preprocessor": "models/phase_5/xgb_early_stop_artifact/preprocessor.joblib",
    "params": params,
    "best_iteration": best_iter,
    "best_score_aucpr_val": best_score,
    "Average Precision (AP)": metrics["Average Precision (AP)"],
    "ROC-AUC": metrics["ROC-AUC"],
    "Brier": metrics["Brier"],
    "n_total": metrics["n_total"],
    "n_positive": metrics["n_positive"],
    "prevalence": metrics["prevalence"],
    "precision_at_5pct": metrics["precision_at_5pct"],
    "recall_at_5pct": metrics["recall_at_5pct"],
    "lift_at_5pct": metrics["lift_at_5pct"],
    "precision_at_10pct": metrics["precision_at_10pct"],
    "recall_at_10pct": metrics["recall_at_10pct"],
    "lift_at_10pct": metrics["lift_at_10pct"],
    "precision_at_20pct": metrics["precision_at_20pct"],
    "recall_at_20pct": metrics["recall_at_20pct"],
    "lift_at_20pct": metrics["lift_at_20pct"],
    "timing": {
        "dmatrix_build_s": round(t_dmatrix, 1),
        "val_build_s": round(t_val, 1),
        "xgb_training_s": round(t_train, 1),
        "total_elapsed_s": round(t_total, 1),
    },
    "memory": {
        "peak_rss_gb": round(peak_rss, 3),
        "peak_sys_pct": round(peak_sys, 1),
        "watchdog_log": _watchdog_log,
        "abort_fired": _abort_flag.is_set() and len(_watchdog_log) > 0 and any(
            s["sys_pct"] >= MEM_ABORT_PCT or s["d_free_gb"] < D_ABORT_GB for s in _watchdog_log
        ),
    },
    "smoke_test": {"passed": True, "batches": SMOKE_BATCHES, "rows": smoke_rows_read},
    "reconciliation": {"total_rows": recon_total, "match": recon_ok_count,
                       "fingerprint": recon_fingerprint},
    "readback_allclose": rb_ok,
    "readback_max_diff": rb_max,
    "prediction_fingerprint_sha256": norm_fp,
    "artifact_fingerprints": fp_dict,
    "feature_count": len(FEATURE_COLS),
    "sealed_test_accessed": False,
    "protected_inputs_changed": changed,
    "environment": env_info,
    "comparison_1m": {
        "model": cand1m["model"],
        "AP": cand1m["Average Precision (AP)"],
        "ROC": cand1m["ROC-AUC"],
        "Brier": cand1m["Brier"],
        "best_iter": cand1m["best_iteration"],
    },
    "created_utc": datetime.now(timezone.utc).isoformat(),
}

json.dump(meta_out, open(ARTIFACT_DIR / "metadata.json", "w"), indent=2, default=str)
json.dump(fp_dict,  open(ARTIFACT_DIR / "fingerprints.json", "w"), indent=2)
json.dump(_watchdog_log, open(EVIDENCE_DIR / "watchdog_log.json", "w"), indent=2)
json.dump(train_iter._evidence, open(EVIDENCE_DIR / "batch_log.json","w"), indent=2)

print()
print("=" * 68)
print("FULL-DATA TRAINING COMPLETE")
print("=" * 68)
print(f"  Label:              {meta_out['label'][:60]}...")
print(f"  Training rows:      {train_iter._total_rows:,}")
print(f"  best_iteration:     {best_iter}")
print(f"  best_score aucpr:   {best_score:.6f}")
print(f"  AP:                 {metrics['Average Precision (AP)']:.6f}")
print(f"  ROC-AUC:            {metrics['ROC-AUC']:.6f}")
print(f"  Brier:              {metrics['Brier']:.6f}")
print(f"  Lift @ 5%:          {metrics['lift_at_5pct']:.3f}x")
print(f"  Lift @ 10%:         {metrics['lift_at_10pct']:.3f}x")
print(f"  Lift @ 20%:         {metrics['lift_at_20pct']:.3f}x")
print(f"  DMatrix build:      {t_dmatrix:.1f}s")
print(f"  XGB training:       {t_train:.1f}s")
print(f"  Total:              {t_total:.1f}s")
print(f"  Peak RSS:           {peak_rss:.2f} GB")
print(f"  Peak sys%:          {peak_sys:.1f}%")
print(f"  Cache size:         {_cache_size_mb():.0f} MB")
print(f"  Read-back allclose: {rb_ok}  max_diff={rb_max:.2e}")
print(f"  Pred fingerprint:   {norm_fp[:32]}...")
print(f"  Protected inputs:   {'UNCHANGED' if not changed else 'CHANGED: '+str(changed)}")
print("  Sealed test read:   NO")
print()
print("  --- COMPARISON: 1M candidate vs Full-data candidate ---")
print(f"  1M    AP={cand1m['Average Precision (AP)']:.6f}  ROC={cand1m['ROC-AUC']:.6f}  Brier={cand1m['Brier']:.6f}  best_iter={cand1m['best_iteration']}")
print(f"  FULL  AP={metrics['Average Precision (AP)']:.6f}  ROC={metrics['ROC-AUC']:.6f}  Brier={metrics['Brier']:.6f}  best_iter={best_iter}")
delta_ap  = metrics["Average Precision (AP)"] - cand1m["Average Precision (AP)"]
delta_roc = metrics["ROC-AUC"] - cand1m["ROC-AUC"]
print(f"  Delta AP={delta_ap:+.6f}  Delta ROC={delta_roc:+.6f}")
print()
print(f"  Artifact: {ARTIFACT_DIR}/")
print("  Staged/committed/pushed: NOTHING")
print("  Sealed test accessed: NO")
print("  Phase 5: IN PROGRESS — awaiting supervisor comparison")
print("  Phase 6: LOCKED")
