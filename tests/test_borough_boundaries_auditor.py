import json
import os
import sys
import tempfile
import pytest
import subprocess
import shapely.geometry
from unittest import mock

from scripts.audit_borough_boundaries import (
    calculate_sha256,
    audit_file_integrity,
    audit_crs,
    audit_features_schema,
    audit_identifiers,
    audit_entity_types,
    _check_rings,
    _check_overlaps,
    _process_feature_geometry,
    _extract_geometries,
    audit_geometries,
    audit_geojson,
    main,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_calculate_sha256(temp_dir):
    temp_file = os.path.join(temp_dir, "test.txt")
    with open(temp_file, "wb") as f:
        f.write(b"test data")
    expected = "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"
    assert calculate_sha256(temp_file) == expected


def test_valid_geojson_parsing(temp_dir):
    geojson_path = os.path.join(temp_dir, "valid.geojson")
    geojson_data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32188"}},
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[270000, 5030000], [271000, 5030000], [271000, 5031000], [270000, 5030000]]
                    ],
                },
                "properties": {
                    "CODEID": 1,
                    "NOM": "LaSalle",
                    "TYPE": "Arrondissement",
                    "DATEMODIF": "2023-11-29",
                },
            }
        ],
    }
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f)

    # Test integrity check
    data = audit_file_integrity(geojson_path)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1

    # Test CRS check
    audit_crs(data)

    # Test schema check
    audit_features_schema(data["features"])

    # Test identifiers check
    audit_identifiers(data["features"])

    # Test entity types check
    audit_entity_types(data["features"])


def test_invalid_json_format(temp_dir):
    invalid_path = os.path.join(temp_dir, "invalid.geojson")
    with open(invalid_path, "w", encoding="utf-8") as f:
        f.write("{invalid json")

    with pytest.raises(SystemExit):
        audit_file_integrity(invalid_path)


def test_wrong_root_type(temp_dir):
    wrong_path = os.path.join(temp_dir, "wrong_root.geojson")
    wrong_data = {"type": "Feature", "properties": {}}
    with open(wrong_path, "w", encoding="utf-8") as f:
        json.dump(wrong_data, f)

    with pytest.raises(SystemExit):
        audit_file_integrity(wrong_path)


def test_missing_features_array(temp_dir):
    missing_path = os.path.join(temp_dir, "missing_features.geojson")
    missing_data = {"type": "FeatureCollection"}
    with open(missing_path, "w", encoding="utf-8") as f:
        json.dump(missing_data, f)

    with pytest.raises(SystemExit):
        audit_file_integrity(missing_path)


def test_missing_and_unexpected_crs(temp_dir):
    # Missing CRS
    data_no_crs = {"type": "FeatureCollection", "features": []}
    audit_crs(data_no_crs)  # should print warnings but not crash

    # Unexpected CRS name
    data_wrong_crs = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": [],
    }
    audit_crs(data_wrong_crs)


def test_null_geometry():
    feature = {"type": "Feature", "geometry": None, "properties": {"NOM": "Test"}}
    name, geom, g_type, err = _process_feature_geometry(0, feature)
    assert name == "Test"
    assert geom is None
    assert g_type is None
    assert err is None


def test_empty_geometry():
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": []},
        "properties": {"NOM": "Test"},
    }
    name, geom, g_type, err = _process_feature_geometry(0, feature)
    assert name == "Test"
    assert geom.is_empty
    assert g_type == "Polygon"


def test_invalid_coordinate_nesting():
    # Insufficient coordinates
    coords = [[[10.0, 20.0], [20.0, 30.0]]]
    p_c, r_c, u_r, i_p, n_f = _check_rings(coords, "Polygon")
    assert i_p == 1
    assert u_r == 1  # also unclosed


def test_non_finite_coordinates():
    # Infinity coordinate
    coords = [[[10.0, float("inf")], [20.0, 30.0], [30.0, 40.0], [10.0, float("inf")]]]
    p_c, r_c, u_r, i_p, n_f = _check_rings(coords, "Polygon")
    assert n_f == 2  # two vertices have non-finite coords


def test_unclosed_rings():
    # Not matching first/last
    coords = [[[10.0, 20.0], [20.0, 30.0], [30.0, 40.0], [50.0, 60.0]]]
    p_c, r_c, u_r, i_p, n_f = _check_rings(coords, "Polygon")
    assert u_r == 1


def test_duplicate_identifiers():
    features = [
        {"type": "Feature", "properties": {"CODEID": 1, "NOM": "A"}},
        {"type": "Feature", "properties": {"CODEID": 1, "NOM": "B"}},
    ]
    # audit_identifiers prints warnings, we check it completes without crash
    audit_identifiers(features)


def test_duplicate_geometries_and_overlaps():
    # Identical geometries
    geom1 = shapely.geometry.Polygon([[0, 0], [0, 10], [10, 10], [0, 0]])
    geom2 = shapely.geometry.Polygon([[0, 0], [0, 10], [10, 10], [0, 0]])
    geoms = [(0, "A", geom1), (1, "B", geom2)]

    overlaps = _check_overlaps(geoms)
    # Overlap area should be identical to area of geom1 (50.0)
    assert len(overlaps) == 1
    assert overlaps[0][0] == "A"
    assert overlaps[0][1] == "B"
    assert pytest.approx(overlaps[0][2]) == 50.0


def test_multiple_types_blank_and_null_properties():
    features = [
        {"type": "Feature", "properties": {"NOM": "A", "TYPE": "Arrondissement", "COMMENT": None}},
        {"type": "Feature", "properties": {"NOM": "B", "TYPE": "Ville liée", "COMMENT": "  "}},
    ]
    audit_features_schema(features)
    audit_entity_types(features)


def test_invalid_datemodif():
    features = [{"type": "Feature", "properties": {"NOM": "A", "DATEMODIF": "Invalid Date"}}]
    audit_features_schema(features)


def test_main_cli_success(temp_dir):
    geojson_path = os.path.join(temp_dir, "test.geojson")
    geojson_data = {"type": "FeatureCollection", "features": []}
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f)

    with mock.patch("sys.argv", ["audit_borough_boundaries.py", geojson_path]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0


def test_source_file_unchanged(temp_dir):
    geojson_path = os.path.join(temp_dir, "test.geojson")
    geojson_data = {"type": "FeatureCollection", "features": []}
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f)

    hash_before = calculate_sha256(geojson_path)
    # Run audit
    audit_geojson(geojson_path)
    hash_after = calculate_sha256(geojson_path)
    assert hash_before == hash_after
