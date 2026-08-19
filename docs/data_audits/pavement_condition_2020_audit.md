# Pavement Condition Campaign Audit: 2020

## 1. Official Identity & Metadata
- **Campaign Label**: 2020 Campaign
- **Network Scope**: Réseau artériel (RAAV)
- **Source URL**: [https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/ab4b1114-4caa-47f0-9314-6e19de9df527/download/auscultation-chaussees-2020-arteriel.json](https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/ab4b1114-4caa-47f0-9314-6e19de9df527/download/auscultation-chaussees-2020-arteriel.json)
- **Source Downloaded Filename**: `auscultation-chaussees-2020` (normalized browser name)
- **Canonical Destination Filename**: `auscultation-chaussees-2020geojson` (or `auscultation-chaussee-2024.gpkg` for 2024)
- **File Size (bytes)**: 8483402
- **SHA-256 Hash**: `6555ef9488b955b677c01993f067651985c5c804185a5675e39e03c9b1ecabf2`
- **Format**: GeoJSON
- **Encoding**: Windows-1252 / CP1252

## 2. Row and Field Counts
- **Physical Row / Feature Count**: 13876
- **Total Data Record Count**: 13876
- **Header Columns**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`
- **Normalized In-Memory Headers**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`

## 3. Survey Dates & Observed Temporal Coverage
- **Min DateReleve**: `2020-09-16`
- **Max DateReleve**: `2020-12-01`
- **Year Distribution**:
  - `2020`: 13876 records

## 4. Identifier Uniqueness
- **ID Column**: `ID_TRC`
- **Unique ID_TRC Count**: 13777
- **Duplicate ID_TRC Excess**: 99
  - **Duplicate ID Groups**: 98
  - **Duplicate Participating Rows**: 197
  - **Largest Duplicate Group Size**: 3

## 5. PCI (Pavement Condition Index) Results
- **Parsed Successfully**: 13876
- **Missing / Null Count**: 0
- **PCI range**: `1.0` to `100.0`
- **PCI mean**: `68.3043`
- **PCI median**: `74.0`
- **PCI percentiles**:
  - 10th: `32.0`
  - 25th: `51.0`
  - 50th: `74.0`
  - 75th: `88.0`
  - 90th: `96.0`
- **PCI out of bounds (below 0 or above 100)**: 0
- **Etat_PCI Distribution**:
  - `Bon`: 2968 rows
  - `Excellent`: 4064 rows
  - `Moyen`: 3047 rows
  - `Mauvais`: 2217 rows
  - `Très mauvais`: 1580 rows

## 6. IRI (International Roughness Index) Results
- **Parsed Successfully**: 12550
- **Missing / Null Count**: 0
- **Sentinel Candidates (IRI = 0 with State = "-")**: 1326
- **IRI range (excluding sentinels)**: `0.40000001` to `27.85000038`
- **IRI mean**: `4.5407`
- **IRI median**: `4.0999999`
- **IRI percentiles**:
  - 10th: `2.5999999`
  - 25th: `3.19000006`
  - 50th: `4.0999999`
  - 75th: `5.42999983`
  - 90th: `7.03000021`
- **IRI negative values**: 0
- **IRI extreme values (> 15.0)**: 17
- **Etat_IRI Distribution**:
  - `Moyen`: 5380 rows
  - `Bon`: 2923 rows
  - `Très mauvais`: 1667 rows
  - `Mauvais`: 2149 rows
  - `Excellent`: 431 rows
  - `-`: 1326 rows

## 7. Consistency Checks
- **PCI index exists but state label missing**: 0
- **PCI state exists but index missing**: 0
- **IRI index exists but state label missing**: 1326
- **IRI state exists but index missing**: 0

## 8. Geometry and Spatial Attributes
- **Format Geometry**: LineString
- **CRS declaration**: `urn:ogc:def:crs:OGC:1.3:CRS84`
- **Geometry Type Distribution**: `{'LineString': 13876}`
- **Null Geometries**: 0
- **Empty Geometries**: 0
- **Invalid Geometries**: 0
- **Exact Duplicate Geometries**: 99
- **Exact Duplicate Features (properties + coordinates)**: 99
- **Bounding Box Bounds**: `[-73.93696408990775, 45.41525343636446, -73.47912177774066, 45.70375341771243]`

## 9. Current Géobase ID Feasibility Check
- **Matched current Géobase IDs**: 13567 / 13777 (98.48%)
- **Unmatched campaign IDs**: 210
- **Feasibility Wording**: "Most historical condition identifiers still appear in the current Géobase snapshot, but unmatched identifiers remain and may reflect segment renumbering, reconstruction, geometry changes or coverage differences."

## 10. Schema Definitions (Attributes table)
| Field | Types | Null Count | Null % | Blank Count |
| --- | --- | --- | --- | --- |
| ID_TRC | int | 0 | 0.00% | 0 |
| Rue | str | 0 | 0.00% | 0 |
| De | str | 0 | 0.00% | 0 |
| A | str | 0 | 0.00% | 0 |
| Longueur | float | 0 | 0.00% | 0 |
| Arrondissement | str | 0 | 0.00% | 0 |
| DateReleve | str | 0 | 0.00% | 0 |
| Indice_PCI | float | 0 | 0.00% | 0 |
| Etat_PCI | str | 0 | 0.00% | 0 |
| Indice_IRI | str | 0 | 0.00% | 0 |
| Etat_IRI | str | 0 | 0.00% | 0 |

## 11. Scientific Limitations & Audit Decisions
- **Scientific Warnings**:
  1. Historical ID_TRC drift relative to the current Géobase.
  2. IRI missingness or sentinel values (e.g. 1326 zeroes in 2020) require a downstream strategy.
  3. Irregular temporal frequency and varying network scopes.
- **Raw-file Integrity Confirmation**: Confirmed. Source size and hash match the expected baseline exactly.
- **Audit Decision**: **PASS WITH LIMITATIONS** (No resolved limitations. Phase 3 locked).
