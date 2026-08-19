# Spatial Linkage Rules and Algorithms Specification

This document defines the mathematical models, spatial overlay rules, and matching heuristics used to establish linkages between the Ville de Montréal Géobase road network and all other project datasets in Phase 3B.

---

## 1. Pothole-to-Road Snapping Rules (Point-to-Line)

### Model & Formulation

Pothole repairs are point events ($P$). Road segments are LineStrings ($L$).
For each point $P_i$, we find the nearest line segment $L_j$ using the minimum Euclidean distance in meters:

$$\text{dist}(P_i, L_j) = \min_{Q \in L_j} \|P_i - Q\|_2$$

### Linkage Metrics

1. **Distance Bands**: Candidate counts are calculated recursively for thresholds: $\le 10\text{m}$, $\le 15\text{m}$, $\le 20\text{m}$, $\le 30\text{m}$, and $\le 50\text{m}$.
2. **Ambiguity and Ties**: A point is flagged as a tie (`ambiguity_flag = 1`) if there are multiple candidate segments within a tolerance of `0.5` meters of the absolute minimum distance.
3. **Linkage Classification**:
   - **`accepted`**: The nearest distance $\text{dist}(P_i, L_j) \le 20.0\text{m}$, and `ambiguity_flag == 0`.
   - **`review_required`**: The nearest distance $\le 20.0\text{m}$, but `ambiguity_flag == 1` (a tie).
   - **`unmatched`**: The nearest distance $> 20.0\text{m}$, or no candidate segments found.

---

## 2. Pavement-Condition Linkage (Line-to-Line)

### Priority Hierarchy

1. **Direct ID Match**: Standard attribute join of the campaign segment identifier (`source_segment_id`) to the Géobase identifier (`ID_TRC`).
2. **Spatial Fallback**: Executed only for unmatched records in campaigns containing spatial geometries (2020, 2022, and 2024).
   - The campaign survey line is buffered by $5.0$ meters to create a search polygon ($S_i$).
   - We calculate the intersection length of each intersecting Géobase segment ($L_k$) with $S_i$:
     $$\text{len}_k = \text{length}(L_k \cap S_i)$$

   - The segment with the maximum intersection length ($\text{len}_k \ge 5.0\text{m}$) is chosen.
   - If multiple segments are within $1.0$ meter of the maximum intersection length, the match is flagged as `ambiguous`.
3. **Tabular Preservation**: Tabular campaigns (2010, 2015, 2018) do not have spatial coordinates. Unmatched segments remain `unmatched` with no fallback geometry.

---

## 3. Road-Asset-to-Road Linkage (Polygon-to-Line)

### Model Heuristics

No direct key exists between pavement asset polygons ($A$) and Géobase lines ($L$). Linkage is established using spatial intersection:
- For each road segment $L_i$, we compute its intersection with each intersecting asset polygon $A_j$:
  $$\text{overlap\_length}_{ij} = \text{length}(L_i \cap A_j)$$
  $$\text{overlap\_fraction}_{ij} = \frac{\text{overlap\_length}_{ij}}{\text{length}(L_i)}$$

### Primary Polygon Selection

- The primary asset polygon is selected as the candidate with the greatest intersection length.
- If multiple candidates have intersection lengths within $0.1$ meters of the maximum, `ambiguity_flag` is set to `1`.
- **Linkage Status**:
   - **`accepted`**: Overlap fraction $\ge 0.10$, and `ambiguity_flag == 0`.
   - **`review_required`**: Overlap fraction $\ge 0.10$, but `ambiguity_flag == 1` (a tie).
   - **`low_overlap`**: Overlap fraction $< 0.10$.
   - **`unmatched`**: No asset polygon intersects.

---

## 4. Administrative-Boundary Linkage (Line-in-Polygon)

### Containment Logic

Road segments ($L_i$) crossing borough or municipal boundary polygons ($B_j$) are resolved by greatest within-boundary length:
- We compute length inside each boundary:
  $$\text{length}_{ij} = \text{length}(L_i \cap B_j)$$
  $$\text{overlap\_fraction}_{ij} = \frac{\text{length}_{ij}}{\text{length}(L_i)}$$

- The segment is assigned to the boundary unit $B_j$ that maximizes $\text{length}_{ij}$.
- If a segment intersects multiple boundaries, it is flagged as boundary-crossing (`candidate_count > 1`).
- If overlap lengths are within $0.1$ meters of each other, it is flagged as a tie (`ambiguity_flag = 1`).
- All unmatched segments are preserved (no nearest-polygon fallback).
