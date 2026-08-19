"""QA tests for Phase 6 repair-history null AP investigation.

Tests for:
- Part 1: Cross-seed repair-only controls
- Part 2: Repair-only sampling isolation
- Part 3: Temporal audit (window bounds, hard-fail conditions)
- Part 4: Score-tail diagnostics
- Cross-seed uniqueness and cache isolation
- Deterministic score-tail calculations
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

PERM_SEED     = 137
MODEL_SEED    = 42
VAL_PREV      = 0.054932   # approximate
REPAIR_FEATS  = 23

# Known SHA for perm=137 shuffled labels (established across all previous experiments)
SHUF_SHA_137_16 = "f7b37f55ab92e659"
# Reference repair-only perm=137 AP (from ablation experiment)
ABLATION_REF_AP_137 = 0.140055


def load_json(name: str) -> dict:
    p = _REPO_ROOT / f"models/phase_6/{name}"
    if not p.exists():
        pytest.skip(f"{name} not yet generated")
    return json.loads(p.read_text())


# ===========================================================================
# 1. Repair-History Investigation (Parts 1 and 2)
# ===========================================================================

class TestRepairHistoryInvestigation:

    @pytest.fixture(scope="class")
    def report(self):
        return load_json("repair_history_investigation.json")

    def test_model_seed_correct(self, report):
        assert report["model_seed"] == MODEL_SEED

    def test_feature_set_is_repair_only(self, report):
        assert report["feature_set"] == "repair_history_only"
        assert len(report["feature_list"]) == REPAIR_FEATS

    def test_no_sealed_targets(self, report):
        assert report["b1_accessed"] is False
        assert report["embargo_accessed"] is False
        assert report["b2_accessed"] is False

    def test_val_prevalence_consistent(self, report):
        assert abs(report["val_prevalence"] - VAL_PREV) < 0.002

    def test_all_cross_seed_runs_present(self, report):
        """perm=42, 137, 2026 must all appear in Part 1."""
        runs = report["runs"]
        for perm in [42, 137, 2026]:
            key = f"part1_perm{perm}_model{MODEL_SEED}"
            assert key in runs, f"Part 1 run for perm={perm} missing"

    def test_all_sampling_configs_present(self, report):
        """B, C, D sampling configs must all appear in Part 2."""
        runs = report["runs"]
        for cfg in ["B_sub1.0_col0.8", "C_sub0.8_col1.0", "D_sub1.0_col1.0"]:
            key = f"part2_{cfg}"
            assert key in runs, f"Part 2 sampling config {cfg} missing"

    def test_perm137_ap_elevated_above_prevalence(self, report):
        """The perm=137 repair-only AP must exceed prevalence (the anomaly)."""
        r    = report["runs"]["part1_perm137_model42"]
        ap   = r["null_ap"]
        prev = report["val_prevalence"]
        ratio = ap / prev
        assert ratio > 1.5, (
            f"perm=137 repair-only AP/prev={ratio:.3f} — anomaly not reproduced"
        )

    def test_perm137_ap_consistent_with_ablation(self, report):
        """perm=137 AP must be within 0.02 of the ablation reference."""
        ap = report["runs"]["part1_perm137_model42"]["null_ap"]
        assert abs(ap - ABLATION_REF_AP_137) < 0.02, (
            f"AP={ap:.6f} deviates from ablation reference {ABLATION_REF_AP_137:.6f}"
        )

    def test_all_runs_have_unique_cache_fingerprints(self, report):
        """Every run must use a unique isolated cache."""
        fps = [r["cache_fingerprint"] for r in report["runs"].values()]
        assert len(set(fps)) == len(fps), "Cache fingerprint collision — runs not isolated"

    def test_all_runs_have_required_fields(self, report):
        required = {
            "perm_seed", "model_seed", "cache_fingerprint",
            "shuf_label_sha256", "pred_sha256",
            "null_ap", "ap_over_prevalence", "null_roc_auc",
            "null_brier", "pred_std", "train_time_s",
            "feature_importance_gain",
        }
        for label, r in report["runs"].items():
            missing = required - set(r.keys())
            assert not missing, f"Run '{label}' missing fields: {missing}"

    def test_all_runs_sealed_clean(self, report):
        for label, r in report["runs"].items():
            assert r["b1_accessed"] is False, f"{label}: B1 accessed"
            assert r["embargo_accessed"] is False, f"{label}: embargo accessed"
            assert r["b2_accessed"] is False, f"{label}: B2 accessed"

    def test_perm137_shuf_sha_matches_known(self, report):
        """perm=137 shuffled-label SHA must match the cross-experiment fingerprint."""
        sha = report["runs"]["part1_perm137_model42"]["shuf_label_sha256"]
        assert sha.startswith(SHUF_SHA_137_16), (
            f"shuf_sha={sha[:16]} does not match {SHUF_SHA_137_16}"
        )

    def test_different_perms_have_different_shuf_shas(self, report):
        """Different permutation seeds must produce different shuffled-label SHAs."""
        shas = {
            perm: report["runs"][f"part1_perm{perm}_model{MODEL_SEED}"]["shuf_label_sha256"]
            for perm in [42, 137, 2026]
        }
        assert len(set(shas.values())) == 3, (
            f"Duplicate SHAs across perms: {shas}"
        )

    def test_sampling_config_a_matches_part1_reference(self, report):
        """Part 2 config A should be the same as Part 1 perm=137 run."""
        r_part1 = report["runs"]["part1_perm137_model42"]
        assert r_part1["subsample"] == 0.8
        assert r_part1["colsample_bytree"] == 0.8

    def test_sampling_b_removes_row_subsampling(self, report):
        r = report["runs"]["part2_B_sub1.0_col0.8"]
        assert r["subsample"] == 1.0
        assert r["colsample_bytree"] == 0.8

    def test_sampling_c_removes_column_subsampling(self, report):
        r = report["runs"]["part2_C_sub0.8_col1.0"]
        assert r["subsample"] == 0.8
        assert r["colsample_bytree"] == 1.0

    def test_sampling_d_removes_both(self, report):
        r = report["runs"]["part2_D_sub1.0_col1.0"]
        assert r["subsample"] == 1.0
        assert r["colsample_bytree"] == 1.0

    def test_feature_importances_sum_positive(self, report):
        """Feature importance gains for perm=137 must sum to a positive value."""
        imp = report["runs"]["part1_perm137_model42"]["feature_importance_gain"]
        assert sum(imp.values()) > 0

    def test_prior_repair_months_12m_in_top_importances(self, report):
        """prior_repair_months_12m must appear in the feature importance dict."""
        imp = report["runs"]["part1_perm137_model42"]["feature_importance_gain"]
        assert "prior_repair_months_12m" in imp, (
            "prior_repair_months_12m absent from importances — unexpected"
        )


# ===========================================================================
# 2. Temporal Audit (Part 3)
# ===========================================================================

class TestTemporalAudit:

    @pytest.fixture(scope="class")
    def report(self):
        return load_json("repair_temporal_audit.json")

    def test_no_sealed_targets(self, report):
        assert report["b1_accessed"] is False
        assert report["embargo_accessed"] is False
        assert report["b2_accessed"] is False

    def test_all_23_features_audited(self, report):
        assert report["part3_temporal_audit"]["features_audited"] == REPAIR_FEATS



    def test_windowed_features_pass_audit(self, report):
        """All 30d/90d/180d/365d windowed features must have upper_bound_in_code=True."""
        details = report["part3_temporal_audit"]["feature_details"]
        for f in details:
            feat = f["feature"]
            if feat == "prior_repair_months_12m":
                continue  # known fail
            if any(suffix in feat for suffix in ["_30d", "_90d", "_180d", "_365d"]):
                assert f["upper_bound_in_code"] is True, (
                    f"{feat}: upper_bound_in_code=False — unexpected window leak"
                )

    def test_days_since_last_repair_upper_bounded(self, report):
        details = report["part3_temporal_audit"]["feature_details"]
        for f in details:
            if f["feature"] == "days_since_last_repair":
                assert f["upper_bound_in_code"] is True
                return

    def test_no_prior_repair_flag_upper_bounded(self, report):
        details = report["part3_temporal_audit"]["feature_details"]
        for f in details:
            if f["feature"] == "no_prior_repair_flag":
                assert f["upper_bound_in_code"] is True
                return

    def test_repair_active_days_within_window(self, report):
        """repair_active_days_Xd max must be <= X (window size)."""
        details = report["part3_temporal_audit"]["feature_details"]
        for f in details:
            feat = f["feature"]
            if feat.startswith("repair_active_days_"):
                w = int(feat.split("_")[-1].replace("d", ""))
                val_max = f["val_max"]
                assert val_max <= w, (
                    f"{feat}: val_max={val_max} > window={w} days — "
                    "active days exceeds window size"
                )


# ===========================================================================
# 3. Score-Tail Diagnostic (Part 4)
# ===========================================================================

class TestScoreTailDiagnostic:

    @pytest.fixture(scope="class")
    def report(self):
        r = load_json("repair_temporal_audit.json")
        if not r["part4_tail_diagnostic"]["preds_available"]:
            pytest.skip("Predictions not yet available for tail diagnostic")
        return r

    def test_tail_metrics_all_thresholds_present(self, report):
        tail = report["part4_tail_diagnostic"]["tail_metrics"]
        for pct in [1, 5, 10, 20]:
            assert f"top_{pct}pct" in tail, f"top_{pct}% tail metrics missing"

    def test_top_1pct_precision_above_prevalence(self, report):
        """Top 1% precision must exceed global prevalence."""
        tail = report["part4_tail_diagnostic"]["tail_metrics"]
        prec = tail["top_1pct"]["precision"]
        prev = VAL_PREV
        assert prec > prev, (
            f"Top 1% precision={prec:.4f} <= prevalence={prev:.4f}"
        )

    def test_precision_monotonically_decreasing(self, report):
        """Precision must decrease as threshold loosens."""
        tail = report["part4_tail_diagnostic"]["tail_metrics"]
        precs = [tail[f"top_{p}pct"]["precision"] for p in [1, 5, 10, 20]]
        for i in range(len(precs) - 1):
            assert precs[i] >= precs[i + 1], (
                f"Precision not monotone: top_{[1,5,10,20][i]}%={precs[i]:.4f} "
                f"< top_{[1,5,10,20][i+1]}%={precs[i+1]:.4f}"
            )

    def test_recall_monotonically_increasing(self, report):
        """Recall must increase as threshold loosens."""
        tail = report["part4_tail_diagnostic"]["tail_metrics"]
        recalls = [tail[f"top_{p}pct"]["recall"] for p in [1, 5, 10, 20]]
        for i in range(len(recalls) - 1):
            assert recalls[i] <= recalls[i + 1], (
                f"Recall not monotone: top_{[1,5,10,20][i]}%={recalls[i]:.4f} "
                f"> top_{[1,5,10,20][i+1]}%={recalls[i+1]:.4f}"
            )

    def test_decile_results_present(self, report):
        dec = report["part4_tail_diagnostic"]["prior_repair_months_12m_deciles"]
        # prior_repair_months_12m is highly skewed (mostly 0): qcut collapses to
        # as few as 3 bins (0, 1-12, >12). Require >= 2 meaningful groups.
        assert len(dec) >= 2, f"Fewer than 2 decile groups returned: {len(dec)}"

    def test_high_decile_real_prevalence_above_low(self, report):
        """Top decile of prior_repair_months_12m must have higher real prevalence
        than bottom decile — confirms predictive signal in the feature."""
        dec = report["part4_tail_diagnostic"]["prior_repair_months_12m_deciles"]
        keys = sorted(dec.keys(), key=int)
        if len(keys) >= 2:
            bot = dec[keys[0]]["real_val_prevalence"]
            top = dec[keys[-1]]["real_val_prevalence"]
            assert top > bot, (
                f"Top decile prev={top:.4f} not > bottom decile prev={bot:.4f}"
            )


# ===========================================================================
# 4. Code-level temporal constraint tests
# ===========================================================================

class TestRepairWindowCode:
    """Tests that verify the repair feature construction code has correct bounds."""

    def test_build_panel_uses_upper_bound_for_active_days(self):
        """repair_active_days uses event_date <= t in the panel builder."""
        panel_script = _REPO_ROOT / "src/montreal_road_risk/features/repairs.py"
        if not panel_script.exists():
            pytest.skip("repairs.py not found")
        code = panel_script.read_text()
        assert '"event_date"] <= t' in code or "'event_date'] <= t" in code, (
            "Upper-bound filter event_date <= t not found in panel builder"
        )

    def test_prior_repair_months_12m_has_upper_bound(self):
        """Regression test: verify prior_repair_months_12m contains event_date <= t upper bound."""
        panel_script = _REPO_ROOT / "src/montreal_road_risk/features/repairs.py"
        if not panel_script.exists():
            pytest.skip("repairs.py not found")
        code = panel_script.read_text()
        lines = code.splitlines()
        raw12m_lines = [i for i, line in enumerate(lines, 1)
                        if "raw_12m = raw_daily" in line]
        assert len(raw12m_lines) > 0, "raw_12m line not found"
        for lineno in raw12m_lines:
            context = "\n".join(lines[lineno - 1: lineno + 5])
            has_upper_bound = "<= t" in context or "<= as_of" in context
            assert has_upper_bound, (
                f"Missing upper bound filter (event_date <= t) at line {lineno}!"
            )

    def test_remediated_prior_repair_months_12m_max_within_12(self):
        """Regression test: verify prior_repair_months_12m max <= 12 in remediated datasets."""
        import pyarrow.parquet as pq
        import pyarrow.compute as pc

        # Check phase_4_remediated_01 or phase_5_remediated_01 if present
        target_files = [
            _REPO_ROOT / "data/processed/phase_5_remediated_01/train_90d.parquet",
            _REPO_ROOT / "data/processed/phase_5_remediated_01/val_90d.parquet",
        ]
        for tf in target_files:
            if tf.exists():
                tbl = pq.read_table(tf, columns=["prior_repair_months_12m"])
                mx = pc.max(tbl.column("prior_repair_months_12m")).as_py()
                assert mx <= 12, (
                    f"{tf.name} prior_repair_months_12m max={mx} > 12 — leakage present!"
                )

    def test_future_event_invariance(self):
        """Regression test: verify adding events after as_of_date does not alter feature values."""
        import pandas as pd
        from montreal_road_risk.features.repairs import rolling_repairs_for_anchor

        t = pd.Timestamp("2022-06-30")
        first_obs = pd.Timestamp("2016-12-07")
        segments = ["SEG_001"]

        raw_daily_past = pd.DataFrame({
            "canonical_segment_id": ["SEG_001", "SEG_001"],
            "event_date": [pd.Timestamp("2022-01-15"), pd.Timestamp("2022-03-20")],
            "raw_count": [1, 1]
        })
        col_daily_past = pd.DataFrame({
            "canonical_segment_id": ["SEG_001", "SEG_001"],
            "event_date": [pd.Timestamp("2022-01-15"), pd.Timestamp("2022-03-20")],
            "col_count": [1, 1]
        })

        raw_daily_with_future = pd.DataFrame({
            "canonical_segment_id": ["SEG_001", "SEG_001", "SEG_001"],
            "event_date": [pd.Timestamp("2022-01-15"), pd.Timestamp("2022-03-20"), pd.Timestamp("2022-08-10")],
            "raw_count": [1, 1, 5]
        })
        col_daily_with_future = pd.DataFrame({
            "canonical_segment_id": ["SEG_001", "SEG_001", "SEG_001"],
            "event_date": [pd.Timestamp("2022-01-15"), pd.Timestamp("2022-03-20"), pd.Timestamp("2022-08-10")],
            "col_count": [1, 1, 5]
        })

        last_rep = pd.Series([pd.Timestamp("2022-03-20")], index=["SEG_001"])

        res_past = rolling_repairs_for_anchor(
            t, segments, raw_daily_past, col_daily_past, last_rep, [30, 90, 180, 365], first_obs
        )
        res_fut = rolling_repairs_for_anchor(
            t, segments, raw_daily_with_future, col_daily_with_future, last_rep, [30, 90, 180, 365], first_obs
        )

        assert res_past["prior_repair_months_12m"].iloc[0] == res_fut["prior_repair_months_12m"].iloc[0]
        assert res_fut["prior_repair_months_12m"].iloc[0] == 2
        assert res_fut["prior_repair_months_12m"].iloc[0] <= 12

        # New requirements: Assert every other historical repair feature is identical.
        # Drop prior_repair_months_12m and compare the rest
        past_other = res_past.drop(columns=["prior_repair_months_12m"])
        fut_other = res_fut.drop(columns=["prior_repair_months_12m"])
        pd.testing.assert_frame_equal(past_other, fut_other)

        # Assert events exactly at t follow the approved inclusive boundary.
        raw_daily_at_t = raw_daily_past.copy()
        raw_daily_at_t.loc[2] = ["SEG_001", pd.Timestamp("2022-06-30"), 1]
        col_daily_at_t = col_daily_past.copy()
        col_daily_at_t.loc[2] = ["SEG_001", pd.Timestamp("2022-06-30"), 1]

        res_at_t = rolling_repairs_for_anchor(
            t, segments, raw_daily_at_t, col_daily_at_t, last_rep, [30, 90, 180, 365], first_obs
        )
        assert res_at_t["repair_event_count_raw_30d"].iloc[0] > res_past["repair_event_count_raw_30d"].iloc[0]
        assert res_at_t["prior_repair_months_12m"].iloc[0] > res_past["prior_repair_months_12m"].iloc[0]

        # Assert events after t never enter any historical feature.
        # This is already covered by the frame_equal assert above, but let's be explicit
        for c in res_fut.columns:
            if "repair" in c:
                assert res_fut[c].iloc[0] == res_past[c].iloc[0]


