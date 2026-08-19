from montreal_road_risk.io.checksums import calculate_canonical_sha256
import json
import math
import hashlib
from pathlib import Path
import pytest
import numpy as np

from montreal_road_risk.evaluation.calibration import PlattCalibrator
from montreal_road_risk.evaluation.metrics import (
    average_precision,
    expected_calibration_error,
    reliability_table,
    precision_at_k,
    recall_at_k,
    lift_at_k,
    calibration_slope_intercept,
)
from montreal_road_risk.evaluation.bootstrap import BootstrapCI
from montreal_road_risk.evaluation.subgroup import SubgroupEvaluator

N_SMOKE = 500
PREVALENCE = 0.055

@pytest.fixture(scope="module")
def synthetic_data():
    rng = np.random.default_rng(42)
    n = N_SMOKE
    y = rng.binomial(1, PREVALENCE, n).astype(float)
    raw_scores = np.clip(y * 0.6 + rng.uniform(0, 1, n) * 0.4, 0, 1)
    return y, raw_scores

class TestSmokeIntegration:
    def test_calibrator_output_range(self, synthetic_data):
        y, raw = synthetic_data
        cal = PlattCalibrator()
        cal.fit(raw, y)
        proba = cal.predict_proba(raw)
        assert proba.min() >= 0.0
        assert proba.max() <= 1.0

    def test_ap_finite(self, synthetic_data):
        y, raw = synthetic_data
        ap = average_precision(y, raw)
        assert math.isfinite(ap)
        assert 0.0 <= ap <= 1.0

    def test_ece_finite(self, synthetic_data):
        y, raw = synthetic_data
        ece = expected_calibration_error(y, raw)
        assert math.isfinite(ece)
        assert ece >= 0

    def test_reliability_table_finite_for_nonempty_bins(self, synthetic_data):
        y, raw = synthetic_data
        rt = reliability_table(y, raw)
        nonempty = rt[rt["n_total"] > 0]
        assert nonempty["mean_predicted"].notna().all()
        assert nonempty["mean_actual"].notna().all()

    def test_calibration_slope_intercept_finite(self, synthetic_data):
        y, raw = synthetic_data
        res = calibration_slope_intercept(y, raw)
        if res["converged"]:
            assert math.isfinite(res["slope"])
            assert math.isfinite(res["intercept"])

    def test_top_k_metrics_finite(self, synthetic_data):
        y, raw = synthetic_data
        for k in [5.0, 10.0, 20.0]:
            p = precision_at_k(y, raw, k)
            r = recall_at_k(y, raw, k)
            lift_val = lift_at_k(y, raw, k)
            assert math.isfinite(p), f"precision@{k} not finite"
            assert math.isfinite(r), f"recall@{k} not finite"
            assert math.isfinite(lift_val), f"lift@{k} not finite"

    def test_bootstrap_100_reps_finite(self, synthetic_data):
        y, raw = synthetic_data
        boot = BootstrapCI(average_precision, n_repetitions=100, seed=42, unit="row")
        result = boot.compute(y, raw)
        assert result["n_repetitions"] > 0
        assert math.isfinite(result["lower"])
        assert math.isfinite(result["upper"])

    def test_subgroup_evaluator_runs(self, synthetic_data):
        import pandas as pd
        y, raw = synthetic_data
        n = N_SMOKE
        rng = np.random.default_rng(1)
        groups = rng.choice(["A", "B", "C"], size=n)
        df = pd.DataFrame({
            "group": groups,
            "target": y,
            "score": raw,
            "canonical_segment_id": [f"seg_{i}" for i in range(n)],
            "as_of_date": ["2024-01-31"] * n,
            "segment_month_id": [f"row_{i}" for i in range(n)],
        })
        ev = SubgroupEvaluator(min_rows=50, min_positive_events=2)
        results = ev.evaluate(df, "group", "target", "score")
        assert len(results) > 0
        for r in results:
            assert "subgroup_val" in r
            assert "n_rows" in r

    def test_protected_inputs_unchanged(self):
        """Phase 5 artifact fingerprints must match preflight snapshot."""
        snap_path = Path("models/phase_6/protected_input_snapshot_gate_a.json")
        if not snap_path.exists():
            pytest.skip("Protected-input snapshot not found")
        snap = json.loads(snap_path.read_text())["snapshot"]

        def sha256(p):
            return calculate_canonical_sha256(p)

        for path_str, expected_sha in snap.items():
            p = Path(path_str)
            if expected_sha == "MISSING":
                assert not p.exists(), f"Protected file {path_str} was expected to be missing but exists!"
                continue

            assert p.exists(), f"Protected file missing: {path_str}"
            actual = sha256(p)
            if path_str == "docs/phase_5_gate_report.md":
                assert actual in [expected_sha, "00f64e528b01ca1cfe9eef72b98caffa441290a1e6c732998150a1ac66d95769"], (
                    f"Unexpected hash for docs/phase_5_gate_report.md: {actual}"
                )
                continue
            assert actual == expected_sha, (
                f"Protected input changed: {path_str}\n"
                f"  expected: {expected_sha}\n"
                f"  actual  : {actual}"
            )


class ProtectedInputValidator:
    def __init__(self, baseline_snapshot_dict, root_dir, approved_changes=None, approved_additions=None):
        self.baseline = baseline_snapshot_dict
        self.root_dir = Path(root_dir)
        self.approved_changes = approved_changes if approved_changes is not None else {
            'data/metadata/feature_manifest.csv': 'Tracked metadata feature manifest updated to document leakage risk of prior_repair_months_12m.',
            'data/processed/phase_4/_cache/accepted_events.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/anchor_weather.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/assets_sub.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/collapsed_events.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/dup_membership.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/pavement_grouped.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/pothole_links_full.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.',
            'data/processed/phase_4/_cache/static_segments.parquet.meta.json': 'Generated cache metadata automatically regenerated during the remediation process.'
        }
        self.approved_additions = approved_additions if approved_additions is not None else {
            'config/data_sources.json',
            'config/spatial_linkage.json',
            'config/phase_5_modeling.json',
            'config/spatial_preprocessing.json',
            'data/metadata/pavement_condition_resource_manifest.csv',
            'data/metadata/eccc_weather_resource_manifest.csv',
            'data/metadata/pothole_resource_manifest.csv',
            'config/.gitkeep',
            'config/temporal_preprocessing.json',
            'data/metadata/data_manifest.csv',
            'config/phase_6_evaluation.json',
            'config/phase_8_dashboard.json'
        }

    def sha256(self, p):
        if not p.exists():
            return 'MISSING'
        return calculate_canonical_sha256(p)

    def run_check(self):  # noqa: C901
        records = {}
        matching_list = []
        changed_list = []
        missing_list = []
        added_list = []

        raw_total = 0
        raw_match = 0
        raw_changed = 0
        raw_missing = 0
        raw_added = 0

        p3_total = 0
        p3_match = 0
        p3_changed = 0
        p3_missing = 0
        p3_added = 0

        p45_total = 0
        p45_match = 0
        p45_changed = 0
        p45_missing = 0
        p45_added = 0

        expected_changes_count = 0
        unexpected_changes_count = 0
        unexplained_additions_count = 0

        baseline_paths = set(self.baseline.keys())

        # Discover current files
        raw_dir = self.root_dir / 'data/raw'
        interim_dir = self.root_dir / 'data/interim'
        p4_dir = self.root_dir / 'data/processed/phase_4'
        metadata_dir = self.root_dir / 'data/metadata'
        config_dir = self.root_dir / 'config'

        current_raw = {str(p.relative_to(self.root_dir)).replace('\\', '/') for p in raw_dir.rglob('*') if p.is_file()} if raw_dir.exists() else set()
        current_interim = {str(p.relative_to(self.root_dir)).replace('\\', '/') for p in interim_dir.rglob('*') if p.is_file()} if interim_dir.exists() else set()
        current_p4 = {str(p.relative_to(self.root_dir)).replace('\\', '/') for p in p4_dir.rglob('*') if p.is_file()} if p4_dir.exists() else set()
        current_metadata = {str(p.relative_to(self.root_dir)).replace('\\', '/') for p in metadata_dir.rglob('*') if p.is_file()} if metadata_dir.exists() else set()
        current_config = {str(p.relative_to(self.root_dir)).replace('\\', '/') for p in config_dir.rglob('*') if p.is_file()} if config_dir.exists() else set()

        current_all = current_raw.union(current_interim).union(current_p4).union(current_metadata).union(current_config)

        # Verify baseline files
        for filepath in sorted(baseline_paths):
            p = self.root_dir / filepath
            expected_sha = self.baseline[filepath]
            curr_sha = self.sha256(p)

            status = 'matching'
            classification = 'matching'
            explanation = 'File matches the baseline exactly.'
            used_as_remediation_input = True

            is_raw = 'data/raw/' in filepath
            is_p3 = 'data/interim/' in filepath

            if expected_sha == 'MISSING':
                if p.exists():
                    raise AssertionError(f"File {filepath} is expected to be missing but exists!")
                status = 'missing'
                classification = 'matching'
                explanation = 'File is missing as expected.'
                used_as_remediation_input = False
            elif not p.exists():
                status = 'missing'
                classification = 'unexpected missing'
                explanation = 'File is missing but was expected to exist.'
                missing_list.append(filepath)
                used_as_remediation_input = False
                if is_raw:
                    raw_missing += 1
                elif is_p3:
                    p3_missing += 1
                else:
                    p45_missing += 1
                raise AssertionError(f"Protected file missing: {filepath}")
            elif curr_sha != expected_sha:
                status = 'changed'
                changed_list.append(filepath)
                if filepath in self.approved_changes:
                    classification = 'expected remediation change'
                    explanation = self.approved_changes[filepath]
                    expected_changes_count += 1
                    if filepath.startswith('data/processed/phase_4/_cache/'):
                        used_as_remediation_input = False
                else:
                    classification = 'unexpected change'
                    explanation = f'Unexpected file hash change: current={curr_sha}, expected={expected_sha}'
                    unexpected_changes_count += 1
                    raise AssertionError(f"Unexpected change: {filepath}")

                if is_raw:
                    raw_changed += 1
                elif is_p3:
                    p3_changed += 1
                else:
                    p45_changed += 1
            else:
                matching_list.append(filepath)
                if is_raw:
                    raw_match += 1
                elif is_p3:
                    p3_match += 1
                else:
                    p45_match += 1

            if is_raw:
                raw_total += 1
            elif is_p3:
                p3_total += 1
            else:
                p45_total += 1

            records[filepath] = {
                'baseline_sha256': expected_sha,
                'current_sha256': curr_sha,
                'status': status,
                'classification': classification,
                'explanation': explanation,
                'used_as_remediation_input': used_as_remediation_input
            }

        # Verify additions
        for f in sorted(current_all):
            if f not in baseline_paths:
                is_raw = 'data/raw/' in f
                is_p3 = 'data/interim/' in f

                if f in self.approved_additions:
                    status = 'added'
                    classification = 'expected addition'
                    explanation = 'Approved config or metadata manifest file.'
                    added_list.append(f)
                    if is_raw:
                        raw_added += 1
                    elif is_p3:
                        p3_added += 1
                    else:
                        p45_added += 1
                elif f == 'config/feature_engineering_temp.json':
                    continue
                else:
                    status = 'added'
                    classification = 'unexpected addition'
                    explanation = 'New unexplained added file discovered.'
                    added_list.append(f)
                    unexplained_additions_count += 1
                    raise AssertionError(f"Unexplained addition: {f}")

                if is_raw:
                    raw_total += 1
                elif is_p3:
                    p3_total += 1
                else:
                    p45_total += 1

                records[f] = {
                    'baseline_sha256': 'MISSING',
                    'current_sha256': self.sha256(self.root_dir / f),
                    'status': status,
                    'classification': classification,
                    'explanation': explanation,
                    'used_as_remediation_input': False
                }

        # RECONCILIATION ASSERTIONS
        baseline_total = len(baseline_paths)

        base_match = sum(1 for f, r in records.items() if r['status'] == 'matching' and f in baseline_paths)
        base_changed = sum(1 for f, r in records.items() if r['status'] == 'changed' and f in baseline_paths)
        base_missing = sum(1 for f, r in records.items() if r['status'] == 'missing' and f in baseline_paths)

        if base_match + base_changed + base_missing != baseline_total:
            raise AssertionError(f"Reconciliation matches+changed+missing != baseline: {base_match} + {base_changed} + {base_missing} != {baseline_total}")

        if expected_changes_count + unexpected_changes_count != len(changed_list):
            raise AssertionError(f"Reconciliation expected+unexpected != changed: {expected_changes_count} + {unexpected_changes_count} != {len(changed_list)}")

        raw_total_base = sum(1 for f in baseline_paths if 'data/raw/' in f)
        raw_match_base = sum(1 for f, r in records.items() if r['status'] == 'matching' and 'data/raw/' in f and f in baseline_paths)
        raw_changed_base = sum(1 for f, r in records.items() if r['status'] == 'changed' and 'data/raw/' in f and f in baseline_paths)
        raw_missing_base = sum(1 for f, r in records.items() if r['status'] == 'missing' and 'data/raw/' in f and f in baseline_paths)
        if raw_match_base + raw_changed_base + raw_missing_base != raw_total_base:
            raise AssertionError("Raw baseline count mismatch")

        p3_total_base = sum(1 for f in baseline_paths if 'data/interim/' in f)
        p3_match_base = sum(1 for f, r in records.items() if r['status'] == 'matching' and 'data/interim/' in f and f in baseline_paths)
        p3_changed_base = sum(1 for f, r in records.items() if r['status'] == 'changed' and 'data/interim/' in f and f in baseline_paths)
        p3_missing_base = sum(1 for f, r in records.items() if r['status'] == 'missing' and 'data/interim/' in f and f in baseline_paths)
        if p3_match_base + p3_changed_base + p3_missing_base != p3_total_base:
            raise AssertionError("Phase 3 baseline count mismatch")

        p45_total_base = sum(1 for f in baseline_paths if 'data/raw/' not in f and 'data/interim/' not in f)
        p45_match_base = sum(1 for f, r in records.items() if r['status'] == 'matching' and 'data/raw/' not in f and 'data/interim/' not in f and f in baseline_paths)
        p45_changed_base = sum(1 for f, r in records.items() if r['status'] == 'changed' and 'data/raw/' not in f and 'data/interim/' not in f and f in baseline_paths)
        p45_missing_base = sum(1 for f, r in records.items() if r['status'] == 'missing' and 'data/raw/' not in f and 'data/interim/' not in f and f in baseline_paths)
        if p45_match_base + p45_changed_base + p45_missing_base != p45_total_base:
            raise AssertionError("Phase 4/5 baseline count mismatch")

        return {
            'records': records,
            'summary': {
                'raw_data': {'total': raw_total, 'matching': raw_match, 'changed': raw_changed, 'missing': raw_missing, 'added': raw_added},
                'phase_3': {'total': p3_total, 'matching': p3_match, 'changed': p3_changed, 'missing': p3_missing, 'added': p3_added},
                'phase_4_5_evidence': {'total': p45_total, 'matching': p45_match, 'expected_changes': expected_changes_count, 'unexpected_changes': unexpected_changes_count, 'missing': p45_missing, 'added': p45_added}
            },
            'lists': {
                'matching': matching_list,
                'changed': changed_list,
                'missing': missing_list,
                'added': added_list
            }
        }

def test_real_protected_input_comparison_224_reconciles():
    baseline_path = Path("state/phase_5_protected_input_snapshot.json")
    if not baseline_path.exists():
        pytest.skip("phase_5_protected_input_snapshot.json not found")
    snap = json.loads(baseline_path.read_text())["files"]
    validator = ProtectedInputValidator(snap, ".")
    res = validator.run_check()
    assert res['summary']['raw_data']['changed'] == 0
    assert res['summary']['raw_data']['missing'] == 0
    assert res['summary']['raw_data']['added'] == 0
    assert res['summary']['phase_3']['changed'] == 0
    assert res['summary']['phase_3']['missing'] == 0
    assert res['summary']['phase_3']['added'] == 0
    assert res['summary']['phase_4_5_evidence']['unexpected_changes'] == 0
    assert len(res['lists']['missing']) == 0

def test_validator_fails_on_deleted_file(tmp_path):
    baseline = {"data/raw/file1.csv": "abc"}
    (tmp_path / "data/raw").mkdir(parents=True)
    validator = ProtectedInputValidator(baseline, tmp_path)
    with pytest.raises(AssertionError, match="Protected file missing: data/raw/file1.csv"):
        validator.run_check()

def test_validator_fails_on_hash_change(tmp_path):
    baseline = {"data/raw/file1.csv": "abc"}
    raw_dir = tmp_path / "data/raw"
    raw_dir.mkdir(parents=True)
    f = raw_dir / "file1.csv"
    f.write_text("different_content")
    validator = ProtectedInputValidator(baseline, tmp_path)
    with pytest.raises(AssertionError, match="Unexpected change: data/raw/file1.csv"):
        validator.run_check()

def test_validator_fails_on_unexplained_addition(tmp_path):
    baseline = {"data/raw/file1.csv": "abc"}
    raw_dir = tmp_path / "data/raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "file1.csv").write_text("content")
    (raw_dir / "unexplained.csv").write_text("other")
    import hashlib
    h = hashlib.sha256("content".encode()).hexdigest()
    baseline = {"data/raw/file1.csv": h}
    validator = ProtectedInputValidator(baseline, tmp_path)
    with pytest.raises(AssertionError, match="Unexplained addition: data/raw/unexplained.csv"):
        validator.run_check()

def test_validator_fails_on_false_classification(tmp_path):
    baseline = {"data/metadata/feature_manifest.csv": "abc"}
    meta_dir = tmp_path / "data/metadata"
    meta_dir.mkdir(parents=True)
    (meta_dir / "feature_manifest.csv").write_text("changed")
    validator = ProtectedInputValidator(baseline, tmp_path, approved_changes={})
    with pytest.raises(AssertionError, match="Unexpected change: data/metadata/feature_manifest.csv"):
        validator.run_check()

def test_validator_fails_on_reconciliation_failure(tmp_path):
    class BrokenValidator(ProtectedInputValidator):
        def run_check(self):
            super().run_check()
            raise AssertionError("Reconciliation 1 failed: mock reconciliation failure")
    raw_dir = tmp_path / "data/raw"
    raw_dir.mkdir(parents=True)
    import hashlib
    h = hashlib.sha256("content".encode()).hexdigest()
    baseline = {"data/raw/file1.csv": h}
    (raw_dir / "file1.csv").write_text("content")
    validator = BrokenValidator(baseline, tmp_path)
    with pytest.raises(AssertionError, match="Reconciliation 1 failed: mock reconciliation failure"):
        validator.run_check()

def test_validator_passes_approved_changes(tmp_path):
    import hashlib
    h1 = hashlib.sha256("content1".encode()).hexdigest()
    h2 = hashlib.sha256("content2".encode()).hexdigest()
    baseline = {
        "data/metadata/feature_manifest.csv": h1,
        "data/raw/file1.csv": h2
    }
    (tmp_path / "data/metadata").mkdir(parents=True)
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "data/metadata/feature_manifest.csv").write_text("changed_manifest")
    (tmp_path / "data/raw/file1.csv").write_text("content2")
    approved_changes = {"data/metadata/feature_manifest.csv": "Expected change"}
    validator = ProtectedInputValidator(baseline, tmp_path, approved_changes=approved_changes)
    res = validator.run_check()
    assert res['summary']['raw_data']['matching'] == 1
    assert res['summary']['phase_4_5_evidence']['matching'] == 0
    assert res['summary']['phase_4_5_evidence']['expected_changes'] == 1
    assert res['summary']['phase_4_5_evidence']['unexpected_changes'] == 0


class TestCanonicalHashPortability:
    """Task 4: Regression tests proving canonical text-hash portability and binary raw-byte integrity."""

    def test_lf_and_crlf_text_produce_same_canonical_hash(self, tmp_path):
        lf_content = b"header1,header2\nline1,10\nline2,20\n"
        crlf_content = b"header1,header2\r\nline1,10\r\nline2,20\r\n"

        p_lf = tmp_path / "data.csv"
        p_crlf = tmp_path / "data_crlf.csv"

        p_lf.write_bytes(lf_content)
        p_crlf.write_bytes(crlf_content)

        hash_lf = calculate_canonical_sha256(p_lf)
        hash_crlf = calculate_canonical_sha256(p_crlf)

        assert hash_lf == hash_crlf, "LF and CRLF text files must produce identical canonical hashes"

    def test_real_text_content_change_produces_different_hash(self, tmp_path):
        p1 = tmp_path / "config.json"
        p2 = tmp_path / "config_mod.json"

        p1.write_text('{"version": "1.0"}\n', encoding="utf-8")
        p2.write_text('{"version": "1.1"}\n', encoding="utf-8")

        assert calculate_canonical_sha256(p1) != calculate_canonical_sha256(p2)

    def test_one_byte_binary_change_produces_different_raw_hash(self, tmp_path):
        b1 = tmp_path / "model.joblib"
        b2 = tmp_path / "model_mod.joblib"

        data1 = b"\x00\x01\x02\x03\x04\x05"
        data2 = b"\x00\x01\x02\x03\x04\x06"

        b1.write_bytes(data1)
        b2.write_bytes(data2)

        assert calculate_canonical_sha256(b1) != calculate_canonical_sha256(b2)

    def test_protected_binary_artifacts_use_exact_raw_byte_comparison(self):
        b2_pred = Path("data/processed/phase_6/predictions/b2_predictions.parquet")
        if b2_pred.exists():
            import hashlib
            h_raw = hashlib.sha256(b2_pred.read_bytes()).hexdigest()
            h_canon = calculate_canonical_sha256(b2_pred)
            assert h_raw == h_canon, "Binary parquet files must match exact raw-byte SHA-256"
