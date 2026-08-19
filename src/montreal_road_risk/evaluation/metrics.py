"""Phase 6 evaluation metrics.

All definitions frozen per ``config/phase_6_evaluation.json``.

Average Precision (AP)
    sklearn.metrics.average_precision_score — the weighted mean of
    precision values achieved at successive recall thresholds, where
    the recall increase at each threshold supplies the weight.
    This is NOT trapezoidal interpolation of the PR curve.

Calibration slope/intercept
    Fitted via logistic regression on logit-transformed probabilities:
        logit(P(Y=1)) = intercept + slope × logit(p_clipped)
    where p_clipped = clip(p, ε, 1−ε), ε = 1e-7.
    Ideal values: intercept = 0, slope = 1.
    Do NOT use scipy.stats.linregress for binary-outcome calibration.

ECE
    Ten frozen equal-width bins [0, 0.1) … [0.9, 1.0].
    Empty bins have weight = zero and contribute zero to ECE.
    Empty bins appear as NaN in the reliability table.
    ECE is always finite, even when bins are empty.

Top-K row count
    ceil(N × K / 100)  — NOT floor.
    Tie-breaking: descending score → canonical_segment_id → as_of_date → segment_month_id.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

# ---------------------------------------------------------------------------
# Primary ranking metrics
# ---------------------------------------------------------------------------

def average_precision(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Weighted mean of precision at successive recall thresholds.

    Delegates to ``sklearn.metrics.average_precision_score``.
    This is NOT trapezoidal PR-AUC.
    """
    return float(average_precision_score(y_true, y_score))


def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Area under the ROC curve."""
    return float(roc_auc_score(y_true, y_score))


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Mean squared error of calibrated probabilities."""
    return float(brier_score_loss(y_true, y_prob))


def log_loss_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Cross-entropy loss."""
    return float(log_loss(y_true, y_prob))


# ---------------------------------------------------------------------------
# Calibration diagnostics
# ---------------------------------------------------------------------------

def calibration_slope_intercept(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    epsilon: float = 1e-7,
    C: float = 1e9,
    max_iter: int = 1000,
) -> dict[str, Any]:
    """Fit calibration slope and intercept via logistic regression on logit-space.

    Model:  logit(P(Y=1)) = intercept + slope × logit(p_clipped)

    Parameters
    ----------
    y_true : array-like of {0, 1}
    y_prob : array-like of float in (0, 1)
    epsilon : float
        Clipping value to prevent log(0).  Frozen in config (1e-7).
    C : float
        Inverse regularization (high = near-unpenalized).
    max_iter : int
        Convergence cap for LogisticRegression.

    Returns
    -------
    dict with keys:
        slope, intercept, converged, calibration_in_the_large, epsilon
    """
    from sklearn.linear_model import LogisticRegression

    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)

    p_clipped = np.clip(p, epsilon, 1.0 - epsilon)
    logit_p = np.log(p_clipped / (1.0 - p_clipped))

    X = logit_p.reshape(-1, 1)

    lr = LogisticRegression(C=C, solver="lbfgs", max_iter=max_iter)
    try:
        lr.fit(X, y)
        converged = True
        slope = float(lr.coef_[0][0])
        intercept = float(lr.intercept_[0])
    except Exception:
        converged = False
        slope = float("nan")
        intercept = float("nan")

    citl = float(np.mean(y) - np.mean(p))  # calibration-in-the-large (separate diagnostic)

    return {
        "slope": slope,
        "intercept": intercept,
        "converged": converged,
        "status": "ok" if converged else "CONVERGENCE_FAILURE",
        "calibration_in_the_large": citl,
        "epsilon": epsilon,
        "ideal_slope": 1.0,
        "ideal_intercept": 0.0,
        "note": (
            "Ideal intercept=0, slope=1. "
            "calibration_in_the_large reported separately; "
            "do not confuse with intercept from slope/intercept model."
        ),
    }


# ---------------------------------------------------------------------------
# ECE and reliability table
# ---------------------------------------------------------------------------

_ECE_EDGES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    bin_edges: list[float] | None = None,
) -> float:
    """Expected Calibration Error with frozen equal-width bins.

    Empty bins have weight=0 and contribute zero to ECE.
    ECE is always finite (even if all bins are empty, which cannot
    happen in practice for non-trivial data).

    Parameters
    ----------
    y_true : array-like of {0, 1}
    y_prob : array-like of float
    bin_edges : list of float (M+1 values for M bins).
        Defaults to the 10-bin frozen config edges.

    Returns
    -------
    float  (finite, ≥ 0)
    """
    if bin_edges is None:
        bin_edges = _ECE_EDGES

    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    N = len(y)
    if N == 0:
        return float("nan")

    edges = np.asarray(bin_edges)
    n_bins = len(edges) - 1
    ece_total = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i < n_bins - 1:
            mask = (p >= lo) & (p < hi)
        else:
            mask = (p >= lo) & (p <= hi)
        n_bin = int(mask.sum())
        if n_bin == 0:
            continue  # weight = 0, contributes zero
        mean_pred = float(p[mask].mean())
        mean_actual = float(y[mask].mean())
        ece_total += (n_bin / N) * abs(mean_pred - mean_actual)

    return float(ece_total)


def reliability_table(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    bin_edges: list[float] | None = None,
) -> pd.DataFrame:
    """Reliability table for calibration diagnostics.

    Empty bins appear as NaN in mean_predicted and mean_actual.

    Returns
    -------
    pd.DataFrame with columns:
        bin_lo, bin_hi, n_total, n_positive, mean_predicted, mean_actual, weight
    """
    if bin_edges is None:
        bin_edges = _ECE_EDGES

    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    N = len(y)
    edges = np.asarray(bin_edges)
    n_bins = len(edges) - 1

    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i < n_bins - 1:
            mask = (p >= lo) & (p < hi)
        else:
            mask = (p >= lo) & (p <= hi)
        n_bin = int(mask.sum())
        rows.append({
            "bin_lo": lo,
            "bin_hi": hi,
            "n_total": n_bin,
            "n_positive": int(y[mask].sum()) if n_bin > 0 else 0,
            "mean_predicted": float(p[mask].mean()) if n_bin > 0 else float("nan"),
            "mean_actual": float(y[mask].mean()) if n_bin > 0 else float("nan"),
            "weight": n_bin / N if N > 0 else 0.0,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Top-K metrics
# ---------------------------------------------------------------------------

def top_k_row_count(n: int, k_pct: float) -> int:
    """Return ceil(N × K / 100).

    Parameters
    ----------
    n : int  — total number of rows
    k_pct : float — percentage (e.g. 5, 10, 20)
    """
    return math.ceil(n * k_pct / 100)


def _top_k_indices(
    scores: np.ndarray,
    segment_ids: np.ndarray,
    dates: np.ndarray,
    row_ids: np.ndarray,
    k: int,
) -> np.ndarray:
    """Return indices of the top-k rows using deterministic 4-level tie-breaking.

    Order: descending score → canonical_segment_id (asc) → as_of_date (asc) → segment_month_id (asc).
    """
    df = pd.DataFrame({
        "score": scores,
        "canonical_segment_id": segment_ids,
        "as_of_date": dates,
        "segment_month_id": row_ids,
        "orig_idx": np.arange(len(scores)),
    })
    df_sorted = df.sort_values(
        by=["score", "canonical_segment_id", "as_of_date", "segment_month_id"],
        ascending=[False, True, True, True],
    )
    return df_sorted["orig_idx"].values[:k]


def precision_at_k(
    y_true: np.ndarray,
    y_score: np.ndarray,
    k_pct: float,
    segment_ids: np.ndarray | None = None,
    dates: np.ndarray | None = None,
    row_ids: np.ndarray | None = None,
) -> float:
    """Fraction of positives among the top-K% rows by score."""
    n = len(y_true)
    k = top_k_row_count(n, k_pct)
    if segment_ids is None:
        segment_ids = np.arange(n).astype(str)
    if dates is None:
        dates = np.zeros(n, dtype=str)
    if row_ids is None:
        row_ids = np.arange(n).astype(str)
    idx = _top_k_indices(y_score, segment_ids, dates, row_ids, k)
    return float(np.mean(np.asarray(y_true)[idx]))


def recall_at_k(
    y_true: np.ndarray,
    y_score: np.ndarray,
    k_pct: float,
    segment_ids: np.ndarray | None = None,
    dates: np.ndarray | None = None,
    row_ids: np.ndarray | None = None,
) -> float:
    """Fraction of all positives captured in the top-K% rows."""
    n = len(y_true)
    k = top_k_row_count(n, k_pct)
    y = np.asarray(y_true)
    total_pos = int(y.sum())
    if total_pos == 0:
        return float("nan")
    if segment_ids is None:
        segment_ids = np.arange(n).astype(str)
    if dates is None:
        dates = np.zeros(n, dtype=str)
    if row_ids is None:
        row_ids = np.arange(n).astype(str)
    idx = _top_k_indices(y_score, segment_ids, dates, row_ids, k)
    return float(y[idx].sum() / total_pos)


def lift_at_k(
    y_true: np.ndarray,
    y_score: np.ndarray,
    k_pct: float,
    **kwargs: Any,
) -> float:
    """Lift = precision_at_k / prevalence."""
    prevalence = float(np.mean(y_true))
    if prevalence == 0:
        return float("nan")
    return precision_at_k(y_true, y_score, k_pct, **kwargs) / prevalence
