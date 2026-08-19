"""Enterprise SaaS CSS Theme Module for Phase 8 Dashboard.

Provides apply_enterprise_theme() to be called on every Streamlit page
immediately after st.set_page_config(). Injects:
  - Google Fonts (Inter)
  - Hidden Streamlit chrome (header, footer, toolbar, deploy btn, spinner)
  - Dark-navy sidebar with white text
  - Premium KPI metric cards with blue left-border accent
  - Styled st.info / st.warning / st.error boxes
  - Styled form submit button
  - Off-white canvas background (#F8FAFC)
"""

from __future__ import annotations

import streamlit as st


def apply_enterprise_theme() -> None:
    """Inject enterprise SaaS CSS into the current Streamlit page."""
    st.markdown(
        """
        <style>
        /* ─── Google Fonts ─────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* ─── Hide Streamlit Chrome ─────────────────────────────── */
        #MainMenu            { display: none !important; }
        header               { display: none !important; }
        footer               { display: none !important; }
        [data-testid="stDecoration"]          { display: none !important; }
        [data-testid="stToolbar"]             { display: none !important; }
        [data-testid="stStatusWidget"]        { display: none !important; }
        [data-testid="stDeployButton"]        { display: none !important; }
        /* Running / spinner top bar */
        [data-testid="stHeader"]              { display: none !important; }
        .stApp > header                       { display: none !important; }

        /* ─── Global Base ────────────────────────────────────────── */
        html, body, [class*="css"] {
            font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
        }

        .stApp {
            background-color: #F8FAFC !important;
        }

        /* ─── Sidebar ────────────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%) !important;
            border-right: 1px solid #334155 !important;
        }

        [data-testid="stSidebar"] * {
            color: #CBD5E1 !important;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #F1F5F9 !important;
            font-weight: 600 !important;
            letter-spacing: -0.02em !important;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stRadio label,
        [data-testid="stSidebar"] .stMultiSelect label,
        [data-testid="stSidebar"] .stSelectbox label {
            color: #94A3B8 !important;
            font-size: 11px !important;
            font-weight: 500 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
        }

        /* Sidebar success message */
        [data-testid="stSidebar"] .stAlert {
            background-color: rgba(37, 99, 235, 0.15) !important;
            border: 1px solid rgba(37, 99, 235, 0.3) !important;
            border-radius: 8px !important;
        }

        /* Sidebar code badge styling */
        [data-testid="stSidebar"] code,
        [data-testid="stSidebar"] div code,
        [data-testid="stSidebar"] span code,
        .stSidebar code {
            background-color: rgba(255, 255, 255, 0.12) !important;
            color: #60A5FA !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 4px !important;
            padding: 2px 6px !important;
            font-size: 0.85rem !important;
            font-family: monospace !important;
        }

        /* Sidebar navigation links */
        [data-testid="stSidebarNav"] a {
            color: #94A3B8 !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            border-radius: 6px !important;
            transition: all 0.15s ease !important;
        }

        [data-testid="stSidebarNav"] a span,
        [data-testid="stSidebarNav"] a div {
            text-transform: capitalize !important;
        }

        [data-testid="stSidebarNav"] a:hover,
        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background-color: rgba(37, 99, 235, 0.2) !important;
            color: #E2E8F0 !important;
        }

        /* ─── Main Content Area ──────────────────────────────────── */
        .block-container {
            padding-top: 1.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 1400px !important;
        }

        /* Page titles */
        h1 {
            font-weight: 700 !important;
            font-size: 1.75rem !important;
            letter-spacing: -0.03em !important;
            padding-bottom: 0.5rem !important;
            border-bottom: 2px solid #E2E8F0 !important;
            margin-bottom: 1.25rem !important;
        }

        .stApp h1:not(.hero-title) {
            color: #0F172A !important;
        }

        /* ─── Hero Banner High Contrast ID Rules ───────────────────── */
        #hero-banner-card,
        #hero-banner-card *,
        #hero-banner-card p,
        #hero-banner-card span,
        #hero-banner-card div,
        #hero-banner-card h1,
        #hero-banner-card h2,
        #hero-banner-card h3 {
            color: #FFFFFF !important;
        }

        #hero-banner-card .hero-title {
            color: #FFFFFF !important;
            font-weight: 800 !important;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5) !important;
        }

        #hero-banner-card .hero-subtitle {
            color: #FFFFFF !important;
            font-weight: 600 !important;
            text-shadow: 0 1px 2px rgba(0,0,0,0.4) !important;
            opacity: 0.95 !important;
        }

        #hero-banner-card .hero-metric-label {
            color: #FFFFFF !important;
            font-weight: 700 !important;
            letter-spacing: 0.08em !important;
        }

        #hero-banner-card .hero-metric-value-1 { color: #60A5FA !important; }
        #hero-banner-card .hero-metric-value-2 { color: #4ADE80 !important; }
        #hero-banner-card .hero-metric-value-3 { color: #C084FC !important; }
        #hero-banner-card .hero-metric-value-4 { color: #2DD4BF !important; }

        #hero-banner-card .hero-metric-footer {
            color: #FFFFFF !important;
            font-weight: 500 !important;
            opacity: 0.9 !important;
        }

        /* Sidebar navigation link capitalization */
        [data-testid="stSidebarNav"] *,
        [data-testid="stSidebarNavItems"] *,
        [data-testid="stSidebarNavItems"] span,
        [data-testid="stSidebarNavItems"] a,
        [data-testid="stSidebarNav"] span,
        [data-testid="stSidebarNav"] a {
            text-transform: capitalize !important;
        }

        h2, h3 {
            font-weight: 600 !important;
            color: #1E293B !important;
            letter-spacing: -0.02em !important;
        }

        /* Divider */
        hr {
            border: none !important;
            border-top: 1px solid #E2E8F0 !important;
            margin: 1.5rem 0 !important;
        }

        /* ─── KPI Metric Cards ───────────────────────────────────── */
        [data-testid="stMetric"] {
            background: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-left: 4px solid #2563EB !important;
            border-radius: 10px !important;
            padding: 1rem 1.25rem !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
            transition: box-shadow 0.2s ease !important;
        }

        [data-testid="stMetric"]:hover {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04) !important;
        }

        [data-testid="stMetricLabel"] {
            color: #64748B !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
            white-space: normal !important;
            overflow: visible !important;
            word-wrap: break-word !important;
        }

        [data-testid="stMetricValue"] {
            color: #0F172A !important;
            font-size: 1.5rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }

        /* ─── Info / Alert Boxes ─────────────────────────────────── */
        .stAlert[data-baseweb="notification"] {
            border-radius: 8px !important;
            border: 1px solid transparent !important;
        }

        div[data-testid="stAlert"][role="alert"] {
            border-radius: 8px !important;
        }

        /* Info → Blue */
        .stAlert.st-ae {
            background-color: #EFF6FF !important;
            border: 1px solid #BFDBFE !important;
            border-left: 4px solid #2563EB !important;
            border-radius: 8px !important;
            color: #1E40AF !important;
        }

        /* Warning → Amber */
        .stAlert.st-ag {
            background-color: #FFFBEB !important;
            border: 1px solid #FDE68A !important;
            border-left: 4px solid #D97706 !important;
            border-radius: 8px !important;
            color: #92400E !important;
        }

        /* Error → Red */
        .stAlert.st-af {
            background-color: #FEF2F2 !important;
            border: 1px solid #FECACA !important;
            border-left: 4px solid #DC2626 !important;
            border-radius: 8px !important;
            color: #7F1D1D !important;
        }

        /* Success → Green */
        .stAlert.st-ah {
            background-color: #F0FDF4 !important;
            border: 1px solid #BBF7D0 !important;
            border-left: 4px solid #16A34A !important;
            border-radius: 8px !important;
            color: #14532D !important;
        }

        /* ─── Buttons (Primary) ──────────────────────────────────── */
        [data-testid="stFormSubmitButton"] > button,
        .stButton > button[kind="primary"],
        .stDownloadButton > button {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            letter-spacing: 0.02em !important;
            padding: 0.625rem 1.25rem !important;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.25) !important;
            transition: all 0.2s ease !important;
            cursor: pointer !important;
        }

        [data-testid="stFormSubmitButton"] > button:hover,
        .stButton > button[kind="primary"]:hover,
        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%) !important;
            box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.35) !important;
            transform: translateY(-1px) !important;
        }

        /* Form submit button full-width spacing */
        [data-testid="stFormSubmitButton"] {
            margin-top: 0.75rem !important;
        }

        /* ─── Tables ─────────────────────────────────────────────── */
        .stTable table {
            border-radius: 8px !important;
            overflow: hidden !important;
            border: 1px solid #E2E8F0 !important;
            font-size: 13px !important;
        }

        .stTable table thead tr {
            background-color: #F1F5F9 !important;
            color: #334155 !important;
            font-weight: 600 !important;
            font-size: 11px !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
        }

        .stTable table tbody tr:nth-child(even) {
            background-color: #F8FAFC !important;
        }

        .stTable table tbody tr:hover {
            background-color: #EFF6FF !important;
        }

        /* ─── Dataframe ──────────────────────────────────────────── */
        .stDataFrame {
            border-radius: 8px !important;
            overflow: hidden !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04) !important;
        }

        /* ─── Tabs ───────────────────────────────────────────────── */
        [data-baseweb="tab-list"] {
            background-color: transparent !important;
            border-bottom: 2px solid #E2E8F0 !important;
            gap: 4px !important;
        }

        [data-baseweb="tab"] {
            font-weight: 500 !important;
            font-size: 13px !important;
            color: #64748B !important;
            border-radius: 6px 6px 0 0 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.15s ease !important;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            color: #2563EB !important;
            border-bottom: 2px solid #2563EB !important;
            font-weight: 600 !important;
        }

        /* ─── Spinner ────────────────────────────────────────────── */
        [data-testid="stSpinner"] {
            color: #2563EB !important;
        }

        /* ─── Caption / Small Text ───────────────────────────────── */
        .stCaption, small {
            color: #94A3B8 !important;
            font-size: 11px !important;
        }

        /* ─── Selectbox / Multiselect inputs ─────────────────────── */
        [data-baseweb="select"] div[class*="control"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 6px !important;
            font-size: 13px !important;
        }

        /* Sidebar-specific widgets dark styling */
        [data-testid="stSidebar"] [data-baseweb="select"] div[class*="control"],
        [data-testid="stSidebar"] [data-baseweb="select"] div[class*="ValueContainer"],
        [data-testid="stSidebar"] [data-baseweb="select"] div[class*="placeholder"],
        [data-testid="stSidebar"] [data-baseweb="select"] div[class*="singleValue"] {
            background-color: #1E293B !important;
            color: #E2E8F0 !important;
            border-color: #334155 !important;
        }

        [data-testid="stSidebar"] [data-baseweb="tag"] {
            background-color: #2563EB !important;
            color: #FFFFFF !important;
            border-radius: 4px !important;
            border: none !important;
        }

        [data-testid="stSidebar"] [data-baseweb="tag"] span {
            color: #FFFFFF !important;
        }

        /* Sidebar radio buttons */
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
            background-color: rgba(255,255,255,0.06) !important;
            border-radius: 6px !important;
            padding: 4px 8px !important;
            margin: 2px 0 !important;
            transition: background-color 0.15s ease !important;
        }

        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
            background-color: rgba(37, 99, 235, 0.2) !important;
        }

        /* ─── Sidebar Dividers ───────────────────────────────────── */
        [data-testid="stSidebar"] hr {
            border-top-color: #334155 !important;
        }

        /* ─── Download Button ────────────────────────────────────── */
        .stDownloadButton {
            margin-top: 0.5rem !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# Priority band badge HTML helper
BADGE_STYLES: dict[str, tuple[str, str]] = {
    "HIGH":   ("#FEF2F2", "#B91C1C", "#DC2626"),   # bg, text, border
    "MEDIUM": ("#FFF7ED", "#92400E", "#D97706"),
    "WATCH":  ("#FEFCE8", "#713F12", "#CA8A04"),
    "OTHER":  ("#F8FAFC", "#475569", "#94A3B8"),
}


def priority_badge_html(tier: str) -> str:
    """Return an inline HTML badge pill for a given priority tier."""
    bg, txt, bdr = BADGE_STYLES.get(tier, BADGE_STYLES["OTHER"])
    return (
        f"<span style=\"display:inline-block; padding:2px 10px; border-radius:999px; "
        f"background:{bg}; color:{txt}; border:1px solid {bdr}; "
        f"font-size:10px; font-weight:700; letter-spacing:0.06em; "
        f"vertical-align:middle;\">{tier}</span>"
    )
