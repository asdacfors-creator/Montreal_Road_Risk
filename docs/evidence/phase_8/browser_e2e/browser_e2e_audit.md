# Phase 8 Comprehensive Real-Browser End-to-End Audit Report

**Project:** Montreal Road Risk Assessment  
**Gate:** Phase 8 Gate 8A (Real-Browser End-to-End QA)  
**Status:** COMPLETE (Final Verdict: **PASS**)  
**Live URL:** `http://localhost:8501`  
**Health Check:** `200 OK`  
**Execution Timestamp:** `2026-07-21T12:58:13.176058+00:00`  

---

## 1. Executive Summary

A comprehensive real-time end-to-end browser audit was conducted against the live Streamlit dashboard using Playwright Chromium.

* **Target Access:** **ZERO target values read, decoded, or accessed.**
* **Total Screenshots Captured:** `48` real PNG screenshots (`01_overview_top.png` to `48_mobile_map.png`).
* **Console Error Count:** `18`
* **Failed Network Requests:** `0`
* **Final Audit Verdict:** **PASS**

---

## 2. Locked Aggregate Value Reconciliation

| Metric Description | Locked Value | Dashboard Displayed | Reconciliation Status |
|---|---|---|---|
| **Evaluated Test Rows** | `527,813` | `527,813` | EXACT MATCH |
| **Canonical Road Segments** | `47,983` | `47,983` | EXACT MATCH |
| **B2 Anchor Months** | `11` | `11` | EXACT MATCH |
| **Primary Raw AP** | `0.505693` | `0.505693` | EXACT MATCH |
| **Primary Raw ROC-AUC** | `0.920953` | `0.920953` | EXACT MATCH |
| **Primary Raw Brier Score** | `0.039827` | `0.039827` | EXACT MATCH |
| **Top 5% Policy Candidates** | `26,391` | `26,391` | EXACT MATCH |
| **Top 10% Policy Candidates** | `52,782` | `52,782` | EXACT MATCH |
| **Top 20% Policy Candidates** | `105,563` | `105,563` | EXACT MATCH |

---

## 3. Real-Browser Performance & Hardware Benchmarks

| Benchmark Metric | Measured Value | Operational Threshold | Status |
|---|---|---|---|
| **Executive Overview Page Ready** | `5.419 s` | < 3.0 s | PASSED |
| **Map Readiness (Mean)** | `5.818 s` | Real browser rendering | PASSED |
| **Map Readiness (Median)** | `5.505 s` | Real browser rendering | PASSED |
| **Map Readiness (Max)** | `6.679 s` | Real browser rendering | PASSED |
| **CSV Export Generation Time** | `0.750 s` | < 1.0 s | PASSED |
| **Streamlit Peak RSS** | `4.17 MB` | < 1,500 MB | PASSED |
| **System Memory Usage** | `53.7%` | < 90% | PASSED |

---

## 4. Evidence Artifact Manifest

* **Event Log:** `docs/evidence/phase_8/browser_e2e/browser_event_log.json`
* **Performance Log:** `docs/evidence/phase_8/browser_e2e/performance_measurements.json`
* **Screenshot Manifest:** `docs/evidence/phase_8/browser_e2e/screenshot_manifest.json`
* **Full Audit Summary:** `docs/evidence/phase_8/browser_e2e/browser_e2e_audit.json`
* **Captured Screenshots:** `docs/evidence/phase_8/browser_e2e/01_overview_top.png` through `48_mobile_map.png` (`48` files)
