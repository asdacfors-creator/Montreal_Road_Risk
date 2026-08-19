# Montreal Road Risk — Project Decision Log

| Field | Value |
| :--- | :--- |
| **Document purpose** | Key Architectural and Scope Decisions |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 6 — Evaluation Framework & Operationalization (In Progress) |
| **Status** | Complete |
| **Last updated** | 2026-07-21 |
| **Source of truth** | Phase 6 Pre-B2 Policy Freeze |
| **Next review** | Gate B2 Review |

---

## Executive Summary

This log records the core architectural decisions, working hypotheses, and pending decisions for the Montreal Road Risk project. It separates approved choices from items requiring validation against real data.

---

## Decision Categories

* **Approved Phase 0/3A/3B/3C/5/6 decision**: Decisions finalized and locked.
* **Provisional hypothesis**: Working assumptions to be tested during pipeline building.
* **Pending real-data verification**: Choices that require raw data inspection or modeling audits.

---

## Project Decision Log Table

| ID | Date | Decision | Type | Evidence | Status | Revisit Phase |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **D0.1** | 2026-07-15 | Frame primary target as a binary 90-day intervention window | Approved Phase 0 decision | Proposal section 6 | Complete | Phase 4 |
| **D0.2** | 2026-07-15 | Frame unit of observation as a segment-month panel | Approved Phase 0 decision | Proposal section 6 | Complete | Phase 4 |
| **D0.3** | 2026-07-15 | MVP models: Baseline, LogReg, RF, XGBoost | Approved Phase 0 decision | Proposal section 6 | Complete | Phase 5 |
| **D0.4** | 2026-07-15 | Defer Random Survival Forest as an optional stretch goal | Approved Phase 0 decision | Proposal section 6 | Complete | Phase 8 |
| **D0.5** | 2026-07-15 | Use `segment_id` as conceptual road network identifier | Provisional hypothesis | Metadata search | Complete | Phase 3A |
| **D0.6** | 2026-07-15 | Snapping tolerances (10m, 25m, 50m) are proposed sensitivity values | Approved Phase 3B decision | Snapping sensitivity analysis | Complete | Phase 3B |
| **D0.7** | 2026-07-15 | Pothole repairs are administrative proxy (not physical state) | Approved Phase 0 decision | Literature review | Complete | Phase 10 |
| **D0.8** | 2026-07-15 | Choice of final repair-event dataset | Approved Phase 3A decision | Data inventory | Complete | Phase 3A |
| **D0.9** | 2026-07-15 | Definition of eligible road-network population | Pending real-data verification | Data inventory | Pending | Phase 2 |
| **D0.10** | 2026-07-15 | Weather station and aggregation method (nearest, airport, IDW) | Approved Phase 3C decision | ECCC daily records | Complete | Phase 3C |
| **D0.11** | 2026-07-15 | Inclusion or exclusion of asset data | Approved Phase 3A decision | Pavement age fields | Complete | Phase 3A |
| **D0.12** | 2026-07-15 | Inclusion or exclusion of PCI/IRI data | Approved Phase 3A decision | Auscultation campaigns | Complete | Phase 3A |
| **D0.13** | 2026-07-15 | Traffic proxy method (functional class average fallback) | Pending real-data verification | Volume sparsity | Pending | Phase 5 |
| **D0.14** | 2026-07-15 | Minimum historical period for rolling features | Pending real-data verification | Historical coverage | Pending | Phase 4 |
| **D0.15** | 2026-07-15 | Final temporal split dates | Pending real-data verification | Chronological range | Pending | Phase 6 |
| **D0.16** | 2026-07-15 | Criticality indicators and policy weights | Pending real-data verification | Municipal priorities | Pending | Phase 7 |
| **D3.1** | 2026-07-16 | Use `EPSG:32188` (NAD83 / MTM zone 8) as working CRS | Approved Phase 3A decision | Native boundaries crs | Complete | Phase 3A |
| **D3.2** | 2026-07-17 | Use `0.10` minimum length overlap for road assets | Approved Phase 3B decision | Overlap sensitivity analysis | Complete | Phase 3B |
| **D3.3** | 2026-07-17 | Explicitly assume America/Toronto local timezone and classify DST anomalies | Approved Phase 3C decision | No timezone metadata in source | Complete | Phase 3C |
| **D3.4** | 2026-07-17 | Same-day weather fallback restricted to mean/min/max temp and total precip allowlist | Approved Phase 3C decision | Microclimate sensitivity check | Complete | Phase 3C |
| **D3.5** | 2026-07-17 | Pavement condition surveys available starting exactly on their survey date | Approved Phase 3C decision | Leakage prevention check | Complete | Phase 3C |
| **D5.1** | 2026-07-19 | Select full-data XGBoost (3,406,793 rows, AP=0.806207) as primary 90-day Phase 5 validation candidate over the 1M-row subsample (AP=0.795903) | Approved Phase 5 decision | AP delta +0.010304, ROC delta +0.001949; primary metric is AP | Complete | Phase 6 |
| **D5.2** | 2026-07-19 | Accept marginally worse Brier score (+0.000481) in full-data model; defer calibration to Phase 6 | Approved Phase 5 decision | Calibration is Phase 6 task; difference is 0.48 ms and may be recovered by Platt scaling | Complete | Phase 6 |
| **D5.3** | 2026-07-19 | Use external-memory streaming (xgb.ExtMemQuantileDMatrix) for full-data training on 16 GB machine | Approved Phase 5 decision | Full-data load (7.25 GB RSS) caused OOM; streaming achieved 2.16 GB peak RSS | Complete | — |
| **D6.1** | 2026-07-20 | Remediate `prior_repair_months_12m` upper-bound bug, rebuild Phase 4 panel (102 anchors) & Phase 5 splits into versioned directories, and retrain Phase 5 model | Emergency containment & remediation decision | Discovered future-data leakage in feature construction (train max=40, val max=16, val correlation 0.477); nonsealed 85 anchors & sealed feature-only 17 anchors rebuilt seal-safe | Complete | Phase 6 |
| **D6.2** | 2026-07-21 | [SUPERSEDED] Fit Platt/sigmoid probability calibrator on logical B1 partition and freeze Top-K (5%, 10%, 20%) and recall-based (Recall-at-0.5) threshold policies | Approved Phase 6 Gate B1 decision | `calibration_manifest.json` and `threshold_manifest.json` (Commit 876d6da) | Superseded | Gate B2 |
| **D6.3** | 2026-07-21 | Execute clean Gate B1 rerun using remediated features and target panels with explicit column projections, quarantining contaminated B1 artifacts. | Emergency Gate B1 Rerun decision | Procedural breach and feature contamination in initial B1 run addressed; clean calibrator fit and recall threshold of 0.20194759 frozen. | Complete | Gate B2 |
| **D6.4** | 2026-07-21 | Freeze Raw XGBoost probabilities as PRIMARY Phase 6 output and Platt probabilities as SENSITIVITY only. Freeze primary raw recall threshold (0.30805489) and sensitivity Platt threshold (0.20194759). | Approved Phase 6 Pre-B2 decision | B1 apparent fit showed better Brier (0.055206 vs 0.056979), Log Loss (0.194230 vs 0.205119), and ECE (0.011290 vs 0.021507) for raw probabilities. AP and ROC-AUC invariant under monotonic Platt scaling. | Complete | Gate B2 |
| **D6.5** | 2026-07-21 | Perform Gate B2 evaluation on 527,813 test rows across 11 B2 anchors. Primary Raw AP=0.505693 (95% CI: [0.497185, 0.514342]), ROC-AUC=0.920953 (95% CI: [0.919359, 0.922670]). Gate B2 seal consumed and closed. | Approved Phase 6 Gate B2 decision | 180-day evaluation disabled; embargo anchors excluded; 500-repetition segment-cluster & row-level bootstrap CIs computed; Phase 6 COMPLETE. | Complete | Phase 7 |
| **D6.6** | 2026-07-21 | Document Gate B2 repeated-access procedural deviation (access_count=2, result_set_count=1, classification B_REPEATED_PROCEDURAL_ACCESS) and harden seal guard against repeat target decoding. | Emergency Gate B2 Deviation Correction | Invocation task-12084 failed post-open on line 238; task-12097 completed single final result set. Authoritative status: COMPLETE WITH DOCUMENTED GATE B2 REPEATED-ACCESS DEVIATION. | Complete | Phase 7 |
| **D7.1** | 2026-07-21 | Authorize target-free Phase 7 Gate 7A model interpretation using exact XGBoost tree contributions (`pred_contribs=True`) on 527,813 B2 rows (11 anchors), 3 stability samples (seeds 42, 137, 2026; Spearman correlations 0.999946-0.999991), Top-10% explanation records (52,782 candidates), target-free subgroup summaries (7 dimensions), and mandatory causality disclaimers. Zero target access. | Approved Phase 7 Gate 7A decision | `gate_7a_manifest.json` and `phase_7_gate_7a_report.md` | Complete | Gate 7B |
| **D8.1** | 2026-07-21 | Authorize Phase 8 Gate 8A target-free interactive Streamlit & Folium operational dashboard (5 pages, 527,813 B2 rows, 47,983 canonical segments, 10m simplified geometry, 100% 1-to-1 join coverage, zero target access, local execution). | Approved Phase 8 Gate 8A decision | `gate_8a_manifest.json` and `phase_8_gate_8a_report.md` | Complete | Phase 9 |

---

## Limitations and Pending Verification

* The target prevalence is **unknown** until the modeling panel is built.
* Real column schemas and spatial matching tolerances require actual data inspection in Phase 2 and Phase 3.
* The full-data XGBoost model has a marginally worse Brier score than the 1M subsample candidate (see L5.4 in limitations log). Probability calibration (Phase 6) may partially address this.

---

## Phase Gate

To transition to Phase 6, the decision log must be reviewed and approved.
* [x] Decision types separated.
* [x] All pending Phase 5 decisions resolved.
* [x] Phase 5 primary 90-day candidate selected (full-data XGBoost).
* [x] Sealed test partition A non-analytic target-column integrity comparison occurred during remediation. Target values were not printed, summarized, scored, passed to a model or used for any modeling decision..
* [x] Pre-B2 Evaluation Policy Frozen (Raw probabilities Primary, Platt Sensitivity).
* [x] Supervisor approval received (2026-07-19).
