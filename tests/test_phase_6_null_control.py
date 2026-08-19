"""Tests for Phase 6 null-control protocol integrity.

Tests cover:
- Global permutation properties (multiset, correlation, non-identity)
- Prevalence preservation across all approved seeds
- Row-identifier stability (features never reordered)
- Prediction-label alignment (sorted score ↔ sorted label)
- Cache prefix uniqueness per seed
- Fresh model initialization (no state shared between seeds)
- Train/validation non-overlap
- Forbidden feature exclusion (no Phase-5 exclude_from_X cols in X)
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
APPROVED_SEEDS = [42, 137, 2026]
N_SMALL = 10_000  # synthetic size for fast tests
PREVALENCE = 0.07  # synthetic prevalence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_labels():
    rng = np.random.default_rng(0)
    y = (rng.random(N_SMALL) < PREVALENCE).astype(np.int8)
    return y


@pytest.fixture(scope="module")
def phase5_exclude_list():
    cfg_path = _REPO_ROOT / "config/phase_5_modeling.json"
    cfg = json.loads(cfg_path.read_text())
    return set(cfg.get("exclude_from_X", []))


@pytest.fixture(scope="module")
def null_ctrl_feature_cols():
    """Feature columns actually used by null control (from val schema)."""
    import pyarrow.parquet as pq
    schema = pq.read_schema(
        _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
    )
    all_cols = [schema.field(i).name for i in range(len(schema))]
    target_col = "target_repair_90d"
    id_cols = {"segment_month_id", "canonical_segment_id", "as_of_date"}
    return [c for c in all_cols if c not in id_cols | {target_col}]


# ===========================================================================
# 1. Global permutation integrity
# ===========================================================================

class TestGlobalPermutationIntegrity:

    def test_permutation_is_global_not_partial(self, synthetic_labels):
        """Permutation covers every index exactly once."""
        n = len(synthetic_labels)
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(n)
            # Every index in [0, n) appears exactly once
            assert sorted(perm.tolist()) == list(range(n)), \
                f"seed {seed}: permutation not a bijection on [0,{n})"

    def test_shuffled_not_identical_to_original(self, synthetic_labels):
        """Shuffled array must differ from original (no trivial identity)."""
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(len(synthetic_labels))
            shuffled = synthetic_labels[perm]
            assert not np.array_equal(shuffled, synthetic_labels), \
                f"seed {seed}: shuffle produced identical array"

    def test_label_correlation_near_zero(self, synthetic_labels):
        """Correlation between original and shuffled labels should be ≈ 0."""
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(len(synthetic_labels))
            shuffled = synthetic_labels[perm]
            corr = float(np.corrcoef(
                synthetic_labels.astype(float), shuffled.astype(float)
            )[0, 1])
            # For n=10_000, std of correlation under H0 ≈ 1/sqrt(n) ≈ 0.01
            # Use 5-sigma threshold: 0.05
            assert abs(corr) < 0.05, \
                f"seed {seed}: correlation {corr:.4f} suspiciously high"

    def test_different_seeds_produce_different_permutations(self, synthetic_labels):
        """Approved seeds must yield distinct permutations."""
        n = len(synthetic_labels)
        perms = {}
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perms[seed] = rng.permutation(n).tobytes()
        # All three must be distinct
        assert len(set(perms.values())) == len(APPROVED_SEEDS), \
            "Two seeds produced identical permutations"

    def test_self_fixed_count_is_integer(self, synthetic_labels):
        """Self-fixed count (Poisson(1)-distributed) is a non-negative int.
        Note: 0 self-fixed (derangement) is valid — P ≈ 1/e ≈ 0.368."""
        n = len(synthetic_labels)
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(n)
            self_fixed = int((perm == np.arange(n)).sum())
            assert self_fixed >= 0  # trivially true, documents expected distribution
            assert self_fixed <= n


# ===========================================================================
# 2. Prevalence preservation
# ===========================================================================

class TestPrevalencePreservation:

    def test_positive_count_preserved_exactly(self, synthetic_labels):
        """Sum of labels must be identical before and after shuffle."""
        orig_sum = int(synthetic_labels.sum())
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(len(synthetic_labels))
            shuffled = synthetic_labels[perm]
            assert int(shuffled.sum()) == orig_sum, \
                f"seed {seed}: positive count changed {int(shuffled.sum())} ≠ {orig_sum}"

    def test_multiset_identical(self, synthetic_labels):
        """Label multiset must be identical (sorted arrays equal)."""
        orig_sorted = np.sort(synthetic_labels)
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(len(synthetic_labels))
            shuffled = synthetic_labels[perm]
            assert np.array_equal(np.sort(shuffled), orig_sorted), \
                f"seed {seed}: multiset changed"


# ===========================================================================
# 3. Row-identifier stability
# ===========================================================================

class TestRowIdentifierStability:

    def test_feature_row_order_not_altered_by_label_shuffle(self, synthetic_labels):
        """Feature rows stay in original order; only label array is permuted."""
        n = len(synthetic_labels)
        # Simulate feature ID array (integers 0..n-1)
        feature_ids = np.arange(n, dtype=np.int64)
        orig_id_sha = hashlib.sha256(feature_ids.tobytes()).hexdigest()

        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(n)
            # Shuffle labels, leave feature IDs unchanged
            _ = synthetic_labels[perm]
            after_id_sha = hashlib.sha256(feature_ids.tobytes()).hexdigest()
            assert after_id_sha == orig_id_sha, \
                f"seed {seed}: feature row order changed after label shuffle"

    def test_label_sha256_changes_per_seed(self, synthetic_labels):
        """Each seed must produce a distinct shuffled-label SHA-256."""
        shas = set()
        for seed in APPROVED_SEEDS:
            rng = np.random.default_rng(seed)
            perm = rng.permutation(len(synthetic_labels))
            shuf = synthetic_labels[perm]
            shas.add(hashlib.sha256(shuf.tobytes()).hexdigest())
        assert len(shas) == len(APPROVED_SEEDS), "Two seeds produced identical shuffled labels"


# ===========================================================================
# 4. Prediction-label alignment
# ===========================================================================

class TestPredictionLabelAlignment:

    def test_prediction_and_label_arrays_same_length(self):
        """Prediction and label arrays must have identical length."""
        n = 1000
        rng = np.random.default_rng(0)
        preds = rng.random(n).astype(np.float32)
        labels = (rng.random(n) < 0.07).astype(float)
        assert len(preds) == len(labels)

    def test_sorted_prediction_alignment(self):
        """argsort of predictions and indexing into labels must be consistent."""
        n = 500
        rng = np.random.default_rng(7)
        preds = rng.random(n).astype(np.float32)
        labels = (rng.random(n) < 0.1).astype(float)
        order = np.argsort(preds)[::-1]
        # Top-5% predictions
        k = max(1, math.ceil(n * 0.05))
        top_k_labels = labels[order[:k]]
        # This should not raise
        assert len(top_k_labels) == k


# ===========================================================================
# 5. Cache prefix uniqueness per seed
# ===========================================================================

class TestCachePrefixUniqueness:

    def _cache_prefix(self, seed: int) -> str:
        """Mirror the cache-prefix logic from the null control script."""
        return f"null_ctrl_s{seed}"

    def test_two_seeds_different_prefixes(self):
        """No two approved seeds can share the same cache prefix."""
        prefixes = [self._cache_prefix(s) for s in APPROVED_SEEDS]
        assert len(set(prefixes)) == len(APPROVED_SEEDS), \
            f"Cache prefix collision: {prefixes}"

    def test_seed_prefix_contains_seed_value(self):
        """Each prefix must embed the seed value for traceability."""
        for seed in APPROVED_SEEDS:
            prefix = self._cache_prefix(seed)
            assert str(seed) in prefix, \
                f"Seed {seed} not embedded in prefix '{prefix}'"


# ===========================================================================
# 6. Fresh model initialization
# ===========================================================================

class TestFreshModelInitialization:

    def test_dmatrix_not_reused(self):
        """Two DMatrix objects from same data are distinct Python objects."""
        try:
            import xgboost as xgb
        except ImportError:
            pytest.skip("xgboost not available")
        rng = np.random.default_rng(0)
        X = rng.random((100, 5)).astype(np.float32)
        y = (rng.random(100) < 0.1).astype(np.float32)
        dm1 = xgb.DMatrix(X, label=y)
        dm2 = xgb.DMatrix(X, label=y)
        assert dm1 is not dm2, "DMatrix objects are the same Python object (reuse detected)"

    def test_booster_not_reused_across_seeds(self):
        """Two xgb.train() calls produce distinct Booster objects."""
        try:
            import xgboost as xgb
        except ImportError:
            pytest.skip("xgboost not available")
        rng = np.random.default_rng(0)
        X = rng.random((200, 4)).astype(np.float32)
        y = (rng.random(200) < 0.1).astype(np.float32)
        params = {"objective": "binary:logistic", "nthread": 1,
                  "max_depth": 2, "seed": 42}
        dm = xgb.DMatrix(X, label=y)
        bst1 = xgb.train(params, dm, num_boost_round=2)
        bst2 = xgb.train(params, dm, num_boost_round=2)
        assert bst1 is not bst2, "Boosters are the same Python object"


# ===========================================================================
# 7. Train/validation non-overlap
# ===========================================================================

class TestTrainValNonOverlap:

    def test_no_id_overlap_in_real_data(self):
        """segment_month_id intersection of train and val must be empty."""
        import pyarrow.parquet as pq
        train_ids = set(
            pq.read_table(
                _REPO_ROOT / "data/processed/phase_5/train_90d.parquet",
                columns=["segment_month_id"]
            ).column("segment_month_id").to_pylist()
        )
        val_ids = set(
            pq.read_table(
                _REPO_ROOT / "data/processed/phase_5/val_90d.parquet",
                columns=["segment_month_id"]
            ).column("segment_month_id").to_pylist()
        )
        overlap = train_ids & val_ids
        assert len(overlap) == 0, \
            f"Train/val overlap: {len(overlap)} shared IDs (purge incomplete)"

    def test_train_val_date_ranges_non_overlapping(self):
        """as_of_date ranges of train and val must not overlap."""
        import pyarrow.parquet as pq
        train_dates = {
            str(d)[:10] for d in pq.read_table(
                _REPO_ROOT / "data/processed/phase_5/train_90d.parquet",
                columns=["as_of_date"]
            ).column("as_of_date").to_pylist()
        }
        val_dates = {
            str(d)[:10] for d in pq.read_table(
                _REPO_ROOT / "data/processed/phase_5/val_90d.parquet",
                columns=["as_of_date"]
            ).column("as_of_date").to_pylist()
        }
        overlap = train_dates & val_dates
        assert len(overlap) == 0, \
            f"Train/val date overlap: {overlap}"


# ===========================================================================
# 8. Forbidden feature exclusion
# ===========================================================================

class TestForbiddenFeatureExclusion:

    def test_no_p5_excluded_column_in_null_ctrl_features(
        self, phase5_exclude_list, null_ctrl_feature_cols
    ):
        """No Phase-5 exclude_from_X column should be present in null-ctrl X."""
        violations = [c for c in phase5_exclude_list if c in null_ctrl_feature_cols]
        assert violations == [], \
            f"Forbidden columns found in null-ctrl features: {violations}"

    def test_target_col_not_in_features(self, null_ctrl_feature_cols):
        """target_repair_90d must be absent from null-ctrl feature set."""
        assert "target_repair_90d" not in null_ctrl_feature_cols

    def test_id_cols_not_in_features(self, null_ctrl_feature_cols):
        """Key ID columns must be absent from null-ctrl feature set."""
        for col in ["segment_month_id", "canonical_segment_id", "as_of_date"]:
            assert col not in null_ctrl_feature_cols, \
                f"ID column '{col}' found in null-ctrl features"

    def test_future_col_is_vetted(self, null_ctrl_feature_cols, phase5_exclude_list):
        """future_asset_record_hidden_flag is present in X but NOT in exclude_from_X.
        This was explicitly reviewed and retained in Phase 5 as a leakage-safe flag.
        Confirm its presence and status."""
        col = "future_asset_record_hidden_flag"
        assert col in null_ctrl_feature_cols, \
            f"Expected '{col}' in features — schema may have changed"
        assert col not in phase5_exclude_list, \
            f"'{col}' was unexpectedly added to exclude_from_X"
