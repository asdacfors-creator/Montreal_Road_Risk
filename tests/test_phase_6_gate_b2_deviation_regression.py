"""Targeted regression tests for Phase 6 Gate B2 seal guard hardening and repeated-access deviation logic.

All tests use synthetic temporary files only and do NOT access real B2 target data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from montreal_road_risk.evaluation.seal_guard import (
    OneTimeEvaluationError,
    TestSealGuard,
    register_b2_access_complete,
    register_b2_access_failure,
    register_b2_access_start,
)


def _make_dummy_manifest(tmp: Path) -> Path:
    m = {
        "sealed_file": str(tmp / "test.parquet"),
        "sealed_file_sha256": "dummy",
        "calibration_anchors": ["2024-01-31"],
        "calibration_expected_rows": 1,
        "embargo_anchors": ["2024-04-30"],
        "embargo_expected_rows": 1,
        "final_test_anchors": ["2024-07-31"],
        "final_test_expected_rows": 1,
        "embargo_targets_accessed": False,
    }
    mp = tmp / "test_split_manifest.json"
    mp.write_text(json.dumps(m))
    return mp


class TestGateB2DeviationRegression:
    def test_crash_only_and_do_not_access_real_b2_after_opened(self, tmp_path):
        """A failure after target opening writes a durable FAILED_AFTER_OPEN record."""
        rec_p = tmp_path / "gate_b2_access_record.json"

        # 1. Start access
        register_b2_access_start(
            access_record_path=rec_p,
            task_id="task-test-fail-1",
            command="python script.py",
        )

        doc = json.loads(rec_p.read_text())
        assert doc["seal_status"] == "OPENED_FOR_EVALUATION"

        # 2. Simulate crash
        register_b2_access_failure(
            access_record_path=rec_p,
            task_id="task-test-fail-1",
            failure_cause="Simulated TypeError in ECE calculation",
            exit_code=1,
        )

        doc_failed = json.loads(rec_p.read_text())
        assert doc_failed["seal_status"] == "FAILED_AFTER_OPEN"
        assert doc_failed["evaluation_status"] == "FAILED_AFTER_OPEN"
        assert len(doc_failed["access_attempts"]) == 1
        assert doc_failed["access_attempts"][0]["status"] == "FAILED_AFTER_OPEN"
        assert "Simulated TypeError" in doc_failed["access_attempts"][0]["failure_cause"]

    def test_second_invocation_blocked_before_target_load(self, tmp_path):
        """Once record is OPENED or FAILED_AFTER_OPEN, second invocation is blocked before target load."""
        rec_p = tmp_path / "gate_b2_access_record.json"
        mp = _make_dummy_manifest(tmp_path)
        guard = TestSealGuard(mp, access_record_path=rec_p)

        # Register failed attempt
        register_b2_access_start(rec_p, task_id="task-1", command="python script.py")
        register_b2_access_failure(rec_p, task_id="task-1", failure_cause="Crash post open")

        # Second invocation attempt must raise OneTimeEvaluationError BEFORE loading targets
        with pytest.raises(OneTimeEvaluationError, match="Repeated execution is blocked"):
            guard.assert_b2_not_run(rec_p)

        # register_b2_access_start must also raise OneTimeEvaluationError
        with pytest.raises(OneTimeEvaluationError, match="Repeated execution is blocked"):
            register_b2_access_start(rec_p, task_id="task-2", command="python script.py")

    def test_append_only_attempt_history(self, tmp_path):
        """Multiple access attempts are appended to access_attempts array and preserved."""
        rec_p = tmp_path / "gate_b2_access_record.json"

        # Record with 2 attempts (Attempt 1: FAILED_AFTER_OPEN, Attempt 2: COMPLETE)
        initial_doc = {
            "schema_version": "1.0",
            "gate": "B2",
            "access_start_utc": "2026-07-21T00:23:57Z",
            "seal_status": "OPENED_FOR_EVALUATION",
            "access_count": 2,
            "result_set_count": 0,
            "access_classification": "B_REPEATED_PROCEDURAL_ACCESS",
            "access_attempts": [
                {
                    "attempt_index": 1,
                    "task_id": "task-12084",
                    "status": "FAILED_AFTER_OPEN",
                    "exit_code": 1,
                    "failure_cause": "TypeError: unexpected n_bins",
                },
                {
                    "attempt_index": 2,
                    "task_id": "task-12097",
                    "status": "OPENED_FOR_EVALUATION",
                    "exit_code": None,
                },
            ],
        }
        rec_p.write_text(json.dumps(initial_doc))

        # Register completion of second attempt
        register_b2_access_complete(
            access_record_path=rec_p,
            task_id="task-12097",
            post_access_fingerprints={"partition1.parquet": "hash1"},
        )

        doc = json.loads(rec_p.read_text())
        assert doc["seal_status"] == "CONSUMED_AND_CLOSED"
        assert doc["result_set_count"] == 1
        assert len(doc["access_attempts"]) == 2
        # Attempt 1 failure evidence is preserved
        assert doc["access_attempts"][0]["task_id"] == "task-12084"
        assert doc["access_attempts"][0]["status"] == "FAILED_AFTER_OPEN"
        # Attempt 2 completion is recorded
        assert doc["access_attempts"][1]["task_id"] == "task-12097"
        assert doc["access_attempts"][1]["status"] == "COMPLETE"

    def test_access_count_reconciliation(self, tmp_path):
        """Verify access_count and result_set_count reconciliation."""
        rec_p = tmp_path / "gate_b2_access_record.json"

        doc_data = {
            "schema_version": "1.0",
            "gate": "B2",
            "access_count": 2,
            "result_set_count": 1,
            "access_classification": "B_REPEATED_PROCEDURAL_ACCESS",
            "seal_status": "CONSUMED_AND_CLOSED",
            "access_attempts": [
                {"attempt_index": 1, "task_id": "task-12084", "status": "FAILED_AFTER_OPEN"},
                {"attempt_index": 2, "task_id": "task-12097", "status": "COMPLETE"},
            ],
        }
        rec_p.write_text(json.dumps(doc_data))

        read_doc = json.loads(rec_p.read_text())
        assert read_doc["access_count"] == len(read_doc["access_attempts"]) == 2
        assert read_doc["result_set_count"] == 1
        assert read_doc["access_classification"] == "B_REPEATED_PROCEDURAL_ACCESS"

    def test_no_overwrite_of_prior_failure_evidence(self, tmp_path):
        """Updating access record does not erase prior attempt failure cause."""
        rec_p = tmp_path / "gate_b2_access_record.json"

        # Initial attempt failure
        register_b2_access_start(rec_p, task_id="task-12084", command="python script.py")
        register_b2_access_failure(rec_p, task_id="task-12084", failure_cause="TypeError on line 238")

        # Read back
        doc1 = json.loads(rec_p.read_text())
        assert doc1["access_attempts"][0]["failure_cause"] == "TypeError on line 238"

        # Attempt 2 start (simulated via append) & completion
        doc1["access_attempts"].append({
            "attempt_index": 2,
            "task_id": "task-12097",
            "status": "OPENED_FOR_EVALUATION",
        })
        rec_p.write_text(json.dumps(doc1))

        register_b2_access_complete(rec_p, task_id="task-12097", post_access_fingerprints={})

        doc2 = json.loads(rec_p.read_text())
        assert len(doc2["access_attempts"]) == 2
        assert doc2["access_attempts"][0]["failure_cause"] == "TypeError on line 238"
        assert doc2["access_attempts"][1]["status"] == "COMPLETE"
        assert doc2["seal_status"] == "CONSUMED_AND_CLOSED"
