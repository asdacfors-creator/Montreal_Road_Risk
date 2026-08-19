# Data Audit Report — 2025 Mechanized Pothole Repairs

## 1. Audit Scope

This audit is strictly limited to the 2025 annual portion of the Montreal mechanized pothole repairs dataset. No other years are covered.

---

## 2. Integrity Evidence

*   **Filename**: `remplissage_niddepoule_2025.gpkg`
*   **Size**: `9117696` bytes
*   **SHA-256 Checksum**: `c64b6dec96dd44bee9ba5a1d4280ba77f733a75e48c4d7ce1f6fbd18148f4320`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit

*   **SQLite/GPKG Integrity Check**: `ok`
*   **Application ID**: `0x47504b47`
*   **User Version**: `10200`
*   **Internal Layer Name**: `remplissage_niddepoule_2025` (Discovered)
*   **Expected Layer count**: Exactly 1 feature layer (discovered).
*   **Schema**:
    *   `fid` (integer, primary key)
    *   `geom` (POINT)
    *   `Véhicule` (string/text)
    *   `Date` (datetime)
*   **Data Rows**: `74159` rows
*   **RTree Rows**: `74159` rows (matches data row count exactly).
*   **FID Contiguity**: Contiguous starting at 1 and ending at 74159.
*   **Missing or Blank Values**: `0` missing values across all columns.

---

## 4. Time-Format and Temporal Results

*   **Date declared type**: DATETIME
*   **Date format**: T separator with 3 fractional digits (e.g. `2025-01-18T21:29:15.063`)
*   **Date Range**: `2025-01-18 21:29:15.063000` to `2025-05-20 15:45:54.063000`
*   **Unique Observed Dates**: `47` calendar dates
*   **Missing Calendar Dates in Range**: `76` dates
*   **Timezone**: Undeclared (no timezone is assumed).

### Monthly Counts

*   `2025-01`: `13942`
*   `2025-02`: `1560`
*   `2025-03`: `29973`
*   `2025-04`: `28399`
*   `2025-05`: `285`
*   `2025-06` to `2025-12`: `0`

*Scientific Note: Severe gaps exist, with only 285 interventions recorded in May, and June through December entirely empty. This represents an incomplete calendar year. Coverage ends 2025-05-20. The 2025 dataset is not a complete calendar year and is not approved automatically as a full final-test year.*

---

## 5. Device/Vehicle Distribution

`Véhicule` is treated as a non-empty categorical string.
*   **Unique Vehicles**: `13`
*   **Vehicle Identifier Patterns**:
    *   `np_number` (e.g. `NP117`): `74159`
    *   `np_hyphen_number`: `0`
    *   `ct_prefixed`: `0`
    *   `other_non_empty`: `0`
*   **Notable Frequencies**:
    *   `NP117`: `9441`
    *   `NP111`: `8831`
    *   `NP113`: `7522`
    *   `NP114`: `7434`
    *   `NP110`: `6821`
    *   `NP109`: `6597`
    *   `NP112`: `6070`
    *   `NP115`: `5052`
    *   `NP107`: `4976`
    *   `NP124`: `3986`
    *   `NP116`: `3821`
    *   `NP118`: `3593`
    *   `NP125`: `3015`

---

## 6. Coordinate Audit and Spatial Exceptions
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Easting: `270722.2037498981` to `306145.215893911`
    *   Northing: `5030610.098262861` to `5062677.350527965`
*   **Declared CRS**: `EPSG:2950` (NAD83 (CSRS) / MTM zone 8).
*   **Montréal Sanity Box Check**: All points lie within broad expected local boundaries.
*   **Unique Coordinate Pairs**: `57887`
*   **Spatial envelope exceptions**: `0` points fall outside of expected regional bounds.

---

## 7. Duplicate-Pattern Results
No rows have been removed or modified.
*   **Exact duplicates (all fields)**: `202` groups, `404` rows, `202` excess rows (max group size `2`)
*   **Same datetime**: `1297` groups, `2615` rows, `1318` excess rows (max group size `3`)
*   **Same geometry**: `7698` groups, `17961` rows, `10263` excess rows (max group size `50`)
*   **Same datetime + geometry**: `202` groups, `404` rows, `202` excess rows (max group size `2`)
*   **Same vehicle + datetime**: `202` groups, `404` rows, `202` excess rows (max group size `2`)
*   **Adjacent Exact Excess**: `0` (No exact duplicates are consecutive in physical layout).

---

## 8. Scientific Limitations
1.  **Interventions vs. Distress**: Records interventions (decisions), not raw physical deterioration.
2.  **Date gaps**: Covers January to May only. Coverage ends 2025-05-20. Not a complete calendar year.
3.  **Projected Coordinates**: Stored in MTM Zone 8 (EPSG:2950).
4.  **No deduplication**: Duplicate spatial patterns are preserved.

---

## 9. Audit Decision
**PASS WITH TEMPORAL LIMITATIONS — structurally valid, but available coverage ends in May 2025 (not a complete calendar year, not approved automatically as a full final-test year) and contains 202 exact-duplicate occurrences.**

---

## 10. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2025.gpkg` raw file remains completely unmodified.
