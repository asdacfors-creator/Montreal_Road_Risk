# Pavement Condition Campaign Audit: 2015

## 1. Official Identity & Metadata

- **Campaign Label**: 2015 Campaign
- **Network Scope**: Réseau routier complet (local et artériel)
- **Source URL**: [https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/c5c3b97e-83ec-468b-a62f-992a2d29e75b/download/auscultation-chaussees-2015.csv](https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/c5c3b97e-83ec-468b-a62f-992a2d29e75b/download/auscultation-chaussees-2015.csv)
- **Source Downloaded Filename**: `auscultation-chaussees-2015` (normalized browser name)
- **Canonical Destination Filename**: `auscultation-chaussees-2015csv` (or `auscultation-chaussee-2024.gpkg` for 2024)
- **File Size (bytes)**: 3828409
- **SHA-256 Hash**: `c062a2989057df64e6bc0fc23d27bfc48988cd72e6d7694c380e0b40a8d10879`
- **Format**: CSV
- **Encoding**: UTF-8

## 2. Row and Field Counts

- **Physical Row / Feature Count**: 30906
- **Total Data Record Count**: 30905
- **Header Columns**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice PCI', 'Etat PCI', 'Indice IRI', 'Etat IRI']`
- **Normalized In-Memory Headers**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`

## 3. Survey Dates & Observed Temporal Coverage

- **Min DateReleve**: `2015-06-09`
- **Max DateReleve**: `2015-10-30`
- **Year Distribution**:
  - `2015`: 30905 records

## 4. Identifier Uniqueness

- **ID Column**: `ID_TRC`
- **Unique ID_TRC Count**: 30905
- **Duplicate ID_TRC Excess**: 0

## 5. PCI (Pavement Condition Index) Results

- **Parsed Successfully**: 30905
- **Missing / Null Count**: 0
- **PCI range**: `1.0` to `100.0`
- **PCI mean**: `51.5215`
- **PCI median**: `50.0`
- **PCI percentiles**:
  - 10th: `19.0`
  - 25th: `30.0`
  - 50th: `50.0`
  - 75th: `71.0`
  - 90th: `88.0`
- **PCI out of bounds (below 0 or above 100)**: 0
- **Etat_PCI Distribution**:
  - `Bon`: 4827 rows
  - `Mauvais`: 8245 rows
  - `Moyen`: 7457 rows
  - `Très mauvais`: 6008 rows
  - `Excellent`: 4368 rows

## 6. IRI (International Roughness Index) Results

- **Parsed Successfully**: 30905
- **Missing / Null Count**: 0
- **Sentinel Candidates (IRI = 0 with State = "-")**: 0
- **IRI range (excluding sentinels)**: `0.04` to `15.36`
- **IRI mean**: `5.3444`
- **IRI median**: `5.08`
- **IRI percentiles**:
  - 10th: `3.07`
  - 25th: `3.9`
  - 50th: `5.08`
  - 75th: `6.52`
  - 90th: `7.96`
- **IRI negative values**: 0
- **IRI extreme values (> 15.0)**: 2
- **Etat_IRI Distribution**:
  - `Moyen`: 13011 rows
  - `Mauvais`: 7826 rows
  - `Bon`: 5375 rows
  - `Très mauvais`: 4327 rows
  - `Excellent`: 366 rows

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

- **Matched current Géobase IDs**: 29444 / 30905 (95.27%)
- **Unmatched campaign IDs**: 1461
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
| Indice_IRI | int, float | 0 | 0.00% | 0 |
| Etat_IRI | str | 0 | 0.00% | 0 |

## 11. Scientific Limitations & Audit Decisions

- **Scientific Warnings**:
  1. Historical ID_TRC drift relative to the current Géobase.
  2. IRI missingness or sentinel values (e.g. 1326 zeroes in 2020) require a downstream strategy.
  3. Irregular temporal frequency and varying network scopes.
- **Raw-file Integrity Confirmation**: Confirmed. Source size and hash match the expected baseline exactly.
- **Audit Decision**: **PASS WITH LIMITATIONS** (No resolved limitations. Phase 3 locked).
