# Montreal Road Risk — Manual Data Download Guide

This guide outlines the step-by-step instructions for manually acquiring the necessary open datasets for the Montreal Road Risk project. 

## Strict General Rules

1. **Official Domains Only**: You must remain on the official Ville de Montréal Open Data portal (`donnees.montreal.ca`) or the official Government of Canada Weather portal (`climate.weather.gc.ca`). **Do not use third-party mirrors, unauthorized API proxies, or random download links.**
2. **VPN Usage**: You may use a reputable VPN if needed to access municipal or federal data portals. **Never share VPN credentials with Antigravity.**
3. **No Modification**: Preserve the original downloaded filenames exactly as they are served. **Do not rename, edit, or unzip the downloaded files.** Keep them in their raw, native states.
4. **No Executables**: Never download executable files (`.exe`, `.msi`, `.bat`, etc.) for this project. The only expected file formats are `CSV`, `ZIP`, `GeoJSON`, `GPKG`, `SHP`, `XLSX`, or `PDF`.
5. **Incremental Verification**: Each file must be placed in its specific destination folder and verified using the verification script (`verify_manual_downloads.py`) before proceeding to download the next dataset in the sequence.

---

## Manual Download Order

Please download the datasets in the following strict order:

### 1. Géobase Road Network

*   **Dataset ID**: `montreal_geobase`
*   **Role**: Canonical Montreal road-segment geometries, names, segment identifiers, and road classes.
*   **Official Landing Page**: [https://donnees.montreal.ca/dataset/geobase](https://donnees.montreal.ca/dataset/geobase)
*   **Required Status**: Required
*   **Preferred Format**: GeoJSON (look for "Réseau routier (Géobase) en format GeoJSON" or similar GeoJSON ZIP file)
*   **Local Destination**: `data/raw/montreal/geobase/`
*   **Current Status**: Downloaded and audited
*   **How to Download**: Navigate to the landing page, locate the GeoJSON resource, and click the **Télécharger** (Download) button. Save the file directly to the local folder.
*   **To Record After Download**: File size, original filename, download date, and SHA-256 hash.

### 2. Mechanized Pothole Repair Records

*   **Dataset ID**: `mechanized_pothole_repairs`
*   **Role**: Primary maintenance repair event log for constructing the 90-day binary classification target.
*   **Official Landing Page**: [https://donnees.montreal.ca/dataset/refection-de-chaussee-par-remplissage-mecanise-de-nid-de-poule](https://donnees.montreal.ca/dataset/refection-de-chaussee-par-remplissage-mecanise-de-nid-de-poule)
*   **Required Status**: Required (All ten annual resources are required candidates for the historical target audit)
*   **Preferred Format**: CSV for 2016–2020 resources; GPKG for 2021–2025 resources.
*   **Local Destination**: `data/raw/montreal/pothole_repairs/`
*   **Current Status**: All 10 annual files downloaded and audited
*   **Download Order**: Download 2016 through 2025 resources one year at a time, verifying each file before downloading the next.
*   **How to Download**: Navigate to the landing page, locate each annual resource from 2016 to 2025, and click the **Télécharger** (Download) button. Save the files directly to the local folder.
*   **Scientific Warnings**:
    1. Records begin in December 2016.
    2. The dataset covers mechanized pothole filling performed by the central road-infrastructure service. Borough repair activities are excluded.
    3. Manual repairs are excluded.
    4. Repairs are concentrated primarily on the arterial network.
    5. GPS accuracy can vary from a few metres to several tens of metres.
    6. Multiple nearby potholes can be repaired without moving the vehicle, so duplicate coordinates or timestamps may legitimately occur. These are raw event records and must not be deduplicated before the audit defines defensible duplicate rules.
    7. The landing-page temporal-coverage metadata appears inconsistent with the availability of annual files through 2025; actual coverage must be determined from each file.
*   **To Record After Download**: File size, original filename, download date, and SHA-256 hash.

### 3. Road Assets — Aggregated Pavement

*   **Dataset ID**: `road_assets_pavement`
*   **Role**: Candidate construction/resurfacing dates, foundation classes, and pavement materials.
*   **Official Landing Page**: [https://donnees.montreal.ca/dataset/voirie-chaussee-intersection](https://donnees.montreal.ca/dataset/voirie-chaussee-intersection)
*   **Required Status**: Required candidate
*   **Preferred Format**: GeoJSON ZIP (look for "Chaussée - Aggregée" or similar GeoJSON ZIP file) and the official attribute-value dictionary CSV.
*   **Local Destination**: `data/raw/montreal/road_assets/`
*   **Current Status**: Downloaded and audited
*   **How to Download**: Download the aggregated pavement GeoJSON/ZIP resource. **Do not download the separate intersection dataset unless the Phase 2 audit later proves it necessary.**
*   **To Record After Download**: Original filename, file size, and SHA-256 hash.

### 4. Pavement-Condition Indicators

*   **Dataset ID**: `pavement_condition`
*   **Role**: Pavement Condition Index (PCI) and International Roughness Index (IRI) indicators.
*   **Official Landing Page**: [https://donnees.montreal.ca/dataset/condition-chaussees-reseau-routier](https://donnees.montreal.ca/dataset/condition-chaussees-reseau-routier)
*   **Required Status**: Required candidate
*   **Preferred Format**: CSV for 2010–2018 resources; GeoJSON for 2020; GPKG for 2022–2024 resources.
*   **Local Destination**: `data/raw/montreal/pavement_condition/`
*   **Current Status**: All six files downloaded and audited
*   **How to Download**: Navigate to the landing page and download all six campaign resources (2010 CSV, 2015 CSV, 2018 CSV, 2020 GeoJSON, 2022 GPKG, 2024 GPKG).
*   **Scientific Warning**:
    1. Irregular survey timelines and varying network scopes (e.g. 2022 covers local, 2024 covers arterial).
    2. Significant format/encoding differences (CSV, CP1252 GeoJSON, binary GPKG).
    3. ~1-5.5% of historical condition identifiers do not match the current Géobase snapshot.
    4. 2020 contains 99 duplicate records and 1,326 missing-data IRI sentinels (`0` with state `-`).
*   **To Record After Download**: Original filenames, file sizes, and SHA-256 hashes in `pavement_condition_resource_manifest.csv`.

### 5. Borough Boundaries

*   **Dataset ID**: `borough_boundaries`
*   **Role**: Administrative boundaries used for spatial grouping, spatial overlay filters, and validation.
*   **Official Landing Page**: [https://donnees.montreal.ca/dataset/limites-administratives-agglomeration](https://donnees.montreal.ca/dataset/limites-administratives-agglomeration)
*   **Required Status**: Required
*   **Preferred Format**: GeoJSON (NAD83 / MTM zone 8 representation)
*   **Local Destination**: `data/raw/montreal/borough_boundaries/`
*   **Current Status**: Downloaded and audited
*   **How to Download**: Download the GeoJSON representing the administrative boundaries of Montreal boroughs in NAD83 / MTM zone 8 (urn:ogc:def:crs:EPSG::32188).
*   **Scientific Warning**:
    1. Static late-2023 boundary snapshot applied to 2016–2025 repair data, causing potential temporal mismatches.
    2. The 15 related municipalities (Ville liée features) are completely absent from the road attributes in the Géobase road network dataset. Assigning road segments to related municipalities requires a spatial overlay join.
    3. 1,084 road segments cross administrative boundaries, requiring a snapping or centroid-containment assignment rule in Phase 3.
*   **To Record After Download**: Filename, size, and SHA-256 hash in `data/metadata/data_manifest.csv`.

### 6. ECCC Weather

*   **Dataset ID**: `eccc_daily_weather`
*   **Role**: Environment and Climate Change Canada historical daily weather variables (minimum/maximum/mean temperature, precipitation, snowfall, freeze-thaw count).
*   **Official Landing Page**: [https://climate.weather.gc.ca/historical_data/search_historic_data_e.html](https://climate.weather.gc.ca/historical_data/search_historic_data_e.html)
*   **Required Status**: Required
*   **Preferred Format**: CSV (daily data)
*   **Local Destination**: `data/raw/eccc_weather/`
*   **Current Status**: Downloaded and audited
*   **How to Download**: Run the reproducible downloader script `scripts/download_eccc_weather.py` which automatically fetches the station inventory and the annual daily weather logs for McTavish (ID 10761) and Montréal-Trudeau (ID 30165) for 2009–2025.
*   **Scientific Warning**:
    1. McTavish Total Rain and Total Snow are 100% missing. Montréal–Trudeau Total Snow is 100% missing, while Total Rain has only 23 populated observations and 6,186 missing observations (99.63% missing). Therefore, the separate Total Rain and Total Snow fields are not suitable as consistent cross-year features. Total Precip is the usable precipitation measurement, subject to its documented missingness.
    2. Point-station measurements are used as island-wide proxies.
    3. Snow on Ground has high missingness (over 70% missing).
*   **To Record After Download**: Filenames, sizes, and SHA-256 hashes in `data/metadata/eccc_weather_resource_manifest.csv`.

### 7. Optional Traffic Counts

*   **Dataset ID**: `traffic_counts`
*   **Role**: Optional traffic-exposure density proxy.
*   **Official Landing Page**: [https://donnees.montreal.ca/dataset/comptage-vehicules-pietons](https://donnees.montreal.ca/dataset/comptage-vehicules-pietons)
*   **Required Status**: Optional (Download only after required core datasets are fully acquired and audited)
*   **Preferred Format**: CSV
*   **Local Destination**: `data/raw/montreal/traffic_counts/`
*   **Current Status**: Not downloaded
*   **How to Download**: Download the active CSV data containing vehicle counting reports.
*   **To Record After Download**: Filename, size, and SHA-256 hash.
