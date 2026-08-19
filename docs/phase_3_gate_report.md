# Phase 3 Quality Gate Report

This report summarizes the results and quality audits for the entirety of **Phase 3: GIS, Spatial and Temporal Preprocessing** (comprising Phase 3A, 3B, and 3C). 

---

## 1. Summary of Phase Results

### Phase 3A: CRS Selection and Canonical Loading

- **Working CRS**: Established and approved **`EPSG:32188`** (NAD83 / MTM zone 8) as the standard working projected coordinate reference system. All raw spatial datasets were converted to this CRS.
- **Canonical loaders**: Built reusable, memory-efficient loaders with strict schema validations.
- **Interim datasets**: Generated initial GeoParquet/Parquet spatial layers representing the audited raw source files.

### Phase 3B: Validated Spatial Linkage

- **Pothole-to-Segment Linkage**: Calculated nearest-distance distributions across sensitivity bands (10m, 15m, 20m, 30m, 50m).
- **Road Asset Crosswalk**: Evaluated segment-asset overlap at multiple levels (0.0, 0.10, 0.25, 0.50). A minimum overlap fraction of **0.10** was recommended.
- **Administrative Boundaries**: Assigned all road segments to the full Ville de Montréal Agglomeration boundaries (covering 34 features: 19 Arrondissements and 15 Villes liées). All 34 administrative polygons are correctly represented with at least one segment.
- **Outlier Segment**: Found exactly 1 unmatched segment (ID `210080`), which lies entirely outside municipal boundaries (matching our audited coordinate outlier).

### Phase 3C: Temporal Normalization and Availability

- **Timezone Assumption**: Localized naive timestamps to `America/Toronto` with DST safeguards (tracking `ambiguous_dst` and `nonexistent_dst` statuses). Potholes: $1,027,267$ successfully localized, $0$ parse failures/missing timestamps.
- **Source Year Status**: Corrected year mismatch logic. Found exactly $5$ genuine out-of-year records (1 in the 2023 file, 4 in the 2024 file). Unparseable dates ($0$ records) are classified separately as `unknown_parse_failure` and are not treated as mismatches.
- **Pavement Campaign Availability**: Enforced strict availability rules based on the exact survey date (`survey_date`), prohibiting backward filling.
- **Daily Weather Fallback**: Combined McTavish (primary) and Montréal-Trudeau (secondary) daily observations (6,209 calendar days) using same-day fallback allowlist: Mean Temp (102 recovered), Min Temp (71 recovered), Max Temp (100 recovered), and Total Precip (348 recovered). Total Rain, Total Snow, and Snow on Ground are kept strictly station-specific (no fallback).

---

## 2. Input/Output Row Reconciliations

Zero silent row loss has been verified across all datasets:

- **Pothole repairs**: $1,027,267$ input rows $\rightarrow$ $1,027,267$ output rows.
- **Pavement condition campaigns**: $121,163$ input rows $\rightarrow$ $121,163$ output rows.
- **Road assets**: $64,025$ input rows $\rightarrow$ $64,025$ output rows.
- **McTavish Weather**: $6,209$ input station-days $\rightarrow$ $6,209$ standardized station-days.
- **Montréal-Trudeau Weather**: $6,209$ input station-days $\rightarrow$ $6,209$ standardized station-days.
- **Canonical Weather**: $6,209$ daily calendar rows.

---

## 3. Spatial and Temporal Limitations

> [!WARNING]
> **Identified Data Limitations & Assumptions:**
> 1. **Boundary-Crossing Segments**: $1,205$ road segments cross administrative boundaries, which could introduce spatial assignment ambiguity.
> 2. **Imprecise Asset Dates**: Construction and resurfacing dates are mapped to computational lower bounds and year starts, carrying separate precision distributions (precise, imprecise_year, approximate_interval, unknown, missing) to prevent downstream exact-day assumptions.
> 3. **Station-Specific Weather**: Total Rain, Total Snow, and Snow on Ground contain missing observations that cannot be filled due to spatial micro-climate sensitivity.
> 4. **Timezone Context**: Without explicit timezone metadata, `America/Toronto` is maintained as a required analytical assumption.

---

## 4. Quality and Safety Controls

- **Raw Data Immutability**: Verified by pre-run and post-run SHA-256 checksum scans. All 55 raw files remain completely unmodified.
- **Information Leakage Prevention**: Verified that no future pavement surveys or future weather observations can be merged backward in time.
- **Determinism**: Asserted that pipeline runs generate identical row counts, sorted DataFrame values, schemas, and content fingerprints.
- **Tests and Lints**:
  - **Pytest**: $118$ tests successfully passed.
  - **Ruff**: $100\%$ clean execution (all checks passed, including import sorting and PEP-8 compliance).
