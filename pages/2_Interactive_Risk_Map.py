"""Page 2 — Interactive Risk Map Page for Phase 8 Dashboard."""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from montreal_road_risk.dashboard.data_loader import (
    load_dashboard_data_mart,
    load_simplified_geometry,
)
from montreal_road_risk.dashboard.filters import apply_dashboard_filters
from montreal_road_risk.dashboard.map_builder import build_risk_map
from montreal_road_risk.dashboard.security import sanitize_csv_dataframe
from montreal_road_risk.dashboard.theme import apply_enterprise_theme

st.set_page_config(page_title="Interactive Risk Map | Montreal Road Risk", page_icon="🗺️", layout="wide")
apply_enterprise_theme()

st.title("🗺️ Interactive Risk Map — Montreal Road Network")

# Load Data (cached — runs once)
with st.spinner("Loading data mart and spatial geometry..."):
    df_mart = load_dashboard_data_mart()
    gdf_geo = load_simplified_geometry()

# ─── Sidebar Filter Form ───────────────────────────────────────────────────────
# All sidebar controls are wrapped in st.form() so that NO expensive map rebuild
# fires until the user explicitly clicks "Apply Map Filters".  (D8.2 Performance Fix)
with st.sidebar.form(key="map_filter_form"):
    st.markdown(
        "<div style='font-size:11px;text-transform:uppercase;letter-spacing:.07em;"
        "color:#94A3B8;font-weight:600;margin-bottom:8px;'>🔍 Filter Risk Map</div>",
        unsafe_allow_html=True,
    )

    # Anchor Month
    anchor_options = sorted(df_mart["date_str"].unique(), reverse=True)
    default_anchor = "2025-05-31" if "2025-05-31" in anchor_options else anchor_options[0]
    selected_anchor = st.selectbox("Anchor Month", anchor_options, index=anchor_options.index(default_anchor))

    st.markdown("---")

    # Borough & Road Class
    borough_list = ["All"] + sorted(df_mart["primary_borough_id"].dropna().unique().tolist())
    selected_boroughs = st.multiselect("Borough(s)", borough_list, default=["All"])

    class_list = ["All"] + sorted(df_mart["functional_road_class"].dropna().unique().tolist())
    selected_classes = st.multiselect("Functional Road Class", class_list, default=["All"])

    st.markdown("---")

    # Priority Band & Policy
    band_options = ["All", "HIGH", "MEDIUM", "WATCH", "OTHER"]
    selected_bands = st.multiselect(
        "Exclusive Map Priority Band",
        band_options,
        default=["HIGH", "MEDIUM"],  # Default Top-10% view (D8.2)
    )

    policy_options = [
        "All",
        "Top 5% Policy (Cumulative)",
        "Top 10% Policy (Cumulative)",
        "Top 20% Policy (Cumulative)",
    ]
    selected_policy = st.selectbox("Cumulative Top-K Policy", policy_options, index=0)

    st.markdown("---")

    # Risk Percentile Slider
    percentile_range = st.slider("Risk Percentile Rank Range", 0.0, 100.0, (0.0, 100.0), step=1.0)

    # Pavement Survey & Repair History
    cond_status = st.radio("Pavement Survey Status", ["All", "Survey Available", "Survey Missing"])
    repair_status = st.radio("Prior Repair History", ["All", "No Prior Repair"])

    st.markdown("---")

    # ── APPLY BUTTON ─────────────────────────────────────────────────────────
    submitted = st.form_submit_button("🚀 Apply Map Filters", use_container_width=True)

# ─── Apply Filters & Render Map (fires only on submit or first load) ───────────
df_filtered = apply_dashboard_filters(
    df=df_mart,
    anchor_month=selected_anchor,
    boroughs=selected_boroughs,
    road_classes=selected_classes,
    exclusive_bands=selected_bands,
    cumulative_policy=selected_policy,
    percentile_range=percentile_range,
    condition_missing_status=cond_status,
    prior_repair_status=repair_status,
)

# Summary header row
n = len(df_filtered)
band_label = ", ".join(selected_bands) if "All" not in selected_bands else "All"
boro_label = str(len(selected_boroughs)) if "All" not in selected_boroughs else "All"

st.markdown(
    f"""
    <div style="display:flex;gap:10px;margin-bottom:12px;">
      <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid #2563EB;
                  border-radius:8px;padding:8px 16px;flex:1;">
        <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#64748B;">
          Matching Segments</div>
        <div style="font-size:20px;font-weight:700;color:#0F172A;">{n:,}</div>
      </div>
      <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid #2563EB;
                  border-radius:8px;padding:8px 16px;flex:1;">
        <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#64748B;">
          Anchor Month</div>
        <div style="font-size:14px;font-weight:700;color:#0F172A;">{selected_anchor}</div>
      </div>
      <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid #2563EB;
                  border-radius:8px;padding:8px 16px;flex:2;">
        <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#64748B;">
          Active Bands</div>
        <div style="font-size:14px;font-weight:700;color:#0F172A;">{band_label}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Render Map
with st.spinner("Rendering Folium Leaflet Map..."):
    m, disp_cnt, warn_msg = build_risk_map(df_filtered, gdf_geo, max_segments=5000)

if warn_msg:
    st.warning(warn_msg)

st_folium(m, width=1300, height=650, returned_objects=[])

# Target-Free Candidate CSV Download (Approved Decision D8.4)
st.markdown("### 📥 Target-Free Operational Candidate Export")
st.caption("Download target-free operational candidate lists for municipal planning (formula injection protected).")

df_csv_export = sanitize_csv_dataframe(df_filtered)
csv_data = df_csv_export.to_csv(index=False).encode("utf-8")

st.download_button(
    label=f"⬇ Download Filtered Candidates ({len(df_filtered):,} Records CSV)",
    data=csv_data,
    file_name=f"montreal_road_risk_candidates_{selected_anchor}.csv",
    mime="text/csv",
)
