# Phase 8 Visible Headed-Browser User Acceptance Test Report

**Completed:** 2026-07-21T16:48:34.436738+00:00  
**Verdict:** `PASS`  
**Headless:** `False`  
**Browser:** Google Chrome / Playwright Chromium  
**Live URL:** http://localhost:8501  
**Health Result:** HTTP 200 OK  

## Page Acceptance Results

- **Executive Overview:** PASS (527,813 test rows, 47,983 segments, 11 anchors, AP=0.505693, ROC-AUC=0.920953, Brier=0.039827, Gate B2 deviation notice, non-causal disclaimer verified)
- **Interactive Risk Map:** PASS (2025-05-31 default anchor, 4,799 HIGH+MEDIUM default candidates, all sidebar filters operational, popup HTML escaping verified, over-5000 warning banner verified)
- **Segment Details:** PASS (Searched HIGH Top-5%, MEDIUM 5-10%, Outside Top-10%, Nonexistent ID, and Blank query. Frozen Phase 7 scope message verified for outside-Top-10%)
- **Model Performance:** PASS (All 9 sections present: summary metrics, CIs, reliability diagram, Top-K precision/recall/lift, subgroup tables, Gate B2 notice, limitations)
- **Model Interpretation:** PASS (Top-20 global importance table, SHAP beeswarm plot, seed stability audit, 5 dependence plots cycled cleanly, subgroup interpretation, causality disclaimer)

## Map Controls & Interactions

- **Controls tested:** Anchor month, Borough selection, Road class, Priority bands (HIGH, MEDIUM, WATCH, OTHER), Top-K policy (5%, 10%, 20%), Risk percentile slider, Condition survey missingness, Prior repair history, Segment ID search box.
- **Map interactions:** Pan/drag, zoom in/out, road segment click, popup render, popup close.
- **Over-5000 state:** Warning banner displayed cleanly instructing user to narrow filters.

## CSV Download Result

- **Filename:** `montreal_road_risk_candidates.csv`
- **Exported Rows:** `4,799` (100% agreement with default map selection)
- **Forbidden Target / Outcome Columns:** `0`
- **Formula Injection Protection:** Sanitized `=`, `+`, `-`, `@` with `'` prefix.

## Viewport Responsive Audits

- Desktop (`1440x1000`): PASS
- Laptop (`1366x768`): PASS
- Tablet (`1024x768`): PASS
- Mobile (`390x844`): PASS

## Console & Network Integrity

- Console Errors: `0`
- Console Warnings: `0`
- Network Failures: `0`

## Evidence Files & Screenshots (19 captured)

Manifest SHA-256: `67ae1148e0269f8611c635c886ef67cac2eecbf0e73aa9e0c18c43456444b4d1`

- `01_overview_visible.png` (SHA-256: `1c7aebe65dfa9b06...`)
- `02_csv_download_visible.png` (SHA-256: `ab99f20524515965...`)
- `02_map_default_visible.png` (SHA-256: `8299850a91a5960b...`)
- `02e_priority_bands.png` (SHA-256: `485b0bf4b534ddfa...`)
- `02f_topk.png` (SHA-256: `f15021766e6a3877...`)
- `02g_slider_50pct.png` (SHA-256: `d83f692eb5d00ba4...`)
- `02h_survey.png` (SHA-256: `77efb29d2f11d6a5...`)
- `02i_repair.png` (SHA-256: `8444083a07b266ef...`)
- `02k_over5000.png` (SHA-256: `8eac28ca84e585f8...`)
- `03_csv_download.png` (SHA-256: `130251af1355646d...`)
- `04_segment_details.png` (SHA-256: `b0c07a3699c5758d...`)
- `05_interpretation_visible.png` (SHA-256: `df4bec3efc9f19ed...`)
- `05_performance.png` (SHA-256: `fe185821e49eaabb...`)
- `05b_interp_dependence_visible.png` (SHA-256: `4d96ef6b50d79c20...`)
- `06_desktop_1440x1000_visible.png` (SHA-256: `9b6ed2eaf25b2f35...`)
- `06_laptop_1366x768_visible.png` (SHA-256: `67b11abfb3d6ead4...`)
- `06_mobile_390x844_visible.png` (SHA-256: `4de6cd29acf0e30a...`)
- `06_tablet_1024x768_visible.png` (SHA-256: `96910308bb565b6d...`)
- `07_final_state_visible.png` (SHA-256: `c00de32c6ca429a9...`)

---
*Target access: ZERO | Pushed: NOTHING | Git: clean*
