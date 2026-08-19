"""Phase 7 target-free model interpretation package for Montreal Road Risk Assessment."""

from montreal_road_risk.interpretation.plots import (
    plot_beeswarm_summary,
    plot_dependence,
    plot_global_importance_bar,
)
from montreal_road_risk.interpretation.reconciliation import (
    FEATURE_NOTES,
    aggregate_importance_by_source_feature,
    aggregate_shap_matrix_to_source_features,
    build_feature_name_mapping,
)
from montreal_road_risk.interpretation.records import (
    build_top10_explanation_records,
)
from montreal_road_risk.interpretation.shap_engine import (
    MANDATORY_CAUSALITY_STATEMENT,
    StreamingSHAPAccumulator,
    check_memory_limit,
    compute_tree_contributions_batch,
    verify_additivity,
    verify_anchor_allowlist,
    verify_target_free_schema,
)
from montreal_road_risk.interpretation.stability import (
    compute_sample_stability,
    draw_stratified_sample,
)
from montreal_road_risk.interpretation.subgroup import (
    summarize_target_free_subgroups,
)

__all__ = [
    "MANDATORY_CAUSALITY_STATEMENT",
    "FEATURE_NOTES",
    "StreamingSHAPAccumulator",
    "check_memory_limit",
    "compute_tree_contributions_batch",
    "verify_anchor_allowlist",
    "verify_additivity",
    "verify_target_free_schema",
    "build_feature_name_mapping",
    "aggregate_importance_by_source_feature",
    "aggregate_shap_matrix_to_source_features",
    "draw_stratified_sample",
    "compute_sample_stability",
    "summarize_target_free_subgroups",
    "build_top10_explanation_records",
    "plot_global_importance_bar",
    "plot_beeswarm_summary",
    "plot_dependence",
]
