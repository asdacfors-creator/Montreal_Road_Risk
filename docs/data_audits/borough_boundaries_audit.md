# Montreal Road Risk — Administrative Boundaries Content Audit

This document presents the content audit and quality checks performed on the Montreal administrative boundaries dataset.

---

## 1. Dataset Identity and Metadata

*   **Dataset ID**: `borough_boundaries`
*   **Official Publisher**: Service des infrastructures du réseau routier (SIRR), Ville de Montréal
*   **Official Landing Page**: [donnees.montreal.ca](https://donnees.montreal.ca/dataset/limites-administratives-agglomeration)
*   **Official Resource Page**: [donnees.montreal.ca (Resource Page)](https://donnees.montreal.ca/dataset/limites-administratives-agglomeration/resource/6b313375-d9bc-4dc3-af8e-ceae3762ae6e)
*   **License**: Creative Commons Attribution 4.0 International (CC-BY-4.0)

---

## 2. File Verification & Paths

*   **Source File Selected**: `<DOWNLOADS_DIR>\limites-administratives-agglomeration-nad83 (1).geojson`
*   **Source Size**: `1,470,723` bytes
*   **Source SHA-256**: `7c860dccbf8a8a1a7ff45d1b65a19f819ebbf444b7f7808506c09ad305aed192`
*   **Destination Path**: `<PROJECT_ROOT>\data\raw\montreal\borough_boundaries\limites-administratives-agglomeration-nad83.geojson`
*   **Destination Size**: `1,470,723` bytes
*   **Destination SHA-256**: `7c860dccbf8a8a1a7ff45d1b65a19f819ebbf444b7f7808506c09ad305aed192`
*   **Source/Destination Integrity**: **PASS** (Both files are binary-identical).
*   **Git-Ignore Verification**: Ignored by `.gitignore` line 28 (`data/raw/*`). It remains untracked and is not committed.

---

## 3. Raw GeoJSON Structure and CRS

*   **Root Type**: `FeatureCollection`
*   **Root Keys**: `['type', 'crs', 'features']`
*   **CRS Declaration**:

    ```json
    "crs": {
      "type": "name",
      "properties": {
        "name": "urn:ogc:def:crs:EPSG::32188"
      }
    }
    ```

*   **CRS Interpretation**: Resolves to `EPSG:32188` (NAD83 / MTM zone 8).
*   **Official CRS Methodology Warning**: The Ville de Montréal states that administrative boundaries were constituted in NAD83 / MTM Zone 8. The portal recommends working in this native reference system to preserve homogeneity. Alternative coordinate reference system transformations provided by the portal (such as WGS 84 GeoJSON versions) have not been validated by the city's geomatics division.
*   **Project Working CRS Status**: **UNDECIDED**. While EPSG:32188 is the native reference system, the final approved project-wide coordinate reference system remains undecided in Phase 2.

---

## 4. Feature and Schema Completeness

*   **Feature Count**: `34`
*   **Properties Schema**: `['ABREV', 'CODEID', 'CODEMAMH', 'CODE_3C', 'COMMENT', 'DATEMODIF', 'NOM', 'NOM_OFFICIEL', 'NUM', 'TYPE']`

### Property Completeness (Missingness Table)

| Property | Null Count | Blank Count | Populated Count | Value Types |
| :--- | :--- | :--- | :--- | :--- |
| **ABREV** | 0 | 0 | 34 | `str` |
| **CODEID** | 0 | 0 | 34 | `int` |
| **CODEMAMH** | 0 | 0 | 34 | `str` |
| **CODE_3C** | 0 | 0 | 34 | `str` |
| **COMMENT** | 32 | 0 | 2 | `str` |
| **DATEMODIF** | 0 | 0 | 34 | `str` |
| **NOM** | 0 | 0 | 34 | `str` |
| **NOM_OFFICIEL**| 0 | 0 | 34 | `str` |
| **NUM** | 0 | 0 | 34 | `int` |
| **TYPE** | 0 | 0 | 34 | `str` |

*   **DATEMODIF Distribution**: `2023-11-29` for all 34 features (100% parseable as strings).
*   **COMMENT Distribution**: Null for 32 features. Populated for 2 features:
    1.  *Côte-des-Neiges-Notre-Dame-de-Grâce*: `"Il est important de noter que la limite située sur la falaise Saint-Jacques n'est pas officielle. Cette limite est à préciser."`
    2.  *Le Sud-Ouest*: `"Il est important de noter que la limite située sur la falaise Saint-Jacques n'est pas officielle. Cette limite est à préciser."`

---

## 5. Identifier Uniqueness Table

| Identifier | Null Count | Blank Count | Unique Count | Duplicate Count | Unique in Snapshot |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CODEID** | 0 | 0 | 34 | 0 | **Yes** |
| **CODEMAMH** | 0 | 0 | 34 | 0 | **Yes** |
| **CODE_3C** | 0 | 0 | 34 | 0 | **Yes** |
| **NUM** | 0 | 0 | 34 | 0 | **Yes** |
| **ABREV** | 0 | 0 | 34 | 0 | **Yes** |
| **NOM** | 0 | 0 | 34 | 0 | **Yes** |
| **NOM_OFFICIEL**| 0 | 0 | 34 | 0 | **Yes** |

*   *Note*: While all identifiers are unique within this downloaded snapshot, none are designated as permanent cross-dataset primary keys.

---

## 6. Entity-Type Distribution

The dataset contains 34 administrative divisions classified by `TYPE`:
*   **Arrondissement** (Montréal Boroughs): `19` features
*   **Ville liée** (Related Municipalities): `15` features

### Exact Borough List (TYPE = "Arrondissement")

1.  Ahuntsic-Cartierville
2.  Anjou
3.  Côte-des-Neiges-Notre-Dame-de-Grâce
4.  L'Île-Bizard-Sainte-Geneviève
5.  LaSalle
6.  Lachine
7.  Le Plateau-Mont-Royal
8.  Le Sud-Ouest
9.  Mercier-Hochelaga-Maisonneuve
10. Montréal-Nord
11. Outremont
12. Pierrefonds-Roxboro
13. Rivière-des-Prairies-Pointe-aux-Trembles
14. Rosemont-La Petite-Patrie
15. Saint-Laurent
16. Saint-Léonard
17. Verdun
18. Ville-Marie
19. Villeray-Saint-Michel-Parc-Extension

### Exact Related-Municipality List (TYPE = "Ville liée")

1.  Baie-D'Urfé
2.  Beaconsfield
3.  Côte-Saint-Luc
4.  Dollard-des-Ormeaux
5.  Dorval
6.  Hampstead
7.  Kirkland
8.  L'Île-Dorval
9.  Mont-Royal
10. Montréal-Est
11. Montréal-Ouest
12. Pointe-Claire
13. Sainte-Anne-de-Bellevue
14. Senneville
15. Westmount

> [!IMPORTANT]
> **Scientific Scope Wording**: The 19 `TYPE = "Arrondissement"` features are Montréal boroughs. The 15 `TYPE = "Ville liée"` features are related municipalities in the Montréal agglomeration. Never describe all 34 features as boroughs. Do not silently combine related municipalities with boroughs in any future borough-level analyses. The final geographic scope for the MVP model remains to be decided.

---

## 7. Geometry Quality and Topology

*   **Geometry-Type**: 100% `MultiPolygon` (34 features)
*   **Null Geometries**: `0`
*   **Empty Geometries**: `0`
*   **Invalid Geometries**: `0` (100% valid under OGC SFS)
*   **Component Polygons**: `36`
*   **Component Rings**: `37`
*   **Unclosed Rings**: `0`
*   **Rings with Insufficient Positions (< 4)**: `0`
*   **Non-finite Coordinates**: `0`
*   **Zero-area Geometries**: `0`
*   **Duplicate Geometries Count**: `0`
*   **Coordinate Bounds (EPSG:32188)**:
    *   Min X: `265,961.230985289`
    *   Min Y: `5,027,324.06799987`
    *   Max X: `306,835.012785289`
    *   Max Y: `5,063,077.78980803`
*   **Area Statistics**:
    *   Total Area: `619,200,849.51` m²
    *   Smallest Area Outlier: *L'Île-Dorval* (`180,525.36` m²)
    *   Largest Area Outlier: *Rivière-des-Prairies-Pointe-aux-Trembles* (`51,265,347.11` m²)
*   **Overlaps Check**: `0` overlapping polygon pairs detected (above 1e-3 m² threshold). The polygon boundaries form a clean partition with disjoint interiors.

---

## 8. In-Memory Feasibility Check with Géobase

A read-only, in-memory feasibility comparison was executed against the Géobase road network (`data/raw/montreal/geobase/geobase.json`) by projecting the road geometries from EPSG:4326 to EPSG:32188 in memory. No reprojected or joined datasets were saved.

### Intersection Statistics

*   Total Géobase road features analyzed: `47,983`
*   Roads intersecting **zero** administrative polygons: `1` segment (99.998% intersect rate)
*   Roads intersecting **exactly one** administrative polygon: `46,898` segments
*   Roads intersecting **multiple** administrative polygons (boundary-crossing roads): `1,084` segments

### Intersections by Boundary Type

*   **Arrondissement**: `37,595` segments
*   **Ville liée**: `10,049` segments
*   **Mixed** (road segment crosses an Arrondissement and a Ville liée boundary): `338` segments

### Name Domain Comparison

*   **Boundary Names (34)**: Matches all 34 names.
*   **Geobase Names (20)**: Contains 19 arrondissements names plus `'N/A'`.
*   **Unmatched in Geobase**: `'N/A'`
*   **Unmatched in boundaries**: The 15 related municipalities.
*   *Scientific Finding*: The Géobase road network attributes (`ARR_GCH` / `ARR_DRT`) only contain names of the 19 Arrondissements. The 15 related municipalities are completely absent from the road attributes in the Géobase dataset. Therefore, assigning road segments to related municipalities requires a spatial intersection join, rather than an attribute key join.

---

## 9. Coverage and Temporal Limitations

1.  **Current Snapshot Constraint**: This dataset is a static administrative-boundary snapshot (last modified on `2023-11-29`).
2.  **Temporal Mismatch**: The historical road-repair observations in this project extend back to 2016. Municipal administrative boundaries can change over time.
3.  **Historical Mismatch Warning**: Because `DATEMODIF` does not provide a complete historical version history, applying 2023 administrative polygons to 2016–2022 observations assumes boundary stability. This assumption must be registered as an active limitation (`L2.27`).

---

## 10. Audit Decision

*   **Audit Decision**: **PASS WITH LIMITATIONS**
*   **Limitations Summary**:
    1.  *Current administrative snapshot vs historical observations*: Potential temporal mismatch for earlier years (`L2.27`).
    2.  *Borough vs related-municipality distinction*: The 15 related municipalities must not be combined with boroughs (`L2.28`).
    3.  *Boundary-crossing road segment assignment*: 1,084 road segments cross administrative boundaries, requiring a snapping or splitting rule (`L2.29`).
    4.  *Official CRS Warning*: Portal WGS 84 transformations are unvalidated by the city (`L2.30`).
    5.  *Working CRS Undecided*: The project working CRS is not yet finalized (`L2.31`).

*   **Raw-File Integrity Confirmation**: Confirmed. The destination file remains a binary-identical copy of the source download.
