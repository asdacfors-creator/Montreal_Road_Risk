# Data Audit Report — 2018 Mechanized Pothole Repairs

## 1. Audit Scope
This audit is strictly limited to the 2018 annual portion of the Montreal mechanized pothole repairs dataset. No other years (2016, 2017, or 2019–2025) are covered by this audit.

---

## 2. Integrity Evidence
*   **Filename**: `remplissage_niddepoule_2018.csv`
*   **Size**: `8344798` bytes
*   **SHA-256 Checksum**: `ef988b45eec79427eecbcca71ae91dcdbc50cf517f691a6edadc3f8c1acbc505`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Audit
*   **Encoding**: UTF-8
*   **Delimiter**: `,` (Comma)
*   **Line-Ending Style**: CRLF (Windows)
*   **Header**: `Appareil,DateJour,DateHeure,Latitude,Longitude`
*   **Data Rows**: `199019` rows
*   **Malformed-Width Rows**: `0` rows
*   **Completely Blank Rows**: `0` rows
*   **Unexpected Extra Columns**: `0` columns
*   **Missing or Blank Values**: `0` missing values across all five columns.

---

## 4. Time-Format Result
*   **2018 Time Format**: `%H:%M:%S` (24-hour time format)
*   *Audit Note: 100% of the rows (199,019) are formatted as `%H:%M:%S`.*

---

## 5. Temporal Coverage and June–November Gap
*   **DateJour Parser Format**: `%Y-%m-%d`
*   **DateHeure Parser Format**: `%H:%M:%S`
*   **Invalid Dates (`DateJour`)**: `0`
*   **Invalid Times (`DateHeure`)**: `0`
*   **DateJour Range**: `2018-01-18` to `2018-12-21`
*   **DateHeure Time Range**: `00:00:00` to `23:59:59`
*   **Combined Timestamp Range**: `2018-01-18 11:04:19` to `2018-12-21 05:59:44`
*   **Unique Observed Dates**: `77` calendar dates
*   **Missing Calendar Dates in Range**: `261` dates
*   **Timezone**: Not declared (no timezone is assumed).

### Monthly Counts
*   `2018-01`: `28634`
*   `2018-02`: `24530`
*   `2018-03`: `55521`
*   `2018-04`: `50274`
*   `2018-05`: `18125`
*   `2018-06` to `2018-11`: `0` (June, July, August, September, October, and November have zero records)
*   `2018-12`: `21935`

*Scientific Note: The complete absence of records from June through November (6 consecutive months) may represent an operational, reporting or source-coverage gap. The raw file alone does not establish the cause. The 2018 file cannot be described as temporally complete.*

---

## 6. Device Distribution (`Appareil`)
`Appareil` is a categorical operational metadata identifier representing the device/equipment performing the repair. It must not be treated as a physical road characteristic or used directly as a predictive feature.
*   **Unique Devices**: `13`
*   **Missingness & Validity**:
    *   Missing Appareil values: 0
    *   Nonnumeric or unexpected textual identifiers: 0
    *   Device 11 has the lowest observed frequency: 2041 records
    *   The lower frequency is descriptive and does not make the identifier invalid
*   **Frequencies**:
    *   Device 6: `23507`
    *   Device 5: `22566`
    *   Device 3: `21779`
    *   Device 8: `21350`
    *   Device 2: `20620`
    *   Device 9: `17370`
    *   Device 7: `15093`
    *   Device 1: `14882`
    *   Device 10: `13265`
    *   Device 12: `12134`
    *   Device 4: `11476`
    *   Device 13: `2936`
    *   Device 11: `2041`

---

## 7. Coordinate Audit
*   **Parsing Failures / Missing / Zeroes**: `0`
*   **Coordinates Range**:
    *   Latitude: `45.4152` to `45.69962`
    *   Longitude: `-73.90339` to `-73.48618`
*   **Montréal Sanity Box Check**: **PASS** (Zero points fall outside the broad Montréal-region sanity box of latitude 45.0 to 46.0 and longitude -75.0 to -72.0).
*   **Unique Coordinate Pairs**: `184872`
*   **Decimal Precision**:
    *   Latitude: 5 digits (`179175` values), 4 digits (`17802` values), 3 digits (`1859` values), 2 digits (`173` values), 1 digit (`10` values).
    *   Longitude: 5 digits (`178982` values), 4 digits (`17991` values), 3 digits (`1817` values), 2 digits (`196` values), 1 digit (`33` values).
    *   *Statement: Decimal-place precision describes how coordinate values are stored; it does not establish their real-world positional accuracy.*
*   *CRS Note: The coordinate values are numeric and fall within the broad Montréal-region sanity box. The CSV does not explicitly declare a Coordinate Reference System (CRS). The values appear to be longitude/latitude coordinates consistent with WGS 84, but the CRS must be confirmed from official metadata before Phase 3.*

---

## 8. Duplicate-Pattern Results
All duplicate records are preserved in raw format. Duplicate coordinate pairs and timestamps can represent legitimate nearby repairs and stationary GPS readings.

The duplicate analysis counts are detailed below:

| Duplicate Pattern Grouping | Repeated Groups | Rows in Groups | Excess Rows | Max Group Size |
| :--- | :--- | :--- | :--- | :--- |
| **Exact full-row duplicates** (all 5 columns) | `1020` | `2069` | `1049` | `5` |
| **Same DateJour and DateHeure** | `4539` | `9197` | `4658` | `5` |
| **Same Latitude and Longitude** | `12817` | `26964` | `14147` | `13` |
| **Same datetime and coordinates** | `1020` | `2069` | `1049` | `5` |
| **Same Appareil and datetime** | `1119` | `2281` | `1162` | `5` |
| **Same Appareil, datetime and coordinates** | `1020` | `2069` | `1049` | `5` |

*Comparison Warning: The 2018 dataset shows a large observed increase in exact duplicate patterns compared to 2017 (1020 groups vs 14 groups). We do not infer the cause (it could be GPS repeating records, equipment telemetry issues, or multiple fast interventions) and we do not remove them.*

*Interpretation: Repeated observations may represent legitimate nearby repairs, repeated GPS positions, repeated timestamps or true duplicate records. The raw data does not establish which explanation applies to each observation. No rows are removed during Phase 2.*

---

## 9. Scientific Limitations
1.  **Interventions vs. Distress**: The file records repair interventions (operational decisions), not every physical pavement distress that occurred on the road.
2.  **Central Service Exclusivity**: Excludes manual repairs and borough-level maintenance operations.
3.  **No Complete Pavement Failure Measure**: Recorded repairs are not a complete measure of pavement deterioration; operational choices and budget availability affect where and when repairs are recorded.
4.  **Spatial Matching Key Absence**: There is no road-segment identifier (such as `ID_TRC`) in the schema. Later linkage to Géobase will require a separately validated spatial matching procedure in Phase 3.
5.  **Temporal Coverage Gap**: June through November has no observations, making 2018 temporally incomplete.
6.  **CRS & Timezone Lack**: Coordinate Reference System and timezone are not explicitly declared.
7.  **GPS Positional Accuracy**: GPS positional accuracy is not established by decimal precision.
8.  **No Causal Claims**: No causal conclusions should be drawn from this dataset.
9.  **No Deduplication**: No deduplication is performed during Phase 2.

---

## 10. Audit Decision
**PASS WITH LIMITATIONS — suitable as the available 2018 portion of the recorded central mechanized repair-event source**
*(This does not approve the file as complete pothole-incidence data).*

---

## 11. Raw-Integrity Confirmation
*   **Confirmed**: The `remplissage_niddepoule_2018.csv` raw file remains completely unmodified.
