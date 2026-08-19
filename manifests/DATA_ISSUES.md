# DATA ISSUES — INSE 6311 Report Visual Package

## Predictive Road Pavement Deterioration Risk Assessment and Maintenance Prioritization for Montréal

**Document Type:** Data lineage and known issues register  
**Last Updated:** 2026-07-25 (UTC)  
**Status:** All issues documented; no suppression of findings

---

## DI-001 — Nov–Dec 2022 Development Gap and Nov–Dec 2023 Excluded Transition

| Field | Value |
|---|---|
| **Severity** | LOW — Documented partition boundaries |
| **Status** | DOCUMENTED |
| **Affects** | Figure 2 (Chronological Split) |

### Nov–Dec 2022 Development Gap
- **Scale:** 2 monthly anchors (95,966 rows).
- **Panel Status:** Retained in the complete 102-anchor panel.
- **Partition Assignment:** Nov–Dec 2022 are retained in the complete 102-anchor panel but are unassigned to governed model fitting or evaluation. No additional leakage-control or buffer rationale is asserted beyond the documented partition schedule.

### Nov–Dec 2023 Excluded Transition
- **Scale:** 2 monthly anchors (95,966 rows).
- **Panel Status:** Retained in the complete 102-anchor panel.
- **Exclusion Rationale:** Nov–Dec 2023 are excluded because their 90-day outcome windows extend into Gate B1 calibration.

**Resolution:** Documented in partition schedules and Figure 2 annotations.

---

## DI-002 — Subgroup Strata with Insufficient Sample

| Field | Value |
|---|---|
| **Severity** | LOW — Expected behaviour |
| **Status** | DOCUMENTED |
| **Affects** | Figure 7 (Subgroup Equity Audit) |

**Description:** Several subgroup strata meet the stratification key (functional road class, PCI availability, etc.) but have either fewer than 500 rows or fewer than 50 positive labels in the Gate B2 evaluation set. These groups carry status `INSUFFICIENT_SAMPLE` in `models/phase_6/test_subgroup_results.json` and are excluded from plots.

**Affected strata (partial list):**
- PCI Missing (`condition_missing_flag=1`): Only ~3,200 rows total, some anchors have zero positives
- Functional Road Class 9 (Expressway ramps): n < 200 across test period
- No Prior Repair flag = 1: Positive prevalence ≈ 1.2% (< 50 positives in some sub-periods)

**Resolution:** Exclusion criteria are documented in the figure caption and manifest. Results for excluded groups are not fabricated or imputed.

---

## DI-003 — B2 Target Label Source Path

| Field | Value |
|---|---|
| **Severity** | MEDIUM — Script bug fixed |
| **Status** | RESOLVED (2026-07-25) |
| **Affects** | Figure 3 (Performance Curves) |

**Description:** During initial figure generation, `generate_figures.py` attempted to load `target_repair_90d` from `data/processed/phase_4_remediated_01` (the remediated dataset). This dataset does not contain target columns (only input features after the Phase 8 data quality remediation). The correct source for B2 labels is `data/processed/phase_4` (original panel, not remediated), which preserves target columns by design.

**Root Cause:** Phase 8 remediation strips target columns from the remediated dataset to prevent target-adjacent information from influencing the remediated feature schema.

**Resolution:** `generate_figures.py` corrected to read from `data/processed/phase_4/panel_year={Y}/panel_month={M}/segment_month.parquet`. The loaded label set matches the Gate B2 access record:
- Expected rows: 527,813 (11 anchors × 47,983 segments)
- Observed positives: 30,572 (5.79% prevalence)
- AP verified: 0.505693 (matches frozen JSON to 6 decimal places)
- AUC verified: 0.920953 (matches frozen JSON to 6 decimal places)

---

## DI-004 — Weibull AFT Fitted on Sample (Not Full Cohort)

| Field | Value |
|---|---|
| **Severity** | LOW — By design |
| **Status** | DOCUMENTED |
| **Affects** | Figure 12 (Weibull AFT) |

**Description:** The Weibull AFT model in Figure 12 is fitted on a 50,000-row stratified random sample of the 250,495-row survival cohort. This was necessary to achieve tractable MLE optimization in the figure generation script. The Phase 9 production Weibull AFT model was fitted on the full cohort.

**Resolution:** The caption and figure annotation explicitly state "50,000-row stratified sample". The covariate direction and magnitude are consistent with the Phase 9 production model. No frozen metrics are cited from this sample-fitted model.

---

## DI-005 — Dashboard Screenshots: Anchor Month Dependency

| Field | Value |
|---|---|
| **Severity** | LOW — Cosmetic only |
| **Status** | DOCUMENTED |
| **Affects** | Figure 9 (Risk Map), Figure 10 (Segment Details) |

**Description:** Dashboard screenshots (Figures 9 and 10) reflect the anchor month active in the dashboard at the time of capture. The risk-map filter was set to HIGH priority band. Segment counts shown in the sidebar reflect the filtered state, not the full 527,813-row test set.

**Resolution:** Captions clearly state "HIGH priority band filter applied" for Figure 9 and "selected high-priority segment" for Figure 10. No frozen metric values are derived from these screenshots.

---

## DI-006 — Kaplan-Meier API Key Names (Script Bug Fixed)

| Field | Value |
|---|---|
| **Severity** | LOW — Script bug fixed |
| **Status** | RESOLVED (2026-07-25) |
| **Affects** | Figure 11 (Kaplan-Meier) |

**Description:** The project's internal `kaplan_meier_estimator()` function returns a dict with keys `timeline`, `survival_probability`, `confidence_interval_lower`, `confidence_interval_upper`, and `median_survival_time`. The initial figure generation script incorrectly assumed `times`, `survival`, `lower_95`, `upper_95`, `median_survival_days`.

**Resolution:** Keys corrected in `generate_figures.py`. Figure 11 verified to produce a sensible survival curve reaching S(t) ≈ 0 for long intervals.

---

## No Data Issues For

The following figures have no known data issues:
- **Figure 1** — Architecture diagram (no dynamic data)
- **Figure 2** — Dates verified against frozen split manifest
- **Figure 4** — Values from frozen `test_evaluation_results.json`
- **Figure 5** — Counts from frozen `test_evaluation_results.json`
- **Figure 6** — SHAP values from frozen `global_importance_source.csv`
- **Figure 8** — Architecture diagram (no dynamic data)
