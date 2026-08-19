"""Phase 8 Dashboard Unit Tests (Synthetic Fixtures).

Tests security assertions, target-column rejection, prohibited path rejection,
fingerprint validation, geometry join arithmetic, mutually exclusive map bands,
cumulative policy booleans, CSV formula sanitization, and Phase 6/7 immutability.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

from montreal_road_risk.dashboard.data_loader import (
    load_dashboard_data_mart,
    load_phase6_aggregate_results,
    load_phase7_interpretation_artifacts,
    load_simplified_geometry,
)
from montreal_road_risk.dashboard.filters import apply_dashboard_filters
from montreal_road_risk.dashboard.security import (
    SecurityViolationError,
    sanitize_csv_dataframe,
    sanitize_popup_html,
    verify_input_path,
    verify_locked_fingerprints,
    verify_target_free_dataframe,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_target_column_rejection():
    """Verify that any target, outcome, or eligibility column causes a SecurityViolationError."""
    bad_df_1 = pd.DataFrame({"segment_month_id": [1, 2], "target_repair_90d": [0, 1]})
    with pytest.raises(SecurityViolationError, match="Target/Outcome column detected"):
        verify_target_free_dataframe(bad_df_1, "Synthetic Test 1")

    bad_df_2 = pd.DataFrame({"segment_month_id": [1, 2], "eligible_for_target": [1, 1]})
    with pytest.raises(SecurityViolationError, match="Target/Outcome column detected"):
        verify_target_free_dataframe(bad_df_2, "Synthetic Test 2")


def test_prohibited_path_rejection():
    """Verify that attempting to access prohibited target-bearing paths raises a SecurityViolationError."""
    with pytest.raises(SecurityViolationError, match="Prohibited target-bearing input path referenced"):
        verify_input_path("data/processed/phase_4/phase_4_panel.parquet")

    with pytest.raises(SecurityViolationError, match="Prohibited target-bearing input path referenced"):
        verify_input_path("data/raw/embargo_targets.parquet")


def test_locked_fingerprints_verification():
    """Verify locked Phase 6 and Phase 7 artifact fingerprints pass validation."""
    verify_locked_fingerprints()


def test_data_mart_schema_and_reconciliation():
    """Verify target-free data mart row count, anchors, and zero-target assertions."""
    df_mart = load_dashboard_data_mart()
    verify_target_free_dataframe(df_mart, "Data Mart Verification Test")

    assert len(df_mart) == 527813, f"Expected 527,813 rows, got {len(df_mart)}"
    assert df_mart["segment_month_id"].nunique() == 527813
    assert df_mart["date_str"].nunique() == 11
    assert (df_mart.groupby("date_str").size() == 47983).all()

    # Verify SHAP Top-10% explained count
    assert df_mart["has_shap_explanation"].sum() == 52782


def test_geometry_join_reconciliation():
    """Verify geometry GeoJSON 100% 1-to-1 match against canonical segments."""
    df_mart = load_dashboard_data_mart()
    gdf_geo = load_simplified_geometry()
    verify_target_free_dataframe(gdf_geo, "Geometry Verification Test")

    assert len(gdf_geo) == 47983
    assert gdf_geo["canonical_segment_id"].nunique() == 47983
    assert gdf_geo.geometry.is_empty.sum() == 0
    assert (~gdf_geo.geometry.is_valid).sum() == 0

    mart_ids = set(df_mart["canonical_segment_id"].unique())
    geo_ids = set(gdf_geo["canonical_segment_id"].unique())

    assert mart_ids == geo_ids, "Geometry ID mismatch between data mart and GeoJSON!"


def test_priority_bands_and_policies():
    """Verify mutually exclusive map priority bands and cumulative policy memberships."""
    df_mart = load_dashboard_data_mart()

    # Mutually exclusive bands
    bands = df_mart["priority_band_exclusive"].value_counts()
    assert set(bands.index) == {"HIGH", "MEDIUM", "WATCH", "OTHER"}

    # Exclusive vs Cumulative checks
    high_rows = df_mart[df_mart["priority_band_exclusive"] == "HIGH"]
    assert (high_rows["in_top5_policy"] & high_rows["in_top10_policy"] & high_rows["in_top20_policy"]).all()

    med_rows = df_mart[df_mart["priority_band_exclusive"] == "MEDIUM"]
    assert (~med_rows["in_top5_policy"] & med_rows["in_top10_policy"] & med_rows["in_top20_policy"]).all()

    watch_rows = df_mart[df_mart["priority_band_exclusive"] == "WATCH"]
    assert (~watch_rows["in_top5_policy"] & ~watch_rows["in_top10_policy"] & watch_rows["in_top20_policy"]).all()


def test_unexplained_rows_default_message():
    """Verify rows outside Top-10% receive default explanation status message."""
    df_mart = load_dashboard_data_mart()

    unexplained = df_mart[~df_mart["has_shap_explanation"]]
    assert len(unexplained) == 527813 - 52782
    expected_msg = "Detailed segment explanation was not generated under the frozen Phase 7 scope."
    assert (unexplained["explanation_status"] == expected_msg).all()
    assert unexplained["top_pos_feat_1"].isna().all()


def test_filter_correctness():
    """Verify sidebar filtering logic."""
    df_mart = load_dashboard_data_mart()

    # Filter by specific borough and anchor month
    filtered = apply_dashboard_filters(
        df=df_mart,
        anchor_month="2025-05-31",
        exclusive_bands=["HIGH"],
    )

    assert len(filtered) > 0
    assert (filtered["date_str"] == "2025-05-31").all()
    assert (filtered["priority_band_exclusive"] == "HIGH").all()


def test_csv_formula_sanitization():
    """Verify formula injection characters (=, +, -, @) are escaped in exported CSV data."""
    df_dirty = pd.DataFrame({
        "segment_id": ["=SUM(1,2)", "+123", "-COMMAND", "@EVIL", "NORMAL"],
        "probability": [0.9, 0.8, 0.7, 0.6, 0.5],
    })
    df_clean = sanitize_csv_dataframe(df_dirty)

    assert df_clean["segment_id"].iloc[0] == "'=SUM(1,2)"
    assert df_clean["segment_id"].iloc[1] == "'+123"
    assert df_clean["segment_id"].iloc[2] == "'-COMMAND"
    assert df_clean["segment_id"].iloc[3] == "'@EVIL"
    assert df_clean["segment_id"].iloc[4] == "NORMAL"


def test_popup_html_escaping():
    """Verify HTML special characters are escaped for popups."""
    bad_text = "<script>alert('xss')</script>"
    escaped = sanitize_popup_html(bad_text)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


def test_aggregate_results_loading():
    """Verify aggregate Phase 6 and Phase 7 results load properly without row targets."""
    p6_res = load_phase6_aggregate_results()
    assert "eval_results" in p6_res
    assert p6_res["eval_results"]["primary_raw_metrics"]["average_precision"] == pytest.approx(0.505693, abs=1e-5)

    p7_res = load_phase7_interpretation_artifacts()
    assert "manifest" in p7_res
    assert "global_importance" in p7_res


def test_integer_flag_filtering_bugfix():
    """Verify int64 binary flag filtering (condition_missing_flag, no_prior_repair_flag) does not crash."""
    df_test = pd.DataFrame({
        "segment_month_id": ["1", "2", "3"],
        "date_str": ["2025-05-31", "2025-05-31", "2025-05-31"],
        "primary_borough_id": ["B1", "B1", "B1"],
        "functional_road_class": ["Arterial", "Arterial", "Arterial"],
        "priority_band_exclusive": ["HIGH", "MEDIUM", "WATCH"],
        "in_top5_policy": [True, False, False],
        "in_top10_policy": [True, True, False],
        "in_top20_policy": [True, True, True],
        "risk_percentile_rank": [99.0, 92.0, 85.0],
        "condition_missing_flag": [0, 1, 0],
        "no_prior_repair_flag": [1, 0, 1],
    })

    res_avail = apply_dashboard_filters(df_test, condition_missing_status="Survey Available")
    assert len(res_avail) == 2
    assert (res_avail["condition_missing_flag"] == 0).all()

    res_missing = apply_dashboard_filters(df_test, condition_missing_status="Survey Missing")
    assert len(res_missing) == 1
    assert (res_missing["condition_missing_flag"] == 1).all()

    res_repair = apply_dashboard_filters(df_test, prior_repair_status="No Prior Repair")
    assert len(res_repair) == 2
    assert (res_repair["no_prior_repair_flag"] == 1).all()

