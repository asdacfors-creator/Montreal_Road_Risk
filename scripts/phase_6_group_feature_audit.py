"""Phase 6 — Group structure audit (Part 2) + Feature-proxy audit (Part 3).

Part 2: Group prevalence correlation between shuffled-train labels and val labels.
Part 3: Feature-proxy audit — cardinality, stability, segment-proxy risk.

No training. No sealed targets accessed.
canonical_segment_id used for diagnosis only — does not enter the estimator.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

_REPO_ROOT = Path(__file__).resolve().parents[1]

TRAIN_PATH = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
VAL_PATH   = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
PERM_SEED  = 137
MIN_GROUP_SIZE = 500   # minimum rows for group to be included in prevalence analysis

SEALED_ANCHORS = {
    "2024-01-31","2024-02-29","2024-03-31",
    "2024-04-30","2024-05-31","2024-06-30",
    "2024-07-31","2024-08-31","2024-09-30","2024-10-31","2024-11-30",
    "2024-12-31","2025-01-31","2025-02-28","2025-03-31",
    "2025-04-30","2025-05-31",
}


def section(msg: str) -> None:
    print(f"\n{'='*70}\n  {msg}\n{'='*70}")


# ---------------------------------------------------------------------------
# PART 2 helpers
# ---------------------------------------------------------------------------

def group_prevalence(df: pd.DataFrame, group_col: str, label_col: str,
                     min_size: int = MIN_GROUP_SIZE) -> pd.DataFrame:
    """Compute per-group label prevalence, filtered by min_size."""
    g = df.groupby(group_col, observed=True)[label_col].agg(["sum", "count"])
    g.columns = ["positives", "count"]
    g = g[g["count"] >= min_size].copy()
    g["prevalence"] = g["positives"] / g["count"]
    return g.sort_values("prevalence", ascending=False)


def report_group(name: str, train_orig: pd.DataFrame, train_shuf: pd.DataFrame,
                 val: pd.DataFrame, group_col: str) -> dict:
    """Report group-level prevalence stats and cross-split correlation."""
    # Only use groups present in all three splits
    gp_orig = group_prevalence(train_orig, group_col, "target_repair_90d")
    gp_shuf = group_prevalence(train_shuf, group_col, "y_shuf")
    gp_val  = group_prevalence(val,        group_col, "target_repair_90d")

    common = gp_orig.index.intersection(gp_shuf.index).intersection(gp_val.index)
    if len(common) < 3:
        return {"grouping": name, "group_col": group_col,
                "n_groups": len(common), "skip": "too few shared groups"}

    orig_prev = gp_orig.loc[common, "prevalence"]
    shuf_prev = gp_shuf.loc[common, "prevalence"]
    val_prev  = gp_val.loc[common,  "prevalence"]

    corr_shuf_val  = float(shuf_prev.corr(val_prev))
    corr_orig_val  = float(orig_prev.corr(val_prev))
    corr_shuf_orig = float(shuf_prev.corr(orig_prev))

    # Groups with largest shuf-val absolute difference
    diff = (shuf_prev - val_prev).abs().sort_values(ascending=False)
    top5_diff = {str(k): round(float(v), 6) for k, v in diff.head(5).items()}

    result = {
        "grouping": name,
        "group_col": group_col,
        "n_groups_total": len(gp_orig),
        "n_groups_common": len(common),
        "min_group_size": MIN_GROUP_SIZE,
        "shuf_prev_min": round(float(shuf_prev.min()), 6),
        "shuf_prev_max": round(float(shuf_prev.max()), 6),
        "shuf_prev_std": round(float(shuf_prev.std()), 6),
        "val_prev_min":  round(float(val_prev.min()), 6),
        "val_prev_max":  round(float(val_prev.max()), 6),
        "val_prev_std":  round(float(val_prev.std()), 6),
        "corr_shuf_vs_val":  round(corr_shuf_val, 4),
        "corr_orig_vs_val":  round(corr_orig_val, 4),
        "corr_shuf_vs_orig": round(corr_shuf_orig, 4),
        "top5_abs_diff_groups": top5_diff,
    }

    print(f"\n  [{name}] col={group_col} n_groups={len(common)}")
    print(f"    shuf_prev range: [{shuf_prev.min():.4f}, {shuf_prev.max():.4f}]  "
          f"std={shuf_prev.std():.4f}")
    print(f"    corr(shuf_train, val) = {corr_shuf_val:+.4f}")
    print(f"    corr(orig_train, val) = {corr_orig_val:+.4f}")
    print(f"    corr(shuf, orig_train)= {corr_shuf_orig:+.4f}")
    if abs(corr_shuf_val) > 0.4:
        print("    !! HIGH correlation — shuffled labels cluster with val-prevalent groups")

    return result


# ---------------------------------------------------------------------------
# PART 3 helpers
# ---------------------------------------------------------------------------

FAMILY_MAP = {}
for f in [
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
]:
    FAMILY_MAP[f] = "repair_history"

for f in [
    "administrative_category", "boundary_candidate_count", "boundary_crossing_flag",
    "functional_road_class", "future_asset_record_hidden_flag",
    "official_administrative_name", "resurfacing_before_construction_candidate_flag",
    "road_category", "road_type", "segment_length_m", "unmatched_boundary_flag",
]:
    FAMILY_MAP[f] = "static_admin"

for f in [
    "age_interval_crosses_as_of_flag", "asset_temporal_eligibility_status",
    "condition_campaign_scope", "condition_candidate_count", "condition_missing_flag",
    "date_contradiction_status", "days_since_condition_survey",
    "iri_max", "iri_min", "iri_std", "latest_iri", "latest_pci",
    "pci_max", "pci_min", "pci_std",
    "resurfacing_interval_crosses_as_of_flag",
    "years_since_construction_lower", "years_since_construction_upper",
    "years_since_resurfacing_lower", "years_since_resurfacing_upper",
]:
    FAMILY_MAP[f] = "pavement_asset"

for f in [
    "freeze_thaw_max_ge_zero_sum_30d","freeze_thaw_max_ge_zero_sum_90d",
    "freeze_thaw_max_ge_zero_sum_180d","freeze_thaw_max_ge_zero_sum_365d",
    "freeze_thaw_min_le_zero_sum_30d","freeze_thaw_min_le_zero_sum_90d",
    "freeze_thaw_min_le_zero_sum_180d","freeze_thaw_min_le_zero_sum_365d",
    "freeze_thaw_strict_sum_30d","freeze_thaw_strict_sum_90d",
    "freeze_thaw_strict_sum_180d","freeze_thaw_strict_sum_365d",
    "max_temp_fallback_days_30d","max_temp_fallback_days_90d",
    "max_temp_fallback_days_180d","max_temp_fallback_days_365d",
    "max_temp_max_30d","max_temp_max_90d","max_temp_max_180d","max_temp_max_365d",
    "mean_temp_fallback_days_30d","mean_temp_fallback_days_90d",
    "mean_temp_fallback_days_180d","mean_temp_fallback_days_365d",
    "mean_temp_mean_30d","mean_temp_mean_90d","mean_temp_mean_180d","mean_temp_mean_365d",
    "min_temp_fallback_days_30d","min_temp_fallback_days_90d",
    "min_temp_fallback_days_180d","min_temp_fallback_days_365d",
    "min_temp_min_30d","min_temp_min_90d","min_temp_min_180d","min_temp_min_365d",
    "total_precip_fallback_days_30d","total_precip_fallback_days_90d",
    "total_precip_fallback_days_180d","total_precip_fallback_days_365d",
    "total_precip_sum_30d","total_precip_sum_90d",
    "total_precip_sum_180d","total_precip_sum_365d",
    "weather_complete_30d","weather_complete_90d",
    "weather_complete_180d","weather_complete_365d",
    "weather_coverage_ratio_30d","weather_coverage_ratio_90d",
    "weather_coverage_ratio_180d","weather_coverage_ratio_365d",
    "weather_valid_days_30d","weather_valid_days_90d",
    "weather_valid_days_180d","weather_valid_days_365d",
]:
    FAMILY_MAP[f] = "weather_temporal"

# Columns that vary only with time (not with segment): weather_temporal
# Columns stable across months for same segment: static_admin, most pavement_asset
# Columns that could proxy segment identity: official_administrative_name, road_type,
#   road_category, administrative_category, functional_road_class, segment_length_m

SEGMENT_PROXY_RISK = {
    "official_administrative_name": "LOW — borough-level (35 values), not segment",
    "road_type": "LOW — road type in French (31 values, e.g. rue/avenue/boulevard)",
    "road_category": "LOW — road category (small cardinality)",
    "administrative_category": "LOW — admin category (small cardinality)",
    "functional_road_class": "LOW — integer road class (small range)",
    "segment_length_m": "MEDIUM — unique per segment geometry, but continuous",
    "days_since_last_repair": "LOW — varies by month, not a segment ID",
    "repair_event_count_collapsed_365d": "LOW — aggregated count",
    "canonical_segment_id": "NOT IN X — used for diagnosis only",
}

FUTURE_DERIVED_CHECK = {
    "future_asset_record_hidden_flag": (
        "IN X — vetted in Phase 5. Reflects asset record existence, "
        "not a future repair outcome. exclude_from_X does NOT include it."
    ),
}


def main() -> None:  # noqa: C901
    print("=" * 70)
    print("PHASE 6 GROUP STRUCTURE + FEATURE-PROXY AUDIT")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Sealed check
    val_dates = pq.read_table(VAL_PATH, columns=["as_of_date"])
    dates = {str(d)[:10] for d in val_dates.column("as_of_date").to_pylist()}
    bad = dates & SEALED_ANCHORS
    assert not bad, f"ABORT: sealed anchors in val: {bad}"

    cfg = json.loads((_REPO_ROOT / "config/phase_5_modeling.json").read_text())
    excl = set(cfg.get("exclude_from_X", []))
    id_cols = {"segment_month_id", "canonical_segment_id", "as_of_date",
               "target_repair_90d"}
    cat_cols = set(cfg.get("categorical_cols", []))

    # -----------------------------------------------------------------------
    # PART 2 — Load train (with shuffled labels + grouping columns)
    # -----------------------------------------------------------------------
    section("PART 2 — Shuffled-label group structure")

    GROUPING_COLS = [
        "as_of_date", "official_administrative_name", "functional_road_class",
        "condition_missing_flag", "future_asset_record_hidden_flag",
        "no_prior_repair_flag", "road_type", "road_category", "administrative_category",
    ]

    # Load train
    train_load_cols_with_date = list(dict.fromkeys(
        ["target_repair_90d", "canonical_segment_id", "as_of_date"] + GROUPING_COLS
    ))

    print("\nLoading train labels + grouping columns...")
    train_tbl = pq.read_table(TRAIN_PATH, columns=train_load_cols_with_date)
    train_df  = train_tbl.to_pandas()
    n_train   = len(train_df)
    print(f"  Train rows: {n_train:,}")

    # Permute labels
    rng    = np.random.default_rng(PERM_SEED)
    perm   = rng.permutation(n_train)
    y_orig = train_df["target_repair_90d"].values.astype(np.int8)
    y_shuf = y_orig[perm]
    shuf_sha = hashlib.sha256(y_shuf.tobytes()).hexdigest()
    print(f"  shuf_sha (16): {shuf_sha[:16]}...")
    print(f"  Original prevalence: {y_orig.mean():.6f}")
    print(f"  Shuffled prevalence: {y_shuf.mean():.6f}")

    train_df["y_shuf"] = y_shuf

    # Month grouping (anchor month string)
    train_df["anchor_month"] = train_df["as_of_date"].astype(str).str[:10]

    # Load val
    print("\nLoading val labels + grouping columns...")
    val_load_cols = list(dict.fromkeys(
        ["target_repair_90d", "as_of_date", "canonical_segment_id"] + GROUPING_COLS
    ))
    val_tbl = pq.read_table(VAL_PATH, columns=val_load_cols)
    val_df  = val_tbl.to_pandas()
    val_df["anchor_month"] = val_df["as_of_date"].astype(str).str[:10]
    n_val = len(val_df)
    print(f"  Val rows: {n_val:,}")
    print(f"  Val prevalence: {val_df['target_repair_90d'].mean():.6f}")

    # Train shuf split (without canonical_segment_id to avoid it entering any model)
    train_shuf = train_df.copy()

    # Group analyses
    groupings = [
        ("anchor_month",              "anchor_month"),
        ("borough",                   "official_administrative_name"),
        ("functional_road_class",     "functional_road_class"),
        ("condition_missing",         "condition_missing_flag"),
        ("asset_hidden",              "future_asset_record_hidden_flag"),
        ("prior_repair_status",       "no_prior_repair_flag"),
        ("road_type",                 "road_type"),
        ("road_category",             "road_category"),
        ("administrative_category",   "administrative_category"),
    ]

    group_results = []
    for gname, gcol in groupings:
        if gcol not in train_df.columns:
            print(f"  [SKIP] {gname}: column {gcol} not found in train")
            continue
        res = report_group(
            name=gname,
            train_orig=train_df,
            train_shuf=train_shuf,
            val=val_df,
            group_col=gcol,
        )
        group_results.append(res)

    # Segment-level analysis (canonical_segment_id, diagnosis only)
    section("PART 2b — Segment-level diagnosis (diagnosis only, not in estimator)")
    seg_shuf_prev = train_shuf.groupby("canonical_segment_id").agg(
        n=("y_shuf", "count"),
        shuf_pos=("y_shuf", "sum"),
        orig_pos=("target_repair_90d", "sum"),
    )
    seg_shuf_prev = seg_shuf_prev[seg_shuf_prev["n"] >= 3].copy()
    seg_shuf_prev["shuf_prev"] = seg_shuf_prev["shuf_pos"] / seg_shuf_prev["n"]
    seg_shuf_prev["orig_prev"] = seg_shuf_prev["orig_pos"] / seg_shuf_prev["n"]

    seg_val_prev = val_df.groupby("canonical_segment_id").agg(
        n=("target_repair_90d", "count"),
        pos=("target_repair_90d", "sum"),
    )
    seg_val_prev = seg_val_prev[seg_val_prev["n"] >= 1].copy()
    seg_val_prev["val_prev"] = seg_val_prev["pos"] / seg_val_prev["n"]

    common_segs = seg_shuf_prev.index.intersection(seg_val_prev.index)
    corr_seg_shuf_val = float(
        seg_shuf_prev.loc[common_segs, "shuf_prev"].corr(
            seg_val_prev.loc[common_segs, "val_prev"]
        )
    )
    corr_seg_orig_val = float(
        seg_shuf_prev.loc[common_segs, "orig_prev"].corr(
            seg_val_prev.loc[common_segs, "val_prev"]
        )
    )
    print(f"\n  Segments analysed: {len(common_segs):,}")
    print(f"  corr(shuf_train_seg_prev, val_seg_prev) = {corr_seg_shuf_val:+.4f}")
    print(f"  corr(orig_train_seg_prev, val_seg_prev) = {corr_seg_orig_val:+.4f}")
    if abs(corr_seg_shuf_val) > 0.05:
        print("  !! Significant segment-level shuffled-label / val correlation")
    else:
        print("  [OK] Low segment-level correlation — no spatial clustering artefact")

    seg_diagnosis = {
        "n_common_segments": int(len(common_segs)),
        "corr_shuf_train_vs_val_prev": round(corr_seg_shuf_val, 4),
        "corr_orig_train_vs_val_prev": round(corr_seg_orig_val, 4),
    }

    # -----------------------------------------------------------------------
    # PART 3 — Feature-proxy audit
    # -----------------------------------------------------------------------
    section("PART 3 — Feature-proxy audit")

    feat_cols = [
        c for c in pq.read_schema(VAL_PATH).names
        if c not in excl and c not in id_cols
    ]
    val_sample = pq.read_table(VAL_PATH, columns=feat_cols).to_pandas()
    n_val_s = len(val_sample)

    # Also compute month-level stability per segment for key features
    # (uses a sample of train)
    print("\nComputing feature cardinality, missingness, stability...")

    feature_audit = []
    segment_stable_kws = ["segment_length_m", "road_type", "road_category",
                           "functional_road_class", "administrative_category",
                           "official_administrative_name",
                           "resurfacing_before_construction_candidate_flag",
                           "boundary_crossing_flag", "unmatched_boundary_flag",
                           "future_asset_record_hidden_flag",
                           "boundary_candidate_count",
                           "condition_candidate_count"]

    for c in feat_cols:
        col = val_sample[c]
        dtype    = str(col.dtype)
        is_cat   = c in cat_cols
        card     = int(col.nunique(dropna=True))
        miss_n   = int(col.isna().sum())
        miss_pct = round(100.0 * miss_n / n_val_s, 2)
        family   = FAMILY_MAP.get(c, "unknown")

        # Stability: is this feature constant across months for same segment?
        # (heuristic: weather features vary by month; others may be stable)
        if family == "weather_temporal":
            monthly_stable = False
        elif c in segment_stable_kws:
            monthly_stable = True
        elif family == "repair_history":
            monthly_stable = False  # repair history changes per month
        elif family == "pavement_asset":
            # Most pavement features stable until next survey; some vary
            monthly_stable = c not in [
                "days_since_condition_survey", "condition_campaign_scope",
                "age_interval_crosses_as_of_flag", "date_contradiction_status",
            ]
        else:
            monthly_stable = None  # unknown

        # Segment proxy risk
        if c in SEGMENT_PROXY_RISK:
            proxy_risk = SEGMENT_PROXY_RISK[c]
        elif c == "segment_length_m":
            proxy_risk = "MEDIUM — unique geometry; continuous; not categorical"
        elif family == "static_admin" and card > 10:
            proxy_risk = "LOW-MEDIUM — group feature, not row-unique identifier"
        elif family == "static_admin":
            proxy_risk = "LOW — low-cardinality group feature"
        else:
            proxy_risk = "NONE — temporal or aggregated feature"


        feature_audit.append({
            "feature": c,
            "family": family,
            "dtype": dtype,
            "is_categorical_config": is_cat,
            "cardinality": card,
            "missing_count": miss_n,
            "missing_pct": miss_pct,
            "monthly_stable": monthly_stable,
            "proxy_risk": proxy_risk,
            "future_derived_note": FUTURE_DERIVED_CHECK.get(c, ""),
        })

    # Print high-cardinality features
    print(f"\n  Total features audited: {len(feature_audit)}")
    high_card = [f for f in feature_audit if f["cardinality"] > 20]
    print(f"  High-cardinality (>20): {len(high_card)}")
    for f in high_card:
        print(f"    {f['feature']}: card={f['cardinality']}  "
              f"proxy_risk={f['proxy_risk']}")

    # Forbidden-feature final check
    print("\n  FORBIDDEN FEATURE FINAL CHECK:")
    target_in_x = [c for c in feat_cols if "target" in c.lower()]
    future_in_x = [c for c in feat_cols
                   if "future" in c.lower() and c not in FUTURE_DERIVED_CHECK]
    raw_in_x    = [c for c in feat_cols
                   if c.startswith("raw_") or "collapsed_future" in c]
    id_in_x     = [c for c in feat_cols
                   if c in {"segment_month_id", "canonical_segment_id", "as_of_date"}]
    print(f"    target_* in X: {target_in_x or 'NONE'}")
    print(f"    future_* in X (unexpected): {future_in_x or 'NONE'}")
    print(f"    raw_* or collapsed_future in X: {raw_in_x or 'NONE'}")
    print(f"    ID cols in X: {id_in_x or 'NONE'}")
    print(f"    future_asset_record_hidden_flag: IN X — "
          f"{FUTURE_DERIVED_CHECK['future_asset_record_hidden_flag']}")

    all_clean = (not target_in_x and not future_in_x
                 and not raw_in_x and not id_in_x)
    print(f"\n  Feature set CLEAN: {all_clean}")

    # -----------------------------------------------------------------------
    # Print summary tables
    # -----------------------------------------------------------------------
    section("PART 3 — Feature audit by family")
    for fam in ["repair_history", "static_admin", "pavement_asset", "weather_temporal"]:
        fam_feats = [f for f in feature_audit if f["family"] == fam]
        cat_count = sum(1 for f in fam_feats if f["is_categorical_config"])
        miss_any  = sum(1 for f in fam_feats if f["missing_pct"] > 0)
        stable    = sum(1 for f in fam_feats
                        if f["monthly_stable"] is True)
        print(f"\n  {fam} ({len(fam_feats)} features):")
        print(f"    categorical: {cat_count}  has_missing: {miss_any}  "
              f"monthly_stable: {stable}")
        for f in fam_feats:
            if f["proxy_risk"] not in ("NONE — temporal or aggregated feature",):
                print(f"    {f['feature']}: card={f['cardinality']}  "
                      f"proxy={f['proxy_risk']}")

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "perm_seed": PERM_SEED,
        "shuf_label_sha256": shuf_sha,
        "part2_group_analysis": {
            "groupings": group_results,
            "segment_diagnosis": seg_diagnosis,
        },
        "part3_feature_audit": {
            "total_features": len(feature_audit),
            "high_cardinality_gt20": [
                {"feature": f["feature"], "cardinality": f["cardinality"],
                 "proxy_risk": f["proxy_risk"]}
                for f in high_card
            ],
            "forbidden_feature_check": {
                "target_in_x": target_in_x,
                "future_in_x_unexpected": future_in_x,
                "raw_or_collapsed_future_in_x": raw_in_x,
                "id_cols_in_x": id_in_x,
                "feature_set_clean": all_clean,
            },
            "features": feature_audit,
        },
        "b1_accessed": False,
        "embargo_accessed": False,
        "b2_accessed": False,
    }
    out = _REPO_ROOT / "models/phase_6/group_feature_audit.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
