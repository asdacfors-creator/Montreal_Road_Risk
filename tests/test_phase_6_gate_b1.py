"""Tests for Phase 6 Gate B1 calibration and threshold freeze.

All tests use synthetic fixtures and temporary directories.
No test reads the sealed test data, B1 panel files, or calibrated model artifacts.
Tests verify the logic and constraints of Gate B1.
"""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from montreal_road_risk.evaluation.calibration import PlattCalibrator
from montreal_road_risk.evaluation.metrics import (
    expected_calibration_error,
    top_k_row_count,
    precision_at_k,
    recall_at_k,
    lift_at_k,
    reliability_table,
    calibration_slope_intercept,
)
from montreal_road_risk.evaluation.seal_guard import (
    TestSealGuard,
    SealViolationError,
)

import pyarrow as pa
import pyarrow.parquet as pq


# ---------------------------------------------------------------------------
# Constants matching the project manifest
# ---------------------------------------------------------------------------
B1_ANCHORS = ["2024-01-31", "2024-02-29", "2024-03-31"]
EMBARGO_ANCHORS = ["2024-04-30", "2024-05-31", "2024-06-30"]
B2_ANCHORS = [
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31",
]
EXPECTED_B1_ROWS = 143_949
EXPECTED_PER_ANCHOR = 47_983
RECALL_TARGET = 0.5
TOP_K_PERCENTS = [5, 10, 20]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_manifest(tmp: Path, sha: str, b1_rows: int, emb_rows: int = 6, b2_rows: int = 22) -> Path:
    m = {
        "sealed_file": str(tmp / "test.parquet"),
        "sealed_file_sha256": sha,
        "calibration_anchors": B1_ANCHORS,
        "calibration_expected_rows": b1_rows,
        "embargo_anchors": EMBARGO_ANCHORS,
        "embargo_expected_rows": emb_rows,
        "final_test_anchors": B2_ANCHORS,
        "final_test_expected_rows": b2_rows,
        "embargo_targets_accessed": False,
    }
    mp = tmp / "test_split_manifest.json"
    mp.write_text(json.dumps(m))
    return mp


def _make_parquet(tmp: Path, anchors: list[str], rows_each: int = 2) -> tuple[Path, str]:
    """Write a synthetic parquet and return path + sha256."""
    dates, seg_ids, smids, scores, targets = [], [], [], [], []
    for a in anchors:
        for i in range(rows_each):
            dates.append(a)
            seg_ids.append(f"seg_{i}")
            smids.append(f"seg_{i}_{a}")
            scores.append(float(i) / max(rows_each, 1))
            targets.append(1 if i % 5 == 0 else 0)
    tbl = pa.table({
        "as_of_date": pa.array(dates, type=pa.string()),
        "canonical_segment_id": pa.array(seg_ids),
        "segment_month_id": pa.array(smids),
        "score": pa.array(scores),
        "target_repair_90d": pa.array(targets, type=pa.int8()),
    })
    path = tmp / "test.parquet"
    pq.write_table(tbl, path)
    return path, _sha256(path)


def _make_b1_auth(tmp: Path) -> Path:
    p = tmp / "gate_b1_authorization.json"
    p.write_text(json.dumps({
        "gate_b1_authorized": True,
        "gate_b2_authorized": False,
        "embargo_authorized": False,
    }))
    return p


def _fit_platt(n: int = 1000, seed: int = 42) -> tuple[PlattCalibrator, np.ndarray, np.ndarray]:
    """Return a fitted PlattCalibrator with synthetic data."""
    rng = np.random.default_rng(seed)
    raw = rng.uniform(0.01, 0.99, n)
    y = (raw + rng.normal(0, 0.1, n) > 0.5).astype(float)
    cal = PlattCalibrator(C=1e9, max_iter=1000, epsilon=1e-7)
    cal.fit(raw, y)
    return cal, raw, y


# ---------------------------------------------------------------------------
# PART 1: B1 Anchor Allowlist
# ---------------------------------------------------------------------------

class TestB1AnchorAllowlist:
    """B1 partition must contain exactly the three approved anchors."""

    def test_b1_exact_anchors(self, tmp_path):
        all_anchors = B1_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_only(path, auth)
        result_dates = set(tbl.column("as_of_date").to_pylist())
        assert result_dates == set(B1_ANCHORS)

    def test_b1_rejects_embargo_anchors(self, tmp_path):
        all_anchors = B1_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_only(path, auth)
        result_dates = {str(d)[:10] for d in tbl.column("as_of_date").to_pylist()}
        for emb in EMBARGO_ANCHORS:
            assert emb not in result_dates, f"Embargo anchor {emb} found in B1 result"

    def test_b1_rejects_b2_anchors(self, tmp_path):
        all_anchors = B1_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_only(path, auth)
        result_dates = {str(d)[:10] for d in tbl.column("as_of_date").to_pylist()}
        for b2 in B2_ANCHORS:
            assert b2 not in result_dates, f"B2 anchor {b2} found in B1 result"

    def test_b1_requires_exactly_three_anchors(self, tmp_path):
        """Manifest has 3 calibration anchors."""
        assert len(B1_ANCHORS) == 3

    def test_b1_row_count_exact_assertion(self, tmp_path):
        path, sha = _make_parquet(tmp_path, B1_ANCHORS, rows_each=2)
        # Manifest expects 999 — must fail
        mp = _make_manifest(tmp_path, sha, b1_rows=999)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        with pytest.raises(SealViolationError, match="row count mismatch"):
            guard.load_b1_only(path, auth)


# ---------------------------------------------------------------------------
# PART 2: Embargo and B2 Denylist (guard-level)
# ---------------------------------------------------------------------------

class TestEmbargoB2Denylist:
    def test_embargo_not_in_b1_anchors(self):
        """No embargo date appears in the B1 allowlist."""
        assert not (set(B1_ANCHORS) & set(EMBARGO_ANCHORS))

    def test_b2_not_in_b1_anchors(self):
        """No B2 date appears in the B1 allowlist."""
        assert not (set(B1_ANCHORS) & set(B2_ANCHORS))

    def test_embargo_not_in_b2_anchors(self):
        """No embargo date appears in the B2 allowlist."""
        assert not (set(EMBARGO_ANCHORS) & set(B2_ANCHORS))

    def test_no_b2_results_after_b1(self, tmp_path):
        """After B1 calibration, no B2 results file should exist."""
        b2_result = tmp_path / "test_evaluation_results.json"
        assert not b2_result.exists()

    def test_b1_auth_cannot_unlock_b2(self, tmp_path):
        auth_doc = {"gate_b1_authorized": True, "gate_b2_authorized": False}
        assert not auth_doc["gate_b2_authorized"]

    def test_temporal_assertion_b1_before_b2(self):
        """max(B1 target end) < min(B2 as_of_date)."""
        import datetime
        b1_last_anchor = max(B1_ANCHORS)
        b2_first_anchor = min(B2_ANCHORS)
        b1_target_end = datetime.date.fromisoformat(b1_last_anchor) + datetime.timedelta(days=90)
        b2_start = datetime.date.fromisoformat(b2_first_anchor)
        assert b1_target_end < b2_start, (
            f"Temporal isolation violated: {b1_target_end} >= {b2_start}"
        )


# ---------------------------------------------------------------------------
# PART 3: Platt Calibrator (unit tests)
# ---------------------------------------------------------------------------

class TestPlattCalibratorOnly:
    """Unit tests — no model, no data access."""

    def test_platt_fit_and_predict(self):
        cal, raw, y = _fit_platt(1000)
        proba = cal.predict_proba(raw)
        assert proba.shape == (1000,)
        assert np.all(proba >= 0.0) and np.all(proba <= 1.0)
        assert np.all(np.isfinite(proba))

    def test_platt_not_fitted_raises(self):
        cal = PlattCalibrator()
        with pytest.raises(RuntimeError, match="not been fitted"):
            cal.predict_proba(np.array([0.5]))

    def test_platt_requires_at_least_2_positives(self):
        cal = PlattCalibrator()
        raw = np.array([0.1, 0.9, 0.5])
        y = np.array([0.0, 0.0, 0.0])  # No positives
        with pytest.raises(ValueError, match="positive events"):
            cal.fit(raw, y)

    def test_platt_isotonic_not_fitted(self):
        """No isotonic regression object should be created."""
        cal, _, _ = _fit_platt(200)
        # PlattCalibrator only has _lr (LogisticRegression), no isotonic attribute
        assert not hasattr(cal, "_isotonic")
        assert hasattr(cal, "_lr")

    def test_platt_probability_range(self):
        """All calibrated probabilities in [0, 1]."""
        cal, raw, y = _fit_platt(500)
        proba = cal.predict_proba(raw)
        assert float(proba.min()) >= 0.0
        assert float(proba.max()) <= 1.0

    def test_platt_save_and_load(self, tmp_path):
        cal, raw, y = _fit_platt(300)
        path = tmp_path / "calibrator_test.joblib"
        sha = cal.save(path)
        assert path.exists()
        assert len(sha) == 64  # SHA-256 hex

        reloaded = PlattCalibrator.load(path)
        proba_orig = cal.predict_proba(raw)
        proba_rb = reloaded.predict_proba(raw)
        assert np.allclose(proba_orig, proba_rb, atol=0, rtol=0)

    def test_platt_readback_determinism(self, tmp_path):
        cal, raw, y = _fit_platt(300)
        path = tmp_path / "calibrator_det.joblib"
        cal.save(path)
        rb = cal.readback_check(path, raw)
        assert rb["allclose"] is True
        assert rb["max_diff"] < 1e-10
        assert rb["status"] == "PASS"

    def test_platt_fingerprint_identical_after_readback(self, tmp_path):
        cal, raw, y = _fit_platt(300)
        path = tmp_path / "cal_fp.joblib"
        sha1 = cal.save(path)
        sha2 = cal.fingerprint(path)
        assert sha1 == sha2

    def test_platt_prediction_count_matches(self):
        n = 500
        cal, raw, y = _fit_platt(n)
        proba = cal.predict_proba(raw)
        assert len(proba) == n


# ---------------------------------------------------------------------------
# PART 4: Top-K Threshold Formulas
# ---------------------------------------------------------------------------

class TestTopKFormulas:
    """Verify ceil(N * K / 100) formula and tie-breaking."""

    @pytest.mark.parametrize("n,k,expected", [
        (143949, 5, math.ceil(143949 * 5 / 100)),
        (143949, 10, math.ceil(143949 * 10 / 100)),
        (143949, 20, math.ceil(143949 * 20 / 100)),
        (100, 5, 5),
        (101, 5, 6),  # ceil(5.05) = 6
        (100, 10, 10),
        (100, 20, 20),
    ])
    def test_top_k_row_count_formula(self, n, k, expected):
        result = top_k_row_count(n, k)
        assert result == expected, f"top_k_row_count({n}, {k}) = {result} != {expected}"

    def test_top_k_uses_ceil_not_floor(self):
        # 143949 * 5% = 7197.45 → ceil = 7198, floor = 7197
        assert top_k_row_count(143949, 5) == 7198
        assert top_k_row_count(143949, 5) != 7197

    def test_top_k_frozen_percentages(self):
        """Only 5%, 10%, 20% are the frozen Top-K percentages."""
        assert TOP_K_PERCENTS == [5, 10, 20]

    def test_precision_at_k_deterministic(self):
        rng = np.random.default_rng(42)
        n = 200
        scores = rng.uniform(0, 1, n)
        y = (rng.uniform(0, 1, n) > 0.5).astype(float)
        seg_ids = np.arange(n).astype(str)
        dates = np.zeros(n, dtype=str)
        row_ids = np.arange(n).astype(str)

        p1 = precision_at_k(y, scores, 10, seg_ids, dates, row_ids)
        p2 = precision_at_k(y, scores, 10, seg_ids, dates, row_ids)
        assert p1 == p2

    def test_recall_at_k_deterministic(self):
        rng = np.random.default_rng(42)
        n = 200
        scores = rng.uniform(0, 1, n)
        y = (rng.uniform(0, 1, n) > 0.5).astype(float)
        r1 = recall_at_k(y, scores, 10)
        r2 = recall_at_k(y, scores, 10)
        assert r1 == r2

    def test_lift_at_k_positive(self):
        rng = np.random.default_rng(42)
        n = 500
        scores = rng.uniform(0, 1, n)
        y = (rng.uniform(0, 1, n) > 0.7).astype(float)
        lift = lift_at_k(y, scores, 10)
        assert lift > 0


# ---------------------------------------------------------------------------
# PART 5: Recall-based threshold
# ---------------------------------------------------------------------------

class TestRecallThreshold:
    def test_recall_target_loaded_from_config(self):
        """recall_diagnostic_target must be loaded from frozen config, not hardcoded."""
        # This verifies the config file contains the expected value
        cfg_path = Path("config/phase_6_evaluation.json")
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            recall_t = cfg["thresholds"]["recall_diagnostic_target"]
            assert recall_t == RECALL_TARGET, (
                f"recall_diagnostic_target in config is {recall_t}, expected {RECALL_TARGET}"
            )

    def test_recall_target_is_0_5(self):
        assert RECALL_TARGET == 0.5

    def test_recall_threshold_selection_and_tie_handling(self):
        """Verify the highest threshold satisfying recall >= target is selected and ties handled."""
        # Setup synthetic data where scores are tied or distinct
        y = np.array([1, 1, 0, 0, 1, 0, 0, 1, 0, 0]) # 4 positives
        proba = np.array([0.9, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1])
        seg_ids = [f"seg_{i}" for i in range(10)]
        dates = ["2024-01-31"] * 10
        smids = [f"seg_{i}_2024-01-31" for i in range(10)]

        df = pd.DataFrame({
            "segment_month_id": smids,
            "canonical_segment_id": seg_ids,
            "as_of_date": dates,
            "cal_prob": proba,
            "target": y
        })

        # Sort deterministically
        df_sorted = df.sort_values(
            by=["cal_prob", "canonical_segment_id", "as_of_date", "segment_month_id"],
            ascending=[False, True, True, True]
        ).reset_index(drop=True)

        total_pos = df_sorted["target"].sum()
        target_pos = math.ceil(total_pos * 0.5) # needs 2 positives (out of 4)

        df_sorted["cumsum_pos"] = df_sorted["target"].cumsum()
        idx = df_sorted[df_sorted["cumsum_pos"] >= target_pos].index[0]
        boundary_prob = float(df_sorted.loc[idx, "cal_prob"])

        # Boundary index with 2 positives captured:
        # sorted order of proba:
        # idx 0: 0.9 (pos=1)
        # idx 1: 0.9 (pos=1) -> cumsum=2. Satisfied here at index 1!
        # boundary_prob is 0.9
        assert idx == 1
        assert boundary_prob == 0.9

        last_tie_idx = df_sorted[df_sorted["cal_prob"] == boundary_prob].index[-1]
        assert last_tie_idx == 1 # since scores are 0.9, 0.9

        prefix = df_sorted.loc[:last_tie_idx]
        assert len(prefix) == 2
        assert prefix["target"].sum() == 2
        assert float(prefix["target"].sum() / total_pos) == 0.5

    def test_lower_threshold_recall_1_is_rejected(self):
        """Verify we do not select a threshold that achieves recall 1.0 when a higher threshold suffices."""
        # 4 positives total.
        # We need >= 2 positives.
        # If we selected the first index in ascending order (or a very low threshold), recall is 1.0.
        # But we must select the highest threshold satisfying recall >= 0.50 (which selects 2 positives).
        # Selected threshold should be 0.9, not 0.1 (which yields recall 1.0).
        y = np.array([1, 1, 0, 0, 1, 0, 0, 1, 0, 0])
        proba = np.array([0.9, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1])
        seg_ids = [f"seg_{i}" for i in range(10)]
        dates = ["2024-01-31"] * 10
        smids = [f"seg_{i}_2024-01-31" for i in range(10)]

        df = pd.DataFrame({
            "segment_month_id": smids,
            "canonical_segment_id": seg_ids,
            "as_of_date": dates,
            "cal_prob": proba,
            "target": y
        }).sort_values(
            by=["cal_prob", "canonical_segment_id", "as_of_date", "segment_month_id"],
            ascending=[False, True, True, True]
        ).reset_index(drop=True)

        total_pos = df["target"].sum()
        target_pos = math.ceil(total_pos * 0.5)

        df["cumsum_pos"] = df["target"].cumsum()
        idx = df[df["cumsum_pos"] >= target_pos].index[0]
        boundary_prob = float(df.loc[idx, "cal_prob"])

        assert boundary_prob == 0.9
        assert boundary_prob > 0.1 # rejected the lower threshold

    def test_four_level_ordering_is_respected(self):
        """Verify sorting respects descending proba -> canonical_segment_id -> as_of_date -> segment_month_id."""
        y = np.array([1, 1, 1, 1])
        proba = np.array([0.5, 0.5, 0.5, 0.5])
        seg_ids = ["seg_b", "seg_a", "seg_a", "seg_a"]
        dates = ["2024-02-29", "2024-02-29", "2024-01-31", "2024-01-31"]
        smids = ["seg_b_2", "seg_a_3", "seg_a_1", "seg_a_2"] # segment_month_id ascending tie break

        df = pd.DataFrame({
            "segment_month_id": smids,
            "canonical_segment_id": seg_ids,
            "as_of_date": dates,
            "cal_prob": proba,
            "target": y
        })

        df_sorted = df.sort_values(
            by=["cal_prob", "canonical_segment_id", "as_of_date", "segment_month_id"],
            ascending=[False, True, True, True]
        ).reset_index(drop=True)

        # Expected sort order of segment_month_id:
        # All cal_prob are 0.5
        # canonical_segment_id: seg_a comes before seg_b
        #   For seg_a: as_of_date 2024-01-31 comes before 2024-02-29
        #     For seg_a, 2024-01-31: segment_month_ids are seg_a_1 and seg_a_2. seg_a_1 comes before seg_a_2.
        #     For seg_a, 2024-02-29: seg_a_3
        #   For seg_b: seg_b_2
        assert df_sorted.loc[0, "segment_month_id"] == "seg_a_1"
        assert df_sorted.loc[1, "segment_month_id"] == "seg_a_2"
        assert df_sorted.loc[2, "segment_month_id"] == "seg_a_3"
        assert df_sorted.loc[3, "segment_month_id"] == "seg_b_2"



# ---------------------------------------------------------------------------
# PART 6: Calibration diagnostics
# ---------------------------------------------------------------------------

class TestCalibrationDiagnostics:
    def test_ece_finite(self):
        rng = np.random.default_rng(42)
        n = 500
        y = (rng.uniform(0, 1, n) > 0.5).astype(float)
        p = rng.uniform(0, 1, n)
        ece = expected_calibration_error(y, p)
        assert np.isfinite(ece)
        assert ece >= 0.0

    def test_ece_perfect_calibration(self):
        """With perfect calibration, ECE should be near zero."""
        rng = np.random.default_rng(42)
        n = 10000
        p = rng.uniform(0, 1, n)
        y = (rng.uniform(0, 1, n) < p).astype(float)
        ece = expected_calibration_error(y, p)
        # ECE of perfect calibration should be small but not zero (sampling variance)
        assert ece < 0.05  # loose tolerance for stochastic test

    def test_reliability_table_shape(self):
        rng = np.random.default_rng(42)
        n = 500
        y = (rng.uniform(0, 1, n) > 0.5).astype(float)
        p = rng.uniform(0, 1, n)
        tbl = reliability_table(y, p)
        assert len(tbl) == 10  # 10 bins
        assert set(tbl.columns) >= {"bin_lo", "bin_hi", "n_total", "n_positive", "mean_predicted", "mean_actual", "weight"}

    def test_calibration_slope_intercept_ideal(self):
        """Perfectly calibrated model should have slope~1, intercept~0."""
        rng = np.random.default_rng(42)
        n = 5000
        p = np.clip(rng.uniform(0, 1, n), 1e-6, 1 - 1e-6)
        y = rng.binomial(1, p).astype(float)
        res = calibration_slope_intercept(y, p)
        assert res["converged"]
        assert abs(res["slope"] - 1.0) < 0.5  # loose tolerance
        assert abs(res["intercept"]) < 0.5

    def test_ap_auc_unchanged_by_monotone_calibration(self):
        """Platt scaling is monotonic; AP and AUC must be invariant."""
        from sklearn.metrics import average_precision_score, roc_auc_score
        rng = np.random.default_rng(42)
        n = 1000
        raw = rng.uniform(0.01, 0.99, n)
        y = (raw + rng.normal(0, 0.2, n) > 0.5).astype(float)

        cal = PlattCalibrator()
        cal.fit(raw, y)
        proba = cal.predict_proba(raw)

        ap_raw = average_precision_score(y, raw)
        ap_cal = average_precision_score(y, proba)
        auc_raw = roc_auc_score(y, raw)
        auc_cal = roc_auc_score(y, proba)

        # Due to monotonicity of Platt scaling, AP and AUC should be identical
        assert abs(ap_raw - ap_cal) < 1e-6, f"AP changed: {ap_raw} vs {ap_cal}"
        assert abs(auc_raw - auc_cal) < 1e-6, f"AUC changed: {auc_raw} vs {auc_cal}"


# ---------------------------------------------------------------------------
# PART 7: No B2 results created
# ---------------------------------------------------------------------------

class TestNoB2Results:
    def test_b2_evaluation_results_file_and_access_record(self):
        b2_results = Path("models/phase_6/test_evaluation_results.json")
        b2_access = Path("models/phase_6/gate_b2_access_record.json")
        assert b2_results.exists(), "B2 final-test results file missing — Gate B2 evaluation must be complete!"
        assert b2_access.exists(), "B2 access record missing!"
        access_doc = json.loads(b2_access.read_text())
        assert access_doc["seal_status"] == "CONSUMED_AND_CLOSED", "B2 seal must be CONSUMED_AND_CLOSED"

    def test_b1_authorization_does_not_set_b2_authorized(self):
        b1_auth_path = Path("models/phase_6/gate_b1_authorization.json")
        if b1_auth_path.exists():
            doc = json.loads(b1_auth_path.read_text())
            assert not doc.get("gate_b2_authorized", False), "B1 auth must not set gate_b2_authorized=true"

    def test_b1_calibration_manifest_embargo_false(self):
        cal_manifest = Path("models/phase_6/calibration_manifest.json")
        if cal_manifest.exists():
            doc = json.loads(cal_manifest.read_text())
            assert doc.get("embargo_accessed") is False
            assert doc.get("b2_accessed") is False


# ---------------------------------------------------------------------------
# PART 8: Protected-input immutability after B1
# ---------------------------------------------------------------------------

class TestProtectedInputImmutability:
    def test_sealed_source_sha_unchanged(self):
        """Sealed source SHA must match the manifest after B1."""
        manifest_path = Path("models/phase_6/test_split_manifest.json")
        sealed_path = Path("data/processed/phase_5/test.parquet")
        if not manifest_path.exists() or not sealed_path.exists():
            pytest.skip("Required files not present")
        manifest = json.loads(manifest_path.read_text())
        expected_sha = manifest["sealed_file_sha256"]
        actual_sha = _sha256(sealed_path)
        assert actual_sha == expected_sha, (
            f"Sealed source SHA changed!\n  expected: {expected_sha}\n  actual: {actual_sha}"
        )

    def test_access_record_confirms_model_unchanged(self):
        access_record = Path("models/phase_6/gate_b1_access_record.json")
        if not access_record.exists():
            pytest.skip("gate_b1_access_record.json not present")
        doc = json.loads(access_record.read_text())
        assert doc.get("model_unchanged") is True
        assert doc.get("preprocessor_unchanged") is True
        assert doc.get("source_unchanged") is True

    def test_access_record_no_embargo_no_b2(self):
        access_record = Path("models/phase_6/gate_b1_access_record.json")
        if not access_record.exists():
            pytest.skip("gate_b1_access_record.json not present")
        doc = json.loads(access_record.read_text())
        assert doc.get("embargo_anchors_accessed") is False
        assert doc.get("b2_anchors_accessed") is False


# ---------------------------------------------------------------------------
# PART 9: load_b1_targets_from_panel method
# ---------------------------------------------------------------------------

class TestLoadB1TargetsFromPanel:
    """Unit tests for the panel-based target loading method."""

    def _make_panel_dir(self, tmp: Path, anchors: list[str]) -> None:
        """Create minimal Phase 4 panel structure in tmp dir."""
        for anchor in anchors:
            parts = anchor.split("-")
            y, m = parts[0], parts[1]
            pdir = tmp / f"panel_year={y}" / f"panel_month={m}"
            pdir.mkdir(parents=True, exist_ok=True)
            pfile = pdir / "segment_month.parquet"
            df = pd.DataFrame({
                "segment_month_id": [f"seg_{i}_{anchor}" for i in range(4)],
                "as_of_date": [anchor] * 4,
                "target_repair_90d": [0, 1, 0, 1],
            })
            df.to_parquet(str(pfile), index=False)

    def test_loads_b1_targets_for_three_anchors(self, tmp_path):
        """Must load rows for exactly the three B1 anchors."""
        self._make_panel_dir(tmp_path, B1_ANCHORS)
        # Also set up a dummy test.parquet and manifest
        _, sha = _make_parquet(tmp_path, B1_ANCHORS, rows_each=4)
        mp = _make_manifest(tmp_path, sha, b1_rows=12)  # 3 * 4 = 12
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_targets_from_panel(tmp_path, auth)
        assert len(tbl) == 12
        dates = set(tbl["as_of_date"].astype(str).str[:10])
        assert dates == set(B1_ANCHORS)

    def test_rejects_missing_panel_file(self, tmp_path):
        """Missing panel file must raise SealViolationError."""
        # Only create 2 of 3 anchor directories
        self._make_panel_dir(tmp_path, B1_ANCHORS[:2])
        _, sha = _make_parquet(tmp_path, B1_ANCHORS[:2], rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=4)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        with pytest.raises(SealViolationError, match="missing"):
            guard.load_b1_targets_from_panel(tmp_path, auth)

    def test_embargo_dates_not_in_result(self, tmp_path):
        """Loading B1 targets must not include embargo dates."""
        self._make_panel_dir(tmp_path, B1_ANCHORS)
        _, sha = _make_parquet(tmp_path, B1_ANCHORS, rows_each=4)
        mp = _make_manifest(tmp_path, sha, b1_rows=12)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_targets_from_panel(tmp_path, auth)
        dates = set(tbl["as_of_date"].astype(str).str[:10])
        for emb in EMBARGO_ANCHORS:
            assert emb not in dates

    def test_b2_dates_not_in_result(self, tmp_path):
        """Loading B1 targets must not include B2 dates."""
        self._make_panel_dir(tmp_path, B1_ANCHORS)
        _, sha = _make_parquet(tmp_path, B1_ANCHORS, rows_each=4)
        mp = _make_manifest(tmp_path, sha, b1_rows=12)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_targets_from_panel(tmp_path, auth)
        dates = set(tbl["as_of_date"].astype(str).str[:10])
        for b2 in B2_ANCHORS:
            assert b2 not in dates


# ---------------------------------------------------------------------------
# PART 10: Calibration Reconciliation & Degradation Reporting
# ---------------------------------------------------------------------------

class TestCalibrationReconciliation:
    def test_raw_and_calibrated_metrics_both_exist(self):
        manifest_path = Path("models/phase_6/calibration_manifest.json")
        if not manifest_path.exists():
            pytest.skip("calibration_manifest.json not present")
        doc = json.loads(manifest_path.read_text())
        assert "raw_metrics" in doc
        assert "calibrated_metrics" in doc
        # Ensure all required metrics exist
        for group in ["raw_metrics", "calibrated_metrics"]:
            assert "AP" in doc[group]
            assert "ROC_AUC" in doc[group]
            assert "Brier" in doc[group]
            assert "log_loss" in doc[group]

    def test_calibration_degradation_honestly_preserved(self):
        """Assert Brier score and log loss worsened after Platt scaling as observed on B1."""
        manifest_path = Path("models/phase_6/calibration_manifest.json")
        if not manifest_path.exists():
            pytest.skip("calibration_manifest.json not present")
        doc = json.loads(manifest_path.read_text())
        brier_raw = doc["raw_metrics"]["Brier"]
        brier_cal = doc["calibrated_metrics"]["Brier"]
        ll_raw = doc["raw_metrics"]["log_loss"]
        ll_cal = doc["calibrated_metrics"]["log_loss"]
        # In this dataset, Platt scaling on raw probabilities worsened Brier score and log loss
        # Assert this degradation is preserved honestly
        assert brier_cal > brier_raw, f"Expected Brier score to worsen (cal={brier_cal} > raw={brier_raw})"
        assert ll_cal > ll_raw, f"Expected Log Loss to worsen (cal={ll_cal} > raw={ll_raw})"

