# Pavement Condition Campaigns Cross-Year Audit Report

## 1. Format and Encoding Differences Across Campaigns

| Campaign | Format | Encoding | File Size (bytes) | SHA-256 Hash |
| --- | --- | --- | --- | --- |
| 2010 | CSV | UTF-8 (No BOM) | 3614958 | `5ee6becde9cb4d2b75246b19458968a6da29c7266f32360b1f097e732ed89a74` |
| 2015 | CSV | UTF-8 (No BOM) | 3828409 | `c062a2989057df64e6bc0fc23d27bfc48988cd72e6d7694c380e0b40a8d10879` |
| 2018 | CSV | UTF-8 (No BOM) | 1790835 | `a2fc5ddf358493aa5d7e3d4b8401fe7880bd799816e36853d6bf7d9bf6ad8023` |
| 2020 | GeoJSON | Windows-1252 / CP1252 | 8483402 | `6555ef9488b955b677c01993f067651985c5c804185a5675e39e03c9b1ecabf2` |
| 2022 | GeoPackage | Binary (SQLite) | 5562368 | `7cca61a6712ddb3fb71147bfd125632d3646f0498f113d670f5a117a150387d3` |
| 2024 | GeoPackage | Binary (SQLite) | 5611520 | `fc474fb8c668a027d80c1c9dc09cf839b3311a21f65409b34a641c9fae02d01a` |

- **Encoding Risk**: Reading the 2020 GeoJSON file as UTF-8 directly will cause decoding errors on French characters. It must be processed with CP1252.

## 2. Header and Schema Differences

CSV files (2010, 2015, 2018) contain space-based names, whereas GeoJSON/GPKG resources use underscores:
- `Indice PCI` / `Indice_PCI`
- `Etat PCI` / `Etat_PCI`
- `Indice IRI` / `Indice_IRI`
- `Etat IRI` / `Etat_IRI`
- *In-memory Normalization*: The auditor normalizes spaces to underscores to allow uniform access.

## 3. CRS and Bounding Box Differences

- **2010, 2015, 2018**: No source geometry is included.
- **2020 GeoJSON**: `urn:ogc:def:crs:OGC:1.3:CRS84` (WGS 84), Bounds: `[-73.93696408990775, 45.41525343636446, -73.47912177774066, 45.70375341771243]`
- **2022 local GPKG**: `EPSG:4326` (WGS 84), Bounds: `[-73.9431719500133, 45.415263012224855, -73.47977608330396, 45.70109617196858]`
- **2024 arterial GPKG**: `EPSG:32188 (NAD83 / MTM zone 8)` (Projected), Bounds: `[270620.98679999897, 5030598.20404946, 306425.7974999998, 5062642.45499946]`
- **CRS Warning**: No working CRS is approved for the project yet. These coordinate differences must be resolved during Phase 3 reprocessing.

## 4. Network-Scope and Survey Timing Analysis

The campaigns do not represent annual full-network surveys:
- **2010 campaign**: complete network, actual survey spans 2009–2011.
- **2015 campaign**: complete network.
- **2018 campaign**: arterial network only.
- **2020 campaign**: arterial network only.
- **2022 campaign**: local network only.
- **2024 campaign**: arterial network only.

### ID Overlaps

- 2022 local vs 2024 arterial: only 28 shared IDs.
- 2018 arterial vs 2022 local: only 60 shared IDs.
- 2020 arterial vs 2022 local: 0 shared IDs.
These low overlaps reflect distinct network scopes. Do not treat 2022 and 2024 as consecutive citywide snapshots. Local and arterial networks follow different measurement schedules.

## 5. Current Géobase ID Match Coverage

| Campaign | Total IDs | Matched in Géobase | Match Rate | Unmatched Count |
| --- | --- | --- | --- | --- |
| 2010 | 29271 | 28009 | 95.69% | 1262 |
| 2015 | 30905 | 29444 | 95.27% | 1461 |
| 2018 | 14114 | 13336 | 94.49% | 778 |
| 2020 | 13777 | 13567 | 98.48% | 210 |
| 2022 | 15821 | 15755 | 99.58% | 66 |
| 2024 | 17176 | 16999 | 98.97% | 177 |

*Interpretation*: Most historical condition identifiers still appear in the current Géobase snapshot, but unmatched identifiers remain and may reflect segment renumbering, reconstruction, geometry changes or coverage differences. Do not assume 100% identifier joining is possible.

## 6. Duplicates, Sentinels, and Missing Values

- **2020 Duplicates**: 99 exact feature duplicates and 99 duplicate ID_TRC values.
- **2020 Sentinels**: 1,326 records exhibit `Indice_IRI = 0` and `Etat_IRI = "-"`. This is a missing-data sentinel pattern and must not be treated as genuine zero roughness.
- **IRI Missingness**: Spans from 0.00% (2010, 2015) to 9.24% (2022) and 4.59% (2024).

## 7. Temporal Leakage Prevention

> [!IMPORTANT]
> **Temporal Leakage Rule**: For any future road-segment-month observation, pavement-condition values may only come from a survey whose DateReleve is on or before the observation cutoff date. A future survey must never be backfilled into earlier observations. The 2022 local campaign and 2024 arterial campaign cover different network scopes and must not be treated as citywide consecutive snapshots.

## 8. Supported and Unsupported Uses

- **Supported Uses**:
  - Segment-level condition feature construction using historical prior surveys.
  - Identification of network-scope constraints (local vs. arterial splits).
  - Categorical state modeling using PCI and IRI indices.
- **Unsupported Uses**:
  - Linear interpolation between 2022 and 2024 to represent citywide consecutive years.
  - Naive direct joins without accounting for ID drift and unmatched segment rates (~1-5%).

## 9. Phase 3-Deferred Decisions

- Imputation or representation strategy for the 1,326 CP1252 GeoJSON IRI sentinels.
- Imputation of missing IRI in 2022 and 2024.
- Spatial reprojection and working project CRS selection.
- Resolution of the 99 duplicate feature records in the 2020 arterial campaign.
- ID drift alignment strategy (handling unmatched campaign segment IDs).
