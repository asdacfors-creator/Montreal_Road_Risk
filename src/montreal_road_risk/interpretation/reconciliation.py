"""Feature name mapping and grouped source feature reconciliation for Phase 7 interpretation.

Maps 201 transformed features back to 110 raw source features and aggregates SHAP attributions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_NOTES: dict[str, str] = {
    "prior_repair_months_12m": (
        "Corrected remediated feature. Evaluated after repairing upper-bound historical "
        "repair date filtering bug in Phase 5 remediation."
    ),
    "segment_length_m": (
        "Structural segment proxy. Highly correlated with road category and network geometry; "
        "its SHAP contribution reflects physical exposure and length-dependent opportunity."
    ),
    "days_since_last_repair": (
        "Temporal maintenance recency indicator. High values indicate extended period without "
        "recorded repair events."
    ),
    "no_prior_repair_flag": (
        "Binary indicator for segments with zero historical repairs in observation window."
    ),
    "condition_missing_flag": (
        "Binary indicator for missing pavement condition survey data."
    ),
    "future_asset_record_hidden_flag": (
        "Binary indicator for future asset construction record post-dating observation cutoff."
    ),
}


def build_feature_name_mapping(
    transformed_names: list[str],
    source_names: list[str],
) -> dict[str, str]:
    """Map each transformed feature (e.g. 'cat__functional_road_class_arterial') to its original source feature name (e.g. 'functional_road_class')."""
    mapping: dict[str, str] = {}
    source_sorted = sorted(source_names, key=len, reverse=True)

    for tf in transformed_names:
        clean = tf.split("__")[-1]
        matched = None
        for s in source_sorted:
            if clean == s or clean.startswith(s + "_") or clean.startswith(s):
                matched = s
                break
        if matched is None:
            raise ValueError(f"Could not map transformed feature '{tf}' to any source feature.")
        mapping[tf] = matched
    return mapping


def aggregate_importance_by_source_feature(
    transformed_importance_df: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    """Aggregate transformed feature importances (mean abs SHAP) to source feature level."""
    df = transformed_importance_df.copy()
    df["source_feature"] = df["transformed_feature"].map(mapping)

    grouped = df.groupby("source_feature").agg(
        mean_abs_shap=pd.NamedAgg(column="mean_abs_shap", aggfunc="sum"),
        mean_signed_shap=pd.NamedAgg(column="mean_signed_shap", aggfunc="mean"),
        max_transformed_abs_shap=pd.NamedAgg(column="mean_abs_shap", aggfunc="max"),
        num_transformed_features=pd.NamedAgg(column="transformed_feature", aggfunc="count"),
    ).reset_index()

    grouped = grouped.sort_values(by="mean_abs_shap", ascending=False).reset_index(drop=True)
    grouped["importance_rank"] = np.arange(1, len(grouped) + 1)

    # Attach feature notes if present
    grouped["feature_note"] = grouped["source_feature"].map(lambda f: FEATURE_NOTES.get(f, ""))
    return grouped


def aggregate_shap_matrix_to_source_features(
    shap_matrix: np.ndarray,
    transformed_names: list[str],
    source_names: list[str],
) -> tuple[np.ndarray, list[str]]:
    """Aggregate an N x P transformed SHAP matrix to an N x S source feature SHAP matrix by summing one-hot/transformed columns for each source feature."""
    mapping = build_feature_name_mapping(transformed_names, source_names)
    unique_sources = sorted(set(mapping.values()))
    n_rows = shap_matrix.shape[0]
    n_sources = len(unique_sources)

    source_shap = np.zeros((n_rows, n_sources), dtype=np.float32)

    for i, s in enumerate(unique_sources):
        tf_indices = [idx for idx, tf in enumerate(transformed_names) if mapping[tf] == s]
        source_shap[:, i] = np.sum(shap_matrix[:, tf_indices], axis=1).astype(np.float32)

    return source_shap, unique_sources
