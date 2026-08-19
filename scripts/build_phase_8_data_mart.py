"""Build Phase 8 Target-Free Dashboard Data Mart script.

Constructs data/processed/phase_8/dashboard_data_mart.parquet by joining:
1. Target-free sealed features (527,813 B2 rows across 11 anchors)
2. B2 raw probabilities (527,813 rows)
3. Phase 7 Top-10% operational explanation records (52,782 rows)

Strict security & reconciliation assertions enforced:
- Exactly 527,813 rows, 11 anchors, 47,983 rows/anchor.
- Zero target/outcome/eligibility columns present.
- Mutually exclusive map priority bands (HIGH, MEDIUM, WATCH, OTHER).
- Cumulative Top-K policy booleans (in_top5_policy, in_top10_policy, in_top20_policy).
- Default message for rows outside Top-10%: 'Detailed segment explanation was not generated under the frozen Phase 7 scope.'
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEALED_FEAT_PATH = PROJECT_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"
B2_PRED_PATH = PROJECT_ROOT / "data/processed/phase_6/predictions/b2_predictions.parquet"
P7_RECORDS_PATH = PROJECT_ROOT / "data/processed/phase_7/b2_top10_explanation_records.parquet"
DATA_MART_PATH = PROJECT_ROOT / "data/processed/phase_8/dashboard_data_mart.parquet"

B2_ANCHORS = [
    "2024-07-31",
    "2024-08-31",
    "2024-09-30",
    "2024-10-31",
    "2024-11-30",
    "2024-12-31",
    "2025-01-31",
    "2025-02-28",
    "2025-03-31",
    "2025-04-30",
    "2025-05-31",
]
EXPECTED_TOTAL_ROWS = 527813
EXPECTED_PER_ANCHOR = 47983
EXPECTED_P7_ROWS = 52782

UNEXPLAINED_MSG = "Detailed segment explanation was not generated under the frozen Phase 7 scope."


def verify_target_free_schema(column_names: list[str]) -> None:
    """Hard-fail if target, outcome, or eligibility columns exist."""
    bad_cols = [
        c for c in column_names
        if any(kw in c.lower() for kw in ["target", "eligible", "repaired", "outcome"])
        and c.lower() not in ["days_since_last_repair", "no_prior_repair_flag", "repair_active_days_365d", "repair_event_count_collapsed_365d", "prior_repair_months_12m"]
    ]
    if bad_cols:
        raise ValueError(f"SECURITY VIOLATION: Target/Outcome columns detected: {bad_cols}")


def build_data_mart() -> None:
    t0 = time.time()
    print("=== BUILDING PHASE 8 DASHBOARD DATA MART ===")

    # 1. Inspect schemas
    verify_target_free_schema(pq.read_schema(SEALED_FEAT_PATH).names)
    verify_target_free_schema(pq.read_schema(B2_PRED_PATH).names)
    verify_target_free_schema(pq.read_schema(P7_RECORDS_PATH).names)

    # 2. Load & filter B2 features
    df_feat_all = pd.read_parquet(SEALED_FEAT_PATH)
    df_feat_all["date_str"] = df_feat_all["as_of_date"].astype(str).str[:10]
    df_b2_feat = df_feat_all[df_feat_all["date_str"].isin(B2_ANCHORS)].copy()
    df_b2_feat = df_b2_feat.sort_values(by=["as_of_date", "canonical_segment_id", "segment_month_id"]).reset_index(drop=True)

    assert len(df_b2_feat) == EXPECTED_TOTAL_ROWS, f"B2 feature rows {len(df_b2_feat)} != {EXPECTED_TOTAL_ROWS}"

    # 3. Load & align B2 predictions
    df_b2_pred = pd.read_parquet(B2_PRED_PATH)
    assert len(df_b2_pred) == EXPECTED_TOTAL_ROWS
    assert (df_b2_feat["segment_month_id"].values == df_b2_pred["segment_month_id"].values).all(), "Predictions alignment mismatch!"

    # Combined base data
    df_mart = df_b2_feat.copy()
    df_mart["raw_probability"] = df_b2_pred["raw_probability"].values
    df_mart["canonical_segment_id"] = df_mart["canonical_segment_id"].astype(str).str.strip()

    # Derived calendar columns
    as_of_dt = pd.to_datetime(df_mart["date_str"])
    df_mart["calendar_year"] = as_of_dt.dt.year.astype(int)
    df_mart["calendar_quarter"] = "Q" + as_of_dt.dt.quarter.astype(str)

    # Risk Percentile Rank (per anchor month population)
    df_mart["risk_percentile_rank"] = df_mart.groupby("date_str")["raw_probability"].rank(pct=True) * 100.0

    # Exclusive Map Priority Bands
    # HIGH: Top 5% (pct >= 95.0)
    # MEDIUM: >5% through Top 10% (90.0 <= pct < 95.0)
    # WATCH: >10% through Top 20% (80.0 <= pct < 90.0)
    # OTHER: outside Top 20% (pct < 80.0)
    conditions = [
        df_mart["risk_percentile_rank"] >= 95.0,
        (df_mart["risk_percentile_rank"] >= 90.0) & (df_mart["risk_percentile_rank"] < 95.0),
        (df_mart["risk_percentile_rank"] >= 80.0) & (df_mart["risk_percentile_rank"] < 90.0),
    ]
    choices = ["HIGH", "MEDIUM", "WATCH"]
    df_mart["priority_band_exclusive"] = np.select(conditions, choices, default="OTHER")

    # Cumulative Top-K Policy Memberships
    df_mart["in_top5_policy"] = df_mart["risk_percentile_rank"] >= 95.0
    df_mart["in_top10_policy"] = df_mart["risk_percentile_rank"] >= 90.0
    df_mart["in_top20_policy"] = df_mart["risk_percentile_rank"] >= 80.0

    # 4. Join Phase 7 Top-10% explanation records
    df_p7 = pd.read_parquet(P7_RECORDS_PATH)
    assert len(df_p7) == EXPECTED_P7_ROWS, f"P7 records count {len(df_p7)} != {EXPECTED_P7_ROWS}"
    verify_target_free_schema(list(df_p7.columns))

    shap_cols = [
        "segment_month_id",
        "raw_margin",
        "base_value",
        "additivity_residual",
        "top_pos_feat_1",
        "top_pos_shap_1",
        "top_pos_feat_2",
        "top_pos_shap_2",
        "top_pos_feat_3",
        "top_pos_shap_3",
        "top_neg_feat_1",
        "top_neg_shap_1",
        "top_neg_feat_2",
        "top_neg_shap_2",
        "top_neg_feat_3",
        "top_neg_shap_3",
    ]
    df_shap_sub = df_p7[shap_cols].copy()

    df_mart = df_mart.merge(df_shap_sub, on="segment_month_id", how="left")
    assert len(df_mart) == EXPECTED_TOTAL_ROWS, f"Row count changed after merge: {len(df_mart)}"

    # Explanation status message
    df_mart["has_shap_explanation"] = df_mart["raw_margin"].notna()
    df_mart["explanation_status"] = np.where(
        df_mart["has_shap_explanation"],
        "Top-10% Segment Explanation Available",
        UNEXPLAINED_MSG,
    )

    # Selected columns for data mart
    selected_cols = [
        "segment_month_id",
        "canonical_segment_id",
        "as_of_date",
        "date_str",
        "calendar_year",
        "calendar_quarter",
        "primary_borough_id",
        "functional_road_class",
        "condition_missing_flag",
        "no_prior_repair_flag",
        "future_asset_record_hidden_flag",
        "segment_length_m",
        "raw_probability",
        "risk_percentile_rank",
        "priority_band_exclusive",
        "in_top5_policy",
        "in_top10_policy",
        "in_top20_policy",
        "has_shap_explanation",
        "explanation_status",
        "raw_margin",
        "base_value",
        "additivity_residual",
        "top_pos_feat_1",
        "top_pos_shap_1",
        "top_pos_feat_2",
        "top_pos_shap_2",
        "top_pos_feat_3",
        "top_pos_shap_3",
        "top_neg_feat_1",
        "top_neg_shap_1",
        "top_neg_feat_2",
        "top_neg_shap_2",
        "top_neg_feat_3",
        "top_neg_shap_3",
    ]

    df_out = df_mart[selected_cols].copy()

    # Final Security & Reconciliation Assertions
    verify_target_free_schema(list(df_out.columns))
    assert len(df_out) == EXPECTED_TOTAL_ROWS
    assert len(df_out["segment_month_id"].unique()) == EXPECTED_TOTAL_ROWS
    assert df_out["has_shap_explanation"].sum() == EXPECTED_P7_ROWS
    assert (df_out.groupby("date_str").size() == EXPECTED_PER_ANCHOR).all()

    # Save Data Mart Parquet
    DATA_MART_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_parquet(DATA_MART_PATH, index=False)

    t_s = time.time() - t0
    print(f"[OK] Dashboard Data Mart written in {t_s:.2f}s: {DATA_MART_PATH}")
    print(f"     Total rows: {len(df_out):,}")
    print(f"     SHAP Top-10% explained rows: {df_out['has_shap_explanation'].sum():,}")
    print(f"     File size: {DATA_MART_PATH.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    build_data_mart()
