# Phase 6 Gate B2 Repeated Access Protocol Deviation Report

**Project:** Montreal Road Risk Assessment  
**Evaluation Gate:** Gate B2 (One-Time Final 90-Day Evaluation)  
**Classification:** `B_REPEATED_PROCEDURAL_ACCESS`  
**Status:** Documented & Preserved  
**Date:** 2026-07-21  

---

## 1. Executive Summary

A forensic audit of the Phase 6 Gate B2 evaluation revealed a procedural violation of the one-time access protocol. The 527,813 authorized 90-day test target rows across 11 B2 anchors were decoded **twice** due to a script execution failure during the initial attempt.

* **First Access Attempt (`task-12084`):** Target columns decoded at `2026-07-21T00:24:09Z`. Invocation failed at `00:24:10Z` with a `TypeError: expected_calibration_error() got an unexpected keyword argument 'n_bins'` before any metrics, bootstrap CIs, subgroup evaluations, or final result JSON files were generated.
* **Second Access Attempt (`task-12097`):** Target columns decoded at `2026-07-21T00:24:59Z`. Invocation completed successfully at `02:54:22Z`, producing the single final evaluation result set.
* **Impact & Usability:** Exactly **one** final result set was produced. No embargo targets or 180-day targets were accessed. Target source files remained unmodified. The final numerical evaluation results remain **scientifically valid**, subject to this documented procedural deviation.

---

## 2. Invocation Breakdown

| Attribute | First Access (`task-12084`) | Second Access (`task-12097`) |
|---|---|---|
| **Task ID** | `c5ab3c6e-421c-46dd-a4ea-1210a26a67ee/task-12084` | `c5ab3c6e-421c-46dd-a4ea-1210a26a67ee/task-12097` |
| **Start Time (UTC)** | `2026-07-21T00:23:57Z` | `2026-07-21T00:24:48Z` |
| **Target Load Time (UTC)** | `2026-07-21T00:24:09Z` | `2026-07-21T00:24:59Z` |
| **Completion/Failure Time (UTC)** | `2026-07-21T00:24:10Z` | `2026-07-21T02:54:22Z` |
| **Exit Code** | `1` | `0` |
| **Outcome** | `FAILED_AFTER_OPEN` | `COMPLETE` |
| **Failure Cause** | `TypeError: expected_calibration_error() got an unexpected keyword argument 'n_bins'` | None (Success) |
| **Metrics / Results Produced** | **No** | **Yes** (1 final result set) |
| **Rows Decoded** | 527,813 | 527,813 |

---

## 3. Compliance Declarations

1. **Classification:** `B_REPEATED_PROCEDURAL_ACCESS` — More than one invocation decoded target data, but only one evaluation result set was produced.
2. **Target File Integrity:** No target-bearing Parquet files were modified during either invocation (all pre/post SHA-256 partition fingerprints match 100%).
3. **Embargo & 180-Day Access:** Zero access to embargo anchors (`2024-04-30`, `2024-05-31`, `2024-06-30`) or 180-day target columns (`target_repair_180d`).
4. **Script Provenance:** Script edit between execution and commit was classified as `formatting/lint only` (Ruff `F401`, `W291`, `B007`).
5. **No Audit Target Access:** No target files were reopened during the post-B2 forensic audit or this correction step.

---

## 4. Associated Commits & Files

* **Authorization Commit:** `cc803a74659b72ec72828b809a47ef59be4aee0c`
* **Final Results Commit:** `c26421684c3ea83c27e02e07ddcd3086eb022fbe`
* **Deviation Artifact:** `models/phase_6/gate_b2_repeated_access_deviation.json`
* **Access Record:** `models/phase_6/gate_b2_access_record.json`
