# Data Audit Report — 2016 Mechanized Pothole Repairs

## 1. Audit Scope
This audit is strictly limited to the December 2016 portion of the Montreal mechanized pothole repairs dataset. No other years (2017–2025) are covered by this audit.

---

## 2. Integrity Evidence
*   **Filename**: `remplissageniddepoule-2016.csv`
*   **Size**: `612719` bytes
*   **SHA-256 Checksum**: `b49386f895285ac50f8ec6136723d9c9a7e78b9a762ef4330977833dd09fb8ca`
*   **Source Verification**: Matches the expected baseline size and checksum exactly.

---

## 3. Structural Results
*   **Encoding**: UTF-8
*   **Delimiter**: `,` (Comma)
*   **Line-Ending Style**: CRLF (Windows)
*   **Header**: `Appareil,DateJour,DateHeure,Latitude,Longitude`
*   **Data Rows**: `13876` rows
*   **Malformed-Width Rows**: `0` rows
*   **Completely Blank Rows**: `0` rows
*   **Unexpected Extra Columns**: `0` columns

### Column-Level Completeness & Missingness
All five columns are 100% complete with no nulls, NaNs, or empty blank strings:

| Column Name | Data Type | Null Count | Blank Count | Description |
| :--- | :--- | :--- | :--- | :--- |
| `Appareil` | int64 | 0 | 0 | Recorded equipment/device identifier (categorical) |
| `DateJour` | object/str | 0 | 0 | Recorded calendar date of the repair |
| `DateHeure` | object/str | 0 | 0 | Time-of-day of the repair (12-hour AM/PM format) |
| `Latitude` | float64 | 0 | 0 | Geographic latitude coordinate |
| `Longitude` | float64 | 0 | 0 | Geographic longitude coordinate |

---

## 4. Temporal Results
*   **DateJour Parser Format**: `%Y-%m-%d`
*   **DateHeure Parser Format**: `%I:%M:%S %p`
*   **Invalid Dates (`DateJour`)**: `0`
*   **Invalid Times (`DateHeure`)**: `0`
*   **DateJour Range**: `2016-12-07` to `2016-12-24`
*   **DateHeure Time Range**: `00:00:01` to `23:59:33` (time-of-day only)
*   **Combined Timestamp Range**: `2016-12-07 05:10:08` to `2016-12-24 07:06:06`
*   **Unique Observed Dates**: `11` dates
*   **Timezone**: Not declared (no timezone member is present in the raw data; no timezone is assumed).

### Record Count per Observed Calendar Date
*   `2016-12-07`: `1020`
*   `2016-12-08`: `1464`
*   `2016-12-09`: `1344`
*   `2016-12-10`: `1586`
*   `2016-12-11`: `1862`
*   `2016-12-12`: `166`
*   `2016-12-20`: `1236`
*   `2016-12-21`: `1546`
*   `2016-12-22`: `1793`
*   `2016-12-23`: `1620`
*   `2016-12-24`: `239`

### Missing Calendar Dates in Range
*   `2016-12-13` to `2016-12-19` (7 consecutive calendar days have zero records).

*Scientific Note: This file represents only a partial December 2016 period of observations (spanning December 7 to December 24), not a complete calendar year of records.*

---

## 5. Device Distribution (`Appareil`)
`Appareil` is treated as a categorical metadata identifier representing the device/equipment performing the repair. No frequencies should be interpreted as direct road deterioration indicators.
*   **Unique Devices**: `11`
*   **Missing Values**: `0`
*   **Non-Integer or Textual Values**: `0`
*   **Device Frequencies**:
    *   Device 6: `1981`
    *   Device 3: `1824`
    *   Device 4: `1635`
    *   Device 2: `1461`
    *   Device 5: `1406`
    *   Device 1: `1397`
    *   Device 9: `1251`
    *   Device 7: `1178`
    *   Device 10: `1031`
    *   Device 8: `711`
    *   Device 11: `1`
*   **Rare Identifiers (appear only once)**: Device `11` (appears exactly `1` time).

---

## 6. Coordinate-Quality Results
*   **Numeric Parsing Failures**: `0`
*   **Missing Coordinates**: `0`
*   **Zero Coordinates**: `0`
*   **Coordinates Range**:
    *   Latitude: `45.42103` to `45.69853`
    *   Longitude: `-73.76707` to `-73.48462`
*   **Sanity Box Check**: **PASS** (Zero points fall outside the broad Montréal-region sanity box of latitude 45.0 to 46.0 and longitude -75.0 to -72.0).
*   **Unique Coordinate Pairs**: `13166`
*   **Decimal Precision**:
    *   Latitude: 5 digits (`12442` values), 4 digits (`1306` values), 3 digits (`120` values), 2 digits (`8` values).
    *   Longitude: 5 digits (`12517` values), 4 digits (`1244` values), 3 digits (`101` values), 2 digits (`12` values), 1 digit (`2` values).
    *   *Statement: Decimal-place precision describes how coordinate values are stored; it does not establish their real-world positional accuracy.*
*   *CRS Note: The coordinate values are numeric and fall within the broad Montréal-region sanity box. The CSV does not explicitly declare a Coordinate Reference System (CRS). The values appear to be longitude/latitude coordinates consistent with WGS 84, but the CRS must be confirmed from official metadata before Phase 3.*

---

## 7. Duplicate-Pattern Audit
No rows have been removed or modified. All duplicates are preserved because repeated observations may represent legitimate nearby repairs, repeated GPS positions, repeated timestamps, or true duplicate records.

The counts of duplicate patterns across separate subsets of columns are detailed below:

| Duplicate Pattern Grouping | Repeated Groups | Rows in Groups | Excess Rows | Max Group Size |
| :--- | :--- | :--- | :--- | :--- |
| **Exact duplicates** (all 5 columns) | `166` | `341` | `175` | `5` |
| **Same datetime** (`DateJour`, `DateHeure`) | `297` | `608` | `311` | `6` |
| **Same coordinates** (`Latitude`, `Longitude`) | `647` | `1357` | `710` | `6` |
| **Same datetime & coords** (`DateJour`, `DateHeure`, `Latitude`, `Longitude`) | `166` | `341` | `175` | `5` |
| **Same device & datetime** (`Appareil`, `DateJour`, `DateHeure`) | `185` | `380` | `195` | `5` |
| **Same device, datetime & coords** (`Appareil`, `DateJour`, `DateHeure`, `Latitude`, `Longitude`) | `166` | `341` | `175` | `5` |

*Interpretation: Repeated observations may represent legitimate nearby repairs, repeated GPS positions, repeated timestamps, or true duplicate records. The raw data does not provide enough evidence to classify every repeated observation. Therefore, no records are removed during Phase 2.*

---

## 8. Scientific Suitability and Limitations
1.  **Intervention vs. Distress**: The file records repair interventions (operational decisions), not every physical pavement distress that occurred on the road.
2.  **Central Service Exclusivity**: The dataset only captures mechanized repair work performed by the central service. All manual repairs and borough-level maintenance operations are excluded.
3.  **No Complete Pavement Failure Measure**: Recorded repairs are not a complete measure of pavement deterioration; operational choices and budget availability affect where and when repairs are recorded.
4.  **Network Bias**: Repair work is heavily concentrated on the major arterial network.
5.  **GPS Accuracy**: GPS location accuracy can vary from a few meters to several tens of meters.
6.  **Nearby Repairs**: Multiple nearby repairs share coordinates or timestamps due to stationary work.
7.  **Temporal Limits**: The dataset spans only a partial period (December 7 to 24, 2016) and is not a complete calendar year.
8.  **Link Key Absence**: There is no road-segment identifier (such as `ID_TRC`) in the schema. Later linkage to Géobase will require a separately validated spatial matching procedure in Phase 3.
9.  **Predictive Feature Warning**: `Appareil` is operational metadata and must not automatically be used as a predictive feature in modeling.
10. **Target Construction Lock**: These repair records may define future target events, but target construction must remain locked until all annual files and temporal coverage have been audited.
11. **No Causal Claim**: No causal claim can be made from this dataset.

---

## 9. Audit Decision
**PASS WITH LIMITATIONS — suitable as the December 2016 portion of the recorded central mechanized repair-event source**

---

## 10. Next Permitted Action
Continue with manual download and basic content audit of the next annual resource in the sequence: **2017 Mechanized Pothole Repairs** (`remplissage_niddepoule-_2017.csv`).
