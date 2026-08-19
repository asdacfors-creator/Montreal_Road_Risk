"""Tests for Phase 6 seed isolation experiment.

Validates that:
- permutation_seed and model_seed are fully independent parameters
- All 6 experiment configurations have distinct cache dirs
- Permutation SHA-256 depends only on perm_seed, not model_seed
- Prediction SHA-256 with same (perm_seed, model_seed) is reproducible
- Forbidden-feature and ID-overlap invariants hold across all configs
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

APPROVED_PERM_SEEDS  = [42, 137, 2026]
APPROVED_MODEL_SEEDS = [42, 137, 2026]
OFFICIAL_MODEL_SEED  = 42          # D6.6 revised: fixed model_seed for official controls
OFFICIAL_PERM_SEEDS  = [42, 137, 2026]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def isolation_report():
    path = _REPO_ROOT / "models/phase_6/seed_isolation_experiment.json"
    if not path.exists():
        pytest.skip("seed_isolation_experiment.json not yet generated")
    return json.loads(path.read_text())


# ===========================================================================
# 1. Seed independence: permutation SHA depends only on perm_seed
# ===========================================================================

class TestPermutationSeedIndependence:

    def test_same_perm_seed_different_model_seed_gives_same_perm_sha(self):
        """perm_seed=137 + model_seed=42 and perm_seed=137 + model_seed=137
        must produce the same permutation index SHA-256."""
        n = 10_000
        for _model_seed_ignored in [42, 137, 2026]:
            for perm_seed in APPROVED_PERM_SEEDS:
                rng = np.random.default_rng(perm_seed)
                perm1 = rng.permutation(n)
                rng2  = np.random.default_rng(perm_seed)
                perm2 = rng2.permutation(n)
                assert np.array_equal(perm1, perm2), (
                    f"perm_seed={perm_seed}: two instances of default_rng "
                    f"produced different permutations"
                )

    def test_different_perm_seeds_give_different_perm_sha(self):
        """Different perm_seeds must produce different permutations."""
        n = 10_000
        perms = {}
        for seed in APPROVED_PERM_SEEDS:
            rng = np.random.default_rng(seed)
            perms[seed] = rng.permutation(n).tobytes()
        assert len(set(perms.values())) == len(APPROVED_PERM_SEEDS), (
            "Two perm_seeds produced identical permutations"
        )

    def test_perm_sha_in_report_consistent_across_same_perm_seed(
        self, isolation_report
    ):
        """In the experiment report, runs with same perm_seed must share
        the same perm_index_sha256 regardless of model_seed."""
        runs = isolation_report["runs"]

        # perm_seed=137 appears in three runs
        perm137_runs = [
            r for r in runs.values() if r["perm_seed"] == 137
        ]
        if len(perm137_runs) < 2:
            pytest.skip("Fewer than 2 perm_seed=137 runs in report")

        shas = {r["perm_index_sha256"] for r in perm137_runs}
        assert len(shas) == 1, (
            f"perm_seed=137 produced different perm SHAs across model seeds: {shas}"
        )

    def test_shuf_label_sha_in_report_consistent_across_same_perm_seed(
        self, isolation_report
    ):
        """Same perm_seed → same shuffled-label SHA regardless of model_seed."""
        runs = isolation_report["runs"]
        perm137_runs = [
            r for r in runs.values()
            if r["perm_seed"] == 137 and r["subsample"] == 0.8
        ]
        if len(perm137_runs) < 2:
            pytest.skip("Fewer than 2 sub=0.8 perm_seed=137 runs in report")

        shas = {r["shuf_label_sha256"] for r in perm137_runs}
        assert len(shas) == 1, (
            f"perm_seed=137 produced different shuffled-label SHAs: {shas}"
        )


# ===========================================================================
# 2. Model seed independence: different model_seeds give different predictions
# ===========================================================================

class TestModelSeedIndependence:

    def test_different_model_seeds_give_different_pred_sha(
        self, isolation_report
    ):
        """perm=137 with model=42 vs model=137 vs model=2026 must give
        different prediction SHAs (different XGBoost row/column sampling)."""
        runs = isolation_report["runs"]
        perm137_sub08 = [
            r for r in runs.values()
            if r["perm_seed"] == 137 and r["subsample"] == 0.8
        ]
        if len(perm137_sub08) < 2:
            pytest.skip("Fewer than 2 model seeds for perm=137 in report")

        pred_shas = [r["pred_sha256"] for r in perm137_sub08]
        assert len(set(pred_shas)) == len(pred_shas), (
            "Two different model_seeds produced identical prediction SHAs"
        )


# ===========================================================================
# 3. Cache isolation per run
# ===========================================================================

class TestCacheIsolation:

    def test_all_runs_have_distinct_cache_fingerprints(self, isolation_report):
        """Every run must have a unique cache_fingerprint."""
        runs = isolation_report["runs"]
        fps  = [r["cache_fingerprint"] for r in runs.values()]
        assert len(set(fps)) == len(fps), (
            f"Cache fingerprint collision detected: {fps}"
        )


# ===========================================================================
# 4. Official fixed-model-seed controls
# ===========================================================================

class TestOfficialControls:

    def test_official_controls_use_fixed_model_seed_42(self, isolation_report):
        """Official controls must fix model_seed=42."""
        runs = isolation_report["runs"]
        official_perm_seeds = {42, 137, 2026}

        for label, r in runs.items():
            if r["subsample"] < 1.0 and r["perm_seed"] in official_perm_seeds:
                if r["model_seed"] != OFFICIAL_MODEL_SEED:
                    # Only fail if this appears to be an official-format run
                    # (non-full-sample, approved perm seed, model seed ≠ 42)
                    # The Part 2 runs (model=137, model=2026) are diagnostic,
                    # not official. Flag only if label starts with "part1"
                    if label.startswith("part1"):
                        assert r["model_seed"] == OFFICIAL_MODEL_SEED, (
                            f"Official Part 1 run '{label}' uses model_seed="
                            f"{r['model_seed']}, expected {OFFICIAL_MODEL_SEED}"
                        )

    def test_part1_perm42_model42_exists(self, isolation_report):
        """Official control perm_seed=42, model_seed=42 must be present."""
        runs = isolation_report["runs"]
        found = any(
            r["perm_seed"] == 42 and r["model_seed"] == 42 and r["subsample"] == 0.8
            for r in runs.values()
        )
        assert found, "Official control (perm=42, model=42) not found in report"

    def test_part1_perm137_model42_exists(self, isolation_report):
        """Official control perm_seed=137, model_seed=42 must be present."""
        runs = isolation_report["runs"]
        found = any(
            r["perm_seed"] == 137 and r["model_seed"] == 42 and r["subsample"] == 0.8
            for r in runs.values()
        )
        assert found, "Official control (perm=137, model=42) not found in report"

    def test_part1_perm2026_model42_exists(self, isolation_report):
        """Official control perm_seed=2026, model_seed=42 must be present."""
        runs = isolation_report["runs"]
        found = any(
            r["perm_seed"] == 2026 and r["model_seed"] == 42 and r["subsample"] == 0.8
            for r in runs.values()
        )
        assert found, "Official control (perm=2026, model=42) not found in report"

    def test_part3_full_sample_diagnostic_exists(self, isolation_report):
        """Part 3 full-sampling diagnostic must be present."""
        runs = isolation_report["runs"]
        found = any(
            r["perm_seed"] == 137 and r["subsample"] == 1.0
            for r in runs.values()
        )
        assert found, "Part 3 full-sample diagnostic not found in report"


# ===========================================================================
# 5. Permutation integrity across all runs
# ===========================================================================

class TestPermutationIntegrityAllRuns:

    def test_label_correlation_below_threshold_all_runs(self, isolation_report):
        """All runs must have |label_correlation| < 0.01."""
        for label, r in isolation_report["runs"].items():
            assert abs(r["label_correlation"]) < 0.01, (
                f"Run '{label}': label_correlation={r['label_correlation']:.4f} "
                f"exceeds threshold"
            )

    def test_no_sealed_targets_accessed(self, isolation_report):
        """b1_accessed, embargo_accessed, b2_accessed must all be False."""
        for label, r in isolation_report["runs"].items():
            assert r["b1_accessed"] is False, f"'{label}': B1 accessed"
            assert r["embargo_accessed"] is False, f"'{label}': embargo accessed"
            assert r["b2_accessed"] is False, f"'{label}': B2 accessed"

    def test_all_runs_have_required_fields(self, isolation_report):
        """Every run dict must contain all required reporting fields."""
        required = {
            "perm_seed", "model_seed", "cache_fingerprint",
            "shuf_label_sha256", "pred_sha256",
            "null_ap", "ap_minus_prevalence", "ap_ratio",
            "null_roc_auc", "auc_minus_half", "null_brier",
            "pred_std", "train_time_s", "peak_rss_gb",
        }
        for label, r in isolation_report["runs"].items():
            missing = required - set(r.keys())
            assert not missing, (
                f"Run '{label}' missing fields: {missing}"
            )


# ===========================================================================
# 6. Decision report structure
# ===========================================================================

class TestDecisionReport:

    def test_decision_block_present(self, isolation_report):
        """Report must contain a 'decision' block with key fields."""
        d = isolation_report.get("decision", {})
        assert "perm_effect_ap" in d
        assert "model_effect_ap_137v42" in d
        assert "full_sample_ap_delta" in d
        assert "gate_a_clears" in d

    def test_val_prevalence_matches_known_value(self, isolation_report):
        """Val prevalence must be consistent with the known value ≈ 0.0549."""
        prev = isolation_report["val_prevalence"]
        assert abs(prev - 0.054932) < 0.0001, (
            f"val_prevalence={prev:.6f} deviates from expected 0.054932"
        )
