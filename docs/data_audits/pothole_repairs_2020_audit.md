# Data Audit Report — 2020 Mechanized Pothole Repairs

## 1. Audit Scope

This audit is strictly limited to the 2020 annual portion of the Montreal mechanized pothole repairs dataset. No other years (2016–2019 or 2021–2025) are covered by this audit.

---

## 2. Integrity Evidence

*   **Filename**: `remplissage_niddepoule_2020.csv`
*   **Size**: `5104739` bytes
*   **SHA-256 Checksum**: `8417021f629007af4d873e1d5faca5924a6d297c35dfc63adf3abe9698ef1703`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit

*   **Encoding**: UTF-8
*   **Delimiter**: `,` (Comma)
*   **Line-Ending Style**: CRLF (Windows)
*   **Header**: `Appareil,DateJour,DateHeure,Latitude,Longitude`
*   **Data Rows**: `81354` rows
*   **Malformed-Width Rows**: `0` rows
*   **Completely Blank Rows**: `0` rows
*   **Unexpected Extra Columns**: `0` columns
*   **Missing or Blank Values**: `0` missing values across all five columns.

---

## 4. Time-Format Result

*   **2020 Time Format**: `%H:%M:%S` (24-hour time format)
*   *Audit Note: 100% of the rows (81,354) are formatted as `%H:%M:%S`.*

---

## 5. Temporal Coverage and Incomplete Year Limitation

*   **DateJour Parser Format**: `%Y-%m-%d`
*   **DateHeure Parser Format**: `%H:%M:%S`
*   **Invalid Dates (`DateJour`)**: `0`
*   **Invalid Times (`DateHeure`)**: `0`
*   **DateJour Range**: `2020-01-14` to `2020-03-20`
*   **DateHeure Time Range**: `00:00:00` to `23:59:59`
*   **Combined Timestamp Range**: `2020-01-14 07:13:12` to `2020-03-20 01:23:45`
*   **Unique Observed Dates**: `34` calendar dates
*   **Missing Calendar Dates in Range**: `33` dates
*   **Timezone**: Not declared (no timezone is assumed).

### Monthly Counts

*   `2020-01`: `22443`
*   `2020-02`: `18808`
*   `2020-03`: `40103`
*   `2020-04` to `2020-12`: `0` (April through December have zero records)

*Scientific Statement: The available 2020 source contains records only from 14 January through 20 March. The raw file alone does not establish why later 2020 observations are absent. No operational shutdown, reporting failure, or pandemic impact is assumed without official source evidence. The 2020 dataset cannot be treated as a complete calendar year.*

---

## 6. Device Distribution

`Appareil` is treated as a non-empty categorical string representing the device/equipment performing the repair. It must not be converted to a numeric measurement, and its lower frequencies must be treated descriptively rather than as invalidity.
*   **Unique Devices**: `14`
*   **Missingness & Validity**:
    *   Missing Appareil values: 0
    *   Nonnumeric or unexpected textual identifiers: 0
    *   All 14 identifiers match the `NP-hyphen-number` pattern.
*   **Frequencies**:
    *   `NP-111`: `8103`
    *   `NP-107`: `7829`
    *   `NP-112`: `7667`
    *   `NP-113`: `7540`
    *   `NP-110`: `7283`
    *   `NP-106`: `6141`
    *   `NP-117`: `6133`
    *   `NP-109`: `6069`
    *   `NP-115`: `5846`
    *   `NP-114`: `5465`
    *   `NP-116`: `5104`
    *   `NP-108`: `3460`
    *   `NP-118`: `3403`
    *   `NP-101`: `1311`

---

## 7. Coordinate Audit and Precision
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Latitude: `45.4159088134766` to `45.701042175293`
    *   Longitude: `-73.9119338989258` to `-73.4833908081055`
*   **Montréal Sanity Box Check**: **PASS** (Zero points fall outside the broad Montréal-region sanity box of latitude 45.0 to 46.0 and longitude -75.0 to -72.0).
*   **Unique Coordinate Pairs**: `69838`
*   **Decimal Precision Distributions**:
    *   Latitude: 13 digits (`72454`), 12 digits (`8219`), 11 digits (`358`), 10 digits (`179`), 9 digits (`50`), 8 digits (`49`), 7 digits (`34`), 6 digits (`2`), 5 digits (`8`), 4 digits (`1`).
    *   Longitude: 13 digits (`73634`), 12 digits (`6368`), 11 digits (`689`), 10 digits (`305`), 9 digits (`186`), 8 digits (`88`), 7 digits (`51`), 6 digits (`12`), 5 digits (`21`).
    *   *Statement: Decimal-place precision describes the source storage representation and does not establish real-world positional accuracy.*
*   *CRS Note: The coordinate values are numeric and fall within the broad Montréal-region sanity box. The CSV does not explicitly declare a Coordinate Reference System (CRS). The values appear to be longitude/latitude coordinates consistent with WGS 84, but the CRS has not been formally verified.*

---

## 8. Duplicate-Pattern Results and 2019 Anomaly Comparison
All duplicate records are preserved in raw format. Duplicate coordinate pairs and timestamps can represent legitimate nearby repairs and stationary GPS readings.

### A. Duplicate-Pattern Metric Grouping
The duplicate analysis counts are detailed below:

| Duplicate Pattern Grouping | Repeated Groups | Rows in Groups | Excess Rows | Max Group Size |
| :--- | :--- | :--- | :--- | :--- |
| **Exact full-row duplicates** (all 5 columns) | `320` | `663` | `343` | `3` |
| **Same DateJour and DateHeure** | `2535` | `5163` | `2628` | `4` |
| **Same Latitude and Longitude** | `7373` | `18889` | `11516` | `53` |
| **Same datetime and coordinates** | `320` | `663` | `343` | `3` |
| **Same Appareil and datetime** | `320` | `663` | `343` | `3` |
| **Same Appareil, datetime and coordinates** | `320` | `663` | `343` | `3` |

### B. Detailed 2020 Exact-Duplicate Statistics
*   **Unique full rows**: `81011`
*   **Rows participating in exact-duplicate groups**: `663` (`0.8150%` of all `81354` rows).
*   **Exact excess rows**: `343` (`0.4216%` excess rate).
*   **Adjacent identical excess occurrences**: `336` (`97.9592%` of excess occurrences are adjacent in file order).
*   **Maximum exact group size**: `3`

#### Repeated-Group Multiplicity
*   Appearing twice: `297` groups
*   Appearing three times: `23` groups

#### Exact-Duplicate Excess by Month
*   `2020-01`: `99`
*   `2020-02`: `45`
*   `2020-03`: `199`

### C. 2019 Anomaly Comparison
*   *Statement: The 2020 exact-duplicate rate is much lower than the large observed 2019 anomaly. This difference does not explain or resolve the 2019 anomaly. Limitation L2.1 remains open and no duplicate-removal policy is applied in Phase 2.*

---

## 9. Scientific Limitations
1.  **Interventions vs. Distress**: The file records repair interventions (operational decisions), not every physical pavement distress that occurred on the road.
2.  **Central Service Exclusivity**: Excludes manual repairs and borough-level maintenance operations.
3.  **No Complete Pavement Failure Measure**: Recorded repairs are not a complete measure of pavement deterioration; operational choices and budget availability affect where and when repairs are recorded.
4.  **Spatial Matching Key Absence**: There is no road-segment identifier (such as `ID_TRC`) in the schema. Later linkage to Géobase will require a separately validated spatial matching procedure in Phase 3.
5.  **Major Temporal Limitation**: June through December has zero records, and the entire year consists of only January–March observations.
6.  **CRS & Timezone Lack**: Coordinate Reference System and timezone are not explicitly declared.
7.  **GPS Positional Accuracy**: GPS positional accuracy is not established by decimal precision.
8.  **No Causal Claims**: No causal conclusions should be drawn from this dataset.
9.  **No Deduplication**: No deduplication is performed during Phase 2.

---

## 10. Audit Decision
**PASS WITH MAJOR TEMPORAL LIMITATIONS — the file is structurally valid and ingestible as the available January–March 2020 repair-event source, but it does not provide complete 2020 coverage.**
*(This does not approve the file as complete pothole-incidence data).*

---

## 11. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2020.csv` raw file remains completely unmodified.
