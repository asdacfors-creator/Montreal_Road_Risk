# Montreal Road Risk — Leakage Prevention Plan

| Field | Value |
| :--- | :--- |
| **Document purpose** | Data Leakage Prevention and Controls |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 3C — Temporal Normalization, Coverage Validation and Final Phase 3 Closure |
| **Status** | Complete |
| **Last updated** | 2026-07-17 |
| **Source of truth** | Machine Learning Best Practices |
| **Next review** | Phase 6 Train-Test Splitting |

---

## Executive Summary

This document defines data leakage pathways (both spatial and temporal) and outlines the programmatic controls, automated validation tests, and manual checklists designed to prevent leakage in the machine learning pipeline.

---

## Leakage Definition

Data leakage occurs when information from the future (target period) or from the validation/test partitions is inadvertently used during model training. This leads to overoptimistic performance metrics during validation that cannot be replicated in a real-world deployment.

---

## Temporal Leakage Table

| Leakage Pathway | Mechanism | Programmatic Control |
| :--- | :--- | :--- |
| **Future Repair Events** | Using repairs that occur after $t$ as features to predict the target at $t$. | Filter repair events: only sum or aggregate records with timestamps $< t$. |
| **Future Weather Observations** | Aggregating freeze-thaw counts or rainfall from periods after $t$. | Construct weather features strictly using historical weather dates preceding $t$. |
| **Future Resurfacing Records** | Using a last-resurfaced year that is greater than or equal to the year of $t$. | Calculate road age using only resurfacing years strictly less than the year of $t$. |
| **Future Pavement Surveys** | Using condition indices (PCI/IRI) from campaigns conducted after $t$. | Join condition campaigns dynamically based on campaign date $< t$. |
| **Full-History Aggregates** | Calculating global features (e.g. total repairs 2018-2026) across the entire dataset. | Compute rolling features (e.g. repairs in last 12 months) relative to $t$. |
| **Hyperparameter Tuning** | Tuning model parameters (e.g. max depth) using the final test period labels. | Optimize parameters strictly on the validation partition. |

---

## Pavement-Condition Specific Rules

> [!IMPORTANT]
> **Temporal Leakage Rule**: For any future road-segment-month observation, pavement-condition values may only come from a survey whose DateReleve is on or before the observation cutoff date. A future survey must never be backfilled into earlier observations. The 2022 local campaign and 2024 arterial campaign cover different network scopes and must not be treated as citywide consecutive snapshots.

Later feature engineering may require the construction of the following features (which are deferred and not created now):
- **Most recent eligible prior survey**: Retrieving the latest pavement survey data strictly before the observation month.
- **Survey age/staleness**: Calculating the temporal difference between the survey DateReleve and the observation month.
- **Network-scope indicator**: A categorical or binary indicator specifying the survey scope (local vs. arterial).
- **Missing-condition indicator**: Flagging segments that have never been surveyed in any campaign.
- **Unmatched-ID indicator**: Flagging segments whose historical ID_TRC does not match the current Géobase.
- **Sentinel/missing IRI policy**: Downstream policy for handling CP1252 GeoJSON `0` + `-` sentinels or other missing values.

---

## Spatial Leakage Table

| Leakage Pathway | Mechanism | Programmatic Control |
| :--- | :--- | :--- |
| **Spatial Duplicates across splits** | Training and testing on the same `segment_id` in overlapping temporal partitions without proper separation. | Implement strict chronological splitting (e.g. Train: 2018–2023, Test: 2025). This separates the evaluation period. |
| **Coordinate Snipping Overlap** | Snapping a point event to multiple segments due to large buffers, duplicate counting events. | Filter and assign each event to a single unique `segment_id`. |

---

## Preprocessing Leakage Controls

* **Fitted Scalers/Encoders**: All scaling parameters (mean, standard deviation for standard scaling) and encoding maps must be fitted *only* on the training set partition. The fitted transformations are then applied to the validation and test partitions.
* **Imputation Statistics**: Missing traffic volume, asset age, or weather indices must be imputed using median/mode statistics computed strictly from the training partition.

---

## Calibration and Model-Selection Controls

* **Probability Calibration**: Platt Scaling or Isotonic Regression must be trained using validation set predictions. The calibration model must never be fitted using the final test partition labels.
* **Feature Selection**: Feature importance evaluation and selection must be conducted using only the training and validation splits.

---

## Planned Automated Verification Tests

1. **Feature Date Assertions**: Verify that the maximum timestamp used for any feature is strictly less than the observation date $t$.
2. **Target Window Assertions**: Verify that target events occur strictly in the window $(t, t + 90\text{ days}]$.
3. **Partition Boundary Assertions**: Assert that the maximum observation date in the training partition is strictly less than the minimum observation date in the validation partition.

---

## Manual Review Checklist

* [ ] Verify that `sklearn.pipeline.Pipeline` is used to chain imputers, scalers, and estimators.
* [ ] Verify that `fit_transform` is never called on validation or test partitions.
* [ ] Confirm that no global dataset statistics (e.g. mean traffic volume) are computed before data splitting.
* [ ] Review feature importance matrices to flag features that show suspicious high importance (e.g., target-correlated proxies).

---

## Weather Leakage Controls
* **Temporal Cutoff constraint**: Weather observations used for a segment-month feature must be available on or before that observation cutoff.
* **Target Window Isolation**: No weather occurring inside the future 90-day or 180-day target window may leak into the predictor features for a given segment-month observation.
* **Allowed Aggregation Windows**: Candidate aggregation windows (previous 30 days, previous 90 days, previous 365 days, and winter-season-to-date) are allowed as predictors, provided they only use historical daily records.

---

## Limitations and Pending Verification
* Final temporal split dates are pending real-data inspection in Phase 3.
* Missingness and imputation requirements for pothole repairs, road assets, pavement condition, and weather have been fully audited in Phase 2.

---

## Phase Gate

To transition to Phase 1, leakage controls must be approved.
* [ ] Leakage pathways mapped.
* [ ] Pipeline controls and assertions defined.
* [ ] No implementation started.
* [ ] Supervisor approval received.
