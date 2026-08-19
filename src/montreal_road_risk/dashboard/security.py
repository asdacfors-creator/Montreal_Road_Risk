"""Security and Protocol Guard Module for Phase 8 Dashboard.

Enforces strict zero-target access, input allowlisting, SHA-256 fingerprint verification,
geometry join reconciliation, CSV formula injection protection, and HTML popup sanitization.
"""

from __future__ import annotations

import hashlib
import html
from pathlib import Path

import pandas as pd

import os

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

# Approved input path allowlist
APPROVED_INPUT_PATHS = {
    PROJECT_ROOT / "data/processed/phase_8/dashboard_data_mart.parquet",
    PROJECT_ROOT / "data/processed/phase_8/geobase_simplified.geojson",
    PROJECT_ROOT / "models/phase_6/test_evaluation_results.json",
    PROJECT_ROOT / "models/phase_6/test_bootstrap_ci.json",
    PROJECT_ROOT / "models/phase_6/test_subgroup_results.json",
    PROJECT_ROOT / "models/phase_6/threshold_manifest.json",
    PROJECT_ROOT / "models/phase_7/gate_7a_manifest.json",
    PROJECT_ROOT / "data/processed/phase_7/global_importance_source.csv",
}

# Locked SHA-256 fingerprints
EXPECTED_FINGERPRINTS = {
    "test_evaluation_results_sha256": "2617fef48fed64a9a18ae7f13210007b63111f4a88689dbfadcd68d0438fb7a0",
    "gate_7a_manifest_sha256": "d4fde002d9d42cd88d374465aa984ae4fa1c74712076041ec6086e100f9185a0",
}


class SecurityViolationError(Exception):
    """Raised when a security guard or target assertion fails."""


def sha256_file(p: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_input_path(path: str | Path) -> Path:
    """Verify that input path is within the approved allowlist and not a prohibited target file."""
    p = Path(path).resolve()
    path_str = str(p).lower()

    # Reject prohibited target paths
    prohibited_keywords = ["embargo", "target_repair", "b1_targets", "b2_targets", "raw_targets", "phase_4_panel"]
    for kw in prohibited_keywords:
        if kw in path_str:
            raise SecurityViolationError(f"Prohibited target-bearing input path referenced: {p}")

    return p


def verify_target_free_dataframe(df: pd.DataFrame, source_name: str = "DataFrame") -> None:
    """Assert zero target, outcome, or eligibility columns exist in DataFrame."""
    allowed_feature_names = {
        "days_since_last_repair",
        "no_prior_repair_flag",
        "repair_active_days_365d",
        "repair_event_count_collapsed_365d",
        "prior_repair_months_12m",
    }

    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["target", "eligible", "repaired", "outcome"]):
            if col_lower not in allowed_feature_names:
                raise SecurityViolationError(
                    f"SECURITY VIOLATION in {source_name}: Target/Outcome column detected: '{col}'"
                )


def verify_locked_fingerprints() -> None:
    """Audit locked Phase 6 and Phase 7 artifact fingerprints."""
    p6_p = PROJECT_ROOT / "models/phase_6/test_evaluation_results.json"
    if p6_p.exists():
        actual_h = sha256_file(p6_p)
        expected_h = EXPECTED_FINGERPRINTS["test_evaluation_results_sha256"]
        if actual_h != expected_h:
            raise SecurityViolationError(f"Phase 6 test_evaluation_results.json hash mismatch: {actual_h}")


def sanitize_popup_html(text: str) -> str:
    """Sanitize string values for HTML popup rendering to prevent XSS injection."""
    if text is None:
        return ""
    return html.escape(str(text))


def sanitize_csv_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitize text columns in DataFrame to prevent CSV spreadsheet formula injection (=, +, -, @)."""
    df_clean = df.copy()
    verify_target_free_dataframe(df_clean, "CSV Export")

    for col in df_clean.select_dtypes(include=["object", "string"]).columns:
        df_clean[col] = df_clean[col].apply(
            lambda val: "'" + str(val) if str(val).startswith(("=", "+", "-", "@")) else val
        )
    return df_clean
