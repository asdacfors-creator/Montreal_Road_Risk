# Pavement Condition Campaign Audit: 2024

## 1. Official Identity & Metadata
- **Campaign Label**: 2024 Campaign
- **Network Scope**: Réseau artériel (RAAV)
- **Source URL**: [https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/97489483-85f9-49cc-be33-829559439ab2/download/auscultation-chaussee-2024.gpkg](https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/97489483-85f9-49cc-be33-829559439ab2/download/auscultation-chaussee-2024.gpkg)
- **Source Downloaded Filename**: `auscultation-chaussees-2024` (normalized browser name)
- **Canonical Destination Filename**: `auscultation-chaussees-2024.gpkg` (or `auscultation-chaussee-2024.gpkg` for 2024)
- **File Size (bytes)**: 5611520
- **SHA-256 Hash**: `fc474fb8c668a027d80c1c9dc09cf839b3311a21f65409b34a641c9fae02d01a`
- **Format**: GeoPackage
- **Encoding**: Binary (SQLite)

## 2. Row and Field Counts
- **Physical Row / Feature Count**: 17176
- **Total Data Record Count**: 17176
- **Header Columns**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`
- **Normalized In-Memory Headers**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`

## 3. Survey Dates & Observed Temporal Coverage
- **Min DateReleve**: `2024-06-04`
- **Max DateReleve**: `2024-10-23`
- **Year Distribution**:
  - `2024`: 17176 records

## 4. Identifier Uniqueness
- **ID Column**: `ID_TRC`
- **Unique ID_TRC Count**: 17176
- **Duplicate ID_TRC Excess**: 0

## 5. PCI (Pavement Condition Index) Results
- **Parsed Successfully**: 17176
- **Missing / Null Count**: 0
- **PCI range**: `2.0` to `100.0`
- **PCI mean**: `65.2045`
- **PCI median**: `68.0`
- **PCI percentiles**:
  - 10th: `32.0`
  - 25th: `50.0`
  - 50th: `68.0`
  - 75th: `83.0`
  - 90th: `93.0`
- **PCI out of bounds (below 0 or above 100)**: 0
- **Etat_PCI Distribution**:
  - `Excellent`: 3213 rows
  - `Mauvais`: 3185 rows
  - `Moyen`: 4926 rows
  - `Très mauvais`: 1955 rows
  - `Bon`: 3897 rows

## 6. IRI (International Roughness Index) Results
- **Parsed Successfully**: 16388
- **Missing / Null Count**: 788
- **Sentinel Candidates (IRI = 0 with State = "-")**: 0
- **IRI range (excluding sentinels)**: `0.83` to `19.53`
- **IRI mean**: `4.3619`
- **IRI median**: `3.86`
- **IRI percentiles**:
  - 10th: `2.45`
  - 25th: `3.01`
  - 50th: `3.86`
  - 75th: `5.15`
  - 90th: `6.97`
- **IRI negative values**: 0
- **IRI extreme values (> 15.0)**: 11
- **Etat_IRI Distribution**:
  - `Moyen`: 7467 rows
  - `Mauvais`: 2301 rows
  - `Bon`: 4391 rows
  - `Très mauvais`: 1884 rows
  - `Excellent`: 345 rows

## 7. Consistency Checks
- **PCI index exists but state label missing**: 0
- **PCI state exists but index missing**: 0
- **IRI index exists but state label missing**: 0
- **IRI state exists but index missing**: 0

## 8. Geometry and Spatial Attributes
- **Format Geometry**: LineString
- **CRS declaration**: `EPSG:32188 (NAD83 / MTM zone 8)`
- **Geometry Type Distribution**: `{'LineString': 17176}`
- **Null Geometries**: 0
- **Empty Geometries**: 0
- **Invalid Geometries**: 0
- **Exact Duplicate Geometries**: 0
- **Exact Duplicate Features (properties + coordinates)**: 0
- **Bounding Box Bounds**: `[270620.98679999897, 5030598.20404946, 306425.7974999998, 5062642.45499946]`
- **RTree Row Count**: 17176

## 9. Current Géobase ID Feasibility Check
- **Matched current Géobase IDs**: 16999 / 17176 (98.97%)
- **Unmatched campaign IDs**: 177
- **Feasibility Wording**: "Most historical condition identifiers still appear in the current Géobase snapshot, but unmatched identifiers remain and may reflect segment renumbering, reconstruction, geometry changes or coverage differences."

## 10. Schema Definitions (Attributes table)
| Field | Types | Null Count | Null % | Blank Count |
| --- | --- | --- | --- | --- |
| ID_TRC | int | 0 | 0.00% | 0 |
| Rue | str | 0 | 0.00% | 0 |
| De | str | 33 | 0.19% | 0 |
| A | str | 0 | 0.00% | 0 |
| Longueur | int | 0 | 0.00% | 0 |
| Arrondissement | str | 0 | 0.00% | 0 |
| DateReleve | str | 0 | 0.00% | 0 |
| Indice_PCI | float | 0 | 0.00% | 0 |
| Etat_PCI | str | 0 | 0.00% | 0 |
| Indice_IRI | float | 788 | 4.59% | 0 |
| Etat_IRI | str | 788 | 4.59% | 0 |

## 11. Scientific Limitations & Audit Decisions
- **Scientific Warnings**:
  1. Historical ID_TRC drift relative to the current Géobase.
  2. IRI missingness or sentinel values (e.g. 1326 zeroes in 2020) require a downstream strategy.
  3. Irregular temporal frequency and varying network scopes.
- **Raw-file Integrity Confirmation**: Confirmed. Source size and hash match the expected baseline exactly.
- **Audit Decision**: **PASS WITH LIMITATIONS** (No resolved limitations. Phase 3 locked).
