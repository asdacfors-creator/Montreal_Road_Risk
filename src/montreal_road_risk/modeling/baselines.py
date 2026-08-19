"""
src/montreal_road_risk/modeling/baselines.py

Three baseline models for Phase 5.

Rules
-----
* All fitted exclusively on training partition.
* All produce probability outputs in [0, 1].
* SegmentHistoryBaseline uses Laplace smoothing — not count/365.
* FunctionalClassPriorBaseline falls back to global prevalence for sparse classes.
* Phase 5 only: no calibration applied here.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Minimum training rows in a class before global-prevalence fallback is used.
FUNCTIONAL_CLASS_MIN_COUNT = 30
# Laplace smoothing alpha
LAPLACE_ALPHA = 1


class PrevalenceBaseline:
    """Predicts the training positive rate for every row."""

    def __init__(self):
        self.prevalence_: float | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "PrevalenceBaseline":
        self.prevalence_ = float(y.mean())
        log.info("PrevalenceBaseline fitted: prevalence=%.6f", self.prevalence_)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.prevalence_ is None:
            raise RuntimeError("Call fit() before predict_proba()")
        proba = np.full(len(X), self.prevalence_, dtype=float)
        return proba

    def __repr__(self):
        return f"PrevalenceBaseline(prevalence={self.prevalence_})"


class FunctionalClassPriorBaseline:
    """
    Per-road-class posterior with global-prevalence fallback for sparse classes.

    For each class with < min_count training rows, falls back to global prevalence.
    """

    def __init__(self, min_count: int = FUNCTIONAL_CLASS_MIN_COUNT):
        self.min_count = min_count
        self.class_prior_: dict | None = None
        self.global_prevalence_: float | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FunctionalClassPriorBaseline":
        if "functional_road_class" not in X.columns:
            raise ValueError("'functional_road_class' column required for FunctionalClassPriorBaseline")

        df = X[["functional_road_class"]].copy()
        df["_y"] = y.values

        global_prev = float(y.mean())
        self.global_prevalence_ = global_prev

        grouped = df.groupby("functional_road_class")["_y"].agg(["sum", "count"])
        priors = {}
        for cls, row in grouped.iterrows():
            if row["count"] >= self.min_count:
                priors[cls] = float(row["sum"] / row["count"])
            else:
                priors[cls] = global_prev
                log.debug(
                    "Class '%s' has %d rows < min_count %d; using global prevalence %.6f",
                    cls, row["count"], self.min_count, global_prev,
                )
        self.class_prior_ = priors
        log.info(
            "FunctionalClassPriorBaseline fitted: %d classes, global_prev=%.6f",
            len(priors), global_prev,
        )
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.class_prior_ is None:
            raise RuntimeError("Call fit() before predict_proba()")
        proba = X["functional_road_class"].map(self.class_prior_).fillna(
            self.global_prevalence_
        ).values.astype(float)
        return proba

    def __repr__(self):
        return f"FunctionalClassPriorBaseline(min_count={self.min_count})"


class SegmentHistoryBaseline:
    """
    Laplace-smoothed empirical positive rate per segment.

    p(segment) = (n_pos_train + alpha) / (n_rows_train + 2*alpha)

    Segments absent from training receive global training prevalence.
    """

    def __init__(self, alpha: float = LAPLACE_ALPHA, segment_col: str = "canonical_segment_id"):
        self.alpha = alpha
        self.segment_col = segment_col
        self.segment_prior_: dict | None = None
        self.global_prevalence_: float | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "SegmentHistoryBaseline":
        if self.segment_col not in X.columns:
            raise ValueError(f"'{self.segment_col}' column required for SegmentHistoryBaseline.fit()")

        df = X[[self.segment_col]].copy()
        df["_y"] = y.values

        global_prev = float(y.mean())
        self.global_prevalence_ = global_prev

        grouped = df.groupby(self.segment_col)["_y"].agg(["sum", "count"])
        priors = {}
        for seg, row in grouped.iterrows():
            n_pos   = row["sum"]
            n_total = row["count"]
            priors[seg] = float((n_pos + self.alpha) / (n_total + 2 * self.alpha))

        self.segment_prior_ = priors
        log.info(
            "SegmentHistoryBaseline fitted: %d segments, global_prev=%.6f, alpha=%.1f",
            len(priors), global_prev, self.alpha,
        )
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.segment_prior_ is None:
            raise RuntimeError("Call fit() before predict_proba()")
        proba = X[self.segment_col].map(self.segment_prior_).fillna(
            self.global_prevalence_
        ).values.astype(float)
        return proba

    def __repr__(self):
        return f"SegmentHistoryBaseline(alpha={self.alpha})"
