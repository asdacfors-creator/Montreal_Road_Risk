# Data Audit Report — 2022 Mechanized Pothole Repairs

## 1. Audit Scope
This audit is strictly limited to the 2022 annual portion of the Montreal mechanized pothole repairs dataset. No other years are covered.

---

## 2. Integrity Evidence
*   **Filename**: `remplissage_niddepoule_2022.gpkg`
*   **Size**: `9093120` bytes
*   **SHA-256 Checksum**: `2da007281adeb4ff32d22e8b7c9fd9729ec8e5b1aa38d45de6c31822c0050048`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit
*   **SQLite/GPKG Integrity Check**: `ok`
*   **Application ID**: `0x47504b47`
*   **User Version**: `10200`
*   **Internal Layer Name**: `remplissage_niddepoule_2022` (Discovered)
*   **Expected Layer count**: Exactly 1 feature layer (discovered).
*   **Schema**:
    *   `fid` (integer, primary key)
    *   `geom` (POINT)
    *   `Véhicule` (string/text)
    *   `Date` (datetime)
*   **Data Rows**: `72062` rows
*   **RTree Rows**: `72062` rows (matches data row count exactly).
*   **FID Contiguity**: Contiguous starting at 1 and ending at 72062.
*   **Missing or Blank Values**: `0` missing values across all columns.

---

## 4. Time-Format and Temporal Results
*   **Date declared type**: DATETIME
*   **Date format**: T separator with 3 fractional digits (e.g. `2022-02-09T07:54:38.063`)
*   **Date Range**: `2022-02-09 07:54:38.063` to `2022-12-16 10:50:20.063`
*   **Unique Observed Dates**: `47` calendar dates
*   **Missing Calendar Dates in Range**: `264` dates
*   **Timezone**: Undeclared (no timezone is assumed).

### Monthly Counts
*   `2022-02`: `13086`
*   `2022-03`: `35242`
*   `2022-04`: `10559`
*   `2022-05`: `1769`
*   `2022-11`: `1`
*   `2022-12`: `11405`
*   `2022-01`, `2022-06` to `2022-10`: `0`

*Scientific Note: Severe gaps between June and October exist, with only 1 intervention recorded in November. This indicates incomplete annual coverage.*

---

## 5. Device/Vehicle Distribution
`Véhicule` is treated as a non-empty categorical string.
*   **Unique Vehicles**: `16`
*   **Vehicle Identifier Patterns**:
    *   `np_number` (starting with `NP` and digits, e.g. `NP115`): `71878`
    *   `ct_prefixed` (starting with `CT`): `76`
    *   `other_non_empty` (e.g. `RM511`): `108`
    *   `np_hyphen_number`: `0`
*   **Notable Frequencies**:
    *   `NP115`: `14489`
    *   `NP114`: `9884`
    *   `NP112`: `9310`
    *   `NP111`: `8713`
    *   `NP117`: `8209`
    *   `NP113`: `6743`
    *   `NP116`: `4123`
    *   `NP107`: `3788`
    *   `NP118`: `1400`
    *   `NP101`: `1395`
    *   `NP110`: `1342`
    *   `NP106`: `1115`
    *   `NP109`: `965`
    *   `RM511`: `108`
    *   `CT104 J-F Hamond`: `76`
    *   `NP100`: `27`

---

## 6. Coordinate Audit and Spatial Exceptions
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Easting: `270620.53951554716` to `306135.10594267864`
    *   Northing: `5030662.594208979` to `5062259.355921834`
*   **Declared CRS**: `EPSG:2950` (NAD83 (CSRS) / MTM zone 8).
    *   *Note*: The coordinate reference system (CRS) is explicitly declared as EPSG:2950 by the source layer.
*   **Montréal Sanity Box Check**: Eastings and Northings lie completely within the Montréal region (valid bounds for EPSG:2950).
*   **Unique Coordinate Pairs**: `57014`
*   **Spatial envelope exceptions**: `0` points fall outside of expected regional bounds in the project CRS.

---

## 7. Duplicate-Pattern Results
No rows have been removed or modified.
*   **Exact duplicates (all fields)**: `2041` groups, `4082` rows, `2041` excess rows (max group size `2`)
*   **Same datetime**: `2761` groups, `5596` rows, `2835` excess rows (max group size `6`)
*   **Same geometry**: `8850` groups, `21813` rows, `12963` excess rows (max group size `46`)
*   **Same datetime + geometry**: `2041` groups, `4082` rows, `2041` excess rows (max group size `2`)
*   **Same vehicle + datetime**: `2078` groups, `4157` rows, `2079` excess rows (max group size `3`)
*   **Adjacent Exact Excess**: `11` rows are identical to their consecutive predecessor.
*   *Statement: The occurrence of exact-duplicate coordinate and timestamp values suggests potential recording system issues or multiple interventions logged in quick succession. These are preserved for down-stream modeling decisions. The duplicate-removal policy remains deferred to a later phase.*

---

## 8. Scientific Limitations
1.  **Interventions vs. Distress**: Records interventions (decisions), not raw physical deterioration.
2.  **Date gaps**: Covers February to May, and December. Virtually zero records June through November.
3.  **Projected Coordinates**: Stored in MTM Zone 8 (EPSG:2950).
4.  **No deduplication**: Duplicate spatial patterns are preserved; the duplicate-removal policy remains deferred.

---

## 9. Audit Decision
**PASS WITH TEMPORAL LIMITATIONS — structurally valid, but suffers from significant seasonal/temporal gaps during summer/fall months and contains 2041 exact-duplicate occurrences. Duplicate-removal policy remains deferred.**

---

## 10. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2022.gpkg` raw file remains completely unmodified.
