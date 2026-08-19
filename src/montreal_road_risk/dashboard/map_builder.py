"""Folium Leaflet map building module for Phase 8 Dashboard.

Generates interactive geospatial maps with municipal visual design (D8.6):
- HIGH (Top 5%): Crimson (#DC2626)
- MEDIUM (5-10%): Dark Orange (#D97706)
- WATCH (10-20%): Amber (#CA8A04)
- OTHER (Outside 20%): Slate Gray (#64748B)
"""

from __future__ import annotations

import folium
import geopandas as gpd
import pandas as pd

from montreal_road_risk.dashboard.security import sanitize_popup_html
from montreal_road_risk.dashboard.theme import priority_badge_html

COLOR_MAP = {
    "HIGH":   "#DC2626",   # Vivid Red
    "MEDIUM": "#D97706",   # Amber-Orange
    "WATCH":  "#CA8A04",   # Gold Amber
    "OTHER":  "#64748B",   # Slate Gray
}

WEIGHT_MAP = {
    "HIGH":   5,
    "MEDIUM": 4,
    "WATCH":  2,
    "OTHER":  1,
}

POPUP_HEADER_BG: dict[str, str] = {
    "HIGH":   "#1E293B",
    "MEDIUM": "#1E293B",
    "WATCH":  "#1E293B",
    "OTHER":  "#334155",
}


def _build_popup_html(
    seg_id: str,
    date_str: str,
    borough: str,
    road_class: str,
    raw_prob: float,
    pct_rank: float,
    tier: str,
    color: str,
    has_shap: bool,
    top_driver_raw: object,
    top_shap_raw: object,
) -> str:
    """Build a premium styled popup card HTML for a road segment."""
    badge = priority_badge_html(tier)
    header_bg = POPUP_HEADER_BG.get(tier, "#1E293B")

    # Conditional SHAP block
    if has_shap and pd.notna(top_driver_raw):
        driver = sanitize_popup_html(str(top_driver_raw))
        shap_val = float(top_shap_raw) if pd.notna(top_shap_raw) else 0.0
        shap_sign = "+" if shap_val >= 0 else ""
        shap_color = "#DC2626" if shap_val >= 0 else "#16A34A"
        shap_block = f"""
        <div style="background:#F8FAFC;border-radius:6px;padding:8px 10px;margin-top:8px;
                    border:1px solid #E2E8F0;">
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                      color:#64748B;font-weight:600;margin-bottom:4px;">Top Risk Driver</div>
          <div style="font-size:11px;color:#0F172A;font-weight:600;">
            {driver}
          </div>
          <div style="font-size:11px;color:{shap_color};font-weight:700;margin-top:2px;">
            SHAP&nbsp;&nbsp;{shap_sign}{shap_val:.4f}
          </div>
        </div>"""
    else:
        shap_block = """
        <div style="background:#F8FAFC;border-radius:6px;padding:8px 10px;margin-top:8px;
                    border:1px solid #E2E8F0;">
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                      color:#64748B;font-weight:600;margin-bottom:4px;">Risk Driver</div>
          <div style="font-size:10px;color:#94A3B8;font-style:italic;">
            Explanation outside frozen Phase&nbsp;7 scope
          </div>
        </div>"""

    return f"""
    <div style="font-family:'Inter',system-ui,sans-serif;width:240px;
                border-radius:10px;overflow:hidden;
                box-shadow:0 10px 25px -5px rgba(0,0,0,.15);
                border:1px solid #E2E8F0;">

      <!-- Header -->
      <div style="background:{header_bg};padding:10px 12px;
                  display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:.07em;
                      color:#94A3B8;font-weight:600;">Segment ID</div>
          <div style="font-size:13px;font-weight:700;color:#F1F5F9;
                      letter-spacing:-.01em;">{seg_id}</div>
        </div>
        {badge}
      </div>

      <!-- Body -->
      <div style="padding:10px 12px;background:#FFFFFF;">

        <!-- 2-col metadata grid -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px;">

          <div style="background:#F8FAFC;border-radius:6px;padding:6px 8px;">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                        color:#64748B;font-weight:600;">Raw Prob.</div>
            <div style="font-size:12px;font-weight:700;color:{color};">{raw_prob:.4f}</div>
          </div>

          <div style="background:#F8FAFC;border-radius:6px;padding:6px 8px;">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                        color:#64748B;font-weight:600;">Pct. Rank</div>
            <div style="font-size:12px;font-weight:700;color:#0F172A;">{pct_rank:.1f}%</div>
          </div>

          <div style="background:#F8FAFC;border-radius:6px;padding:6px 8px;">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                        color:#64748B;font-weight:600;">Anchor Date</div>
            <div style="font-size:11px;font-weight:500;color:#0F172A;">{date_str}</div>
          </div>

          <div style="background:#F8FAFC;border-radius:6px;padding:6px 8px;">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                        color:#64748B;font-weight:600;">Borough</div>
            <div style="font-size:11px;font-weight:500;color:#0F172A;">{borough}</div>
          </div>

        </div>

        <!-- Road Class full-width -->
        <div style="background:#F8FAFC;border-radius:6px;padding:6px 8px;margin-bottom:0;">
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:.06em;
                      color:#64748B;font-weight:600;">Road Class</div>
          <div style="font-size:11px;font-weight:500;color:#0F172A;">{road_class}</div>
        </div>

        {shap_block}

        <!-- Footer -->
        <div style="margin-top:8px;padding-top:6px;border-top:1px solid #F1F5F9;
                    font-size:9px;color:#CBD5E1;font-style:italic;text-align:center;">
          Non-causal risk model attribution
        </div>

      </div>
    </div>
    """


def build_risk_map(
    df_filtered: pd.DataFrame,
    gdf_simplified: gpd.GeoDataFrame,
    max_segments: int = 10000,
) -> tuple[folium.Map, int, str]:
    """Build a Folium map of filtered road segments with enterprise popup card design."""
    df_map_sub = df_filtered.copy()

    total_matching = len(df_map_sub)
    warning_msg = ""
    if total_matching > max_segments:
        df_map_sub = df_map_sub.sort_values(by="risk_percentile_rank", ascending=False).head(max_segments)
        warning_msg = (
            f"PERFORMANCE NOTICE: Displaying top {max_segments:,} segments out of {total_matching:,} "
            f"matching filters. Please narrow filters (e.g. select a specific borough or tier) for full detail."
        )

    gdf_joined = gdf_simplified.merge(df_map_sub, on="canonical_segment_id", how="inner")
    displayed_count = len(gdf_joined)

    mtl_lat, mtl_lon = 45.5017, -73.5673
    m = folium.Map(
        location=[mtl_lat, mtl_lon],
        zoom_start=11,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    for _idx, row in gdf_joined.iterrows():
        tier = row.get("priority_band_exclusive", "OTHER")
        color = COLOR_MAP.get(tier, "#64748B")
        weight = WEIGHT_MAP.get(tier, 1)

        seg_id = sanitize_popup_html(row.get("canonical_segment_id", "N/A"))
        date_str = sanitize_popup_html(row.get("date_str", "N/A"))
        borough = sanitize_popup_html(row.get("primary_borough_id", "N/A"))
        road_class = sanitize_popup_html(row.get("functional_road_class", "N/A"))
        raw_prob = float(row.get("raw_probability", 0.0))
        pct_rank = float(row.get("risk_percentile_rank", 0.0))
        has_shap = bool(row.get("has_shap_explanation", False))
        top_driver_raw = row.get("top_pos_feat_1", None)
        top_shap_raw = row.get("top_pos_shap_1", None)

        popup_html = _build_popup_html(
            seg_id=seg_id,
            date_str=date_str,
            borough=borough,
            road_class=road_class,
            raw_prob=raw_prob,
            pct_rank=pct_rank,
            tier=tier,
            color=color,
            has_shap=has_shap,
            top_driver_raw=top_driver_raw,
            top_shap_raw=top_shap_raw,
        )

        geom = row.geometry
        if geom is not None and not geom.is_empty:
            if geom.geom_type == "LineString":
                coords = [(lat, lon) for lon, lat in geom.coords]
                folium.PolyLine(
                    locations=coords,
                    color=color,
                    weight=weight,
                    opacity=0.9,
                    popup=folium.Popup(popup_html, max_width=260),
                ).add_to(m)
            elif geom.geom_type == "MultiLineString":
                for part in geom.geoms:
                    coords = [(lat, lon) for lon, lat in part.coords]
                    folium.PolyLine(
                        locations=coords,
                        color=color,
                        weight=weight,
                        opacity=0.9,
                        popup=folium.Popup(popup_html, max_width=260),
                    ).add_to(m)

    return m, displayed_count, warning_msg
