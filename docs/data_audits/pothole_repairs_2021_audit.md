# Data Audit Report — 2021 Mechanized Pothole Repairs

## 1. Audit Scope
This audit is strictly limited to the 2021 annual portion of the Montreal mechanized pothole repairs dataset. No other years are covered.

---

## 2. Integrity Evidence
*   **Filename**: `remplissage_niddepoule_2021.gpkg`
*   **Size**: `6266880` bytes
*   **SHA-256 Checksum**: `a7c7b0a44db5ef84fd885d35730a94d0292815da8c036cb479c6dc793d2dd245`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit
*   **SQLite/GPKG Integrity Check**: `ok`
*   **Application ID**: `0x47504b47`
*   **User Version**: `10200`
*   **Internal Layer Name**: `remplissage_niddepoule_2021` (Discovered)
*   **Expected Layer count**: Exactly 1 feature layer (discovered).
*   **Schema**:
    *   `fid` (integer, primary key)
    *   `geom` (POINT)
    *   `Véhicule` (string/text)
    *   `Date` (datetime)
*   **Data Rows**: `50320` rows
*   **RTree Rows**: `50320` rows (matches data row count exactly).
*   **FID Contiguity**: Contiguous starting at 1 and ending at 50320.
*   **Missing or Blank Values**: `0` missing values across all columns.

---

## 4. Time-Format and Temporal Results
*   **Date declared type**: DATETIME
*   **Date format**: T separator with 3 fractional digits (e.g. `2021-01-25T07:35:20.063`)
*   **Date Range**: `2021-01-25 07:35:20.063` to `2021-03-17 09:32:25.127`
*   **Unique Observed Dates**: `24` calendar dates
*   **Missing Calendar Dates in Range**: `28` dates
*   **Timezone**: Undeclared (no timezone is assumed).

### Monthly Counts
*   `2021-01`: `8655`
*   `2021-02`: `10060`
*   `2021-03`: `31605`
*   `2021-04` to `2021-12`: `0`

*Scientific Note: Widespread lack of records for April through December indicates this is an incomplete calendar year and cannot be used as a full annual representation. Available temporal coverage ends 2021-03-17.*

---

## 5. Device/Vehicle Distribution
`Véhicule` is treated as a non-empty categorical string.
*   **Unique Vehicles**: `14` (All 50320 rows use NP-hyphen-number identifiers).
*   **NP-hyphen-number Count**: `50320`
*   **Notable Frequencies**:
    *   `NP-117`: `7786`
    *   `NP-111`: `6886`
    *   `NP-106`: `4975`
    *   `NP-115`: `4970`
    *   `NP-107`: `4267`
    *   `NP-112`: `4179`
    *   `NP-109`: `3670`
    *   `NP-116`: `3451`
    *   `NP-110`: `3125`
    *   `NP-114`: `3028`
    *   `NP-118`: `1607`
    *   `NP-108`: `1571`
    *   `NP-100`: `449`
    *   `NP-101`: `1` (lowest observed frequency)

---

## 6. Coordinate Audit and Spatial Exceptions
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Longitude: `-73.93544006347656` to `-73.43585205078125`
    *   Latitude: `45.303707122802734` to `45.69873809814453`
*   **Montréal Sanity Box Check**: **PASS** (Zero points fall outside the broad regional box of lat 45-46, lon -75 to -72).
*   **Unique Coordinate Pairs**: `43134`
*   **Geometry Blob srs_id**: `100000` (custom GeoPackage SRS entry whose definition matches WGS 84).
    *   *Note*: The file uses a custom WGS 84 SRS entry with `srs_id 100000` and organization is `NONE`. It is not described as formally declared EPSG:4326.
*   **CRS Declared**: WGS 84 (custom srs_id 100000, organization NONE).

### Spatial envelope exceptions
Five 2021 repair points fall outside the axis-aligned bounding envelope of the current Géobase road-network snapshot: one point is east of the envelope and four points are south of it. This observation does not prove that the points fall outside Montréal or outside any borough. Administrative-boundary validity remains unassessed until an authoritative boundary layer is acquired and a polygon containment test is performed during the authorized GIS-processing phase. The exact coordinates and identifiers of these points are preserved:
1.  **fid 46641**: `NP-116` at `2021-03-17T03:27:36.063` (lon `-73.43585205078125`, lat `45.5064582824707`) - Located east of the snapshot envelope.
2.  **fid 46642**: `NP-116` at `2021-03-17T07:40:05.127` (lon `-73.7470703125`, lat `45.305625915527344`) - Located south of the snapshot envelope.
3.  **fid 46643**: `NP-116` at `2021-03-17T07:59:32.063` (lon `-73.74784088134766`, lat `45.304447174072266`) - Located south of the snapshot envelope.
4.  **fid 46644**: `NP-116` at `2021-03-17T08:10:45.127` (lon `-73.74817657470703`, lat `45.303707122802734`) - Located south of the snapshot envelope.
5.  **fid 46645**: `NP-116` at `2021-03-17T09:32:25.127` (lon `-73.74612426757812`, lat `45.30690383911133`) - Located south of the snapshot envelope.

*Note: These five points outside the current Géobase snapshot envelope are not automatically invalid. Spatial investigation of these points is deferred to Phase 3.*

---

## 7. Duplicate-Pattern Results
No rows have been removed or modified.
*   **Exact duplicates (all fields)**: `0`
*   **Same datetime**: `781` groups, `1571` rows, `790` excess rows (max group size `3`)
*   **Same geometry**: `4248` groups, `11434` rows, `7186` excess rows (max group size `65`)
*   **Same datetime + geometry**: `0` groups
*   **Same vehicle + datetime**: `0` groups
*   *Statement: Repeated coordinates or timestamps may represent nearby repairs, operational logging, or true duplicate records. The raw source alone does not establish the cause.*

---

## 8. Scientific Limitations
1.  **Interventions vs. Distress**: Records interventions (decisions), not raw physical deterioration.
2.  **Date gaps**: Only covers January through March. Coverage ends 2021-03-17.
3.  **WGS 84 custom entry**: Declared srs_id is 100000, organization is NONE, not described as formally declared EPSG:4326.
4.  **Spatial envelope exceptions**: Five 2021 repair points fall outside the axis-aligned bounding envelope of the current Géobase road-network snapshot (one point is east of the envelope and four points are south of it). This observation does not prove that the points fall outside Montréal or outside any borough. Administrative-boundary validity remains unassessed and spatial investigation is deferred.
5.  **No deduplication**: Duplicate spatial patterns are preserved.

---

## 9. Audit Decision
**PASS WITH MAJOR TEMPORAL AND SPATIAL LIMITATIONS — structurally valid, but available coverage ends in March, CRS metadata uses a custom WGS 84 entry with srs_id 100000 and organization NONE, and five points require later spatial investigation (which is deferred to Phase 3).**

---

## 10. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2021.gpkg` raw file remains completely unmodified.
