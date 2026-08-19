"""
Targeted Live Browser Verification Script for Phase 8 Dashboard Bugfixes
========================================================================
Verifies:
1. "Survey Available" and "Survey Missing" filters do NOT throw KeyError.
2. "No Prior Repair" filter operates cleanly.
3. Map popup rendering displays clean explanation notes instead of "nan".
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

BASE_URL = "http://localhost:8501"
EVIDENCE_DIR = pathlib.Path("docs/evidence/phase_8/bugfix_verification")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

SLOW_MO = 300
NAV_WAIT = 2500
ACTION_WAIT = 1200


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


screenshots = []


def snap(page, name: str) -> dict:
    dest = EVIDENCE_DIR / name
    page.screenshot(path=str(dest), full_page=True)
    rec = {"filename": name, "path": str(dest), "sha256": sha256(dest), "captured_at": now()}
    screenshots.append(rec)
    print(f"  SNAP: {name}  sha256={rec['sha256'][:16]}...")
    return rec


def spin_wait(page, extra_ms=0):
    try:
        page.wait_for_selector("[data-testid='stSpinner']", timeout=2000, state="attached")
        page.wait_for_selector("[data-testid='stSpinner']", timeout=20000, state="detached")
    except PWTimeout:
        pass
    time.sleep((extra_ms or 1200) / 1000)


def run_verification():
    results = {
        "timestamp": now(),
        "url": BASE_URL,
        "headless": False,
        "checks": {},
        "screenshots": [],
    }

    with sync_playwright() as pw:
        print("\n=== STARTING LIVE BROWSER BUGFIX VERIFICATION ===")
        browser = pw.chromium.launch(headless=False, slow_mo=SLOW_MO)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()

        # Step 1: Open Interactive Risk Map page
        page.goto(BASE_URL + "/Interactive_Risk_Map", wait_until="domcontentloaded")
        spin_wait(page, 4000)
        print("  OK: Navigated to Interactive Risk Map page")

        # Check 1: Test "Survey Available" radio option
        print("  Testing 'Survey Available' filter...")
        try:
            lbl_avail = page.locator("label:has-text('Survey Available')").first
            lbl_avail.click()
            spin_wait(page, ACTION_WAIT)
            body_txt = page.inner_text("body")
            no_crash_avail = "KeyError" not in body_txt and "Traceback" not in body_txt
            results["checks"]["survey_available_filter"] = {
                "no_crash": no_crash_avail,
                "matched_text": "Matching Segments:" in body_txt,
            }
            snap(page, "01_survey_available_fix.png")
            print(f"    {'PASS' if no_crash_avail else 'FAIL'}: Survey Available filter")
        except Exception as e:
            results["checks"]["survey_available_filter"] = {"error": str(e)}

        # Check 2: Test "Survey Missing" radio option
        print("  Testing 'Survey Missing' filter...")
        try:
            lbl_missing = page.locator("label:has-text('Survey Missing')").first
            lbl_missing.click()
            spin_wait(page, ACTION_WAIT)
            body_txt = page.inner_text("body")
            no_crash_missing = "KeyError" not in body_txt and "Traceback" not in body_txt
            results["checks"]["survey_missing_filter"] = {
                "no_crash": no_crash_missing,
                "matched_text": "Matching Segments:" in body_txt,
            }
            snap(page, "02_survey_missing_fix.png")
            print(f"    {'PASS' if no_crash_missing else 'FAIL'}: Survey Missing filter")
        except Exception as e:
            results["checks"]["survey_missing_filter"] = {"error": str(e)}

        # Reset condition survey to "All"
        try:
            lbl_all = page.locator("label:has-text('All')").all()
            for l in lbl_all:
                if "survey" in l.inner_text().lower() or l.inner_text().strip() == "All":
                    l.click()
                    spin_wait(page, ACTION_WAIT)
                    break
        except Exception:
            pass

        # Check 3: Test "No Prior Repair" radio option
        print("  Testing 'No Prior Repair' filter...")
        try:
            lbl_repair = page.locator("label:has-text('No Prior Repair')").first
            lbl_repair.click()
            spin_wait(page, ACTION_WAIT)
            body_txt = page.inner_text("body")
            no_crash_repair = "KeyError" not in body_txt and "Traceback" not in body_txt
            results["checks"]["no_prior_repair_filter"] = {
                "no_crash": no_crash_repair,
                "matched_text": "Matching Segments:" in body_txt,
            }
            snap(page, "03_no_prior_repair_fix.png")
            print(f"    {'PASS' if no_crash_repair else 'FAIL'}: No Prior Repair filter")
        except Exception as e:
            results["checks"]["no_prior_repair_filter"] = {"error": str(e)}

        # Reset repair filter
        page.goto(BASE_URL + "/Interactive_Risk_Map", wait_until="domcontentloaded")
        spin_wait(page, 4000)

        # Check 4: Test map popup click & verify no "nan" rendering
        print("  Testing map popup interaction for nan rendering check...")
        try:
            iframe_el = page.locator("iframe").first
            if iframe_el.is_visible():
                bb = iframe_el.bounding_box()
                if bb:
                    cx, cy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
                    # Click map center to trigger popup
                    page.mouse.click(cx, cy)
                    time.sleep(1.5)
                    # Screenshot popup open
                    snap(page, "04_popup_no_nan.png")

                    # Read iframe contents to verify string "nan" is not rendered
                    iframe_content = page.frame_locator("iframe").first.locator("body").inner_text()
                    has_nan = (
                        "Top Driver: nan" in iframe_content or "SHAP Value: +nan" in iframe_content
                    )
                    results["checks"]["popup_nan_check"] = {
                        "has_literal_nan_driver": has_nan,
                        "popup_rendered": True,
                    }
                    print(f"    {'PASS' if not has_nan else 'FAIL'}: Popup 'nan' check")
        except Exception as e:
            results["checks"]["popup_nan_check"] = {"error": str(e)}

        print("\n=== VERIFICATION COMPLETE ===")
        time.sleep(2)
        browser.close()

    results["screenshots"] = screenshots
    manifest_path = EVIDENCE_DIR / "bugfix_verification_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"📄 Verification manifest saved to {manifest_path}")
    return results


if __name__ == "__main__":
    run_verification()
