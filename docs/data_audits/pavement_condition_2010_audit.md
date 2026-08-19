# Pavement Condition Campaign Audit: 2010

## 1. Official Identity & Metadata

- **Campaign Label**: 2010 Campaign
- **Network Scope**: Réseau routier complet (local et artériel)
- **Source URL**: [https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/d714c4b1-fe1a-4f9e-aa76-3fe45076c830/download/auscultation-chaussees-2010.csv](https://donnees.montreal.ca/dataset/cee47404-08bc-40e6-af71-cfcdce4617e8/resource/d714c4b1-fe1a-4f9e-aa76-3fe45076c830/download/auscultation-chaussees-2010.csv)
- **Source Downloaded Filename**: `auscultation-chaussees-2010` (normalized browser name)
- **Canonical Destination Filename**: `auscultation-chaussees-2010csv` (or `auscultation-chaussee-2024.gpkg` for 2024)
- **File Size (bytes)**: 3614958
- **SHA-256 Hash**: `5ee6becde9cb4d2b75246b19458968a6da29c7266f32360b1f097e732ed89a74`
- **Format**: CSV
- **Encoding**: UTF-8

## 2. Row and Field Counts

- **Physical Row / Feature Count**: 29272
- **Total Data Record Count**: 29271
- **Header Columns**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice PCI', 'Etat PCI', 'Indice IRI', 'Etat IRI']`
- **Normalized In-Memory Headers**: `['ID_TRC', 'Rue', 'De', 'A', 'Longueur', 'Arrondissement', 'DateReleve', 'Indice_PCI', 'Etat_PCI', 'Indice_IRI', 'Etat_IRI']`

## 3. Survey Dates & Observed Temporal Coverage

- **Min DateReleve**: `2009-09-15`
- **Max DateReleve**: `2011-07-26`
- **Year Distribution**:
  - `2011`: 8517 records
  - `2010`: 10408 records
  - `2009`: 10346 records

> [!IMPORTANT]
> The resource is labelled as the 2010 campaign, but its actual DateReleve coverage spans 2009–2011.

## 4. Identifier Uniqueness

- **ID Column**: `ID_TRC`
- **Unique ID_TRC Count**: 29271
- **Duplicate ID_TRC Excess**: 0

## 5. PCI (Pavement Condition Index) Results

- **Parsed Successfully**: 29271
- **Missing / Null Count**: 0
- **PCI range**: `1.0` to `100.0`
- **PCI mean**: `58.9788`
- **PCI median**: `61.0`
- **PCI percentiles**:
  - 10th: `24.0`
  - 25th: `40.0`
  - 50th: `61.0`
  - 75th: `78.0`
  - 90th: `92.0`
- **PCI out of bounds (below 0 or above 100)**: 0
- **Etat_PCI Distribution**:
  - `Bon`: 6973 rows
  - `Moyen`: 7588 rows
  - `Excellent`: 5333 rows
  - `Mauvais`: 5844 rows
  - `Très mauvais`: 3533 rows

## 6. IRI (International Roughness Index) Results

- **Parsed Successfully**: 29271
- **Missing / Null Count**: 0
- **Sentinel Candidates (IRI = 0 with State = "-")**: 0
- **IRI range (excluding sentinels)**: `0.05` to `72.7`
- **IRI mean**: `5.4825`
- **IRI median**: `4.89`
- **IRI percentiles**:
  - 10th: `2.75`
  - 25th: `3.59`
  - 50th: `4.89`
  - 75th: `6.74`
  - 90th: `8.85`
- **IRI negative values**: 0
- **IRI extreme values (> 15.0)**: 263

> [!IMPORTANT]
> The maximum IRI value of 72.7 is an observed extreme value and is preserved during Phase 2.
- **Etat_IRI Distribution**:
  - `Moyen`: 10964 rows
  - `Mauvais`: 5869 rows
  - `Excellent`: 898 rows
  - `Bon`: 6263 rows
  - `Très mauvais`: 5277 rows

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

- **Matched current Géobase IDs**: 28009 / 29271 (95.69%)
- **Unmatched campaign IDs**: 1262
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
