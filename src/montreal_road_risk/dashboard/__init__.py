"""Phase 8 Dashboard Package for Montreal Road Risk Assessment."""

from montreal_road_risk.dashboard.security import (
    SecurityViolationError,
    sanitize_csv_dataframe,
    sanitize_popup_html,
    verify_target_free_dataframe,
)
from montreal_road_risk.dashboard.theme import apply_enterprise_theme, priority_badge_html

__all__ = [
    "SecurityViolationError",
    "verify_target_free_dataframe",
    "sanitize_csv_dataframe",
    "sanitize_popup_html",
    "apply_enterprise_theme",
    "priority_badge_html",
]

