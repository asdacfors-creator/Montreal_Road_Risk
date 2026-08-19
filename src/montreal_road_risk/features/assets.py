import os

import numpy as np
import pandas as pd


def build_asset_features(config, project_root, panel_df):  # noqa: C901
    """
    Performs dynamic joining of road asset construction and resurfacing age features,
    ensuring intervals that cross or lie after as_of_date are hidden.
    Uses vectorized numpy operations.
    """
    assets_path = os.path.join(project_root, config["inputs"]["road_assets"])
    crosswalk_path = os.path.join(project_root, config["inputs"]["road_assets_links"])

    print(f"Loading road assets from: {assets_path}")
    assets_df = pd.read_parquet(assets_path)

    print(f"Loading road asset segment crosswalk from: {crosswalk_path}")
    cross_df = pd.read_parquet(crosswalk_path)

    # 1. Map segments to assets using accepted links
    accepted_cross = cross_df[cross_df["linkage_status"] == "accepted"].copy()
    accepted_cross["canonical_segment_id"] = accepted_cross["canonical_segment_id"].astype(str)

    assets_df["asset_id_raw"] = assets_df["asset_id_raw"].astype(str)
    accepted_cross["primary_asset_id"] = accepted_cross["primary_asset_id"].astype(str)

    # Static join
    merged_assets = accepted_cross.merge(
        assets_df,
        left_on="primary_asset_id",
        right_on="asset_id_raw",
        how="inner"
    )

    # Select necessary columns
    assets_sub = merged_assets[[
        "canonical_segment_id",
        "construction_date_lower_bound",
        "construction_date_upper_bound",
        "resurfacing_date_lower_bound",
        "resurfacing_date_upper_bound",
        "resurfacing_before_construction_candidate_flag",
        "date_contradiction_status"
    ]].copy()

    # Parse to datetime
    date_cols = [
        "construction_date_lower_bound",
        "construction_date_upper_bound",
        "resurfacing_date_lower_bound",
        "resurfacing_date_upper_bound"
    ]
    for col in date_cols:
        assets_sub[col] = pd.to_datetime(assets_sub[col], errors="coerce")

    print("Performing vectorized join and age computations for road assets...")
    # Join statically into panel_df
    panel_merged = panel_df.merge(assets_sub, on="canonical_segment_id", how="left")

    # Vectors
    t = pd.to_datetime(panel_merged["as_of_date"])
    c_lower = panel_merged["construction_date_lower_bound"]
    c_upper = panel_merged["construction_date_upper_bound"]
    r_lower = panel_merged["resurfacing_date_lower_bound"]
    r_upper = panel_merged["resurfacing_date_upper_bound"]

    # Construction age logicals
    has_const = c_lower.notna() & c_upper.notna()
    const_future = has_const & (c_lower > t)
    const_cross = has_const & (c_lower <= t) & (t < c_upper)
    const_active = has_const & (c_upper <= t)

    # Resurfacing age logicals
    has_res = r_lower.notna() & r_upper.notna()
    res_cross = has_res & (r_lower <= t) & (t < r_upper)
    res_active = has_res & (r_upper <= t)

    # Age arithmetic
    panel_merged["years_since_construction_lower"] = np.where(const_active, (t - c_upper).dt.days / 365.25, np.nan)
    panel_merged["years_since_construction_upper"] = np.where(const_active, (t - c_lower).dt.days / 365.25, np.nan)
    panel_merged["years_since_resurfacing_lower"] = np.where(res_active, (t - r_upper).dt.days / 365.25, np.nan)
    panel_merged["years_since_resurfacing_upper"] = np.where(res_active, (t - r_lower).dt.days / 365.25, np.nan)

    # Flags
    panel_merged["future_asset_record_hidden_flag"] = np.where(const_future, 1, 0)
    panel_merged["age_interval_crosses_as_of_flag"] = np.where(const_cross, 1, 0)
    panel_merged["resurfacing_interval_crosses_as_of_flag"] = np.where(res_cross, 1, 0)

    # Eligibility status
    conditions = [
        const_active,
        const_cross,
        const_future
    ]
    choices = ["active", "crosses", "future"]
    panel_merged["asset_temporal_eligibility_status"] = np.select(conditions, choices, default="missing")

    # Set default values for missing columns
    panel_merged["resurfacing_before_construction_candidate_flag"] = panel_merged["resurfacing_before_construction_candidate_flag"].fillna(0).astype(int)
    panel_merged["date_contradiction_status"] = panel_merged["date_contradiction_status"].fillna("no_contradiction").astype(str)

    # Drop temp columns
    panel_merged = panel_merged.drop(columns=date_cols)

    # Set index to segment_month_id
    panel_merged = panel_merged.set_index("segment_month_id", drop=False)

    print(f"Computed road asset features for {len(panel_merged)} panel rows.")
    return panel_merged
