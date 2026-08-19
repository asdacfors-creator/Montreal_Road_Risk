"""Tests for scripts/audit_pothole_gpkg.py.

Tests read-only opening, layer discovery, layer mismatches, geometry validation,
fid uniqueness, date parsing, vehicle pattern classification, duplicate summary,
and exit codes.
"""

import gc
import os
import sqlite3
import tempfile
import pytest
import geopandas as gpd
from shapely.geometry import Point

from scripts.audit_pothole_gpkg import run_audit, _classify_vehicle_id, parse_date_flexible


@pytest.fixture
def temp_gpkg_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
    gc.collect()


def test_vehicle_classification():
    """Test vehicle classification logic."""
    assert _classify_vehicle_id("123") == "numeric_only"
    assert _classify_vehicle_id("NP-108") == "np_hyphen_number"
    assert _classify_vehicle_id("NP108") == "np_number"
    assert _classify_vehicle_id("CT104 J-F Hamond") == "ct_prefixed"
    assert _classify_vehicle_id("RM511") == "other_non_empty"
    assert _classify_vehicle_id(" ") == "blank"
    assert _classify_vehicle_id(None) == "blank"


def test_date_parsing():
    """Test flexible date parsing formats."""
    # T separator and 3 fractional
    t1 = parse_date_flexible("2021-01-25T07:35:20.063")
    assert t1.year == 2021
    assert t1.month == 1
    assert t1.microsecond == 63000

    # space separator and 6 fractional
    t2 = parse_date_flexible("2022-02-09 07:54:38.063000")
    assert t2.year == 2022
    assert t2.microsecond == 63000

    # without fractional seconds
    t3 = parse_date_flexible("2023-05-05 00:48:19")
    assert t3.year == 2023
    assert t3.second == 19
    assert t3.microsecond == 0


def test_valid_gpkg_audit(temp_gpkg_dir):
    """Test auditing a structurally valid GeoPackage."""
    gpkg_path = os.path.join(temp_gpkg_dir, "test_valid.gpkg")

    gdf = gpd.GeoDataFrame(
        {
            "fid": [1, 2],
            "Véhicule": ["NP-101", "NP-113"],
            "Date": ["2021-01-25T07:35:20.063", "2021-03-17 09:32:25.127"],
            "geometry": [Point(-73.6, 45.5), Point(-73.5, 45.6)],
        },
        crs="EPSG:4326",
    )

    gdf.to_file(gpkg_path, layer="remplissage_niddepoule_2021", driver="GPKG")

    res = run_audit(gpkg_path, 2021)
    assert res is not None
    assert res["raw_pass"] is True
    assert res["layer_info"]["layer_name"] == "remplissage_niddepoule_2021"
    assert res["layer_info"]["row_count"] == 2
    assert res["temporal"]["date_nulls"] == 0
    assert res["vehicle"]["pattern_counts"]["np_hyphen_number"] == 2


def test_mismatched_year_warnings(temp_gpkg_dir):
    """Test auditing when layer name or records mismatch expected year."""
    gpkg_path = os.path.join(temp_gpkg_dir, "test_mismatch.gpkg")

    gdf = gpd.GeoDataFrame(
        {
            "fid": [1, 2],
            "Véhicule": ["NP-101", "NP-113"],
            "Date": ["2021-01-25T07:35:20.063", "2022-03-17 09:32:25.127"],
            "geometry": [Point(-73.6, 45.5), Point(-73.5, 45.6)],
        },
        crs="EPSG:4326",
    )

    gdf.to_file(gpkg_path, layer="remplissage_niddepoule_2024", driver="GPKG")

    res = run_audit(gpkg_path, 2021)
    assert res is not None
    assert res["mismatches"]["filename_year"] is None
    assert res["mismatches"]["expected_year"] == 2021
    assert res["mismatches"]["layer_year"] == 2024
    assert res["mismatches"]["out_of_year_records_count"] == 1


def test_invalid_point_geometry(temp_gpkg_dir):
    """Test failure when geometry is null."""
    gpkg_path = os.path.join(temp_gpkg_dir, "test_invalid_geom.gpkg")

    gdf = gpd.GeoDataFrame(
        {
            "fid": [1, 2],
            "Véhicule": ["NP-101", "NP-113"],
            "Date": ["2021-01-25T07:35:20.063", "2021-03-17 09:32:25.127"],
            "geometry": [Point(-73.6, 45.5), None],
        },
        crs="EPSG:4326",
    )

    gdf.to_file(gpkg_path, layer="remplissage_niddepoule_2021", driver="GPKG")

    res = run_audit(gpkg_path, 2021)
    assert res is not None
    assert res["raw_pass"] is False
    assert res["geometry_quality"]["null_count"] == 1


def test_non_unique_fid(temp_gpkg_dir):
    """Test failure when fid values are duplicated."""
    gpkg_path = os.path.join(temp_gpkg_dir, "test_fid.gpkg")

    gdf = gpd.GeoDataFrame(
        {
            "Véhicule": ["NP-101", "NP-113"],
            "Date": ["2021-01-25T07:35:20.063", "2021-03-17 09:32:25.127"],
            "geometry": [Point(-73.6, 45.5), Point(-73.5, 45.6)],
        },
        crs="EPSG:4326",
    )

    gdf.to_file(gpkg_path, layer="remplissage_niddepoule_2021", driver="GPKG")

    # Recreate the table without constraint to allow duplicate fids
    conn = sqlite3.connect(gpkg_path)
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE remplissage_niddepoule_2021 RENAME TO old_table;")
    cursor.execute(
        "CREATE TABLE remplissage_niddepoule_2021 (fid INTEGER, geom BLOB, Véhicule TEXT, Date TEXT);"
    )
    cursor.execute(
        "INSERT INTO remplissage_niddepoule_2021 (fid, geom, Véhicule, Date) VALUES (1, X'00', 'NP-101', '2021-01-25');"
    )
    cursor.execute(
        "INSERT INTO remplissage_niddepoule_2021 (fid, geom, Véhicule, Date) VALUES (1, X'00', 'NP-113', '2021-03-17');"
    )
    conn.commit()
    conn.close()

    res = run_audit(gpkg_path, 2021)
    assert res is not None
    assert res["raw_pass"] is False
    assert res["fid_audit"]["unique"] is False
