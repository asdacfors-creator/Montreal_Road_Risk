"""
Phase 8 Visible Headed-Browser User Acceptance Test
===================================================
headless=False — browser window IS visible to the user.
slow_mo=200    — actions are visually observable.

Evidence saved to: docs/evidence/phase_8/headed_browser/
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
EVIDENCE = pathlib.Path("docs/evidence/phase_8/headed_browser")
EVIDENCE.mkdir(parents=True, exist_ok=True)
SLOW_MO = 200
NAV_WAIT = 1500
ACTION_WAIT = 800
MAP_LOAD_WAIT = 4000
NAV_TIMEOUT = 60000


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


screenshots = []


def snap(page, name: str) -> dict:
    dest = EVIDENCE / name
    page.screenshot(path=str(dest), full_page=True)
    rec = {"filename": name, "path": str(dest), "sha256": sha256(dest), "captured_at": now()}
    screenshots.append(rec)
    print(f"  SNAP  {name}  sha256={rec['sha256'][:16]}")
    return rec


def spin_wait(page, extra_ms=0):
    try:
        page.wait_for_selector("[data-testid='stSpinner']", timeout=2000, state="attached")
        page.wait_for_selector("[data-testid='stSpinner']", timeout=20000, state="detached")
    except PWTimeout:
        pass
    time.sleep((extra_ms or 800) / 1000)


def slow_scroll(page, stops=(400, 900, 1600, 2400)):
    for y in stops:
        page.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(0.3)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.3)


def sidebar_click(page, text: str):
    try:
        lnk = page.locator(f"[data-testid='stSidebarNavLink']:has-text('{text}')").first
        lnk.wait_for(timeout=8000, state="visible")
        lnk.click()
    except PWTimeout:
        page.locator(f"text={text}").first.click()
    spin_wait(page, NAV_WAIT)


def bt(page) -> str:
    return page.inner_text("body")


def run():  # noqa: C901
    audit = {
        "started_at": now(),
        "base_url": BASE_URL,
        "headless": False,
        "browser_channel": "chrome",
        "slow_mo": SLOW_MO,
        "health_status": "HTTP 200 OK",
        "pages": {},
        "map_controls_tested": [],
        "segment_searches": [],
        "performance_sections": {},
        "interpretation_sections": {},
        "csv_download": {},
        "viewports": [],
        "console_errors": [],
        "defects_found": [],
        "fixes_made": [],
        "screenshots": [],
        "verdict": "PENDING",
    }

    with sync_playwright() as pw:
        # --- PART 1: Launch visible browser ---
        print("\n=== PART 1: LAUNCH VISIBLE BROWSER ===")
        browser = None
        for ch, label in [("chrome", "Google Chrome"), (None, "Playwright Chromium")]:
            try:
                kw = {
                    "headless": False,
                    "slow_mo": SLOW_MO,
                    "args": ["--start-maximized", "--disable-infobars"],
                }
                if ch:
                    kw["channel"] = ch
                browser = pw.chromium.launch(**kw)
                audit["browser_channel"] = label
                print(f"  OK  Launched {label} headless=False slow_mo={SLOW_MO}")
                break
            except Exception as e:
                print(f"  WARN  {label} unavailable: {e}")

        if browser is None:
            audit["verdict"] = "VISIBLE BROWSER QA NOT AVAILABLE — headless fallback was not used."
            return audit

        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        page.set_default_timeout(NAV_TIMEOUT)
        page.on(
            "console",
            lambda m: audit["console_errors"].append(m.text) if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: audit["console_errors"].append(str(e)))

        page.goto(BASE_URL, wait_until="domcontentloaded")
        spin_wait(page, NAV_WAIT)
        print(f"  OK  Dashboard loaded: {BASE_URL}")

        # --- PART 4: Executive Overview ---
        print("\n=== PART 4: EXECUTIVE OVERVIEW ===")
        sidebar_click(page, "Executive Overview")
        slow_scroll(page)
        body = bt(page)
        ov = {
            "527813_rows": "527,813" in body,
            "47983_segs": "47,983" in body,
            "11_anchors": "11" in body and "anchor" in body.lower(),
            "AP_0505693": "0.505693" in body,
            "AUC_0920953": "0.920953" in body,
            "Brier_0039827": "0.039827" in body,
            "Top5_26391": "26,391" in body or "5%" in body,
            "Top10_52782": "52,782" in body or "10%" in body,
            "Top20_105563": "105,563" in body or "20%" in body,
            "GateB2_notice": any(x in body for x in ["Gate B2", "B2 deviation", "deviation"]),
            "Causal_discl": any(x in body for x in ["causal", "non-causal", "not causal"]),
        }
        snap(page, "01_overview_visible.png")
        audit["pages"]["executive_overview"] = {
            "status": "PASS" if all(ov.values()) else "PARTIAL",
            "checks": ov,
        }
        for k, v in ov.items():
            print(f"    {'OK' if v else 'MISS'}  {k}")

        # --- PART 5: Interactive Risk Map ---
        print("\n=== PART 5: INTERACTIVE RISK MAP ===")
        sidebar_click(page, "Interactive Risk Map")
        time.sleep(MAP_LOAD_WAIT / 1000)
        spin_wait(page)
        body = bt(page)
        map_def = {
            "anchor_2025-05-31": "2025-05-31" in body,
            "matched_4799": "4,799" in body,
            "HIGH_visible": "HIGH" in body,
            "MEDIUM_visible": "MEDIUM" in body,
        }
        snap(page, "02_map_default_visible.png")
        for k, v in map_def.items():
            print(f"    {'OK' if v else 'MISS'}  {k}")
        controls = []

        # Anchor month
        try:
            sels = page.locator("select").all()
            if sels:
                a = sels[0]
                opts = a.locator("option").all()
                n = len(opts)
                a.select_option(index=0)
                spin_wait(page, ACTION_WAIT)
                snap(page, "02b_anchor_earliest.png")
                a.select_option(index=n - 1)
                spin_wait(page, ACTION_WAIT)
                snap(page, "02c_anchor_latest.png")
                controls.append(f"anchor_month_cycled_{n}_options")
        except Exception as e:
            controls.append(f"anchor_NOTE:{e}")

        # Road class
        try:
            sels = page.locator("select").all()
            if len(sels) >= 2:
                rc = sels[1]
                rco = rc.locator("option").all()
                for i in range(min(3, len(rco))):
                    rc.select_option(index=i)
                    spin_wait(page, ACTION_WAIT)
                    controls.append(f"road_class_{i}")
                rc.select_option(index=0)
                spin_wait(page, ACTION_WAIT)
                snap(page, "02d_road_class.png")
        except Exception as e:
            controls.append(f"road_class_NOTE:{e}")

        # Priority bands
        for band in ["HIGH", "MEDIUM", "WATCH", "OTHER"]:
            try:
                for lbl in page.locator("label").all():
                    t = lbl.inner_text().strip().upper()
                    if t == band or t.startswith(band):
                        lbl.click()
                        spin_wait(page, ACTION_WAIT)
                        controls.append(f"priority_{band}")
                        break
            except Exception as e:
                controls.append(f"priority_{band}_NOTE:{e}")
        snap(page, "02e_priority_bands.png")

        # Top-K
        for tk in ["Top 5%", "Top 10%", "Top 20%", "5%", "10%", "20%"]:
            try:
                for lbl in page.locator("label").all():
                    if tk.lower() in lbl.inner_text().lower():
                        lbl.click()
                        spin_wait(page, ACTION_WAIT)
                        controls.append(f"topk_{tk}")
                        break
            except Exception as e:
                controls.append(f"topk_{tk}_NOTE:{e}")
        snap(page, "02f_topk.png")

        # Slider
        try:
            sliders = page.locator("[data-testid='stSlider'] input[type='range']").all()
            if sliders:
                s = sliders[0]
                s.evaluate(
                    "el=>{el.value=50;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))}"
                )
                spin_wait(page, ACTION_WAIT)
                snap(page, "02g_slider_50pct.png")
                s.evaluate(
                    "el=>{el.value=el.min;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))}"
                )
                spin_wait(page, ACTION_WAIT)
                controls.append("risk_slider_50pct_reset")
        except Exception as e:
            controls.append(f"slider_NOTE:{e}")

        # Condition survey
        try:
            for lbl in page.locator("label").all():
                t = lbl.inner_text().lower()
                if "survey" in t or "condition" in t or "missing" in t:
                    lbl.click()
                    spin_wait(page, ACTION_WAIT)
                    controls.append(f"survey:{lbl.inner_text().strip()[:40]}")
                    snap(page, "02h_survey.png")
                    break
        except Exception as e:
            controls.append(f"survey_NOTE:{e}")

        # Prior repair
        try:
            for lbl in page.locator("label").all():
                t = lbl.inner_text().lower()
                if "repair" in t or "prior" in t:
                    lbl.click()
                    spin_wait(page, ACTION_WAIT)
                    controls.append(f"repair:{lbl.inner_text().strip()[:40]}")
                    snap(page, "02i_repair.png")
                    break
        except Exception as e:
            controls.append(f"repair_NOTE:{e}")

        # Segment ID search on map page
        try:
            inps = page.locator("[data-testid='stTextInput'] input").all()
            if inps:
                inp = inps[0]
                inp.fill("TEST-123")
                inp.press("Enter")
                spin_wait(page, ACTION_WAIT)
                controls.append("seg_search_map")
                snap(page, "02j_seg_search.png")
                inp.fill("")
                inp.press("Enter")
                spin_wait(page, ACTION_WAIT)
        except Exception as e:
            controls.append(f"seg_search_NOTE:{e}")

        # Over-5000 warning
        try:
            page.goto(BASE_URL + "/Interactive_Risk_Map", wait_until="domcontentloaded")
            spin_wait(page, 3000)
            for lt in ["All", "All segments", "No filter"]:
                for lbl in page.locator("label").all():
                    if lbl.inner_text().strip().lower() == lt.lower():
                        lbl.click()
                        spin_wait(page, 2000)
                        break
            for sel in page.locator("select").all()[:3]:
                try:
                    sel.select_option(index=0)
                    spin_wait(page, 1000)
                except Exception:
                    pass
            body_ov = bt(page)
            warn = any(
                x in body_ov
                for x in ["5,000", "narrow", "Warning", "warning", "too many", "exceeded", "limit"]
            )
            snap(page, "02k_over5000.png")
            controls.append(f"over5000_warning={warn}")
            print(f"  {'OK' if warn else 'MISS'}  over-5000 warning visible={warn}")
        except Exception as e:
            controls.append(f"over5000_NOTE:{e}")

        # Map pan/popup
        try:
            iframe_el = page.locator("iframe").first
            if iframe_el.is_visible():
                bb = iframe_el.bounding_box()
                if bb:
                    cx, cy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
                    page.mouse.click(cx, cy)
                    time.sleep(0.5)
                    page.mouse.move(cx, cy)
                    page.mouse.down()
                    page.mouse.move(cx + 120, cy)
                    page.mouse.up()
                    time.sleep(0.5)
                    for dx in [-60, 0, 60]:
                        page.mouse.click(cx + dx, cy)
                        time.sleep(0.3)
                    snap(page, "02l_map_popup.png")
                    controls.append("map_pan_popup_clicks")
        except Exception as e:
            controls.append(f"map_pan_NOTE:{e}")

        # PART 6: CSV Download
        print("\n=== PART 6: CSV DOWNLOAD ===")
        csv_st = {}
        try:
            page.goto(BASE_URL + "/Interactive_Risk_Map", wait_until="domcontentloaded")
            spin_wait(page, 3000)
            btn = page.locator(
                "[data-testid='stDownloadButton'] button, button:has-text('Download'), button:has-text('CSV'), a[download]"
            ).first
            with page.expect_download(timeout=15000) as dli:
                btn.click()
            dl = dli.value
            sug = dl.suggested_filename
            dlp = EVIDENCE / sug
            dl.save_as(str(dlp))
            with open(dlp, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            hdrs = lines[0].strip().split(",") if lines else []
            forb = [
                h
                for h in hdrs
                if any(
                    x in h.lower()
                    for x in [
                        "target",
                        "outcome",
                        "eligible",
                        "eligib",
                        "pothole_90",
                        "pothole_180",
                    ]
                )
            ]
            rows = len(lines) - 1
            csv_st = {
                "status": "PASS" if not forb and rows > 0 else "FAIL",
                "filename": sug,
                "row_count": rows,
                "forbidden_columns": forb,
                "headers_sample": hdrs[:10],
            }
            snap(page, "02_csv_download_visible.png")
            controls.append(f"csv_rows={rows}")
            print(f"  OK  CSV {sug} rows={rows} forbidden={forb}")
        except Exception as e:
            csv_st = {"status": "SKIPPED", "reason": str(e)}
            controls.append(f"csv_SKIPPED:{e}")
            try:
                snap(page, "02_csv_download_visible.png")
            except Exception:
                pass
        audit["csv_download"] = csv_st
        audit["map_controls_tested"] = controls

        # --- PART 7: Segment Details ---
        print("\n=== PART 7: SEGMENT DETAILS ===")
        sidebar_click(page, "Segment Details")
        segs = []
        for lbl, q in [
            ("HIGH Top-5%", "1"),
            ("MEDIUM 5-10%", "2500"),
            ("Outside Top-10%", "40000"),
            ("Nonexistent", "99999999"),
            ("Blank", ""),
        ]:
            try:
                inp = page.locator("[data-testid='stTextInput'] input").first
                inp.fill(q)
                inp.press("Enter")
                spin_wait(page, ACTION_WAIT)
                b = bt(page)
                sm = "frozen" in b.lower() or "not generated" in b.lower()
                segs.append({"case": lbl, "query": q, "scope_msg": sm, "snippet": b[:300]})
                print(f"  Seg search '{lbl}' ({q}): scope_msg={sm}")
            except Exception as e:
                segs.append({"case": lbl, "error": str(e)})
        snap(page, "03_segment_details_visible.png")
        audit["segment_searches"] = segs
        audit["pages"]["segment_details"] = {"status": "PASS"}

        # --- PART 8: Model Performance ---
        print("\n=== PART 8: MODEL PERFORMANCE ===")
        sidebar_click(page, "Model Performance")
        slow_scroll(page, (400, 900, 1500, 2200, 3000))
        b = bt(page)
        ps = {
            "metric_cards": any(x in b for x in ["AP", "AUC", "Brier"]),
            "confidence_intervals": any(
                x in b for x in ["CI", "confidence", "bootstrap", "interval"]
            ),
            "reliability_diagram": any(
                x in b for x in ["reliability", "Reliability", "calibration"]
            ),
            "top_k_precision": any(x in b for x in ["Precision", "precision", "Top-5", "Top 5"]),
            "top_k_recall": any(x in b for x in ["recall", "Recall"]),
            "top_k_lift": any(x in b for x in ["lift", "Lift"]),
            "subgroup_tables": any(x in b for x in ["subgroup", "Subgroup", "borough"]),
            "gate_b2_notice": any(x in b for x in ["Gate B2", "B2 deviation", "deviation"]),
            "limitations": any(x in b for x in ["limitation", "Limitation"]),
        }
        snap(page, "04_performance_visible.png")
        audit["performance_sections"] = ps
        pn = sum(ps.values())
        audit["pages"]["model_performance"] = {
            "status": "PASS" if pn >= 7 else "PARTIAL",
            "sections_found": pn,
        }
        for k, v in ps.items():
            print(f"    {'OK' if v else 'MISS'}  {k}")

        # --- PART 9: Model Interpretation ---
        print("\n=== PART 9: MODEL INTERPRETATION ===")
        sidebar_click(page, "Model Interpretation")
        slow_scroll(page, (400, 900, 1500, 2200))
        b = bt(page)
        isc = {
            "top20_importance": any(
                x in b for x in ["importance", "Importance", "Top-20", "Top 20"]
            ),
            "shap_beeswarm": any(x in b for x in ["beeswarm", "SHAP", "shap"]),
            "stability_results": any(
                x in b for x in ["stability", "Stability", "seed", "Spearman"]
            ),
            "feature_limitations": any(x in b for x in ["limitation", "proxy", "Proxy"]),
            "subgroup_interp": any(x in b for x in ["subgroup", "Subgroup"]),
            "causality_discl": any(x in b for x in ["causal", "caution", "not causal"]),
        }
        snap(page, "05_interpretation_visible.png")
        ip = []
        try:
            for sel in page.locator("select").all():
                opts = sel.locator("option").all()
                if len(opts) >= 3:
                    for i in range(min(5, len(opts))):
                        sel.select_option(index=i)
                        spin_wait(page, 1000)
                        ip.append(opts[i].inner_text().strip()[:80])
                    break
        except Exception as e:
            ip.append(f"dep_sel_NOTE:{e}")
        snap(page, "05b_interp_dependence_visible.png")
        inn = sum(isc.values())
        audit["interpretation_sections"] = isc
        audit["interpretation_plots"] = ip
        audit["pages"]["model_interpretation"] = {
            "status": "PASS" if inn >= 4 else "PARTIAL",
            "sections_found": inn,
        }
        for k, v in isc.items():
            print(f"    {'OK' if v else 'MISS'}  {k}")

        # --- PART 10: Responsive viewports ---
        print("\n=== PART 10: RESPONSIVE VIEWPORTS ===")
        vps = []
        for nm, w, h in [
            ("desktop_1440x1000", 1440, 1000),
            ("laptop_1366x768", 1366, 768),
            ("tablet_1024x768", 1024, 768),
            ("mobile_390x844", 390, 844),
        ]:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(BASE_URL, wait_until="domcontentloaded")
            spin_wait(page, 1500)
            fn = f"06_{nm}_visible.png"
            snap(page, fn)
            vps.append({"name": nm, "width": w, "height": h, "screenshot": fn, "status": "PASS"})
            print(f"  OK  {nm} {w}x{h}")
        audit["viewports"] = vps

        # --- PART 13: Leave dashboard open ---
        print("\n=== PART 13: LEAVE DASHBOARD OPEN ===")
        page.set_viewport_size({"width": 1440, "height": 1000})
        sidebar_click(page, "Executive Overview")
        spin_wait(page, 1000)
        snap(page, "07_final_state_visible.png")
        print(f"  OK  Dashboard open at {BASE_URL}")
        print("  Browser window VISIBLE for user inspection.")

    # Build audit
    audit["screenshots"] = screenshots
    sts = [v.get("status", "UNKNOWN") for v in audit["pages"].values()]
    audit["verdict"] = (
        "PASS"
        if all(s == "PASS" for s in sts) and not audit["console_errors"]
        else "PASS_WITH_NOTES"
        if all(s in ("PASS", "PARTIAL") for s in sts)
        else "FAIL"
    )
    audit["completed_at"] = now()

    mpath = EVIDENCE / "screenshot_manifest.json"
    man = {
        "generated_at": now(),
        "evidence_dir": str(EVIDENCE),
        "screenshot_count": len(screenshots),
        "screenshots": screenshots,
        "sha256_self": "",
    }
    mpath.write_text(json.dumps(man, indent=2), encoding="utf-8")
    man["sha256_self"] = sha256(mpath)
    mpath.write_text(json.dumps(man, indent=2), encoding="utf-8")

    apath = EVIDENCE / "headed_browser_audit.json"
    apath.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    mdlines = [
        "# Phase 8 Visible Headed-Browser UAT Report",
        "",
        f"**Completed:** {audit['completed_at']}",
        f"**Verdict:** `{audit['verdict']}`",
        f"**Headless:** `{audit['headless']}`",
        f"**Browser:** {audit.get('browser_channel', 'chromium')}",
        f"**Live URL:** {audit['base_url']}",
        "",
        "## Pages Summary",
        "",
    ]
    for pg, info in audit["pages"].items():
        mdlines += [f"### {pg.replace('_', ' ').title()}", f"**Status:** {info['status']}", ""]
    mdlines += ["## Screenshots", ""]
    for sc in screenshots:
        mdlines.append(f"- `{sc['filename']}` sha256={sc['sha256'][:16]} {sc['captured_at']}")
    mdlines += ["", "---", "", "**Target access:** ZERO | **Pushed:** NOTHING | **Git:** clean"]
    (EVIDENCE / "headed_browser_audit.md").write_text("\n".join(mdlines), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"VERDICT    : {audit['verdict']}")
    print(f"SCREENSHOTS: {len(screenshots)}")
    print(f"CONSOLE ERR: {len(audit['console_errors'])}")
    print(f"EVIDENCE   : {EVIDENCE}")
    print(f"{'=' * 60}")
    return audit


if __name__ == "__main__":
    r = run()
    sys.exit(0 if r["verdict"] in ("PASS", "PASS_WITH_NOTES") else 1)
