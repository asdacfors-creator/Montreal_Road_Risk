# Phase 6 Final Evaluation Report

**Project:** Montreal Road Risk Assessment  
**Evaluation Gate:** Gate B2 (Final 90-Day Evaluation)  
**Status:** COMPLETE WITH DOCUMENTED GATE B2 REPEATED-ACCESS DEVIATION (Seal Consumed & Closed)  
**Evaluation Date:** 2026-07-21T02:54:22.758860+00:00  

---

## 1. Executive Summary

The Phase 6 Gate B2 evaluation for the primary 90-day maintenance risk prediction model has been completed under the frozen pre-B2 evaluation policy, with documented Gate B2 repeated-access procedural deviation (`access_count = 2`, `result_set_count = 1`).

* **Primary Probability Domain:** Raw XGBoost Probabilities
* **Sensitivity Probability Domain:** Platt Scaled Probabilities
* **Evaluated Test Partition:** 11 B2 Anchors (`2024-07-31` to `2025-05-31`)
* **Total Test Rows:** 527,813
* **Positive Events:** 30,572
* **Target Prevalence:** 0.057922 (5.792%)
* **Access Classification:** `B_REPEATED_PROCEDURAL_ACCESS` (task-12084 failed post-open; task-12097 completed single result set)

---

## 2. Primary Raw Performance Metrics

| Metric | Point Estimate | Cluster Bootstrap 95% CI (Primary) |
|---|---|---|
| **Average Precision (AP)** | `0.505693` | `[0.497185, 0.514342]` |
| **ROC-AUC** | `0.920953` | `[0.919359, 0.922670]` |
| **Brier Score** | `0.039827` | `[0.039022, 0.040611]` |
| **Log Loss** | `0.144321` | — |
| **ECE (10 Bins)** | `0.021618` | — |

---

## 3. Operational Top-K Ranking Results (Raw Probability)

| Policy | Row Count | Precision (95% CI) | Recall (95% CI) | Lift (95% CI) |
|---|---|---|---|---|
| **Top 5%** | `26,391` | `0.539654` | `0.465851` | `9.316899` |
| **Top 10%** | `52,782` | `0.381153` (`[0.373479, 0.388789]`) | `0.658053` (`[0.651795, 0.664496]`) | `6.580444` (`[6.517861, 6.644871]`) |
| **Top 20%** | `105,563` | `0.237697` | `0.820751` | `4.103740` |

---

## 4. Frozen Primary Threshold Diagnostics (Threshold = 0.30805489)

* **TP:** 10,949
* **FP:** 6,702
* **FN:** 19,623
* **TN:** 490,539
* **Achieved Precision:** `0.620305`
* **Achieved Recall:** `0.358138`
* **Achieved F1:** `0.454099`
* **Achieved Lift:** `10.709307`

---

## 5. Platt Sensitivity Analysis

| Metric | Raw Primary | Platt Sensitivity | Delta (Platt - Raw) |
|---|---|---|---|
| **Brier Score** | `0.039827` | `0.042056` | `+0.002230` |
| **Log Loss** | `0.144321` | `0.162630` | `+0.018309` |
| **ECE (10 Bins)** | `0.021618` | `0.009944` | `-0.011673` |
| **Recall Threshold** | `0.30805489` (Raw) | `0.20194759` (Platt) | — |

---

## 6. Target Partition Integrity & Verification

* **Pre/Post Partition Fingerprints:** 100% Identical across all 11 target-source files.
* **180-Day Final Test Evaluation:** Permanently disabled.
* **Embargo Anchors:** Permanently excluded.
* **Access Classification:** **B_REPEATED_PROCEDURAL_ACCESS** (2 access attempts, 1 final result set).
* **Gate B2 Seal Status:** **CONSUMED_AND_CLOSED**.
