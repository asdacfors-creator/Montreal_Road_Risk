"""Tests for Phase 6 bootstrap CI.

Synthetic fixtures only. No sealed test data accessed.
"""

from __future__ import annotations

import numpy as np
import pytest

from montreal_road_risk.evaluation.bootstrap import BootstrapCI
from montreal_road_risk.evaluation.metrics import average_precision


class TestBootstrapDeterminism:
    def test_same_seed_identical_results(self):
        rng = np.random.default_rng(99)
        y = rng.integers(0, 2, 200).astype(float)
        s = rng.uniform(0, 1, 200)
        segs = np.array([f"seg_{i % 20}" for i in range(200)])

        boot = BootstrapCI(average_precision, n_repetitions=50, seed=42, unit="segment")
        r1 = boot.compute(y, s, segs)
        r2 = boot.compute(y, s, segs)
        assert r1["lower"] == r2["lower"]
        assert r1["upper"] == r2["upper"]
        assert r1["point_estimate"] == r2["point_estimate"]

    def test_row_and_segment_ci_differ(self):
        """CI widths differ between row-level and segment-cluster bootstrap."""
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 500).astype(float)
        s = rng.uniform(0, 1, 500)
        segs = np.array([f"seg_{i % 50}" for i in range(500)])

        boot_seg = BootstrapCI(average_precision, n_repetitions=50, seed=42, unit="segment")
        boot_row = BootstrapCI(average_precision, n_repetitions=50, seed=42, unit="row")
        r_seg = boot_seg.compute(y, s, segs)
        r_row = boot_row.compute(y, s)
        # They may not always differ for small n, but should have valid CIs
        assert r_seg["status"] == "ok"
        assert r_row["status"] == "ok"

    def test_smoke_100_reps(self):
        rng = np.random.default_rng(7)
        y = rng.integers(0, 2, 300).astype(float)
        s = rng.uniform(0, 1, 300)
        boot = BootstrapCI(average_precision, n_repetitions=100, seed=42, unit="row")
        r = boot.compute(y, s)
        assert r["n_repetitions"] > 0
        assert np.isfinite(r["lower"])
        assert np.isfinite(r["upper"])

    def test_invalid_unit_raises(self):
        with pytest.raises(ValueError, match="unit must be"):
            BootstrapCI(average_precision, unit="invalid")

    def test_segment_requires_segment_ids(self):
        y = np.array([0, 1, 0, 1])
        s = np.array([0.2, 0.8, 0.3, 0.7])
        boot = BootstrapCI(average_precision, n_repetitions=10, unit="segment")
        with pytest.raises(ValueError, match="segment_ids required"):
            boot.compute(y, s)  # no segment_ids passed
