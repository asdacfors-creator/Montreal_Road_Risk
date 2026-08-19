# Phase 3C Temporal Preprocessing Audit Report

This report summarizes the results of the temporal normalization, timezone localization, and daily weather fallback operations conducted during Phase 3C.

---

## 1. Dataset Temporal Coverage

The table below shows the record counts, observed date ranges, missing counts, and parse statistics for each dataset.

| Dataset | Total Records | Earliest Date | Latest Date | Missing Dates | Parse Failures / Unknowns | Distinct Repeated Dates | Rows in Repeated Dates | Excess Rows |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Pothole Repairs** | $1,027,267$ | 2016-12-07 | 2025-05-20 | $0$ | $0$ | $548$ | $1,027,252$ | $1,026,704$ |
| **Pavement Condition** | $121,163$ | 2009-09-15 | 2024-10-23 | $0$ | $0$ | $318$ | $121,163$ | $120,845$ |
| **Road Assets** | $64,025$ | 1899-12-30 | 2026-01-14 | $0$ | $35,830$ | $403$ | $28,102$ | $27,699$ |
| **Weather Daily (Canonical)** | $6,209$ | 2009-01-01 | 2025-12-31 | $0$ | $0$ | $0$ | $0$ | $0$ |

### A. Wording and Definition of "Repeated Dates"
- **Distinct Repeated Dates**: The number of unique calendar dates that appear more than once in the dataset.
- **Rows in Repeated Dates**: The total number of rows associated with these repeated dates.
- **Excess Rows**: The number of additional rows beyond one row per repeated date (which corresponds to `duplicated().sum()`).
- *Note*: Legitimate multiple repairs or surveys on the same date are not considered duplicate events; they represent distinct events occurring on the same calendar day.

### B. Road Assets Construction and Resurfacing Mappings
January 1st is utilized strictly as a computational year lower bound (`construction_date_lower_bound` / `resurfacing_date_lower_bound`) or year start (`construction_year_start` / `resurfacing_year_start`) and does not represent an actual observed date where the source provides only a year or approximate interval. Precision categories are tracked separately:

- **Construction Date Precision Counts**:
  - `unknown` (Inconnu): $35,830$ rows
  - `approximate_interval` (+/- 100 years): $20,880$ rows
  - `imprecise_year` (within current year, +/- 5 years, +/- 6 months, etc.): $7,275$ rows
  - `precise` (précise): $40$ rows
- **Resurfacing Date Precision Counts**:
  - `missing` (no resurfacing record): $55,535$ rows
  - `precise`: $7,132$ rows
  - `imprecise_year`: $1,358$ rows
- **Date Logic Anomalies**:
  - Exactly $132$ records contain resurfacing-before-construction anomalies where the construction date is registered after the resurfacing date.

---

## 2. Timezone and Localization Results

Naive timestamps are assumed to represent local time in Montreal and are localized to `America/Toronto` with DST safeguards:

### Potholes
- **Total Records**: $1,027,267$
- **Successfully Localized**: $1,027,267$
- **Ambiguous DST**: $0$
- **Nonexistent DST**: $0$
- **Missing Timestamps / Parse Failures**: $0$ (timestamps could not be parsed)
- **Source Year Status**:
  - `match`: $1,027,262$
  - `unknown_parse_failure`: $0$
  - `mismatch`: $5$

### Genuine Year Mismatch Records
Only five genuine out-of-year records exist in the pothole repairs dataset (which are preserved unmodified in their source files):

| Source File | Source Year | Parsed Event Year | Count | Earliest Date | Latest Date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pothole_repairs_2023_32188.parquet` | 2023 | 2022 | 1 | 2022-12-20 | 2022-12-20 |
| `pothole_repairs_2024_32188.parquet` | 2024 | 2023 | 4 | 2023-04-11 | 2023-11-07 |

---

## 3. Daily Weather Fallback Performance

Combined daily records span $6,209$ days from 2009-01-01 through 2025-12-31. Same-day fallback from McTavish (primary) to Montréal-Trudeau (secondary) was performed **only** for allowlisted variables:

| Variable Name | McTavish Missing Count | Fallback Used Count | Remaining Missing Count |
| :--- | :--- | :--- | :--- |
| **Mean Temp** | $104$ | $102$ | $2$ (both stations missing) |
| **Min Temp** | $71$ | $71$ | $0$ |
| **Max Temp** | $102$ | $100$ | $2$ (both stations missing) |
| **Total Precip** | $375$ | $348$ | $27$ (both stations missing) |

*Excluded from fallback (Strictly station-specific)*:
- **Total Rain**: McTavish only (no fallback allowed)
- **Total Snow**: McTavish only (no fallback allowed)
- **Snow on Ground**: McTavish only (no fallback allowed)

---

## 4. Right-Edge Target Eligibility Horizons

Below are the computed candidate right-edge dates for future 90-day and 180-day target outcome windows. These are coverage analysis boundaries only and do not define any modelling splits.

- **Potholes**:
  - Latest Date: `2025-05-20`
  - Candidate Right Edge (90-day): `2025-02-19`
  - Candidate Right Edge (180-day): `2024-11-21`
- **Pavement Condition**:
  - Latest Date: `2024-10-23`
  - Candidate Right Edge (90-day): `2024-07-25`
  - Candidate Right Edge (180-day): `2024-04-26`
- **Weather Daily**:
  - Latest Date: `2025-12-31`
  - Candidate Right Edge (90-day): `2025-10-02`
  - Candidate Right Edge (180-day): `2025-07-04`
