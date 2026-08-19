"""Phase 6 seal guard — controls access to sealed test partitions.

The physical file ``data/processed/phase_5/test.parquet`` is never
physically split.  All partitioning is logical, enforced here via
anchor allowlists from ``test_split_manifest.json``.

Gate B1 and Gate B2 each require a separate explicit authorization
manifest.  B1 authorization never implies B2 authorization.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SealViolationError(RuntimeError):
    """Raised when a gate boundary would be violated."""


class OneTimeEvaluationError(RuntimeError):
    """Raised when a one-time evaluation is attempted a second time."""


_GATE_A = "gate_a"
_GATE_B1 = "gate_b1"
_GATE_B2 = "gate_b2"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic write dict to JSON file via temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def register_b2_access_start(
    access_record_path: str | Path,
    task_id: str,
    command: str,
    target_column: str = "target_repair_90d",
    b2_anchors: list[str] | None = None,
    total_rows: int = 527813,
    pre_access_fingerprints: dict[str, str] | None = None,
    authorization_commit: str = "cc803a74659b72ec72828b809a47ef59be4aee0c",
) -> dict[str, Any]:
    """Register start of Gate B2 target decoding atomically.

    Raises OneTimeEvaluationError if access record already exists with status
    OPENED_FOR_EVALUATION, FAILED_AFTER_OPEN, or CONSUMED_AND_CLOSED.
    """
    rec_path = Path(access_record_path)
    now_iso = datetime.now(timezone.utc).isoformat()

    existing_doc: dict[str, Any] | None = None
    if rec_path.exists():
        try:
            existing_doc = json.loads(rec_path.read_text(encoding="utf-8"))
        except Exception:
            existing_doc = None

    if existing_doc:
        seal_status = existing_doc.get("seal_status")
        if seal_status in ["OPENED_FOR_EVALUATION", "FAILED_AFTER_OPEN", "CONSUMED_AND_CLOSED"]:
            raise OneTimeEvaluationError(
                f"Gate B2 target access record shows prior access state '{seal_status}' (access_count={existing_doc.get('access_count', 1)}).\n"
                "Repeated execution is blocked before target loading."
            )

    # Initialize or update record
    attempts = existing_doc.get("access_attempts", []) if existing_doc else []
    new_attempt = {
        "attempt_index": len(attempts) + 1,
        "task_id": task_id,
        "access_start_utc": now_iso,
        "target_load_utc": now_iso,
        "status": "OPENED_FOR_EVALUATION",
        "exit_code": None,
        "results_produced": False,
    }
    attempts.append(new_attempt)

    record_doc = {
        "schema_version": "1.0",
        "gate": "B2",
        "access_start_utc": existing_doc.get("access_start_utc", now_iso) if existing_doc else now_iso,
        "seal_status": "OPENED_FOR_EVALUATION",
        "authorization_commit": authorization_commit,
        "target_column": target_column,
        "b2_anchors": b2_anchors or [],
        "total_rows_decoded": total_rows,
        "access_count": len(attempts),
        "result_set_count": existing_doc.get("result_set_count", 0) if existing_doc else 0,
        "access_classification": existing_doc.get("access_classification", "B_REPEATED_PROCEDURAL_ACCESS") if existing_doc else "B_REPEATED_PROCEDURAL_ACCESS",
        "future_target_access_prohibited": True,
        "access_attempts": attempts,
        "pre_access_fingerprints": pre_access_fingerprints or {},
        "evaluation_status": "IN_PROGRESS",
    }

    _atomic_write_json(rec_path, record_doc)
    return record_doc


def register_b2_access_failure(
    access_record_path: str | Path,
    task_id: str,
    failure_cause: str,
    exit_code: int = 1,
) -> dict[str, Any]:
    """Register failure after target opening atomically without discarding evidence."""
    rec_path = Path(access_record_path)
    assert rec_path.exists(), "Access record must exist to register failure."

    doc = json.loads(rec_path.read_text(encoding="utf-8"))
    doc["seal_status"] = "FAILED_AFTER_OPEN"
    doc["evaluation_status"] = "FAILED_AFTER_OPEN"

    attempts = doc.get("access_attempts", [])
    if attempts:
        attempts[-1]["status"] = "FAILED_AFTER_OPEN"
        attempts[-1]["exit_code"] = exit_code
        attempts[-1]["failure_cause"] = failure_cause
        attempts[-1]["results_produced"] = False
    else:
        attempts.append({
            "attempt_index": 1,
            "task_id": task_id,
            "status": "FAILED_AFTER_OPEN",
            "exit_code": exit_code,
            "failure_cause": failure_cause,
            "results_produced": False,
        })
    doc["access_attempts"] = attempts

    _atomic_write_json(rec_path, doc)
    return doc


def register_b2_access_complete(
    access_record_path: str | Path,
    task_id: str,
    post_access_fingerprints: dict[str, str],
) -> dict[str, Any]:
    """Register completion after target evaluation atomically."""
    rec_path = Path(access_record_path)
    assert rec_path.exists(), "Access record must exist to register completion."

    doc = json.loads(rec_path.read_text(encoding="utf-8"))
    now_iso = datetime.now(timezone.utc).isoformat()

    doc["seal_status"] = "CONSUMED_AND_CLOSED"
    doc["evaluation_status"] = "COMPLETE"
    doc["evaluation_completion_utc"] = now_iso
    doc["result_set_count"] = 1
    doc["post_access_fingerprints"] = post_access_fingerprints

    attempts = doc.get("access_attempts", [])
    if attempts:
        attempts[-1]["status"] = "COMPLETE"
        attempts[-1]["exit_code"] = 0
        attempts[-1]["completion_utc"] = now_iso
        attempts[-1]["results_produced"] = True
    doc["access_attempts"] = attempts

    _atomic_write_json(rec_path, doc)
    return doc


class TestSealGuard:
    """Enforces logical partition access for the sealed test file.

    Parameters
    ----------
    manifest_path:
        Path to ``test_split_manifest.json``.
    results_path:
        Path where ``test_evaluation_results.json`` will be written.
        Used by :meth:`assert_b2_not_run` to enforce one-time evaluation.
    access_record_path:
        Path to ``gate_b2_access_record.json``.
    """

    def __init__(
        self,
        manifest_path: str | Path,
        results_path: str | Path | None = None,
        access_record_path: str | Path | None = None,
    ) -> None:
        self._manifest_path = Path(manifest_path)
        self._results_path = Path(results_path) if results_path else None
        self._access_record_path = Path(access_record_path) if access_record_path else None
        self._manifest: dict[str, Any] = json.loads(
            self._manifest_path.read_text(encoding="utf-8")
        )

    # ------------------------------------------------------------------
    # File integrity
    # ------------------------------------------------------------------

    @staticmethod
    def sha256_file(path: str | Path) -> str:
        """Return the SHA-256 hex digest of a file (canonical for text, raw for binary)."""
        from montreal_road_risk.io.checksums import calculate_canonical_sha256
        return calculate_canonical_sha256(path)

    def verify_sealed_file(self, actual_path: str | Path | None = None) -> str:
        """Assert the sealed file SHA-256 matches the manifest.

        Parameters
        ----------
        actual_path:
            Override the path from the manifest (useful in tests).

        Returns
        -------
        str
            The verified SHA-256 hex digest.

        Raises
        ------
        SealViolationError
            If the digest does not match.
        """
        path = Path(actual_path) if actual_path else Path(self._manifest["sealed_file"])
        actual = self.sha256_file(path)
        stored = self._manifest["sealed_file_sha256"]
        if actual != stored:
            raise SealViolationError(
                f"Sealed file hash mismatch.\n"
                f"  expected : {stored}\n"
                f"  actual   : {actual}\n"
                f"  path     : {path}"
            )
        return actual

    # ------------------------------------------------------------------
    # Authorization checks
    # ------------------------------------------------------------------

    def _require_b1_manifest(self, b1_auth_path: str | Path) -> None:
        """Assert that a Gate B1 authorization manifest exists and is valid."""
        p = Path(b1_auth_path)
        if not p.exists():
            raise SealViolationError(
                f"Gate B1 authorization manifest not found: {p}\n"
                "Gate B1 requires a separate explicit supervisor authorization."
            )
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not doc.get("gate_b1_authorized", False):
            raise SealViolationError(
                "Gate B1 authorization manifest found but gate_b1_authorized=false."
            )

    def _require_b2_manifest(self, b2_auth_path: str | Path) -> None:
        """Assert that a Gate B2 authorization manifest exists and is valid.

        Gate B2 authorization is completely independent of Gate B1.
        """
        p = Path(b2_auth_path)
        if not p.exists():
            raise SealViolationError(
                f"Gate B2 authorization manifest not found: {p}\n"
                "Gate B2 requires a DIFFERENT explicit supervisor authorization.\n"
                "Gate B1 authorization never implies Gate B2."
            )
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not doc.get("gate_b2_authorized", False):
            raise SealViolationError(
                "Gate B2 authorization manifest found but gate_b2_authorized=false."
            )
        # Explicitly check that it is not the same token as B1
        if doc.get("gate_b1_authorized", False) and not doc.get("gate_b2_authorized", False):
            raise SealViolationError(
                "Gate B1 authorization token cannot be used for Gate B2."
            )

    def assert_b2_not_run(self, access_record_path: str | Path | None = None) -> None:
        """Assert that Gate B2 target access has not already occurred."""
        rec_p = Path(access_record_path) if access_record_path else self._access_record_path

        if self._results_path and self._results_path.exists():
            raise OneTimeEvaluationError(
                f"test_evaluation_results.json already exists: {self._results_path}\n"
                "Gate B2 evaluation is complete and closed."
            )

        if rec_p and rec_p.exists():
            doc = json.loads(rec_p.read_text(encoding="utf-8"))
            seal_status = doc.get("seal_status")
            access_cnt = doc.get("access_count", 0)
            if seal_status in ["OPENED_FOR_EVALUATION", "FAILED_AFTER_OPEN", "CONSUMED_AND_CLOSED"] or access_cnt > 0:
                raise OneTimeEvaluationError(
                    f"Gate B2 access record found at {rec_p} with seal_status='{seal_status}' (access_count={access_cnt}).\n"
                    "Repeated execution is blocked before target loading."
                )

    def assert_embargo_not_accessed(self) -> None:
        """Assert that embargo targets remain unaccessed (manifest check)."""
        if self._manifest.get("embargo_targets_accessed", False):
            raise SealViolationError("Embargo targets have been accessed — this is prohibited.")

    # ------------------------------------------------------------------
    # Partition access (Gate B1)
    # ------------------------------------------------------------------

    def load_b1_only(
        self,
        parquet_path: str | Path,
        b1_auth_path: str | Path,
        columns: list[str] | None = None,
    ) -> Any:
        """Load only B1 calibration-anchor rows from the sealed file."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        self._require_b1_manifest(b1_auth_path)
        self.verify_sealed_file(parquet_path)
        self.assert_embargo_not_accessed()

        cal_anchors = set(self._manifest["calibration_anchors"])
        embargo_anchors = set(self._manifest["embargo_anchors"])
        b2_anchors = set(self._manifest["final_test_anchors"])

        tbl = pq.read_table(parquet_path, columns=columns)
        dates = tbl.column("as_of_date").to_pylist()
        dates_str = [str(d)[:10] for d in dates]

        mask = [d in cal_anchors for d in dates_str]
        b1_table = tbl.filter(pa.array(mask))

        result_dates = {str(d)[:10] for d in b1_table.column("as_of_date").to_pylist()}
        bad_embargo = result_dates & embargo_anchors
        bad_b2 = result_dates & b2_anchors
        if bad_embargo:
            raise SealViolationError(f"Embargo rows leaked into B1 result: {bad_embargo}")
        if bad_b2:
            raise SealViolationError(f"Final-test rows leaked into B1 result: {bad_b2}")

        expected = self._manifest["calibration_expected_rows"]
        actual = len(b1_table)
        if actual != expected:
            raise SealViolationError(f"B1 row count mismatch: expected {expected}, got {actual}")
        return b1_table

    def load_b1_targets_from_panel(
        self,
        panel_base_dir: str | Path,
        b1_auth_path: str | Path,
        target_col: str = "target_repair_90d",
    ) -> Any:
        """Load B1 target labels from Phase 4 panel partitions."""
        import pandas as pd

        self._require_b1_manifest(b1_auth_path)
        self.assert_embargo_not_accessed()

        cal_anchors = self._manifest["calibration_anchors"]
        embargo_anchors = set(self._manifest["embargo_anchors"])
        b2_anchors = set(self._manifest["final_test_anchors"])

        panel_base = Path(panel_base_dir)
        frames = []
        for anchor in cal_anchors:
            parts = anchor.split("-")
            y, m = parts[0], parts[1]
            ppath = panel_base / f"panel_year={y}" / f"panel_month={m}" / "segment_month.parquet"
            if not ppath.exists():
                raise SealViolationError(f"Phase 4 panel file missing for B1 anchor {anchor}: {ppath}")
            df = pd.read_parquet(
                str(ppath),
                columns=["segment_month_id", "as_of_date", target_col],
            )
            frames.append(df)

        targets_df = pd.concat(frames, ignore_index=True)
        targets_df["_date_str"] = targets_df["as_of_date"].astype(str).str[:10]

        all_dates = set(targets_df["_date_str"])
        bad_embargo = all_dates & embargo_anchors
        bad_b2 = all_dates & b2_anchors
        if bad_embargo:
            raise SealViolationError(f"Embargo anchor dates in B1 target load: {bad_embargo}")
        if bad_b2:
            raise SealViolationError(f"B2 anchor dates in B1 target load: {bad_b2}")

        targets_df = targets_df.drop(columns=["_date_str"])

        expected = self._manifest["calibration_expected_rows"]
        actual = len(targets_df)
        if actual != expected:
            raise SealViolationError(f"B1 target row count mismatch: expected {expected}, got {actual}")
        return targets_df

    # ------------------------------------------------------------------
    # Partition access (Gate B2)
    # ------------------------------------------------------------------

    def load_b2_only(
        self,
        parquet_path: str | Path,
        b2_auth_path: str | Path,
        calibration_manifest_path: str | Path,
        columns: list[str] | None = None,
        access_record_path: str | Path | None = None,
    ) -> Any:
        """Load only B2 final-test-anchor rows from the sealed file."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        self._require_b2_manifest(b2_auth_path)
        self.assert_b2_not_run(access_record_path)
        self.verify_sealed_file(parquet_path)
        self.assert_embargo_not_accessed()

        if not Path(calibration_manifest_path).exists():
            raise SealViolationError(
                f"calibration_manifest.json not found: {calibration_manifest_path}\n"
                "Calibration must be completed (Gate B1) before Gate B2."
            )

        cal_anchors = set(self._manifest["calibration_anchors"])
        embargo_anchors = set(self._manifest["embargo_anchors"])
        b2_anchors = set(self._manifest["final_test_anchors"])

        tbl = pq.read_table(parquet_path, columns=columns)
        dates = tbl.column("as_of_date").to_pylist()
        dates_str = [str(d)[:10] for d in dates]

        mask = [d in b2_anchors for d in dates_str]
        b2_table = tbl.filter(pa.array(mask))

        result_dates = {str(d)[:10] for d in b2_table.column("as_of_date").to_pylist()}
        bad_cal = result_dates & cal_anchors
        bad_emb = result_dates & embargo_anchors
        if bad_cal:
            raise SealViolationError(f"Calibration rows leaked into B2 result: {bad_cal}")
        if bad_emb:
            raise SealViolationError(f"Embargo rows leaked into B2 result: {bad_emb}")

        expected = self._manifest["final_test_expected_rows"]
        actual = len(b2_table)
        if actual != expected:
            raise SealViolationError(f"B2 row count mismatch: expected {expected}, got {actual}")
        return b2_table

    def verify_no_contaminated_paths(self, paths: list[str] | dict[str, str]) -> None:
        """Fail if any path references contaminated/un-remediated sources."""
        p_list = paths.values() if isinstance(paths, dict) else paths
        for path in p_list:
            p_str = str(path).replace("\\", "/")
            if "data/processed/phase_5/test.parquet" in p_str:
                raise ValueError(f"Contaminated path forbidden: {path}")
            if "data/processed/phase_4/" in p_str or p_str.endswith("data/processed/phase_4"):
                raise ValueError(f"Contaminated path forbidden: {path}")
            if "full_training_external_memory_candidate" in p_str:
                raise ValueError(f"Contaminated model forbidden: {path}")
            if "quarantine" in p_str:
                raise ValueError(f"Quarantined artifact forbidden: {path}")

    def verify_features_allowlist(self, df_cols: list[str] | set[str], expected_features: list[str]) -> None:
        """Fail if features differ in names, ordering, or contains targets."""
        for col in df_cols:
            if any(t in col.lower() for t in ["target", "eligible"]) and col != "target_repair_90d":
                raise ValueError(f"Target column leaked into feature matrix: {col}")

        df_feats = [c for c in df_cols if c not in ["segment_month_id", "canonical_segment_id", "as_of_date", "date_str"]]
        if len(df_feats) != len(expected_features):
            raise ValueError(f"Feature count mismatch: expected {len(expected_features)}, got {len(df_feats)}")
        for idx, (f_act, f_exp) in enumerate(zip(df_feats, expected_features, strict=False)):
            if f_act != f_exp:
                raise ValueError(f"Feature mismatch at index {idx}: expected {f_exp}, got {f_act}")

    def verify_unrestricted_read_forbidden(self, columns: list[str] | None) -> None:
        """Fail if columns projection list is empty or None (unrestricted read)."""
        if columns is None or len(columns) == 0:
            raise ValueError("Unrestricted pd.read_parquet is forbidden on protected files.")
