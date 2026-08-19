# Phase 4 Feature Engineering Report

**Project:** Montreal Road Risk  
**Phase:** Phase 4 — Leakage-Safe Labels and Feature Engineering  
**Version:** 1.0  
**Date:** 2026-07-18  

---

## 1. Overview

This report documents the feature engineering methodologies, feature groups, and data representations constructed for the Montreal Road Risk modeling panel. The final dataset consists of a monthly segment-month panel of **4,894,266** rows, constructed from **47,983** road segments over **102** monthly anchors (December 31, 2016 through May 31, 2025).

---

## 2. Feature Groups and Variables

The features are grouped into five distinct logical categories:

### 2.1 Historical Repairs (Lagged Target Features)

These features characterize a segment's historical repair activity strictly on or before the anchor date ($t$).

- **`days_since_last_repair`**: Number of days from the most recent accepted repair on the segment to $t$.
- **`no_prior_repair_flag`**: Binary flag (1 if no repairs were recorded on the segment before $t$, 0 otherwise).
- **`repair_event_count_raw_{W}d`**: Total raw accepted pothole repairs on the segment in the trailing $W$-day window ($W \in \{30, 90, 180, 365\}$).
- **`repair_event_count_collapsed_{W}d`**: Total duplicate-collapsed accepted pothole repairs in the trailing $W$-day window.
- **`repair_active_days_{W}d`**: Number of distinct calendar days with at least one accepted repair in the trailing $W$-day window.
- **`prior_repair_months_12m`**: Number of distinct calendar months with at least one accepted repair in the past 12 months.

### 2.2 Rolling Weather Features

Weather features are compiled from daily Environment and Climate Change Canada (ECCC) records, using a robust multi-station fallback strategy. They represent rolling climate metrics for the trailing $W$-day window ($W \in \{30, 90, 180, 365\}$).

- **`total_precip_sum_{W}d`**: Cumulative precipitation (mm) in the window.
- **`mean_temp_mean_{W}d`**: Average daily mean temperature (°C).
- **`min_temp_min_{W}d`**: Minimum daily temperature (°C).
- **`max_temp_max_{W}d`**: Maximum daily temperature (°C).
- **`freeze_thaw_strict_sum_{W}d`**: Count of strict freeze-thaw cycles (days with $T_{min} < 0^\circ\text{C}$ and $T_{max} > 0^\circ\text{C}$).
- **`freeze_thaw_min_le_zero_sum_{W}d`**: Count of freeze-thaw cycles using $T_{min} \le 0^\circ\text{C}$ and $T_{max} > 0^\circ\text{C}$).
- **`freeze_thaw_max_ge_zero_sum_{W}d`**: Count of freeze-thaw cycles using $T_{min} < 0^\circ\text{C}$ and $T_{max} \ge 0^\circ\text{C}$).
- **`weather_coverage_ratio_{W}d`** & **`weather_complete_{W}d`**: Window observation coverage indicators.
- **`{metric}_fallback_days_{W}d`**: Number of days in the window where a fallback station was used.

### 2.3 Pavement Condition Surveys

Pavement condition metrics represent the structural health of the road, updated dynamically using an as-of join key (`survey_date <= t`).

- **`latest_pci`**: Median Pavement Condition Index (PCI) score from the most recent survey.
- **`pci_min`**, **`pci_max`**, **`pci_std`**: PCI distribution statistics for the segment.
- **`latest_iri`**: Median International Roughness Index (IRI) score.
- **`condition_candidate_count`**: Number of independent condition measurements recorded during the survey.
- **`condition_campaign_scope`**: Categorical campaign type (`arterial`, `local`, `mixed_or_citywide`, `unknown`).
- **`condition_missing_flag`**: Binary flag indicating if no surveys had occurred on or before $t$.
- **`days_since_condition_survey`**: Time elapsed since the most recent survey.

### 2.4 Road Assets

Asset construction and resurfacing age details are joined relative to $t$. If construction lies in the future or crosses the anchor, it is censored.

- **`years_since_construction_lower` / `_upper`**: Age interval of the road asset.
- **`years_since_resurfacing_lower` / `_upper`**: Resurfacing age interval.
- **`future_asset_record_hidden_flag`**: 1 if construction starts after $t$.
- **`age_interval_crosses_as_of_flag`**: 1 if the construction interval straddles $t$.
- **`resurfacing_interval_crosses_as_of_flag`**: 1 if the resurfacing interval straddles $t$.
- **`asset_temporal_eligibility_status`**: Categorical status (`active`, `crosses`, `future`, `missing`).
- **`resurfacing_before_construction_candidate_flag`** & **`date_contradiction_status`**: Data quality audits.

### 2.5 Static Road Features

Static descriptors of the segment derived from the Geobase road network and administrative boundary crosswalks.

- **`functional_road_class`**: Functional category (e.g. collector, local).
- **`road_type` / `road_category`**: Structural type (e.g. bridge, tunnel, street).
- **`segment_length_m`**: Length of the road segment in metres.
- **`official_administrative_name`**: Name of the borough containing the segment.
- **`administrative_category`**: Category of the administrative unit (`Arrondissement`, `Ville liée`, or `unresolved`).
- **`boundary_crossing_flag`**: 1 if the segment crosses a borough boundary.
- **`boundary_candidate_count`**: Number of intersecting administrative polygons.
- **`unmatched_boundary_flag`**: 1 if the segment is unmatched (specifically segment `4017818`).

---

## 3. Data Missingness and Baseline Analysis

We summarize key missingness rates and counts across the completed dataset:
1. **Pavement condition missingness**: **33.1216%** of segment-month rows have no prior pavement survey. This represents segments that were not surveyed in any historical campaigns prior to the anchor.
2. **No prior repair rows**: **64.19%** of segment-month rows have no record of mechanized pothole repair in history prior to the anchor.
3. **Asset status distribution**:
   - `missing`: **3,301,842** rows (67.46%)
   - `active`: **1,295,304** rows (26.47%)
   - `crosses`: **196,831** rows (4.02%)
   - `future`: **100,289** rows (2.05%)

---

## 4. Leakage Prevention and Chronological Boundaries

To guarantee that the modeling dataset is safe from information leakage (lookahead bias), the following controls are strictly enforced:
- **Repair History**: Only events with `event_timestamp_naive <= t` enter historical features.
- **Pavement Conditions**: Only surveys with `survey_date <= t` enter pavement features. Surveys happening after $t$ are strictly excluded from the as-of state.
- **Road Assets**: Assets with `construction_date_lower_bound > t` are hidden (`future` status), and their ages are set to null.
- **Weather**: Daily weather features only aggregate days in $(t-W, t]$.
- **Target Variable**: Target windows strictly start at $t + 1$ day, ensuring no overlap with history. Strict-policy targets are kept entirely null due to the absence of verified complete-universe daily data.
