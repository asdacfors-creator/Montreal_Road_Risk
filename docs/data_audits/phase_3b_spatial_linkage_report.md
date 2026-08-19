# Phase 3B Spatial Linkage and Crosswalk Audit Report

This report summarizes the results, match rates, spatial distributions, and integrity validation for the Phase 3B spatial linkage and crosswalk construction.

---

## 1. Executive Summary

- **Pipeline Status**: SUCCESS
- **Execution Mode**: Vectorized (C++ bulk spatial overlays via shapely 2.x / pygeos)
- **Raw File Immutability Check**: Passed (0 files modified under `data/raw/`)
- **Preflight Validation (Phase 3A baseline)**: Passed (clean git working tree, no tracked raw/interim files, clean linting)
- **Serialization Read-Back Check**: Passed for all four Parquet/GeoParquet linkage datasets.
- **Unit Test Suite**: 7/7 tests passed successfully (109/109 tests passed project-wide)

---

## 2. Match Coverage & Row Counts

The table below summarizes input and output row counts and matching statistics for each dataset.

| Dataset Linkage / Campaign | Input Row Count | Output Row Count | Direct ID Matches | Spatial Fallbacks | Ambiguous (Ties) | Unmatched Count | Match Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Potholes 2016** | 13,876 | 13,876 | *N/A* | 13,856 | 1 | 19 | 99.86% |
| **Potholes 2017** | 205,437 | 205,437 | *N/A* | 205,369 | 7 | 61 | 99.97% |
| **Potholes 2018** | 199,019 | 199,019 | *N/A* | 198,929 | 17 | 73 | 99.95% |
| **Potholes 2019** | 174,856 | 174,856 | *N/A* | 174,478 | 22 | 356 | 99.78% |
| **Potholes 2020** | 81,354 | 81,354 | *N/A* | 81,255 | 10 | 89 | 99.88% |
| **Potholes 2021** | 50,320 | 50,320 | *N/A* | 49,558 | 8 | 754 | 98.49% |
| **Potholes 2022** | 72,062 | 72,062 | *N/A* | 70,881 | 12 | 1,169 | 98.36% |
| **Potholes 2023** | 105,773 | 105,773 | *N/A* | 103,372 | 30 | 2,371 | 97.73% |
| **Potholes 2024** | 50,411 | 50,411 | *N/A* | 49,614 | 5 | 792 | 98.42% |
| **Potholes 2025** | 74,159 | 74,159 | *N/A* | 73,145 | 14 | 1,000 | 98.63% |
| **Pavement 2010** | 29,271 | 29,271 | 28,009 | *N/A (Tabular)* | 0 | 1,262 | 95.69% |
| **Pavement 2015** | 30,905 | 30,905 | 29,444 | *N/A (Tabular)* | 0 | 1,461 | 95.27% |
| **Pavement 2018** | 14,114 | 14,114 | 13,336 | *N/A (Tabular)* | 0 | 778 | 94.49% |
| **Pavement 2020** | 13,876 | 13,876 | 13,663 | 203 | 7 | 3 | 99.93% |
| **Pavement 2022** | 15,821 | 15,821 | 15,755 | 63 | 3 | 0 | 99.98% |
| **Pavement 2024** | 17,176 | 17,176 | 16,999 | 166 | 10 | 1 | 99.94% |
| **Road Assets** | 47,983 | 47,983 | *N/A* | 44,166 | 40 | 3,817 | 92.05% |
| **Borough Boundaries** | 47,983 | 47,983 | *N/A* | 47,982 | 0 | 1 | 99.99% |

---

## 3. Pothole Distance & Candidate Distributions

### Snapping Distance Percentiles (overall 1,027,267 repairs)
- **50th percentile (Median)**: $3.73$ meters
- **90th percentile**: $9.43$ meters
- **95th percentile**: $11.84$ meters
- **Maximum distance**: $14,132.85$ meters (indicates outlier GPS points outside municipal boundaries)

### Candidate Count within Sensitivity Distance Bands (Cumulative)
- **Within 10m**: $940,404$ records
- **Within 15m**: $1,004,821$ records
- **Within 20m**: $1,020,583$ records
- **Within 30m**: $1,025,116$ records
- **Within 50m**: $1,026,366$ records

### Recommendation Justification
Since **95.0% of all repair points snap within 11.84 meters**, and match rate leveling occurs at 20 meters ($1,020,583$ matches), a snapping threshold of **20.0 meters** is recommended. Increasing the threshold to 30m or 50m adds negligible valid matches while significantly increasing risk of incorrect laneway assignment and coordinate error. 
All points exceeding $20.0$m ($6,684$ points) are preserved as `unmatched` with `canonical_segment_id = None`.

---

## 4. Road Asset Overlap Distributions

Pavement asset match counts evaluated at multiple candidate overlap fractions:
- **Overlap fraction $\ge 0.0$ (Any intersection)**: $44,166$ segments ($92.05\%$)
- **Overlap fraction $\ge 0.10$**: $43,878$ segments ($91.45\%$)
- **Overlap fraction $\ge 0.25$**: $43,585$ segments ($90.83\%$)
- **Overlap fraction $\ge 0.50$**: $41,363$ segments ($86.20\%$)
- **Average overlap fraction**: $75.11\%$
- **Tied cases (competing polygons)**: $40$ segments overall ($33$ ties at the recommended $0.10$ threshold)

### Recommendation Justification
A candidate threshold of **0.10** is recommended as the minimum overlap fraction. This filters out segment intersections that merely graze the boundary edges of pavement polygons (under 10% length), while preserving over 91.4% of valid polygon matches. The 10% rule identifies a primary candidate and does not prove that the road-asset polygon is historically correct for every observation date.

---

## 5. Administrative-Boundary Linkage and Cross-Check

- **Source Administrative Polygons**: $34$ total polygons ($19$ Arrondissements, $15$ Villes liées).
- **Boundary Crossing Segments (Candidate Count > 1)**: $1,205$ road segments.
- **Tied Assignments (Ambiguity Flag == 1)**: $4$ road segments.
- **Unmatched Segments**: $1$ segment (lies entirely outside municipal boundaries, matching our coordinate outlier from Géobase).
- **Assignments by Category**:
  - **Arrondissements**: $37,751$ road segments assigned.
  - **Villes liées**: $10,231$ road segments assigned.
- **Zero-Intersection Polygons**: $0$ administrative polygons intersect zero Géobase segments. All $34$ polygons ($19$ Arrondissements, $15$ Villes liées) have at least one assigned segment.
- **Comparison with ARR_GCH/ARR_DRT**:
  - Out of 47,983 segments, $37,479$ agree with the text attributes from the raw Géobase.
  - This $78.11\%$ agreement rate is descriptive only; the boundaries represent different snapshots, and spatial greatest-length assignment in projected coordinate space is used as the authoritative spatial join.
- **Discrepancy Clarification**: Previous chat summaries incorrectly reported a boundary count of $19$ instead of $34$ because they confused the count of Montréal's internal Arrondissements ($19$) with the total administrative boundaries of the Montréal Agglomeration ($34$), which includes both Arrondissements and Villes liées. Both Phase 3A and Phase 3B correctly processed all $34$ boundary polygons in code.

---

## 6. Verification & Pipeline Artifacts Created

### Output Files Generated
1. `data/interim/phase_3b/pothole_segment_links.parquet` ($1,027,267$ rows)
2. `data/interim/phase_3b/pavement_condition_segment_links.parquet` ($121,163$ rows)
3. `data/interim/phase_3b/road_asset_segment_crosswalk.parquet` ($47,983$ rows)
4. `data/interim/phase_3b/road_boundary_crosswalk.parquet` ($47,983$ rows)
5. `data/interim/phase_3b/linkage_qa_summary.json`
6. `data/interim/phase_3b/phase_3b_run_manifest.json`

### Verification Checks Passed
- **JSON Validation**: Config parses successfully using standard json validation.
- **Ruff Inquiries**: Zero syntax or format warnings.
- **Parquet Roundtrip**: Read-back check confirmed that file length, schema, and values are identical to data before serialization.
