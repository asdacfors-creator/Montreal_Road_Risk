# Data Audit Report — Road Assets Pavement (Chaussée Agrégée)

## 1. Dataset Identity and Official Resource Names
*   **Official Dataset Name**: `Chaussée agrégée et intersection — Base de données des actifs de voirie`
*   **Official Resources**:
    *   `Voirie - C22 - actif Chaussée agrégée - format GeoJSON` (Primary road-assets polygon archive)
    *   `Voirie - liste de valeurs - format CSV` (Attribute-value dictionary reference CSV)

---

## 2. File Verification and Normalization

### A. Source and Destination Paths
*   **Source Archive Path**: `<DOWNLOADS_DIR>\voi_chaussee_s_c22_geojson (1).zip`
*   **Destination Archive Path**: `D:\Montreal_Road_Risk\data\raw\montreal\road_assets\voi_chaussee_s_c22_geojson.zip`
    *   *Filename Normalization Note*: The destination file copy name is normalized by removing the browser-generated `" (1)"` suffix. The original file remains unchanged in the downloads folder.
*   **Source Reference CSV Path**: `<DOWNLOADS_DIR>\voi_liste_valeurs_csv.csv`
*   **Destination Reference CSV Path**: `D:\Montreal_Road_Risk\data\raw\montreal\road_assets\voi_liste_valeurs_csv.csv`

### B. File Hashes and Sizes

| File | Size (Bytes) | SHA-256 Checksum | Verification Status |
| :--- | :--- | :--- | :--- |
| **Source ZIP Archive** | `36622399` | `baeb0afd09d13f1a812836aea36ab04efc2f6333a7600caf31218ee522f3b4e7` | Matches |
| **Destination ZIP Archive** | `36622399` | `baeb0afd09d13f1a812836aea36ab04efc2f6333a7600caf31218ee522f3b4e7` | Matches |
| **Source Reference CSV** | `6829` | `e8ae05f22796ae361360da6ac3f28fe7d79cd7200cf4e5e93ecf85e9bf2704b0` | Matches |
| **Destination Reference CSV** | `6829` | `e8ae05f22796ae361360da6ac3f28fe7d79cd7200cf4e5e93ecf85e9bf2704b0` | Matches |

*Integrity Check*: Source and destination files are identical. Original downloads exist.

---

## 3. ZIP Archive and GeoJSON Structural Integrity

### A. ZIP Archive Details
*   **Genuine ZIP**: `True`
*   **Integrity Test**: `ok` (CRC verification passed)
*   **Member Count**: `1`
*   **Member Name**: `VOI_CHAUSSEE_S_C22_GeoJSON.json`
*   **Member Uncompressed Size**: `159981330` bytes
*   **Member SHA-256 Checksum**: `9b6e19c47e85e8337a4ded215ddab8a322c63d9f57cd86ccc55d32037651c35d`

### B. GeoJSON Structure
*   **JSON Parse Result**: `Parse Successful`
*   **Top-level Object Type**: `FeatureCollection`
*   **Dataset Name**: `VOI_CHAUSSEE_S_C22`
*   **Feature Count**: `64025`
*   **Properties Count**: `12`
*   **Property Schema Consistency**: `100% Consistent` (All 64,025 features share the exact same property keys).
*   **CRS Declaration**:
    *   *CRS Statement*: The raw GeoJSON contains no explicit `crs` member. Its longitude/latitude coordinates are consistent with GeoJSON coordinate conventions and Montréal, but no project working CRS is approved in Phase 2.

---

## 4. Geometry Quality Audit
*   **Geometry-type distribution**: `{"Polygon": 64025}`
*   **Null geometries**: `0`
*   **Empty geometries**: `0`
*   **Invalid geometries**: `0` (All geometries are valid under OGC standards).
*   **Valid geometries**: `64025`
*   **Bounding box**: `[-73.98319802048044, 45.40234644547825, -73.47906159631005, 45.70369273119455]` (Coordinates are consistent with the broad Montréal region).
*   **Exact duplicate geometries**: `0`
*   **Duplicate ID + geometry combinations**: `0`
*   **Zero-area projected polygons**: `0` (Calculated using temporary memory-only projection to MTM Zone 8 / EPSG:2950).

---

## 5. Identifier Quality
*   **Attribute Key**: `ID_VOI_CHAUSSEE_AGR`
*   **Non-null values**: `64025`
*   **Unique values**: `64025`
*   **Duplicate excess**: `0`
*   *Statement*: ID_VOI_CHAUSSEE_AGR is unique within this road-assets snapshot.
*   *Note*: No direct identifier relationship to Géobase (which uses `ID_TRC`) is currently established. Join-feasibility remains spatial-only.

---

## 6. Complete Attribute Missingness Table

| Field Name | Data Type | Non-null Count | Null Count | Blank Count | Missing % | Unique Count | Representative Examples |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ID_VOI_CHAUSSEE_AGR`** | `<class 'int'>` | 64025 | 0 | 0 | 0.00% | 64025 | `101023537`, `200146944`, `200146945` |
| **`CATEGORIECHAUSSEE_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 6 | `Rue`, `Ruelle`, `Bretelle`, `Autoroute` |
| **`DATECONSTRUCTION`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 587 | `19170701000000`, `20010101000000` |
| **`DATECONSTRUCTIONPREC_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 9 | `Inconnu`, `DATE construction +/- 100 ans` |
| **`DATERESURFACAGE`** | `<class 'str'>` | 8490 | 55535 | 0 | 86.74% | 564 | `None`, `20190908000000`, `20250127000000` |
| **`MATERIAUCHAUSSEE_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 9 | `Asphalte`, `Béton`, `Béton et pavé`, `Gazon` |
| **`POSITION_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 8 | `Actif de voirie (5) situé au sol`, `Viaduc` |
| **`PROPRIETAIRE_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 36 | `Dorval - Ile Dorval`, `Ahuntsic - Cartierville` |
| **`TYPEFONDATION_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 4 | `Souple`, `Rigide`, `Inconnu`, `Mixte` |
| **`TYPEUSAGECYCLABLE_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 8 | `Sans usage cyclable`, `Chaussée désignée` |
| **`UTILISATION_REF`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 9 | `Véhicule`, `Aménagement`, `Piéton`, `Rue verte` |
| **`DATE_VERSION`** | `<class 'str'>` | 64025 | 0 | 0 | 0.00% | 1 | `20260704000000` |

---

## 7. Date Integrity and Logic Audits

### A. DATECONSTRUCTION
*   **Parseable**: `64025`
*   **Missing**: `0`
*   **Earliest**: `1865-12-30`
*   **Latest**: `2026-01-14`

### B. DATECONSTRUCTIONPREC_REF Precision Distribution
A populated date field does not imply precise knowledge of the construction date. Over 88% of construction dates are flagged as highly imprecise or unknown:

| Precision Category | Row Count | Percentage |
| :--- | :--- | :--- |
| **`Inconnu`** | 35830 | 55.96% |
| **`DATE construction +/- 100 ans maximum`** | 20880 | 32.61% |
| **`DATE construction +/- 5 ans maximum`** | 4407 | 6.88% |
| **`DATE construction dans année courante`** | 2773 | 4.33% |
| **`DATE construction +/- 6 mois maximum`** | 52 | 0.08% |
| **`DATE construction +/- 25 ans`** | 29 | 0.05% |
| **`DATE construction précise`** | 25 | 0.04% |
| **`DATE construction précise au mois courant`** | 15 | 0.02% |
| **`DATE construction +/- 10 ans`** | 14 | 0.02% |

### C. DATERESURFACAGE
*   **Non-missing**: `8490`
*   **Missing**: `55535`
*   **Missing percentage**: `86.74%`
*   **Earliest resurfacing**: `1989-01-01`
*   **Latest resurfacing**: `2025-10-21`
*   *Warning*: This high missingness rate is scientifically critical. Missing resurfacing dates must not be filled with construction dates or arbitrary defaults.

### D. DATE_VERSION
*   **Unique value**: `2026-07-04` (representing the snapshot dataset extraction version).

### E. Date Logic Anomalies
*   **Invalid date strings**: `0`
*   **Future construction relative to DATE_VERSION**: `0`
*   **Future resurfacing relative to DATE_VERSION**: `0`
*   **Resurfacing before construction**: `133` cases
*   **Construction after resurfacing**: `133` cases (matches the resurfacing before construction count).
    *   *Note*: These 133 records contain logical anomalies where the construction date is registered after the resurfacing date. These raw records remain unmodified.

---

## 8. Attribute-Value Reference CSV Audit

### A. CSV Integrity
*   **Encoding**: `UTF-8 with BOM`
*   **Delimiter**: `,` (Comma)
*   **Header**: `['ATTRIBUT', 'REFERENCE']`
*   **Total Physical Rows**: `185` (1 header row + 184 data rows)
*   **Blank Rows**: `0`
*   **Duplicate Rows**: `0`
*   **Attributes Represented**: `16` distinct dictionary categories

### B. Reference Domain Mapping Coverage
The GeoJSON Uses `MATERIAUCHAUSSEE_REF` which maps to the CSV domain key `MATERIAU_REF` (alias mapping). The mapping checks reveal:
*   **100% Coverage**: Every observed code in the GeoJSON `*_REF` fields is successfully mapped to its corresponding domain key in the CSV (unmapped observed values count is `0` across all fields).
*   **Documented but Unused Values**:
    *   `CATEGORIECHAUSSEE_REF`: 4 values unused (e.g., `Inconnu`, `Chemin privé`)
    *   `DATECONSTRUCTIONPREC_REF`: 2 values unused
    *   `MATERIAUCHAUSSEE_REF` (`MATERIAU_REF`): 11 values unused (e.g., `Pavé de bois`, `Terre battue`)
    *   `POSITION_REF`: 1 value unused
    *   `PROPRIETAIRE_REF`: 5 values unused
    *   `TYPEFONDATION_REF`: 3 values unused
    *   `TYPEUSAGECYCLABLE_REF`: 5 values unused
    *   `UTILISATION_REF`: 4 values unused

---

## 9. Scientific Feasibility and Decisions

1.  **Is the archive structurally valid?** Yes, the zip is uncorrupted and passes integrity tests.
2.  **Is the GeoJSON structurally valid?** Yes, parses completely.
3.  **Are the geometries suitable as road-asset polygon candidates?** Yes, all are valid Polygon geometries.
4.  **Is `ID_VOI_CHAUSSEE_AGR` unique within this snapshot?** Yes. ID_VOI_CHAUSSEE_AGR is unique within this road-assets snapshot.
5.  **Are construction dates available?** Yes, fully populated.
6.  **How reliable are construction dates given `DATECONSTRUCTIONPREC_REF`?** Mostly unreliable for precise age calculations. More than 88% of construction dates are flagged as unknown or +/- 100 years precision.
7.  **How serious is the 86.74% resurfacing-date missingness?** Highly critical. Features based on resurfacing age cannot be computed for most segments.
8.  **Are material and foundation categories interpretable using the reference CSV?** Yes. 100% of observed reference domains are fully mapped by the CSV.
9.  **Is a direct identifier join to Géobase verified?** No. Géobase uses `ID_TRC` and road-assets uses `ID_VOI_CHAUSSEE_AGR`. Join must remain spatial.
10. **Can the dataset be retained as a candidate classification-MVP feature source?** Yes.
11. **Which potential features are supported?** categorical construction-era, construction-precision category, resurfacing-availability flag, pavement material, foundation type, road use, cycling use.
12. **Which potential features must be restricted, flagged or rejected?** Precise road age (due to +/- 100 year uncertainty) and precise resurfacing age (due to 86.74% missingness) must be flagged and restricted.
13. **What must remain deferred until Phase 3?** All spatial snapping, buffer overlay intersections, and coordinate transformations to join road assets with Géobase.

---

## 10. Audit Decision
**PASS WITH LIMITATIONS — The dataset is structurally valid and clean, but contains severe temporal limitations (86.74% missing resurfacing dates, 88.57% unknown/imprecise construction dates, and 133 date-logic anomalies). Geometries are unprojected and lacks direct ID join with Géobase, which must be resolved spatially in Phase 3.**

---

## 11. Raw-File Integrity and Phase 3 Lock Confirmation
*   **Raw-File Integrity**: Confirmed. Raw destination files remain completely unmodified.
*   **Phase 3 Lock**: Confirmed. Phase 3 remains locked.
