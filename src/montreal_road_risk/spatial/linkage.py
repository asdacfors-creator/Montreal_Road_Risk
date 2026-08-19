import numpy as np
import pandas as pd


def _process_nearest_results(
    nearest_map,
    geobase_ids,
    recommended_threshold,
    tie_tolerance,
    linkage_distance,
    canonical_segment_ids,
    ambiguity_flags,
    linkage_statuses,
):
    """Helper to process nearest-neighbor matches for each point."""
    for pt_idx, matches in nearest_map.items():
        if not matches:
            continue
        min_d = min(m[1] for m in matches)
        linkage_distance[pt_idx] = min_d

        close_matches = [m for m in matches if m[1] <= min_d + tie_tolerance]
        primary_gb_idx = close_matches[0][0]
        primary_id = geobase_ids[primary_gb_idx]

        if len(close_matches) > 1:
            ambiguity_flags[pt_idx] = 1

        if min_d <= recommended_threshold:
            canonical_segment_ids[pt_idx] = primary_id
            if len(close_matches) > 1:
                linkage_statuses[pt_idx] = "review_required"
            else:
                linkage_statuses[pt_idx] = "accepted"
        else:
            linkage_statuses[pt_idx] = "unmatched"
            canonical_segment_ids[pt_idx] = None


def _calculate_candidate_counts(potholes_gdf, geobase_gdf, candidate_bands, candidate_counts):
    """Helper to perform bulk spatial query and calculate counts in candidate bands."""
    max_band = max(candidate_bands)
    buffered = potholes_gdf.geometry.buffer(max_band)
    left_idx, right_idx = geobase_gdf.sindex.query(buffered, predicate="intersects")

    if len(left_idx) > 0:
        all_dists = potholes_gdf.geometry.values[left_idx].distance(geobase_gdf.geometry.values[right_idx])
        df_query = pd.DataFrame({
            "pt_idx": left_idx,
            "dist": all_dists
        })
        for band in candidate_bands:
            band_mask = df_query["dist"] <= band
            counts_series = df_query[band_mask].groupby("pt_idx").size()
            candidate_counts[band][counts_series.index] = counts_series.values


def extract_pothole_linkages(potholes_gdf, geobase_gdf, candidate_bands, tie_tolerance=0.5, recommended_threshold=20.0):
    """
    Link pothole point repairs to Géobase road segments.

    Parameters:
    -----------
    potholes_gdf : gpd.GeoDataFrame
        Pothole point events in EPSG:32188.
    geobase_gdf : gpd.GeoDataFrame
        Géobase LineString segments in EPSG:32188.
    candidate_bands : list of float
        Distance bands (e.g. [10, 15, 20, 30, 50]) to count candidates.
    tie_tolerance : float
        Tolerance in meters to identify tied nearest segments.
    recommended_threshold : float
        The snapping distance threshold for accepted linkage.

    Returns:
    --------
    pd.DataFrame
        DataFrame with linkage columns to join or append to potholes_gdf.
    """
    assert potholes_gdf.crs.to_string() == "EPSG:32188", "Potholes CRS must be EPSG:32188"
    assert geobase_gdf.crs.to_string() == "EPSG:32188", "Géobase CRS must be EPSG:32188"

    n_points = len(potholes_gdf)

    # 1. Initialize result columns
    linkage_distance = np.full(n_points, np.nan, dtype=np.float64)
    canonical_segment_ids = [None] * n_points
    ambiguity_flags = np.zeros(n_points, dtype=np.int32)
    linkage_statuses = ["unmatched"] * n_points

    # Initialize candidate counts for each band
    candidate_counts = {band: np.zeros(n_points, dtype=np.int32) for band in candidate_bands}

    if n_points == 0 or len(geobase_gdf) == 0:
        res = pd.DataFrame({
            "canonical_segment_id": canonical_segment_ids,
            "linkage_method": ["nearest_segment"] * n_points,
            "linkage_status": linkage_statuses,
            "linkage_distance_m": linkage_distance,
            "ambiguity_flag": ambiguity_flags
        })
        for band in candidate_bands:
            res[f"candidate_count_{int(band)}m"] = 0
        return res

    # 2. Find nearest segments using sindex.nearest
    indices, dists = geobase_gdf.sindex.nearest(potholes_gdf.geometry, return_distance=True)

    # Build mapping from point_idx to list of (geobase_idx, dist)
    nearest_map = {}
    for i in range(len(dists)):
        pt_idx = indices[0, i]
        gb_idx = indices[1, i]
        d = dists[i]
        if pt_idx not in nearest_map:
            nearest_map[pt_idx] = []
        nearest_map[pt_idx].append((gb_idx, d))

    # Extract geobase IDs
    geobase_ids = geobase_gdf["canonical_segment_id"].values

    # Process nearest results
    _process_nearest_results(
        nearest_map,
        geobase_ids,
        recommended_threshold,
        tie_tolerance,
        linkage_distance,
        canonical_segment_ids,
        ambiguity_flags,
        linkage_statuses,
    )

    # 3. Calculate candidate counts in distance bands using bulk spatial index query
    _calculate_candidate_counts(potholes_gdf, geobase_gdf, candidate_bands, candidate_counts)

    # 4. Construct final DataFrame
    res = pd.DataFrame({
        "canonical_segment_id": canonical_segment_ids,
        "linkage_method": "nearest_segment",
        "linkage_status": linkage_statuses,
        "linkage_distance_m": linkage_distance,
        "ambiguity_flag": ambiguity_flags
    })

    for band in candidate_bands:
        res[f"candidate_count_{int(band)}m"] = candidate_counts[band]

    return res
