# ruff: noqa: E402
"""Phase 6 Gate A preflight script.

Checks:
- Active Python processes
- Git state and HEAD = afec84b
- Model and preprocessor fingerprints
- Test seal SHA-256 (no labels read)
- Schema fingerprint and row count
- Backup readability
- System RAM and disk
- Writes test_split_manifest.json (no labels, anchor allowlists only)
- Runs a 500-row synthetic smoke test
- Runs a non-target-column real-data streaming benchmark (features only)
- Writes preflight_summary.json

Does NOT access B1, embargo, or B2 targets.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
import pyarrow as pa
import pyarrow.parquet as pq

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

ABORT_PCT = 85.0
MIN_DISK_FREE_GB = 8.0
EXPECTED_ROWS = 815711
EXPECTED_MODEL_SHA = "f9fab0ec1d8e257f8f201085aa62123056a424552a05e4aa3da9c0affff70c07"
EXPECTED_PREP_SHA = "6bfe7209f95b86e962e50249ea2492bc7630f9a37d1700f350e4d748a64492ff"
SEALED_TEST_PATH = "data/processed/phase_5/test.parquet"
PHASE5_COMMIT = "afec84b"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_memory() -> None:
    pct = psutil.virtual_memory().percent
    if pct >= ABORT_PCT:
        raise MemoryError(f"System memory at {pct:.1f}% >= abort threshold {ABORT_PCT:.1f}%.")


def banner(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


banner("PHASE 6 GATE A PREFLIGHT")
print(f"Time: {datetime.now(timezone.utc).isoformat()}")

results: dict = {
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "gate": "A",
    "checks": {},
}

# ============================================================
# PART 1: Python processes
# ============================================================
section("ACTIVE PYTHON PROCESSES")
for proc in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
    try:
        if "python" in proc.info["name"].lower():
            rss = proc.info["memory_info"].rss / 1e9
            cmd = " ".join(proc.info["cmdline"] or [])[:120]
            print(f"  PID {proc.info['pid']:6d}  RSS={rss:.2f} GB  {cmd}")
    except Exception:
        pass

# ============================================================
# PART 2: Git state
# ============================================================
section("GIT STATE")
r = subprocess.run(["git", "log", "-5", "--oneline"], capture_output=True, text=True, cwd=str(_REPO_ROOT))
print(r.stdout.strip())
r2 = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(_REPO_ROOT))
st = r2.stdout.strip()
print(f"git status: {st if st else '(clean)'}")
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(_REPO_ROOT)).stdout.strip()
head_ok = head.startswith(PHASE5_COMMIT) or PHASE5_COMMIT in head
print(f"HEAD: {head}  phase5_commit_ok: {head_ok}")
results["checks"]["git_clean"] = not bool(st)
results["checks"]["head_is_phase5"] = head_ok

# ============================================================
# PART 3: Model fingerprints
# ============================================================
section("MODEL FINGERPRINTS")
fp = json.loads((_REPO_ROOT / "models/phase_5/full_training_external_memory_candidate/fingerprints.json").read_text())
model_sha = sha256_file(_REPO_ROOT / "models/phase_5/full_training_external_memory_candidate/model.joblib")
prep_sha = sha256_file(_REPO_ROOT / "models/phase_5/full_training_external_memory_candidate/preprocessor.joblib")
model_ok = model_sha == fp["model.joblib"]
prep_ok = prep_sha == fp["preprocessor.joblib"]
print(f"model.joblib:  actual={model_sha[:24]}...  match={model_ok}")
print(f"preprocessor:  actual={prep_sha[:24]}...  match={prep_ok}")
results["checks"]["model_fingerprint"] = model_ok
results["checks"]["prep_fingerprint"] = prep_ok

if not model_ok or not prep_ok:
    print("ABORT: Model fingerprint mismatch. Halting.")
    sys.exit(1)

# ============================================================
# PART 4: Test seal (byte-level SHA-256 only, no labels)
# ============================================================
section("TEST SEAL FINGERPRINT (no labels read)")
test_path = _REPO_ROOT / SEALED_TEST_PATH
test_sha = sha256_file(test_path)
test_size = test_path.stat().st_size
print(f"test.parquet SHA-256: {test_sha}")
print(f"test.parquet size   : {test_size:,} bytes")

schema = pq.read_schema(test_path)
schema_fp = hashlib.sha256(str(schema).encode()).hexdigest()
meta = pq.read_metadata(test_path)
actual_rows = meta.num_rows
row_ok = actual_rows == EXPECTED_ROWS
print(f"Schema fingerprint  : {schema_fp}")
print(f"Row count           : {actual_rows:,}  expected={EXPECTED_ROWS:,}  match={row_ok}")
print("Target column       : NOT decoded")
results["checks"]["test_seal_sha256"] = test_sha
results["checks"]["test_seal_schema_fp"] = schema_fp
results["checks"]["test_seal_rows"] = row_ok

if not row_ok:
    print("ABORT: Test seal row count mismatch.")
    sys.exit(1)

# ============================================================
# PART 5: Backup
# ============================================================
section("BACKUP READABILITY")
bk_path = Path(r"C:\Montreal_Road_Risk_Backup\Phase_5_Full_Training_Candidate_afec84b\model.joblib")
if bk_path.exists():
    bk_sha = sha256_file(bk_path)
    bk_ok = bk_sha == model_sha
    print(f"Backup model.joblib: {bk_sha[:24]}...  match={bk_ok}")
    results["checks"]["backup_readable"] = bk_ok
else:
    print("WARNING: Backup path not found")
    results["checks"]["backup_readable"] = "NOT_FOUND"

# ============================================================
# PART 6: System state
# ============================================================
section("SYSTEM STATE")
check_memory()
mem = psutil.virtual_memory()
disk_d = psutil.disk_usage(str(_REPO_ROOT.drive + "\\"))
disk_c = psutil.disk_usage("C:\\")
print(f"RAM total   : {mem.total/1e9:.2f} GB")
print(f"RAM avail   : {mem.available/1e9:.2f} GB  ({mem.percent:.1f}% used)")
print(f"D: free     : {disk_d.free/1e9:.2f} GB")
print(f"C: free     : {disk_c.free/1e9:.2f} GB")
disk_ok = disk_d.free / 1e9 >= MIN_DISK_FREE_GB
print(f"D: disk check (>={MIN_DISK_FREE_GB} GB): {disk_ok}")
results["checks"]["ram_pct"] = mem.percent
results["checks"]["disk_free_gb"] = round(disk_d.free / 1e9, 2)
results["checks"]["disk_ok"] = disk_ok

# ============================================================
# PART 7: Write split manifest (no labels)
# ============================================================
section("LOGICAL TEST SPLIT MANIFEST")

manifest_path = _REPO_ROOT / "models/phase_6/test_split_manifest.json"
# Update existing manifest with verified SHA
m = json.loads(manifest_path.read_text())
m["sealed_file_sha256"] = test_sha
m["schema_fingerprint"] = schema_fp
m["total_actual_rows"] = actual_rows
m["preflight_utc"] = datetime.now(timezone.utc).isoformat()
manifest_path.write_text(json.dumps(m, indent=2))
print(f"Manifest updated: {manifest_path}")
print(f"SHA-256 written (no labels): {test_sha[:24]}...")
print("Physical split: NOT created")
print("Target decoded: NO")
results["checks"]["manifest_written"] = True

# ============================================================
# PART 8: Subgroup cardinality from panel metadata (no targets)
# ============================================================
section("SUBGROUP CARDINALITY FROM PANEL METADATA")
col_names = [schema.field(i).name for i in range(len(schema))]
print(f"Total columns in schema: {len(col_names)}")
print(f"Target column in schema: {'target_repair_90d' in col_names}")

# Read cardinality of as_of_date (anchor enumeration) without decoding target
import pyarrow.compute as pc

# Read only as_of_date column — no targets
date_col_tbl = pq.read_table(test_path, columns=["as_of_date"])
anchors_actual = sorted(set(pc.cast(date_col_tbl.column("as_of_date"), pa.string()).to_pylist()))
print(f"Unique anchors found : {len(anchors_actual)}")
print(f"First anchor         : {anchors_actual[0]}")
print(f"Last anchor          : {anchors_actual[-1]}")
results["checks"]["anchors_count"] = len(anchors_actual)
results["checks"]["anchors_match_17"] = len(anchors_actual) == 17

# Feature manifest check
feat_manifest_path = _REPO_ROOT / "data/metadata/feature_manifest.csv"
if feat_manifest_path.exists():
    import csv
    with open(feat_manifest_path, newline="", encoding="utf-8") as fh:
        feat_rows = list(csv.DictReader(fh))
    print(f"Feature manifest rows: {len(feat_rows)}")
    feat_names = [r.get("feature_name", r.get("column_name", "")) for r in feat_rows]
    has_asset_flag = "future_asset_record_hidden_flag" in feat_names
    print(f"future_asset_record_hidden_flag in manifest: {has_asset_flag}")
    results["checks"]["feature_manifest_rows"] = len(feat_rows)
    results["checks"]["asset_flag_in_manifest"] = has_asset_flag
else:
    print("WARNING: feature_manifest.csv not found at expected path")

del date_col_tbl
gc.collect()

# ============================================================
# PART 9: Synthetic smoke test (500 rows, all metrics finite)
# ============================================================
section("SYNTHETIC SMOKE TEST (500 rows)")
from montreal_road_risk.evaluation.calibration import PlattCalibrator
from montreal_road_risk.evaluation.metrics import (
    average_precision,
    brier_score,
    calibration_slope_intercept,
    expected_calibration_error,
    precision_at_k,
    recall_at_k,
    roc_auc,
    top_k_row_count,
)

rng = np.random.default_rng(42)
N_SMOKE = 500
y_smoke = rng.binomial(1, 0.055, N_SMOKE).astype(float)
s_smoke = np.clip(y_smoke * 0.6 + rng.uniform(0, 1, N_SMOKE) * 0.4, 0, 1)

cal_smoke = PlattCalibrator()
cal_smoke.fit(s_smoke, y_smoke)
p_smoke = cal_smoke.predict_proba(s_smoke)

smoke_results = {
    "n": N_SMOKE,
    "ap": average_precision(y_smoke, p_smoke),
    "roc_auc": roc_auc(y_smoke, p_smoke),
    "brier": brier_score(y_smoke, p_smoke),
    "ece": expected_calibration_error(y_smoke, p_smoke),
    "slope_res": calibration_slope_intercept(y_smoke, p_smoke),
    "p5_n": top_k_row_count(N_SMOKE, 5),
    "p10_n": top_k_row_count(N_SMOKE, 10),
    "p20_n": top_k_row_count(N_SMOKE, 20),
    "prec_at_10": precision_at_k(y_smoke, p_smoke, 10.0),
    "recall_at_10": recall_at_k(y_smoke, p_smoke, 10.0),
}
all_finite = all(
    math.isfinite(v) for v in [
        smoke_results["ap"], smoke_results["roc_auc"], smoke_results["brier"],
        smoke_results["ece"], smoke_results["prec_at_10"], smoke_results["recall_at_10"],
    ]
)
print(f"Smoke AP     : {smoke_results['ap']:.4f}")
print(f"Smoke ROC-AUC: {smoke_results['roc_auc']:.4f}")
print(f"Smoke Brier  : {smoke_results['brier']:.4f}")
print(f"Smoke ECE    : {smoke_results['ece']:.6f}")
print(f"Top-5% rows  : {smoke_results['p5_n']}  (ceil(500*5/100)=25)")
print(f"Top-10% rows : {smoke_results['p10_n']} (ceil(500*10/100)=50)")
print(f"Top-20% rows : {smoke_results['p20_n']} (ceil(500*20/100)=100)")
print(f"Slope conv   : {smoke_results['slope_res']['status']}")
print(f"All finite   : {all_finite}")
results["checks"]["smoke_test_all_finite"] = all_finite
results["checks"]["smoke_top_k_5"] = smoke_results["p5_n"]

# ============================================================
# PART 10: Non-target real-data streaming benchmark
# ============================================================
section("REAL-DATA STREAMING BENCHMARK (no target column)")
check_memory()
BENCH_COLS = ["canonical_segment_id", "as_of_date", "segment_month_id", "functional_road_class"]
# Add feature columns (no target)
target_col = "target_repair_90d"
bench_cols_safe = [c for c in col_names if c != target_col][:30]  # first 30 non-target cols

rss_before = psutil.Process().memory_info().rss / 1e9
t0 = time.perf_counter()
batch_rows = 0
for batch in pq.ParquetFile(test_path).iter_batches(batch_size=100_000, columns=bench_cols_safe):
    batch_rows += len(batch)
    check_memory()
    del batch
    gc.collect()
    if batch_rows >= 100_000:
        break  # One-partition benchmark only
t1 = time.perf_counter()
rss_after = psutil.Process().memory_info().rss / 1e9
bench_time = t1 - t0
bench_rss_delta = rss_after - rss_before
print(f"Rows scanned   : {batch_rows:,}")
print(f"Columns read   : {len(bench_cols_safe)} (no target)")
print(f"Elapsed        : {bench_time:.2f} s")
print(f"RSS delta      : {bench_rss_delta:.3f} GB")
print(f"Current RAM    : {psutil.virtual_memory().percent:.1f}%")
bench_ok = psutil.virtual_memory().percent < ABORT_PCT
print(f"Memory OK      : {bench_ok}")
results["checks"]["benchmark_ok"] = bench_ok
results["checks"]["benchmark_rss_delta_gb"] = round(bench_rss_delta, 3)
results["checks"]["benchmark_elapsed_s"] = round(bench_time, 2)
results["checks"]["target_column_accessed"] = False

del batch_rows
gc.collect()

# ============================================================
# PART 11: Protected input immutability
# ============================================================
section("PROTECTED INPUT IMMUTABILITY")
snap = json.loads((_REPO_ROOT / "models/phase_6/protected_input_snapshot_gate_a.json").read_text())["snapshot"]
immut_ok = True
for path_str, stored_sha in snap.items():
    p = _REPO_ROOT / path_str
    if not p.exists() or stored_sha == "MISSING":
        continue
    actual = sha256_file(p)
    if actual != stored_sha:
        print(f"  CHANGED: {path_str}")
        immut_ok = False
    else:
        print(f"  OK: {p.name}")
print(f"All protected inputs unchanged: {immut_ok}")
results["checks"]["protected_inputs_immutable"] = immut_ok

# ============================================================
# Write preflight summary
# ============================================================
section("PREFLIGHT SUMMARY")
all_pass = all([
    results["checks"]["model_fingerprint"],
    results["checks"]["prep_fingerprint"],
    results["checks"]["test_seal_rows"],
    results["checks"]["smoke_test_all_finite"],
    results["checks"]["benchmark_ok"],
    results["checks"]["protected_inputs_immutable"],
    not results["checks"]["target_column_accessed"],
])
results["checks"]["all_pass"] = all_pass
results["model_sha"] = model_sha
results["test_sha"] = test_sha
results["schema_fp"] = schema_fp

out_dir = _REPO_ROOT / "models/phase_6"
out_dir.mkdir(parents=True, exist_ok=True)
summary_path = out_dir / "preflight_summary.json"
summary_path.write_text(json.dumps(results, indent=2))
print(f"Summary written: {summary_path}")
print(f"\nPREFLIGHT RESULT: {'PASS' if all_pass else 'FAIL'}")
print(f"  model fingerprint      : {results['checks']['model_fingerprint']}")
print(f"  test seal rows         : {results['checks']['test_seal_rows']}")
print(f"  smoke test all finite  : {results['checks']['smoke_test_all_finite']}")
print(f"  benchmark OK           : {results['checks']['benchmark_ok']}")
print(f"  protected inputs immut : {results['checks']['protected_inputs_immutable']}")
print(f"  target accessed        : {results['checks']['target_column_accessed']}")
print("  B1 authorized          : False")
print("  B2 authorized          : False")

if not all_pass:
    sys.exit(1)
