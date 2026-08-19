# Temporal Normalization and Alignment Rules Specification

This document defines the temporal standards, parsing heuristics, timezone contexts, and fallback logic established during Phase 3C of the Montreal Road Deterioration project.

---

## 1. Timezone and Localization Policy

### Explicit Timezone Assumption

Source timestamps (such as those in raw pothole repairs CSV/GPKG files) lack explicit timezone metadata (UTC offsets or timezone strings). 

- **Timezone Assumption**: All timestamps are assumed to represent local time in Montreal, Quebec, Canada, and are explicitly localized to the **`America/Toronto`** timezone.
- **Naiveness Preservation**: The original naive date and time string fields are preserved unmodified in all intermediate and output Parquet files.

### Daylight-Saving Time (DST) Safety

To prevent coordinate shifts or duplicate observations due to spring-forward and fall-back transitions, the pipeline classifies localization status for every record into one of five categories:
1. **`successfully_localized`**: Naive time mapped to a unique local timezone offset.
2. **`ambiguous_dst`**: Fall-back transition hour (e.g. 01:00 to 02:00 in November) where a local time occurs twice.
3. **`nonexistent_dst`**: Spring-forward transition hour (e.g. 02:00 to 03:00 in March) where local time does not exist.
4. **`missing`**: The raw timestamp was null or missing in the source.
5. **`parse_failure`**: The raw timestamp was unparseable.

> [!WARNING]
> **No Silent Shifts**: Under no circumstances does the pipeline guess or shift ambiguous or nonexistent timestamps. If localization cannot be resolved uniquely, the record retains its original naive local time, is flagged with `ambiguous_dst` or `nonexistent_dst`, and is saved in that state for downstream manual verification.

---

## 2. Pavement-Condition Campaign Availability

Pavement quality inspections (reporting Pavement Condition Index (PCI) and International Roughness Index (IRI)) represent irregular campaigns conducted in 2010, 2015, 2018, 2020, 2022, and 2024.

### Information Leakage Controls

To guarantee that model training remains mathematically sound and free from future data leakage:
- **Availability cut-off**: An auscultation observation becomes available for panel merging **no earlier than its actual survey date** (`survey_date` / `DateReleve`).
- **Prohibition of Backward Filling**: A future survey campaign (e.g. 2024 condition inspections) must never be back-propagated or used to represent road state in earlier observation months (e.g. 2023).
- **Forward-carry constraints**: Any decision to carry condition observations forward in time is deferred to Phase 4 panel construction and is strictly locked during Phase 3.
- **Same-day duplicate handling**: Multiple inspections occurring on the same segment on the same day are fully preserved as separate records and flagged with duplicate indicators.

---

## 3. ECCC Weather Same-Day Fallback Rules

Daily weather observations are compiled from 2009-01-01 through 2025-12-31 (6,209 daily rows) for both stations:
- **Primary Station**: McTavish (Climate ID `7024745`)
- **Secondary Station**: Montréal-Trudeau (Climate ID `702S006`)

### Variable-Specific Fallback Allowlist

To prevent geographic dilution of sensitive precipitation types, same-calendar-day fallback from McTavish to Trudeau is permitted **only** for:
- `Mean Temp (°C)`
- `Min Temp (°C)`
- `Max Temp (°C)`
- `Total Precip (mm)`

For each of these allowed variables, daily records contain explicit fallback flags:
- `{var}_fallback_used` (0/1)
- `{var}_original_mctavish_missing` (0/1)
- `{var}_source_station_used` (`"MCTAVISH"` or `"MONTREAL_TRUDEAU"`)

### Excluded Variables (No Fallback or Combining)

The following variables are highly sensitive to local micro-climates and are excluded from fallback:
- **`Total Rain (mm)`**: Spatially variable, insufficient completeness to justify interpolation.
- **`Total Snow (cm)`**: Spatially variable, insufficient completeness.
- **`Snow on Grnd (cm)`**: Highly sensitive to local heat-island and terrain factors; must remain strictly station-specific.

### Observed-Zero Preservation

An observed numeric zero (0.0) is a valid, meaningful weather observation (e.g., no snow on ground, or 0.0°C temperature) and is **never** interpreted as missing or null.

---

## 4. Road Assets Temporal Uncertainty Rules

Road asset construction and resurfacing dates are highly imprecise. Over 88% of construction dates represent year-only, approximate, or unknown values.

### A. Non-Exact observed construction dates

- **Proxy Lower Bounds**: January 1st is utilized strictly as a computational year start (`construction_year_start` / `resurfacing_year_start`) or computational lower bound (`construction_date_lower_bound` / `resurfacing_date_lower_bound`). Downstream modeling components must not treat this proxy as an exact day.
- **Precision Tracking**: Every asset is explicitly flagged with its temporal precision status (`construction_date_precision`, `resurfacing_date_precision`):
  - `precise`: Fully parseable exact date.
  - `imprecise_year`: Matched year-only string (e.g. `2012`).
  - `approximate_interval`: Wide interval approximation (e.g., +/- 100 years).
  - `unknown`: Missing date precision but has a reference statement (e.g., "Inconnu").
  - `missing`: Tabular null or empty value.
- **Proxy and Unknown Flags**:
  - `construction_date_is_proxy` / `resurfacing_date_is_proxy` is `1` for any non-precise date (including year-only, approximate, or unknown).
  - `construction_date_unknown` / `resurfacing_date_unknown` is `1` for any unknown or missing date.

### B. Resurfacing-Before-Construction Anomaly Check

- The pipeline checks and flags records where the resurfacing lower bound date is strictly less than the construction lower bound date.
- These records are flagged with `resurfacing_before_construction_candidate_flag = 1` and preserved unmodified for downstream sensitivity analysis.
