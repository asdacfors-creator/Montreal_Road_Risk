# Data Audit Report — 2023 Mechanized Pothole Repairs

## 1. Audit Scope

This audit is strictly limited to the 2023 annual portion of the Montreal mechanized pothole repairs dataset. No other years are covered.

---

## 2. Integrity Evidence

*   **Filename**: `remplissage_niddepoule_2023.gpkg`
*   **Size**: `12926976` bytes
*   **SHA-256 Checksum**: `548568a84ce07cec077c6da6ea2f5b1e98ff620b9317c9d22bda7e74ef75e04e`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit

*   **SQLite/GPKG Integrity Check**: `ok`
*   **Application ID**: `0x47504b47`
*   **User Version**: `10200`
*   **Internal Layer Name**: `remplissage_niddepoule_2024` (Discovered - Note the layer-year mismatch anomaly).
    *   *Note*: The layer was not renamed in Phase 2 and remains `remplissage_niddepoule_2024` in the raw database.
*   **Expected Layer count**: Exactly 1 feature layer (discovered).
*   **Schema**:
    *   `fid` (integer, primary key)
    *   `geom` (POINT)
    *   `Véhicule` (string/text)
    *   `Date` (datetime)
*   **Data Rows**: `105773` rows
*   **RTree Rows**: `105773` rows (matches data row count exactly).
*   **FID Contiguity**: Contiguous starting at 1 and ending at 105773.
*   **Missing or Blank Values**: `0` missing values across all columns.

---

## 4. Time-Format and Temporal Results

*   **Date declared type**: DATETIME
*   **Date format**: Space separator, without fractional seconds or with 3 fractional digits (e.g. `2022-12-20 15:34:07` and `2023-01-01 12:34:56.789`)
*   **Date Range**: `2022-12-20 15:34:07` to `2023-05-05 00:48:19.907000`
*   **Unique Observed Dates**: `61` calendar dates
*   **Missing Calendar Dates in Range**: `76` dates
*   **Timezone**: Undeclared (no timezone is assumed).

### Monthly Counts

*   `2022-12`: `1` (Temporal out-of-year anomaly: `2022-12-20 15:34:07`)
*   `2023-01`: `4791`
*   `2023-02`: `35578`
*   `2023-03`: `42056`
*   `2023-04`: `18688`
*   `2023-05`: `4659`
*   `2023-06` to `2023-12`: `0`

*Scientific Note: Severe temporal gaps exist, with zero records registered for June through December. This is an incomplete calendar year.*

---

## 5. Device/Vehicle Distribution

`Véhicule` is treated as a non-empty categorical string.
*   **Unique Vehicles**: `15`
*   **Vehicle Identifier Patterns**:
    *   `np_number` (e.g. `NP118`): `105421`
    *   `ct_prefixed` (e.g. `CT104`): `186`
    *   `other_non_empty` (e.g. `RM511`): `166`
    *   `np_hyphen_number`: `0`
*   **Notable Frequencies**:
    *   `NP118`: `11600`
    *   `NP117`: `11214`
    *   `NP109`: `6029` (Top frequencies are dominated by NP-numbered devices).

---

## 6. Coordinate Audit and Spatial Exceptions
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Easting: `270693.6133481674` to `306143.43716817675`
    *   Northing: `5030613.224240331` to `5062694.309502335`
*   **Declared CRS**: `EPSG:2950` (NAD83 (CSRS) / MTM zone 8).
*   **Montréal Sanity Box Check**: All coordinates are within expected local ranges.
*   **Unique Coordinate Pairs**: `89242`
*   **Spatial envelope exceptions**: `0` points fall outside of expected regional bounds.

---

## 7. Duplicate-Pattern Results
No rows have been removed or modified.
*   **Exact duplicates (all fields)**: `106` groups, `214` rows, `108` excess rows (max group size `3`)
*   **Same datetime**: `1595` groups, `3214` rows, `1619` excess rows (max group size `3`)
*   **Same geometry**: `11409` groups, `27940` rows, `16531` excess rows (max group size `59`)
*   **Same datetime + geometry**: `106` groups, `214` rows, `108` excess rows (max group size `3`)
*   **Same vehicle + datetime**: `189` groups, `381` rows, `192` excess rows (max group size `3`)
*   **Adjacent Exact Excess**: `103` rows are identical to their consecutive predecessor.

---

## 8. Anomalies and Year Mismatches
1.  **Layer Name Mismatch**: The internal layer name is `remplissage_niddepoule_2024` even though the physical file contains 2023 observations. This represents a database naming anomaly. The layer is not renamed in Phase 2.
2.  **Temporal Out-of-Year Record**: One record (fid `1`) falls in the previous calendar year (`2022-12-20 15:34:07`).
    *   `Date` = `2022-12-20 15:34:07`
    *   `Véhicule` = `CT104 J-F Hamond`

---

## 9. Audit Decision
**PASS WITH LAYER-YEAR MISMATCH AND TEMPORAL LIMITATIONS — structurally valid, but contains a layer-naming anomaly (layer named 2024 inside 2023 file, which was not renamed in Phase 2), one record from 2022, and covers only January through May (ending in May 2023). This represents a major metadata and temporal limitation.**

---

## 10. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2023.gpkg` raw file remains completely unmodified.
