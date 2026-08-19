# Pavement Condition Campaign Audit: 2022

## 1. Official Identity & Metadata
- **Campaign Label**: 2022 Campaign
- **Network Scope**: Réseau local
- **Source URL**: [https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/a4ac1425-0f4e-4dca-91da-c8666509a395/download/auscultation-chaussees-2022-local.gpkg](https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/a4ac1425-0f4e-4dca-91da-c8666509a395/download/auscultation-chaussees-2022-local.gpkg)
- **Source Downloaded Filename**: `auscultation-chaussees-2022` (normalized browser name)
- **Canonical Destination Filename**: `auscultation-chaussees-2022geopackage` (or `auscultation-chaussee-2024.gpkg` for 2024)
- **File Size (bytes)**: 5562368
- **SHA-256 Hash**: `7cca61a6712ddb3fb71147bfd125632d3646f0498f113d670f5a117a150387d3`
- **Format**: GeoPackage
- **Encoding**: Binary (SQLite)

## 2. Row and Field Counts
- **Physical Row / Feature Count**: 15821
- **Total Data Record Count**: 15821
- **Header Columns**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`
- **Normalized In-Memory Headers**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`

## 3. Survey Dates & Observed Temporal Coverage
- **Min DateReleve**: `2022-07-27`
- **Max DateReleve**: `2022-10-10`
- **Year Distribution**:
  - `2022`: 15821 records

## 4. Identifier Uniqueness
- **ID Column**: `ID_TRC`
- **Unique ID_TRC Count**: 15821
- **Duplicate ID_TRC Excess**: 0

## 5. PCI (Pavement Condition Index) Results
- **Parsed Successfully**: 15821
- **Missing / Null Count**: 0
- **PCI range**: `0.0` to `100.0`
- **PCI mean**: `55.3708`
- **PCI median**: `57.0`
- **PCI percentiles**:
  - 10th: `16.0`
  - 25th: `28.0`
  - 50th: `57.0`
  - 75th: `82.0`
  - 90th: `94.0`
- **PCI out of bounds (below 0 or above 100)**: 0
- **Etat_PCI Distribution**:
  - `Bon`: 3219 rows
  - `Excellent`: 4183 rows
  - `Très mauvais`: 2736 rows
  - `Moyen`: 2561 rows
  - `Mauvais`: 3122 rows

## 6. IRI (International Roughness Index) Results
- **Parsed Successfully**: 14359
- **Missing / Null Count**: 1462
- **Sentinel Candidates (IRI = 0 with State = "-")**: 0
- **IRI range (excluding sentinels)**: `0.82` to `22.87`
- **IRI mean**: `4.5144`
- **IRI median**: `4.12`
- **IRI percentiles**:
  - 10th: `2.49`
  - 25th: `3.12`
  - 50th: `4.12`
  - 75th: `5.46`
  - 90th: `7.14`
- **IRI negative values**: 0
- **IRI extreme values (> 15.0)**: 15
- **Etat_IRI Distribution**:
  - `Excellent`: 1449 rows
  - `Bon`: 5280 rows
  - `Moyen`: 4898 rows
  - `Mauvais`: 1868 rows
  - `Très mauvais`: 864 rows

## 7. Consistency Checks
- **PCI index exists but state label missing**: 0
- **PCI state exists but index missing**: 0
- **IRI index exists but state label missing**: 0
- **IRI state exists but index missing**: 0

## 8. Geometry and Spatial Attributes
- **Format Geometry**: LineString
- **CRS declaration**: `EPSG:4326 (WGS 84 geodetic)`
- **Geometry Type Distribution**: `{'LineString': 15821}`
- **Null Geometries**: 0
- **Empty Geometries**: 0
- **Invalid Geometries**: 0
- **Exact Duplicate Geometries**: 0
- **Exact Duplicate Features (properties + coordinates)**: 0
- **Bounding Box Bounds**: `[-73.9431719500133, 45.415263012224855, -73.47977608330396, 45.70109617196858]`
- **RTree Row Count**: 15821

## 9. Current Géobase ID Feasibility Check
- **Matched current Géobase IDs**: 15755 / 15821 (99.58%)
- **Unmatched campaign IDs**: 66
- **Feasibility Wording**: "Most historical condition identifiers still appear in the current Géobase snapshot, but unmatched identifiers remain and may reflect segment renumbering, reconstruction, geometry changes or coverage differences."

## 10. Schema Definitions (Attributes table)
| Field | Types | Null Count | Null % | Blank Count |
| --- | --- | --- | --- | --- |
| ID_TRC | int | 0 | 0.00% | 0 |
| Rue | str | 0 | 0.00% | 0 |
| De | str | 0 | 0.00% | 259 |
| A | str | 0 | 0.00% | 404 |
| Longueur | float | 0 | 0.00% | 0 |
| Arrondissement | str | 0 | 0.00% | 0 |
| DateReleve | str | 0 | 0.00% | 0 |
| Indice_PCI | float | 0 | 0.00% | 0 |
| Etat_PCI | str | 0 | 0.00% | 0 |
| Indice_IRI | str | 0 | 0.00% | 1462 |
| Etat_IRI | str | 0 | 0.00% | 1462 |

## 11. Scientific Limitations & Audit Decisions
- **Scientific Warnings**:
  1. Historical ID_TRC drift relative to the current Géobase.
  2. IRI missingness or sentinel values (e.g. 1326 zeroes in 2020) require a downstream strategy.
  3. Irregular temporal frequency and varying network scopes.
- **Raw-file Integrity Confirmation**: Confirmed. Source size and hash match the expected baseline exactly.
- **Audit Decision**: **PASS WITH LIMITATIONS** (No resolved limitations. Phase 3 locked).
