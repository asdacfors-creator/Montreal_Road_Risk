# Phase 6 Gate B1 Report

**Project:** Montreal Road Risk — 90-day Repair Risk Classifier  
**Gate:** B1 (Probability Calibration & Threshold Freeze)  
**Status:** CLEAN RERUN COMPLETE (Scientific Review Pending)  
**Created:** 2026-07-21T00:00:00Z  
**Last Updated:** 2026-07-21T04:15:00Z  

---

## 1. Protocol Deviation & Incident Notice

> [!WARNING]
> **Procedural Breach Notice (Gate B1 Deviation):**
> During initial B1 runs (commit e08d7ba and 876d6da), contaminated features (`data/processed/phase_5/test.parquet`) and target files (`data/processed/phase_4`) were referenced. The unrestricted reading of `test.parquet` decoded the target column `target_repair_180d` into memory for all test rows.
> 
> **Impact:** 
> - The 180-day final-test seal is **procedurally compromised**.
> - B1 prior_repair_months_12m values were contaminated in `28,607` of `143,949` rows (19.873%).
> - No embargo or B2 target_repair_90d values were decoded or evaluated.
> - Invalid B1 artifacts have been **quarantined** in `models/phase_6/quarantine/gate_b1_contaminated_01/`.
> - Gate B2 remains **locked** pending supervisor review.

---

## 2. Gate B1 Scope

Gate B1 is authorized to:
- Load target values for the three approved B1 calibration anchors (`2024-01-31`, `2024-02-29`, `2024-03-31`)
- Fit the Platt probability calibrator on clean, remediated features
- Calculate calibration-fit diagnostics on B1 only
- Freeze approved rank-based and diagnostic threshold policies

Gate B1 does **not** authorize:
- Access to embargo targets (`2024-04-30` → `2024-06-30`)
- Access to B2 final-test targets (`2024-07-31` → `2025-05-31`)
- Base-model retraining or hyperparameter tuning
- Final-test evaluation

---

## 3. Clean Input Paths & File Integrity

All execution paths were strictly frozen to point to remediated inputs:

| Item | Path / Value | SHA-256 Fingerprint |
|---|---|---|
| **Clean Feature Source** | `data/processed/phase_5_remediated_01/sealed_features_90d.parquet` | `569e549c9e636bd253bf849c9334a96de08e3152d4f4d6b47c51c84f7e100021` |
| **Clean B1 Targets** | `data/processed/phase_4_remediated_01/` | Enforced strict column projection list |
| **Remediated Model** | `models/phase_5/full_training_remediated_01/model.joblib` | `f034d42f9994cd09059e691220ce75209d8da26040be70e988c418ec9ebb413f` |
| **Remediated Preprocessor** | `models/phase_5/full_training_remediated_01/preprocessor.joblib` | `f2dac65ab2a09dd4e978a519a611a14116b25f598277ed8c8ccc2eabc02a3fe7` |

---

## 4. Logical Split & Minimal Data Access

* **B1 Row Count:** 143,949 rows (exactly 47,983 rows per anchor)
* **B1 Positive Count:** 12,081 events (prevalence: 8.3926%)
* **Projected Columns Decoded:** `segment_month_id`, `canonical_segment_id`, `as_of_date`, `target_repair_90d`
* **Negative Controls:**
  - Embargo targets (2024-04-30 → 2024-06-30): **NOT ACCESSED**
  - B2 targets (2024-07-31 → 2025-05-31): **NOT ACCESSED / LOCKED**

---

## 5. Calibration Fit Results

* **Method:** Platt Scaling (Sigmoid Logistic Regression)
* **Fitted Parameters:**
  - Intercept (a): `-3.505020`
  - Slope (b): `6.917125`
* **Calibrator SHA-256:** `0206507256e13ad11a1c73130f5fb9d194f4a685f421d6fc8840c0aaccb8a782`
* **Raw B1 Prediction SHA-256:** `5f616f7bfea2dada377094a0af547ef62824160aace75d132e7a1c6b0c1a65f9`
* **Calibrated B1 Prediction SHA-256:** `33788c952d629ae51faf8ecc2a0528200ae05b757b4553e96805748f130e89f7`

---

## 6. Apparent Calibration Diagnostics

These metrics are apparent calibration-fit diagnostics on B1 calibration data, **not** independent performance.

### Raw vs Calibrated Metrics Table

| Metric | Raw Probabilities | Calibrated Probabilities | Delta (Cal - Raw) |
|---|---|---|---|
| **AP** | `0.504947` | `0.504947` | `0.000000` (Invariant) |
| **ROC-AUC** | `0.887521` | `0.887521` | `0.000000` (Invariant) |
| **Brier Score** | `0.055206` | `0.056979` | `+0.001773` (Degradation) |
| **Log Loss** | `0.194230` | `0.205119` | `+0.010889` (Degradation) |
| **ECE (10 Bins)** | `0.011290` | `0.021507` | `+0.010217` (Degradation) |
| **Calibration Slope** | `0.887521` (approx) | `1.000000` (approx) | Improved to ~1.00 |
| **Calibration Intercept** | Negative | ~0.000000 | Improved to ~0.00 |

> [!WARNING]
> **Calibration Status:** Sigmoid scaling degraded all three proper calibration metrics (Brier score, Log Loss, and ECE). Therefore, it is recommended to use raw probabilities as the primary B2 output, with Platt scaling as a sensitivity check. The final decision remains with the supervisor.

### Reliability Table (Calibrated)

| Bin Low | Bin High | Total N | Positives | Mean Predicted | Mean Actual | Weight |
|---|---|---|---|---|---|---|
| 0.0 | 0.1 | 123,242 | 3,752 | 0.037620 | 0.030444 | 0.856150 |
| 0.1 | 0.2 | 8,631 | 2,252 | 0.142506 | 0.260920 | 0.059959 |
| 0.2 | 0.3 | 3,916 | 1,356 | 0.243090 | 0.346272 | 0.027204 |
| 0.3 | 0.4 | 1,823 | 737 | 0.344566 | 0.404279 | 0.012664 |
| 0.4 | 0.5 | 1,022 | 469 | 0.445840 | 0.458904 | 0.007100 |
| 0.5 | 0.6 | 679 | 357 | 0.546992 | 0.525773 | 0.004717 |
| 0.6 | 0.7 | 704 | 374 | 0.652245 | 0.531250 | 0.004891 |
| 0.7 | 0.8 | 1,086 | 684 | 0.756025 | 0.629834 | 0.007544 |

## 7. Frozen Threshold Policies & Pre-B2 Policy Freeze

> [!IMPORTANT]
> **Pre-B2 Policy Freeze (Raw Probabilities Primary):**
> Before any Gate B2 target access, raw XGBoost probabilities are frozen as the **PRIMARY** Phase 6 output based on better Brier, Log Loss, and ECE performance. Platt probabilities are retained for **SENSITIVITY** analysis only.

### Primary vs. Sensitivity Threshold Summary

* **Primary Raw Recall Threshold ($\text{Recall} \ge 0.50$):** `0.30805489`
* **Sensitivity Platt Recall Threshold ($\text{Recall} \ge 0.50$):** `0.20194759`
* **Selected Row Count:** `11,966`
* **Achieved Recall:** `0.500041`
* **Precision:** `0.504847`
* **F1 Score:** `0.502433`
* **Lift:** `6.015415`
* **Recall Overshoot:** `0.000041`
* **Boundary Tie Count:** `1`

### Operational Top-K Thresholds (Rank-Based on Raw Ordering)

* **Top 5%:** 7,198 rows | Precision: `0.600861` | Recall: `0.358000` | Lift: `7.159456`
* **Top 10%:** 14,395 rows | Precision: `0.473567` | Recall: `0.564274` | Lift: `5.642706`
* **Top 20%:** 28,790 rows | Precision: `0.319729` | Recall: `0.761940` | Lift: `3.809675`

---

## 8. Pre-B2 Evaluation Manifest

* **Manifest File:** `models/phase_6/evaluation_manifest.json`
* **Manifest SHA-256:** `8116fb61965a150fa289eab838d753cb639e45943eb4edc9452dd62f18a05993`
* **B2 Anchors (11):** `2024-07-31` to `2025-05-31` (Expected rows: `527,813`)
* **180-day Final Test Evaluation:** Permanently disabled due to procedural breach.
* **Gate B2 Status:** Locked pending supervisor authorization.

---

## 9. Tests and QA Status

* **Pytest Summary:** `401 passed, 12 warnings in 83.37s` (including new path/contamination regression tests)
* **Ruff Summary:** `All checks passed!`
* **Protected Inputs Verification:** **UNCHANGED** (Model, preprocessor, features verified unchanged).
* **Gate B2 Status:** **LOCKED** (Supervisor decision required).
