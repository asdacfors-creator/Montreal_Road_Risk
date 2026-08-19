# Data Audit Report — 2017 Mechanized Pothole Repairs

## 1. Audit Scope
This audit is strictly limited to the 2017 annual portion of the Montreal mechanized pothole repairs dataset. No other years (2016 or 2018–2025) are covered by this audit.

---

## 2. Integrity Evidence
*   **Filename**: `remplissage_niddepoule-_2017.csv`
*   **Size**: `8616313` bytes
*   **SHA-256 Checksum**: `af4f1fede65dee1d171b01e261929168621408526d2746a17875119c3f328069`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit
*   **Encoding**: UTF-8
*   **Delimiter**: `,` (Comma)
*   **Line-Ending Style**: CRLF (Windows)
*   **Header**: `Appareil,DateJour,DateHeure,Latitude,Longitude`
*   **Data Rows**: `205437` rows
*   **Malformed-Width Rows**: `0` rows
*   **Completely Blank Rows**: `0` rows
*   **Unexpected Extra Columns**: `0` columns
*   **Missing or Blank Values**: `0` missing values across all five columns.

---

## 4. Time-Format Change from 2016
*   **2016 Time Format**: `%I:%M:%S %p` (12-hour AM/PM format)
*   **2017 Time Format**: `%H:%M:%S` (24-hour time format)
*   *Audit Note: The time-of-day representation differs between annual files. The reusable auditor script was updated to dynamically detect and support both formats. In the 2017 file, 100% of the rows (205,437) are formatted as `%H:%M:%S`.*

---

## 5. Temporal Coverage and July–November Gap
*   **DateJour Parser Format**: `%Y-%m-%d`
*   **DateHeure Parser Format**: `%H:%M:%S`
*   **Invalid Dates (`DateJour`)**: `0`
*   **Invalid Times (`DateHeure`)**: `0`
*   **DateJour Range**: `2017-01-11` to `2017-12-21`
*   **DateHeure Time Range**: `00:00:01` to `23:59:59`
*   **Combined Timestamp Range**: `2017-01-11 16:32:47` to `2017-12-21 18:24:16`
*   **Unique Observed Dates**: `121` calendar dates
*   **Missing Calendar Dates in Range**: `224` dates
*   **Timezone**: Not declared (no timezone is assumed).

### Monthly Counts
*   `2017-01`: `30455`
*   `2017-02`: `30267`
*   `2017-03`: `40762`
*   `2017-04`: `53226`
*   `2017-05`: `45023`
*   `2017-06`: `2397`
*   `2017-07`: `0`
*   `2017-08`: `0`
*   `2017-09`: `0`
*   `2017-10`: `0`
*   `2017-11`: `0`
*   `2017-12`: `3307`

*Scientific Note: The complete absence of records from July through November (5 consecutive months) may represent an operational, reporting or source-coverage gap. The raw file alone does not establish the cause. The 2017 file cannot be described as temporally complete.*

---

## 6. Device Distribution (`Appareil`)
`Appareil` is a categorical operational metadata identifier representing the device/equipment performing the repair. It must not be treated as a physical road characteristic or used directly as a predictive feature.
*   **Unique Devices**: `12`
*   **Missingness & Validity**:
    *   Missing Appareil values: 0
    *   Nonnumeric or unexpected textual identifiers: 0
    *   Device 12 has the lowest observed frequency: 359 records
    *   The lower frequency is descriptive and does not make the identifier invalid
*   **Frequencies**:
    *   Device 3: `23690`
    *   Device 6: `23466`
    *   Device 7: `19741`
    *   Device 4: `18872`
    *   Device 8: `18731`
    *   Device 1: `18603`
    *   Device 9: `18319`
    *   Device 10: `17587`
    *   Device 5: `17144`
    *   Device 11: `15405`
    *   Device 2: `13520`
    *   Device 12: `359`

---

## 7. Coordinate Audit
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Latitude: `45.4152` to `45.7009`
    *   Longitude: `-73.93691` to `-73.48357`
*   **Montréal Sanity Box Check**: **PASS** (Zero points fall outside the broad Montréal-region sanity box of latitude 45.0 to 46.0 and longitude -75.0 to -72.0).
*   **Unique Coordinate Pairs**: `192494`
*   **Decimal Precision**:
    *   Latitude: 5 digits (`184958` values), 4 digits (`18472` values), 3 digits (`1828` values), 2 digits (`163` values), 1 digit (`16` values).
    *   Longitude: 5 digits (`184868` values), 4 digits (`18587` values), 3 digits (`1790` values), 2 digits (`176` values), 1 digit (`16` values).
    *   *Statement: Decimal-place precision describes how coordinate values are stored; it does not establish their real-world positional accuracy.*
*   *CRS Note: The coordinate values are numeric and fall within the broad Montréal-region sanity box. The CSV does not explicitly declare a Coordinate Reference System (CRS). The values appear to be longitude/latitude coordinates consistent with WGS 84, but the CRS must be confirmed from official metadata before Phase 3.*

---

## 8. Duplicate-Pattern Results
All duplicate records are preserved in raw format. Duplicate coordinate pairs and timestamps can represent legitimate nearby repairs and stationary GPS readings.

The duplicate analysis counts are detailed below:

| Duplicate Pattern Grouping | Repeated Groups | Rows in Groups | Excess Rows | Max Group Size |
| :--- | :--- | :--- | :--- | :--- |
| **Exact duplicates** (all 5 columns) | `14` | `28` | `14` | `2` |
| **Same datetime** (`DateJour`, `DateHeure`) | `2835` | `5684` | `2849` | `3` |
| **Same coordinates** (`Latitude`, `Longitude`) | `11946` | `24889` | `12943` | `9` |
| **Same datetime & coords** (`DateJour`, `DateHeure`, `Latitude`, `Longitude`) | `14` | `28` | `14` | `2` |
| **Same Appareil & datetime** (`Appareil`, `DateJour`, `DateHeure`) | `18` | `36` | `18` | `2` |
| **Same Appareil, datetime & coords** (`Appareil`, `DateJour`, `DateHeure`, `Latitude`, `Longitude`) | `14` | `28` | `14` | `2` |

*Interpretation: Repeated observations may represent legitimate nearby repairs, repeated GPS positions, repeated timestamps or true duplicate records. The raw data does not establish which explanation applies to every repeated observation. No rows are removed during Phase 2.*

---

## 9. Scientific Limitations
1.  **Interventions vs. Distress**: The file records repair interventions (operational decisions), not every physical pavement distress that occurred on the road.
2.  **Central Service Exclusivity**: Excludes manual repairs and borough-level maintenance operations.
3.  **No Complete Pavement Failure Measure**: Recorded repairs are not a complete measure of pavement deterioration; operational choices and budget availability affect where and when repairs are recorded.
4.  **Spatial Matching Key Absence**: There is no road-segment identifier (such as `ID_TRC`) in the schema. Later linkage to Géobase will require a separately validated spatial matching procedure in Phase 3.
5.  **Time Format Inconsistency**: The time format differs between the 2016 (`%I:%M:%S %p`) and 2017 (`%H:%M:%S`) annual files.
6.  **Temporal Coverage Gap**: July through November has no observations, making 2017 temporally incomplete.
7.  **CRS & Timezone Lack**: Coordinate Reference System and timezone are not explicitly declared.
8.  **No Causal Claims**: No causal conclusions should be drawn from this dataset.
9.  **No Deduplication**: No deduplication is performed during Phase 2.

---

## 10. Audit Decision
**PASS WITH LIMITATIONS — suitable as the available 2017 portion of the recorded central mechanized repair-event source**
*(This does not approve the file as complete pothole-incidence data).*

---

## 11. Raw-Integrity Confirmation
*   **Confirmed**: Both `remplissageniddepoule-2016.csv` and `remplissage_niddepoule-_2017.csv` raw files remain completely unmodified.
