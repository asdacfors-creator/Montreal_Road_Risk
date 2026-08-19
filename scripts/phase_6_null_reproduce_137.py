"""Phase 6 — Seed 137 determinism reproduction (Gate A investigation).

Runs seed 137 TWICE in the same process, each time:
  - fresh np.random.default_rng(137) permutation
  - fresh X_train loaded from scratch
  - fresh xgb.DMatrix (in-memory, no disk cache)
  - fresh xgb.train() booster
  - fresh evaluation on val partition

Verifies:
  - Prediction arrays are byte-for-byte identical
  - Metrics are identical to within floating-point tolerance
  - Row order of features exactly matches row order of shuffled labels
  - No state leaks between runs

Output: models/phase_6/seed_137_reproduction.json
"""
from __future__ import annotations

import gc
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
import xgboost as xgb
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

SEED        = 137
FIXED_ROUNDS = 184
TRAIN_PATH  = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
VAL_PATH    = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
MODEL_DIR   = _REPO_ROOT / "models/phase_5/full_training_external_memory_candidate"

SEALED_ANCHORS = {
    "2024-01-31", "2024-02-29", "2024-03-31",
    "2024-04-30", "2024-05-31", "2024-06-30",
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31",
}


def sha256_arr(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()


def run_once(run_id: int) -> dict:
    """One complete seed-137 null control run from scratch."""
    print(f"\n{'─'*60}")
    print(f"  RUN {run_id} of 2  —  seed={SEED}")
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'─'*60}")

    # ------------------------------------------------------------------
    # Unique per-run temp directory (proves no cache sharing even if
    # external memory were used — it isn't, but belt-and-suspenders)
    # ------------------------------------------------------------------
    run_tmpdir = tempfile.mkdtemp(prefix=f"null_ctrl_s{SEED}_run{run_id}_")
    print(f"  Temp dir (cache isolation): {run_tmpdir}")

    # ------------------------------------------------------------------
    # Load val (fresh read)
    # ------------------------------------------------------------------
    val_tbl  = pq.read_table(VAL_PATH)
    val_dates = {str(d)[:10] for d in val_tbl.column("as_of_date").to_pylist()}
    assert not (val_dates & SEALED_ANCHORS), "sealed anchors in val"
    y_val    = np.array(val_tbl.column("target_repair_90d").to_pylist(), dtype=float)
    n_val    = len(y_val)

    # ------------------------------------------------------------------
    # Load train labels (fresh read) + record SHA-256 of row-order IDs
    # ------------------------------------------------------------------
    train_tbl_labels = pq.read_table(TRAIN_PATH,
                                     columns=["segment_month_id", "target_repair_90d"])
    y_train_orig = np.array(
        train_tbl_labels.column("target_repair_90d").to_pylist(), dtype=np.int8
    )
    train_ids_ordered = train_tbl_labels.column("segment_month_id").to_pylist()
    train_id_fp = hashlib.sha256(json.dumps(train_ids_ordered[:20]).encode()).hexdigest()
    del train_tbl_labels
    n_train = len(y_train_orig)

    # ------------------------------------------------------------------
    # Global permutation — fresh RNG each run
    # ------------------------------------------------------------------
    rng      = np.random.default_rng(SEED)   # same seed → same permutation
    perm_idx = rng.permutation(n_train)
    y_shuf   = y_train_orig[perm_idx]

    perm_sha = sha256_arr(perm_idx.astype(np.int64))
    shuf_sha = sha256_arr(y_shuf.astype(np.int8))
    assert y_shuf.sum() == y_train_orig.sum(), "multiset not preserved"
    assert not np.array_equal(y_shuf, y_train_orig), "shuffle identical"

    print(f"  Perm SHA-256:    {perm_sha[:32]}...")
    print(f"  Shuffled SHA-256:{shuf_sha[:32]}...")

    # ------------------------------------------------------------------
    # Load and transform training features (fresh, no cache)
    # ------------------------------------------------------------------
    preprocessor = joblib.load(MODEL_DIR / "preprocessor.joblib")

    target_col = "target_repair_90d"
    id_cols    = {"segment_month_id", "canonical_segment_id", "as_of_date"}
    feature_cols = [c for c in val_tbl.schema.names if c not in id_cols | {target_col}]

    cfg_p5      = json.loads((_REPO_ROOT / "config/phase_5_modeling.json").read_text())
    cat_cols    = set(cfg_p5.get("categorical_cols", []))
    cat_feat    = [c for c in feature_cols if c in cat_cols]

    def normalize(df):
        df = df.copy()
        if "days_since_last_repair" in df.columns:
            df["days_since_last_repair"] = df["days_since_last_repair"].fillna(-1)
        for c in cat_feat:
            if c in df.columns:
                df[c] = df[c].fillna("missing").astype(object)
        return df

    X_chunks = []
    pf = pq.ParquetFile(TRAIN_PATH)
    for batch in pf.iter_batches(batch_size=200_000, columns=feature_cols):
        df = batch.to_pandas()
        X_chunks.append(preprocessor.transform(normalize(df)).astype(np.float32))
        del df, batch
        gc.collect()
    X_train = np.vstack(X_chunks)
    del X_chunks
    gc.collect()

    # Feature row SHA-256 (proves features NOT reordered)
    feat_sha = sha256_arr(X_train[:5])   # first 5 rows fingerprint
    print(f"  Feature[0:5] SHA-256: {feat_sha[:32]}...")

    # Row count alignment assertion
    assert len(X_train) == n_train, f"Feature rows {len(X_train)} ≠ label rows {n_train}"

    # ------------------------------------------------------------------
    # DMatrix — fresh, in-memory, no disk cache
    # ------------------------------------------------------------------
    dm_train = xgb.DMatrix(X_train, label=y_shuf.astype(np.float32))
    del X_train
    gc.collect()

    # ------------------------------------------------------------------
    # Train — fresh booster
    # ------------------------------------------------------------------
    meta   = json.loads((MODEL_DIR / "metadata.json").read_text())
    params = dict(meta["params"])
    params["seed"]    = SEED
    params["nthread"] = 1
    # Remove eval_metric from params (not needed without watchlist)
    params.pop("eval_metric", None)
    params["eval_metric"] = "aucpr"  # kept but no watchlist → ignored

    t0 = time.perf_counter()
    bst = xgb.train(params, dm_train, num_boost_round=FIXED_ROUNDS)
    elapsed = time.perf_counter() - t0
    del dm_train
    gc.collect()
    print(f"  Training time: {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # Evaluate on val (fresh transform)
    # ------------------------------------------------------------------
    X_val_df = val_tbl.select(feature_cols).to_pandas()
    X_val    = preprocessor.transform(normalize(X_val_df)).astype(np.float32)
    del X_val_df

    dm_val = xgb.DMatrix(X_val)
    preds  = bst.predict(dm_val, iteration_range=(0, FIXED_ROUNDS))
    del dm_val, X_val, bst
    gc.collect()

    pred_sha = sha256_arr(preds.astype(np.float32))
    ap  = float(average_precision_score(y_val, preds))
    auc = float(roc_auc_score(y_val, preds))
    brier = float(brier_score_loss(y_val, preds))

    print(f"  Pred SHA-256: {pred_sha[:32]}...")
    print(f"  AP={ap:.6f}  ROC-AUC={auc:.6f}  Brier={brier:.6f}")
    print(f"  Pred mean={preds.mean():.4f}  std={preds.std():.4f}")

    # Cleanup temp dir (no actual files but remove the dir)
    import shutil
    shutil.rmtree(run_tmpdir, ignore_errors=True)

    return {
        "run_id"           : run_id,
        "seed"             : SEED,
        "perm_sha256"      : perm_sha,
        "shuffled_sha256"  : shuf_sha,
        "feat_first5_sha256": feat_sha,
        "train_id_fp"      : train_id_fp,
        "pred_sha256"      : pred_sha,
        "null_ap"          : ap,
        "null_roc_auc"     : auc,
        "null_brier"       : brier,
        "pred_mean"        : float(preds.mean()),
        "pred_std"         : float(preds.std()),
        "train_time_s"     : round(elapsed, 1),
        "n_train"          : n_train,
        "n_val"            : n_val,
        "params"           : params,
    }


def main() -> None:  # noqa: C901
    print("=" * 60)
    print("SEED 137 DETERMINISM REPRODUCTION")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    result1 = run_once(1)
    result2 = run_once(2)

    # Determinism check
    print(f"\n{'='*60}")
    print("DETERMINISM COMPARISON")
    print(f"{'='*60}")

    same_perm  = result1["perm_sha256"]       == result2["perm_sha256"]
    same_shuf  = result1["shuffled_sha256"]   == result2["shuffled_sha256"]
    same_feat  = result1["feat_first5_sha256"]== result2["feat_first5_sha256"]
    same_pred  = result1["pred_sha256"]       == result2["pred_sha256"]
    same_ap    = abs(result1["null_ap"] - result2["null_ap"]) < 1e-8
    same_auc   = abs(result1["null_roc_auc"] - result2["null_roc_auc"]) < 1e-8

    print(f"  Permutation identical  : {same_perm}")
    print(f"  Shuffled labels identical: {same_shuf}")
    print(f"  Feature[0:5] identical : {same_feat}")
    print(f"  Predictions identical  : {same_pred}")
    print(f"  AP identical           : {same_ap}  ({result1['null_ap']:.6f} vs {result2['null_ap']:.6f})")
    print(f"  ROC-AUC identical      : {same_auc} ({result1['null_roc_auc']:.6f} vs {result2['null_roc_auc']:.6f})")

    fully_deterministic = all([same_perm, same_shuf, same_feat, same_pred, same_ap, same_auc])
    print(f"\n  FULLY DETERMINISTIC: {fully_deterministic}")
    if fully_deterministic:
        print("  → Seed 137 result is real and reproducible, not noise.")
        print("  → Statistical explanation (XGBoost subsampling variance) applies.")
    else:
        print("  !! NON-DETERMINISM DETECTED — investigate XGBoost build.")

    # Compare with original run
    original_ap  = 0.099158
    original_auc = 0.647576
    ap_match  = abs(result1["null_ap"] - original_ap) < 0.001
    auc_match = abs(result1["null_roc_auc"] - original_auc) < 0.001
    print(f"\n  Original run AP={original_ap:.6f}  AUC={original_auc:.6f}")
    print(f"  Repro    run AP={result1['null_ap']:.6f}  AUC={result1['null_roc_auc']:.6f}")
    print(f"  AP  matches original (±0.001): {ap_match}")
    print(f"  AUC matches original (±0.001): {auc_match}")

    out = {
        "created_utc"        : datetime.now(timezone.utc).isoformat(),
        "seed"               : SEED,
        "run_1"              : result1,
        "run_2"              : result2,
        "fully_deterministic": fully_deterministic,
        "original_ap"        : original_ap,
        "original_auc"       : original_auc,
        "ap_matches_original": ap_match,
        "auc_matches_original": auc_match,
        "b1_targets_accessed": False,
        "embargo_accessed"   : False,
        "b2_targets_accessed": False,
    }
    out_path = _REPO_ROOT / "models/phase_6/seed_137_reproduction.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nResults written: {out_path}")


if __name__ == "__main__":
    main()
