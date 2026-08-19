# Data Audit Report — 2024 Mechanized Pothole Repairs

## 1. Audit Scope
This audit is strictly limited to the 2024 annual portion of the Montreal mechanized pothole repairs dataset. No other years are covered.

---

## 2. Integrity Evidence
*   **Filename**: `remplissage_niddepoule_2024.gpkg`
*   **Size**: `6369280` bytes
*   **SHA-256 Checksum**: `7e3ea9b16999fea7286501e5f1490ef84c89655bd6c3d812b38473e5232ccf34`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit
*   **SQLite/GPKG Integrity Check**: `ok`
*   **Application ID**: `0x47504b47`
*   **User Version**: `10200`
*   **Internal Layer Name**: `remplissage_niddepoule_2024` (Discovered)
*   **Expected Layer count**: Exactly 1 feature layer (discovered).
*   **Schema**:
    *   `fid` (integer, primary key)
    *   `geom` (POINT)
    *   `Véhicule` (string/text)
    *   `Date` (datetime)
*   **Data Rows**: `50411` rows
*   **RTree Rows**: `50411` rows (matches data row count exactly).
*   **FID Contiguity**: Contiguous starting at 1 and ending at 50411.
*   **Missing or Blank Values**: `0` missing values across all columns.

---

## 4. Time-Format and Temporal Results
*   **Date declared type**: DATETIME
*   **Date format**: T separator with 3 fractional digits (e.g. `2024-01-18T21:29:15.063`)
*   **Date Range**: `2023-04-11 09:04:57.063000` to `2024-05-30 23:56:08.063000`
*   **Unique Observed Dates**: `40` calendar dates
*   **Missing Calendar Dates in Range**: `376` dates
*   **Timezone**: Undeclared (no timezone is assumed).

### Monthly Counts
*   `2023-04`: `1` (Temporal out-of-year record from `2023-04-11 09:04:57.063`)
*   `2023-11`: `3` (Temporal out-of-year records from November 2023)
*   `2024-01`: `15783`
*   `2024-03`: `28518`
*   `2024-04`: `2350`
*   `2024-05`: `3756`
*   `2024-02`, `2024-06` to `2024-12`: `0`

*Scientific Note: Serious gaps exist; specifically, February 2024 has zero records, and June through December 2024 are entirely empty. This is an incomplete calendar year. Available 2024 coverage ends in May.*

---

## 5. Device/Vehicle Distribution
`Véhicule` is treated as a non-empty categorical string.
*   **Unique Vehicles**: `15`
*   **Vehicle Identifier Patterns**:
    *   `np_number` (e.g. `NP118`): `50403`
    *   `other_non_empty` (e.g. `RM511`): `8`
    *   `np_hyphen_number`: `0`
    *   `ct_prefixed`: `0`
*   **Notable Frequencies**:
    *   `NP118`: `8403`
    *   `NP115`: `7508`
    *   `NP107`: `6519`
    *   `NP117`: `6009`

---

## 6. Coordinate Audit and Spatial Exceptions
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Easting: `270757.7236069804` to `305995.53587361804`
    *   Northing: `5030616.666201861` to `5062074.05263267`
*   **Declared CRS**: `EPSG:2950` (NAD83 (CSRS) / MTM zone 8).
*   **Montréal Sanity Box Check**: All coordinates lie within anticipated local ranges.
*   **Unique Coordinate Pairs**: `44336`
*   **Spatial envelope exceptions**: `0` points fall outside of expected regional bounds.

---

## 7. Duplicate-Pattern Results
No rows have been removed or modified.
*   **Exact duplicates (all fields)**: `21` groups, `42` rows, `21` excess rows (max group size `2`)
*   **Same datetime**: `612` groups, `1232` rows, `620` excess rows (max group size `3`)
*   **Same geometry**: `4419` groups, `10494` rows, `6075` excess rows (max group size `25`)
*   **Same datetime + geometry**: `21` groups, `43` rows, `22` excess rows (max group size `3`)
*   **Same vehicle + datetime**: `42` groups, `84` rows, `42` excess rows (max group size `2`)
*   **Adjacent Exact Excess**: `19` rows are identical to their consecutive predecessor.

---

## 8. Anomalies and Year Mismatches
1.  **Temporal Out-of-Year Records**: Four records fall in the previous calendar year (2023).
    *   1 record on `2023-04-11 09:04:57.063`
    *   3 records in November 2023
    *   *Note*: These cross-year records remain unchanged in Phase 2.

---

## 9. Audit Decision
**PASS WITH TEMPORAL LIMITATIONS — structurally valid, but covers only January, March, April, and May 2024, with zero records in February, and contains four out-of-year records from 2023 (which remain unchanged in Phase 2). This represents a major temporal and cross-year limitation.**

---

## 10. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2024.gpkg` raw file remains completely unmodified.
