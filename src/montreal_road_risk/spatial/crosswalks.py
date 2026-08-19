import geopandas as gpd
import numpy as np
import pandas as pd


def _find_spatial_fallback(geom, geobase_gdf, min_intersection_length):
    """Helper to perform spatial fallback calculation for a single geometry."""
    if geom is None or geom.is_empty:
        return None, "unmatched", "unmatched", np.nan, 0, 0

    buffered = geom.buffer(10.0)
    candidates_idx = geobase_gdf.sindex.query(buffered, predicate="intersects")

    if len(candidates_idx) == 0:
        return None, "unmatched", "unmatched", np.nan, 0, 0

    cand_ids = []
    cand_lengths = []
    cand_gb_indices = []
    geom_buffer_for_len = geom.buffer(5.0)

    for gb_idx in candidates_idx:
        gb_geom = geobase_gdf.geometry.iloc[gb_idx]
        if gb_geom is not None and not gb_geom.is_empty:
            intersection = gb_geom.intersection(geom_buffer_for_len)
            inter_len = intersection.length
            if inter_len >= min_intersection_length:
                cand_ids.append(geobase_gdf.iloc[gb_idx]["canonical_segment_id"])
                cand_lengths.append(inter_len)
                cand_gb_indices.append(gb_idx)

    n_cands = len(cand_ids)
    if n_cands == 0:
        return None, "unmatched", "unmatched", np.nan, 0, 0

    max_len_idx = np.argmax(cand_lengths)
    max_len = cand_lengths[max_len_idx]
    best_id = cand_ids[max_len_idx]
    best_gb_idx = cand_gb_indices[max_len_idx]

    ties = [length for idx, length in enumerate(cand_lengths) if idx != max_len_idx and length >= max_len - 1.0]

    if len(ties) > 0:
        return best_id, "spatial_fallback", "ambiguous", np.nan, 1, n_cands
    else:
        dist = geom.distance(geobase_gdf.geometry.iloc[best_gb_idx])
        return best_id, "spatial_fallback", "spatial_fallback", dist, 0, n_cands


def build_pavement_condition_linkage(pavement_df, geobase_gdf, min_intersection_length=5.0):
    """
    Build linkage from pavement condition campaign records to Géobase.
    First checks direct ID match. If unmatched and record has geometry, uses spatial fallback.
    """
    assert geobase_gdf.crs.to_string() == "EPSG:32188", "Géobase CRS must be EPSG:32188"

    # Check if pavement_df is a GeoDataFrame and has active geometry
    has_geom = isinstance(pavement_df, gpd.GeoDataFrame) and pavement_df.geometry is not None
    if has_geom:
        assert pavement_df.crs.to_string() == "EPSG:32188", "Pavement GDF CRS must be EPSG:32188"

    n_rows = len(pavement_df)

    # Output columns
    canonical_segment_ids = [None] * n_rows
    linkage_methods = ["unmatched"] * n_rows
    linkage_statuses = ["unmatched"] * n_rows
    linkage_distances = np.full(n_rows, np.nan, dtype=np.float64)
    ambiguity_flags = np.zeros(n_rows, dtype=np.int32)
    candidate_counts = np.zeros(n_rows, dtype=np.int32)

    # Index geobase by canonical_segment_id for fast lookup
    geobase_lookup = {row["canonical_segment_id"]: idx for idx, row in geobase_gdf.iterrows()}

    # Iterate over pavement records
    for i in range(n_rows):
        row = pavement_df.iloc[i]
        src_id = row.get("source_segment_id")

        # 1. Direct ID check
        if src_id in geobase_lookup:
            canonical_segment_ids[i] = src_id
            linkage_methods[i] = "direct_id"
            linkage_statuses[i] = "direct_id"
            linkage_distances[i] = 0.0
            continue

        # 2. Spatial fallback check (only if campaign has geometry)
        if has_geom:
            geom = pavement_df.geometry.iloc[i]
            best_id, method, status, dist, ambiguity, n_cands = _find_spatial_fallback(
                geom, geobase_gdf, min_intersection_length
            )
            canonical_segment_ids[i] = best_id
            linkage_methods[i] = method
            linkage_statuses[i] = status
            linkage_distances[i] = dist
            ambiguity_flags[i] = ambiguity
            candidate_counts[i] = n_cands

    # Build result df
    res = pavement_df.copy()
    res["canonical_segment_id"] = canonical_segment_ids
    res["linkage_method"] = linkage_methods
    res["linkage_status"] = linkage_statuses
    res["linkage_distance_m"] = linkage_distances
    res["ambiguity_flag"] = ambiguity_flags
    res["candidate_count"] = candidate_counts

    return res


def build_road_asset_linkage(geobase_gdf, road_assets_gdf, candidate_overlap_levels):
    """
    Build linkage from Géobase road segments to road-assets pavement polygons.
    """
    assert geobase_gdf.crs.to_string() == "EPSG:32188", "Géobase CRS must be EPSG:32188"
    assert road_assets_gdf.crs.to_string() == "EPSG:32188", "Road assets CRS must be EPSG:32188"

    n_segments = len(geobase_gdf)

    # Initialize output arrays
    primary_asset_ids = [None] * n_segments
    overlap_lengths = np.zeros(n_segments, dtype=np.float64)
    overlap_fractions = np.zeros(n_segments, dtype=np.float64)
    candidate_counts = np.zeros(n_segments, dtype=np.int32)
    ambiguity_flags = np.zeros(n_segments, dtype=np.int32)
    linkage_statuses = ["unmatched"] * n_segments

    asset_record_ids = road_assets_gdf["source_record_number"].values

    # query intersection of geobase (query) against road_assets (tree)
    # left_idx: index in road_assets_gdf (tree), right_idx: index in geobase_gdf (query)
    left_idx, right_idx = road_assets_gdf.sindex.query(geobase_gdf.geometry, predicate="intersects")

    if len(left_idx) > 0:
        # Vectorized intersections
        intersections = geobase_gdf.geometry.values[left_idx].intersection(road_assets_gdf.geometry.values[right_idx])
        inter_lengths = intersections.length

        # Build pandas DataFrame for fast groupby operations
        df_inter = pd.DataFrame({
            "seg_idx": left_idx,
            "asset_id": asset_record_ids[right_idx],
            "inter_len": inter_lengths
        })
        # Filter out 0 or nan overlap lengths
        df_inter = df_inter[df_inter["inter_len"] > 0.0].copy()

        if len(df_inter) > 0:
            # Group by segment index and count total candidate intersections
            counts = df_inter.groupby("seg_idx").size()
            candidate_counts[counts.index] = counts.values

            # Sort descending by overlap length so that groupby("seg_idx").first() picks the max
            df_sorted = df_inter.sort_values("inter_len", ascending=False)
            df_primary = df_sorted.groupby("seg_idx").first()

            # Join the max overlap length back to identify ties
            df_joined = df_inter.join(df_primary[["inter_len"]].rename(columns={"inter_len": "max_len"}), on="seg_idx")
            # Tie criteria: candidate with length within 0.1m of max, but different asset ID
            df_ties = df_joined[(df_joined["inter_len"] >= df_joined["max_len"] - 0.1) & (df_joined["asset_id"] != df_primary.loc[df_joined["seg_idx"], "asset_id"].values)]
            tie_indices = set(df_ties["seg_idx"])

            # Fill output arrays using df_primary index
            for seg_idx, row in df_primary.iterrows():
                seg_len = geobase_gdf.geometry.iloc[seg_idx].length
                if seg_len > 0:
                    max_len = row["inter_len"]
                    frac = max_len / seg_len
                    overlap_lengths[seg_idx] = max_len
                    overlap_fractions[seg_idx] = frac
                    primary_asset_ids[seg_idx] = int(row["asset_id"])

                    if seg_idx in tie_indices:
                        ambiguity_flags[seg_idx] = 1

                    # Classify status using 0.10 candidate threshold (tentative recommendation)
                    if frac >= 0.10:
                        if seg_idx in tie_indices:
                            linkage_statuses[seg_idx] = "review_required"
                        else:
                            linkage_statuses[seg_idx] = "accepted"
                    else:
                        linkage_statuses[seg_idx] = "low_overlap"

    res = geobase_gdf.copy()
    res["primary_asset_id"] = primary_asset_ids
    res["overlap_length_m"] = overlap_lengths
    res["overlap_fraction"] = overlap_fractions
    res["candidate_count"] = candidate_counts
    res["ambiguity_flag"] = ambiguity_flags
    res["linkage_status"] = linkage_statuses
    res["linkage_method"] = "spatial_intersection"

    return res


def build_administrative_boundary_linkage(geobase_gdf, borough_gdf):
    """
    Build linkage from Géobase road segments to administrative borough boundaries.
    """
    assert geobase_gdf.crs.to_string() == "EPSG:32188", "Géobase CRS must be EPSG:32188"
    assert borough_gdf.crs.to_string() == "EPSG:32188", "Borough boundaries CRS must be EPSG:32188"

    n_segments = len(geobase_gdf)

    # Initialize output columns
    primary_borough_ids = [None] * n_segments
    primary_borough_names = [None] * n_segments
    overlap_lengths = np.zeros(n_segments, dtype=np.float64)
    overlap_fractions = np.zeros(n_segments, dtype=np.float64)
    candidate_counts = np.zeros(n_segments, dtype=np.int32)
    ambiguity_flags = np.zeros(n_segments, dtype=np.int32)
    linkage_statuses = ["unmatched"] * n_segments

    # Get borough stable identifiers
    borough_codes = borough_gdf["CODEID"].values if "CODEID" in borough_gdf.columns else (borough_gdf["source_segment_id"].values if "source_segment_id" in borough_gdf.columns else borough_gdf.index.values)
    borough_names = borough_gdf["NOM"].values if "NOM" in borough_gdf.columns else (borough_gdf["nom_arrond"].values if "nom_arrond" in borough_gdf.columns else borough_gdf.index.values)

    # Spatial index query (borough is tree, geobase is query)
    left_idx, right_idx = borough_gdf.sindex.query(geobase_gdf.geometry, predicate="intersects")

    if len(left_idx) > 0:
        # Vectorized intersections
        intersections = geobase_gdf.geometry.values[left_idx].intersection(borough_gdf.geometry.values[right_idx])
        inter_lengths = intersections.length

        # Build pandas DataFrame for fast groupby
        df_inter = pd.DataFrame({
            "seg_idx": left_idx,
            "borough_code": borough_codes[right_idx],
            "borough_name": borough_names[right_idx],
            "inter_len": inter_lengths
        })
        # Filter out 0 or nan overlap lengths
        df_inter = df_inter[df_inter["inter_len"] > 0.0].copy()

        if len(df_inter) > 0:
            # Group by segment index and count total candidate intersections
            counts = df_inter.groupby("seg_idx").size()
            candidate_counts[counts.index] = counts.values

            # Sort descending by overlap length so that groupby("seg_idx").first() picks the max
            df_sorted = df_inter.sort_values("inter_len", ascending=False)
            df_primary = df_sorted.groupby("seg_idx").first()

            # Join the max overlap length back to identify ties
            df_joined = df_inter.join(df_primary[["inter_len"]].rename(columns={"inter_len": "max_len"}), on="seg_idx")
            # Tie criteria: candidate with length within 0.1m of max, but different borough code
            df_ties = df_joined[(df_joined["inter_len"] >= df_joined["max_len"] - 0.1) & (df_joined["borough_code"] != df_primary.loc[df_joined["seg_idx"], "borough_code"].values)]
            tie_indices = set(df_ties["seg_idx"])

            # Fill output arrays using df_primary index
            for seg_idx, row in df_primary.iterrows():
                seg_len = geobase_gdf.geometry.iloc[seg_idx].length
                if seg_len > 0:
                    max_len = row["inter_len"]
                    frac = max_len / seg_len
                    overlap_lengths[seg_idx] = max_len
                    overlap_fractions[seg_idx] = frac
                    primary_borough_ids[seg_idx] = row["borough_code"]
                    primary_borough_names[seg_idx] = row["borough_name"]

                    if seg_idx in tie_indices:
                        ambiguity_flags[seg_idx] = 1

                    # Administrative boundaries have full coverage (except edge exceptions)
                    # If overlap fraction > 0.0, we accept it as match
                    if frac > 0.0:
                        if seg_idx in tie_indices:
                            linkage_statuses[seg_idx] = "review_required"
                        else:
                            linkage_statuses[seg_idx] = "accepted"

    res = geobase_gdf.copy()
    res["primary_borough_id"] = primary_borough_ids
    res["primary_borough_name"] = primary_borough_names
    res["overlap_length_m"] = overlap_lengths
    res["overlap_fraction"] = overlap_fractions
    res["candidate_count"] = candidate_counts
    res["ambiguity_flag"] = ambiguity_flags
    res["linkage_status"] = linkage_statuses
    res["linkage_method"] = "spatial_intersection"

    return res
