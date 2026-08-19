"""Target-free subgroup interpretation for Phase 7 model attribution.

Summarizes predicted risk distributions and top driving SHAP features by borough, road class,
asset flags, and temporal quarters.
Does NOT compute AP, AUC, Brier, or any outcome/performance metrics.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def summarize_target_free_subgroups(
    b2_features_df: pd.DataFrame,
    b2_predictions_df: pd.DataFrame,
    source_shap_matrix: np.ndarray,
    source_feature_names: list[str],
) -> dict[str, Any]:
    """Compute target-free subgroup interpretation summaries.

    Groups by metadata and feature columns and summarizes predicted risk and top SHAP drivers.
    """
    df = b2_features_df.copy()
    df["raw_probability"] = b2_predictions_df["raw_probability"].values
    df["date_dt"] = pd.to_datetime(df["as_of_date"].astype(str).str[:10])
    df["calendar_quarter"] = "Q" + df["date_dt"].dt.quarter.astype(str)
    df["calendar_year"] = df["date_dt"].dt.year.astype(str)

    subgroup_dims = [
        "primary_borough_id",
        "functional_road_class",
        "condition_missing_flag",
        "future_asset_record_hidden_flag",
        "no_prior_repair_flag",
        "calendar_quarter",
        "calendar_year",
    ]

    subgroup_summaries: dict[str, Any] = {}

    for dim in subgroup_dims:
        if dim not in df.columns:
            continue

        dim_results = {}
        grouped = df.groupby(dim, observed=False)

        for g_val, sub_df in grouped:
            g_key = str(g_val)
            indices = sub_df.index.values
            sub_n = len(sub_df)
            if sub_n == 0:
                continue

            sub_probs = sub_df["raw_probability"].values
            sub_shap = source_shap_matrix[indices, :]

            # Mean abs SHAP in this subgroup
            sub_mean_abs = np.mean(np.abs(sub_shap), axis=0)
            sub_mean_signed = np.mean(sub_shap, axis=0)

            # Top 3 driving source features
            top3_idx = np.argsort(-sub_mean_abs)[:3]
            top3_drivers = []
            for idx in top3_idx:
                top3_drivers.append({
                    "feature": source_feature_names[idx],
                    "mean_abs_shap": float(sub_mean_abs[idx]),
                    "mean_signed_shap": float(sub_mean_signed[idx]),
                })

            dim_results[g_key] = {
                "n_rows": sub_n,
                "pct_of_total": float(sub_n / len(df)),
                "raw_probability_stats": {
                    "mean": float(np.mean(sub_probs)),
                    "median": float(np.median(sub_probs)),
                    "std": float(np.std(sub_probs)),
                    "p75": float(np.percentile(sub_probs, 75)),
                    "p90": float(np.percentile(sub_probs, 90)),
                },
                "top_3_driving_features": top3_drivers,
            }

        subgroup_summaries[dim] = dim_results

    return subgroup_summaries
