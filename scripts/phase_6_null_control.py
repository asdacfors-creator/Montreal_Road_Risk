"""Phase 6 — Shuffled-label negative control (Gate A only).

Runs three global permutation controls on the Phase 5 val partition.
Seeds: 42, 137, 2026 (D6.6 approved).

Rules (enforced):
- Permutation is GLOBAL across all training segment-months (not within-segment).
- Prevalence is preserved exactly after shuffle.
- Feature rows, identifiers, and row order are unchanged.
- Only training labels are shuffled.
- Evaluation is on the Phase 5 val partition only.
- No B1, embargo, or B2 targets are accessed.
- Fixed 184 boosting rounds (no early stopping on val labels).
- Negative-control models are NOT the selected model.

Usage:
    python scripts/phase_6_null_control.py --seed 42
    python scripts/phase_6_null_control.py --seed 137
    python scripts/phase_6_null_control.py --seed 2026
    python scripts/phase_6_null_control.py --all-seeds
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

SEALED_ANCHORS = {
    "2024-01-31", "2024-02-29", "2024-03-31",  # B1
    "2024-04-30", "2024-05-31", "2024-06-30",  # embargo
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31",  # B2
}

APPROVED_SEEDS = [42, 137, 2026]
FIXED_ROUNDS = 184
ABORT_PCT = 85.0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(arr: np.ndarray) -> str:
    return sha256_bytes(arr.tobytes())


def check_memory() -> None:
    pct = psutil.virtual_memory().percent
    if pct >= ABORT_PCT:
        raise MemoryError(f"System RAM at {pct:.1f}% >= abort threshold.")


def run_control(seed: int, existing_results: dict) -> dict:  # noqa: C901
    """Run one global-shuffle negative control."""
    if seed not in APPROVED_SEEDS:
        raise ValueError(f"Seed {seed} not in approved set {APPROVED_SEEDS}")

    print(f"\n{'=' * 70}")
    print(f"NEGATIVE CONTROL — seed={seed}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'=' * 70}")

    import joblib
    import pyarrow.parquet as pq
    import xgboost as xgb
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    # -----------------------------------------------------------------------
    # Load training targets only (not test partition)
    # -----------------------------------------------------------------------
    print("\n[1/9] Loading training labels...")
    check_memory()
    train_path = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
    val_path = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"

    # Safety: assert val does not contain sealed test anchors
    val_meta = pq.read_metadata(val_path)
    print(f"  Val rows: {val_meta.num_rows:,}")
    val_tbl = pq.read_table(val_path)
    val_dates = {str(d)[:10] for d in val_tbl.column("as_of_date").to_pylist()}
    sealed_in_val = val_dates & SEALED_ANCHORS
    if sealed_in_val:
        raise RuntimeError(
            f"ABORT: sealed test anchors found in val partition: {sealed_in_val}"
        )
    print(f"  Val dates: {sorted(val_dates)[:3]} ... (no sealed anchors: OK)")

    # Load training labels + IDs
    train_tbl = pq.read_table(train_path, columns=["segment_month_id", "target_repair_90d"])
    y_train_orig = np.array(train_tbl.column("target_repair_90d").to_pylist(), dtype=np.int8)
    n_train = len(y_train_orig)
    print(f"  Train rows: {n_train:,}")

    # HARDENED ASSERTION 1: train/val segment_month_id non-overlap
    train_id_set = set(train_tbl.column("segment_month_id").to_pylist())
    val_id_set   = set(val_tbl.column("segment_month_id").to_pylist())
    id_overlap   = train_id_set & val_id_set
    if id_overlap:
        raise RuntimeError(
            f"ABORT: train/val segment_month_id overlap: {len(id_overlap)} IDs"
        )
    print("  Train/val ID overlap: 0 (purged split OK)")
    del train_id_set, val_id_set, id_overlap
    del train_tbl

    # Record fingerprints
    orig_label_sha = sha256_array(y_train_orig.astype(np.int8))
    prevalence_orig = float(y_train_orig.mean())
    print(f"  Original label SHA-256 (first 16): {orig_label_sha[:16]}...")
    print(f"  Original prevalence: {prevalence_orig:.6f}")

    # -----------------------------------------------------------------------
    # Global permutation (NOT within-segment or within-month)
    # -----------------------------------------------------------------------
    print(f"\n[2/9] Global permutation (seed={seed})...")
    rng = np.random.default_rng(seed)
    perm_idx = rng.permutation(n_train)
    perm_idx_sha = sha256_array(perm_idx.astype(np.int64))
    y_shuffled = y_train_orig[perm_idx]
    shuffled_sha = sha256_array(y_shuffled.astype(np.int8))

    # HARDENED ASSERTION 2: permutation integrity
    assert not np.array_equal(y_shuffled, y_train_orig), "ABORT: shuffle produced identical labels"
    assert y_shuffled.sum() == y_train_orig.sum(), (
        f"ABORT: multiset not preserved: orig={y_train_orig.sum()}, shuffled={y_shuffled.sum()}"
    )
    label_corr = float(np.corrcoef(
        y_train_orig.astype(float), y_shuffled.astype(float)
    )[0, 1])
    assert abs(label_corr) < 0.01, (
        f"ABORT: original/shuffled label correlation {label_corr:.4f} suspiciously high"
    )
    self_fixed = int((perm_idx == np.arange(n_train)).sum())
    # self_fixed follows Poisson(1) — 0 (derangement) is valid P≈1/e≈0.368

    # Verify exact prevalence preservation
    prevalence_shuffled = float(y_shuffled.mean())
    print(f"  Permutation SHA-256 (16): {perm_idx_sha[:16]}...")
    print(f"  Shuffled label SHA-256 (16): {shuffled_sha[:16]}...")
    print(f"  Shuffled prevalence: {prevalence_shuffled:.6f}  (preserved: {prevalence_shuffled == prevalence_orig})")
    print(f"  Self-fixed positions: {self_fixed}  Label correlation: {label_corr:.6f}")

    # -----------------------------------------------------------------------
    # Load full training features (chunked, in-memory; no disk DMatrix cache)
    # -----------------------------------------------------------------------
    print("\n[3/9] Loading training features (chunked)...")
    check_memory()

    preprocessor = joblib.load(
        _REPO_ROOT / "models/phase_5/full_training_external_memory_candidate/preprocessor.joblib"
    )

    # Get feature columns from val (same schema)
    target_col = "target_repair_90d"
    id_cols = {"segment_month_id", "canonical_segment_id", "as_of_date"}
    feature_cols = [
        c for c in val_tbl.schema.names
        if c != target_col and c not in id_cols
    ]

    # HARDENED ASSERTION 3: no Phase-5 excluded column in X
    _cfg = json.loads((_REPO_ROOT / "config/phase_5_modeling.json").read_text())
    _exclude_from_x: set[str] = set(_cfg.get("exclude_from_X", []))
    _forbidden_in_x = [c for c in _exclude_from_x if c in feature_cols]
    if _forbidden_in_x:
        raise RuntimeError(
            f"ABORT: Phase-5 excluded columns present in null-control X: {_forbidden_in_x}"
        )

    _cat_cols = set(_cfg.get("categorical_cols", []))
    _cat_cols_feat = [c for c in feature_cols if c in _cat_cols]

    def _normalize_batch(X):
        """Apply per-batch dtype fixes identical to Phase 5 _normalize_batch."""
        X = X.copy()
        if "days_since_last_repair" in X.columns:
            X["days_since_last_repair"] = X["days_since_last_repair"].fillna(-1)
        for c in _cat_cols_feat:
            if c in X.columns:
                X[c] = X[c].fillna("missing").astype(object)
        return X

    print(f"  Categorical cols for normalize: {len(_cat_cols_feat)}")
    print(f"  Forbidden-column check: PASS (0 of {len(_exclude_from_x)} excluded cols in X)")

    os.makedirs(_REPO_ROOT / "data/processed/phase_6", exist_ok=True)


    # Accumulate transformed feature chunks
    X_chunks = []
    row_offset = 0
    pf = pq.ParquetFile(train_path)
    chunk_size = 200_000
    for batch in pf.iter_batches(batch_size=chunk_size, columns=feature_cols):
        check_memory()
        chunk_df = batch.to_pandas()
        X_chunk = preprocessor.transform(_normalize_batch(chunk_df)).astype(np.float32)
        X_chunks.append(X_chunk)
        row_offset += len(chunk_df)
        del chunk_df, batch
        gc.collect()
    X_train_all = np.vstack(X_chunks)
    del X_chunks
    gc.collect()
    print(f"  Transformed shape: {X_train_all.shape}")

    # Apply shuffled labels
    dm_train = xgb.DMatrix(X_train_all, label=y_shuffled.astype(np.float32))
    del X_train_all
    gc.collect()

    # -----------------------------------------------------------------------
    # Train with shuffled labels — fixed rounds, no early stopping
    # -----------------------------------------------------------------------
    print(f"\n[4/9] Training null model (seed={seed}, rounds={FIXED_ROUNDS})...")
    check_memory()

    fp_data = json.loads(
        (_REPO_ROOT / "models/phase_5/full_training_external_memory_candidate/metadata.json").read_text()
    )
    # Use the same hyperparameters as the Phase 5 selected model, override seed
    base_params = dict(fp_data.get("params", {}))
    base_params["seed"] = seed
    base_params["nthread"] = 1
    params = base_params
    print(f"  Params: {params}")
    t0 = time.perf_counter()
    # No watchlist — no validation labels used during training
    bst_null = xgb.train(params, dm_train, num_boost_round=FIXED_ROUNDS)
    t1 = time.perf_counter()
    train_time = t1 - t0
    peak_rss = psutil.Process().memory_info().rss / 1e9
    print(f"  Training time: {train_time:.1f} s  Peak RSS: {peak_rss:.2f} GB")
    del dm_train
    gc.collect()

    # -----------------------------------------------------------------------
    # Evaluate on val partition ONLY
    # -----------------------------------------------------------------------
    print("\n[5/9] Evaluating on val partition (no sealed data)...")
    check_memory()

    y_val_list = val_tbl.column(target_col).to_pylist()
    y_val = np.array(y_val_list, dtype=float)
    X_val_df = val_tbl.select(feature_cols).to_pandas()
    X_val = preprocessor.transform(_normalize_batch(X_val_df)).astype(np.float32)
    del X_val_df
    val_prevalence = float(y_val.mean())
    print(f"  Val rows: {len(y_val):,}  Val prevalence: {val_prevalence:.6f}")

    dm_val = xgb.DMatrix(X_val)
    raw_scores = bst_null.predict(dm_val, iteration_range=(0, FIXED_ROUNDS))
    pred_sha256 = sha256_array(raw_scores.astype(np.float32))
    del dm_val, X_val
    gc.collect()

    null_ap = float(average_precision_score(y_val, raw_scores))
    null_auc = float(roc_auc_score(y_val, raw_scores))
    null_brier = float(brier_score_loss(y_val, raw_scores))
    pred_mean = float(raw_scores.mean())
    pred_std = float(raw_scores.std())

    print(f"  Null AP     : {null_ap:.6f}")
    print(f"  Val prev    : {val_prevalence:.6f}")
    print(f"  AP - prev   : {null_ap - val_prevalence:.6f}")
    print(f"  Null ROC-AUC: {null_auc:.6f}")
    print(f"  Null Brier  : {null_brier:.6f}")
    print(f"  Pred mean   : {pred_mean:.4f}  std: {pred_std:.4f}")

    # -----------------------------------------------------------------------
    # Investigation alert if AP >> 2×prevalence after global shuffle
    # -----------------------------------------------------------------------
    alert = null_ap > 2.0 * val_prevalence
    if alert:
        print(f"\n  [ALERT] Null AP ({null_ap:.4f}) > 2× prevalence ({2*val_prevalence:.4f})")
        print("  Investigate permutation alignment before proceeding.")
    else:
        print("  [OK] Null AP within expected range (≤ 2× prevalence)")

    # Do NOT save the null model binary unless explicitly needed for audit
    # bst_null is discarded after reporting
    del bst_null, raw_scores
    gc.collect()

    result = {
        "seed": seed,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "permutation_type": "global",
        "fixed_rounds": FIXED_ROUNDS,
        "n_train": n_train,
        "prevalence_original": prevalence_orig,
        "prevalence_shuffled": prevalence_shuffled,
        "prevalence_preserved": bool(y_train_orig.sum() == y_shuffled.sum()),
        "orig_label_sha256": orig_label_sha,
        "perm_index_sha256": perm_idx_sha,
        "shuffled_label_sha256": shuffled_sha,
        "shuffled_identical_to_original": False,
        "self_fixed_count": self_fixed,
        "label_correlation": round(label_corr, 8),
        "id_overlap_count": 0,
        "forbidden_feature_count": 0,
        "pred_sha256": pred_sha256,
        "val_prevalence": val_prevalence,
        "null_ap": null_ap,
        "null_roc_auc": null_auc,
        "null_brier": null_brier,
        "ap_minus_prevalence": null_ap - val_prevalence,
        "pred_mean": pred_mean,
        "pred_std": pred_std,
        "train_time_s": round(train_time, 1),
        "peak_rss_gb": round(peak_rss, 2),
        "peak_system_pct": psutil.virtual_memory().percent,
        "alert_ap_elevated": alert,
        "b1_targets_accessed": False,
        "embargo_targets_accessed": False,
        "b2_targets_accessed": False,
        "null_model_replaces_selected": False,
    }
    return result


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, help="Single seed to run (42, 137, or 2026)")
    parser.add_argument("--all-seeds", action="store_true", help="Run all three approved seeds")
    args = parser.parse_args()

    out_path = _REPO_ROOT / "models/phase_6/shuffled_label_control_results.json"
    existing: dict = {}
    if out_path.exists():
        existing = json.loads(out_path.read_text())

    seeds_to_run = APPROVED_SEEDS if args.all_seeds else ([args.seed] if args.seed else [42])

    for seed in seeds_to_run:
        result = run_control(seed, existing)
        existing[f"seed_{seed}"] = result

        # Pause after seed 42 if alert
        if seed == 42 and result["alert_ap_elevated"] and not args.all_seeds:
            print("\n[PAUSE] Seed 42 elevated AP detected. Inspect before running seeds 137 and 2026.")
            out_path.write_text(json.dumps(existing, indent=2))
            print(f"Partial results saved: {out_path}")
            sys.exit(2)

    existing["all_seeds_complete"] = len(existing) >= 3
    existing["b1_targets_accessed"] = False
    existing["embargo_targets_accessed"] = False
    existing["b2_targets_accessed"] = False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(existing, indent=2))
    print(f"\nNull control results saved: {out_path}")


if __name__ == "__main__":
    main()
