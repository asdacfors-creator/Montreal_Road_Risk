"""Phase 6 — Repair feature temporal audit (Part 3) + Score-tail diagnostic (Part 4).

Part 3: Verify all 23 repair features are bounded at as_of_date. Hard-fail if any
        feature uses events after as_of_date or within the target window.

Part 4: Precision/recall at top 1/5/10/20%, feature deciles vs shuffled/real prevalence.

Reads saved predictions from Part 1 (repair_only_perm137_preds.npy).
No training. No sealed targets accessed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

_REPO_ROOT = Path(__file__).resolve().parents[1]

VAL_PATH   = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
TRAIN_PATH = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
PREDS_PATH = _REPO_ROOT / "models/phase_6/repair_only_perm137_preds.npy"
INV_JSON   = _REPO_ROOT / "models/phase_6/repair_history_investigation.json"
PERM_SEED  = 137

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
]

SEALED_ANCHORS = {
    "2024-01-31","2024-02-29","2024-03-31",
    "2024-04-30","2024-05-31","2024-06-30",
    "2024-07-31","2024-08-31","2024-09-30","2024-10-31","2024-11-30",
    "2024-12-31","2025-01-31","2025-02-28","2025-03-31",
    "2025-04-30","2025-05-31",
}

# Expected maximum values for bounded features (None = unbounded, e.g., counts)
# For "months in 12-month window", max = 12 distinct months
# For "active days in Xd window", max = X days
# For event COUNTS, no bound applies (multiple events per day possible)
HARD_BOUNDS = {
    "prior_repair_months_12m": 12,
    "repair_active_days_30d":  30,
    "repair_active_days_90d":  90,
    "repair_active_days_180d": 180,
    "repair_active_days_365d": 365,
    "repair_history_valid_days_30d":  30,
    "repair_history_valid_days_90d":  90,
    "repair_history_valid_days_180d": 180,
    "repair_history_valid_days_365d": 365,
}

# Feature metadata: window definition
FEATURE_META = {
    "days_since_last_repair": {
        "window": "all history",
        "earliest": "all data",
        "latest": "event_date <= as_of_date (line 601)",
        "upper_bound_in_code": True,
        "dtype": "float (nullable)",
        "missing": "NaN → fillna(-1) before model",
    },
    "no_prior_repair_flag": {
        "window": "all history",
        "earliest": "all data",
        "latest": "event_date <= as_of_date (line 601)",
        "upper_bound_in_code": True,
        "dtype": "int",
        "missing": "0 = prior repairs exist, 1 = no prior repairs",
    },
    "prior_repair_months_12m": {
        "window": "12 months before as_of_date",
        "earliest": "(as_of_date - 11 months).replace(day=1)",
        "latest": "MISSING UPPER BOUND — no event_date <= as_of_date filter (line 638)",
        "upper_bound_in_code": False,  # BUG
        "dtype": "int",
        "missing": "0 if no repairs in window",
    },
}
# All windowed features (30d/90d/180d/365d) use: event_date > w_start AND event_date <= t
for w in [30, 90, 180, 365]:
    for prefix, suffix in [
        ("repair_active_days", f"_{w}d"),
        ("repair_event_count_collapsed", f"_{w}d"),
        ("repair_history_complete", f"_{w}d"),
        ("repair_history_coverage_ratio", f"_{w}d"),
        ("repair_history_valid_days", f"_{w}d"),
    ]:
        feat = f"{prefix}{suffix}"
        if feat in REPAIR_HISTORY:
            FEATURE_META[feat] = {
                "window": f"{w} days before as_of_date",
                "earliest": f"as_of_date - {w} days",
                "latest": "event_date <= as_of_date (line 614)",
                "upper_bound_in_code": True,
                "dtype": "int or float",
                "missing": "0 if no activity in window",
            }


def section(msg: str) -> None:
    print(f"\n{'='*70}\n  {msg}\n{'='*70}")


def main() -> None:  # noqa: C901
    print("=" * 70)
    print("PHASE 6 REPAIR TEMPORAL AUDIT + SCORE-TAIL DIAGNOSTIC")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Sealed check
    val_dates = pq.read_table(VAL_PATH, columns=["as_of_date"])
    dates = {str(d)[:10] for d in val_dates.column("as_of_date").to_pylist()}
    bad = dates & SEALED_ANCHORS
    assert not bad, f"ABORT: sealed anchors in val: {bad}"

    # -----------------------------------------------------------------------
    # PART 3 — Temporal audit
    # -----------------------------------------------------------------------
    section("PART 3 — Repair feature temporal audit")

    # Load val repair features + target
    val_df = pq.read_table(VAL_PATH,
                           columns=REPAIR_HISTORY + ["target_repair_90d", "as_of_date"]
                           ).to_pandas()
    val_df["as_of_date"] = pd.to_datetime(val_df["as_of_date"])
    n_val = len(val_df)
    print(f"\n  Val rows: {n_val:,}")
    print(f"  Val anchor range: {val_df['as_of_date'].min().date()} to {val_df['as_of_date'].max().date()}")

    # Load train for the same
    train_rep = pq.read_table(TRAIN_PATH,
                               columns=REPAIR_HISTORY + ["target_repair_90d", "as_of_date"]
                               ).to_pandas()
    train_rep["as_of_date"] = pd.to_datetime(train_rep["as_of_date"])
    n_train = len(train_rep)

    # Permuted labels (perm=137)
    rng    = np.random.default_rng(PERM_SEED)
    perm   = rng.permutation(n_train)
    y_orig = train_rep["target_repair_90d"].values.astype(np.int8)
    y_shuf = y_orig[perm]

    hard_fails = []
    audit_rows = []

    for feat in REPAIR_HISTORY:
        meta = FEATURE_META.get(feat, {})
        col  = val_df[feat]
        col_tr = train_rep[feat]

        mx_val   = float(col.max())
        mx_tr    = float(col_tr.max())
        miss_pct = round(100.0 * col.isna().sum() / n_val, 2)
        card     = int(col.nunique(dropna=True))
        corr_real = round(float(col.corr(val_df["target_repair_90d"])), 4)
        # Shuffled-label correlation (train)
        try:
            corr_shuf = round(float(
                pd.Series(col_tr.values).corr(pd.Series(y_shuf.astype(float)))
            ), 4)
        except Exception:
            corr_shuf = None

        # Hard-bound check
        bound = HARD_BOUNDS.get(feat)
        exceeds = (bound is not None and mx_val > bound)
        exceeds_train = (bound is not None and mx_tr > bound)

        # Feature importance from investigation JSON (if available)
        gain_imp = None
        if INV_JSON.exists():
            inv = json.loads(INV_JSON.read_text())
            ref_run = inv["runs"].get("part1_perm137_model42", {})
            gain_imp = ref_run.get("feature_importance_gain", {}).get(feat)

        row = {
            "feature": feat,
            "window": meta.get("window", "unknown"),
            "earliest": meta.get("earliest", "unknown"),
            "latest": meta.get("latest", "unknown"),
            "upper_bound_in_code": meta.get("upper_bound_in_code", True),
            "missing_value": meta.get("missing", ""),
            "dtype": str(col.dtype),
            "cardinality": card,
            "val_max": mx_val,
            "train_max": mx_tr,
            "hard_bound": bound,
            "exceeds_bound": exceeds,
            "exceeds_bound_train": exceeds_train,
            "missing_pct_val": miss_pct,
            "corr_shuf_label_train": corr_shuf,
            "corr_real_label_val": corr_real,
            "xgb_gain_importance_perm137": gain_imp,
        }
        audit_rows.append(row)

        status = "HARD FAIL" if not meta.get("upper_bound_in_code", True) else (
            "BOUND EXCEEDED" if exceeds else "OK"
        )
        print(f"\n  {feat}:")
        print(f"    window={meta.get('window','?')}  "
              f"upper_bound_in_code={meta.get('upper_bound_in_code', True)}  "
              f"status={status}")
        print(f"    val_max={mx_val:.1f}  hard_bound={bound}  exceeds={exceeds}")
        print(f"    corr_shuf={corr_shuf}  corr_real={corr_real}  "
              f"gain_imp={gain_imp}  card={card}  miss_pct={miss_pct}%")

        if not meta.get("upper_bound_in_code", True):
            hard_fails.append({
                "feature": feat,
                "reason": "Missing upper-bound filter (event_date <= as_of_date)",
                "code_location": "build_segment_month_panel.py:638",
                "evidence": {
                    "val_max": mx_val, "hard_bound": bound,
                    "val_rows_exceeding": int((col > bound).sum()) if bound else None,
                    "train_rows_exceeding": int((col_tr > bound).sum()) if bound else None,
                    "train_max": mx_tr,
                    "corr_real_label_val": corr_real,
                }
            })

    print(f"\n  HARD FAILS: {len(hard_fails)}")
    for hf in hard_fails:
        print(f"  !! {hf['feature']}: {hf['reason']}")
        print(f"     val_max={hf['evidence']['val_max']}  bound={hf['evidence']['hard_bound']}")
        print(f"     val rows > bound: {hf['evidence']['val_rows_exceeding']}")
        print(f"     train rows > bound: {hf['evidence']['train_rows_exceeding']}")
        print(f"     corr(real_label)={hf['evidence']['corr_real_label_val']}")

    # -----------------------------------------------------------------------
    # PART 4 — Score-tail diagnostic
    # -----------------------------------------------------------------------
    section("PART 4 — Score-tail diagnostic (perm=137, repair-only)")

    if not PREDS_PATH.exists():
        print(f"  Predictions not yet available at {PREDS_PATH}")
        print("  Part 4 will complete after Part 1 training finishes.")
        preds = None
    else:
        preds = np.load(str(PREDS_PATH))
        print(f"  Loaded predictions: {len(preds):,} rows")

    tail_results = {}
    if preds is not None:
        y_val_real = val_df["target_repair_90d"].values.astype(float)
        n          = len(y_val_real)
        prev       = float(y_val_real.mean())

        # Sort descending by score
        order = np.argsort(preds)[::-1]

        print(f"\n  val_prev={prev:.6f}  n={n:,}")
        print(f"\n  {'Threshold':>10}  {'N rows':>7}  {'N pos':>6}  {'Precision':>10}  {'Recall':>8}")
        for pct in [1, 5, 10, 20]:
            k      = max(1, int(n * pct / 100))
            top_k  = order[:k]
            n_pos  = int(y_val_real[top_k].sum())
            prec   = n_pos / k
            recall = n_pos / max(1, y_val_real.sum())
            print(f"  top {pct:>2}%  ({pct/100:.2f})  {k:>7,}  {n_pos:>6}  "
                  f"{prec:>10.4f}  {recall:>8.4f}")
            tail_results[f"top_{pct}pct"] = {
                "threshold_pct": pct,
                "n_rows": k,
                "n_positives": n_pos,
                "precision": round(prec, 6),
                "recall": round(float(recall), 6),
                "precision_over_prevalence": round(prec / prev, 4),
            }

        # Feature decile analysis
        print("\n  Repair-feature prevalence by decile (shuffled-train vs real-val):")
        print("  Feature: prior_repair_months_12m (the flagged leakage feature)")
        feat_col_val   = val_df["prior_repair_months_12m"].values
        feat_col_tr    = train_rep["prior_repair_months_12m"].values

        decile_labels_val = pd.qcut(pd.Series(feat_col_val), q=10,
                                     labels=False, duplicates="drop")
        decile_labels_tr  = pd.qcut(pd.Series(feat_col_tr), q=10,
                                     labels=False, duplicates="drop")

        decile_results = {}
        print(f"\n  {'Decile':>7}  {'shuf_tr_prev':>13}  {'real_val_prev':>14}  "
              f"{'ratio':>6}")
        for d in sorted(pd.Series(decile_labels_val).dropna().unique()):
            mask_val = (decile_labels_val == d).values
            mask_tr  = (decile_labels_tr == d).values if len(decile_labels_tr) == n_train else None
            rp_val   = float(y_val_real[mask_val].mean()) if mask_val.sum() > 0 else 0.0
            rp_shuf  = float(y_shuf[mask_tr].mean()) if mask_tr is not None and mask_tr.sum() > 0 else None
            ratio    = rp_val / prev if prev > 0 else 0
            print(f"  {int(d):>7}  {rp_shuf if rp_shuf is not None else 'N/A':>13.4f}  "
                  f"{rp_val:>14.4f}  {ratio:>6.3f}x")
            decile_results[str(int(d))] = {
                "real_val_prevalence": round(rp_val, 6),
                "shuf_train_prevalence": round(rp_shuf, 6) if rp_shuf else None,
                "real_val_over_global": round(ratio, 4),
            }

        # Top-score bucket: which repair features are highest?
        if INV_JSON.exists():
            inv   = json.loads(INV_JSON.read_text())
            ref   = inv["runs"].get("part1_perm137_model42", {})
            gains = ref.get("feature_importance_gain", {})
            print("\n  Feature importance (gain) for repair-only perm=137:")
            top_feats = sorted(gains.items(), key=lambda x: -x[1])[:10]
            for feat, g in top_feats:
                print(f"    {feat}: {g:.2f}")

        # Score by high-value prior_repair_months_12m
        print("\n  Score distribution for segments with prior_repair_months_12m > 12:")
        mask_over = feat_col_val > 12
        if mask_over.sum() > 0:
            scores_over = preds[mask_over]
            labels_over = y_val_real[mask_over]
            print(f"    n_rows={mask_over.sum()}, "
                  f"mean_score={scores_over.mean():.4f}, "
                  f"real_prev={labels_over.mean():.4f}")
        else:
            print("    No val rows with prior_repair_months_12m > 12")
    else:
        decile_results = {}

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "perm_seed": PERM_SEED,
        "part3_temporal_audit": {
            "features_audited": len(audit_rows),
            "hard_fails": hard_fails,
            "hard_fail_count": len(hard_fails),
            "feature_details": audit_rows,
        },
        "part4_tail_diagnostic": {
            "preds_available": preds is not None,
            "tail_metrics": tail_results,
            "prior_repair_months_12m_deciles": decile_results,
        },
        "b1_accessed": False,
        "embargo_accessed": False,
        "b2_accessed": False,
    }
    out = _REPO_ROOT / "models/phase_6/repair_temporal_audit.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport written: {out}")

    if hard_fails:
        print("\n" + "!" * 70)
        print("  HARD FAIL — LEAKAGE FOUND IN REPAIR FEATURE CONSTRUCTION")
        print("!" * 70)
        for hf in hard_fails:
            print(f"\n  Feature: {hf['feature']}")
            print(f"  Reason: {hf['reason']}")
            print(f"  Location: {hf['code_location']}")
    else:
        print("\n[OK] All repair features pass temporal audit.")


if __name__ == "__main__":
    main()
