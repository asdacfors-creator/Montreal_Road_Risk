import os
import zipfile
import csv
import json
import tempfile
import pytest
import subprocess
from scripts.audit_road_assets import (
    verify_zip,
    parse_geojson,
    audit_geometries,
    audit_attributes,
    parse_compact_date,
    audit_dates,
    audit_reference_csv,
    check_reference_coverage,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def create_zip(zip_path, member_name, content_bytes):
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(member_name, content_bytes)


def test_valid_zip_and_geojson_parsing(temp_dir):
    zip_path = os.path.join(temp_dir, "test.zip")
    member_name = "VOI_CHAUSSEE_S_C22_GeoJSON.json"

    # Valid GeoJSON
    geojson_data = {
        "type": "FeatureCollection",
        "name": "VOI_CHAUSSEE_S_C22",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-73.5, 45.5], [-73.6, 45.5], [-73.6, 45.6], [-73.5, 45.5]]],
                },
                "properties": {
                    "ID_VOI_CHAUSSEE_AGR": 1000,
                    "DATECONSTRUCTION": "20200101000000",
                    "DATECONSTRUCTIONPREC_REF": "DATE construction précise",
                    "DATERESURFACAGE": None,
                    "MATERIAUCHAUSSEE_REF": "Asphalte",
                },
            }
        ],
    }
    create_zip(zip_path, member_name, json.dumps(geojson_data).encode("utf-8"))

    # Test parser directly on parsed member.
    res = parse_geojson(zip_path, member_name)
    assert res["top_level_type"] == "FeatureCollection"
    assert res["feature_count"] == 1
    assert res["all_schemas_match"] is True


def test_corrupt_zip(temp_dir):
    zip_path = os.path.join(temp_dir, "corrupt.zip")
    with open(zip_path, "wb") as f:
        f.write(b"not a zip file content")
    with pytest.raises(ValueError, match="Not a genuine ZIP archive"):
        verify_zip(zip_path)


def test_unsafe_member_path(temp_dir):
    zip_path = os.path.join(temp_dir, "unsafe.zip")
    create_zip(zip_path, "../unsafe_member.json", b"{}")
    with pytest.raises(ValueError, match="Unsafe archive member path"):
        verify_zip(zip_path)


def test_missing_geojson_member(temp_dir):
    zip_path = os.path.join(temp_dir, "missing.zip")
    create_zip(zip_path, "wrong_name.json", b"{}")
    with pytest.raises(ValueError, match="Expected member name VOI_CHAUSSEE_S_C22_GeoJSON.json"):
        verify_zip(zip_path)


def test_multiple_unexpected_members(temp_dir):
    zip_path = os.path.join(temp_dir, "multiple.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("member1.json", b"{}")
        z.writestr("member2.json", b"{}")
    with pytest.raises(ValueError, match="Expected exactly 1 archive member"):
        verify_zip(zip_path)


def test_invalid_json(temp_dir):
    zip_path = os.path.join(temp_dir, "invalid.zip")
    create_zip(zip_path, "VOI_CHAUSSEE_S_C22_GeoJSON.json", b"{invalid json")
    with pytest.raises(ValueError, match="JSON parse error"):
        parse_geojson(zip_path, "VOI_CHAUSSEE_S_C22_GeoJSON.json")


def test_non_featurecollection_json(temp_dir):
    zip_path = os.path.join(temp_dir, "non_fc.zip")
    create_zip(zip_path, "VOI_CHAUSSEE_S_C22_GeoJSON.json", b'{"type": "Feature"}')
    with pytest.raises(ValueError, match="Expected top-level object type"):
        parse_geojson(zip_path, "VOI_CHAUSSEE_S_C22_GeoJSON.json")


def test_geometry_null_and_invalid():
    # Null geometry
    features = [
        {"geometry": None, "properties": {"ID_VOI_CHAUSSEE_AGR": 1}},
        # Invalid geometry structure
        {
            "geometry": {"type": "Polygon", "coordinates": "invalid"},
            "properties": {"ID_VOI_CHAUSSEE_AGR": 2},
        },
    ]
    res = audit_geometries(features)
    assert res["null_geometries"] == 1
    assert res["invalid_geometries"] == 1


def test_duplicate_identifiers():
    features = [
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-73.5, 45.5], [-73.6, 45.5], [-73.6, 45.6], [-73.5, 45.5]]],
            },
            "properties": {"ID_VOI_CHAUSSEE_AGR": 100},
        },
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-73.5, 45.5], [-73.6, 45.5], [-73.6, 45.6], [-73.5, 45.5]]],
            },
            "properties": {"ID_VOI_CHAUSSEE_AGR": 100},
        },
    ]
    # Check duplicate ID + geom combinations and unique counts
    res_geom = audit_geometries(features)
    res_attr = audit_attributes(features)
    assert res_geom["duplicate_id_geom_combinations"] == 1
    assert res_attr["ID_VOI_CHAUSSEE_AGR"]["unique_count"] == 1


def test_compact_date_parsing():
    assert parse_compact_date("20260704000000").year == 2026
    with pytest.raises(ValueError, match="Invalid date string format length"):
        parse_compact_date("20260704")
    with pytest.raises(ValueError, match="Unparseable date string"):
        parse_compact_date("20260704990000")  # invalid hour/minute/second


def test_construction_precision_and_resurfacing_missingness():
    features = [
        {
            "properties": {
                "DATECONSTRUCTION": "20200101000000",
                "DATECONSTRUCTIONPREC_REF": "DATE construction précise",
                "DATERESURFACAGE": None,
                "DATE_VERSION": "20260704000000",
            }
        },
        {
            "properties": {
                "DATECONSTRUCTION": "20200101000000",
                "DATECONSTRUCTIONPREC_REF": "Inconnu",
                "DATERESURFACAGE": "20220101000000",
                "DATE_VERSION": "20260704000000",
            }
        },
    ]
    res_dates = audit_dates(features)
    assert res_dates["precision_distribution"]["Inconnu"] == 1
    assert res_dates["precision_distribution"]["DATE construction précise"] == 1
    assert res_dates["resurfacing_missing"] == 1
    assert res_dates["resurfacing_parseable"] == 1


def test_reference_csv_validation(temp_dir):
    csv_path = os.path.join(temp_dir, "ref.csv")
    with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ATTRIBUT", "REFERENCE"])
        writer.writerow(["MATERIAU_REF", "Asphalte"])
        writer.writerow(["MATERIAU_REF", "Béton"])

    csv_res = audit_reference_csv(csv_path)
    assert csv_res["encoding"] == "UTF-8 with BOM"
    assert csv_res["data_row_count"] == 2
    assert "MATERIAU_REF" in csv_res["ref_domains"]
    assert "Asphalte" in csv_res["ref_domains"]["MATERIAU_REF"]


def test_alias_mapping_and_reference_coverage():
    ref_domains = {
        "MATERIAU_REF": {"Asphalte", "Béton"},
        "CATEGORIECHAUSSEE_REF": {"Rue", "Autoroute"},
    }
    features = [
        {"properties": {"MATERIAUCHAUSSEE_REF": "Asphalte", "CATEGORIECHAUSSEE_REF": "Rue"}},
        {
            "properties": {
                "MATERIAUCHAUSSEE_REF": "Pavé",  # unmapped value
                "CATEGORIECHAUSSEE_REF": "Rue",
            }
        },
    ]
    res = check_reference_coverage(features, ref_domains)
    assert "Pavé" in res["MATERIAUCHAUSSEE_REF"]["unmapped_observed"]
    assert "Béton" in res["MATERIAUCHAUSSEE_REF"]["documented_but_unused"]


def test_auditor_exit_codes(temp_dir):
    # Test script command-line failures exit code
    res = subprocess.run(
        [
            ".\\.venv\\Scripts\\python.exe",
            "scripts/audit_road_assets.py",
            "--archive",
            "non_existent.zip",
            "--reference",
            "non_existent.csv",
        ],
        capture_output=True,
    )
    assert res.returncode == 1


def test_manual_download_verifier_detection():
    # Verify that both road assets files are scanned by the verifier utility
    from scripts.verify_manual_downloads import _group_files_by_dataset

    datasets = {
        "road_assets_pavement": {
            "required_status": "required_candidate",
            "download_status": "not_downloaded",
        }
    }
    inventory = [
        {"original_filename": "voi_chaussee_s_c22_geojson.zip", "folder": "road_assets"},
        {"original_filename": "voi_liste_valeurs_csv.csv", "folder": "road_assets"},
    ]
    matched, _ = _group_files_by_dataset(inventory, datasets)
    assert len(matched["road_assets_pavement"]) == 2
