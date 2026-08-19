"""
Non-parametric survival analysis module.
Provides zero-dependency vectorised Kaplan-Meier estimation and Log-Rank tests using NumPy and SciPy.
"""

import numpy as np
import pandas as pd
from scipy import stats


def kaplan_meier_estimator(
    durations: np.ndarray | pd.Series,
    events: np.ndarray | pd.Series,
) -> dict:
    """
    Computes the non-parametric Kaplan-Meier survival function S_hat(t),
    Greenwood's variance, 95% confidence intervals, and median survival time.

    Parameters
    ----------
    durations : np.ndarray | pd.Series
        Array of observed durations (days).
    events : np.ndarray | pd.Series
        Binary event indicators (1 = event, 0 = right-censored).

    Returns
    -------
    dict
        Dictionary containing:
        - 'timeline': unique event times (sorted)
        - 'survival_probability': S_hat(t) values
        - 'greenwood_variance': V_hat[S_hat(t)]
        - 'confidence_interval_lower': 95% lower bound
        - 'confidence_interval_upper': 95% upper bound
        - 'n_at_risk': number at risk at each time step
        - 'n_events': number of events at each time step
        - 'median_survival_time': estimated median survival time T_50 (days)
    """
    durations = np.asarray(durations, dtype=float)
    events = np.asarray(events, dtype=int)

    if len(durations) == 0:
        raise ValueError("Durations array cannot be empty.")
    if len(durations) != len(events):
        raise ValueError("Durations and events must have equal length.")

    # Sort by duration
    sort_idx = np.argsort(durations)
    dur_sorted = durations[sort_idx]
    evt_sorted = events[sort_idx]

    # Get unique times and aggregated event/censor counts
    unique_times, indices = np.unique(dur_sorted, return_index=True)
    n_total = len(dur_sorted)

    timeline = []
    survival_prob = []
    greenwood_sum = []
    n_at_risk_list = []
    n_events_list = []

    current_n_at_risk = n_total
    current_s = 1.0
    cum_greenwood = 0.0

    for i, t in enumerate(unique_times):
        # Slice range for time t
        idx_start = indices[i]
        idx_end = indices[i + 1] if i + 1 < len(indices) else len(dur_sorted)

        d_i = np.sum(evt_sorted[idx_start:idx_end])  # number of events at t
        c_i = (idx_end - idx_start) - d_i            # number of censored at t
        n_i = current_n_at_risk                       # number at risk at t

        if n_i <= 0:
            break

        if d_i > 0:
            current_s *= (1.0 - d_i / n_i)
            if n_i > d_i:
                cum_greenwood += d_i / (n_i * (n_i - d_i))

        timeline.append(t)
        survival_prob.append(current_s)
        greenwood_sum.append((current_s ** 2) * cum_greenwood)
        n_at_risk_list.append(n_i)
        n_events_list.append(d_i)

        current_n_at_risk -= (d_i + c_i)

    timeline = np.array(timeline)
    survival_prob = np.array(survival_prob)
    greenwood_var = np.array(greenwood_sum)

    # 95% Greenwood confidence bounds (clipped to [0, 1])
    std_err = np.sqrt(greenwood_var)
    ci_lower = np.clip(survival_prob - 1.96 * std_err, 0.0, 1.0)
    ci_upper = np.clip(survival_prob + 1.96 * std_err, 0.0, 1.0)

    # Median survival time (first time t where S(t) <= 0.5)
    below_50 = np.where(survival_prob <= 0.5)[0]
    median_time = float(timeline[below_50[0]]) if len(below_50) > 0 else np.nan

    return {
        "timeline": timeline,
        "survival_probability": survival_prob,
        "greenwood_variance": greenwood_var,
        "confidence_interval_lower": ci_lower,
        "confidence_interval_upper": ci_upper,
        "n_at_risk": np.array(n_at_risk_list),
        "n_events": np.array(n_events_list),
        "median_survival_time": median_time,
    }


def log_rank_test(
    durations_a: np.ndarray | pd.Series,
    events_a: np.ndarray | pd.Series,
    durations_b: np.ndarray | pd.Series,
    events_b: np.ndarray | pd.Series,
) -> dict:
    """
    Performs a 2-group Log-Rank hypothesis test comparing survival distributions.

    Parameters
    ----------
    durations_a, events_a : Group A durations and event indicators
    durations_b, events_b : Group B durations and event indicators

    Returns
    -------
    dict
        - 'test_statistic': Chi-square statistic (1 d.o.f.)
        - 'p_value': Two-sided p-value
        - 'degrees_of_freedom': 1
        - 'observed_events_a': Total observed events in group A
        - 'expected_events_a': Total expected events in group A
        - 'observed_events_b': Total observed events in group B
        - 'expected_events_b': Total expected events in group B
    """
    dur_a = np.asarray(durations_a, dtype=float)
    evt_a = np.asarray(events_a, dtype=int)
    dur_b = np.asarray(durations_b, dtype=float)
    evt_b = np.asarray(events_b, dtype=int)

    # All distinct event times across both groups where at least 1 event occurred
    all_durations = np.concatenate([dur_a, dur_b])
    all_events = np.concatenate([evt_a, evt_b])

    event_times = np.unique(all_durations[all_events == 1])

    O_a = 0.0
    E_a = 0.0
    var_a = 0.0

    for t in event_times:
        # Group A at risk & events at t
        n_a_t = np.sum(dur_a >= t)
        d_a_t = np.sum((dur_a == t) & (evt_a == 1))

        # Group B at risk & events at t
        n_b_t = np.sum(dur_b >= t)
        d_b_t = np.sum((dur_b == t) & (evt_b == 1))

        n_t = n_a_t + n_b_t
        d_t = d_a_t + d_b_t

        if n_t <= 1 or d_t == 0:
            continue

        e_a_t = (n_a_t / n_t) * d_t
        v_t = (n_a_t * n_b_t * d_t * (n_t - d_t)) / ((n_t ** 2) * (n_t - 1))

        O_a += d_a_t
        E_a += e_a_t
        var_a += v_t

    if var_a <= 0:
        chi2_stat = 0.0
        p_val = 1.0
    else:
        chi2_stat = float(((O_a - E_a) ** 2) / var_a)
        p_val = float(1.0 - stats.chi2.cdf(chi2_stat, df=1))

    O_b = np.sum(evt_b)
    E_b = (np.sum(evt_a) + O_b) - E_a

    return {
        "test_statistic": chi2_stat,
        "p_value": p_val,
        "degrees_of_freedom": 1,
        "observed_events_a": int(np.sum(evt_a)),
        "expected_events_a": float(E_a),
        "observed_events_b": int(O_b),
        "expected_events_b": float(E_b),
    }
