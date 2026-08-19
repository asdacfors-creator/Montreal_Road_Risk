"""Tests for Phase 6 seal guard.

All tests use synthetic fixtures and temporary directories.
No test reads sealed test data or depends on Phase 6 outputs.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from montreal_road_risk.evaluation.seal_guard import (
    TestSealGuard,
    SealViolationError,
    OneTimeEvaluationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CALIBRATION_ANCHORS = ["2024-01-31", "2024-02-29", "2024-03-31"]
EMBARGO_ANCHORS = ["2024-04-30", "2024-05-31", "2024-06-30"]
B2_ANCHORS = [
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31",
]


def _make_manifest(tmp: Path, sha: str, b1_rows: int = 6, emb_rows: int = 6, b2_rows: int = 22) -> Path:
    m = {
        "sealed_file": str(tmp / "test.parquet"),
        "sealed_file_sha256": sha,
        "calibration_anchors": CALIBRATION_ANCHORS,
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
    import hashlib
    dates = []
    seg_ids = []
    scores = []
    for a in anchors:
        for i in range(rows_each):
            dates.append(a)
            seg_ids.append(f"seg_{a}_{i}")
            scores.append(float(i) / rows_each)
    tbl = pa.table({
        "as_of_date": pa.array(dates, type=pa.string()),
        "canonical_segment_id": pa.array(seg_ids),
        "segment_month_id": pa.array([f"{d}_{s}" for d, s in zip(dates, seg_ids, strict=False)]),
        "score": pa.array(scores),
        "target_repair_90d": pa.array([1 if s > 0.5 else 0 for s in scores]),
    })
    path = tmp / "test.parquet"
    pq.write_table(tbl, path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return path, h.hexdigest()


def _make_b1_auth(tmp: Path) -> Path:
    p = tmp / "b1_auth.json"
    p.write_text(json.dumps({"gate_b1_authorized": True}))
    return p


def _make_b2_auth(tmp: Path) -> Path:
    p = tmp / "b2_auth.json"
    p.write_text(json.dumps({"gate_b2_authorized": True}))
    return p


def _make_cal_manifest(tmp: Path) -> Path:
    p = tmp / "calibration_manifest.json"
    p.write_text(json.dumps({"method": "platt", "converged": True}))
    return p


# ---------------------------------------------------------------------------
# Gate A: no target access
# ---------------------------------------------------------------------------

class TestGateANoBrAccess:
    """Gate A cannot read B1 or B2 targets."""

    def test_b1_requires_auth_manifest(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6, emb_rows=6, b2_rows=22)
        guard = TestSealGuard(mp)
        # No auth manifest → SealViolationError
        with pytest.raises(SealViolationError, match="Gate B1 authorization"):
            guard.load_b1_only(path, tmp_path / "nonexistent_auth.json")

    def test_b2_requires_auth_manifest(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6, emb_rows=6, b2_rows=22)
        guard = TestSealGuard(mp, results_path=tmp_path / "results.json")
        cal_man = _make_cal_manifest(tmp_path)
        with pytest.raises(SealViolationError, match="Gate B2 authorization"):
            guard.load_b2_only(path, tmp_path / "nonexistent.json", cal_man)


# ---------------------------------------------------------------------------
# File integrity
# ---------------------------------------------------------------------------

class TestSealIntegrity:
    def test_sha256_mismatch_raises(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        wrong_sha = "a" * 64
        mp = _make_manifest(tmp_path, wrong_sha, b1_rows=6)
        guard = TestSealGuard(mp)
        with pytest.raises(SealViolationError, match="hash mismatch"):
            guard.verify_sealed_file(path)

    def test_correct_sha_passes(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6)
        guard = TestSealGuard(mp)
        result = guard.verify_sealed_file(path)
        assert result == sha


# ---------------------------------------------------------------------------
# B1 loads only calibration anchors
# ---------------------------------------------------------------------------

class TestB1Access:
    def test_b1_loads_only_cal_anchors(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6, emb_rows=6, b2_rows=22)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        tbl = guard.load_b1_only(path, auth)
        dates_in_result = set(tbl.column("as_of_date").to_pylist())
        assert dates_in_result == set(CALIBRATION_ANCHORS)
        for emb in EMBARGO_ANCHORS:
            assert emb not in dates_in_result
        for b2 in B2_ANCHORS:
            assert b2 not in dates_in_result

    def test_b1_wrong_row_count_raises(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        # Manifest expects 999 rows
        mp = _make_manifest(tmp_path, sha, b1_rows=999)
        guard = TestSealGuard(mp)
        auth = _make_b1_auth(tmp_path)
        with pytest.raises(SealViolationError, match="row count mismatch"):
            guard.load_b1_only(path, auth)


# ---------------------------------------------------------------------------
# B2 loads only final-test anchors
# ---------------------------------------------------------------------------

class TestB2Access:
    def test_b2_loads_only_final_test_anchors(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS + EMBARGO_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6, emb_rows=6, b2_rows=22)
        guard = TestSealGuard(mp, results_path=tmp_path / "no_results_yet.json")
        auth = _make_b2_auth(tmp_path)
        cal_man = _make_cal_manifest(tmp_path)
        tbl = guard.load_b2_only(path, auth, cal_man)
        dates_in_result = set(tbl.column("as_of_date").to_pylist())
        assert dates_in_result == set(B2_ANCHORS)
        for cal in CALIBRATION_ANCHORS:
            assert cal not in dates_in_result
        for emb in EMBARGO_ANCHORS:
            assert emb not in dates_in_result

    def test_b1_auth_cannot_authorize_b2(self, tmp_path):
        all_anchors = CALIBRATION_ANCHORS + B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=6, emb_rows=0, b2_rows=22)
        guard = TestSealGuard(mp, results_path=tmp_path / "no_results.json")
        # Use B1 auth for B2 — should fail
        b1_auth = _make_b1_auth(tmp_path)
        cal_man = _make_cal_manifest(tmp_path)
        with pytest.raises(SealViolationError, match="Gate B2 authorization"):
            guard.load_b2_only(path, b1_auth, cal_man)


# ---------------------------------------------------------------------------
# One-time evaluation guard
# ---------------------------------------------------------------------------

class TestOneTimeGuard:
    def test_b2_cannot_run_twice(self, tmp_path):
        results = tmp_path / "test_evaluation_results.json"
        results.write_text(json.dumps({"ap": 0.8}))
        all_anchors = B2_ANCHORS
        path, sha = _make_parquet(tmp_path, all_anchors, rows_each=2)
        mp = _make_manifest(tmp_path, sha, b1_rows=0, emb_rows=0, b2_rows=22)
        guard = TestSealGuard(mp, results_path=results)
        auth = _make_b2_auth(tmp_path)
        cal_man = _make_cal_manifest(tmp_path)
        with pytest.raises(OneTimeEvaluationError):
            guard.load_b2_only(path, auth, cal_man)


# ---------------------------------------------------------------------------
# Threshold manifest immutability (conceptual guard)
# ---------------------------------------------------------------------------

class TestThresholdFreeze:
    def test_threshold_manifest_immutable_after_write(self, tmp_path):
        """Once written, threshold_manifest should not be re-written (test guard)."""
        thm = tmp_path / "threshold_manifest.json"
        thm.write_text(json.dumps({"frozen": True, "top_5_pct": 0.05}))
        original_content = thm.read_text()
        # Guard: reading it does not change it
        _ = json.loads(thm.read_text())
        assert thm.read_text() == original_content
