import numpy as np
import pyproj
import shapely


def check_invalid_geometries(gdf):
    """Count invalid, null, and empty geometries in a GeoDataFrame."""
    # Handle possible missing geometry column
    if gdf.geometry is None:
        return 0, 0, 0
    null_count = gdf.geometry.isna().sum()
    empty_count = gdf.geometry.is_empty.sum()
    # is_valid can raise errors if geometry is null, so handle that safely
    valid_mask = gdf.geometry.notna()
    invalid_count = (~gdf.geometry[valid_mask].is_valid).sum()
    return int(null_count), int(empty_count), int(invalid_count)


def calculate_roundtrip_error(gdf, source_crs_val, target_crs_val):
    """Calculate maximum round-trip transformation error for a sample of points."""
    if len(gdf) == 0 or gdf.geometry is None:
        return 0.0

    # Sample up to 100 points or centroids
    sample_geoms = gdf.geometry.dropna().head(100)
    if len(sample_geoms) == 0:
        return 0.0

    sample_points = [g.centroid for g in sample_geoms]

    try:
        transformer_fwd = pyproj.Transformer.from_crs(
            source_crs_val, target_crs_val, always_xy=True
        )
        transformer_bwd = pyproj.Transformer.from_crs(
            target_crs_val, source_crs_val, always_xy=True
        )

        max_error = 0.0
        for pt in sample_points:
            x, y = pt.x, pt.y
            x_proj, y_proj = transformer_fwd.transform(x, y)
            x_back, y_back = transformer_bwd.transform(x_proj, y_proj)
            error = np.sqrt((x - x_back) ** 2 + (y - y_back) ** 2)
            if error > max_error:
                max_error = error
        return float(max_error)
    except Exception:
        return -1.0


def check_axis_swap(gdf, crs_val):
    """Check if coordinates show evidence of unexpected axis swapping (e.g. Lat/Lon swapped)."""
    if len(gdf) == 0 or gdf.geometry is None:
        return False
    sample = gdf.geometry.dropna().head(5)
    if len(sample) == 0:
        return False

    # In Montreal, WGS84 coordinates are Longitude ~ -73.x, Latitude ~ 45.x
    # Projected MTM8 / EPSG:2950 coordinates are X ~ 290000.x, Y ~ 5030000.x
    crs = pyproj.CRS(crs_val)
    for geom in sample:
        pt = geom.centroid
        if crs.is_geographic:
            # If Latitude is in pt.x and Longitude is in pt.y (which is swapped since X=Lon, Y=Lat)
            # Normal: pt.x (lon) ~ -73, pt.y (lat) ~ 45
            # Swapped: pt.x ~ 45, pt.y ~ -73
            if 40.0 <= pt.x <= 50.0 and -80.0 <= pt.y <= -70.0:
                return True
        else:
            # For MTM8/EPSG:32188/EPSG:2950, normal X is around 200000-400000, Y is around 5000000.
            # If swapped: pt.x > 1000000, pt.y < 1000000
            if pt.x > 4000000 and pt.y < 1000000:
                return True
    return False


def count_non_finite_coordinates(gdf):
    """Count coordinates that are NaN or Inf in the GeoDataFrame."""
    if len(gdf) == 0 or gdf.geometry is None:
        return 0
    non_finite = 0
    for geom in gdf.geometry.dropna():
        coords = shapely.get_coordinates(geom)
        if not np.isfinite(coords).all():
            non_finite += 1
    return non_finite


def calculate_envelope_containment(gdf, admin_bbox):
    """Count how many geometries lie inside and outside the administrative bounding box."""
    if len(gdf) == 0 or gdf.geometry is None or admin_bbox is None:
        return 0, 0
    minx, miny, maxx, maxy = admin_bbox

    # Calculate bounds of each geometry in gdf
    bounds = gdf.geometry.bounds
    within_mask = (
        (bounds["minx"] >= minx)
        & (bounds["maxx"] <= maxx)
        & (bounds["miny"] >= miny)
        & (bounds["maxy"] <= maxy)
    )

    inside_count = within_mask.sum()
    outside_count = len(gdf) - inside_count
    return int(inside_count), int(outside_count)


def perform_spatial_qa(
    source_gdf, dest_gdf, admin_bbox=None, source_crs="EPSG:4326", target_crs="EPSG:32188"
):
    """Execute a complete spatial QA suite comparing source and destination GeoDataFrames."""
    src_rows = len(source_gdf)
    dest_rows = len(dest_gdf)

    src_geom_dist = (
        source_gdf.geometry.geom_type.value_counts().to_dict()
        if source_gdf.geometry is not None
        else {}
    )
    dest_geom_dist = (
        dest_gdf.geometry.geom_type.value_counts().to_dict()
        if dest_gdf.geometry is not None
        else {}
    )

    src_null, src_empty, src_invalid = check_invalid_geometries(source_gdf)
    dest_null, dest_empty, dest_invalid = check_invalid_geometries(dest_gdf)

    src_bounds = (
        tuple(source_gdf.total_bounds)
        if len(source_gdf) > 0 and source_gdf.geometry is not None
        else (0.0, 0.0, 0.0, 0.0)
    )
    dest_bounds = (
        tuple(dest_gdf.total_bounds)
        if len(dest_gdf) > 0 and dest_gdf.geometry is not None
        else (0.0, 0.0, 0.0, 0.0)
    )

    inside, outside = calculate_envelope_containment(dest_gdf, admin_bbox)

    roundtrip_err = calculate_roundtrip_error(source_gdf, source_crs, target_crs)
    axis_swap_detected = check_axis_swap(dest_gdf, target_crs)
    non_finite_count = count_non_finite_coordinates(dest_gdf)

    # Fetch a representative sample of coordinates
    sample_src_coords = []
    sample_dest_coords = []
    if len(source_gdf) > 0 and source_gdf.geometry is not None:
        valid_geoms = source_gdf.geometry.dropna()
        if len(valid_geoms) > 0:
            pt_src = valid_geoms.iloc[0].centroid
            sample_src_coords = [pt_src.x, pt_src.y]
    if len(dest_gdf) > 0 and dest_gdf.geometry is not None:
        valid_geoms = dest_gdf.geometry.dropna()
        if len(valid_geoms) > 0:
            pt_dest = valid_geoms.iloc[0].centroid
            sample_dest_coords = [pt_dest.x, pt_dest.y]

    return {
        "source_row_count": src_rows,
        "destination_row_count": dest_rows,
        "source_geometry_types": src_geom_dist,
        "destination_geometry_types": dest_geom_dist,
        "source_null_geoms": src_null,
        "destination_null_geoms": dest_null,
        "source_empty_geoms": src_empty,
        "destination_empty_geoms": dest_empty,
        "source_invalid_geoms": src_invalid,
        "destination_invalid_geoms": dest_invalid,
        "source_bounds": src_bounds,
        "destination_bounds": dest_bounds,
        "inside_admin_envelope": inside,
        "outside_admin_envelope": outside,
        "sample_source_coordinate": sample_src_coords,
        "sample_destination_coordinate": sample_dest_coords,
        "roundtrip_error": roundtrip_err,
        "axis_swap_detected": axis_swap_detected,
        "non_finite_coordinate_count": non_finite_count,
    }
