"""Phase 6 bootstrap confidence intervals.

Primary unit: segment-cluster (canonical_segment_id sampled with replacement).
Secondary unit: row-level (standard IID bootstrap).

Both use index-only resampling to avoid duplicating large data arrays.
Seed=42, 100 smoke repetitions, 500 final repetitions (D6.4, D6.5 approved).
"""

from __future__ import annotations

from typing import Callable

import numpy as np


class BootstrapCI:
    """Percentile bootstrap confidence intervals.

    Parameters
    ----------
    metric_fn : callable(y_true, y_score) -> float
        The metric to bootstrap.
    n_repetitions : int
        Number of bootstrap samples (100 for smoke, 500 for final).
    confidence : float
        Coverage probability (default 0.95).
    seed : int
        Random seed (D6.5: fixed at 42).
    unit : str
        ``"segment"`` for segment-cluster bootstrap (primary),
        ``"row"`` for row-level IID bootstrap (secondary).
    """

    def __init__(
        self,
        metric_fn: Callable[[np.ndarray, np.ndarray], float],
        n_repetitions: int = 500,
        confidence: float = 0.95,
        seed: int = 42,
        unit: str = "segment",
    ) -> None:
        self.metric_fn = metric_fn
        self.n_repetitions = n_repetitions
        self.confidence = confidence
        self.seed = seed
        self.unit = unit
        if unit not in ("segment", "row"):
            raise ValueError(f"unit must be 'segment' or 'row', got {unit!r}")

    def compute(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
        segment_ids: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Compute bootstrap CI.

        Parameters
        ----------
        y_true : 1-D array of labels.
        y_score : 1-D array of scores.
        segment_ids : 1-D array of segment identifiers.
            Required when ``unit == "segment"``.

        Returns
        -------
        dict with keys: point_estimate, lower, upper, n_repetitions, seed, unit, confidence
        """
        y = np.asarray(y_true, dtype=float)
        s = np.asarray(y_score, dtype=float)
        point = self.metric_fn(y, s)

        rng = np.random.default_rng(self.seed)
        boot_stats = []

        if self.unit == "segment":
            if segment_ids is None:
                raise ValueError("segment_ids required for segment-cluster bootstrap.")
            seg = np.asarray(segment_ids)
            unique_segs = np.unique(seg)
            for _ in range(self.n_repetitions):
                sampled_segs = rng.choice(unique_segs, size=len(unique_segs), replace=True)
                idx = np.concatenate([np.where(seg == s_)[0] for s_ in sampled_segs])
                if len(np.unique(y[idx])) < 2:
                    continue
                boot_stats.append(self.metric_fn(y[idx], s[idx]))
        else:
            n = len(y)
            for _ in range(self.n_repetitions):
                idx = rng.integers(0, n, size=n)
                if len(np.unique(y[idx])) < 2:
                    continue
                boot_stats.append(self.metric_fn(y[idx], s[idx]))

        if not boot_stats:
            return {
                "point_estimate": point,
                "lower": float("nan"),
                "upper": float("nan"),
                "n_repetitions": 0,
                "seed": self.seed,
                "unit": self.unit,
                "confidence": self.confidence,
                "status": "INSUFFICIENT_VARIATION",
            }

        alpha = 1.0 - self.confidence
        lower = float(np.percentile(boot_stats, 100 * alpha / 2))
        upper = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
        return {
            "point_estimate": point,
            "lower": lower,
            "upper": upper,
            "n_repetitions": len(boot_stats),
            "seed": self.seed,
            "unit": self.unit,
            "confidence": self.confidence,
            "status": "ok",
        }
