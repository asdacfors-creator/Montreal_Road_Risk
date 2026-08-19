"""
Unit tests for Phase 9 Survival Analysis Module.
Tests cohort generation, Kaplan-Meier estimation, Log-Rank tests, Weibull AFT model, and C-index metrics.
"""

from pathlib import Path
import numpy as np
import pandas as pd

from montreal_road_risk.survival.cohort import build_survival_cohort
from montreal_road_risk.survival.non_parametric import kaplan_meier_estimator, log_rank_test
from montreal_road_risk.survival.modeling import WeibullAFTModel
from montreal_road_risk.survival.metrics import concordance_index


def test_survival_cohort_generation():
    """Verify survival_cohort.parquet structure, column types, and censoring indicators."""
    cohort_path = Path("data/processed/phase_9/survival_cohort.parquet")
    if not cohort_path.exists():
        df = build_survival_cohort(output_path=cohort_path)
    else:
        df = pd.read_parquet(cohort_path)

    expected_cols = [
        "canonical_segment_id",
        "interval_index",
        "start_date",
        "end_date",
        "duration_days",
        "event_observed",
        "functional_road_class",
        "primary_borough_id",
        "segment_length_m",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing required column: {col}"

    assert len(df) > 0, "Cohort dataframe is empty."
    assert (df["duration_days"] > 0).all(), "Found non-positive durations."
    assert set(df["event_observed"].unique()).issubset({0, 1}), "Invalid event_observed values."
    assert df["canonical_segment_id"].nunique() >= 47970, f"Expected ~47,983 unique segments, got {df['canonical_segment_id'].nunique()}"


def test_kaplan_meier_estimator():
    """Verify Kaplan-Meier estimation mathematical properties."""
    durations = np.array([10, 20, 30, 40, 50, 60, 70, 80])
    events = np.array([1, 1, 0, 1, 0, 1, 1, 0])

    km_res = kaplan_meier_estimator(durations, events)

    assert "timeline" in km_res
    assert "survival_probability" in km_res
    assert "median_survival_time" in km_res

    s_prob = km_res["survival_probability"]
    assert (s_prob >= 0.0).all() and (s_prob <= 1.0).all(), "Survival probabilities must be in [0, 1]."
    # Monotonically non-increasing property
    assert (np.diff(s_prob) <= 1e-9).all(), "Survival probability must be monotonically non-increasing."


def test_log_rank_test():
    """Verify Log-Rank hypothesis test between two distinct survival distributions."""
    dur_a = np.array([10, 15, 20, 25, 30, 35, 40])
    evt_a = np.array([1, 1, 1, 1, 1, 1, 1])

    dur_b = np.array([50, 60, 70, 80, 90, 100, 110])
    evt_b = np.array([1, 1, 1, 1, 1, 1, 1])

    res = log_rank_test(dur_a, evt_a, dur_b, evt_b)

    assert res["degrees_of_freedom"] == 1
    assert res["test_statistic"] > 0.0
    assert res["p_value"] < 0.05, "Log-rank test should detect significant difference between Group A and Group B."


def test_weibull_aft_model():
    """Verify Weibull AFT model fitting and predictions."""
    np.random.seed(42)
    n = 200
    X = np.random.randn(n, 2)
    true_log_t = 3.0 + 0.5 * X[:, 0] - 0.3 * X[:, 1] + np.random.gumbel(size=n)
    durations = np.exp(true_log_t)
    durations = np.clip(durations, 1.0, 1000.0)
    events = np.random.binomial(1, 0.8, size=n)

    model = WeibullAFTModel(l2_reg=1e-4)
    model.fit(durations, events, X)

    assert model.is_fitted_
    assert model.sigma_ > 0.0, "Weibull scale parameter sigma must be strictly positive."

    pred_median = model.predict_median_survival(X)
    assert len(pred_median) == n
    assert (pred_median > 0.0).all(), "Predicted median survival times must be positive."

    surv_prob = model.predict_survival_probability(times=[30.0, 60.0], X=X[:5])
    assert surv_prob.shape == (5, 2)
    assert (surv_prob >= 0.0).all() and (surv_prob <= 1.0).all()


def test_concordance_index():
    """Verify Harrell's C-index computation."""
    durations = np.array([10, 20, 30, 40, 50])
    events = np.array([1, 1, 1, 1, 1])
    # Higher risk score -> shorter survival duration
    predicted_risk_scores = np.array([5.0, 4.0, 3.0, 2.0, 1.0])

    c_idx = concordance_index(durations, events, predicted_risk_scores)
    assert c_idx == 1.0, f"Expected perfect C-index of 1.0, got {c_idx}"
