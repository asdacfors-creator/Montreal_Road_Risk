# Montreal Road Risk — Data Source Inventory

| Field | Value |
| :--- | :--- |
| **Document purpose** | Data Source Inventory and Verification Log |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 0 — Definition, Requirements and Feasibility |
| **Status** | Ready for Supervisor Re-review |
| **Last updated** | 2026-07-15 |
| **Source of truth** | Official Metadata Landing Pages |
| **Next review** | Phase 2 Data Quality Audit |

---

## Executive Summary

This inventory documents the verified metadata, landing pages, geometries, licenses, and proposed project roles of the official datasets for the Montreal Road Risk project. It serves as the baseline for Phase 2 data acquisition.

---

## Source-Status Legend

* **Verified from official metadata**: Metadata confirmed on the official landing page.
* **Conditional**: Available under specific restrictions or conditions.
* **Uncertain**: Requires confirmation of schema or compatibility.
* **Unavailable**: Not accessible or not published.
* **Requires downloaded-file inspection**: Schema and column details must be confirmed in Phase 2.

---

## Unified Source Table

| Dataset Name | Official Publisher | Official Landing Page URL | Access Date | Reported Formats | Reported Coverage | Update Frequency | Official Licence | Documented Identifiers | Documented Date Fields | Geometry Type | Proposed Project Role | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mechanized Pothole Repairs** | Service des infrastructures du réseau routier (SIRR), Ville de Montréal | [donnees.montreal.ca](https://donnees.montreal.ca/dataset/travaux-de-colmatage-de-nids-de-poule) | 2026-07-15 | CSV, SHP, GeoJSON | Ville de Montréal | Periodically | Open Government Licence - Montréal | `id_colmatage` | `date_colmatage` | Point | Primary target label variable | Verified |
| **Géobase Road Network** | Service des technologies de l'information (STI), Ville de Montréal | [donnees.montreal.ca](https://donnees.montreal.ca/dataset/geobase-reseau-routier) | 2026-07-15 | SHP, GeoJSON, GML | Agglomération de Montréal | Monthly | Open Government Licence - Montréal | `ID_TRONCON`, `ID_VOIE` | `DATE_CREATION` | LineString | Spatial backbone defining `segment_id` | Verified |
| **Asset & Resurfacing** | Service des infrastructures du réseau routier (SIRR), Ville de Montréal | [donnees.montreal.ca](https://donnees.montreal.ca/dataset/voirie-chaussee-intersection) | 2026-07-16 | GeoJSON (ZIP) & CSV | Ville de Montréal | Annual | Open Government Licence - Montréal | `ID_VOI_CHAUSSEE_AGR` | `DATECONSTRUCTION`, `DATERESURFACAGE` | Polygon | Road material, age, and resurfacing features | Audited with Limitations |
| **Pavement Condition** | Service des infrastructures du réseau routier (SIRR), Ville de Montréal | [donnees.montreal.ca](https://donnees.montreal.ca/dataset/condition-chaussees-reseau-routier) | 2026-07-16 | CSV, GeoJSON, GPKG | Complete & Arterial & Local networks | Irregular | Open Government Licence - Montréal | `ID_TRC` | `DateReleve` | LineString / Table | Pavement quality index features (PCI/IRI) | Audited with Limitations |
| **Traffic Counts** | Service de l'urbanisme et de la mobilité (SUM), Ville de Montréal | [donnees.montreal.ca](https://donnees.montreal.ca/dataset/comptage-vehicules-cyclistes-pedestres-intersections) | 2026-07-15 | CSV, GeoJSON | Major intersections | Periodically | Open Government Licence - Montréal | `id_intersection` | `date_debut` | Point | Criticality score traffic volume input | Verified |
| **Borough Boundaries** | Service des infrastructures du réseau routier (SIRR), Ville de Montréal | [donnees.montreal.ca](https://donnees.montreal.ca/dataset/limites-administratives-agglomeration) | 2026-07-16 | GeoJSON | Agglomération de Montréal | Exceptionally rare | Open Government Licence - Montréal | `CODEID`, `NOM` | `DATEMODIF` | MultiPolygon | Spatial aggregation and borough filters | Audited with Limitations |
| **ECCC Weather Data** | Environment and Climate Change Canada (ECCC) | [weather.gc.ca](https://climate.weather.gc.ca/historical_data/search_historic_data_e.html) | 2026-07-16 | CSV | National (Montreal stations) | Daily | Open Government Licence - Canada | Station ID, Climate ID | `Date/Time`, `Year`, `Month`, `Day` | Point | Freeze-thaw predictive weather features | Audited with Limitations |

---

## Source-by-Source Details

### 1. Mechanized Pothole Repairs
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Check if the schema contains a column representing `segment_id` (e.g., `ID_TRONCON`). If missing, spatial snapping must be implemented.
* **Limitations and Warnings**: Represents only mechanized repairs. Manual interventions are excluded.

### 2. Géobase Road Network
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Verify the schema of `ID_TRONCON` to ensure it can serve as the unique spatial key `segment_id`.
* **Limitations and Warnings**: Topology changes (street modifications) occur monthly, which may cause matching drift with older historical repair data.

### 3. Asset & Resurfacing
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Completed. Verified unique identifier `ID_VOI_CHAUSSEE_AGR` (64,025 unique values).
* **Limitations and Warnings**:
  1. Construction dates are 100% present but 88.57% are unknown/imprecise (+/- 100 years).
  2. Resurfacing dates are 86.74% missing (55,535 features are null).
  3. Date logic anomalies exist (133 records show resurfacing before construction).
  4. No direct identifier relationship to Géobase exists; spatial joining is required.

### 4. Pavement Condition (PCI/IRI)
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Completed. Verified six historical campaigns (2010, 2015, 2018, 2020, 2022, 2024).
* **Limitations and Warnings**:
  1. Irregular survey timing and scope: 2010/2015 cover complete network, 2018/2020/2024 cover arterial only, 2022 covers local only.
  2. Format and encoding shifts: CSV (2010-2018), CP1252 GeoJSON (2020), GPKG (2022-2024).
  3. Identifier matching: 1% to 5.5% of condition IDs do not exist in the current Géobase.
  4. 2020 contains 99 duplicate feature records and 1,326 IRI missing-data sentinel values (`0` with state `-`).

### 5. Traffic Counts
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Inspect coordinate mapping of sensors and check distance to nearest road segments.
* **Limitations and Warnings**: High spatial sparsity. Most local streets have no sensors, requiring functional class proxies.

### 6. Borough Boundaries
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Completed. Verified GeoJSON (34 features) in NAD83 / MTM zone 8 (EPSG:32188).
* **Limitations and Warnings**:
  1. Represents administrative divisions, which do not align with physical road network layouts.
  2. The 15 related municipalities (Ville liée features) are completely absent from the road attributes in the Géobase road network dataset. Assigning road segments to related municipalities requires a spatial overlay join.
  3. 1,084 road segments cross administrative boundaries, requiring a snapping or centroid-containment assignment rule in Phase 3.
  4. Temporal mismatch: This is a static 2023 snapshot applied to historical observations going back to 2016.

### 7. ECCC Weather Data
* **Inclusion/Exclusion**: Included.
* **Phase 2 Verification Required**: Completed. Retrieved and audited continuous daily logs (2009-2025) for McTavish (Station 10761) and Trudeau (Station 30165).
* **Limitations and Warnings**:
  1. Point-station measurements are used as island-wide proxies.
  2. McTavish Total Rain and Total Snow are 100% missing. Montréal–Trudeau Total Snow is 100% missing, while Total Rain has only 23 populated observations and 6,186 missing observations (99.63% missing). Therefore, the separate Total Rain and Total Snow fields are not suitable as consistent cross-year features. Total Precip is the usable precipitation measurement, subject to its documented missingness.
  3. Snow on Ground has high missingness (over 70% missing).
  4. Station ID is an internal ECCC identifier and is mutable. Climate ID must be used as the stable key.

---

## Inclusion and Rejection Criteria

### Inclusion Criteria
* Datasets must be published by official municipal or federal agencies.
* Spatial layers must cover the territory of the Agglomération de Montréal.
* Date fields must cover the historical modeling period.

### Rejection Criteria
* Discard datasets with no documented metadata or licensing information.
* Reject records with invalid or missing coordinates that cannot be resolved textually.
* Reject datasets with restrictive commercial licenses.

---

## Limitations and Pending Verification

* Coverage and missingness for traffic, pavement condition (PCI/IRI), and asset resurfacing are **currently unknown** and must be measured in Phase 2.
* Direct ID matching between assets and the road network is a provisional hypothesis; spatial overlays will be required if the ID keys do not match.

---

## Phase Gate

To transition to Phase 1, the data inventory must be finalized.
* [ ] Landing pages and licenses verified.
* [ ] No data downloaded.
* [ ] Verification requirements for Phase 2 defined.
* [ ] Supervisor approval received.
