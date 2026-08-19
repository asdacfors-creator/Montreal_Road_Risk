"""Page 1 — Executive Overview Page for Phase 8 Dashboard."""

from __future__ import annotations

import streamlit as st

from montreal_road_risk.dashboard.data_loader import (
    load_dashboard_data_mart,
    load_phase6_aggregate_results,
)
from montreal_road_risk.dashboard.theme import apply_enterprise_theme

st.set_page_config(page_title="Executive Overview | Montreal Road Risk", page_icon="📊", layout="wide")
apply_enterprise_theme()

st.title("📊 Executive Overview — Operational Risk Summary")

# Load data & aggregate results
with st.spinner("Loading executive overview data..."):
    df_mart = load_dashboard_data_mart()
    p6_results = load_phase6_aggregate_results()

eval_res = p6_results.get("eval_results", {})
raw_metrics = eval_res.get("raw_probability_metrics", {})
boot_ci = p6_results.get("bootstrap_ci", {})
thresholds = p6_results.get("thresholds", {})

# Top Section: Key Metrics Display
st.markdown("### 1. Evaluated Population & Final Model Performance")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Evaluated Segment-Months", f"{len(df_mart):,}")
col2.metric("Canonical Segments", f"{df_mart['canonical_segment_id'].nunique():,}")
col3.metric("Primary Raw AP", f"{raw_metrics.get('average_precision', 0.505693):.6f}")
col4.metric("Primary Raw ROC-AUC", f"{raw_metrics.get('roc_auc', 0.920953):.6f}")
col5.metric("Primary Raw Brier Score", f"{raw_metrics.get('brier_score', 0.039827):.6f}")

st.markdown("---")

# Cumulative Operational Capacity Summaries
st.markdown("### 2. Frozen Operational Priority Policies")

cap_col1, cap_col2, cap_col3 = st.columns(3)

with cap_col1:
    st.info("🔴 **Top 5% High-Priority Policy**")
    top5_cnt = df_mart["in_top5_policy"].sum()
    st.write(f"**Candidate Count:** {top5_cnt:,} segment-months ({top5_cnt / 11:,.0f} / month)")
    st.write("**Exclusive Band:** High Priority (Risk Percentile ≥ 95.0%)")

with cap_col2:
    st.warning("🟠 **Top 10% Medium-Priority Policy**")
    top10_cnt = df_mart["in_top10_policy"].sum()
    st.write(f"**Candidate Count:** {top10_cnt:,} segment-months ({top10_cnt / 11:,.0f} / month)")
    st.write("**Exclusive Band:** Medium Priority (90.0% ≤ Risk Percentile < 95.0%)")
    st.caption("Includes detailed SHAP tree contribution attributions.")

with cap_col3:
    st.success("🟡 **Top 20% Watch-List Policy**")
    top20_cnt = df_mart["in_top20_policy"].sum()
    st.write(f"**Candidate Count:** {top20_cnt:,} segment-months ({top20_cnt / 11:,.0f} / month)")
    st.write("**Exclusive Band:** Watch List Priority (80.0% ≤ Risk Percentile < 90.0%)")

st.markdown("---")

# Gate B2 Repeated Access Deviation Notice
st.markdown("### 3. Execution Provenance & Procedural Integrity")
st.error(
    """
    **Documented Gate B2 Protocol Deviation Notice:**
    Phase 6 Gate B2 evaluation involved repeated procedural access (`access_count = 2`, `result_set_count = 1`, classification `B_REPEATED_PROCEDURAL_ACCESS`).
    Invocation `task-12084` opened authorized B2 test rows but failed post-open prior to metric computation due to a function argument mismatch. Invocation `task-12097` reopened the same authorized rows and completed the single final result set. All numerical evaluation metrics (AP=0.505693, ROC-AUC=0.920953) are locked and immutable.
    """
)

# Mandatory Non-Causal Disclaimer
st.caption(
    """
    > ⚠️ **Mandatory Operational Disclaimer:**
    > *SHAP attributions and model predicted risk percentiles describe model behavior and statistical associations only. They do not establish physical causality or prove that executing a repair intervention will change actual pavement condition.*
    """
)
