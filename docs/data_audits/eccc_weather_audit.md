# Montreal Road Risk — ECCC Weather Content Audit

This document presents the content audit and quality checks performed on the Environment and Climate Change Canada (ECCC) daily weather datasets.

---

## 1. Dataset Identity and Metadata

*   **Dataset ID**: `eccc_daily_weather`
*   **Official Landing Page**: [climate.weather.gc.ca Search Portal](https://climate.weather.gc.ca/historical_data/search_historic_data_e.html)
*   **Station Inventory URL**: [Station Inventory EN.csv](https://collaboration.cmc.ec.gc.ca/cmc/climate/Get_More_Data_Plus_de_donnees/Station%20Inventory%20EN.csv)
*   **Bulk Download URL**: [bulk_data_e.html](https://climate.weather.gc.ca/climate_data/bulk_data_e.html)
*   **License**: Open Government Licence - Canada (ECCC Standard)

---

## 2. File Verification & Paths

### Station Inventory File

*   **Local Relative Path**: `data/raw/eccc_weather/station_inventory/Station Inventory EN.csv`
*   **Modified Date Line**: `Modified Date: 2026-07-08 23:30 UTC`
*   **Disclaimer (Inventory)**: `"Station Inventory Disclaimer: Please note that this inventory list is a snapshot of stations on our website as of the modified date, and may be subject to change without notice."`
*   **Disclaimer (Station ID)**: `"Station ID Disclaimer: Station IDs are an internal index numbering system and may be subject to change without notice."`
*   **File Size**: `1,331,639` bytes
*   **SHA-256**: `33fcee2d966edf47fdaf5164fe91772f1987e4e7b4a19eede7ffdfcf898ea632`

### Annual Daily CSV Files

*   **File Count**: `34` annual files (17 McTavish + 17 Montréal-Trudeau)
*   **Expected Directory (McTavish)**: `data/raw/eccc_weather/mctavish/`
*   **Expected Directory (Trudeau)**: `data/raw/eccc_weather/montreal_trudeau/`
*   **Source/Destination Integrity**: **PASS** (Downloads match exact source HTTP responses).
*   **Git-Ignore Verification**: Ignored by `.gitignore` line 28 (`data/raw/*`). All raw files remain untracked and are not committed.

---

## 3. Raw CSV Structure and Encoding

*   **Encoding**: UTF-8 with BOM (`\ufeff`)
*   **Total Headers count**: `31` columns
*   **Header Keys**:

    `["Longitude (x)", "Latitude (y)", "Station Name", "Climate ID", "Date/Time", "Year", "Month", "Day", "Data Quality", "Max Temp (°C)", "Max Temp Flag", "Min Temp (°C)", "Min Temp Flag", "Mean Temp (°C)", "Mean Temp Flag", "Heat Deg Days (°C)", "Heat Deg Days Flag", "Cool Deg Days (°C)", "Cool Deg Days Flag", "Total Rain (mm)", "Total Rain Flag", "Total Snow (cm)", "Total Snow Flag", "Total Precip (mm)", "Total Precip Flag", "Snow on Grnd (cm)", "Snow on Grnd Flag", "Dir of Max Gust (10s deg)", "Dir of Max Gust Flag", "Spd of Max Gust (km/h)", "Spd of Max Gust Flag"]`

---

## 4. Date Continuity and Coverage
*   **Expected Period**: 2009-01-01 through 2025-12-31 inclusive (6,209 calendar days per station)
*   **McTavish Date Coverage**: Spans `2009-01-01` to `2025-12-31` (6,209 unique data rows)
*   **Trudeau Date Coverage**: Spans `2009-01-01` to `2025-12-31` (6,209 unique data rows)
*   **Missing Calendar Dates**: `0`
*   **Duplicate Dates**: `0`
*   **Out-of-year Dates**: `0`
*   **Non-monotonic Dates**: `0`

---

## 5. Complete Field Inventory (Missingness Table)

| Weather Variable | McTavish Missing | McTavish Missing % | Trudeau Missing | Trudeau Missing % |
| :--- | :--- | :--- | :--- | :--- |
| **Max Temp (°C)** | 102 | 1.6428% | 773 | 12.4497% |
| **Min Temp (°C)** | 71 | 1.1435% | 746 | 12.0148% |
| **Mean Temp (°C)** | 104 | 1.6750% | 776 | 12.4980% |
| **Total Precip (mm)**| 375 | 6.0396% | 141 | 2.2709% |
| **Total Rain (mm)** | 6209 | 100.00% | 6186 | 99.6296% |
| **Total Snow (cm)** | 6209 | 100.00% | 6209 | 100.00% |
| **Snow on Grnd (cm)**| 4674 | 75.2778% | 4462 | 71.8634% |

> [!WARNING]
> **Total Rain and Total Snow Unavailability**:
> 1. McTavish Total Rain and Total Snow are 100% missing. Montréal–Trudeau Total Snow is 100% missing, while Total Rain has only 23 populated observations and 6,186 missing observations (99.63% missing). Therefore, the separate Total Rain and Total Snow fields are not suitable as consistent cross-year features. Total Precip is the usable precipitation measurement, subject to its documented missingness.
> 2. Snow on Ground has severe missingness (over 70% missing at both stations).
> 3. Do not convert missing values to numeric zero.

### Flag Distributions
*   **Trace (T)**:
    *   McTavish Snow on Ground: 91 trace observations.
    *   Trudeau Snow on Ground: 99 trace observations.
*   **Estimated (E)**:
    *   McTavish Max Temp: 10, Min Temp: 74, Mean Temp: 41, Total Precip: 4.
    *   Trudeau Max Temp: 6, Min Temp: 35, Mean Temp: 5, Total Precip: 2.
*   **Missing (M)**: Flags coincide with empty measurements.

---

## 6. Temperature Quality Audit

### McTavish Temperature Ranges
*   **Max Temp**: Min = `-22.3°C`, Max = `36.6°C`, Mean = `12.28°C`, Median = `12.8°C`
*   **Min Temp**: Min = `-29.2°C`, Max = `25.5°C`, Mean = `4.26°C`, Median = `5.0°C`
*   **Mean Temp**: Min = `-24.9°C`, Max = `30.1°C`, Mean = `8.27°C`, Median = `9.0°C`

### Montréal-Trudeau Temperature Ranges
*   **Max Temp**: Min = `-22.3°C`, Max = `36.1°C`, Mean = `12.49°C`, Median = `13.4°C`
*   **Min Temp**: Min = `-29.1°C`, Max = `24.6°C`, Mean = `3.45°C`, Median = `4.2°C`
*   **Mean Temp**: Min = `-24.8°C`, Max = `29.9°C`, Mean = `7.98°C`, Median = `8.9°C`

*   **Anomalies check**:
    *   Max lower than min: `0` records.
    *   Mean outside min/max bounds: `0` records.
    *   Physically implausible values: None (all values lie within historically observed limits for Montréal).

---

## 7. Candidate Freeze-Thaw Feasibility counts (McTavish)
For audit purposes, candidate freeze-thaw counts were evaluated on the primary McTavish station:
*   **Definition 1 (Strict)**: `min_temp < 0°C AND max_temp > 0°C`
*   **Definition 2 (Le Zero)**: `min_temp <= 0°C AND max_temp > 0°C`
*   **Definition 3 (Ge Zero)**: `min_temp < 0°C AND max_temp >= 0°C`

### Yearly Candidate Freeze-Thaw Counts
*   **2009**: Def1 = 57, Def2 = 59, Def3 = 57 (3 missing temperature days)
*   **2010**: Def1 = 43, Def2 = 44, Def3 = 44 (3 missing temperature days)
*   **2011**: Def1 = 52, Def2 = 53, Def3 = 53 (0 missing temperature days)
*   **2012**: Def1 = 67, Def2 = 69, Def3 = 68 (1 missing temperature day)
*   **2013**: Def1 = 68, Def2 = 70, Def3 = 71 (1 missing temperature day)
*   **2014**: Def1 = 54, Def2 = 55, Def3 = 54 (37 missing temperature days)
*   **2015**: Def1 = 41, Def2 = 41, Def3 = 41 (7 missing temperature days)
*   **2016**: Def1 = 68, Def2 = 72, Def3 = 69 (6 missing temperature days)
*   **2017**: Def1 = 54, Def2 = 56, Def3 = 57 (14 missing temperature days)
*   **2018**: Def1 = 82, Def2 = 84, Def3 = 82 (8 missing temperature days)
*   **2019**: Def1 = 63, Def2 = 63, Def3 = 65 (1 missing temperature day)
*   **2020**: Def1 = 78, Def2 = 80, Def3 = 78 (3 missing temperature days)
*   **2021**: Def1 = 51, Def2 = 51, Def3 = 52 (2 missing temperature days)
*   **2022**: Def1 = 52, Def2 = 53, Def3 = 54 (6 missing temperature days)
*   **2023**: Def1 = 74, Def2 = 75, Def3 = 76 (3 missing temperature days)
*   **2024**: Def1 = 60, Def2 = 61, Def3 = 60 (2 missing temperature days)
*   **2025**: Def1 = 66, Def2 = 66, Def3 = 67 (7 missing temperature days)

---

## 8. Cross-Station Comparison (McTavish vs Montréal-Trudeau)
*   **Overlapping Dates Count**: `6,209` (100% overlap)
*   **Mean Temperature Correlation**: **0.998**
*   **Precipitation Correlation**: **0.9209**
*   **Mean Temperature Difference**: **0.426°C** (McTavish is slightly warmer)
*   **Median Temperature Difference**: **0.300°C**
*   **Missing Temperature at both stations**: **2** dates (2015-09-02, 2017-09-19)
*   **Missing Precipitation at both stations**: **27** dates
*   **Missing Temp at McTavish Only**: **102** dates (Trudeau is available)
*   **Missing Temp at Trudeau Only**: **774** dates (McTavish is available)

> [!NOTE]
> **Station Complementarity**:
> On dates where the primary station (McTavish) has missing values, the secondary station (Trudeau) has valid values in all but 2 cases. This high degree of complementarity supports fallback interpolation in Phase 3.

---

## 9. Temporal Leakage Rule
*   **Observation Month Cutoff**: Weather observations used for a segment-month feature must be available on or before that observation month's cutoff date.
*   **Predictor Window**: No weather occurring inside the future 90-day or 180-day target window may leak into the predictor features for a given segment-month observation.
*   **Candidate aggregation windows**: previous 30 days, previous 90 days, previous 365 days, and winter-season-to-date.

---

## 10. Audit Decision
*   **Audit Decision**: **PASS WITH LIMITATIONS**
*   **Limitations Logged**:
    1.  *Point Station Exposure*: Stations are treated as citywide proxies (**L2.32**).
    2.  *Spatial microclimate variations* (**L2.33**).
    3.  *McTavish Missing Precipitation* (**L2.34**).
    4.  *Trudeau missing temperature gaps* (**L2.35**).
    5.  *Total Rain and Total Snow Unavailable* (**L2.36**).
    6.  *Snow on Ground Incompleteness* (**L2.37**).
    7.  *Station ID Mutability* (**L2.38**).
    8.  *Cross-station fallback policy not yet approved* (**L2.39**).
    9.  *Freeze-thaw definition not yet finalized* (**L2.40**).
    10. *Weather features must obey observation cutoffs* (**L2.41**).
