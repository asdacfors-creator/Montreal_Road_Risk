# Pavement Condition Campaign Audit: 2018

## 1. Official Identity & Metadata

- **Campaign Label**: 2018 Campaign
- **Network Scope**: Réseau artériel (RAAV)
- **Source URL**: [https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/85085655-4ac0-4114-9793-715c0b63e2a0/download/auscultation-chaussees-2018-arteriel.csv](https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/85085655-4ac0-4114-9793-715c0b63e2a0/download/auscultation-chaussees-2018-arteriel.csv)
- **Source Downloaded Filename**: `auscultation-chaussees-2018` (normalized browser name)
- **Canonical Destination Filename**: `auscultation-chaussees-2018csv` (or `auscultation-chaussee-2024.gpkg` for 2024)
- **File Size (bytes)**: 1790835
- **SHA-256 Hash**: `a2fc5ddf358493aa5d7e3d4b8401fe7880bd799816e36853d6bf7d9bf6ad8023`
- **Format**: CSV
- **Encoding**: UTF-8

## 2. Row and Field Counts

- **Physical Row / Feature Count**: 14115
- **Total Data Record Count**: 14114
- **Header Columns**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice PCI', 'Etat PCI', 'Indice IRI', 'Etat IRI']`
- **Normalized In-Memory Headers**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`

## 3. Survey Dates & Observed Temporal Coverage

- **Min DateReleve**: `2018-07-04`
- **Max DateReleve**: `2018-08-19`
- **Year Distribution**:
  - `2018`: 14114 records

## 4. Identifier Uniqueness

- **ID Column**: `ID_TRC`
- **Unique ID_TRC Count**: 14114
- **Duplicate ID_TRC Excess**: 0

## 5. PCI (Pavement Condition Index) Results

- **Parsed Successfully**: 14114
- **Missing / Null Count**: 0
- **PCI range**: `5.0` to `100.0`
- **PCI mean**: `61.5963`
- **PCI median**: `64.0`
- **PCI percentiles**:
  - 10th: `18.0`
  - 25th: `37.0`
  - 50th: `64.0`
  - 75th: `90.0`
  - 90th: `99.0`
- **PCI out of bounds (below 0 or above 100)**: 0
- **Etat_PCI Distribution**:
  - `Excellent`: 4049 rows
  - `Bon`: 1827 rows
  - `Mauvais`: 2435 rows
  - `Moyen`: 2713 rows
  - `Très mauvais`: 3090 rows

## 6. IRI (International Roughness Index) Results

- **Parsed Successfully**: 14099
- **Missing / Null Count**: 15
- **Sentinel Candidates (IRI = 0 with State = "-")**: 0
- **IRI range (excluding sentinels)**: `1.01` to `32.66`
- **IRI mean**: `5.2348`
- **IRI median**: `4.48`
- **IRI percentiles**:
  - 10th: `2.64`
  - 25th: `3.31`
  - 50th: `4.48`
  - 75th: `6.39`
  - 90th: `8.77`
- **IRI negative values**: 0
- **IRI extreme values (> 15.0)**: 141
- **Etat_IRI Distribution**:
  - `Bon`: 2824 rows
  - `Moyen`: 5525 rows
  - `Très mauvais`: 3029 rows
  - `Mauvais`: 2426 rows
  - `Excellent`: 295 rows

## 7. Consistency Checks

- **PCI index exists but state label missing**: 0
- **PCI state exists but index missing**: 0
- **IRI index exists but state label missing**: 0
- **IRI state exists but index missing**: 0

## 8. Geometry and Spatial Attributes

- **Format Geometry**: None
- **CRS declaration**: `No source geometry is included in this selected campaign resource.`
- **Geometry Details**: No source geometry is included in this selected campaign resource.

## 9. Current Géobase ID Feasibility Check

- **Matched current Géobase IDs**: 13336 / 14114 (94.49%)
- **Unmatched campaign IDs**: 778
- **Feasibility Wording**: "Most historical condition identifiers still appear in the current Géobase snapshot, but unmatched identifiers remain and may reflect segment renumbering, reconstruction, geometry changes or coverage differences."

## 10. Schema Definitions (Attributes table)

| Field | Types | Null Count | Null % | Blank Count |
| --- | --- | --- | --- | --- |
| ID_TRC | int | 0 | 0.00% | 0 |
| Rue | str | 0 | 0.00% | 0 |
| De | str | 0 | 0.00% | 0 |
| A | str | 0 | 0.00% | 0 |
| Longueur | int | 0 | 0.00% | 0 |
| Arrondissement | str | 0 | 0.00% | 0 |
| DateReleve | str | 0 | 0.00% | 0 |
| Indice_PCI | int | 0 | 0.00% | 0 |
| Etat_PCI | str | 0 | 0.00% | 0 |
| Indice_IRI | str, int, float | 0 | 0.00% | 15 |
| Etat_IRI | str | 0 | 0.00% | 15 |

## 11. Scientific Limitations & Audit Decisions

- **Scientific Warnings**:
  1. Historical ID_TRC drift relative to the current Géobase.
  2. IRI missingness or sentinel values (e.g. 1326 zeroes in 2020) require a downstream strategy.
  3. Irregular temporal frequency and varying network scopes.
- **Raw-file Integrity Confirmation**: Confirmed. Source size and hash match the expected baseline exactly.
- **Audit Decision**: **PASS WITH LIMITATIONS** (No resolved limitations. Phase 3 locked).
