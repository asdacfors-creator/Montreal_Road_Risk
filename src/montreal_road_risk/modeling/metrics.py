"""
src/montreal_road_risk/modeling/metrics.py

Validation metric computation for Phase 5.

Rules
-----
* Primary metric: sklearn.metrics.average_precision_score → "Average Precision (AP)"
* AP is NOT the same as trapezoidal PR-AUC; only AP is used.
* Precision/Recall/Lift@K uses ceiling for K-row count.
* Tie-breaking: descending probability, then ascending canonical_segment_id,
  then ascending as_of_date. Identifiers used only for evaluation ordering.
* Phase 5 computes validation metrics only.
* No calibration, no ECE, no test metrics.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)

log = logging.getLogger(__name__)

# Primary metric label — used consistently throughout all reports
PRIMARY_METRIC_LABEL = "Average Precision (AP)"


def compute_ap(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Average Precision (AP) — primary metric."""
    return float(average_precision_score(y_true, y_score))


def compute_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    return float(roc_auc_score(y_true, y_score))


def compute_brier(y_true: np.ndarray, y_score: np.ndarray) -> float:
    return float(brier_score_loss(y_true, y_score))


def compute_at_k(
    y_true: np.ndarray,
    y_score: np.ndarray,
    k_pct: float,
    segment_ids: Optional[np.ndarray] = None,
    as_of_dates: Optional[np.ndarray] = None,
) -> dict:
    """
    Compute Precision, Recall, and Lift at K% of the scored set.

    Tie-breaking order:
      1. Descending probability (primary)
      2. Ascending canonical_segment_id (secondary — for evaluation only)
      3. Ascending as_of_date (tertiary — for evaluation only)

    K-row count = ceil(k_pct / 100 * n)
    """
    n = len(y_true)
    k_rows = math.ceil(k_pct / 100.0 * n)

    # Build sort dataframe
    sort_df = pd.DataFrame({
        "y_true":   y_true,
        "y_score":  y_score,
        "seg_id":   segment_ids if segment_ids is not None else np.arange(n),
        "aod":      as_of_dates if as_of_dates is not None else np.zeros(n),
    })
    sort_df = sort_df.sort_values(
        ["y_score", "seg_id", "aod"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    top_k = sort_df.iloc[:k_rows]
    prevalence = float(y_true.mean()) if y_true.mean() > 0 else 1e-9

    precision_k = float(top_k["y_true"].mean())
    recall_k    = float(top_k["y_true"].sum() / max(y_true.sum(), 1))
    lift_k      = precision_k / prevalence

    return {
        f"precision_at_{k_pct}pct": precision_k,
        f"recall_at_{k_pct}pct":    recall_k,
        f"lift_at_{k_pct}pct":      lift_k,
        f"k_rows_{k_pct}pct":       k_rows,
        f"k_threshold_{k_pct}pct":  float(sort_df.iloc[k_rows - 1]["y_score"]),
    }


def compute_validation_metrics(
    y_true: np.ndarray,
    y_score: np.ndarray,
    k_pcts: list[float] = (5, 10, 20),
    segment_ids: Optional[np.ndarray] = None,
    as_of_dates: Optional[np.ndarray] = None,
    model_name: str = "model",
) -> dict:
    """
    Full validation metric suite. Returns dict suitable for JSON serialization.
    """
    ap      = compute_ap(y_true, y_score)
    roc_auc = compute_roc_auc(y_true, y_score)
    brier   = compute_brier(y_true, y_score)
    n_pos   = int(y_true.sum())
    n_total = int(len(y_true))

    result = {
        "model":                    model_name,
        PRIMARY_METRIC_LABEL:       ap,
        "ROC-AUC":                  roc_auc,
        "Brier":                    brier,
        "n_total":                  n_total,
        "n_positive":               n_pos,
        "prevalence":               n_pos / n_total if n_total > 0 else 0.0,
    }

    for k in k_pcts:
        at_k = compute_at_k(y_true, y_score, k, segment_ids, as_of_dates)
        result.update(at_k)

    log.info(
        "%s validation — AP=%.4f ROC-AUC=%.4f Brier=%.4f  (n=%d, pos=%d)",
        model_name, ap, roc_auc, brier, n_total, n_pos,
    )
    return result
