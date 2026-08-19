import pyproj


def get_crs_info(crs_val):
    """Retrieve detailed information about a CRS using pyproj."""
    crs = pyproj.CRS(crs_val)

    # Extract datum and ellipsoid info safely
    datum_name = crs.datum.name if crs.datum else "Unknown"
    ellipsoid_name = crs.ellipsoid.name if crs.ellipsoid else "Unknown"

    # Extract axis info
    axis_info_list = []
    for axis in crs.axis_info:
        axis_info_list.append(f"{axis.name} ({axis.direction}) in {axis.unit_name}")
    axis_str = ", ".join(axis_info_list)

    # Extract area of use
    area = crs.area_of_use
    area_str = f"{area.name} (Bounds: {area.bounds})" if area else "Unknown"

    return {
        "crs_name": crs.name,
        "datum": datum_name,
        "ellipsoid": ellipsoid_name,
        "units": crs.axis_info[0].unit_name if crs.axis_info else "Unknown",
        "axis_info": axis_str,
        "area_of_use": area_str,
    }


def get_transformation_details(source_crs_val, target_crs_val):
    """Extract transformation operation, warnings, grids requirements using pyproj.Transformer."""
    try:
        transformer = pyproj.Transformer.from_crs(source_crs_val, target_crs_val, always_xy=True)
        description = transformer.description
        has_grids = transformer.has_grids
        # In newer pyproj versions, we can check if a fallback is used when grid is missing
        # or if the transformation is valid.
        return {
            "operation": description,
            "has_grids": has_grids,
            "warnings": "None"
            if not has_grids
            else "Grids required, check local proj installation.",
            "fallback_used": not has_grids,  # if no grid is needed, fallback is not used
        }
    except Exception as e:
        return {
            "operation": f"Error: {str(e)}",
            "has_grids": False,
            "warnings": f"Failed to instantiate transformer: {str(e)}",
            "fallback_used": True,
        }


def reproject_gdf(gdf, target_crs):
    """Reproject a GeoDataFrame to a target CRS."""
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS defined. Cannot reproject.")
    return gdf.to_crs(target_crs)
