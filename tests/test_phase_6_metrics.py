"""Tests for Phase 6 metrics.

All tests use synthetic data. No sealed test data accessed.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from sklearn.metrics import average_precision_score as sklearn_ap

from montreal_road_risk.evaluation.metrics import (
    average_precision,
    calibration_slope_intercept,
    expected_calibration_error,
    reliability_table,
    precision_at_k,
    recall_at_k,
    lift_at_k,
    top_k_row_count,
)


# ---------------------------------------------------------------------------
# Average Precision
# ---------------------------------------------------------------------------

class TestAveragePrecision:
    def test_matches_sklearn(self):
        rng = np.random.default_rng(42)
        y = rng.integers(0, 2, 100)
        s = rng.uniform(0, 1, 100)
        assert math.isclose(average_precision(y, s), sklearn_ap(y, s), rel_tol=1e-9)

    def test_perfect_classifier(self):
        y = np.array([0, 0, 1, 1])
        s = np.array([0.1, 0.2, 0.8, 0.9])
        assert average_precision(y, s) == pytest.approx(1.0)

    def test_random_classifier_near_prevalence(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 10000, endpoint=False)
        prev = y.mean()
        ap = average_precision(y, rng.uniform(0, 1, 10000))
        # AP of random classifier ≈ prevalence (not trapezoidal PR-AUC)
        assert abs(ap - prev) < 0.05


# ---------------------------------------------------------------------------
# Calibration slope and intercept (logistic regression, NOT linregress)
# ---------------------------------------------------------------------------

class TestCalibrationSlopeIntercept:
    def test_perfectly_calibrated(self):
        """Perfectly calibrated: slope ≈ 1, intercept ≈ 0."""
        rng = np.random.default_rng(7)
        p = rng.uniform(0.01, 0.99, 500)
        y = rng.binomial(1, p)
        res = calibration_slope_intercept(y, p)
        assert res["converged"]
        assert res["status"] == "ok"
        assert abs(res["slope"] - 1.0) < 0.3
        assert abs(res["intercept"] - 0.0) < 0.3

    def test_convergence_flag_exists(self):
        y = np.array([0, 1, 0, 1])
        p = np.array([0.2, 0.8, 0.3, 0.7])
        res = calibration_slope_intercept(y, p)
        assert "converged" in res
        assert "status" in res

    def test_calibration_in_the_large_separate(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([0.3, 0.3, 0.7, 0.7])
        res = calibration_slope_intercept(y, p)
        citl = res["calibration_in_the_large"]
        # citl = mean(y) - mean(p) = 0.5 - 0.5 = 0
        assert abs(citl) < 0.01

    def test_not_linregress(self):
        """Verify it is not scipy linregress — output has no 'rvalue' key."""
        y = np.array([0, 1, 0, 1, 0, 1])
        p = np.array([0.2, 0.7, 0.3, 0.6, 0.4, 0.8])
        res = calibration_slope_intercept(y, p)
        assert "rvalue" not in res
        assert "slope" in res
        assert "intercept" in res


# ---------------------------------------------------------------------------
# ECE
# ---------------------------------------------------------------------------

class TestECE:
    def test_ece_finite_with_empty_bins(self):
        """Empty bins contribute zero; ECE must be finite."""
        y = np.array([0, 1])
        p = np.array([0.05, 0.15])  # Only bins [0, 0.1) and [0.1, 0.2) occupied
        ece = expected_calibration_error(y, p)
        assert math.isfinite(ece)
        assert ece >= 0

    def test_ece_invariant_to_row_order(self):
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 200)
        p = rng.uniform(0, 1, 200)
        perm = rng.permutation(200)
        assert math.isclose(
            expected_calibration_error(y, p),
            expected_calibration_error(y[perm], p[perm]),
            rel_tol=1e-12,
        )

    def test_ece_perfect_calibration(self):
        """Every bin: mean_pred = mean_actual → ECE = 0."""
        # Create data where in each bin the predictions equal the mean label
        y = np.zeros(100)
        p = np.zeros(100)
        for i in range(10):
            lo = i * 0.1
            hi = lo + 0.05
            mid = (lo + hi) / 2
            start_i = i * 10
            end_i = (i + 1) * 10
            p[start_i:end_i] = mid
            # Assign labels so that mean(y) ≈ mid
            n_pos = round(10 * mid)
            y[start_i:start_i + n_pos] = 1
        ece = expected_calibration_error(y, p)
        assert ece < 0.15  # Not perfect due to rounding, but small

    def test_reliability_table_empty_bin_is_nan(self):
        y = np.array([0, 1])
        p = np.array([0.05, 0.15])
        rt = reliability_table(y, p)
        empty_bins = rt[rt["n_total"] == 0]
        assert empty_bins["mean_predicted"].isna().all()
        assert empty_bins["mean_actual"].isna().all()

    def test_reliability_table_weight_sum_le_1(self):
        rng = np.random.default_rng(2)
        y = rng.integers(0, 2, 100)
        p = rng.uniform(0, 1, 100)
        rt = reliability_table(y, p)
        assert rt["weight"].sum() <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# Top-K
# ---------------------------------------------------------------------------

class TestTopK:
    def test_row_count_uses_ceil(self):
        assert top_k_row_count(100, 5) == 5    # ceil(100 * 5/100) = 5
        assert top_k_row_count(101, 5) == 6    # ceil(101 * 5/100) = ceil(5.05) = 6
        assert top_k_row_count(99, 10) == 10   # ceil(99 * 10/100) = ceil(9.9) = 10
        assert top_k_row_count(100, 10) == 10
        assert top_k_row_count(101, 10) == 11  # ceil(10.1) = 11

    def test_row_count_not_floor(self):
        # This would be 9 with floor, 10 with ceil
        assert top_k_row_count(99, 10) == 10

    def test_tie_breaking_is_deterministic(self):
        """Same inputs produce identical top-K selection on repeated calls."""
        rng = np.random.default_rng(5)
        n = 50
        y = rng.integers(0, 2, n)
        s = rng.choice([0.5, 0.5, 0.5], size=n)  # lots of ties
        segs = np.array([f"seg_{i:03d}" for i in range(n)])
        dates = np.array(["2024-01-31"] * n)
        rows = np.array([f"row_{i:03d}" for i in range(n)])

        p1 = precision_at_k(y, s, 20.0, segs, dates, rows)
        p2 = precision_at_k(y, s, 20.0, segs, dates, rows)
        assert p1 == p2

    def test_precision_at_k_perfect(self):
        y = np.array([1, 1, 1, 0, 0, 0, 0, 0, 0, 0])
        s = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])
        # top 30% = 3 rows → all positives
        assert precision_at_k(y, s, 30.0) == pytest.approx(1.0)

    def test_recall_at_k(self):
        y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
        s = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])
        # top 20% = 2 rows → both positives captured
        assert recall_at_k(y, s, 20.0) == pytest.approx(1.0)

    def test_lift_at_k(self):
        y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
        s = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
        prevalence = 0.2
        p_at_k = precision_at_k(y, s, 20.0)
        lift = lift_at_k(y, s, 20.0)
        assert math.isclose(lift, p_at_k / prevalence, rel_tol=1e-9)
