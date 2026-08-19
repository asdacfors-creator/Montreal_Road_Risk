# Data Audit Report — Montreal Géobase Routière

## 1. Source and Purpose
*   **Dataset ID**: `montreal_geobase`
*   **Official Name**: Géobase — réseau routier
*   **Source URL**: [https://donnees.montreal.ca/dataset/geobase](https://donnees.montreal.ca/dataset/geobase)
*   **License**: Creative Commons Attribution 4.0 International (CC-BY 4.0)
*   **Purpose**: To serve as the canonical road-network base map of Montreal's road segments, providing geometries, segment identifiers (`ID_TRC`), road names (`ODONYME`), and road classes (`CLASSE`).

---

## 2. File Integrity
*   **Filename**: `geobase.json`
*   **Size**: `43145805` bytes
*   **SHA-256 Checksum**: `fbb1a46f4fd64ae156a778a3bfe3ef176583967607de33762d26b07f53572c25`
*   **Validation Status**: Valid JSON (Top-level type: `FeatureCollection`, Name: `geobase_mtl`).

---

## 3. Schema Summary
The dataset contains `47983` features and 18 attributes:

| Column Name | Data Type | Null Count | Description |
| :--- | :--- | :--- | :--- |
| `ID_TRC` | int32 | 0 | Unique segment identifier |
| `DEB_GCH` | int32 | 0 | Left-side starting address number |
| `FIN_GCH` | int32 | 0 | Left-side ending address number |
| ARR_GCH | object/str | 0 | Left-side borough name abbreviation |
| `SENS_CIR` | int32 | 0 | Circulation direction code |
| `CLASSE` | int32 | 0 | Functional road class (0–9) |
| `LIE_VOIE` | object/str | 41749 | Road link type |
| `TYP_VOIE` | object/str | 30 | Road type description |
| `DIR_VOIE` | object/str | 43462 | Road direction description |
| `NOM_VOIE` | object/str | 0 | Street name |
| `DEB_DRT` | int32 | 0 | Right-side starting address number |
| `FIN_DRT` | int32 | 0 | Right-side ending address number |
| ARR_DRT | object/str | 0 | Right-side borough name abbreviation |
| `LIM_GCH` | object/str | 0 | Left boundary |
| `LIM_DRT` | object/str | 0 | Right boundary |
| `POSITION` | int32 | 0 | Physical position relative to ground |
| `ODONYME` | object/str | 0 | Full structured road name |
| `geometry` | geometry | 0 | LineString geospatial coordinates |

---

## 4. Geometry Audit
*   **Total Geometry Count**: `47983` (100% of rows have geometries)
*   **Geometry Type**: `LineString` (`47983` features)
*   **Null Geometries**: `0`
*   **Empty Geometries**: `0`
*   **Invalid Geometries**: `0`
*   **Suspicious Geometries**: None (no self-intersections or duplicate nodes found)

---

## 5. Identifier Audit (`ID_TRC`)
*   **Total Values**: `47983`
*   **Unique Values**: `47983`
*   **Null Values**: `0`
*   **Duplicate Values**: `0`
*   **Value Range**:
    *   Minimum `ID_TRC`: `1010001`
    *   Maximum `ID_TRC`: `4019258`
*   **Verdict**: ID_TRC is unique and suitable as the road-segment identifier within this Géobase snapshot. Use of ID_TRC across repair, pavement-condition and road-asset datasets remains unverified and must be assessed separately.

---

## 6. Attribute Audits

### Road Class (`CLASSE`)
*   **Null Values**: `0`
*   **Value Range**: All values lie strictly within the range `0–9` (no values outside this range).
*   **Class Frequencies & Descriptions**:
    *   Class 0 (Rues locales / Local streets): `29185`
    *   Class 1 (Certaines voies piétonnières / Certain pedestrian walkways): `140`
    *   Class 2 (Places d’affaires / Business locations): `20`
    *   Class 3 (Quai / Quay): `8`
    *   Class 4 (Privée / Private): `1090`
    *   Class 5 (Collectrices / Collectors): `6919`
    *   Class 6 (Artères secondaires / Secondary arteries): `4545`
    *   Class 7 (Artères principales / Main arteries): `3871`
    *   Class 8 (Autoroutes / Motorways): `2129`
    *   Class 9 (Rue projetée / Projected street): `76`

### Road Names (`ODONYME`)
*   **Null Values**: `0`
*   **Blank or Empty String Values**: `0`

### Borough-Side Fields (`ARR_GCH` / `ARR_DRT`)
*   **Null `ARR_GCH`**: `0`
*   **Null `ARR_DRT`**: `0`
*   **Both Missing**: `0`
*   *Note: These fields contain administrative borough identifiers assigned to the left and right sides of each segment.*

### Missingness Summary
The critical identifier, geometry, road-class, borough-side and complete-street-name fields are populated. However, LIE_VOIE, DIR_VOIE and a small number of TYP_VOIE values are null or blank. These components can be optional within the road-name structure and must not be imputed during this basic audit.

The complete missingness counts for all 17 non-geometry attributes are detailed below:

| Attribute | Null or Blank Count | Total Features | Percentage Missing |
| :--- | :--- | :--- | :--- |
| `ID_TRC` | 0 | 47983 | 0.00% |
| `DEB_GCH` | 0 | 47983 | 0.00% |
| `FIN_GCH` | 0 | 47983 | 0.00% |
| `ARR_GCH` | 0 | 47983 | 0.00% |
| `SENS_CIR` | 0 | 47983 | 0.00% |
| `CLASSE` | 0 | 47983 | 0.00% |
| `LIE_VOIE` | 41749 | 47983 | 87.01% |
| `TYP_VOIE` | 30 | 47983 | 0.06% |
| `DIR_VOIE` | 43462 | 47983 | 90.58% |
| `NOM_VOIE` | 0 | 47983 | 0.00% |
| `DEB_DRT` | 0 | 47983 | 0.00% |
| `FIN_DRT` | 0 | 47983 | 0.00% |
| `ARR_DRT` | 0 | 47983 | 0.00% |
| `LIM_GCH` | 0 | 47983 | 0.00% |
| `LIM_DRT` | 0 | 47983 | 0.00% |
| `POSITION` | 0 | 47983 | 0.00% |
| `ODONYME` | 0 | 47983 | 0.00% |

---

## 7. Coordinate and CRS Findings
*   **Reported CRS**: CRS interpreted by GeoPandas as EPSG:4326. The raw GeoJSON does not contain an explicit crs member; WGS 84 longitude/latitude interpretation is consistent with GeoJSON conventions and the observed Montréal coordinate bounds.
*   **Geographic Coordinate Bounds**:
    *   Minimum Longitude: `-73.98318853`
    *   Minimum Latitude: `45.40238371`
    *   Maximum Longitude: `-73.47912183`
    *   Maximum Latitude: `45.70366395`
*   **Montreal Consistency Check**: **PASS** (The bounding box corresponds precisely with the Island and agglomeration of Montréal).

---

## 8. Scientific Limitations
1.  **Unique Identifier Scope**: While `ID_TRC` is verified as the unique identifier within this Géobase file, this does **not** yet prove that other datasets (such as pothole repairs or pavement conditions) use this identifier or are directly compatible. Cross-dataset joining compatibility still requires Phase 2 audits and Phase 3 validation.
2.  **Lack of Historical Dimension**: The Géobase represents a current, single-point-in-time network snapshot. It does **not** provide a historical observation date for every road segment. Consequently, it cannot be used to reconstruct historical network topologies.
3.  **Borough Assignments**: Left-hand (`ARR_GCH`) and right-hand (`ARR_DRT`) borough identifiers may diverge for boundary segments (e.g., bordering streets). Any deterministic assignment of a segment to a single borough must be governed by a documented spatial assignment rule established in Phase 3.
4.  **No Causal Association**: Road class (`CLASSE`) is a candidate feature for predicting deterioration risk, but no causal interpretation between road class and structural failure may be inferred from this baseline snapshot.

---

## 9. Audit Decision
**PASS — suitable as the canonical road-network candidate (basic structural and content audit only; does not approve spatial joins or cross-dataset compatibility)**

---

## 10. Next Permitted Action
Begin manual download and basic content audit of the second dataset in the sequence: **mechanized pothole repairs** (`mechanized_pothole_repairs`).
