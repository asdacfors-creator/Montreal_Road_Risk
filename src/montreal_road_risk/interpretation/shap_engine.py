"""Target-free SHAP engine and streaming accumulator for Phase 7 model interpretation.

Computes exact XGBoost tree contributions on the raw-margin scale (pred_contribs=True)
without reading any target columns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import psutil
import xgboost as xgb

MANDATORY_CAUSALITY_STATEMENT = (
    "SHAP values describe model behavior and association. "
    "They do not establish causal effects or prove that changing a feature will change repair risk."
)


def verify_target_free_schema(columns: list[str] | set[str]) -> None:
    """Raise ValueError if any column contains 'target' or 'eligible' (case-insensitive)."""
    for col in columns:
        col_lower = col.lower()
        if "target" in col_lower or "eligible" in col_lower:
            raise ValueError(f"Forbidden target or eligibility column found in schema: {col}")


def verify_anchor_allowlist(anchors: list[str] | set[str], allowed_anchors: list[str] | set[str]) -> None:
    """Raise ValueError if any anchor is not in allowed_anchors."""
    allowed_set = set(allowed_anchors)
    for a in anchors:
        if a not in allowed_set:
            raise ValueError(f"Unauthorized anchor date found: {a}. Allowed: {allowed_anchors}")


def check_memory_limit(max_memory_percent: float = 85.0) -> float:
    """Measure system RAM usage and raise MemoryError if it exceeds max_memory_percent."""
    mem_pct = psutil.virtual_memory().percent
    if mem_pct > max_memory_percent:
        raise MemoryError(
            f"System memory limit exceeded: {mem_pct:.1f}% > {max_memory_percent:.1f}% hard-stop threshold."
        )
    return mem_pct


def compute_tree_contributions_batch(
    booster: xgb.Booster,
    X_transformed: np.ndarray | pd.DataFrame,
    feature_names: list[str] | None = None,
    best_iteration: int | None = None,
) -> np.ndarray:
    """Compute exact tree contributions on raw-margin scale for a batch of transformed features.

    Returns array of shape (n_rows, n_transformed_features + 1)
    where the last column is the base value (bias).
    """
    if isinstance(X_transformed, pd.DataFrame):
        dm = xgb.DMatrix(X_transformed)
    else:
        dm = xgb.DMatrix(X_transformed, feature_names=feature_names or getattr(booster, "feature_names", None))

    iter_range = (0, best_iteration + 1) if best_iteration is not None else (0, 0)
    contribs = booster.predict(dm, pred_contribs=True, iteration_range=iter_range)
    return contribs


def verify_additivity(
    contribs: np.ndarray,
    raw_margins: np.ndarray,
    tolerance: float = 1e-4,
) -> float:
    """Assert base_value + sum(feature_contributions) == raw_margin within numerical tolerance.

    Returns the maximum absolute residual.
    """
    feature_contribs = contribs[:, :-1]
    base_values = contribs[:, -1]
    reconstructed_margin = np.sum(feature_contribs, axis=1) + base_values
    diffs = np.abs(reconstructed_margin - raw_margins)
    max_diff = float(np.max(diffs))
    if max_diff > tolerance:
        raise ValueError(
            f"SHAP additivity assertion failed: max absolute difference {max_diff:.6e} > tolerance {tolerance:.6e}"
        )
    return max_diff


class StreamingSHAPAccumulator:
    """Streams batch SHAP contribution matrices to compute global importance statistics without storing the full N x P matrix in memory."""

    def __init__(self, n_features: int) -> None:
        self.n_features = n_features
        self.n_total_rows = 0
        self.sum_abs_shap = np.zeros(n_features, dtype=np.float64)
        self.sum_signed_shap = np.zeros(n_features, dtype=np.float64)
        self.pos_count = np.zeros(n_features, dtype=np.int64)
        self.neg_count = np.zeros(n_features, dtype=np.int64)
        self.base_value: float | None = None

    def update(self, contribs: np.ndarray) -> None:
        """Update streaming sums with a batch of tree contributions."""
        n_rows = contribs.shape[0]
        feature_shap = contribs[:, :-1].astype(np.float64)
        bv = float(contribs[0, -1])
        if self.base_value is None:
            self.base_value = bv

        self.n_total_rows += n_rows
        self.sum_abs_shap += np.sum(np.abs(feature_shap), axis=0)
        self.sum_signed_shap += np.sum(feature_shap, axis=0)
        self.pos_count += np.sum(feature_shap > 0, axis=0)
        self.neg_count += np.sum(feature_shap < 0, axis=0)

    def finalize(self, feature_names: list[str]) -> pd.DataFrame:
        """Finalize and return global transformed feature importance DataFrame."""
        if self.n_total_rows == 0:
            raise ValueError("No rows accumulated.")

        mean_abs = self.sum_abs_shap / self.n_total_rows
        mean_signed = self.sum_signed_shap / self.n_total_rows
        pos_freq = self.pos_count / self.n_total_rows
        neg_freq = self.neg_count / self.n_total_rows

        df = pd.DataFrame({
            "transformed_feature": feature_names,
            "mean_abs_shap": mean_abs,
            "mean_signed_shap": mean_signed,
            "positive_frequency": pos_freq,
            "negative_frequency": neg_freq,
        })
        df = df.sort_values(by="mean_abs_shap", ascending=False).reset_index(drop=True)
        df["importance_rank"] = np.arange(1, len(df) + 1)
        return df
