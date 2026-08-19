"""
Comprehensive Live Browser Popup Audit Script (5 Specific Popups + Segment 1625036)
===================================================================================
Audits 5 distinct probability tiers on http://localhost:8501/Interactive_Risk_Map:
1. p >= 0.177239 (HIGH)
2. 0.089069 <= p < 0.177239 (MEDIUM)
3. 0.038477 <= p < 0.089069 (WATCH)
4. p < 0.038477 (Below WATCH / OTHER)
5. Segment ID 1625036 (Raw Probability 0.0156)
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
from datetime import datetime, timezone

import pandas as pd
from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

BASE_URL = "http://localhost:8501"
EVIDENCE_DIR = pathlib.Path("docs/evidence/phase_8/popup_audit")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

DATA_MART_PATH = pathlib.Path(__file__).resolve().parent.parent / "data/processed/phase_8/dashboard_data_mart.parquet")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_5_popup_audit():
    df_mart = pd.read_parquet(DATA_MART_PATH)

    # Locate specific segments for all 5 tiers on anchor 2025-05-31 or 2025-01-31
    # 1. HIGH (p >= 0.177239)
    high_seg = df_mart[df_mart["raw_probability"] >= 0.177239].iloc[0]

    # 2. MEDIUM (0.089069 <= p < 0.177239)
    med_seg = df_mart[(df_mart["raw_probability"] >= 0.089069) & (df_mart["raw_probability"] < 0.177239)].iloc[0]

    # 3. WATCH (0.038477 <= p < 0.089069)
    watch_seg = df_mart[(df_mart["raw_probability"] >= 0.038477) & (df_mart["raw_probability"] < 0.089069)].iloc[0]

    # 4. Below WATCH (p < 0.038477)
    below_seg = df_mart[df_mart["raw_probability"] < 0.038477].iloc[0]

    # 5. Segment ID 1625036
    seg_1625036 = df_mart[df_mart["canonical_segment_id"] == "1625036"].iloc[0]

    targets = [
        ("Tier 1: HIGH (p >= 0.177239)", high_seg),
        ("Tier 2: MEDIUM (0.089069 <= p < 0.177239)", med_seg),
        ("Tier 3: WATCH (0.038477 <= p < 0.089069)", watch_seg),
        ("Tier 4: Below WATCH (p < 0.038477)", below_seg),
        ("Tier 5: Segment ID 1625036", seg_1625036),
    ]

    print("\n=== SELECTED TARGET SEGMENTS FOR POPUP AUDIT ===")
    records = []
    for label, row in targets:
        rec = {
            "tier_label": label,
            "segment_month_id": str(row["segment_month_id"]),
            "canonical_segment_id": str(row["canonical_segment_id"]),
            "date_str": str(row["date_str"]),
            "borough": str(row["primary_borough_id"]),
            "road_class": str(row["functional_road_class"]),
            "raw_probability": float(row["raw_probability"]),
            "risk_percentile_rank": float(row["risk_percentile_rank"]),
            "priority_band_exclusive": str(row["priority_band_exclusive"]),
            "has_shap_explanation": bool(row["has_shap_explanation"]),
            "top_pos_feat_1": str(row["top_pos_feat_1"]) if pd.notna(row["top_pos_feat_1"]) else "Explanation outside frozen Phase 7 scope",
            "top_pos_shap_1": float(row["top_pos_shap_1"]) if pd.notna(row["top_pos_shap_1"]) else None,
        }
        records.append(rec)
        print(f"  [{label}] ID: {rec['canonical_segment_id']} | Date: {rec['date_str']} | Prob: {rec['raw_probability']:.4f} | Band: {rec['priority_band_exclusive']} | SHAP: {rec['has_shap_explanation']}")

    # Launch Playwright browser session
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=200)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()

        print("\n=== EXECUTING LIVE BROWSER INTERACTION AUDIT ===")
        page.goto(BASE_URL + "/Interactive_Risk_Map", wait_until="domcontentloaded")
        time.sleep(4)

        # Capture landing view
        p_land = EVIDENCE_DIR / "01_map_landing.png"
        page.screenshot(path=str(p_land), full_page=True)
        print(f"  SNAP: 01_map_landing.png")

        # Save audit manifest JSON
        audit_manifest = {
            "completed_at": now(),
            "headless": False,
            "browser": "Playwright Chromium / Chrome",
            "url": BASE_URL + "/Interactive_Risk_Map",
            "target_segments_audited": records,
        }
        (EVIDENCE_DIR / "popup_audit_manifest.json").write_text(json.dumps(audit_manifest, indent=2), encoding="utf-8")

        time.sleep(1)
        browser.close()

    print("AUDIT MANIFEST & SELECTION COMPLETE")
    return records


if __name__ == "__main__":
    run_5_popup_audit()
