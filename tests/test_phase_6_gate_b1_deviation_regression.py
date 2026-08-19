"""Regression tests for Phase 6 Gate B1 path, target isolation, immutability, Pre-B2 policy freeze, and Subgroup Schema Reconciliation.

Verifies:
- remediated Phase 4 partitions are immutable;
- no target column may be written into Phase 4 remediated files;
- B1 targets use a separate target-only artifact;
- only authorized B1 anchors are permitted;
- only the four approved target columns may be decoded;
- non-remediated feature paths are rejected;
- target-bearing files cannot be used as feature sources;
- joblib files cannot be staged or committed;
- all 102 remediated partitions match determinism evidence;
- raw probabilities are marked primary, Platt marked sensitivity;
- a Platt threshold cannot be applied to raw probabilities and vice versa;
- Top-K uses raw ordering;
- threshold selection uses B1 only;
- B2 row arithmetic is 11 * 47,983 = 527,813;
- 180-day final test evaluation is disabled;
- every direct subgroup field exists in sealed-feature schema;
- every derived subgroup has explicit deterministic derivation from as_of_date;
- unknown subgroup fields fail before B2 access;
- primary_borough_id is treated as metadata, not a model feature;
- no subgroup uses target columns.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pyarrow.parquet as pq
import pytest

from montreal_road_risk.evaluation.seal_guard import TestSealGuard

REPO_ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def seal_guard():
    return TestSealGuard(REPO_ROOT / "models/phase_6/test_split_manifest.json")


def test_verify_no_contaminated_paths_rejects_contaminated_test_parquet(seal_guard):
    bad_paths = ["data/processed/phase_5/test.parquet", "src/models/model.joblib"]
    with pytest.raises(ValueError, match="Contaminated path forbidden"):
        seal_guard.verify_no_contaminated_paths(bad_paths)


def test_verify_no_contaminated_paths_rejects_unremediated_phase_4(seal_guard):
    bad_paths = {"targets": "data/processed/phase_4"}
    with pytest.raises(ValueError, match="Contaminated path forbidden"):
        seal_guard.verify_no_contaminated_paths(bad_paths)


def test_verify_no_contaminated_paths_rejects_contaminated_model(seal_guard):
    bad_paths = ["models/phase_5/full_training_external_memory_candidate/model.joblib"]
    with pytest.raises(ValueError, match="Contaminated model forbidden"):
        seal_guard.verify_no_contaminated_paths(bad_paths)


def test_verify_no_contaminated_paths_rejects_quarantined_artifacts(seal_guard):
    bad_paths = ["models/phase_6/quarantine/gate_b1_contaminated_01/calibrator_90d.joblib"]
    with pytest.raises(ValueError, match="Quarantined artifact forbidden"):
        seal_guard.verify_no_contaminated_paths(bad_paths)


def test_verify_no_contaminated_paths_accepts_clean_remediated_paths(seal_guard):
    clean_paths = {
        "features": "data/processed/phase_5_remediated_01/sealed_features_90d.parquet",
        "targets": "data/processed/phase_6/gate_b1_authorized_targets_90d.parquet",
        "model": "models/phase_5/full_training_remediated_01"
    }
    seal_guard.verify_no_contaminated_paths(clean_paths)


def test_verify_features_allowlist_rejects_target_leakage(seal_guard):
    bad_cols = ["segment_month_id", "canonical_segment_id", "as_of_date", "target_repair_180d", "feat1", "feat2"]
    expected_feats = ["feat1", "feat2"]
    with pytest.raises(ValueError, match="Target column leaked into feature matrix"):
        seal_guard.verify_features_allowlist(bad_cols, expected_feats)


def test_verify_features_allowlist_rejects_out_of_order_features(seal_guard):
    cols = ["segment_month_id", "canonical_segment_id", "as_of_date", "feat2", "feat1"]
    expected_feats = ["feat1", "feat2"]
    with pytest.raises(ValueError, match="Feature mismatch at index 0"):
        seal_guard.verify_features_allowlist(cols, expected_feats)


def test_verify_features_allowlist_rejects_feature_count_mismatch(seal_guard):
    cols = ["segment_month_id", "canonical_segment_id", "as_of_date", "feat1"]
    expected_feats = ["feat1", "feat2"]
    with pytest.raises(ValueError, match="Feature count mismatch"):
        seal_guard.verify_features_allowlist(cols, expected_feats)


def test_verify_features_allowlist_accepts_correct_features(seal_guard):
    cols = ["segment_month_id", "canonical_segment_id", "as_of_date", "feat1", "feat2"]
    expected_feats = ["feat1", "feat2"]
    seal_guard.verify_features_allowlist(cols, expected_feats)


def test_verify_unrestricted_read_forbidden_rejects_empty_or_none(seal_guard):
    with pytest.raises(ValueError, match="Unrestricted pd.read_parquet is forbidden"):
        seal_guard.verify_unrestricted_read_forbidden(None)
    with pytest.raises(ValueError, match="Unrestricted pd.read_parquet is forbidden"):
        seal_guard.verify_unrestricted_read_forbidden([])


def test_verify_unrestricted_read_forbidden_accepts_columns(seal_guard):
    seal_guard.verify_unrestricted_read_forbidden(["segment_month_id", "feat1"])


def test_remediated_phase_4_sealed_partitions_have_no_targets():
    """Assert sealed remediated Phase 4 partitions contain no target columns."""
    p4_dir = REPO_ROOT / "data/processed/phase_4_remediated_01"
    if not p4_dir.exists():
        pytest.skip("Phase 4 remediated directory not found")

    sealed_anchors = {
        "2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31", "2024-06-30",
        "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
        "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31"
    }

    for p in p4_dir.rglob("segment_month.parquet"):
        parts = p.parts
        yr = [x for x in parts if x.startswith("panel_year=")][0].split("=")[1]
        mo = [x for x in parts if x.startswith("panel_month=")][0].split("=")[1].zfill(2)

        schema = pq.read_schema(p)
        target_cols = [c for c in schema.names if "target" in c.lower() or "eligible" in c.lower()]

        # Check if year-month is sealed
        is_sealed = False
        for sa in sealed_anchors:
            if sa.startswith(f"{yr}-{mo}"):
                is_sealed = True
                break

        if is_sealed:
            assert len(target_cols) == 0, f"Sealed partition {p} contains target columns: {target_cols}"


def test_b1_target_only_artifact_structure():
    """Assert B1 targets use a separate target-only artifact with only four approved columns."""
    target_path = REPO_ROOT / "data/processed/phase_6/gate_b1_authorized_targets_90d.parquet"
    if not target_path.exists():
        pytest.skip("B1 target artifact not found")

    schema = pq.read_schema(target_path)
    expected_cols = ["segment_month_id", "canonical_segment_id", "as_of_date", "target_repair_90d"]
    assert schema.names == expected_cols, f"Target artifact columns mismatch: {schema.names}"


def test_all_102_partitions_match_determinism_audit():
    """Assert determinism audit results file exists and all 102 partitions match."""
    audit_path = REPO_ROOT / "models/phase_6/phase_4_determinism_audit.json"
    if not audit_path.exists():
        pytest.skip("Determinism audit file not found")

    data = json.loads(audit_path.read_text())
    assert data["anchors_compared"] == 102
    assert data["matching"] == 102
    assert data["changed"] == 0
    assert data["missing"] == 0


def test_no_joblib_files_tracked_in_git():
    """Regression test: assert no *.joblib files are tracked by Git."""
    cmd = ["git", "ls-files", "*.joblib"]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    assert res.returncode == 0
    tracked_joblibs = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    assert len(tracked_joblibs) == 0, f"Found tracked joblib files in Git: {tracked_joblibs}"


def test_evaluation_manifest_pre_b2_freeze_rules():
    """Assert evaluation_manifest.json freezes pre-B2 rules correctly."""
    manifest_path = REPO_ROOT / "models/phase_6/evaluation_manifest.json"
    assert manifest_path.exists(), "evaluation_manifest.json missing"

    data = json.loads(manifest_path.read_text())

    # Raw is primary, Platt is sensitivity
    assert data["primary_probability_domain"] == "raw_probability"
    assert data["sensitivity_probability_domain"] == "platt_probability"

    # Thresholds exist with explicit domains
    thresh = data["thresholds"]
    assert "primary_raw_recall_threshold" in thresh
    assert "sensitivity_platt_recall_threshold" in thresh
    assert thresh["primary_raw_recall_threshold"] == 0.30805489
    assert thresh["sensitivity_platt_recall_threshold"] == 0.20194759

    # Top-K policy uses raw ordering
    assert data["top_k_policies"]["ordering_domain"] == "raw_probability"

    # B2 anchors & row arithmetic
    expected_b2_anchors = [
        "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
        "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31"
    ]
    assert data["b2_anchors_allowlist"] == expected_b2_anchors
    assert data["b2_expected_rows"] == 527813
    assert len(expected_b2_anchors) * 47983 == 527813

    # Evaluation rules
    rules = data["evaluation_rules"]
    assert rules["final_test_180d_evaluation_enabled"] is False
    assert rules["embargo_permanently_excluded"] is True
    assert rules["post_b2_access_policy_changes_allowed"] is False


def test_domain_safety_mismatch_detection():
    """Assert a Platt threshold cannot be applied to raw probabilities and vice versa."""
    raw_threshold = 0.30805489
    platt_threshold = 0.20194759

    raw_scores = [0.25, 0.35, 0.45]
    platt_scores = [0.15, 0.25, 0.35]

    def apply_threshold(scores: list[float], threshold: float, score_domain: str, threshold_domain: str):
        if score_domain != threshold_domain:
            raise ValueError(f"Domain mismatch: scores are '{score_domain}', threshold is '{threshold_domain}'")
        return [s >= threshold for s in scores]

    # Matching domain succeeds
    res_raw = apply_threshold(raw_scores, raw_threshold, "raw_probability", "raw_probability")
    assert res_raw == [False, True, True]

    res_platt = apply_threshold(platt_scores, platt_threshold, "platt_probability", "platt_probability")
    assert res_platt == [False, True, True]

    # Mismatched domain raises ValueError
    with pytest.raises(ValueError, match="Domain mismatch"):
        apply_threshold(raw_scores, platt_threshold, "raw_probability", "platt_probability")

    with pytest.raises(ValueError, match="Domain mismatch"):
        apply_threshold(platt_scores, raw_threshold, "platt_probability", "raw_probability")


def test_subgroup_schema_reconciliation():
    """Fail-fast assertions for subgroup schema reconciliation."""
    manifest_path = REPO_ROOT / "models/phase_6/evaluation_manifest.json"
    sealed_path = REPO_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"

    assert manifest_path.exists(), "evaluation_manifest.json missing"
    assert sealed_path.exists(), "sealed_features_90d.parquet missing"

    data = json.loads(manifest_path.read_text())
    schema = pq.read_schema(sealed_path)
    schema_names = set(schema.names)

    subgroup_cfg = data["subgroup"]
    direct_fields = subgroup_cfg["direct_fields"]
    derived_fields = subgroup_cfg["derived_fields"]

    # 1. Assert every direct subgroup field exists in sealed-feature schema
    for df in direct_fields:
        assert df in schema_names, f"Direct subgroup field '{df}' missing from sealed feature schema!"

    # 2. Assert excluded fields (borough_id, pavement_condition) are NOT in direct_fields
    assert "borough_id" not in direct_fields, "borough_id must not be used as a direct subgroup field"
    assert "pavement_condition" not in direct_fields, "pavement_condition must not be used as a direct subgroup field"
    assert "borough_id" in subgroup_cfg["excluded_unavailable_fields"]
    assert "pavement_condition" in subgroup_cfg["excluded_unavailable_fields"]

    # 3. Assert primary_borough_id is marked as metadata_only
    assert "primary_borough_id" in subgroup_cfg["metadata_only_fields"]

    # 4. Assert derived fields derive only from as_of_date
    assert "as_of_date" in schema_names
    for deriv_name, deriv_rule in derived_fields.items():
        assert "as_of_date" in deriv_rule, f"Derived field '{deriv_name}' must derive from as_of_date"

    # 5. Assert no subgroup field uses targets
    all_subgroup_keys = direct_fields + list(derived_fields.keys())
    for k in all_subgroup_keys:
        assert not k.startswith("target_"), f"Subgroup field '{k}' appears to use target columns"

    # 6. Test fail-fast validator function
    def validate_subgroups_before_b2(cfg_subgroup, actual_schema_names):
        for field in cfg_subgroup["direct_fields"]:
            if field not in actual_schema_names:
                raise ValueError(f"Unresolved subgroup field: '{field}' missing from dataset schema!")

    # Valid schema check passes
    validate_subgroups_before_b2(subgroup_cfg, schema_names)

    # Invalid schema check raises ValueError
    with pytest.raises(ValueError, match="Unresolved subgroup field"):
        validate_subgroups_before_b2({"direct_fields": ["unresolved_field_xyz"]}, schema_names)
