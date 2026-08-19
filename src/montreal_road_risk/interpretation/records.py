"""Operational explanation records generator for Top-10% risk-priority candidates in Phase 7.

Extracts exact SHAP tree contributions for the Top-10% policy rows (52,782 segment-month records)
without reading any target columns.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from montreal_road_risk.interpretation.reconciliation import (
    aggregate_shap_matrix_to_source_features,
)
from montreal_road_risk.interpretation.shap_engine import (
    compute_tree_contributions_batch,
    verify_target_free_schema,
)


def build_top10_explanation_records(
    b2_features_df: pd.DataFrame,
    b2_predictions_df: pd.DataFrame,
    booster: Any,
    prep: Any,
    k_pct: float = 10.0,
) -> pd.DataFrame:
    """Build detailed operational explanation records for the frozen Top-10% risk-priority candidates."""
    n_total = len(b2_predictions_df)
    n_top_k = math.ceil(n_total * k_pct / 100.0)

    # Sort predictions according to frozen tie-break policy
    pred_sorted = b2_predictions_df.sort_values(
        by=["raw_probability", "canonical_segment_id", "as_of_date", "segment_month_id"],
        ascending=[False, True, True, True],
    ).reset_index()  # preserves original row index as 'index'

    top_k_pred = pred_sorted.iloc[:n_top_k].copy()
    top_k_indices = top_k_pred["index"].values

    # Select features for top K rows
    feature_names = list(prep.feature_names_in_)
    tf_names = list(prep.get_feature_names_out())

    top_k_feats = b2_features_df.iloc[top_k_indices][feature_names].copy()
    if "functional_road_class" in top_k_feats.columns:
        top_k_feats["functional_road_class"] = top_k_feats["functional_road_class"].astype(object)

    X_trans = prep.transform(top_k_feats)

    best_iter = getattr(booster, "best_iteration", None)
    contribs = compute_tree_contributions_batch(booster, X_trans, best_iteration=best_iter)

    tf_shap = contribs[:, :-1]
    base_val = float(contribs[0, -1])

    # Aggregate transformed SHAP to source feature SHAP
    src_shap, src_names = aggregate_shap_matrix_to_source_features(
        tf_shap, tf_names, feature_names
    )

    raw_probs = top_k_pred["raw_probability"].values
    raw_margins = np.log(raw_probs / (1.0 - raw_probs))
    reconstructed_margin = np.sum(tf_shap, axis=1) + base_val
    additivity_residuals = np.abs(reconstructed_margin - raw_margins)

    # Calculate percentile rank (100 = highest risk)
    top_k_pred["risk_percentile_rank"] = np.round(
        (1.0 - (np.arange(1, n_top_k + 1) / n_total)) * 100.0, 2
    )

    records = []

    for i in range(n_top_k):
        row_src_shap = src_shap[i, :]

        # Top 3 positive contributors (increasing risk)
        pos_indices = np.argsort(-row_src_shap)[:3]
        # Top 3 negative contributors (decreasing risk)
        neg_indices = np.argsort(row_src_shap)[:3]

        rec = {
            "segment_month_id": top_k_pred.iloc[i]["segment_month_id"],
            "canonical_segment_id": top_k_pred.iloc[i]["canonical_segment_id"],
            "as_of_date": str(top_k_pred.iloc[i]["as_of_date"])[:10],
            "primary_borough_id": top_k_pred.iloc[i]["primary_borough_id"],
            "functional_road_class": top_k_pred.iloc[i]["functional_road_class"],
            "raw_probability": float(top_k_pred.iloc[i]["raw_probability"]),
            "risk_percentile_rank": float(top_k_pred.iloc[i]["risk_percentile_rank"]),
            "priority_tier": "Top_10_Pct_Risk_Priority_Candidate",
            "raw_margin": float(raw_margins[i]),
            "base_value": base_val,
            "additivity_residual": float(additivity_residuals[i]),
            # Top positive
            "top_pos_feat_1": src_names[pos_indices[0]],
            "top_pos_shap_1": float(row_src_shap[pos_indices[0]]),
            "top_pos_feat_2": src_names[pos_indices[1]] if len(pos_indices) > 1 else "",
            "top_pos_shap_2": float(row_src_shap[pos_indices[1]]) if len(pos_indices) > 1 else 0.0,
            "top_pos_feat_3": src_names[pos_indices[2]] if len(pos_indices) > 2 else "",
            "top_pos_shap_3": float(row_src_shap[pos_indices[2]]) if len(pos_indices) > 2 else 0.0,
            # Top negative
            "top_neg_feat_1": src_names[neg_indices[0]],
            "top_neg_shap_1": float(row_src_shap[neg_indices[0]]),
            "top_neg_feat_2": src_names[neg_indices[1]] if len(neg_indices) > 1 else "",
            "top_neg_shap_2": float(row_src_shap[neg_indices[1]]) if len(neg_indices) > 1 else 0.0,
            "top_neg_feat_3": src_names[neg_indices[2]] if len(neg_indices) > 2 else "",
            "top_neg_shap_3": float(row_src_shap[neg_indices[2]]) if len(neg_indices) > 2 else 0.0,
        }
        records.append(rec)

    records_df = pd.DataFrame(records)
    verify_target_free_schema(list(records_df.columns))
    return records_df
