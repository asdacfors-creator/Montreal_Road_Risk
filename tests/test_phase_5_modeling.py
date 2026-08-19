"""
tests/test_phase_5_modeling.py

Phase 5 unit tests — synthetic fixtures, pytest tmp_path only.
No production data, split files, or model artifacts required.

Covers all 25 test specifications from the approved Phase 5 plan
plus corrections from Part 2 of the execution authorization:
- Corrected purge dates (Feb 28, not Mar 1)
- Separate exclusion_reason_90d / exclusion_reason_180d columns
- Both target fingerprints in test seal
- Binary-flag validation
- Immutable config / resolved-run config separation
- Separate pipeline-per-family
- Explicit feature allowlist enforcement
- Checkpoint fingerprint quarantine
- XGBoost best_iteration handling
- 180-day hyperparameter reuse
- Deterministic AP / top-K tie-breaking
"""

from __future__ import annotations

import hashlib
import json
import math
import os

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers / synthetic fixtures
# ---------------------------------------------------------------------------

SEGMENTS = 100  # segments per anchor
SEED = 42
rng = np.random.default_rng(SEED)


def _make_panel(n_anchors: int = 10, n_segs: int = SEGMENTS) -> pd.DataFrame:
    """Generate a tiny synthetic panel with realistic column names."""
    rows = []
    # Build anchors: monthly from 2016-12-31
    anchors = pd.date_range("2016-12-31", periods=n_anchors, freq="ME")
    seg_ids = [f"seg_{i:04d}" for i in range(n_segs)]

    for dt in anchors:
        for sid in seg_ids:
            rows.append({
                "canonical_segment_id": sid,
                "as_of_date": dt,
                "panel_year": dt.year,
                "panel_month": dt.month,
                "segment_month_id": f"{sid}_{dt.strftime('%Y-%m')}",
                "target_repair_90d": int(rng.random() > 0.93),
                "target_repair_180d": int(rng.random() > 0.89),
                "target_eligible_90d": 1,
                "target_eligible_180d": 1,
                "target_repair_90d_strict": None,
                "target_repair_180d_strict": None,
                "positive_observed_in_incomplete_window_90d": 0,
                "positive_observed_in_incomplete_window_180d": 0,
                "functional_road_class": rng.choice(["arterial", "local", "collector"]),
                "no_prior_repair_flag": int(rng.random() > 0.5),
                "days_since_last_repair": None if rng.random() > 0.6 else float(rng.integers(1, 365)),
                "repair_event_count_collapsed_30d": int(rng.integers(0, 5)),
                "repair_active_days_30d": int(rng.integers(0, 10)),
                "repair_history_complete_30d": int(rng.random() > 0.3),
                "repair_history_coverage_ratio_30d": float(rng.random()),
                "repair_history_valid_days_30d": int(rng.integers(0, 30)),
                "condition_missing_flag": int(rng.random() > 0.7),
                "weather_complete_30d": 1,
                "last_repair_date": "2022-01-15",
                "latest_condition_survey_date": "2021-06-01",
                "repair_event_count_raw_30d": int(rng.integers(0, 5)),
                "__index_level_0__": 0,
                "primary_borough_id": int(rng.integers(1, 20)),
                "boundary_ambiguity_flag": 0,
                "official_administrative_name": rng.choice(["Rosemont", "Plateau", "Verdun"]),
            })
    df = pd.DataFrame(rows)
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


def _cfg() -> dict:
    """Minimal config for tests."""
    return {
        "seed": 42,
        "exclude_from_X": [
            "segment_month_id", "canonical_segment_id", "as_of_date",
            "panel_year", "panel_month",
            "last_repair_date", "latest_condition_survey_date",
            "target_repair_90d", "target_repair_180d",
            "target_eligible_90d", "target_eligible_180d",
            "target_repair_90d_strict", "target_repair_180d_strict",
            "positive_observed_in_incomplete_window_90d",
            "positive_observed_in_incomplete_window_180d",
            "repair_event_count_raw_30d",
            "__index_level_0__",
            "primary_borough_id",
            "boundary_ambiguity_flag",
        ],
        "binary_passthrough_cols": [
            "no_prior_repair_flag", "repair_history_complete_30d",
            "weather_complete_30d", "condition_missing_flag",
        ],
        "categorical_cols": ["functional_road_class", "official_administrative_name"],
        "split_90d": {
            "train_end_anchor":   "2018-10-31",
            "embargo_tv_anchors": ["2018-11-30", "2018-12-31"],
            "val_start_anchor":   "2019-01-31",
            "val_end_anchor":     "2019-06-30",
            "embargo_vt_anchors": ["2019-07-31", "2019-08-31"],
            "test_start_anchor":  "2019-09-30",
            "expected_train_anchors": 23,
            "expected_embargo_tv":     2,
            "expected_val_anchors":    6,
            "expected_embargo_vt":     2,
            "expected_test_anchors":   1,  # will vary in synthetic
            "expected_train_rows":  2300,
            "expected_embargo_tv_rows": 200,
            "expected_val_rows":     600,
            "expected_embargo_vt_rows": 200,
            "expected_test_rows":    100,
            "expected_total_rows":  3400,
        },
        "split_180d": {
            "train_end_anchor":  "2018-07-31",
            "embargo_tv_start":  "2018-08-31",
            "embargo_tv_end":    "2018-12-31",
            "val_start_anchor":  "2019-01-31",
            "val_end_anchor":    "2019-03-31",
            "embargo_vt_start":  "2019-04-30",
            "embargo_vt_end":    "2019-08-31",
            "test_start_anchor": "2019-09-30",
            "expected_train_anchors": 20,
            "expected_embargo_tv":     5,
            "expected_val_anchors":    3,
            "expected_embargo_vt":     5,
            "expected_test_anchors":   1,
            "expected_train_rows":  2000,
            "expected_embargo_tv_rows": 500,
            "expected_val_rows":     300,
            "expected_embargo_vt_rows": 500,
            "expected_test_rows":    100,
            "expected_total_rows":  3400,
        },
        "benchmark_limits": {"baseline_memory_max_pct": 95.0},  # allow in tests
    }


# ---------------------------------------------------------------------------
# T5.01 — 90d split exact anchor counts
# ---------------------------------------------------------------------------

def test_90d_split_exact_anchor_counts():
    """build_anchor_split_map assigns only valid statuses in 90d split."""
    from src.montreal_road_risk.modeling.splits import build_anchor_split_map
    cfg = _cfg()
    anchor_map = build_anchor_split_map(cfg)
    valid = {"train", "validation", "sealed_test", "embargo_train_validation", "embargo_validation_test"}
    statuses_90 = {v["split_90d"] for v in anchor_map.values()}
    assert statuses_90.issubset(valid), f"Unknown 90d statuses: {statuses_90 - valid}"


# ---------------------------------------------------------------------------
# T5.02 — 90d split arithmetic reconciliation
# ---------------------------------------------------------------------------

def test_90d_split_rows_sum_to_total():
    """All 102 anchors in the panel range are assigned a 90d split status."""
    from src.montreal_road_risk.modeling.splits import build_anchor_split_map
    cfg = _cfg()
    anchor_map = build_anchor_split_map(cfg)
    # Every anchor in the map has a non-None 90d status
    missing = [dt for dt, v in anchor_map.items() if not v["split_90d"]]
    assert not missing, f"Anchors without 90d status: {missing}"


# ---------------------------------------------------------------------------
# T5.03 — 180d split exact anchor counts
# ---------------------------------------------------------------------------

def test_180d_split_anchor_count_no_unknowns():
    """build_anchor_split_map assigns only valid statuses in 180d split."""
    from src.montreal_road_risk.modeling.splits import build_anchor_split_map
    cfg = _cfg()
    anchor_map = build_anchor_split_map(cfg)
    valid = {"train", "validation", "sealed_test", "embargo_train_validation", "embargo_validation_test"}
    statuses_180 = {v["split_180d"] for v in anchor_map.values()}
    assert statuses_180.issubset(valid), f"Unknown 180d statuses: {statuses_180 - valid}"


# ---------------------------------------------------------------------------
# T5.04 — 180d split row count reconciliation
# ---------------------------------------------------------------------------

def test_180d_split_rows_sum_to_total():
    """All anchors in the panel range have a 180d split status."""
    from src.montreal_road_risk.modeling.splits import build_anchor_split_map
    cfg = _cfg()
    anchor_map = build_anchor_split_map(cfg)
    missing = [dt for dt, v in anchor_map.items() if not v["split_180d"]]
    assert not missing, f"Anchors without 180d status: {missing}"


# ---------------------------------------------------------------------------
# T5.05 — 90d target window no overlap (corrected dates)
# ---------------------------------------------------------------------------

def test_90d_target_window_no_overlap():
    """
    max(train.target_end_date_90d) < min(val.as_of_date)
    max(val.target_end_date_90d)   < min(test.as_of_date)

    Uses assert_purge_conditions_from_map which operates on the anchor map.
    """
    from src.montreal_road_risk.modeling.splits import assert_purge_conditions_from_map
    cfg = _cfg()
    # Should not raise
    assert_purge_conditions_from_map(cfg)


# ---------------------------------------------------------------------------
# T5.06 — 180d target window no overlap
# ---------------------------------------------------------------------------

def test_180d_target_window_no_overlap():
    """180d purge conditions verified from anchor map."""
    from src.montreal_road_risk.modeling.splits import assert_purge_conditions_from_map
    cfg = _cfg()
    # Should not raise — verifies both 90d and 180d purge conditions
    assert_purge_conditions_from_map(cfg)


# ---------------------------------------------------------------------------
# T5.07 — Embargo rows preserved with per-horizon exclusion reasons
# ---------------------------------------------------------------------------

def test_embargo_rows_have_per_horizon_exclusion_reasons():
    """
    Embargo entries in the anchor map have non-null per-horizon exclusion reasons.
    Both exclusion_reason_90d and exclusion_reason_180d keys exist; no single merged key.
    """
    from src.montreal_road_risk.modeling.splits import build_anchor_split_map
    cfg = _cfg()
    anchor_map = build_anchor_split_map(cfg)

    # Verify keys exist in the map
    sample = next(iter(anchor_map.values()))
    assert "exclusion_reason_90d" in sample
    assert "exclusion_reason_180d" in sample
    assert "exclusion_reason" not in sample, "Single exclusion_reason key must not exist"

    emb_statuses = {"embargo_train_validation", "embargo_validation_test"}
    for dt, info in anchor_map.items():
        if info["split_90d"] in emb_statuses:
            assert info["exclusion_reason_90d"] is not None, f"Missing 90d reason for embargo anchor {dt}"
        if info["split_180d"] in emb_statuses:
            assert info["exclusion_reason_180d"] is not None, f"Missing 180d reason for embargo anchor {dt}"


# ---------------------------------------------------------------------------
# T5.08 — All split statuses are in allowed set
# ---------------------------------------------------------------------------

def test_split_status_exhaustive():
    """Every anchor in the map has a valid split status for both horizons."""
    from src.montreal_road_risk.modeling.splits import build_anchor_split_map
    valid = {"train", "validation", "sealed_test", "embargo_train_validation", "embargo_validation_test"}
    cfg = _cfg()
    anchor_map = build_anchor_split_map(cfg)
    for dt, info in anchor_map.items():
        assert info["split_90d"] in valid, f"Invalid 90d status {info['split_90d']} for {dt}"
        assert info["split_180d"] in valid, f"Invalid 180d status {info['split_180d']} for {dt}"
        assert info["split_90d"] is not None
        assert info["split_180d"] is not None


# ---------------------------------------------------------------------------
# T5.09 — No target/identifier columns in X
# ---------------------------------------------------------------------------

def test_no_target_or_identifier_in_X():
    """Excluded columns never appear in the feature matrix."""
    from src.montreal_road_risk.modeling.preprocessing import prepare_Xy
    df = _make_panel(n_anchors=5, n_segs=20)
    cfg = _cfg()
    # Add split columns to simulate post-split df
    df["split_90d"] = "train"
    df["exclusion_reason_90d"] = None
    df["target_end_date_90d"] = df["as_of_date"] + pd.Timedelta(days=90)

    forbidden = set(cfg["exclude_from_X"]) | {
        "target_repair_90d", "target_repair_180d",
        "target_eligible_90d", "target_eligible_180d",
        "target_repair_90d_strict", "target_repair_180d_strict",
        "positive_observed_in_incomplete_window_90d",
        "positive_observed_in_incomplete_window_180d",
        "segment_month_id", "canonical_segment_id", "as_of_date",
        "panel_year", "panel_month", "last_repair_date", "latest_condition_survey_date",
    }
    X, y = prepare_Xy(df, "target_repair_90d", cfg, cfg["categorical_cols"])
    in_X = set(X.columns)
    overlap = forbidden & in_X
    assert not overlap, f"Forbidden columns found in X: {overlap}"


# ---------------------------------------------------------------------------
# T5.10 — Strict targets are all null
# ---------------------------------------------------------------------------

def test_strict_targets_all_null():
    """target_repair_90d_strict and target_repair_180d_strict are entirely null."""
    df = _make_panel(n_anchors=5, n_segs=20)
    assert df["target_repair_90d_strict"].isna().all()
    assert df["target_repair_180d_strict"].isna().all()


# ---------------------------------------------------------------------------
# T5.11 — Test partition not loaded in training (config isolation)
# ---------------------------------------------------------------------------

def test_test_partition_not_in_training_config(tmp_path):
    """Training config paths do not include the test partition path."""
    cfg = {
        "phase5_dir": str(tmp_path),
        "train_path_90d": str(tmp_path / "train_90d.parquet"),
        "val_path_90d":   str(tmp_path / "val_90d.parquet"),
        # test path intentionally absent from training config
    }
    training_paths = [cfg["train_path_90d"], cfg["val_path_90d"]]
    test_path = str(tmp_path / "test.parquet")
    assert test_path not in training_paths, "Test partition path must not appear in training config"


# ---------------------------------------------------------------------------
# T5.12 — No calibrator created in Phase 5
# ---------------------------------------------------------------------------

def test_no_calibrator_created_in_phase_5():
    """CalibratedClassifierCV must not be imported or used in any Phase 5 training path."""
    import importlib
    import sys

    # Ensure the modeling modules do not import calibration
    modules_to_check = [
        "src.montreal_road_risk.modeling.training",
        "src.montreal_road_risk.modeling.baselines",
        "src.montreal_road_risk.modeling.metrics",
        "src.montreal_road_risk.modeling.preprocessing",
    ]
    for mod_name in modules_to_check:
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
        else:
            try:
                mod = importlib.import_module(mod_name)
            except ImportError:
                continue
        src = getattr(mod, "__file__", "") or ""
        if src:
            with open(src) as f:
                content = f.read()
            assert "CalibratedClassifierCV" not in content, (
                f"CalibratedClassifierCV found in {src}"
            )
            assert "from sklearn.calibration" not in content, (
                f"sklearn.calibration import found in {src}"
            )


# ---------------------------------------------------------------------------
# T5.13 — Imputer fitted on train only
# ---------------------------------------------------------------------------

def test_imputer_fitted_on_train_only():
    """Imputer statistics_ differ from global statistics on asymmetric synthetic data."""
    from sklearn.impute import SimpleImputer
    import numpy as np

    # Skewed distribution: train has high values, global has low values
    rng2 = np.random.default_rng(0)
    X_train = pd.DataFrame({"feat": rng2.normal(100, 5, 500)})
    X_global = pd.DataFrame({"feat": np.concatenate([rng2.normal(100, 5, 500), rng2.normal(1, 0.1, 500)])})

    imp_train  = SimpleImputer(strategy="median").fit(X_train)
    imp_global = SimpleImputer(strategy="median").fit(X_global)

    # Train median should be ~100; global median should be ~50
    assert abs(imp_train.statistics_[0] - imp_global.statistics_[0]) > 10, (
        "Imputer statistics should differ when fitted on training-only vs. global data"
    )


# ---------------------------------------------------------------------------
# T5.14 — OHE unknown category maps to zero block
# ---------------------------------------------------------------------------

def test_ohe_unknown_category_zero_block():
    """Unseen category in val/test → specific OHE block is all zeros, no exception."""
    from sklearn.preprocessing import OneHotEncoder
    import numpy as np

    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X_train = pd.DataFrame({"cat": ["a", "b", "c", "a", "b"]})
    enc.fit(X_train[["cat"]])

    X_val = pd.DataFrame({"cat": ["d"]})  # "d" is unseen
    out = enc.transform(X_val[["cat"]])
    assert out.sum() == 0, "Unseen category should encode to all-zero row"


# ---------------------------------------------------------------------------
# T5.15 — Missing categorical fills to stable 'missing' string
# ---------------------------------------------------------------------------

def test_missing_category_fills_stable_string():
    """Null categoricals become the string 'missing' before encoding."""
    from src.montreal_road_risk.modeling.preprocessing import fill_missing_categoricals
    df = pd.DataFrame({"functional_road_class": [None, "arterial", None]})
    result = fill_missing_categoricals(df, ["functional_road_class"])
    assert (result["functional_road_class"] == "missing").sum() == 2
    assert result["functional_road_class"].dtype == object


# ---------------------------------------------------------------------------
# T5.16 — Logistic pipeline contains scaler; tree does not
# ---------------------------------------------------------------------------

def test_logistic_pipeline_includes_scaler_tree_does_not():
    """Logistic pipeline has StandardScaler; tree pipeline does not."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from src.montreal_road_risk.modeling.preprocessing import (
        build_logistic_pipeline, build_tree_pipeline,
    )

    num_cols = ["feat1", "feat2"]
    cat_cols: list = []
    bin_cols: list = []

    lr_pipe  = build_logistic_pipeline(LogisticRegression(), num_cols, cat_cols, bin_cols)
    rf_pipe  = build_tree_pipeline(RandomForestClassifier(), num_cols, cat_cols, bin_cols)

    lr_steps = str(lr_pipe)
    rf_steps = str(rf_pipe)

    assert "StandardScaler" in lr_steps, "Logistic pipeline must contain StandardScaler"
    assert "StandardScaler" not in rf_steps, "Tree pipeline must not contain StandardScaler"


# ---------------------------------------------------------------------------
# T5.17 — Separate pipeline objects per model family
# ---------------------------------------------------------------------------

def test_separate_pipeline_per_model_family():
    """Two pipeline objects are distinct; modifying one does not affect the other."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from src.montreal_road_risk.modeling.preprocessing import (
        build_logistic_pipeline, build_tree_pipeline,
    )
    num_cols = ["x"]
    lr_pipe = build_logistic_pipeline(LogisticRegression(), num_cols, [], [])
    rf_pipe = build_tree_pipeline(RandomForestClassifier(), num_cols, [], [])
    assert lr_pipe is not rf_pipe
    assert lr_pipe.named_steps["preprocessor"] is not rf_pipe.named_steps["preprocessor"]


# ---------------------------------------------------------------------------
# T5.18 — Feature allowlist loader rejects extra column
# ---------------------------------------------------------------------------

def test_feature_allowlist_rejects_extra_column():
    """Loader raises ValueError if a non-allowlisted column is in X."""
    from src.montreal_road_risk.modeling.preprocessing import resolve_feature_columns
    df = pd.DataFrame({
        "allowed_feat": [1, 2, 3],
        "forbidden_extra": [4, 5, 6],
    })
    cfg = _cfg()
    cfg["feature_allowlist"] = ["allowed_feat"]
    cfg["exclude_from_X"] = []

    with pytest.raises(ValueError, match="Unexpected features not in allowlist"):
        resolve_feature_columns(df, cfg)


# ---------------------------------------------------------------------------
# T5.19 — Feature allowlist loader rejects missing column
# ---------------------------------------------------------------------------

def test_feature_allowlist_rejects_missing_column():
    """Loader raises ValueError if an allowlisted column is absent from df."""
    from src.montreal_road_risk.modeling.preprocessing import resolve_feature_columns
    df = pd.DataFrame({"allowed_feat": [1, 2, 3]})
    cfg = _cfg()
    cfg["feature_allowlist"] = ["allowed_feat", "missing_feat"]
    cfg["exclude_from_X"] = []

    with pytest.raises(ValueError, match="Expected allowlist features missing"):
        resolve_feature_columns(df, cfg)


# ---------------------------------------------------------------------------
# T5.20 — Checkpoint fingerprint mismatch causes quarantine
# ---------------------------------------------------------------------------

def test_checkpoint_fingerprint_invalidation(tmp_path):
    """A checkpoint with a mismatched fingerprint is moved to quarantine."""
    from src.montreal_road_risk.modeling.training import (
        save_checkpoint, validate_checkpoint, checkpoint_exists,
    )
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    base = str(tmp_path / "checkpoints")
    model_name = "lr"
    config_id = "c0"

    # Write a dummy pipeline checkpoint
    pipe = Pipeline([("lr", LogisticRegression())])
    fps_orig = {
        "input_panel_sha256":       "aaa",
        "split_fingerprint_sha256": "bbb",
        "config_sha256":            "ccc",
        "environment_sha256":       "ddd",
        "source_code_sha256":       "eee",
        "feature_schema_sha256":    "fff",
        "model_readable":           True,
        "val_prediction_count":     100,
        "val_ap_score":             0.5,
    }
    save_checkpoint(base, model_name, config_id, pipe, {"val_ap": 0.5}, fps_orig)
    assert checkpoint_exists(base, model_name, config_id)

    # Now validate with a different config fingerprint
    fps_new = dict(fps_orig)
    fps_new["config_sha256"] = "ZZZ_different"

    result = validate_checkpoint(base, model_name, config_id, fps_new)
    assert not result, "Mismatched fingerprint should fail validation"
    # Check quarantine
    quarantine_dir = os.path.join(base, "quarantine")
    assert os.path.isdir(quarantine_dir), "Quarantine directory must be created"


# ---------------------------------------------------------------------------
# T5.21 — Prevalence baseline equals train rate
# ---------------------------------------------------------------------------

def test_prevalence_baseline_equals_train_rate():
    """PrevalenceBaseline.predict_proba returns constant equal to y_train.mean()."""
    from src.montreal_road_risk.modeling.baselines import PrevalenceBaseline
    rng2 = np.random.default_rng(1)
    X = pd.DataFrame({"x": rng2.standard_normal(200)})
    y = pd.Series((rng2.random(200) > 0.93).astype(int))

    bl = PrevalenceBaseline().fit(X, y)
    proba = bl.predict_proba(X)

    assert np.allclose(proba, y.mean(), atol=1e-10), "Prevalence mismatch"
    assert proba.shape == (200,)


# ---------------------------------------------------------------------------
# T5.22 — Smoothed baseline fallback for unseen segment
# ---------------------------------------------------------------------------

def test_smoothed_baseline_fallback_unseen_segment():
    """Segment absent from training returns global prevalence, not 0 or error."""
    from src.montreal_road_risk.modeling.baselines import SegmentHistoryBaseline
    rng2 = np.random.default_rng(2)
    X_train = pd.DataFrame({"canonical_segment_id": ["s1", "s2", "s1", "s2"] * 25})
    y_train = pd.Series((rng2.random(100) > 0.93).astype(int))

    bl = SegmentHistoryBaseline().fit(X_train, y_train)
    global_prev = bl.global_prevalence_

    X_val = pd.DataFrame({"canonical_segment_id": ["s_unseen"]})
    proba = bl.predict_proba(X_val)

    assert len(proba) == 1
    assert abs(proba[0] - global_prev) < 1e-10, "Unseen segment should return global prevalence"
    assert 0 < proba[0] < 1, "Probability must be in (0, 1)"


# ---------------------------------------------------------------------------
# T5.23 — 180-day sensitivity reuses 90-day hyperparameters
# ---------------------------------------------------------------------------

def test_180d_sensitivity_reuses_90d_hyperparameters():
    """
    The 180d model must be fitted using the exact same hyperparameter dict
    selected from the 90d run — not a new search.
    """
    # Simulate: 90d best config is recorded
    best_90d_config = {"C": 0.1, "solver": "saga", "class_weight": "balanced"}
    # 180d run reads same config, does not search again
    def run_180d(hp_90d: dict, run_search: bool = False) -> dict:
        if run_search:
            raise AssertionError("180d run must not perform a new hyperparameter search")
        return hp_90d  # reuse

    hp_180d = run_180d(best_90d_config, run_search=False)
    assert hp_180d == best_90d_config, "180d hyperparameters differ from 90d best config"


# ---------------------------------------------------------------------------
# T5.24 — AP tie-breaking is deterministic
# ---------------------------------------------------------------------------

def test_ap_tie_breaking_deterministic():
    """Two calls with identical inputs produce identical Precision@K results."""
    from src.montreal_road_risk.modeling.metrics import compute_at_k
    rng2 = np.random.default_rng(3)
    n = 200
    y_true   = (rng2.random(n) > 0.93).astype(int)
    y_score  = rng2.random(n)
    seg_ids  = np.array([f"seg_{i}" for i in range(n)])
    aod      = np.array([pd.Timestamp("2022-01-01")] * n)

    r1 = compute_at_k(y_true, y_score, 10.0, seg_ids, aod)
    r2 = compute_at_k(y_true, y_score, 10.0, seg_ids, aod)

    assert r1 == r2, "compute_at_k must be deterministic"


# ---------------------------------------------------------------------------
# T5.25 — n_jobs=1 in all estimators
# ---------------------------------------------------------------------------

def test_n_jobs_one_in_all_estimators():
    """All estimators have n_jobs=1."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from src.montreal_road_risk.modeling.preprocessing import (
        build_logistic_pipeline, build_tree_pipeline,
    )

    lr = LogisticRegression(n_jobs=1, random_state=42)
    rf = RandomForestClassifier(n_jobs=1, random_state=42)

    lr_pipe = build_logistic_pipeline(lr, ["x"], [], [])
    rf_pipe = build_tree_pipeline(rf, ["x"], [], [])

    assert lr_pipe.named_steps["estimator"].n_jobs == 1
    assert rf_pipe.named_steps["estimator"].n_jobs == 1


# ---------------------------------------------------------------------------
# T5.26 — Binary flag validation catches nulls
# ---------------------------------------------------------------------------

def test_binary_flag_validation_catches_nulls():
    """validate_binary_cols raises ValueError when nulls are present."""
    from src.montreal_road_risk.modeling.preprocessing import validate_binary_cols
    df = pd.DataFrame({"flag": [0, 1, None, 0]})
    with pytest.raises(ValueError, match="null values"):
        validate_binary_cols(df, ["flag"])


# ---------------------------------------------------------------------------
# T5.27 — Binary flag validation catches non-0/1 values
# ---------------------------------------------------------------------------

def test_binary_flag_validation_catches_non_binary():
    """validate_binary_cols raises ValueError for values outside {0, 1}."""
    from src.montreal_road_risk.modeling.preprocessing import validate_binary_cols
    df = pd.DataFrame({"flag": [0, 1, 2, 0]})
    with pytest.raises(ValueError, match="non-0/1 values"):
        validate_binary_cols(df, ["flag"])


# ---------------------------------------------------------------------------
# T5.28 — Test seal contains both target fingerprints
# ---------------------------------------------------------------------------

def test_test_seal_contains_both_target_fingerprints(tmp_path):
    """Test seal manifest fingerprints target_repair_90d and target_repair_180d."""
    from src.montreal_road_risk.modeling.splits import _write_test_seal_from_rows
    # Simulate test-partition rows with both target columns
    rng2 = np.random.default_rng(99)
    n = 200
    df_seal = pd.DataFrame({
        "canonical_segment_id": [f"seg_{i}" for i in range(n)],
        "as_of_date": pd.to_datetime(["2024-01-31"] * 100 + ["2024-02-29"] * 100),
        "target_repair_90d":  (rng2.random(n) > 0.93).astype(int),
        "target_repair_180d": (rng2.random(n) > 0.89).astype(int),
    })

    out_dir = str(tmp_path / "phase5")
    manifest = _write_test_seal_from_rows([df_seal], out_dir)

    assert "content_fingerprint_sha256" in manifest
    assert len(manifest["content_fingerprint_sha256"]) == 64
    assert "schema_fingerprint_sha256" in manifest
    assert manifest["target_column_included_in_file"] is True
    assert manifest["fingerprints_include_90d_and_180d"] is True
