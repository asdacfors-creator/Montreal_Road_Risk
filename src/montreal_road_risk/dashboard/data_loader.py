"""Data loading and caching module for Phase 8 Dashboard.

Loads target-free dashboard data mart, simplified geometry GeoJSON, locked Phase 6 aggregate JSONs,
and Phase 7 interpretation artifacts with fingerprint & zero-target security verification.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import streamlit as st

from montreal_road_risk.dashboard.security import (
    verify_locked_fingerprints,
    verify_target_free_dataframe,
)

def _resolve_project_root() -> Path:
    """Resolve the application root directory portably."""
    env_root = os.environ.get("MONTREAL_ROAD_RISK_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "app.py").exists() and (candidate / "pyproject.toml").exists():
            return candidate

    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "app.py").exists() and (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    cwd = Path.cwd()
    if (cwd / "app.py").exists() and (cwd / "pyproject.toml").exists():
        return cwd

    raise RuntimeError(
        "Montreal Road Risk project root not found. "
        "Set the MONTREAL_ROAD_RISK_ROOT environment variable to the "
        "directory containing app.py and pyproject.toml."
    )

PROJECT_ROOT: Path = _resolve_project_root()
DATA_MART_PATH = PROJECT_ROOT / "data/processed/phase_8/dashboard_data_mart.parquet"
GEOJSON_PATH = PROJECT_ROOT / "data/processed/phase_8/geobase_simplified.geojson"
P6_RESULTS_PATH = PROJECT_ROOT / "models/phase_6/test_evaluation_results.json"
P6_BOOTSTRAP_PATH = PROJECT_ROOT / "models/phase_6/test_bootstrap_ci.json"
P6_SUBGROUP_PATH = PROJECT_ROOT / "models/phase_6/test_subgroup_results.json"
P6_THRESHOLDS_PATH = PROJECT_ROOT / "models/phase_6/threshold_manifest.json"
P7_MANIFEST_PATH = PROJECT_ROOT / "models/phase_7/gate_7a_manifest.json"
P7_GLOBAL_IMPORTANCE_PATH = PROJECT_ROOT / "data/processed/phase_7/global_importance_source.csv"


@st.cache_data(show_spinner=False)
def load_dashboard_data_mart() -> pd.DataFrame:
    """Load pre-computed target-free dashboard data mart with security verification."""
    verify_locked_fingerprints()
    if not DATA_MART_PATH.exists():
        raise FileNotFoundError(f"Dashboard Data Mart not found: {DATA_MART_PATH}. Run build_phase_8_data_mart.py first.")

    df = pd.read_parquet(DATA_MART_PATH)
    verify_target_free_dataframe(df, "Dashboard Data Mart")
    return df


@st.cache_data(show_spinner=False)
def load_simplified_geometry() -> gpd.GeoDataFrame:
    """Load simplified geometry GeoJSON with security verification."""
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(f"Simplified GeoJSON not found: {GEOJSON_PATH}. Run build_phase_8_geometry.py first.")

    gdf = gpd.read_file(GEOJSON_PATH)
    verify_target_free_dataframe(gdf, "Simplified GeoJSON Geometry")
    gdf["canonical_segment_id"] = gdf["canonical_segment_id"].astype(str).str.strip()
    return gdf


@st.cache_data(show_spinner=False)
def load_phase6_aggregate_results() -> dict[str, Any]:
    """Load locked Phase 6 aggregate metric JSON artifacts."""
    verify_locked_fingerprints()
    res = {}
    if P6_RESULTS_PATH.exists():
        res["eval_results"] = json.loads(P6_RESULTS_PATH.read_text(encoding="utf-8"))
    if P6_BOOTSTRAP_PATH.exists():
        res["bootstrap_ci"] = json.loads(P6_BOOTSTRAP_PATH.read_text(encoding="utf-8"))
    if P6_SUBGROUP_PATH.exists():
        res["subgroup_results"] = json.loads(P6_SUBGROUP_PATH.read_text(encoding="utf-8"))
    if P6_THRESHOLDS_PATH.exists():
        res["thresholds"] = json.loads(P6_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    return res


@st.cache_data(show_spinner=False)
def load_phase7_interpretation_artifacts() -> dict[str, Any]:
    """Load Phase 7 interpretation manifest and global importance CSV."""
    res = {}
    if P7_MANIFEST_PATH.exists():
        res["manifest"] = json.loads(P7_MANIFEST_PATH.read_text(encoding="utf-8"))
    if P7_GLOBAL_IMPORTANCE_PATH.exists():
        df_imp = pd.read_csv(P7_GLOBAL_IMPORTANCE_PATH)
        verify_target_free_dataframe(df_imp, "Global Importance CSV")
        res["global_importance"] = df_imp
    return res
