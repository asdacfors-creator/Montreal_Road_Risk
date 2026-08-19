"""Filter logic module for Phase 8 Dashboard.

Filters target-free data mart based on user sidebar controls.
"""

from __future__ import annotations

import pandas as pd


def apply_dashboard_filters(
    df: pd.DataFrame,
    anchor_month: str | None = None,
    boroughs: list[str] | None = None,
    road_classes: list[str] | None = None,
    exclusive_bands: list[str] | None = None,
    cumulative_policy: str | None = None,
    percentile_range: tuple[float, float] = (0.0, 100.0),
    condition_missing_status: str = "All",
    prior_repair_status: str = "All",
) -> pd.DataFrame:
    """Apply interactive sidebar filters to target-free DataFrame."""
    filtered = df.copy()

    if anchor_month and anchor_month != "All":
        filtered = filtered[filtered["date_str"] == anchor_month]

    if boroughs and "All" not in boroughs:
        filtered = filtered[filtered["primary_borough_id"].isin(boroughs)]

    if road_classes and "All" not in road_classes:
        filtered = filtered[filtered["functional_road_class"].isin(road_classes)]

    if exclusive_bands and "All" not in exclusive_bands:
        filtered = filtered[filtered["priority_band_exclusive"].isin(exclusive_bands)]

    policy_map = {
        "Top 5% Policy (Cumulative)": "in_top5_policy",
        "Top 10% Policy (Cumulative)": "in_top10_policy",
        "Top 20% Policy (Cumulative)": "in_top20_policy",
    }
    if cumulative_policy in policy_map:
        filtered = filtered[filtered[policy_map[cumulative_policy]]]

    p_min, p_max = percentile_range
    filtered = filtered[
        (filtered["risk_percentile_rank"] >= p_min) & (filtered["risk_percentile_rank"] <= p_max)
    ]

    if condition_missing_status == "Survey Available":
        filtered = filtered[filtered["condition_missing_flag"] == 0]
    elif condition_missing_status == "Survey Missing":
        filtered = filtered[filtered["condition_missing_flag"] == 1]

    if prior_repair_status == "No Prior Repair":
        filtered = filtered[filtered["no_prior_repair_flag"] == 1]

    return filtered
