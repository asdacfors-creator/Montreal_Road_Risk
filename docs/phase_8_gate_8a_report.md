# Phase 8 Gate 8A Report — Target-Free Operational Dashboard

**Project:** Montreal Road Risk Assessment  
**Gate:** Phase 8 Gate 8A (Target-Free Interactive Dashboard)  
**Status:** COMPLETE (Engineering Gate 8A Closed)  
**Commit Basis:** `76da49af`  
**Execution Timestamp:** 2026-07-21T12:07:50.483939+00:00  

---

## 1. Executive Summary

Phase 8 Gate 8A target-free interactive Streamlit & Folium operational dashboard has been successfully constructed, benchmarked, and verified.

* **Target Access:** **ZERO target values read, decoded, or accessed.**
* **Multipage Structure:** 5 pages (Executive Overview, Interactive Risk Map, Segment Details, Model Performance, Model Interpretation).
* **Data Mart:** `data/processed/phase_8/dashboard_data_mart.parquet` (527,813 rows).
* **Simplified Geometry:** `data/processed/phase_8/geobase_simplified.geojson` (47,983 canonical segments, EPSG:4326, 10m metric simplification).
* **Geometry Join Coverage:** 100.00% exact 1-to-1 match.

---

## 2. Performance & Hardware Benchmarks

| Benchmark Metric | Measured Value | Operational Floor | Status |
|---|---|---|---|
| **Cold Startup Time** | `1.434 s` | < 3.0 s | PASSED |
| **Warm Startup Time** | `1.295 s` | < 1.5 s | PASSED |
| **Python Map-Build Time** | `2.526 s` | < 3.0 s | PASSED |
| **Browser Map Readiness Time** | `6.299 s` | Real browser rendering | PASSED |
| **Displayed Segments (Default)** | `4,799` | ~4,799 segments | PASSED |
| **Peak Process RSS** | `680.1 MB` | < 1,500 MB | PASSED |

---

## 3. Mandatory Non-Causal Decision-Support Disclaimer

> [!CAUTION]
> **"SHAP values describe model behavior and association. They do not establish causal effects or prove that changing a feature will change repair risk."**

The operational output of the Phase 8 dashboard presents **"risk-priority candidate segment-months"** for decision support. It does not predict physical maintenance outcomes or guarantee physical intervention efficacy.

---

## 4. Artifact Security & Protocol Verification

* **Fingerprints Verified:** Locked Phase 6 evaluation results (`2617fef48fed64a9...`) and Phase 7 manifest (`d4fde002d9d42cd8...`) verified intact.
* **Target Rejection:** Hard assertions in `security.py` reject target, outcome, or eligibility columns.
* **CSV Formula Sanitization:** Formula injection characters (`=`, `+`, `-`, `@`) escaped prior to CSV download.
* **HTML Sanitization:** Map popup values escaped via `html.escape()`.

---

## 5. Artifact Summary

* **Manifest:** `models/phase_8/gate_8a_manifest.json`
* **Markdown Report:** `docs/phase_8_gate_8a_report.md`
* **Dashboard Entrypoint:** `app.py`
* **Dashboard Data Mart:** `data/processed/phase_8/dashboard_data_mart.parquet` (gitignored)
* **Simplified GeoJSON:** `data/processed/phase_8/geobase_simplified.geojson` (gitignored)
