"""Phase 6 — Repair-history null AP investigation.

Part 1: Cross-seed cross-controls (repair-only, perm=42/137/2026, model=42)
Part 2: Sampling isolation (repair-only, perm=137, model=42, sub/col variants)

Saves predictions and feature importances for the perm=137 repair-only model.
No sealed targets accessed. No B1/embargo/B2 targets accessed.
"""
from __future__ import annotations

import gc
import hashlib
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import xgboost as xgb
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

TRAIN_PATH   = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
VAL_PATH     = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
MODEL_DIR    = _REPO_ROOT / "models/phase_5/full_training_external_memory_candidate"
FIXED_ROUNDS = 184
MODEL_SEED   = 42

SEALED_ANCHORS = {
    "2024-01-31","2024-02-29","2024-03-31",
    "2024-04-30","2024-05-31","2024-06-30",
    "2024-07-31","2024-08-31","2024-09-30","2024-10-31","2024-11-30",
    "2024-12-31","2025-01-31","2025-02-28","2025-03-31",
    "2025-04-30","2025-05-31",
}

REPAIR_HISTORY = [
    "days_since_last_repair", "no_prior_repair_flag", "prior_repair_months_12m",
    "repair_active_days_30d", "repair_active_days_90d",
    "repair_active_days_180d", "repair_active_days_365d",
    "repair_event_count_collapsed_30d", "repair_event_count_collapsed_90d",
    "repair_event_count_collapsed_180d", "repair_event_count_collapsed_365d",
    "repair_history_complete_30d", "repair_history_complete_90d",
    "repair_history_complete_180d", "repair_history_complete_365d",
    "repair_history_coverage_ratio_30d", "repair_history_coverage_ratio_90d",
    "repair_history_coverage_ratio_180d", "repair_history_coverage_ratio_365d",
    "repair_history_valid_days_30d", "repair_history_valid_days_90d",
    "repair_history_valid_days_180d", "repair_history_valid_days_365d",
]  # 23 features — ALL numeric


def sha256_arr(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()


def section(msg: str) -> None:
    print(f"\n{'─'*70}\n  {msg}\n{'─'*70}")


def check_sealed() -> None:
    tbl = pq.read_table(VAL_PATH, columns=["as_of_date"])
    dates = {str(d)[:10] for d in tbl.column("as_of_date").to_pylist()}
    bad = dates & SEALED_ANCHORS
    if bad:
        raise RuntimeError(f"ABORT: sealed anchors in val: {bad}")


def permute_labels(y_orig: np.ndarray, perm_seed: int) -> tuple[np.ndarray, str]:
    rng    = np.random.default_rng(perm_seed)
    perm   = rng.permutation(len(y_orig))
    y_shuf = y_orig[perm]
    assert y_shuf.sum() == y_orig.sum()
    assert not np.array_equal(y_shuf, y_orig)
    sha = sha256_arr(y_shuf.astype(np.int8))
    return y_shuf, sha


def prep_repair_df(df):
    df = df.copy()
    df["days_since_last_repair"] = df["days_since_last_repair"].fillna(-1)
    for c in REPAIR_HISTORY:
        if c in df.columns:
            df[c] = df[c].fillna(-1)
    return df


def run_repair_model(
    perm_seed: int,
    subsample: float,
    colsample_bytree: float,
    y_orig: np.ndarray,
    val_tbl,
    y_val: np.ndarray,
    save_preds: bool = False,
) -> dict:
    """Train repair-only model with given perm/sampling config."""
    y_shuf, shuf_sha = permute_labels(y_orig, perm_seed)
    label = f"perm{perm_seed}_sub{subsample}_col{colsample_bytree}"
    section(f"REPAIR-ONLY: {label}")

    cache_dir = tempfile.mkdtemp(prefix=f"rep_{label[:30]}_")
    cache_fp  = hashlib.sha256(cache_dir.encode()).hexdigest()
    print(f"  cache_dir: {cache_dir}")
    print(f"  shuf_sha: {shuf_sha[:16]}...")

    try:
        # Load and transform train
        chunks = []
        for batch in pq.ParquetFile(TRAIN_PATH).iter_batches(
            batch_size=200_000, columns=REPAIR_HISTORY
        ):
            df = batch.to_pandas()
            chunks.append(prep_repair_df(df).values.astype(np.float32))
            del df, batch
            gc.collect()
        X_train = np.vstack(chunks)
        del chunks
        gc.collect()

        dm_train = xgb.DMatrix(X_train, label=y_shuf.astype(np.float32),
                                feature_names=REPAIR_HISTORY)
        del X_train
        gc.collect()

        meta   = json.loads((MODEL_DIR / "metadata.json").read_text())
        params = dict(meta["params"])
        params["seed"]             = MODEL_SEED
        params["nthread"]          = 1
        params["subsample"]        = subsample
        params["colsample_bytree"] = colsample_bytree
        params.pop("eval_metric", None)
        params["eval_metric"] = "aucpr"

        t0  = time.perf_counter()
        bst = xgb.train(params, dm_train, num_boost_round=FIXED_ROUNDS)
        elapsed = time.perf_counter() - t0
        del dm_train
        gc.collect()

        # Val predictions
        X_val_df = val_tbl.select(REPAIR_HISTORY).to_pandas()
        X_val_np = prep_repair_df(X_val_df).values.astype(np.float32)
        dm_val   = xgb.DMatrix(X_val_np, feature_names=REPAIR_HISTORY)
        del X_val_df, X_val_np

        preds = bst.predict(dm_val, iteration_range=(0, FIXED_ROUNDS))

        # Feature importances (gain)
        importances = bst.get_score(importance_type="gain")
        importances_cover = bst.get_score(importance_type="cover")

        del bst
        gc.collect()

        pred_sha = sha256_arr(preds.astype(np.float32))
        ap    = float(average_precision_score(y_val, preds))
        auc   = float(roc_auc_score(y_val, preds))
        brier = float(brier_score_loss(y_val, preds))
        pstd  = float(preds.std())
        prev  = float(y_val.mean())

        print(f"  AP={ap:.6f}  AP/prev={ap/prev:.4f}  AUC={auc:.6f}  "
              f"Brier={brier:.6f}  pred_std={pstd:.4f}  time={elapsed:.1f}s")

        result = {
            "label": label,
            "perm_seed": perm_seed, "model_seed": MODEL_SEED,
            "subsample": subsample, "colsample_bytree": colsample_bytree,
            "feature_set": "repair_history_only",
            "feature_count": len(REPAIR_HISTORY),
            "cache_fingerprint": cache_fp,
            "shuf_label_sha256": shuf_sha,
            "pred_sha256": pred_sha,
            "val_prevalence": round(prev, 8),
            "null_ap": round(ap, 8),
            "ap_over_prevalence": round(ap / prev, 6),
            "ap_minus_prevalence": round(ap - prev, 8),
            "null_roc_auc": round(auc, 8),
            "auc_minus_half": round(auc - 0.5, 8),
            "null_brier": round(brier, 8),
            "pred_std": round(pstd, 6),
            "train_time_s": round(elapsed, 1),
            "feature_importance_gain": {k: round(v, 4) for k, v in
                                         sorted(importances.items(),
                                                key=lambda x: -x[1])},
            "feature_importance_cover": {k: round(v, 4) for k, v in
                                          sorted(importances_cover.items(),
                                                 key=lambda x: -x[1])},
            "b1_accessed": False, "embargo_accessed": False, "b2_accessed": False,
        }

        if save_preds:
            preds_path = (_REPO_ROOT / "models/phase_6"
                          / "repair_only_perm137_preds.npy")
            np.save(str(preds_path), preds.astype(np.float32))
            result["preds_saved_to"] = str(preds_path)
            print(f"  Predictions saved: {preds_path}")

        return result

    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def main() -> None:  # noqa: C901
    print("=" * 70)
    print("PHASE 6 REPAIR-HISTORY NULL AP INVESTIGATION — PARTS 1 & 2")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("model_seed=42, features=repair_history_only (23)")
    print("=" * 70)

    check_sealed()

    print("\nLoading shared data...")
    val_tbl = pq.read_table(VAL_PATH)
    y_val   = np.array(val_tbl.column("target_repair_90d").to_pylist(), dtype=float)
    train_y = pq.read_table(TRAIN_PATH, columns=["target_repair_90d"])
    y_orig  = np.array(train_y.column("target_repair_90d").to_pylist(), dtype=np.int8)
    del train_y
    prev    = float(y_val.mean())
    print(f"  n_train={len(y_orig):,}  n_val={len(y_val):,}  val_prev={prev:.8f}")

    results = {}

    # -----------------------------------------------------------------------
    # PART 1 — Cross-seed controls
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PART 1 — Cross-seed repair-only controls (sub=0.8, col=0.8)")
    print("=" * 70)
    for perm in [42, 137, 2026]:
        save = (perm == 137)  # save preds for perm=137 (used in Part 4)
        key = f"part1_perm{perm}_model{MODEL_SEED}"
        results[key] = run_repair_model(
            perm_seed=perm, subsample=0.8, colsample_bytree=0.8,
            y_orig=y_orig, val_tbl=val_tbl, y_val=y_val,
            save_preds=save,
        )

    # -----------------------------------------------------------------------
    # PART 2 — Sampling isolation (perm=137, repair-only)
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PART 2 — Sampling isolation (perm=137, repair-only)")
    print("=" * 70)
    # A is already in Part 1 (perm=137, sub=0.8, col=0.8) — reference
    for sub, col, lbl in [
        (1.0, 0.8, "B_sub1.0_col0.8"),
        (0.8, 1.0, "C_sub0.8_col1.0"),
        (1.0, 1.0, "D_sub1.0_col1.0"),
    ]:
        key = f"part2_{lbl}"
        results[key] = run_repair_model(
            perm_seed=137, subsample=sub, colsample_bytree=col,
            y_orig=y_orig, val_tbl=val_tbl, y_val=y_val,
            save_preds=False,
        )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PART 1 — Cross-seed repair-only (sub=0.8, col=0.8)")
    print("=" * 70)
    print(f"  {'perm':>6}  {'AP':>10}  {'AP/prev':>8}  {'AUC':>10}  {'Brier':>10}")
    for perm in [42, 137, 2026]:
        r = results[f"part1_perm{perm}_model{MODEL_SEED}"]
        print(f"  {perm:>6}  {r['null_ap']:>10.6f}  "
              f"{r['ap_over_prevalence']:>8.4f}  "
              f"{r['null_roc_auc']:>10.6f}  {r['null_brier']:>10.6f}")

    ref = results["part1_perm137_model42"]
    print("\n  Reference A (perm=137, sub=0.8, col=0.8):")
    print(f"    AP={ref['null_ap']:.6f}  AP/prev={ref['ap_over_prevalence']:.4f}  "
          f"AUC={ref['null_roc_auc']:.6f}")

    print("\n" + "=" * 70)
    print("  PART 2 — Sampling isolation (perm=137, repair-only)")
    print("=" * 70)
    print(f"  {'Config':<20}  {'sub':>5}  {'col':>5}  {'AP':>10}  "
          f"{'AP/prev':>8}  {'AUC':>10}")
    configs = [
        ("A_sub0.8_col0.8 [ref]", "part1_perm137_model42", 0.8, 0.8),
        ("B_sub1.0_col0.8",        "part2_B_sub1.0_col0.8", 1.0, 0.8),
        ("C_sub0.8_col1.0",        "part2_C_sub0.8_col1.0", 0.8, 1.0),
        ("D_sub1.0_col1.0",        "part2_D_sub1.0_col1.0", 1.0, 1.0),
    ]
    for name, key, sub, col in configs:
        r = results[key]
        print(f"  {name:<20}  {sub:>5.1f}  {col:>5.1f}  "
              f"{r['null_ap']:>10.6f}  {r['ap_over_prevalence']:>8.4f}  "
              f"{r['null_roc_auc']:>10.6f}")

    print("\n  Feature importance (gain) for perm=137:")
    imp = results["part1_perm137_model42"]["feature_importance_gain"]
    for feat, val in list(imp.items())[:10]:
        print(f"    {feat}: {val:.2f}")

    # Write report
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_seed": MODEL_SEED,
        "feature_set": "repair_history_only",
        "feature_list": REPAIR_HISTORY,
        "val_prevalence": round(prev, 8),
        "runs": results,
        "b1_accessed": False, "embargo_accessed": False, "b2_accessed": False,
    }
    out = _REPO_ROOT / "models/phase_6/repair_history_investigation.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
