# Montreal Road Risk — Spatial and Temporal Join Strategy

| Field | Value |
| :--- | :--- |
| **Document purpose** | Spatial and Temporal Joining Specification |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 3B — Validated Spatial Linkage and Crosswalk Construction |
| **Status** | In Progress |
| **Last updated** | 2026-07-17 |
| **Source of truth** | Phase 3B Execution |
| **Next review** | Phase 3C Temporal Panel Ingestion |

---

## Executive Summary

This document specifies the joining pathways, candidates for spatial matching tolerances, temporal aggregation models, and validation rules for merging data sources into the segment-month panel.

---

## Join-Dependency Overview

Building the panel requires joining seven heterogeneous datasets. Spatial matching Snaps points to lines, overlaps polygons on lines, or intersects polygons. Temporal matching carries periodic data forward or aligns dates.

---

## Source-by-Source Join Table

| Target Layer | Join Type | Conceptual Key | Proposed Method | Fallback Method |
| :--- | :--- | :--- | :--- | :--- |
| **Repair Events** | Spatial snapping | `segment_id` | Match by attribute if present | Snap coordinates to line |
| **Borough Boundaries** | Spatial overlay | Centroid-in-Polygon | Centroid overlay | Attribute join on borough string |
| **Asset Resurfacing** | Spatial overlap | `segment_id` | Buffer overlay (length overlap) | Attribute join on segment key |
| **Pavement Condition** | Spatial + Temporal | `segment_id` + Campaign Year | Forward-carry campaign PCI | Match nearest campaign in time |
| **Traffic Counts** | Spatial propagation | Intersection coordinates | Segment name & class route match | Functional class average |
| **Weather Data** | Spatial + Temporal | Centroid distance + Date | Centroid distance interpolation | Primary station (McTavish) value |

---

## Preferred and Fallback Joins

### Repair-Event Snapping
* **Preferred Method**: Join using the official road segment identifier if documented in the repair dataset.
* **Fallback Method**: Snap point coordinates of the repair event to the nearest LineString geometry of the road network.

### Borough and Related Municipality Spatial Joins
* **Preferred Method**: Spatial intersection of the road segment's centroid with administrative boundary polygons (both Arrondissements and Villes liées).
* **Fallback Method**: Join on the borough name string (`ARR_GCH` / `ARR_DRT`) if present in the segment attributes.
* **Limitations Warning**: The 15 related municipalities (Ville liée features) are completely absent from the road attributes in the Géobase road network dataset. Therefore, assigning road segments to related municipalities requires a spatial intersection join, rather than an attribute key join.

### Asset and Resurfacing
* **Preferred Method**: Spatial overlay of road LineStrings with asset polygons.
* **Provisional Candidate**: Attribute features to the segment if the LineString overlaps the polygon by a provisional candidate threshold (to be evaluated in Phase 3).
* **Fallback Method**: Direct attribute join on segment identifier if pre-mapped in the source file.

---

## Spatial Matching Tolerances and Candidates

The spatial matching snapping threshold cannot be fixed in Phase 0. The following candidate tolerances are proposed as sensitivity values to be tested in Phase 3:
* **Candidate Snapping Distances**: 10 meters, 25 meters, and 50 meters.
* **Selection Criteria**: The final snapping threshold will be selected after auditing:
  * Overall match rates.
  * Spatial distance distributions.
  * Number of ambiguous matches (points snapping equally close to multiple lines).
  * Unmatched event counts.
  * Visual map inspection of samples.

---

## Weather Aggregation Candidates

The weather spatial interpolation and aggregation method will be tested in Phase 5 from the following candidates:
* **Primary Station (McTavish)**: Assign daily values from McTavish directly to all segments (since McTavish has 98.32% temperature completeness).
* **Nearest Station Fallback**: Assign daily values from the closest of the two audited stations.
* **Inverse Distance Weighting (IDW) or Average**: Interpolate daily values using distance-based weights from McTavish and Montréal-Trudeau.
* **Temporal Fallback Imputation**: If the primary station has a missing day, impute using the secondary station's value adjusted for the mean offset of 0.426°C.

---

## Validation Metrics and Rejection Rules

### Validation Metrics
* Snap distance distribution percentiles (50th, 90th, 95th).
* Percent of segments containing invalid centroids.
* Count of mismatched or multi-allocated events.

### Rejection Rules
* Discard repair events with invalid coordinates or coordinates snapping beyond the maximum selected tolerance.
* Reject joins that create many-to-many row duplications in the panel.
* Reject condition indices or weather logs where the inspection/observation date is after the panel observation date $t$ (leakage condition).

---

## Limitations and Pending Verification

* Coverage and missingness of pavement condition (PCI/IRI), asset resurfacing, and daily weather have been fully audited in Phase 2. Traffic counts remain outstanding/deferred.
* The physical identifier for `segment_id` is confirmed as `ID_TRONCON` (or `ID_TRC` in condition campaigns).
* Related municipalities (Ville liée) are completely absent from the road attributes in the Géobase road network dataset, meaning spatial overlay is required for assignment.
* 1,205 road segments cross administrative boundaries, requiring a snapping or centroid-containment assignment rule in Phase 3.

---

## Phase Gate

To transition to Phase 4, the join strategy must be approved.
* [x] Snapping candidates and selection criteria defined.
* [x] Weather aggregation candidates established.
* [x] Temporal preprocessing integration complete.
* [x] Supervisor approval received.
