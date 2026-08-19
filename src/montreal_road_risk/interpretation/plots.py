"""Visualization routines for Phase 7 target-free model interpretation.

Generates PNG plots for global feature importance, beeswarm summary, and feature dependence.
Embeds the mandatory causality disclaimer statement on every figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from montreal_road_risk.interpretation.shap_engine import (
    MANDATORY_CAUSALITY_STATEMENT,
)


def plot_global_importance_bar(
    grouped_importance_df: pd.DataFrame,
    out_path: str | Path,
    top_n: int = 20,
) -> None:
    """Plot horizontal bar chart of top N grouped source feature importances."""
    df_top = grouped_importance_df.head(top_n).sort_values(by="mean_abs_shap", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    ax.barh(df_top["source_feature"], df_top["mean_abs_shap"], color="#1f77b4")

    ax.set_xlabel("Mean Absolute SHAP Value (Raw Margin Contribution)")
    ax.set_title(f"Top {top_n} Source Feature Importance (Phase 7 Gate 7A)", fontsize=12, pad=15)
    ax.grid(axis="x", linestyle="--", alpha=0.7)

    # Embed mandatory causality statement as caption
    fig.text(
        0.5,
        0.01,
        MANDATORY_CAUSALITY_STATEMENT,
        ha="center",
        va="bottom",
        fontsize=8,
        style="italic",
        wrap=True,
        color="#333333",
    )

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_p, dpi=150)
    plt.close(fig)


def plot_beeswarm_summary(
    shap_matrix: np.ndarray,
    X_sample: np.ndarray | pd.DataFrame,
    feature_names: list[str],
    out_path: str | Path,
    top_n: int = 20,
) -> None:
    """Generate SHAP beeswarm summary plot for a sample of rows."""
    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)

    if isinstance(X_sample, pd.DataFrame):
        X_data = X_sample.values
    else:
        X_data = X_sample

    if X_data.shape[1] != shap_matrix.shape[1]:
        # If matrix dimensions don't match (e.g. raw 110 features vs 201 transformed), pad/slice or raise informative error
        raise ValueError(
            f"Shape mismatch: X_data has {X_data.shape[1]} columns but shap_matrix has {shap_matrix.shape[1]} columns."
        )

    # Wrap in Explanation object
    explanation = shap.Explanation(
        values=shap_matrix,
        data=X_data,
        feature_names=feature_names,
    )

    shap.plots.beeswarm(explanation, max_display=top_n, show=False)

    plt.title(f"SHAP Beeswarm Summary Plot (Top {top_n} Features)", fontsize=12, pad=15)

    # Embed mandatory causality statement
    plt.figtext(
        0.5,
        0.01,
        MANDATORY_CAUSALITY_STATEMENT,
        ha="center",
        va="bottom",
        fontsize=8,
        style="italic",
        wrap=True,
        color="#333333",
    )

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_p, dpi=150)
    plt.close("all")


def plot_dependence(
    shap_matrix: np.ndarray,
    X_sample: np.ndarray | pd.DataFrame,
    feature_names: list[str],
    feature_name: str,
    out_path: str | Path,
) -> None:
    """Generate SHAP scatter/dependence plot for a specific feature."""
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)

    if isinstance(X_sample, pd.DataFrame):
        X_data = X_sample.values
    else:
        X_data = X_sample

    feat_idx = feature_names.index(feature_name)
    explanation = shap.Explanation(
        values=shap_matrix,
        data=X_data,
        feature_names=feature_names,
    )

    shap.plots.scatter(explanation[:, feat_idx], show=False)

    plt.title(f"SHAP Dependence Plot: {feature_name}", fontsize=12, pad=15)

    plt.figtext(
        0.5,
        0.01,
        MANDATORY_CAUSALITY_STATEMENT,
        ha="center",
        va="bottom",
        fontsize=8,
        style="italic",
        wrap=True,
        color="#333333",
    )

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_p, dpi=150)
    plt.close("all")
