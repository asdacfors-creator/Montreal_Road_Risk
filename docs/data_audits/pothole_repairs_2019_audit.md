# Data Audit Report — 2019 Mechanized Pothole Repairs

## 1. Audit Scope

This audit is strictly limited to the 2019 annual portion of the Montreal mechanized pothole repairs dataset. No other years (2016–2018 or 2020–2025) are covered by this audit.

---

## 2. Integrity Evidence

*   **Filename**: `remplissage_niddepoule_2019.csv`
*   **Size**: `9566853` bytes
*   **SHA-256 Checksum**: `68ecb956608b3230e939943aadd96a216b03ca16b4138902e7a52e5ce1e4e3db`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit

*   **Encoding**: UTF-8
*   **Delimiter**: `,` (Comma)
*   **Line-Ending Style**: CRLF (Windows)
*   **Header**: `Appareil,DateJour,DateHeure,Latitude,Longitude`
*   **Data Rows**: `174856` rows
*   **Malformed-Width Rows**: `0` rows
*   **Completely Blank Rows**: `0` rows
*   **Unexpected Extra Columns**: `0` columns
*   **Missing or Blank Values**: `0` missing values across all five columns.

---

## 4. Time-Format Result

*   **2019 Time Format**: `%H:%M:%S` (24-hour time format)
*   *Audit Note: 100% of the rows (174,856) are formatted as `%H:%M:%S`.*

---

## 5. Temporal Coverage and June–November Gap

*   **DateJour Parser Format**: `%Y-%m-%d`
*   **DateHeure Parser Format**: `%H:%M:%S`
*   **Invalid Dates (`DateJour`)**: `0`
*   **Invalid Times (`DateHeure`)**: `0`
*   **DateJour Range**: `2019-01-15` to `2019-12-16`
*   **DateHeure Time Range**: `00:00:01` to `23:59:59`
*   **Combined Timestamp Range**: `2019-01-15 03:01:15` to `2019-12-16 14:16:07`
*   **Unique Observed Dates**: `102` calendar dates
*   **Missing Calendar Dates in Range**: `234` dates
*   **Timezone**: Not declared (no timezone is assumed).

### Monthly Counts

*   `2019-01`: `6995`
*   `2019-02`: `48595`
*   `2019-03`: `43248`
*   `2019-04`: `31316`
*   `2019-05`: `20262`
*   `2019-06` to `2019-10`: `0` (June, July, August, September, and October have zero records)
*   `2019-11`: `9453`
*   `2019-12`: `14987`

*Scientific Note: The complete absence of records from June through October (5 consecutive months) may represent an operational, reporting or source-coverage gap. The raw file alone does not establish the cause. The 2019 file cannot be described as temporally complete.*

---

## 6. Device Distribution and Alphanumeric Evolution

`Appareil` is treated as a non-empty categorical string representing the device/equipment performing the repair. It must not be converted to a numeric measurement, and its lower frequencies must be treated descriptively rather than as invalidity.
*   **Unique Devices**: `17`
*   **Missingness & Validity**:
    *   Missing Appareil values: 0
    *   Nonnumeric or unexpected textual identifiers: 0
    *   Device `NP-119` has the lowest observed frequency among NP-hyphen-number patterns: 5 records
    *   Device `G7C020FD0F0C` represents an alternative alphanumeric pattern: 17 records
    *   These low frequencies are descriptive and do not make the identifiers invalid.
*   **Device Pattern Counts**:
    *   `numeric_only`: `0`
    *   `np_hyphen_number`: `174839` values (16 devices)
    *   `other_non_empty`: `17` values (1 device: `G7C020FD0F0C`)
    *   `blank`: `0`
*   **Frequencies**:
    *   `NP-117`: `16164`
    *   `NP-118`: `15869`
    *   `NP-109`: `15543`
    *   `NP-113`: `14987`
    *   `NP-110`: `14639`
    *   `NP-114`: `14547`
    *   `NP-111`: `14374`
    *   `NP-112`: `14201`
    *   `NP-107`: `12893`
    *   `NP-115`: `12630`
    *   `NP-106`: `11224`
    *   `NP-116`: `9055`
    *   `NP-108`: `6974`
    *   `NP-100`: `1154`
    *   `NP-101`: `580`
    *   `G7C020FD0F0C`: `17`
    *   `NP-119`: `5`

---

## 7. Coordinate Audit and Precision Shifts
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Latitude: `45.41554160625` to `45.6996346`
    *   Longitude: `-73.9170074` to `-73.4844177971`
*   **Montréal Sanity Box Check**: **PASS** (Zero points fall outside the broad Montréal-region sanity box of latitude 45.0 to 46.0 and longitude -75.0 to -72.0).
*   **Unique Coordinate Pairs**: `119647`
*   **Decimal Precision Distributions**:
    *   Latitude: 13 digits (`13361`), 12 digits (`20860`), 11 digits (`11398`), 10 digits (`11402`), 9 digits (`10494`), 8 digits (`39935`), 7 digits (`60846`), 6 digits (`5948`), 5 digits (`547`), 4 digits (`65`).
    *   Longitude: 13 digits (`13584`), 12 digits (`21647`), 11 digits (`13385`), 10 digits (`11166`), 9 digits (`11093`), 8 digits (`40048`), 7 digits (`56898`), 6 digits (`6211`), 5 digits (`770`), 4 digits (`53`), 3 digits (`1`).
    *   *Audit Note: The textual storage-precision distribution shifts upward in 2019. Latitude values contain 4–13 digits after the decimal point and longitude values contain 3–13 digits. Many 2019 values contain 7–13 digits, whereas most—but not all—values in the 2016–2018 CSV files contain five digits. No statistical significance test was performed. This storage-format difference does not establish improved positional accuracy. Decimal-place precision describes how coordinate values are stored; it does not establish their real-world positional accuracy.*
*   *CRS Note: The coordinate values are numeric and fall within the broad Montréal-region sanity box. The CSV does not explicitly declare a Coordinate Reference System (CRS). The values appear to be longitude/latitude coordinates consistent with WGS 84, but the CRS must be confirmed from official metadata before Phase 3.*

---

## 8. Duplicate-Pattern Results and 2019 Anomaly
All duplicate records are preserved in raw format. Duplicate coordinate pairs and timestamps can represent legitimate nearby repairs and stationary GPS readings.

### A. Duplicate-Pattern Metric Grouping
The duplicate analysis counts are detailed below:

| Duplicate Pattern Grouping | Repeated Groups | Rows in Groups | Excess Rows | Max Group Size |
| :--- | :--- | :--- | :--- | :--- |
| **Exact full-row duplicates** (all 5 columns) | `31858` | `83280` | `51422` | `5` |
| **Same DateJour and DateHeure** | `32826` | `86116` | `53290` | `9` |
| **Same Latitude and Longitude** | `32332` | `87541` | `55209` | `69` |
| **Same datetime and coordinates** | `31858` | `83280` | `51422` | `5` |
| **Same Appareil and datetime** | `31858` | `83280` | `51422` | `5` |
| **Same Appareil, datetime and coordinates** | `31858` | `83280` | `51422` | `5` |

### B. Detailed 2019 Exact-Duplicate Anomaly Statistics
To formally record this anomaly, we distinguish:
1. **Rows participating in exact-duplicate groups**: `83280` rows (`47.6278%` of all `174856` rows).
2. **Excess rows beyond the first copy in each group**: `51422` rows (`29.4082%` of all rows).
*Note: Both percentages are valid metrics; the first measures the total volume of rows involved in any repetition, while the second measures the number of redundant records that could potentially be pruned.*

*   **Unique full rows**: `123434`
*   **Exact-duplicate groups**: `31858`
*   **Exact-duplicate excess rows**: `51422`
*   **Adjacent identical excess occurrences**: `51152`
*   **Percentage of exact excess occurring adjacently**: `99.4749%`
*   **Maximum exact group size**: `5`

#### Repeated-Group Multiplicity
*   Appearing twice: `19440` groups
*   Appearing three times: `7151` groups
*   Appearing four times: `3388` groups
*   Appearing five times: `1879` groups

#### Exact-Duplicate Excess by Month
*   `2019-01`: `2326`
*   `2019-02`: `16548`
*   `2019-03`: `13207`
*   `2019-04`: `9780`
*   `2019-05`: `6780`
*   `2019-06` to `2019-10`: `0`
*   `2019-11`: `2728`
*   `2019-12`: `53`

### C. Interpretation
“The 2019 file contains a large observed exact-duplicate anomaly. Most excess identical occurrences are adjacent in source-file order. This may reflect export, logging, operational or genuine repeated-event behaviour, but the raw file alone does not establish the cause. Raw records remain unchanged. A formal duplicate-resolution policy is required before event aggregation, target construction or modelling.”

*Note: Repeated observations may represent legitimate nearby repairs, repeated GPS positions, repeated timestamps or true duplicate records. The raw data does not establish which explanation applies to each observation. No rows are removed during Phase 2.*

---

## 9. Scientific Limitations
1.  **Interventions vs. Distress**: The file records repair interventions (operational decisions), not every physical pavement distress that occurred on the road.
2.  **Central Service Exclusivity**: Excludes manual repairs and borough-level maintenance operations.
3.  **No Complete Pavement Failure Measure**: Recorded repairs are not a complete measure of pavement deterioration; operational choices and budget availability affect where and when repairs are recorded.
4.  **Spatial Matching Key Absence**: There is no road-segment identifier (such as `ID_TRC`) in the schema. Later linkage to Géobase will require a separately validated spatial matching procedure in Phase 3.
5.  **Temporal Coverage Gap**: June through October has no observations, making 2019 temporally incomplete.
6.  **CRS & Timezone Lack**: Coordinate Reference System and timezone are not explicitly declared.
7.  **GPS Positional Accuracy**: GPS positional accuracy is not established by decimal precision.
8.  **No Causal Claims**: No causal conclusions should be drawn from this dataset.
9.  **No Deduplication**: No deduplication is performed during Phase 2.

---

## 10. Audit Decision
**PASS WITH MAJOR LIMITATIONS — the file is structurally valid and ingestible, but the exact-duplicate anomaly and temporal gaps must be resolved before target construction.**
*(This does not approve the file as complete pothole-incidence data).*

---

## 11. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2019.csv` raw file remains completely unmodified.
