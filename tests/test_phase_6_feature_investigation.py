"""QA tests for Phase 6 targeted feature-group investigation.

Tests for:
- Sampling isolation report (Part 1)
- Group/feature audit report (Parts 2 and 3)
- Sampling ablation report (Part 4)
- Cross-report consistency
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

PERM_SEED    = 137
MODEL_SEED   = 42
VAL_PREV_APPROX = 0.054932
SHUF_SHA_EXPECTED_16 = "f7b37f55ab92e659"   # perm_seed=137 shuffled label SHA


def load_json(name: str) -> dict:
    path = _REPO_ROOT / f"models/phase_6/{name}"
    if not path.exists():
        pytest.skip(f"{name} not yet generated")
    return json.loads(path.read_text())


# ===========================================================================
# 1. Group / Feature Audit (Parts 2 and 3)
# ===========================================================================

class TestGroupFeatureAudit:

    @pytest.fixture(scope="class")
    def report(self):
        return load_json("group_feature_audit.json")

    def test_shuf_sha_matches_known_value(self, report):
        """Shuffled-label SHA for perm=137 must match the known fingerprint."""
        sha = report["shuf_label_sha256"]
        assert sha.startswith(SHUF_SHA_EXPECTED_16), (
            f"shuf_sha={sha[:16]} does not match expected {SHUF_SHA_EXPECTED_16}"
        )

    def test_perm_seed_correct(self, report):
        assert report["perm_seed"] == PERM_SEED

    def test_no_sealed_targets_accessed(self, report):
        assert report["b1_accessed"] is False
        assert report["embargo_accessed"] is False
        assert report["b2_accessed"] is False

    def test_feature_set_clean(self, report):
        """No target, future (unexpected), raw, or ID columns in X."""
        check = report["part3_feature_audit"]["forbidden_feature_check"]
        assert check["feature_set_clean"] is True
        assert check["target_in_x"] == []
        assert check["future_in_x_unexpected"] == []
        assert check["raw_or_collapsed_future_in_x"] == []
        assert check["id_cols_in_x"] == []

    def test_total_features_110(self, report):
        assert report["part3_feature_audit"]["total_features"] == 110

    def test_segment_level_corr_near_zero(self, report):
        """Shuffled-label segment-level correlation with val must be < 0.05."""
        seg = report["part2_group_analysis"]["segment_diagnosis"]
        corr = abs(seg["corr_shuf_train_vs_val_prev"])
        assert corr < 0.05, (
            f"Segment-level shuf/val correlation {corr:.4f} exceeds 0.05 — "
            f"possible spatial clustering artefact"
        )

    def test_borough_corr_near_zero(self, report):
        """Borough-level shuf/val correlation must be below 0.15."""
        groupings = report["part2_group_analysis"]["groupings"]
        for g in groupings:
            if g.get("group_col") == "official_administrative_name":
                corr = abs(g["corr_shuf_vs_val"])
                assert corr < 0.15, (
                    f"Borough shuf/val corr={corr:.4f} exceeds threshold"
                )
                return

    def test_segment_length_cardinality_equals_n_segments(self, report):
        """segment_length_m cardinality should equal number of unique segments."""
        feats = report["part3_feature_audit"]["features"]
        slm = next((f for f in feats if f["feature"] == "segment_length_m"), None)
        if slm is None:
            pytest.skip("segment_length_m not in feature audit")
        # n_segments = 47,983 from segment-level analysis
        n_segs = report["part2_group_analysis"]["segment_diagnosis"]["n_common_segments"]
        assert slm["cardinality"] == n_segs, (
            f"segment_length_m cardinality={slm['cardinality']} != "
            f"n_segments={n_segs} — unique-segment proxy confirmed"
        )

    def test_all_110_features_classified(self, report):
        """Every feature must have a family assignment."""
        feats = report["part3_feature_audit"]["features"]
        unknown = [f["feature"] for f in feats if f["family"] == "unknown"]
        assert not unknown, f"Features without family: {unknown}"

    def test_no_group_corr_explains_elevated_auc(self, report):
        """No group-level corr should explain AUC=0.641.
        Road-category corr=0.46 is flagged, but group std is tiny (<0.002).
        This test ensures we document that the magnitude is negligible."""
        groupings = report["part2_group_analysis"]["groupings"]
        for g in groupings:
            if g.get("skip"):
                continue
            shuf_std = g.get("shuf_prev_std", 0.0)
            corr     = abs(g.get("corr_shuf_vs_val", 0.0))
            if corr > 0.4:
                # High correlation but magnitude must be tiny
                assert shuf_std < 0.005, (
                    f"Group {g['grouping']}: corr={corr:.3f} AND "
                    f"shuf_prev_std={shuf_std:.4f} — group structure may explain anomaly"
                )


# ===========================================================================
# 2. Sampling Ablation (Parts 1 and 4)
# ===========================================================================

class TestSamplingAblation:

    @pytest.fixture(scope="class")
    def report(self):
        return load_json("sampling_ablation_experiment.json")

    def test_perm_and_model_seeds_correct(self, report):
        assert report["perm_seed"] == PERM_SEED
        assert report["model_seed"] == MODEL_SEED

    def test_shuf_sha_matches(self, report):
        sha = report["shuf_label_sha256"]
        assert sha.startswith(SHUF_SHA_EXPECTED_16)

    def test_no_sealed_targets(self, report):
        assert report["b1_accessed"] is False
        assert report["embargo_accessed"] is False
        assert report["b2_accessed"] is False

    def test_val_prevalence_consistent(self, report):
        prev = report["val_prevalence"]
        assert abs(prev - VAL_PREV_APPROX) < 0.001

    def test_all_sampling_configs_present(self, report):
        """B and C must be present (A and D are references)."""
        runs = report["runs"]
        assert "B_sub1.0_col0.8" in runs, "Config B missing"
        assert "C_sub0.8_col1.0" in runs, "Config C missing"

    def test_all_ablation_configs_present(self, report):
        """All 6 ablation configs must be present."""
        runs = report["runs"]
        expected = [
            "abl1_repair_history_only",
            "abl2_static_admin_only",
            "abl3_pavement_asset_only",
            "abl4_weather_temporal_only",
            "abl5_all_except_repair_history",
            "abl6_all_except_static_admin",
        ]
        for e in expected:
            assert e in runs, f"Ablation config '{e}' missing from report"

    def test_ablation_feature_counts_correct(self, report):
        """Each ablation must use the correct number of features."""
        runs = report["runs"]
        expected_counts = {
            "abl1_repair_history_only":       23,
            "abl2_static_admin_only":         11,
            "abl3_pavement_asset_only":       20,
            "abl4_weather_temporal_only":     56,
            "abl5_all_except_repair_history": 11 + 20 + 56,   # 87
            "abl6_all_except_static_admin":   23 + 20 + 56,   # 99
        }
        for label, expected in expected_counts.items():
            if label not in runs:
                continue
            actual = runs[label]["feature_count"]
            assert actual == expected, (
                f"{label}: expected {expected} features, got {actual}"
            )

    def test_config_b_row_isolation(self, report):
        """Config B (sub=1.0, col=0.8) removes row subsampling."""
        r = report["runs"]["B_sub1.0_col0.8"]
        assert r["subsample"] == 1.0
        assert r["colsample_bytree"] == 0.8

    def test_config_c_col_isolation(self, report):
        """Config C (sub=0.8, col=1.0) removes column subsampling."""
        r = report["runs"]["C_sub0.8_col1.0"]
        assert r["subsample"] == 0.8
        assert r["colsample_bytree"] == 1.0

    def test_each_run_has_unique_cache_fingerprint(self, report):
        """All runs must have distinct cache fingerprints."""
        fps = [r["cache_fingerprint"] for r in report["runs"].values()]
        assert len(set(fps)) == len(fps), "Cache fingerprint collision"

    def test_all_runs_sealed_clean(self, report):
        """Every run record must confirm no sealed target access."""
        for label, r in report["runs"].items():
            assert r["b1_accessed"] is False, f"{label}: B1 accessed"
            assert r["embargo_accessed"] is False, f"{label}: embargo accessed"
            assert r["b2_accessed"] is False, f"{label}: B2 accessed"

    def test_all_runs_have_required_fields(self, report):
        """Every run must contain all required reporting fields."""
        required = {
            "perm_seed", "model_seed", "cache_fingerprint",
            "shuf_label_sha256", "pred_sha256",
            "null_ap", "ap_minus_prevalence", "ap_ratio",
            "null_roc_auc", "auc_minus_half", "null_brier", "pred_std",
            "train_time_s",
        }
        for label, r in report["runs"].items():
            missing = required - set(r.keys())
            assert not missing, f"Run '{label}' missing fields: {missing}"


# ===========================================================================
# 3. Cross-report consistency
# ===========================================================================

class TestCrossReportConsistency:

    def test_shuf_sha_consistent_across_reports(self):
        """perm=137 shuffled-label SHA must be identical in all reports."""
        reports = {}
        for name in [
            "group_feature_audit.json",
            "sampling_ablation_experiment.json",
            "seed_isolation_experiment.json",
            "seed_137_reproduction.json",
        ]:
            p = _REPO_ROOT / "models/phase_6" / name
            if p.exists():
                d = json.loads(p.read_text())
                # Extract SHA from various report structures
                sha = (d.get("shuf_label_sha256")
                       or d.get("runs", {}).get("part1and2_perm137_model42", {})
                           .get("shuf_label_sha256")
                       or d.get("run1", {}).get("shuf_label_sha256", "")
                       or next(
                           (v.get("shuf_label_sha256", "")
                            for v in d.get("runs", {}).values()
                            if v.get("perm_seed") == 137),
                           ""
                       ))
                if sha:
                    reports[name] = sha[:16]

        if len(reports) < 2:
            pytest.skip("Fewer than 2 reports available for cross-check")

        shas = set(reports.values())
        assert len(shas) == 1, (
            f"Shuffled-label SHA inconsistent across reports: {reports}"
        )

    def test_val_prevalence_consistent_across_reports(self):
        """val_prevalence must be consistent (±0.001) across all reports."""
        prevs = []
        for name in [
            "group_feature_audit.json",
            "sampling_ablation_experiment.json",
            "seed_isolation_experiment.json",
        ]:
            p = _REPO_ROOT / "models/phase_6" / name
            if p.exists():
                d = json.loads(p.read_text())
                prev = d.get("val_prevalence")
                if prev:
                    prevs.append(float(prev))
        if len(prevs) < 2:
            pytest.skip("Fewer than 2 reports with val_prevalence")
        assert max(prevs) - min(prevs) < 0.001, (
            f"val_prevalence inconsistent: {prevs}"
        )
