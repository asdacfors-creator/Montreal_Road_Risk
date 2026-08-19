"""Phase 8 Dashboard Main Entrypoint — Enterprise SaaS Landing Portal.

Montreal Road Risk Assessment & Predictive Maintenance Platform (INSE 6311).
Target-Free Operational Decision-Support Engine for Municipal Infrastructure.

Run locally using:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from montreal_road_risk.dashboard.theme import apply_enterprise_theme

st.set_page_config(
    page_title="Montreal Road Risk Assessment Platform",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_enterprise_theme()

# ─── Hero Header Banner ────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      #hero-banner-card,
      #hero-banner-card *,
      #hero-banner-card p,
      #hero-banner-card span,
      #hero-banner-card div,
      #hero-banner-card h1 {
        color: #FFFFFF !important;
      }
      #hero-banner-card .v1 { color: #60A5FA !important; }
      #hero-banner-card .v2 { color: #4ADE80 !important; }
      #hero-banner-card .v3 { color: #C084FC !important; }
      #hero-banner-card .v4 { color: #2DD4BF !important; }
    </style>

    <div id="hero-banner-card" style="background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 50%,#0F172A 100%);
                border-radius:16px;padding:36px 40px 28px;margin-bottom:28px;
                border:1px solid #334155;position:relative;overflow:hidden;">

      <!-- subtle grid overlay -->
      <div style="position:absolute;inset:0;opacity:.04;
                  background-image:linear-gradient(#fff 1px,transparent 1px),
                                   linear-gradient(90deg,#fff 1px,transparent 1px);
                  background-size:40px 40px;"></div>

      <!-- status pills -->
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;position:relative;">
        <span style="background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.35);
                     color:#4ADE80 !important;font-size:10px;font-weight:700;letter-spacing:.06em;
                     padding:3px 10px;border-radius:999px;">🟢 System Active</span>
        <span style="background:rgba(37,99,235,.15);border:1px solid rgba(37,99,235,.35);
                     color:#60A5FA !important;font-size:10px;font-weight:700;letter-spacing:.06em;
                     padding:3px 10px;border-radius:999px;">🔒 Frozen Model&nbsp;&nbsp;edec87e</span>
        <span style="background:rgba(168,85,247,.15);border:1px solid rgba(168,85,247,.35);
                     color:#C084FC !important;font-size:10px;font-weight:700;letter-spacing:.06em;
                     padding:3px 10px;border-radius:999px;">📊 527,813 Observations</span>
        <span style="background:rgba(20,184,166,.15);border:1px solid rgba(20,184,166,.35);
                     color:#2DD4BF !important;font-size:10px;font-weight:700;letter-spacing:.06em;
                     padding:3px 10px;border-radius:999px;">🗺️ 47,983 Road Geometries</span>
      </div>

      <!-- title block -->
      <div style="position:relative;">
        <h1 style="margin:0;padding:0;border:none;font-size:2.1rem;font-weight:800;
                   color:#FFFFFF !important;text-shadow:0 2px 4px rgba(0,0,0,0.5);letter-spacing:-.03em;line-height:1.2;max-width:800px;">
          🏙️&nbsp; Montréal Road Risk Assessment<br>&amp; Predictive Maintenance Platform
        </h1>
        <div style="margin:14px 0 0;color:#FFFFFF !important;font-size:14px;font-weight:600;max-width:680px;
                    line-height:1.6;text-shadow:0 1px 2px rgba(0,0,0,0.4);">
          Target-Free Operational Decision-Support Engine for Municipal Infrastructure &mdash;
          INSE 6311 &nbsp;&middot;&nbsp; Concordia University &nbsp;&middot;&nbsp; Phase 8
        </div>
      </div>

      <!-- key metrics strip -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:28px;position:relative;">
        <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
                    border-radius:10px;padding:14px 16px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#FFFFFF !important;font-weight:700;margin-bottom:4px;">
            Average Precision</div>
          <div class="v1" style="font-size:1.5rem;font-weight:800;color:#60A5FA !important;letter-spacing:-.02em;">0.5057</div>
          <div style="font-size:10px;color:#FFFFFF !important;font-weight:500;margin-top:2px;">Phase 6 Gate B2 · Locked</div>
        </div>
        <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
                    border-radius:10px;padding:14px 16px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#FFFFFF !important;font-weight:700;margin-bottom:4px;">
            ROC-AUC</div>
          <div class="v2" style="font-size:1.5rem;font-weight:800;color:#4ADE80 !important;letter-spacing:-.02em;">0.9210</div>
          <div style="font-size:10px;color:#FFFFFF !important;font-weight:500;margin-top:2px;">Phase 6 Gate B2 · Locked</div>
        </div>
        <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
                    border-radius:10px;padding:14px 16px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#FFFFFF !important;font-weight:700;margin-bottom:4px;">
            Anchor Months</div>
          <div class="v3" style="font-size:1.5rem;font-weight:800;color:#C084FC !important;letter-spacing:-.02em;">11</div>
          <div style="font-size:10px;color:#FFFFFF !important;font-weight:500;margin-top:2px;">Jul 2024 → May 2025</div>
        </div>
        <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
                    border-radius:10px;padding:14px 16px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#FFFFFF !important;font-weight:700;margin-bottom:4px;">
            SHAP Explanations</div>
          <div class="v4" style="font-size:1.5rem;font-weight:800;color:#2DD4BF !important;letter-spacing:-.02em;">52,782</div>
          <div style="font-size:10px;color:#FFFFFF !important;font-weight:500;margin-top:2px;">Top 10% candidate pool</div>
        </div>
      </div>

    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Section 2: 3-Step Process Flow ───────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:8px;">
      <div style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;
                  color:#2563EB;font-weight:700;margin-bottom:4px;">How It Works</div>
      <h2 style="margin:0;font-size:1.2rem;color:#0F172A;font-weight:700;letter-spacing:-.02em;">
        The Predictive Maintenance Engine</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

flow_col1, flow_col2, flow_col3 = st.columns(3)

_flow_cards = [
    (
        "🛰️",
        "Spatial-Temporal Feature Panel",
        "Step 1 — Data Aggregation",
        "#2563EB",
        "Aggregates <strong>11 anchor months</strong> across <strong>47,983 canonical Montréal road geometries</strong> "
        "(EPSG:32188 projected metric CRS). Each observation = one segment × one anchor month panel row. "
        "Features span climate, pavement condition, repair history, and road network geometry.",
        ["527,813 panel rows", "35 input features", "EPSG:32188 CRS"],
    ),
    (
        "🧠",
        "Raw XGBoost Risk Engine",
        "Step 2 — Probability Scoring",
        "#7C3AED",
        "Evaluates all 35 features through a frozen <strong>XGBoost gradient-boosted tree ensemble</strong> "
        "without post-hoc calibration distortion. Outputs a raw risk probability "
        "(<em>p</em>) for each segment-month pair. "
        "Model locked at commit <code>edec87e</code> — no retraining permitted.",
        ["AP = 0.5057", "ROC-AUC = 0.9210", "Seed 42 · Frozen"],
    ),
    (
        "🛠️",
        "Actionable Inspection Queue",
        "Step 3 — Operational Prioritisation",
        "#059669",
        "Segments are ranked by raw probability into <strong>four exclusive priority tiers</strong> "
        "using frozen Phase 6 probability thresholds. City repair crews receive structured Top-K "
        "inspection candidate lists — target-free and formula-injection protected.",
        ["HIGH ≥ 0.177239", "MEDIUM ≥ 0.089069", "WATCH ≥ 0.038477"],
    ),
]

for col, (icon, title, step_label, accent, body, tags) in zip(
    [flow_col1, flow_col2, flow_col3], _flow_cards, strict=False
):
    tag_html = "".join(
        f"<span style='background:#F1F5F9;border:1px solid #E2E8F0;color:#334155;"
        f"font-size:9px;font-weight:600;letter-spacing:.04em;padding:2px 8px;"
        f"border-radius:999px;'>{t}</span>"
        for t in tags
    )
    col.markdown(
        f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-top:4px solid {accent};
                    border-radius:12px;padding:20px;height:280px;
                    box-shadow:0 4px 6px -1px rgba(0,0,0,.05);display:flex;flex-direction:column;">
          <div style="font-size:28px;margin-bottom:8px;">{icon}</div>
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:.08em;
                      color:{accent};font-weight:700;margin-bottom:4px;">{step_label}</div>
          <div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:8px;
                      letter-spacing:-.01em;">{title}</div>
          <div style="font-size:11px;color:#475569;line-height:1.6;flex:1;">{body}</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:12px;">{tag_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom:28px;'></div>", unsafe_allow_html=True)

# ─── Section 3: Data Lineage Grid ─────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:8px;">
      <div style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;
                  color:#2563EB;font-weight:700;margin-bottom:4px;">Data Provenance</div>
      <h2 style="margin:0;font-size:1.2rem;color:#0F172A;font-weight:700;letter-spacing:-.02em;">
        Official Input Data Streams</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

_data_sources = [
    ("🗺️", "Montreal Géobase Road Network",
     "47,983 canonical road segments mapped in projected metric CRS (EPSG:32188 — NAD83 / MTM zone 8). "
     "Provides canonical segment IDs and simplified line geometries for GIS rendering (EPSG:4326).",
     "Ville de Montréal Open Data"),
    ("❄️", "ECCC Daily Weather History",
     "Environment & Climate Change Canada station observations: freeze-thaw cycles, "
     "precipitation totals, snowfall accumulation, and temperature extremes per anchor month.",
     "Environment & Climate Change Canada"),
    ("🛠️", "Historical Repair Events",
     "Pothole repair and road maintenance intervention timestamps from municipal "
     "work-order records. Used to construct binary 90-day repair outcomes and repair history lag features.",
     "Ville de Montréal Works Department"),
    ("🛣️", "Pavement Survey Records",
     "Structural condition indices (PCI/IRI) and last-survey timestamps. "
     "Missing survey flags are imputed using road-class default fill values.",
     "Montréal Pavement Asset Registry"),
    ("🚛", "Traffic & Road Asset Proxies",
     "Functional road class (arterial, collector, local), bus-route coverage flags, "
     "and segment length as exposure proxies in the feature engineering pipeline.",
     "Géobase + STM GTFS Network"),
    ("📐", "Feature Engineering Pipeline",
     "35 derived panel features including rolling repair counts, weather interaction terms, "
     "segment-length normalisation, and temporal lag indicators aggregated over 30–365 day windows.",
     "Internal — Phase 3 / Phase 4"),
]

data_cols = st.columns(3)
for i, (icon, title, desc, source) in enumerate(_data_sources):
    col = data_cols[i % 3]
    col.markdown(
        f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;
                    padding:16px;margin-bottom:14px;
                    box-shadow:0 2px 4px rgba(0,0,0,.04);">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <span style="font-size:22px;">{icon}</span>
            <span style="font-size:12px;font-weight:700;color:#0F172A;letter-spacing:-.01em;">{title}</span>
          </div>
          <div style="font-size:11px;color:#475569;line-height:1.55;margin-bottom:10px;">{desc}</div>
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:#94A3B8;
                      border-top:1px solid #F1F5F9;padding-top:8px;font-weight:600;">
            Source &nbsp;·&nbsp; {source}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ─── Section 4: System Navigation & Module Tour ────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:8px;margin-top:8px;">
      <div style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;
                  color:#2563EB;font-weight:700;margin-bottom:4px;">Dashboard Navigation</div>
      <h2 style="margin:0;font-size:1.2rem;color:#0F172A;font-weight:700;letter-spacing:-.02em;">
        Five Analytical Modules</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

_pages = [
    (
        "1️⃣",
        "Executive Overview",
        "#2563EB",
        "Strategic KPIs & Governance",
        "Population-level KPI summaries including total segment-months, canonical segments, "
        "and SHAP-explained candidate counts. Displays <strong>Gate B2 repeated-access deviation disclosure</strong>, "
        "frozen operational policy capacity thresholds (Top 5 / 10 / 20%), "
        "and the mandatory non-causal operational disclaimer.",
        "Use this page to validate model integrity and audit provenance before decision-making.",
    ),
    (
        "2️⃣",
        "Interactive Risk Map",
        "#7C3AED",
        "GIS Geospatial Explorer",
        "Hardware-accelerated <strong>Folium Leaflet vector map</strong> rendering road segments "
        "colour-coded by priority band (HIGH / MEDIUM / WATCH / OTHER). "
        "Sidebar filters allow anchor month, borough, road class, and priority band selection. "
        "Click any road polyline to open a premium popup card with raw probability, SHAP attribution, and metadata.",
        "Use this page to visually locate and filter high-risk road geometries across Montréal boroughs.",
    ),
    (
        "3️⃣",
        "Segment Details Inspector",
        "#059669",
        "Single-Segment Microscope",
        "Single-segment drill-down tool displaying exact raw risk probabilities, "
        "population percentile rank, cumulative policy membership, and a full "
        "<strong>SHAP top-3 positive and negative driver breakdown</strong> "
        "(log-odds margin scale) for Top-10% explained segments. "
        "Non-explained segments display the frozen Phase 7 scope notice.",
        "Use this page to inspect individual road segments and understand their model-attributed risk drivers.",
    ),
    (
        "4️⃣",
        "Model Performance & Equity",
        "#D97706",
        "Locked Evaluation Dashboard",
        "Presents all locked <strong>Phase 6 Gate B2 evaluation metrics</strong> (AP, ROC-AUC, Brier, Log-Loss, ECE) "
        "with 95% cluster-stratified bootstrap confidence intervals. "
        "Includes Top-K precision/recall/lift table, 10-bin reliability calibration table, "
        "and documented evaluation limitations (L6.2 exclusion, L6.4 deviation).",
        "Use this page to audit model accuracy, calibration quality, and operational recall capacity.",
    ),
    (
        "5️⃣",
        "Model Interpretation (SHAP)",
        "#DC2626",
        "Global Feature Explainability",
        "Displays <strong>global grouped source feature importance</strong> ranked by mean absolute SHAP value "
        "across the Top-10% candidate pool. Shows beeswarm summary plots, "
        "seed rank-stability audit (Spearman ρ across seeds 42 / 137 / 2026), "
        "key feature partial dependence plots, and structural proxy warnings "
        "(e.g. <code>segment_length_m</code>, correlated climate features).",
        "Use this page to understand which features drive aggregate risk prioritisation — non-causally.",
    ),
]

nav_col_left, nav_col_right = st.columns(2)
for i, (num, title, accent, subtitle, desc, guidance) in enumerate(_pages):
    col = nav_col_left if i % 2 == 0 else nav_col_right
    col.markdown(
        f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid {accent};
                    border-radius:10px;padding:18px 20px;margin-bottom:14px;
                    box-shadow:0 2px 4px rgba(0,0,0,.04);">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
            <span style="font-size:18px;">{num}</span>
            <div>
              <div style="font-size:13px;font-weight:700;color:#0F172A;letter-spacing:-.01em;">{title}</div>
              <div style="font-size:9px;text-transform:uppercase;letter-spacing:.07em;
                          color:{accent};font-weight:700;">{subtitle}</div>
            </div>
          </div>
          <div style="font-size:11px;color:#475569;line-height:1.6;margin-bottom:10px;">{desc}</div>
          <div style="font-size:10px;color:#0F172A;background:#F8FAFC;border-radius:6px;
                      padding:8px 10px;border-left:3px solid {accent};">
            💡 <em>{guidance}</em></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

# ─── Section 5: Governance Callout Box ────────────────────────────────────────
st.markdown(
    """
    <div style="background:linear-gradient(135deg,#FFF7ED,#FFFBF5);
                border:1px solid #FDE68A;border-left:5px solid #D97706;
                border-radius:12px;padding:20px 24px;margin-bottom:16px;">
      <div style="display:flex;align-items:flex-start;gap:14px;">
        <span style="font-size:28px;line-height:1;">⚠️</span>
        <div>
          <div style="font-size:13px;font-weight:700;color:#92400E;margin-bottom:6px;">
            Mandatory Operational Disclaimer</div>
          <div style="font-size:12px;color:#78350F;line-height:1.7;">
            Model predictions represent <strong>statistical risk prioritisation for maintenance inspection
            scheduling</strong>. SHAP attributions and predicted risk percentiles describe feature
            associations and model behaviour only &mdash; they do <strong>NOT</strong> establish physical
            causality or constitute proof of pothole occurrence. All operational decisions remain
            subject to field engineer validation and municipal policy review.
          </div>
          <div style="margin-top:10px;font-size:11px;color:#78350F;background:rgba(255,255,255,0.7);padding:10px 12px;border-radius:8px;border:1px solid #FCD34D;">
            <strong>Priority Band &amp; Count Logic:</strong> Priority bands (HIGH = top 5%, MEDIUM = next 5%, WATCH = next 10%, OTHER = bottom 80%) are assigned based on <em>within-anchor-month percentile rank</em> across each month's 47,983 segments. In low-risk months such as May 2025 (where max raw probability is 0.032016), the top-ranked segment has percentile rank ~100.0% for that month and is correctly assigned to HIGH. The fixed Gate B1 diagnostic threshold (0.30805489) is used solely for diagnostic classification metrics and does not define priority bands. Local SHAP explanations are embedded in <code>dashboard_data_mart.parquet</code> for 52,782 Top-10% segment-months.
          </div>
          <div style="display:flex;gap:12px;margin-top:12px;flex-wrap:wrap;">
            <span style="font-size:10px;background:#FEF3C7;border:1px solid #FCD34D;
                         color:#92400E;padding:3px 10px;border-radius:6px;font-weight:600;">
              Non-Causal Attribution Only</span>
            <span style="font-size:10px;background:#FEF3C7;border:1px solid #FCD34D;
                         color:#92400E;padding:3px 10px;border-radius:6px;font-weight:600;">
              Gate B2 Locked Results</span>
            <span style="font-size:10px;background:#FEF3C7;border:1px solid #FCD34D;
                         color:#92400E;padding:3px 10px;border-radius:6px;font-weight:600;">
              Target-Free Dashboard</span>
            <span style="font-size:10px;background:#FEF3C7;border:1px solid #FCD34D;
                         color:#92400E;padding:3px 10px;border-radius:6px;font-weight:600;">
              No B1/B2/90-day/180-day Exposure</span>
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="padding:10px 0 6px;">
      <div style="font-size:11px;font-weight:700;color:#F1F5F9;margin-bottom:4px;">
        Montréal Road Risk</div>
      <div style="font-size:10px;color:#94A3B8;line-height:1.6;">
        Phase 8 · INSE 6311<br>
        Operational Decision-Support<br>
        Commit&nbsp;<span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.2);color:#60A5FA;font-family:monospace;font-size:10px;padding:2px 6px;border-radius:4px;display:inline-block;margin-top:2px;">edec87e</span>
      </div>
    </div>
    <hr style="border-color:#334155;margin:10px 0;">
    <div style="font-size:10px;color:#475569;line-height:1.6;">
      Use the <strong style="color:#94A3B8;">sidebar navigation</strong> above
      to explore the five analytical modules.
    </div>
    """,
    unsafe_allow_html=True,
)
