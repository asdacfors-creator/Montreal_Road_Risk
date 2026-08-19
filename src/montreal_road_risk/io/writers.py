import geopandas as gpd
import pandas as pd


def write_parquet(df, filepath, **kwargs):
    """Write a standard DataFrame to a Parquet file."""
    df.to_parquet(filepath, index=False, **kwargs)


def write_geoparquet(gdf, filepath, **kwargs):
    """Write a GeoDataFrame to a GeoParquet file."""
    gdf.to_parquet(filepath, index=False, **kwargs)


def verify_parquet_roundtrip(filepath, expected_df, is_spatial=False):
    """Read back and verify the written Parquet/GeoParquet file against expected properties."""
    if is_spatial:
        actual = gpd.read_parquet(filepath)
        if not isinstance(actual, gpd.GeoDataFrame):
            raise TypeError("Read back object is not a GeoDataFrame.")

        # Compare CRS
        if actual.crs != expected_df.crs:
            raise ValueError(f"CRS mismatch: {actual.crs} vs {expected_df.crs}")

        # Compare geometry types
        actual_geom_types = actual.geometry.geom_type.unique()
        expected_geom_types = expected_df.geometry.geom_type.unique()
        if set(actual_geom_types) != set(expected_geom_types):
            raise ValueError(
                f"Geometry type mismatch: {actual_geom_types} vs {expected_geom_types}"
            )
    else:
        actual = pd.read_parquet(filepath)
        if not isinstance(actual, pd.DataFrame):
            raise TypeError("Read back object is not a DataFrame.")

    # Compare row count
    if len(actual) != len(expected_df):
        raise ValueError(f"Row count mismatch: {len(actual)} vs {len(expected_df)}")

    # Compare columns
    if list(actual.columns) != list(expected_df.columns):
        raise ValueError(f"Columns mismatch: {list(actual.columns)} vs {list(expected_df.columns)}")

    return True
