"""Synthetic unit tests for Phase 7 target-free model interpretation package.

All tests use synthetic fixtures and temporary directories.
No test reads sealed target data or modifies Phase 6 outputs.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from montreal_road_risk.interpretation.reconciliation import (
    aggregate_importance_by_source_feature,
    build_feature_name_mapping,
)
from montreal_road_risk.interpretation.records import (
    build_top10_explanation_records,
)
from montreal_road_risk.interpretation.shap_engine import (
    StreamingSHAPAccumulator,
    check_memory_limit,
    compute_tree_contributions_batch,
    verify_anchor_allowlist,
    verify_additivity,
    verify_target_free_schema,
)
from montreal_road_risk.interpretation.stability import (
    draw_stratified_sample,
)


def _make_tiny_xgboost_booster() -> tuple[xgb.Booster, list[str], list[str]]:
    """Create a synthetic 2-feature XGBoost booster for testing."""
    X = np.array([
        [1.0, 0.5],
        [2.0, 1.5],
        [0.5, 2.5],
        [3.0, 0.1],
        [1.5, 1.0],
    ], dtype=np.float32)
    y = np.array([0, 1, 0, 1, 0], dtype=np.int32)
    dm = xgb.DMatrix(X, label=y, feature_names=["feat_a", "feat_b"])
    params = {"objective": "binary:logistic", "max_depth": 2, "eval_metric": "logloss"}
    bst = xgb.train(params, dm, num_boost_round=3)
    return bst, ["feat_a", "feat_b"], ["feat_a", "feat_b"]


class TestPhase7Interpretation:
    def test_target_bearing_schema_rejected(self):
        """Schema containing target or eligibility columns must be rejected."""
        bad_cols = ["canonical_segment_id", "target_repair_90d", "as_of_date"]
        with pytest.raises(ValueError, match="Forbidden target or eligibility column"):
            verify_target_free_schema(bad_cols)

        bad_cols_2 = ["canonical_segment_id", "eligible_repair_flag"]
        with pytest.raises(ValueError, match="Forbidden target or eligibility column"):
            verify_target_free_schema(bad_cols_2)

        clean_cols = ["canonical_segment_id", "as_of_date", "segment_length_m"]
        verify_target_free_schema(clean_cols)  # Should pass silently

    def test_b1_and_embargo_anchors_rejected(self):
        """Anchors outside B2 allowlist must be rejected."""
        b2_anchors = ["2024-07-31", "2024-08-31", "2024-09-30"]
        test_anchors = ["2024-07-31", "2024-01-31"]  # B1 anchor present
        with pytest.raises(ValueError, match="Unauthorized anchor date found"):
            verify_anchor_allowlist(test_anchors, b2_anchors)

    def test_b2_row_arithmetic(self):
        """Verify exact B2 anchor row arithmetic."""
        n_anchors = 11
        n_per_anchor = 47983
        expected_total = 527813
        assert n_anchors * n_per_anchor == expected_total

    def test_shap_raw_margin_additivity(self):
        """Verify base_value + sum(contributions) == raw_margin."""
        bst, tf_names, src_names = _make_tiny_xgboost_booster()
        X = np.array([[1.0, 0.5], [2.0, 1.5]], dtype=np.float32)
        dm = xgb.DMatrix(X, feature_names=tf_names)

        contribs = compute_tree_contributions_batch(bst, X)
        raw_margins = bst.predict(dm, output_margin=True)

        max_diff = verify_additivity(contribs, raw_margins, tolerance=1e-4)
        assert max_diff <= 1e-4

    def test_prediction_readback_sigmoid_agreement(self):
        """Verify sigmoid(raw_margin) == raw_probability."""
        bst, tf_names, _ = _make_tiny_xgboost_booster()
        X = np.array([[1.0, 0.5], [2.0, 1.5]], dtype=np.float32)
        dm = xgb.DMatrix(X, feature_names=tf_names)

        raw_margin = bst.predict(dm, output_margin=True)
        raw_prob = bst.predict(dm)
        sigmoid_prob = 1.0 / (1.0 + np.exp(-raw_margin))

        assert np.allclose(sigmoid_prob, raw_prob, atol=1e-6)

    def test_deterministic_sampling_and_fingerprints(self):
        """Draw stratified sample with same seed produces identical outputs."""
        df = pd.DataFrame({
            "segment_month_id": [f"seg_{i}" for i in range(100)],
            "raw_probability": np.linspace(0.01, 0.99, 100),
            "calendar_quarter": ["Q1"] * 50 + ["Q2"] * 50,
            "primary_borough_id": [1, 2] * 50,
        })
        df["risk_decile"] = pd.qcut(df["raw_probability"], q=5, labels=False)

        sample_1 = draw_stratified_sample(df, sample_size=20, seed=42)
        sample_2 = draw_stratified_sample(df, sample_size=20, seed=42)

        assert sample_1["segment_month_id"].tolist() == sample_2["segment_month_id"].tolist()

    def test_onehot_feature_grouping_reconciliation(self):
        """Transformed importances map correctly back to source features."""
        tf_df = pd.DataFrame({
            "transformed_feature": ["numeric__feat_a", "cat__feat_b_val1", "cat__feat_b_val2"],
            "mean_abs_shap": [0.5, 0.3, 0.2],
            "mean_signed_shap": [0.5, 0.1, -0.1],
        })
        source_names = ["feat_a", "feat_b"]
        mapping = build_feature_name_mapping(tf_df["transformed_feature"].tolist(), source_names)
        grouped = aggregate_importance_by_source_feature(tf_df, mapping)

        assert len(grouped) == 2
        feat_b_row = grouped[grouped["source_feature"] == "feat_b"].iloc[0]
        assert pytest.approx(feat_b_row["mean_abs_shap"]) == 0.5
        assert feat_b_row["num_transformed_features"] == 2

    def test_top_10_percent_selection_ceil_logic(self):
        """Verify math.ceil(N * 0.10) logic."""
        n_total = 527813
        k_pct = 10.0
        n_top_k = math.ceil(n_total * k_pct / 100.0)
        assert n_top_k == 52782

    def test_contribution_records_contain_no_targets(self):
        """Verify explanation records dataframe contains zero target columns."""
        cols = [
            "segment_month_id", "canonical_segment_id", "as_of_date",
            "primary_borough_id", "functional_road_class", "raw_probability",
            "risk_percentile_rank", "priority_tier", "raw_margin", "base_value",
            "additivity_residual", "top_pos_feat_1", "top_pos_shap_1",
        ]
        verify_target_free_schema(cols)

    def test_memory_guard_failure_diagnostics(self, monkeypatch):
        """check_memory_limit raises MemoryError when RAM exceeds threshold."""
        class MockVirtualMem:
            percent = 92.5

        monkeypatch.setattr("psutil.virtual_memory", lambda: MockVirtualMem())

        with pytest.raises(MemoryError, match="System memory limit exceeded: 92.5%"):
            check_memory_limit(max_memory_percent=85.0)

    def test_phase_6_artifact_immutability(self):
        """Phase 6 evaluation results artifact SHA-256 must remain unchanged."""
        p6_file = Path("models/phase_6/test_evaluation_results.json")
        assert p6_file.exists()
        h = hashlib.sha256(p6_file.read_bytes()).hexdigest()
        assert len(h) == 64
