import geopandas as gpd
import pandas as pd
import pyogrio


def load_csv(filepath, **kwargs):
    """Load a CSV file with automatic encoding detection (UTF-8-SIG or CP1252 fallback)."""
    try:
        # Try UTF-8-SIG first to handle UTF-8 with BOM
        return pd.read_csv(filepath, encoding="utf-8-sig", **kwargs)
    except (UnicodeDecodeError, ValueError):
        # Fallback to CP1252 (commonly used for French characters on Windows)
        return pd.read_csv(filepath, encoding="cp1252", **kwargs)


def load_geojson(filepath, **kwargs):
    """Load a GeoJSON file safely using GeoPandas with fallback encoding support."""
    try:
        return gpd.read_file(filepath, driver="GeoJSON", **kwargs)
    except Exception:
        return gpd.read_file(filepath, driver="GeoJSON", encoding="windows-1252", **kwargs)


def list_gpkg_layers(filepath):
    """Discover layers in a GeoPackage using pyogrio."""
    return pyogrio.list_layers(filepath)


def load_gpkg_layer(filepath, layer_name=None, **kwargs):
    """Load a specific layer from a GeoPackage."""
    if layer_name is None:
        layers = list_gpkg_layers(filepath)
        if len(layers) > 0:
            layer_name = layers[0][0]
        else:
            raise ValueError(f"No layers found in GPKG: {filepath}")
    return gpd.read_file(filepath, layer=layer_name, **kwargs)
