"""Page 3 — Segment Details Inspector Page for Phase 8 Dashboard."""

from __future__ import annotations

import streamlit as st

from montreal_road_risk.dashboard.data_loader import load_dashboard_data_mart
from montreal_road_risk.dashboard.theme import apply_enterprise_theme

st.set_page_config(page_title="Segment Details | Montreal Road Risk", page_icon="🔍", layout="wide")
apply_enterprise_theme()

st.title("🔍 Segment Details Inspector — SHAP Attribution Breakdown")

# Load Data Mart
with st.spinner("Loading data mart..."):
    df_mart = load_dashboard_data_mart()

# Selection Mechanism
st.sidebar.header("🔎 Select Road Segment")

# Filter by Anchor Date first
anchor_list = sorted(df_mart["date_str"].unique(), reverse=True)
sel_anchor = st.sidebar.selectbox("Anchor Date", anchor_list, index=0)

df_anchor = df_mart[df_mart["date_str"] == sel_anchor]

# Options list for segment ID — prioritize explained segments (has_shap_explanation == True) and sort by risk_percentile_rank descending
df_anchor_sorted = df_anchor.sort_values(by=["has_shap_explanation", "risk_percentile_rank"], ascending=[False, False])
seg_options = df_anchor_sorted["canonical_segment_id"].tolist()
sel_seg_id = st.sidebar.selectbox("Canonical Segment ID", seg_options, index=0)

row = df_anchor[df_anchor["canonical_segment_id"] == sel_seg_id].iloc[0]

# Page Header
st.subheader(f"Road Segment ID: `{row['canonical_segment_id']}` (Anchor: `{row['date_str']}`)")

# Layout: 2 Columns
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📋 Segment Attributes & Metadata")
    st.write(f"**Segment Month ID:** `{row['segment_month_id']}`")
    st.write(f"**Primary Borough:** `{row['primary_borough_id']}`")
    st.write(f"**Functional Road Class:** `{row['functional_road_class']}`")
    st.write(f"**Segment Length:** `{row['segment_length_m']:.1f} metres`")
    st.write(f"**Pavement Survey Status:** `{'Missing (Imputed Default)' if row['condition_missing_flag'] else 'Available'}`")
    st.write(f"**Prior Repair Status:** `{'No Prior Repair Recorded' if row['no_prior_repair_flag'] else 'Prior Repair History Present'}`")

with col_right:
    st.markdown("### 📊 Risk Model Outputs & Priority Tiers")
    st.metric("Raw Risk Probability", f"{row['raw_probability']:.6f}")
    st.metric("Population Risk Percentile Rank", f"{row['risk_percentile_rank']:.2f}%")

    tier_color = {"HIGH": "🔴", "MEDIUM": "🟠", "WATCH": "🟡", "OTHER": "⚪"}.get(row['priority_band_exclusive'], "⚪")
    st.markdown(f"**Exclusive Map Priority Band:** {tier_color} **`{row['priority_band_exclusive']}`**")

    pol_str = []
    if row['in_top5_policy']:
        pol_str.append("Top 5% Policy")
    if row['in_top10_policy']:
        pol_str.append("Top 10% Policy")
    if row['in_top20_policy']:
        pol_str.append("Top 20% Policy")
    st.write(f"**Cumulative Policy Memberships:** `{', '.join(pol_str) if pol_str else 'None (Outside Top 20%)'}`")

st.markdown("---")

# SHAP Attribution Breakdown
st.markdown("### 🧠 SHAP Attribution Breakdown (Log-Odds Margin Scale)")

if row["has_shap_explanation"]:
    st.info(f"**Base Value (Expected Log-Odds Margin):** `{row['base_value']:.6f}` | **Raw Margin:** `{row['raw_margin']:.6f}` | **Additivity Residual:** `{row['additivity_residual']:.6e}`")

    shap_col1, shap_col2 = st.columns(2)

    with shap_col1:
        st.markdown("#### ⬆️ Top Positive SHAP Drivers (Increasing Risk)")
        st.markdown(f"1. **`{row['top_pos_feat_1']}`**: `+{row['top_pos_shap_1']:.6f}`")
        st.markdown(f"2. **`{row['top_pos_feat_2']}`**: `+{row['top_pos_shap_2']:.6f}`")
        st.markdown(f"3. **`{row['top_pos_feat_3']}`**: `+{row['top_pos_shap_3']:.6f}`")

    with shap_col2:
        st.markdown("#### ⬇️ Top Negative SHAP Drivers (Decreasing Risk)")
        st.markdown(f"1. **`{row['top_neg_feat_1']}`**: `{row['top_neg_shap_1']:.6f}`")
        st.markdown(f"2. **`{row['top_neg_feat_2']}`**: `{row['top_neg_shap_2']:.6f}`")
        st.markdown(f"3. **`{row['top_neg_feat_3']}`**: `{row['top_neg_shap_3']:.6f}`")
else:
    st.warning(f"⚠️ **{row['explanation_status']}**")
    st.caption("Detailed segment SHAP attributions were exported exclusively for Top-10% risk-priority candidates under Phase 7 Scope.")

# Non-Causal Disclaimer
st.caption(
    """
    > ⚠️ **Non-Causal Decision-Support Disclaimer:**
    > *SHAP values describe model risk attributions and feature associations only. They do not establish physical causality or guarantee that altering a feature value will alter physical repair risk.*
    """
)
