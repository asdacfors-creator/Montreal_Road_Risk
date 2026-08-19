"""
Survival evaluation metrics module.
Provides zero-dependency vectorised implementation of Harrell's Concordance Index (C-Index).
"""

import numpy as np
import pandas as pd


def concordance_index(
    durations: np.ndarray | pd.Series,
    events: np.ndarray | pd.Series,
    predicted_risk_scores: np.ndarray | pd.Series,
) -> float:
    """
    Computes Harrell's Concordance Index (C-Index) for time-to-event outcomes.

    A pair (i, j) is eligible if duration_i < duration_j and event_i == 1.
    The pair is concordant if predicted_risk_score_i > predicted_risk_score_j.
    Tied scores count as 0.5.

    Parameters
    ----------
    durations : Observed time-to-event or censoring durations (days)
    events : Binary event indicators (1 = event observed, 0 = right-censored)
    predicted_risk_scores : Model predicted risk scores (higher score = higher risk / shorter survival)

    Returns
    -------
    float
        Harrell's C-index value in range [0.0, 1.0].
    """
    durations = np.asarray(durations, dtype=float)
    events = np.asarray(events, dtype=int)
    scores = np.asarray(predicted_risk_scores, dtype=float)

    n = len(durations)
    if n < 2:
        return 0.5

    concordant = 0.0
    total_pairs = 0.0

    # Vectorized / pairwise comparison for eligible pairs
    # Pair (i, j) eligible if events[i] == 1 and durations[i] < durations[j]
    event_indices = np.where(events == 1)[0]

    for i in event_indices:
        t_i = durations[i]
        s_i = scores[i]

        # Candidates j where t_j > t_i
        eligible_j = np.where(durations > t_i)[0]

        if len(eligible_j) == 0:
            continue

        s_j = scores[eligible_j]

        # Concordance check: s_i > s_j is concordant
        concordant += np.sum(s_i > s_j) + 0.5 * np.sum(s_i == s_j)
        total_pairs += len(eligible_j)

    if total_pairs == 0:
        return 0.5

    return float(concordant / total_pairs)
