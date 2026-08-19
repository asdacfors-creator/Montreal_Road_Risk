# Phase 4 Preflight Report

**Project:** Montreal Road Risk  
**Phase:** Phase 4 — Leakage-Safe Labels and Feature Engineering  
**Script:** `scripts/verify_preflight_coverage.py`  
**Date:** 2026-07-18  

---

## 1. Objective

The preflight verification confirms that all required Phase 4 inputs exist, are readable, and have sufficient coverage to construct a non-trivially populated analytical panel before any expensive pipeline execution begins.

---

## 2. Input Verification Results

### 2.1 Géobase Road Segments

| Item | Value |
|---|---|
| Source | `data/interim/spatial_base/geobase_32188.parquet` |
| Canonical segment count | **47,983** |
| Unique IDs | 47,983 (no duplicates) |
| CRS | EPSG:32188 |

### 2.2 Phase 3C Pothole Events

| Item | Value |
|---|---|
| Source | `data/interim/phase_3c/pothole_repairs_linked.parquet` + annual Phase 3A files |
| Total pothole events | **1,027,267** |
| Accepted events (linkage_status = accepted) | **1,020,457** |
| Unmatched events | **6,684** |
| Review-required events | **126** |
| Total excluded | **6,810** |
| Source-year mismatches | **5** |

### 2.3 Weather Data

| Item | Value |
|---|---|
| Source | ECCC daily climate records |
| First valid observation | 2016-12-07 |
| Coverage through | 2025-03-31 (acquisition date) |
| Anchor weather rows (102 month-end dates) | 102 |

### 2.4 Pavement Condition Surveys

| Item | Value |
|---|---|
| Source | Pavement condition linkage via Phase 3B |
| Survey-segment records (after linkage acceptance) | **117,416** |
| Campaigns | 2010, 2015, 2018, 2020, 2022, 2024 |
| Same-day duplicate resolution | Median of readings |
| As-of rule | `survey_date <= as_of_date` strictly enforced |

### 2.5 Road Assets

| Item | Value |
|---|---|
| Source | Road assets Phase 3B linkage |
| Accepted asset-segment links | From `road_assets_links.parquet` |
| Temporal eligibility states | active / crosses / future / missing |
| Date contradiction tracking | `date_contradiction_status` field |

### 2.6 Borough Boundaries

| Item | Value |
|---|---|
| Source | `data/interim/spatial_base/administrative_boundaries_32188.parquet` |
| Crosswalk | `data/interim/phase_3b/road_boundary_crosswalk.parquet` |
| Unmatched administrative segment | **4017818** (verified) |
| Previously incorrect segment (210080) | Does not exist in Géobase — corrected |

---

## 3. Anchor Calendar

| Parameter | Value |
|---|---|
| First anchor | 2016-12-31 |
| Last anchor | 2025-03-31 |
| Frequency | Monthly (month-end) |
| Total anchors | **102** |
| Published-resource eligible 90-day | **102** |
| Published-resource eligible 180-day | **102** |
| Strict-completeness eligible (any horizon) | **0** |

---

## 4. Panel Feasibility

| Metric | Value |
|---|---|
| Segments × Anchors | 47,983 × 102 |
| Expected panel rows | **4,894,266** |
| Expected target non-null rows (primary policy) | **4,894,266** |
| Expected strict-policy null rows | **4,894,266** |

---

## 5. Coverage Gaps and Limitations

| ID | Description |
|---|---|
| L3.1 | 2019 resource: no recorded events June–October (no-record interval, not a source gap) |
| L3.2 | No 2020 annual mechanized-repair resource published |
| L3.3 | 2025 resource was still updating at acquisition |
| L2.1 | Borough/manual repairs are not captured in any annual resource |
| L3.4 | 5 events have parsed year ≠ source file year; timestamps used as-is |

---

## 6. Pre-run Immutability Snapshot

- 88 files hashed under `data/raw/` and `data/interim/phase_3a/b/c/`
- Snapshot saved: `data/processed/phase_4/pre_run_snapshot.json`
- Comparison performed after run completion (see Phase 4 Gate Report §7)
