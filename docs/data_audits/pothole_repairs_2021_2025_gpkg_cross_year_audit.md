# Cross-Year Data Audit Report — 2021–2025 GeoPackage Pothole Repairs

## 1. Audit Scope and Objectives
This report provides a comparative cross-year audit of the five annual mechanized pothole-repair datasets stored as OGC GeoPackages (2021–2025). The goal is to identify structural, naming, and coordinate reference system changes that could impact down-stream modeling and target construction.

---

## 2. Comparative Analysis Table

| Data Year | Physical File Name | Total Rows | Discovered Layer Name | Declared CRS | Unique Vehicles | Date Range | Exact Duplicates |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2021** | `remplissage_niddepoule_2021.gpkg` | `50,320` | `remplissage_niddepoule_2021` | WGS 84 (custom srs_id `100000`) | `14` | `2021-01-25` to `2021-03-17` | `0` |
| **2022** | `remplissage_niddepoule_2022.gpkg` | `72,062` | `remplissage_niddepoule_2022` | MTM Zone 8 (`EPSG:2950`) | `16` | `2022-02-09` to `2022-12-16` | `2,041` groups (`4,082` rows) |
| **2023** | `remplissage_niddepoule_2023.gpkg` | `105,773` | `remplissage_niddepoule_2024` | MTM Zone 8 (`EPSG:2950`) | `15` | `2022-12-20` to `2023-05-05` | `106` groups (`214` rows) |
| **2024** | `remplissage_niddepoule_2024.gpkg` | `50,411` | `remplissage_niddepoule_2024` | MTM Zone 8 (`EPSG:2950`) | `15` | `2023-04-11` to `2024-05-30` | `21` groups (`42` rows) |
| **2025** | `remplissage_niddepoule_2025.gpkg` | `74,159` | `remplissage_niddepoule_2025` | MTM Zone 8 (`EPSG:2950`) | `13` | `2025-01-18` to `2025-05-20` | `202` groups (`404` rows) |

---

## 3. Key Transitions, Naming, and Format Shifts

### A. CSV-to-GPKG Transition
The transition from historical CSV files (2016–2020) to OGC GeoPackage binary files (2021–2025) introduces major changes in file formatting, structural constraints, and coordinate representation. The CSV-to-GPKG transition must be handled by separate ingestion pipelines.

### B. Appareil-to-Véhicule Column Header Transition
In the CSV datasets (2016–2020), the device category was tracked under the column header `Appareil`. In the GeoPackages (2021–2025), the column name is transitioned to `Véhicule`. Preprocessing must map these fields to a unified variable.

### C. Date-Format Differences
The representation of timestamps varies between resources:
*   CSV files use `%Y-%m-%d` and `%H:%M:%S` text fields.
*   `2021`, `2022`, `2024`, and `2025` GPKG files use a `T` separator with 3 fractional digits (e.g., `2021-01-25T07:35:20.063`).
*   `2023` GPKG file uses a space separator with varying (0 or 3) fractional digits (e.g., `2022-12-20 15:34:07` and `2023-01-01 12:34:56.789`).
Dynamic timestamp parsing is required.

### D. Vehicle-ID Naming Differences
*   **2021 GPKG**: Vehicle IDs use a hyphenated convention (`NP-` followed by digits, e.g., `NP-117`).
*   **2022–2025 GPKGs**: Vehicle IDs drop the hyphen (`NP` followed by digits, e.g., `NP117`).
*   **Alphanumeric Codes**: Alphanumeric codes (e.g., `CT` and `RM` prefixes) occur in 2022, 2023, and 2024 datasets, whereas 2025 contains strictly `NP`-prefixed devices.

### E. Coordinate Reference System (CRS) Differences
*   **2021 GPKG**: Geometry is stored as longitude/latitude in a custom WGS 84 SRS record (custom `srs_id 100000`, organization `NONE`, and not described as formally declared `EPSG:4326`).
*   **2022–2025 GPKGs**: Declared `EPSG:2950` (NAD83 (CSRS) / MTM zone 8) is explicitly declared by the source layers.
*   *Note*: Phase 3 spatial transformation/reprojection has not occurred in Phase 2.

---

## 4. Layer-Naming and Temporal Year Mismatches
1.  **2023 Internal-Layer Naming Mismatch**:
    *   The file `remplissage_niddepoule_2023.gpkg` contains a single layer internally named `remplissage_niddepoule_2024`. The layer is not renamed in Phase 2.
2.  **Out-of-Year Records**:
    *   **2023 File**: Contains `1` record from 2022 (`2022-12-20 15:34:07`).
    *   **2024 File**: Contains `4` records from 2023.

---

## 5. Duplicate Pattern Differences
*   **2021**: No exact duplicates.
*   **2022**: High exact duplicate rate (`2,041` groups, `4,082` rows).
*   **2023–2025**: Lower, but persistent exact duplicates.
*   *Note*: The exact duplicate-removal policy remains deferred.

---

## 6. Critical Scientific Warnings on Temporal Coverage
> [!WARNING]
> **No annual GeoPackage file contains complete calendar-year coverage.**
> 
> *   **2021**: Active only Jan–Mar (ends 2021-03-17).
> *   **2022**: Large missing periods (zero records June–October).
> *   **2023**: Ends in May (Jan–May).
> *   **2024**: Gaps in Feb, and ends in May.
> *   **2025**: Ends 2025-05-20 (not a complete calendar year).
> 
> Annual temporal gaps exist because none of the files contain complete calendar-year coverage.

---

## 7. Modeling Splits and Preprocessing Status
*   **Exact Modeling Split Undecided**: No chronological train/validation/test dates may be hardcoded yet, and the modeling splits remain undecided.
*   **Phase 3 Preprocessing**: Reprojection and spatial joins have not occurred.

---

## 8. Audit Verdict
**ALL FIVE GEOPACKAGES PASS PHYSICAL AND STRUCTURAL AUDITS WITH LIMITATIONS — Databases are uncorrupted, but spatial harmonization (geographic to MTM projection), vehicle ID string formatting, layer-year mismatches, and severe temporal coverage gaps must be handled during Phase 3. Phase 3 transformation/reprojection has not occurred.**
