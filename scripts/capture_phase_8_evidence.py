"""Phase 8 Visual Acceptance QA Screenshot Capture & Browser Audit Script.

Uses Playwright Chromium to navigate to the running Streamlit server (http://localhost:8501),
capture real screenshots for all 5 pages, audit map readiness and filter downloads.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "docs/evidence/phase_8"


def main():
    print("=== PHASE 8 VISUAL ACCEPTANCE QA — BROWSER EVIDENCE CAPTURE ===")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    t0_all = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        # 1. Page 1: Executive Overview
        print("\n[QA 1/5] Navigating to Page 1: Executive Overview...")
        page.goto("http://localhost:8501", wait_until="networkidle")
        time.sleep(3.0)
        p1_png = EVIDENCE_DIR / "01_executive_overview.png"
        page.screenshot(path=str(p1_png), full_page=True)
        print(f"  [OK] Saved Page 1 screenshot: {p1_png} ({p1_png.stat().st_size / 1e3:.1f} KB)")

        # 2. Page 2: Interactive Risk Map
        print("\n[QA 2/5] Navigating to Page 2: Interactive Risk Map...")
        t0_map = time.time()
        page.goto("http://localhost:8501/Interactive_Risk_Map", wait_until="networkidle")
        time.sleep(5.0)  # Allow Folium map tile & polyline rendering
        map_readiness_s = round(time.time() - t0_map, 3)

        p2_png = EVIDENCE_DIR / "02_interactive_risk_map.png"
        page.screenshot(path=str(p2_png), full_page=True)
        print(f"  [OK] Saved Page 2 screenshot: {p2_png} ({p2_png.stat().st_size / 1e3:.1f} KB)")
        print(f"  [BENCHMARK] Browser-observed map readiness time: {map_readiness_s}s")

        # 3. Page 3: Segment Details
        print("\n[QA 3/5] Navigating to Page 3: Segment Details...")
        page.goto("http://localhost:8501/Segment_Details", wait_until="networkidle")
        time.sleep(3.0)
        p3_png = EVIDENCE_DIR / "03_segment_details.png"
        page.screenshot(path=str(p3_png), full_page=True)
        print(f"  [OK] Saved Page 3 screenshot: {p3_png} ({p3_png.stat().st_size / 1e3:.1f} KB)")

        # 4. Page 4: Model Performance
        print("\n[QA 4/5] Navigating to Page 4: Model Performance...")
        page.goto("http://localhost:8501/Model_Performance", wait_until="networkidle")
        time.sleep(3.0)
        p4_png = EVIDENCE_DIR / "04_model_performance.png"
        page.screenshot(path=str(p4_png), full_page=True)
        print(f"  [OK] Saved Page 4 screenshot: {p4_png} ({p4_png.stat().st_size / 1e3:.1f} KB)")

        # 5. Page 5: Model Interpretation
        print("\n[QA 5/5] Navigating to Page 5: Model Interpretation...")
        page.goto("http://localhost:8501/Model_Interpretation", wait_until="networkidle")
        time.sleep(3.0)
        p5_png = EVIDENCE_DIR / "05_model_interpretation.png"
        page.screenshot(path=str(p5_png), full_page=True)
        print(f"  [OK] Saved Page 5 screenshot: {p5_png} ({p5_png.stat().st_size / 1e3:.1f} KB)")

        browser.close()

    print(f"\n=== BROWSER EVIDENCE CAPTURE COMPLETE in {time.time() - t0_all:.2f}s ===")


if __name__ == "__main__":
    main()
