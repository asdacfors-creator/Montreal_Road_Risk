# Montreal Road Risk — Phase 2 Gate Report

This document presents the final validation and gate check for closing Phase 2 (Data Acquisition and Quality Audit) and transitioning to Phase 3 (GIS, Spatial and Temporal Preprocessing).

---

## 1. Required Datasets Evaluation

### 1. Montréal Géobase

*   **Acquisition Status**: Complete.
*   **Integrity Status**: Passed. Size: `43,145,805` bytes, SHA-256: `fbb1a46f4fd64ae156a778a3bfe3ef176583967607de33762d26b07f53572c25`.
*   **Audit Decision**: **PASS WITH LIMITATIONS** (see `docs/data_audits/geobase_audit.md`).
*   **Temporal Coverage**: Static 2026 snapshot.
*   **CRS/Geographic Basis**: WGS 84 (EPSG:4326) representation, native MTM 8 coordinates not validated.
*   **Primary Join Candidate**: Primary spatial network base. Key: `ID_TRONCON`.
*   **Major Limitations**:
    1. Static snapshot applied to historical observations going back to 2016.
    2. Names classified as Ville liée are completely absent from the `ARR_GCH` / `ARR_DRT` attributes.
*   **Phase 3 Readiness**: **Ready**.

### 2. Mechanized Pothole Repairs (2016–2025)

*   **Acquisition Status**: Complete (10 of 10 annual resource files).
*   **Integrity Status**: Passed (verified via `verify_manual_downloads.py`).
*   **Audit Decision**: **PASS WITH LIMITATIONS** (see `docs/data_audits/pothole_repairs_2021_2025_gpkg_cross_year_audit.md` and annual audits).
*   **Temporal Coverage**: 2016–2025 (note: 2020 and 2021 have incomplete annual coverage).
*   **CRS/Geographic Basis**: CSVs (2016–2020) are in WGS 84; GPKGs (2021–2025) contain EPSG:2950 projected coordinates.
*   **Primary Join Candidate**: Spatial snapping of coordinate points to the nearest road network line segment.
*   **Major Limitations**:
    1. 2019 contains a large duplicate anomaly (51,422 excess rows).
    2. Column shift from `Appareil` to `Véhicule` in 2021.
    3. Severe seasonal gaps in 2020 and 2021.
*   **Phase 3 Readiness**: **Ready**.

### 3. Road-Assets Pavement

*   **Acquisition Status**: Complete (GeoJSON ZIP + Attribute values CSV).
*   **Integrity Status**: Passed. GeoJSON ZIP size: `36,622,399` bytes, CSV size: `6,829` bytes.
*   **Audit Decision**: **PASS WITH LIMITATIONS** (see `docs/data_audits/road_assets_pavement_audit.md`).
*   **Temporal Coverage**: Static snapshot (construction dates back to 1865).
*   **CRS/Geographic Basis**: WGS 84 representation (no explicit CRS member in GeoJSON).
*   **Primary Join Candidate**: Spatial buffer overlay of road asset polygon onto road segment line.
*   **Major Limitations**:
    1. `DATECONSTRUCTION` has 88.57% unknown or highly imprecise values.
    2. `DATERESURFACAGE` has 86.74% missing values.
    3. 133 records have resurfacing dates registered before construction dates.
*   **Phase 3 Readiness**: **Ready**.

### 4. Pavement-Condition Campaigns (2010–2024)

*   **Acquisition Status**: Complete (6 campaign resources: 2010, 2015, 2018, 2020, 2022, 2024).
*   **Integrity Status**: Passed.
*   **Audit Decision**: **PASS WITH LIMITATIONS** (see `docs/data_audits/pavement_condition_cross_year_audit.md`).
*   **Temporal Coverage**: Irregular campaign years (2010, 2015, 2018, 2020, 2022, 2024).
*   **CRS/Geographic Basis**: Mix of WGS 84 CSVs, JSONs, and projected GPKGs (EPSG:2950).
*   **Primary Join Candidate**: Attribute join on segment `ID_TRC` key.
*   **Major Limitations**:
    1. Match rate to Géobase ranges from 94.49% to 99.58% (unmatched segments are lost).
    2. 2020 campaign contains 99 exact duplicates and 1,326 missing-data IRI sentinels.
    3. Campaigns are local-only (2022) or arterial-only (2024).
*   **Phase 3 Readiness**: **Ready**.

### 5. Administrative Boundaries

*   **Acquisition Status**: Complete.
*   **Integrity Status**: Passed. Size: `1,470,723` bytes, SHA-256: `7c860dccbf8a8a1a7ff45d1b65a19f819ebbf444b7f7808506c09ad305aed192`.
*   **Audit Decision**: **PASS WITH LIMITATIONS** (see `docs/data_audits/borough_boundaries_audit.md`).
*   **Temporal Coverage**: Static 2023 snapshot.
*   **CRS/Geographic Basis**: EPSG:32188 (NAD83 / MTM Zone 8).
*   **Primary Join Candidate**: Centroid-in-Polygon spatial overlay.
*   **Major Limitations**:
    1. Names classified as Ville liée in the administrative-boundary source were not observed in the audited current Géobase ARR_GCH/ARR_DRT attribute domains. Spatial overlay remains a candidate method for assigning related-municipality geography.
    2. 1,084 road segments cross boundaries.
    3. Temporal mismatch of static 2023 boundaries applied to 2016 repairs.
*   **Phase 3 Readiness**: **Ready**.

### 6. ECCC Daily Weather

*   **Acquisition Status**: Complete (1 station inventory + 34 annual station files).
*   **Integrity Status**: Passed.
*   **Audit Decision**: **PASS WITH LIMITATIONS** (see `docs/data_audits/eccc_weather_audit.md`).
*   **Temporal Coverage**: Continuous daily records 2009–2025.
*   **CRS/Geographic Basis**: Point station coordinates.
*   **Primary Join Candidate**: Centroid distance interpolation to McTavish and Montréal-Trudeau.
*   **Major Limitations**:
    1. McTavish has 104 mean temperature missing records; Trudeau has 776 missing.
    2. McTavish Total Rain and Total Snow are 100% missing. Montréal–Trudeau Total Snow is 100% missing, while Total Rain has only 23 populated observations and 6,186 missing observations (99.63% missing). Therefore, the separate Total Rain and Total Snow fields are not suitable as consistent cross-year features. Total Precip is the usable precipitation measurement, subject to its documented missingness.
    3. Point station coordinates used as citywide proxy.
*   **Phase 3 Readiness**: **Ready**.

---

## 2. Deferred Datasets

*   **Traffic Counts**: Deferred to subsequent phases. It is optional and does not block the classification MVP model.

---

## 3. Preprocessing, Joining, and Modeling Checks

*   **No Preprocessing Done**: Confirmed. All raw files remain in native formats and paths. No files reprojected, simplified, or edited.
*   **No Finalized Spatial Join**: Confirmed. No joined files exist.
*   **No Labels or Features Constructed**: Confirmed. Target construction is locked.
*   **No Model Trained**: Confirmed. No models exist.

---

## 4. Phase 2 Verification and Close Check

*   [x] All required raw sources are present in `data/raw/`.
*   [x] All required sources have passed integrity and hash verification.
*   [x] Content audit reports are published for all 6 required datasets.
*   [x] Manifest entries are fully populated.
*   [x] Spatial and temporal join hypotheses are documented.
*   [x] Leakage prevention rules are documented.
*   [x] Working projected CRS is undecided and deferred to Phase 3.
*   [x] Chronological train/validation/test splits are undecided.

---

## 5. Gate Decision

*   **Decision**: **CLOSE PHASE 2 / AUTHORIZE PHASE 3**
*   **Next Action**: Phase 3 GIS, Spatial and Temporal Preprocessing.
*   **Phase 3 Authorization Status**: **AUTHORIZED BUT NOT STARTED**.
