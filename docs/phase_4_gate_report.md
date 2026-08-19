# Phase 4 Quality Gate Report

This report summarizes the results, methodology, and quality gate audits for **Phase 4: Leakage-Safe Labels and Feature Engineering**.

---

## 1. Summary of Phase Results

### Panel and Outcome Targets
- **Cartesian Product**: Built the segment-by-month panel spanning 47,983 segments and 102 monthly anchors (December 31, 2016 through May 31, 2025), producing exactly **4,894,266** panel rows.
- **Primary 90-Day Target**: Constructs target label representing if a segment has at least one mechanized repair event in the official Montreal resources during the future 90 days.
- **180-Day Sensitivity Target**: Evaluates future repair likelihood over a wider 180-day window.
- **Target Exclusion Audit**: Separates events with `linkage_status` of `unmatched` or `review_required`. Exactly **6,810** events are documented in the exclusion audit.
- **Duplicate Collapsing**: Groups same-day, same-vehicle, same-location repair events. Collapses **1,020,457** accepted events into **965,274** unique collapsed events.

### Feature Engineering
- **Historical Repairs**: Computes rolling active days, raw counts, collapsed counts (over 30d, 90d, 180d, 365d), and active repair months in the past 12 months.
- **Canonical Weather**: Computes rolling temperature (mean, min, max), precipitation, and freeze-thaw counts (strict, min <= 0, max >= 0) with fallback indicators.
- **Pavement Conditions**: Joins latest pavement surveys dynamically using `survey_date <= as_of_date`. Resolves same-day duplicates using median.
- **Road Assets**: Computes years since construction/resurfacing. Conceals future assets and flags date contradictions.
- **Static Features**: Joins functional road class, administrative name, and unmatched boundary flags.

---

## 2. Eligibility Policy Decisions

| Policy | Anchor Horizon | Total Anchors | Eligible Anchors | Ineligible Reason |
| :--- | :--- | :---: | :---: | :--- |
| **Strict Verified Completeness** | 90 days / 180 days | 102 | **0** | No years are officially audited as 100% complete |
| **Published Resource Observation Universe** | 90 days / 180 days | 102 | **102** | Every finalized official annual resource represents the full universe |

---

## 3. Dataset-Level QA and Row Reconciliations

- **Total Panel Rows**: 4,894,266
- **Eligible 90d Rows (Primary)**: 4,894,266
- **Eligible 180d Rows (Primary)**: 4,894,266
- **Strict Policy 90d/180d Target (Null Count)**: 4,894,266
- **Target Exclusions**: 6,810 event rows
- **Duplicate Membership Entries**: 1,020,457 event rows
- **Collapsed Accepted Events**: 965,274 event rows

---

## 4. Quality and Safety Controls

- **Raw Data Immutability**: Proved that all 55 raw files (and Phase 3 inputs) remain 100% untouched. Checksum scan matched perfectly (0 changed, 0 missing, 0 added).
- **Information Leakage Prevention**: Enforced strict chronological boundaries (`event_date <= as_of_date`, `survey_date <= as_of_date`, `weather_date <= as_of_date`). Asserted that strict policy targets are null.
- **Determinism**: Regenerated partitions in verification mode and verified that row-count, schemas, null masks, and sorted-content fingerprints are identical (all 102 partitions verified deterministic).
- **Lints and Tests**:
  - **Pytest**: 150 tests successfully passed (100% success rate).
  - **Ruff**: 100% clean check.
