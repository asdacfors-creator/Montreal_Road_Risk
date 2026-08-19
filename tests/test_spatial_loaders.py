import os
import tempfile
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from montreal_road_risk.io.loaders import load_csv, load_geojson


def test_load_csv_with_encodings():
    # Setup temporary file with French characters and different encodings
    content = "ID,Nom,Valeur\n1,Montréal,100\n2,Québec,200\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test UTF-8 with BOM (utf-8-sig)
        utf8_path = os.path.join(tmpdir, "test_utf8.csv")
        with open(utf8_path, "w", encoding="utf-8-sig") as f:
            f.write(content)

        df1 = load_csv(utf8_path)
        assert len(df1) == 2
        assert df1["Nom"].iloc[0] == "Montréal"

        # Test CP1252 fallback
        cp1252_path = os.path.join(tmpdir, "test_cp1252.csv")
        with open(cp1252_path, "w", encoding="cp1252") as f:
            f.write(content)

        df2 = load_csv(cp1252_path)
        assert len(df2) == 2
        assert df2["Nom"].iloc[0] == "Montréal"


def test_load_geojson_with_fallback_encoding():
    # Setup small GeoJSON structure
    geojson_content = """{
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": { "type": "Point", "coordinates": [-73.55, 45.5] },
                "properties": { "name": "Montréal" }
            }
        ]
    }"""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test loading windows-1252 encoded GeoJSON file (which will trigger fallback)
        fpath = os.path.join(tmpdir, "test_french.geojson")
        with open(fpath, "w", encoding="windows-1252") as f:
            f.write(geojson_content)

        gdf = load_geojson(fpath)
        assert len(gdf) == 1
        assert gdf.crs is not None
        assert gdf["name"].iloc[0] == "Montréal"
