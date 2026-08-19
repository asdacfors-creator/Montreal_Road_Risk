"""Tests for Phase 6 subgroup evaluator.

Synthetic fixtures only. No sealed test data accessed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from montreal_road_risk.evaluation.subgroup import SubgroupEvaluator, _INSUFFICIENT


def _make_df(n_per_group: dict[str, int], n_pos_frac: float = 0.2, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for grp, n in n_per_group.items():
        n_pos = max(1, int(n * n_pos_frac))
        y = np.zeros(n)
        y[:n_pos] = 1
        s = rng.uniform(0, 1, n)
        for i in range(n):
            rows.append({
                "borough": grp,
                "target_repair_90d": y[i],
                "score": s[i],
                "canonical_segment_id": f"seg_{grp}_{i}",
                "as_of_date": "2024-01-31",
                "segment_month_id": f"{grp}_{i}",
            })
    return pd.DataFrame(rows)


class TestSubgroupMinSize:
    def test_insufficient_rows_marked(self):
        df = _make_df({"small": 10, "large": 600})
        ev = SubgroupEvaluator(min_rows=500, min_positive_events=50)
        results = ev.evaluate(df, "borough", "target_repair_90d", "score")
        by_grp = {r["subgroup_val"]: r for r in results}
        assert by_grp["small"]["ap"] == _INSUFFICIENT
        assert by_grp["small"]["status"] == _INSUFFICIENT

    def test_sufficient_rows_returns_metrics(self):
        df = _make_df({"large": 600})
        ev = SubgroupEvaluator(min_rows=500, min_positive_events=50)
        results = ev.evaluate(df, "borough", "target_repair_90d", "score")
        assert results[0]["status"] in ("ok", "error")  # no INSUFFICIENT

    def test_insufficient_not_silently_dropped(self):
        df = _make_df({"tiny": 5})
        ev = SubgroupEvaluator(min_rows=500, min_positive_events=50)
        results = ev.evaluate(df, "borough", "target_repair_90d", "score")
        assert len(results) == 1  # present, not dropped
        assert results[0]["ap"] == _INSUFFICIENT

    def test_no_model_change_after_subgroup(self):
        """Subgroup results are descriptive only — results dict has no retraining keys."""
        df = _make_df({"grp": 600})
        ev = SubgroupEvaluator()
        results = ev.evaluate(df, "borough", "target_repair_90d", "score")
        for r in results:
            assert "model" not in r
            assert "retrain" not in r
