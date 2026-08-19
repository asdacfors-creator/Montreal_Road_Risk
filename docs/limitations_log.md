# Montreal Road Risk — Project Limitations Log

| Field | Value |
| :--- | :--- |
| **Document purpose** | Limitations and Assumptions Log |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 5 — Baselines and Classification Models (Closed) |
| **Status** | In Progress |
| **Last updated** | 2026-07-19 |
| **Source of truth** | Phase 5 Closure and Model Selection |
| **Next review** | Phase 6 Calibration |

---

## Executive Summary

This log documents the fundamental limitations, data biases, and modeling assumptions identified during Phase 0 and Phase 2. It tracks their operational consequences, mitigations, and final report documentation status.

---

## Project Limitations Log Table

| ID | Limitation | Evidence Status | Consequence | Mitigation | Report Location | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **L0.1** | Target variable represents administrative actions, not physical state | Verified from proposal proxy limits | Model predicts repair occurrence, not physical pavement cracking directly. | Explicitly document target definition; combine predictions with criticality. | Chapter 4 (Methodology) | Approved |
| **L0.2** | Spatial snapping tolerance is not fixed | Pending real-data inspection | Snapping coordinates to lines may assign events to wrong road lanes. | Test candidate snapping tolerances (10m, 25m, 50m) in Phase 3. | Chapter 3 (Data Preprocessing) | Pending |
| **L0.3** | Target prevalence is currently unknown | Pending real-data inspection | Class imbalance ratio is unknown, making evaluation metrics sensitive. | Record as unknown until panel is audited; use PR-AUC and Precision-at-K. | Chapter 5 (Results) | Pending |
| **L0.4** | Traffic volume data missingness | Coverage & missingness unknown | Direct counts may be unavailable for minor streets, biasing criticality. | Impute missing traffic categories using functional class proxy. | Chapter 3 (Data Preprocessing) | Pending |
| **L0.5** | Pavement age (asset dates) missingness | Coverage & missingness unknown | Missing construction/resurfacing dates will affect road age features. | Impute missing dates using functional class and borough medians. | Chapter 3 (Data Preprocessing) | Pending |
| **L0.6** | Pavement quality (PCI/IRI) coverage | Coverage & missingness unknown | Condition scores may be blank for local roads or require interpolation. | Inspect campaign coverage; apply temporal forward-carry or drop features. | Chapter 3 (Data Preprocessing) | Pending |
| **L0.7** | Weather station aggregation uncertainty | Pending real-data inspection | Station coverage might require spatial interpolation or airport proxy. | Test aggregates (nearest station, area average, IDW) in Phase 5. | Chapter 3 (Data Preprocessing) | Pending |
| **L0.8** | Géobase segment identifier schema | Pending real-data inspection | Real segment ID remains conceptual (`segment_id`) until schema is confirmed. | Inspect database schema in Phase 2 to map to physical key. | Chapter 3 (Data Preprocessing) | Pending |
| **L0.9** | Project schedule | Verified deadline (Aug 7, 2026) | Insufficient time to implement all advanced options simultaneously. | Strict time tracking; defer optional Survival Analysis stretch goal. | Chapter 1 (Introduction) | Approved |
| **L2.1** | 2019 mechanized-repair exact-duplicate anomaly | 31858 groups, 83280 rows, 51422 excess rows | Inflated repair counts, target inflation, evaluation/prioritisation bias | Raw file unchanged, no Phase 2 deduplication, lock target construction | docs/data_audits/pothole_repairs_2019_audit.md | Open |
| **L2.2** | 2020 mechanized-repair incomplete temporal coverage | Records only Jan 14 - Mar 20 (81354 rows) | Distorts seasonality features, target construction lacks rest of 2020 | Document limitation, matching only active periods, do not assume full year | docs/data_audits/pothole_repairs_2020_audit.md | Open |
| **L2.3** | Cross-year CRS and schema transition in 2021–2025 GPKGs | CSV to GPKG format, column shift, WGS 84 vs EPSG:2950 | Spatial query/grouping failures, vehicle matching failures | Reproject 2021 custom WGS 84 coordinates to EPSG:2950; normalize vehicle IDs; project-wide CRS not approved yet | docs/data_audits/pothole_repairs_2021_2025_gpkg_cross_year_audit.md | Open |
| **L2.4** | GPKG annual files (2021–2025) lack complete temporal coverage | All five GPKG files contain massive data gaps in summer/fall campaign periods | Cannot evaluate model or target construction during unobserved months | Restrict target panel construction to observed calendar ranges across years | docs/data_audits/pothole_repairs_2021_2025_gpkg_cross_year_audit.md | Open |
| **L2.5** | 2023 mechanized-repair layer-naming and out-of-year anomalies | Internal layer named `remplissage_niddepoule_2024`, one 2022 record | Pipeline failures if layer names are hardcoded; out-of-year records | Use dynamic layer discovery; do not modify raw records or layer names in Phase 2 | docs/data_audits/pothole_repairs_2023_audit.md | Open |
| **L2.6** | 2021 spatial-envelope exceptions | 5 events fall outside the axis-aligned bounding envelope of the current Géobase road-network snapshot | May cause erroneous exclusions of valid boundary-edge repairs | Points are not automatically invalid; defer spatial investigation to Phase 3 | docs/data_audits/pothole_repairs_2021_audit.md | Open |
| **L2.7** | Chronological split remains unapproved | Temporal coverage gaps across 2016-2025 | Biased evaluations; cannot train/test continuously | Common coverage weather/assets not established; do not hardcode train/val/test splits yet | docs/data_audits/pothole_repairs_2021_2025_gpkg_cross_year_audit.md | Open |
| **L2.8** | Road-assets construction-date precision uncertainty | 88.57% of construction dates are unknown or imprecise (+/- 100 years) | Highly imprecise age calculations at the segment level | Use broad construction-era bins instead of exact age features in Phase 5 | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.9** | Road-assets high resurfacing-date missingness | 86.74% (55,535 features) have null resurfacing dates | Surface age cannot be calculated directly for most segments | Implement a binary resurfacing-availability flag in Phase 5; do not impute dates | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.10** | Unverified road-assets-to-Géobase relationship | Road-assets uses `ID_VOI_CHAUSSEE_AGR` while Géobase uses `ID_TRC` | Direct ID matching is impossible, causing join failures | Implement buffer-based spatial intersection overlays in Phase 3 | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.11** | No explicit CRS member in road-assets GeoJSON | Raw GeoJSON lacks a `crs` member | Coordinate mismatch risks if projection parameters are assumed | Handle as geographic coordinates in Phase 3 and reproject to MTM8 | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.12** | Road-assets date-logic anomalies | 133 records have resurfacing dates registered before construction dates | May cause negative duration or logic failures in feature engines | Document anomalies; flag or ignore raw order inconsistency during panel build | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.13** | Reference-field alias between MATERIAUCHAUSSEE_REF and MATERIAU_REF | GeoJSON uses `MATERIAUCHAUSSEE_REF` while CSV uses `MATERIAU_REF` | Inability to map categories directly without alias parsing | Map observed values to `MATERIAU_REF` using alias mapping in scripts | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.14** | Potential stale or uneven territorial road-asset updates | Varying updates or reporting delays across boroughs | Spatial bias in age and material features | Add categorical borough and owner features to control for reporting bias | docs/data_audits/road_assets_pavement_audit.md | Open |
| **L2.15** | 2010-labelled campaign spans 2009–2011 | DateReleve coverage | Survey dates are not limited to 2010, violating strict temporal year assumptions | Use exact survey date (`DateReleve`) for temporal alignment, not label | docs/data_audits/pavement_condition_2010_audit.md | Open |
| **L2.16** | Campaigns have different network scopes | Complete vs Arterial vs Local | Biased comparison across years if scope is not controlled | Map scope explicitly and restrict comparisons within same network hierarchies | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L2.17** | Surveys are irregular and not annual | Survey campaigns occur irregularly | Temporal interpolation errors; stale metrics for some segment-months | Compute and include survey staleness/age as a feature in Phase 5 | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L2.18** | Cross-resource format and encoding differences | CSV vs GeoJSON vs GPKG; CP1252 vs UTF-8 | Ingestion pipeline failure or character corruption | Apply format-specific parsers; open 2020 GeoJSON strictly with CP1252 | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L2.19** | CRS differences across spatial resources | WGS 84 (4326) vs MTM 8 (32188) | Spatial join or coordinates comparison failures | Standardize all spatial condition assets to a uniform project CRS in Phase 3 | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L2.20** | Historical ID_TRC values do not match current Géobase | Match rates between ~94.49% and 99.58% | Loss of historical segment-months or missing condition scores for ~1-5% of segments | Handle as unmatched-ID indicator in Phase 5; do not discard records | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L2.21** | 2020 contains 99 exact duplicate excess records | 99 duplicate feature/ID rows in 2020 GeoJSON | Double counting of condition state, target inflation | Defer deduplication policy until Phase 3 join effects are assessed | docs/data_audits/pavement_condition_2020_audit.md | Open |
| **L2.22** | 2020 contains 1,326 IRI sentinel candidates | 1,326 records with Indice_IRI = 0 and Etat_IRI = "-" | Treating sentinels as actual zero roughness biases models | Handle as missingness indicators in Phase 5; do not convert to 0 | docs/data_audits/pavement_condition_2020_audit.md | Open |
| **L2.23** | IRI missingness varies by campaign | Missingness ranges from 0.00% to 9.24% | Missing feature data on segments, biased comparisons | Handle missingness using indicators and robust imputation in Phase 5 | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L2.24** | Very high IRI observations require robustness assessment | Maximum IRI of 72.7 observed in 2010 | Extreme outliers could skew regression models | Preserved during Phase 2; assess clipping or robust scaling in Phase 5 | docs/data_audits/pavement_condition_2010_audit.md | Open |
| **L2.25** | Future-survey leakage risk | Inadvertent backfilling of future surveys | Information leakage from the future violating temporal order | Enforce strict chronological cutoff: DateReleve must be <= observation date | docs/leakage_prevention.md | Open |
| **L2.26** | Local and arterial campaigns must not be treated as citywide snapshots | 2022 local vs 2024 arterial scope | Overlap is only 28 IDs; consecutive years are not comparable | Use separate network indicators and distinct campaign alignments | docs/data_audits/pavement_condition_cross_year_audit.md | Open |
| **L6.1** | B1 calibration partition spans winter/spring months only (2024-01-31 to 2024-03-31) | Approved Gate B1 split manifest | Probability predictions may exhibit seasonal calibration bias if summer/fall repair/weather patterns vary. | Document seasonality limitations; maintain rank-based Top-K operational thresholds. | docs/phase_6_gate_b1_report.md | Approved |
| **L6.2** | 180-day final-test evaluation excluded due to procedural target decoding breach in initial Gate B1 run | Documented protocol deviation report (`docs/phase_6_gate_b1_protocol_deviation.md`) | 180-day final test evaluation target seal was procedurally compromised. | 180-day final-test evaluation is permanently excluded from Phase 6. Gate B2 is restricted to 90-day evaluation. | docs/phase_6_gate_b1_protocol_deviation.md | Approved |
| **L6.3** | Gate B2 evaluation restricted to primary 90-day model and 11 B2 anchors | Approved Gate B2 authorization & evaluation manifest | 180-day final-test metrics unavailable; evaluation results apply only to 90-day horizon across 2024-07 to 2025-05. | Complete 500-repetition segment-cluster bootstrap CIs provided for all primary metrics (AP=0.505693, ROC-AUC=0.920953). | docs/phase_6_evaluation_report.md | Approved |
| **L6.4** | Gate B2 evaluation involved repeated target access (`access_count = 2`, classification `B_REPEATED_PROCEDURAL_ACCESS`) due to task-12084 failure post-open | Documented repeated access deviation report (`docs/phase_6_gate_b2_repeated_access_deviation.md`) | Gate B2 target columns were loaded twice before single final result set was computed by task-12097. | Preserved single numerical result set; documented deviation in `gate_b2_repeated_access_deviation.json`; hardened seal guard. | docs/phase_6_gate_b2_repeated_access_deviation.md | Approved |
| **L7.1** | SHAP values describe model attribution and feature association only; they do not establish physical causality or intervention effects | Mandated causality statement (`shap_engine.py`) | Stakeholders might misinterpret SHAP contributions as physical repair guarantees. | Mandatory causality disclaimers embedded in all plots, reports, and code modules; output labeled 'risk-priority candidates'. | docs/phase_7_gate_7a_report.md | Approved |
| **L7.2** | Background-free SHAP tree path calculation scale is raw log-odds margin, requiring non-linear sigmoid mapping to probability space | XGBoost `pred_contribs=True` | Linear SHAP sum does not equal probability directly (additivity holds on raw log-odds scale). | Verified exact log-odds additivity (max residual 3.81e-6) and exact probability read-back via sigmoid mapping. | docs/phase_7_gate_7a_report.md | Approved |
| **L8.1** | Web map Leaflet rendering capacity is limited to 5,000 active segment polylines per viewport for interactive performance (< 1.0s) | Performance benchmark (`map_builder.py`) | Rendering all 47,983 citywide segments simultaneously in Leaflet DOM degrades browser responsiveness. | Performance warning banner displayed if filter matches > 5,000 segments; users advised to narrow borough or priority band. | docs/phase_8_gate_8a_report.md | Approved |

---

## Detailed Limitation Registry

### L2.1: 2019 Mechanized-Repair Exact-Duplicate Anomaly

* **Status**: Open
* **Evidence**:
  * 31,858 exact-duplicate groups
  * 83,280 participating rows
  * 51,422 excess rows (29.4082% excess-row rate)
  * 51,152 adjacent identical excess occurrences
  * 99.4749% of excess occurrences adjacent
* **Potential impact**:
  * Inflated repair-event counts, target inflation, biased evaluation and prioritisation.
* **Current control**:
  * Raw file preserved unchanged; no deduplication in Phase 2; target construction remains locked.
* **Resolution plan**:
  * Compare duplicate mechanisms across years, define duplicate policy, sensitivity analysis.

### L2.2: 2020 Mechanized-Repair Incomplete Temporal Coverage

* **Status**: Open
* **Evidence**:
  * Records span only from `2020-01-14` to `2020-03-20` (81,354 rows).
  * April through December have zero records.
* **Potential impact**:
  * Incomplete representation of seasonal deterioration patterns; distorted annual rate calculations.
* **Current control**:
  * Raw file preserved unchanged; target construction remains locked; 2020 must not be treated as a complete calendar year.
* **Resolution plan**:
  * Document temporal alignment rules; exclude unobserved periods in 2020 from modeling.

### L2.3: Cross-Year CRS and Schema Transition in 2021–2025 GPKGs

* **Status**: Open
* **Evidence**:
  * CSV to GPKG transition.
  * Column shift: `Appareil` (2016–2020 CSVs) to `Véhicule` (2021–2025 GPKGs).
  * 2021 uses custom WGS 84 SRS entry with `srs_id 100000` and organization `NONE` (not described as formally declared EPSG:4326).
  * 2022–2025 use EPSG:2950 (NAD83 (CSRS) / MTM zone 8).
  * Project-wide working CRS has not been approved yet.
* **Potential impact**:
  * Spatial query and grouping mismatches if not standardized. Disjointed device-specific analysis.
* **Current control**:
  * Raw files remain unmodified. Verification logs record coordinate systems and formats.
* **Resolution plan**:
  * Reproject 2021 layer to MTM Zone 8 (EPSG:2950) in Phase 3. Normalize vehicle ID strings (drop hyphens).

### L2.4: Annual Temporal Campaign Gaps in 2021–2025 GPKGs

* **Status**: Open
* **Evidence**:
  * 2021 ends in March (2021-03-17).
  * 2022 has large missing periods (zero records June–October).
  * 2023 ends in May.
  * 2024 ends in May.
  * 2025 ends on 20 May.
  * Annual files cannot be treated as complete calendar years.
* **Potential impact**:
  * Lack of continuous temporal observations for deterioration models.
* **Current control**:
  * Documented in cross-year audit report.
* **Resolution plan**:
  * Align target construction and temporal aggregations strictly with observed campaigns.

### L2.5: Layer-Year and Record-Year Anomalies in GPKGs

* **Status**: Open
* **Evidence**:
  * 2023 file internally names its layer as `remplissage_niddepoule_2024`.
  * 2023 file contains one 2022 record (`2022-12-20`).
  * 2024 file contains four 2023 records.
  * Raw records and layer names remain unchanged.
* **Potential impact**:
  * Ingestion pipeline failures or manual configuration overhead.
* **Current control**:
  * Dynamic layer discovery is implemented in auditor.
* **Resolution plan**:
  * Ensure downstream ingestion code uses layer discovery rather than hardcoded string matching.

### L2.6: 2021 Spatial-Envelope Exceptions

* **Status**: Open
* **Evidence**:
  * Five 2021 repair points fall outside the axis-aligned bounding envelope of the current Géobase road-network snapshot: one point is east of the envelope and four points are south of it. This observation does not prove that the points fall outside Montréal or outside any borough. Administrative-boundary validity remains unassessed until an authoritative boundary layer is acquired and a polygon containment test is performed during the authorized GIS-processing phase.
  * They are not automatically invalid.
* **Potential impact**:
  * Inability to snap to road segments in the geobase network.
* **Current control**:
  * Raw files and coordinates remain unmodified; their exact coordinates and identifiers are preserved.
* **Resolution plan**:
  * Defer spatial investigation of these points to Phase 3.

### L2.7: Chronological Split Remains Unapproved

* **Status**: Open
* **Evidence**:
  * 2016 is partial (ends in December).
  * 2017–2019 contain major temporal gaps.
  * 2020 and 2021 end in March.
  * 2022–2024 contain gaps or cross-year records.
  * 2025 ends in May.
  * Common coverage with weather, pavement condition, traffic, and asset data has not been established.
* **Potential impact**:
  * Temporal leakage or evaluation bias if train/val/test splits are hardcoded prematurely.
* **Current control**:
  * No train/validation/test split dates may be hardcoded yet.
* **Resolution plan**:
  * Evaluate other datasets' temporal bounds in Phase 2 before proposing split dates.

### L2.8: Road-Assets Construction-Date Precision Uncertainty

* **Status**: Open
* **Evidence**:
  * 88.57% of construction dates in the road-assets GeoJSON are flagged as highly imprecise (+/- 100 years max: 20,880 rows) or unknown (Inconnu: 35,830 rows).
* **Potential impact**:
  * Highly inaccurate age features if parsed directly as exact years, leading to noise in deterioration model calculations.
* **Current control**:
  * Raw values and precision identifiers are preserved without cleaning in Phase 2.
* **Resolution plan**:
  * Group segments into broad construction-era categorical bins (e.g. Pre-1950, 1950-1980, Post-1980) rather than exact year differences in Phase 5.

### L2.9: Road-Assets High Resurfacing-Date Missingness

* **Status**: Open
* **Evidence**:
  * 86.74% (55,535 features out of 64,025) have null values in `DATERESURFACAGE`.
* **Potential impact**:
  * Inability to compute elapsed years since the last resurfacing for the vast majority of segments.
* **Current control**:
  * Missing dates remain null and are not replaced, filled, or defaulted in Phase 2.
* **Resolution plan**:
  * Implement a binary flag indicating whether resurfacing history is available for the segment. Defer any interpolation or imputation to Phase 5.

### L2.10: Unverified Road-Assets-to-Géobase Relationship

* **Status**: Open
* **Evidence**:
  * The road-assets features are identified by `ID_VOI_CHAUSSEE_AGR` while Géobase segments use `ID_TRC`. No common attribute joins are documented.
* **Potential impact**:
  * Attribute matching failures if direct tabular joins are attempted.
* **Current control**:
  * Raw geometries and identifiers are preserved without joining.
* **Resolution plan**:
  * Implement buffer-based spatial intersection overlays in Phase 3 to map road-asset polygons to nearest Géobase line segments.

### L2.11: No Explicit CRS Member in Road-Assets GeoJSON

* **Status**: Open
* **Evidence**:
  * The raw GeoJSON archive member contains no top-level `crs` dictionary.
* **Potential impact**:
  * Spatial misalignment and coordinate mismatches if coordinates are projected or mapped under assumed reference systems.
* **Current control**:
  * Raw coordinate strings remain unprojected.
* **Resolution plan**:
  * Read as geographic coordinates (WGS 84) and explicitly reproject to MTM Zone 8 (EPSG:2950) in Phase 3.

### L2.12: Road-Assets Date-Logic Anomalies

* **Status**: Open
* **Evidence**:
  * 133 features have a resurfacing date that precedes their registered construction date (e.g. construction year recorded after resurfacing year).
* **Potential impact**:
  * Logical inconsistencies (negative duration) in feature extraction.
* **Current control**:
  * Raw dates remain unmodified.
* **Resolution plan**:
  * Flag anomalous records during panel feature construction; either ignore the resurfacing date or set to null when computing intervals.

### L2.13: Reference-Field Alias Between MATERIAUCHAUSSEE_REF and MATERIAU_REF

* **Status**: Open
* **Evidence**:
  * The GeoJSON uses the attribute name `MATERIAUCHAUSSEE_REF` whereas the reference value CSV domain uses `MATERIAU_REF`.
* **Potential impact**:
  * Category lookups will fail if exact column matches are expected.
* **Current control**:
  * Raw attribute names and values are preserved.
* **Resolution plan**:
  * Implement mapping alias translations in ingestion scripts.

### L2.14: Potential Stale or Uneven Territorial Road-Asset Updates

* **Status**: Open
* **Evidence**:
  * Road asset updates and reporting are administered by individual local boroughs, which may lead to varying update schedules or stale entries.
* **Potential impact**:
  * Spatial bias in age and material features, leading to model predictions reflecting administrative reporting differences rather than physical risk.
* **Current control**:
  * Borough and owner categorical variables are preserved.
* **Resolution plan**:
  * Add categorical borough (`PROPRIETAIRE_REF`) and road class features to model partitions to help control for reporting biases.

### L2.15: 2010-Labelled Campaign Spans 2009–2011

* **Status**: Open
* **Evidence**:
  * The dataset is labeled as 2010, but actual survey timestamps span `2009-09-15` through `2011-07-26`.
* **Potential impact**:
  * Violates strict temporal assumptions if the survey year is hardcoded to 2010.
* **Current control**:
  * Raw DateReleve entries are kept.
* **Resolution plan**:
  * Align surveys based on their exact `DateReleve` field, not the aggregate campaign label.

### L2.16: Campaigns Have Different Network Scopes

* **Status**: Open
* **Evidence**:
  * 2010 and 2015 cover the complete network, while 2018, 2020, and 2024 cover the arterial network only, and 2022 covers the local network only.
* **Potential impact**:
  * Biased cross-year comparisons and inconsistent network evaluations if network scopes are not controlled.
* **Current control**:
  * Scopes are identified and documented.
* **Resolution plan**:
  * Group segments by functional class and restrict comparison within the same hierarchy (local vs. arterial).

### L2.17: Surveys are Irregular and Not Annual

* **Status**: Open
* **Evidence**:
  * Inconsistent campaign intervals (2010, 2015, 2018, 2020, 2022, 2024).
* **Potential impact**:
  * Temporal interpolation errors; stale condition score representation for some months.
* **Current control**:
  * No imputation or interpolation in Phase 2.
* **Resolution plan**:
  * Compute and include survey age/staleness as a feature.

### L2.18: Cross-Resource Format and Encoding Differences

* **Status**: Open
* **Evidence**:
  * CSV formats (UTF-8, no BOM) for 2010, 2015, 2018. GeoJSON (CP1252) for 2020. GeoPackages (binary SQLite) for 2022, 2024.
* **Potential impact**:
  * Ingestion pipeline failure, encoding/parsing errors.
* **Current control**:
  * Format-specific logic created inside scripts/audit_pavement_condition.py.
* **Resolution plan**:
  * Maintain separate custom reader interfaces for each campaign type.

### L2.19: CRS Differences Across Spatial Resources

* **Status**: Open
* **Evidence**:
  * 2020 uses WGS 84 (CRS84). 2022 uses WGS 84 (EPSG:4326). 2024 uses Projected MTM 8 (EPSG:32188).
* **Potential impact**:
  * Spatial join failures if projections are not aligned.
* **Current control**:
  * Files remain in their source coordinate systems.
* **Resolution plan**:
  * Explicitly reproject all spatial files to a single working CRS (e.g. MTM 8) in Phase 3.

### L2.20: Historical ID_TRC Values Do Not Match Current Géobase

* **Status**: Open
* **Evidence**:
  * Unmatched IDs range from 66 (2022 local) to 1,461 (2015 complete). Match rate varies from 94.49% to 99.58%.
* **Potential impact**:
  * Loss of historical segment condition coverage for unmatched nodes.
* **Current control**:
  * Raw IDs are preserved.
* **Resolution plan**:
  * Defer resolution to Phase 3. Create an unmatched ID indicator feature in Phase 5.

### L2.21: 2020 Contains 99 Exact Duplicate Excess Records

* **Status**: Open
* **Evidence**:
  * 99 exact feature duplicates and duplicate ID_TRCs in the 2020 GeoJSON resource.
* **Potential impact**:
  * Overcounting repair risk and target inflation.
* **Current control**:
  * Defer duplicate resolution.
* **Resolution plan**:
  * Assess join outcomes and establish a deduplication logic in Phase 3.

### L2.22: 2020 Contains 1,326 IRI Sentinel Candidates

* **Status**: Open
* **Evidence**:
  * 1,326 features in 2020 have `Indice_IRI = 0` and `Etat_IRI = "-"`.
* **Potential impact**:
  * Treating these zeros as actual zero roughness biases risk models.
* **Current control**:
  * Flagged and isolated in the auditor.
* **Resolution plan**:
  * Model sentinels as missing values in Phase 5; do not convert to zero.

### L2.23: IRI Missingness Varies by Campaign

* **Status**: Open
* **Evidence**:
  * 0.00% missing in 2010/2015, 0.11% in 2018, 9.24% in 2022, and 4.59% in 2024.
* **Potential impact**:
  * Missing features during prediction, bias.
* **Current control**:
  * Missing values left as is.
* **Resolution plan**:
  * Design a robust missingness indicator and imputation scheme in Phase 5.

### L2.24: Very High IRI Observations Require Robustness Assessment

* **Status**: Open
* **Evidence**:
  * IRI of 72.7 observed in 2010.
* **Potential impact**:
  * Extreme outliers skew regression predictions.
* **Current control**:
  * Outlier preserved in raw format.
* **Resolution plan**:
  * Assess clipping or robust scaling methods in Phase 5.

### L2.25: Future-Survey Leakage Risk

* **Status**: Closed
* **Evidence**:
  * Physical pavement survey scores backfilled into historical segments.
* **Potential impact**:
  * Information leakage from future condition measurements, violating temporal order.
* **Current control**:
  * Strict temporal boundary checking rule enforced in Phase 3C (`DateReleve <= observation cutoff`).
* **Resolution plan**:
  * closed in Phase 3C.

### L2.26: Local and Arterial Campaigns Must Not Be Treated as Citywide Snapshots

* **Status**: Open
* **Evidence**:
  * 2022 local covers only the local network; 2024 arterial covers only the arterial network. They share only 28 segment IDs.
* **Potential impact**:
  * Erroneously assuming a citywide annual update between 2022 and 2024.
* **Current control**:
  * Documented scope splits.
* **Resolution plan**:
  * Use separate network indicator flags and distinct campaign alignments.

### L2.27: Current Administrative Boundary Snapshot vs Historical Observations

* **Status**: Open
* **Evidence**:
  * Boundaries GeoJSON last updated on 2023-11-29.
  * Historical road-repair events start in 2016.
* **Potential impact**:
  * Municipal reorganizations or boundary adjustments between 2016 and 2023 may cause spatial assignment errors.
* **Current control**:
  * Raw geometries preserved.
* **Resolution plan**:
  * Treat as stationary partition unless historical boundary versions are acquired in subsequent phases.

### L2.28: Distinction Between Montréal Boroughs and Related Municipalities

* **Status**: Open
* **Evidence**:
  * 15 features in the dataset are classified as related municipalities (TYPE = "Ville liée"), and 19 features are boroughs (TYPE = "Arrondissement").
* **Potential impact**:
  * Erroneously combining related municipalities with boroughs in a unified borough-level analysis.
* **Current control**:
  * Separate entity lists documented in the audit report.
* **Resolution plan**:
  * Exclude related municipalities from borough-level aggregation or handle them separately under a unified agglomeration-level partition.

### L2.29: Boundary-Crossing Road Segment Assignments

* **Status**: Closed
* **Evidence**:
  * 1,205 Géobase road features intersect more than one administrative polygon in memory.
* **Potential impact**:
  * Ambiguity in segment-to-borough assignments, leading to double-counting or segment assignment drift.
* **Current control**:
  * Greatest length intersection spatial join implemented and locked in Phase 3B.
* **Resolution plan**:
  * Closed in Phase 3B.

### L2.30: Unvalidated Alternative Coordinate Transformations

* **Status**: Open
* **Evidence**:
  * Ville de Montréal recommends working in the native NAD83 / MTM Zone 8 reference system.
  * City states alternative coordinate transformations supplied on the portal are not validated by the geomatics division.
* **Potential impact**:
  * Spatial inaccuracies or distortion if alternative coordinates (e.g. WGS 84 versions) are used without validation.
* **Current control**:
  * Native NAD83 MTM Zone 8 GeoJSON resource downloaded.
* **Resolution plan**:
  * Use the native reference system coordinates or perform validated coordinate transformations within our GIS pipelines.

### L2.31: Approved Project-Wide Coordinate Reference System (CRS) Undecided

* **Status**: Open
* **Evidence**:
  * Datasets use varying systems (EPSG:4326, custom 100000, EPSG:2950, and EPSG:32188).
* **Potential impact**:
  * Incompatible overlays and matching errors if layers are joined in mixed coordinates.
* **Current control**:
  * Standard projection is deferred; all files are kept in native formats.
* **Resolution plan**:
  * Select and approve a single working projected CRS (candidate: EPSG:2950 or EPSG:32188) in Phase 3.

### L2.32: Point-Station Observations Used as Montréal-Wide Exposure Proxies

* **Status**: Open
* **Evidence**:
  * Temperature and precipitation features are constructed using only two specific station points (McTavish and Montréal-Trudeau) for the entire island.
* **Potential impact**:
  * Assumes climate homogeneity across the island, ignoring local microclimate variations.
* **Current control**:
  * Native station datasets kept separate.
* **Resolution plan**:
  * Standardize using primary McTavish data and evaluate spatial interpolation sensitivity in Phase 3.

### L2.33: Microclimate Spatial Variations Across the Island

* **Status**: Open
* **Evidence**:
  * Mean temperature difference between McTavish (urban/central) and Montréal-Trudeau (airport/suburban) is 0.426°C.
* **Potential impact**:
  * Inaccuracies in freeze-thaw counts or temperature estimates for segments far from the McTavish station.
* **Current control**:
  * Both station datasets are preserved in raw folders.
* **Resolution plan**:
  * Test distance-weighted spatial interpolation (IDW) against single-station assignment in Phase 3.

### L2.34: McTavish Missing Precipitation Periods

* **Status**: Open
* **Evidence**:
  * McTavish has 375 missing Total Precip records (6.0396% missingness rate).
* **Potential impact**:
  * Missing predictor values during modeling, causing sample drop or biased imputation.
* **Current control**:
  * Missing values left as is in raw format.
* **Resolution plan**:
  * Define a temporal fallback policy in Phase 3 to impute McTavish missing precipitation using Trudeau observations.

### L2.35: Montréal-Trudeau Historical Temperature Gaps

* **Status**: Open
* **Evidence**:
  * Montréal-Trudeau has 776 missing mean temperature records (12.498% missingness rate).
* **Potential impact**:
  * Reduced reliability of Trudeau as a secondary temperature fallback.
* **Current control**:
  * Trudeau is designated as secondary comparison/backup only.
* **Resolution plan**:
  * Only use Trudeau to fill McTavish missing days where Trudeau itself is non-missing.

### L2.36: Rainfall and Snowfall Components Unavailable

* **Status**: Open
* **Evidence**:
  * McTavish Total Rain and Total Snow are 100% missing. Montréal–Trudeau Total Snow is 100% missing, while Total Rain has only 23 populated observations and 6,186 missing observations (99.63% missing).
* **Potential impact**:
  * Inability to evaluate liquid vs solid precipitation effects separately.
* **Current control**:
  * Rain and snow columns are isolated and must not be used.
* **Resolution plan**:
  * McTavish Total Rain and Total Snow are 100% missing. Montréal–Trudeau Total Snow is 100% missing, while Total Rain has only 23 populated observations and 6,186 missing observations (99.63% missing). Therefore, the separate Total Rain and Total Snow fields are not suitable as consistent cross-year features. Total Precip is the usable precipitation measurement, subject to its documented missingness.

### L2.37: Snow-on-Ground Incompleteness

* **Status**: Open
* **Evidence**:
  * Snow on Ground has over 70% missingness at both stations.
* **Potential impact**:
  * Impedes the calculation of snow insulation features for winter pavement models.
* **Current control**:
  * Missing values left in raw files.
* **Resolution plan**:
  * Evaluate whether to discard the snow-on-ground feature or apply a seasonal imputation policy in Phase 3.

### L2.38: ECCC Retrospective Revisions

* **Status**: Open
* **Evidence**:
  * ECCC retrospectively adjusts daily climate logs on the portal when historical quality controls are run.
* **Potential impact**:
  * Slight variation in files retrieved at different dates.
* **Current control**:
  * Retrieval date (2026-07-16) and SHA-256 hashes are strictly recorded in the manifest.
* **Resolution plan**:
  * Treat the current data manifest as the immutable baseline.

### L2.39: Station-ID Mutability

* **Status**: Open
* **Evidence**:
  * Station IDs are internal ECCC indicators and can change over time.
* **Potential impact**:
  * Broken download links or mapping queries in subsequent runs.
* **Current control**:
  * Climate IDs (stable identifiers) are stored in manifests and data sources.
* **Resolution plan**:
  * Always resolve station queries using Climate IDs in Phase 3.

### L2.40: Freeze-Thaw Definition Not Yet Finalized

* **Status**: Open
* **Evidence**:
  * Three different candidate freeze-thaw counts were evaluated in the audit (Def 1, Def 2, Def 3).
* **Potential impact**:
  * Ambiguity in pavement deterioration feature definition.
* **Current control**:
  * Only candidate counts are reported; no feature engineering has occurred.
* **Resolution plan**:
  * Evaluate the predictive sensitivity of all three candidate definitions during Phase 5 feature selection.

### L2.41: Weather Features Must Obey Observation Cutoffs

* **Status**: Closed
* **Evidence**:
  * Segment-month paneled features require strict causal alignment.
* **Potential impact**:
  * Risk of information leakage if weather occurring in the target window is used as a predictor.
* **Current control**:
  * Enforced programmatically in Phase 3C (`Date <= observation cutoff`).
* **Resolution plan**:
  * Closed in Phase 3C.

### L2.42: Imprecise Construction and Resurfacing Dates for Road Assets

* **Status**: Closed
* **Evidence**:
  * Over 88% of construction dates represent year-only, approximate, or unknown values (with exactly 40 precise construction dates and 7,132 precise resurfacing dates).
* **Potential impact**:
  * Year-only dates are mapped to January 1st as a computational lower bound, introducing temporal uncertainty.
* **Current control**:
  * Explicit precision status flags (`precise`, `imprecise_year`, `approximate_interval`, `unknown`, `missing`) and proxy indicators are carried forward to prevent downstream exact-day assumptions.
* **Resolution plan**:
  * Closed in Phase 3C.

### L2.43: America/Toronto Timezone Context Assumption

* **Status**: Closed
* **Evidence**:
  * Source timestamps lack explicit timezone offsets.
* **Potential impact**:
  * Potential temporal shifts during DST transitions if naive local times are forced to UTC.
* **Current control**:
  * America/Toronto assumed. Naive dates/times preserved. Timezone localization status flags (`ambiguous_dst`, `nonexistent_dst`) tracked without silent shifts.
* **Resolution plan**:
  * Closed in Phase 3C.

---

## Phase Gate

To transition to Phase 6, the limitations log must be approved.

* [x] Limitations table populated.
* [x] Consequence and mitigations defined.
* [x] Temporal pre-processing limitations recorded and closed.
* [x] Phase 5 model-selection limitations recorded.
* [x] Supervisor approval received (2026-07-19).

---

## Phase 5 — Modeling Limitations (added 2026-07-19)

| ID | Limitation | Evidence Status | Consequence | Mitigation | Report Location | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **L5.1** | Full-data XGBoost training requires external-memory streaming on 16 GB machine | Verified: dense load caused 7.25 GB RSS → OOM abort | Training cannot be reproduced with a simple pandas.read_parquet call | Use xgb.ExtMemQuantileDMatrix with ParquetFile.iter_batches; documented in scripts/phase_5_full_train_xgb_external_memory.py | Phase 5 validation report | Mitigated |
| **L5.2** | No independent full-training determinism rerun was performed under Phase 5 closure authorization | Architectural decision: retraining not authorized; only artifact read-back confirmed | Cannot claim bit-exact independent training reproducibility | Read-back allclose=True, max_diff=0.00e+00 confirms artifact determinism; independent rerun requires separate authorization | Phase 5 validation report | Documented |
| **L5.3** | Frozen preprocessor fitted on 1M-row stratified subsample rather than all 3.4M rows | Deliberate design: prevents preprocessing leakage; ensures schema compatibility | Preprocessor may not capture the full distribution of rare categories in the 3.4M panel | Acceptable trade-off: frozen preprocessor is deterministic and leakage-safe; Phase 6 may revisit | Phase 5 validation report | Accepted |
| **L5.4** | Full-data model Brier score (0.029702) is marginally worse than 1M candidate (0.029220); delta = +0.000481 | Verified from Part 2 artifact re-verification | Slightly worse calibration on the validation set | Probability calibration (Platt scaling / Isotonic Regression) is a Phase 6 task and may recover this gap | Phase 5 validation report; Phase 6 calibration | Deferred to Phase 6 |
| **L5.5** | 90-day primary candidate selected; 180-day results not re-evaluated or changed under this authorization | Scope: authorization limited to 90-day primary candidate | 180-day model remains an unchanged secondary artifact from the original Phase 5 grid run | Previously reported 180-day results remain valid; no action taken | Phase 5 validation report | Accepted |
| **L5.6** | Sealed test targets not evaluated; all reported metrics are validation-set only | Design: test seal intact pending Phase 6 authorization | Reported AP/ROC-AUC/Brier are validation estimates; generalization to test set unknown | Test evaluation to be performed in Phase 6 under supervisor authorization | Phase 6 gate | Deferred to Phase 6 |

---

## Phase 6 — Evaluation & Calibration Limitations (added 2026-07-21)

| ID | Limitation | Evidence Status | Consequence | Mitigation | Report Location | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **L6.1** | B1 calibration partition spans winter/spring months only (2024-01-31 to 2024-03-31) | Approved Gate B1 split manifest | Probability predictions may exhibit seasonal calibration bias if summer/fall repair/weather patterns vary. | Document seasonality limitations; maintain rank-based Top-K operational thresholds. | docs/phase_6_gate_b1_report.md | Approved |
| **L6.2** | Platt scaling directly on raw probabilities degraded Brier score (+0.001773), Log Loss (+0.010889), and ECE (+0.010217) | Clean Rerun Calibration Diagnostics | Apparent probability calibration errors are slightly worse than raw predictions. | Document degradation honestly; recommend raw probabilities as primary, Platt as sensitivity. | docs/phase_6_gate_b1_report.md | Approved |
| **L6.3** | Gate B1 procedural breach: contaminated feature inputs used in initial run, and target_repair_180d decoded across full test set | Verified in Gate B1 Source-Path Audit | 180-day final-test seal is procedurally compromised. | Quarantined contaminated B1 artifacts; ran clean Gate B1 rerun using remediated features/targets with strict column projection; locked B2. | docs/phase_6_gate_b1_protocol_deviation.md | Approved |
