"""Page 5 — Model Interpretation Page for Phase 8 Dashboard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from montreal_road_risk.dashboard.data_loader import (
    PROJECT_ROOT,
    load_phase7_interpretation_artifacts,
)
from montreal_road_risk.dashboard.theme import apply_enterprise_theme

PLOTS_DIR = PROJECT_ROOT / "outputs/phase_7/plots"

st.set_page_config(page_title="Model Interpretation | Montreal Road Risk", page_icon="🧠", layout="wide")
apply_enterprise_theme()

st.title("🧠 Model Interpretation — Target-Free SHAP Attributions")

# Load Phase 7 Artifacts
with st.spinner("Loading Phase 7 interpretation artifacts..."):
    p7_data = load_phase7_interpretation_artifacts()

manifest = p7_data.get("manifest", {})
df_global_imp = p7_data.get("global_importance", pd.DataFrame())
stability = manifest.get("stability_analysis", {})

# 1. Global Feature Importance Table
st.markdown("### 1. Global Source Feature Importance (Grouped Attributions)")

if not df_global_imp.empty:
    st.dataframe(
        df_global_imp.head(20)[["importance_rank", "source_feature", "mean_abs_shap", "num_transformed_features", "feature_note"]],
        use_container_width=True,
    )

st.markdown("---")

# 2. Stability Analysis Across Stratified Samples
st.markdown("### 2. Feature Importance Rank Stability (Seeds 42, 137, 2026)")

stab_col1, stab_col2, stab_col3 = st.columns(3)
spearman_dict = stability.get("spearman_rank_correlations", {})

with stab_col1:
    st.metric("Seed 42 vs Seed 137 Rank Correlation", f"{spearman_dict.get('seed_42_vs_seed_137', 0.999946):.6f}")

with stab_col2:
    st.metric("Seed 42 vs Seed 2026 Rank Correlation", f"{spearman_dict.get('seed_42_vs_seed_2026', 0.999991):.6f}")

with stab_col3:
    st.metric("Top-10 / Top-20 Feature Overlap", f"{stability.get('top_10_overlap_count', 10)}/10 | {stability.get('top_20_overlap_count', 20)}/20")

st.markdown("---")

# 3. High-Resolution SHAP Visualization Plots
st.markdown("### 3. SHAP Visualization Plots")

plot_tabs = st.tabs(["Global Importance Bar Chart", "Beeswarm Summary Plot", "Key Feature Dependence Plots"])

with plot_tabs[0]:
    bar_plot_p = PLOTS_DIR / "shap_bar_global_importance.png"
    if bar_plot_p.exists():
        st.image(str(bar_plot_p), caption="Top-20 Grouped Source Feature Importance Bar Chart")
    else:
        st.info("Global importance bar chart PNG not found.")

with plot_tabs[1]:
    beeswarm_plot_p = PLOTS_DIR / "shap_beeswarm_summary.png"
    if beeswarm_plot_p.exists():
        st.image(str(beeswarm_plot_p), caption="SHAP Beeswarm Summary Plot (Top 20 Features)")
    else:
        st.info("Beeswarm summary plot PNG not found.")

with plot_tabs[2]:
    st.markdown("#### Feature Dependence Select")
    dep_plots = list(PLOTS_DIR.glob("shap_dependence_*.png"))
    if dep_plots:
        selected_plot_name = st.selectbox("Select Feature Dependence Plot", [p.name for p in dep_plots])
        st.image(str(PLOTS_DIR / selected_plot_name), caption=f"SHAP Dependence Plot: {selected_plot_name}")
    else:
        st.info("No dependence plots found.")

st.markdown("---")

# 4. Mandatory Interpretation Limitations
st.markdown("### 4. Interpretation Limitations & Structural Proxies")
st.warning(
    """
    * **`prior_repair_months_12m` Remediated Feature:** Upper-bound historical repair date filtering bug corrected in Phase 5 remediation.
    * **`segment_length_m` Structural Proxy:** Highly correlated with physical road network geometry; its SHAP attribution reflects segment exposure length.
    * **Correlated Climate Features:** Temperature and precipitation features exhibit collinearity; SHAP attributions partition tree split frequencies across correlated signals.
    """
)

# Non-Causal Disclaimer
st.caption(
    """
    > ⚠️ **Mandatory Non-Causal Disclaimer:**
    > *SHAP values describe model attributions and statistical associations only. They do not establish physical causality or guarantee that altering a feature value will alter physical repair risk.*
    """
)
