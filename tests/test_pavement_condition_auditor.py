import os
import csv
import json
import sqlite3
import tempfile
import pytest
import subprocess
from datetime import datetime
from scripts.audit_pavement_condition import (
    calculate_sha256,
    normalize_header_key,
    parse_date,
    unpack_gpkg_geom,
    calculate_numeric_stats,
    audit_pavement_condition_file,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def create_mock_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow(r)


def create_mock_geojson(path, data, encoding="windows-1252"):
    with open(path, "w", encoding=encoding) as f:
        json.dump(data, f)


def create_mock_gpkg(path, table_name, columns, rows, srs_id=4326, app_id=0x47504B47):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    cursor.execute(f"PRAGMA application_id = {app_id};")

    # Create spatial ref table
    cursor.execute("""
    CREATE TABLE gpkg_spatial_ref_sys (
        srs_name TEXT, srs_id INTEGER PRIMARY KEY, organization TEXT,
        organization_coordsys_id INTEGER, definition TEXT, description TEXT
    );
    """)
    cursor.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES ('WGS 84', 4326, 'EPSG', 4326, 'undefined', 'undefined');"
    )
    cursor.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES ('NAD83 / MTM zone 8', 32188, 'EPSG', 32188, 'undefined', 'undefined');"
    )

    # Create geometry columns table
    cursor.execute("""
    CREATE TABLE gpkg_geometry_columns (
        table_name TEXT, column_name TEXT, geometry_type_name TEXT,
        srs_id INTEGER, z INTEGER, m INTEGER
    );
    """)
    cursor.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 'LINESTRING', ?, 0, 0);",
        (table_name, srs_id),
    )

    col_def = ", ".join([f"'{col}' {dtype}" for col, dtype in columns.items()])
    cursor.execute(
        f"CREATE TABLE '{table_name}' (fid INTEGER PRIMARY KEY AUTOINCREMENT, geom BLOB, {col_def});"
    )

    placeholders = ", ".join(["?"] * (len(columns) + 1))
    cursor.execute(
        f"INSERT INTO '{table_name}' (geom, {', '.join(columns.keys())}) VALUES ({placeholders});",
        rows[0],
    )
    conn.commit()
    conn.close()


def test_csv_parsing_and_consistent_widths(temp_workspace):
    csv_path = os.path.join(temp_workspace, "test_width.csv")
    create_mock_csv(csv_path, ["ID_TRC", "Rue"], [[1, "Rue A"], [2, "Rue B", "Extra"]])
    with pytest.raises(ValueError, match="width mismatch"):
        audit_pavement_condition_file(csv_path, set())


def test_utf8_csv_parsing(temp_workspace):
    csv_path = os.path.join(temp_workspace, "test_utf8.csv")
    create_mock_csv(
        csv_path,
        ["ID_TRC", "Rue", "DateReleve", "Indice PCI", "Etat PCI", "Indice IRI", "Etat IRI"],
        [[100, "Rue Saint-Denis", "2020-10-01", 80, "Bon", 2.5, "Bon"]],
    )
    res = audit_pavement_condition_file(csv_path, set())
    assert res["format"] == "CSV"
    assert res["data_rows"] == 1
    assert res["pci_stats"]["min"] == 80.0


def test_cp1252_geojson_parsing(temp_workspace):
    geojson_path = os.path.join(temp_workspace, "test_cp1252.json")
    data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[-73.5, 45.5], [-73.6, 45.5]]},
                "properties": {
                    "ID_TRC": 200,
                    "DateReleve": "2020-09-15",
                    "Indice PCI": 70,
                    "Etat PCI": "Moyen",
                    "Indice IRI": 3.0,
                    "Etat IRI": "Moyen",
                },
            }
        ],
    }
    create_mock_geojson(geojson_path, data)
    res = audit_pavement_condition_file(geojson_path, set())
    assert res["format"] == "GeoJSON"
    assert res["crs"] == "urn:ogc:def:crs:OGC:1.3:CRS84"
    assert res["data_rows"] == 1


def test_invalid_json(temp_workspace):
    path = os.path.join(temp_workspace, "invalid.json")
    with open(path, "w") as f:
        f.write("{invalid json")
    with pytest.raises(ValueError, match="JSON parse error"):
        audit_pavement_condition_file(path, set())


def test_corrupt_gpkg(temp_workspace):
    path = os.path.join(temp_workspace, "corrupt.gpkg")
    with open(path, "wb") as f:
        f.write(b"not a sqlite db")
    with pytest.raises(ValueError, match="PRAGMA integrity_check failed|not a database"):
        audit_pavement_condition_file(path, set())


def test_gpkg_application_id_and_integrity(temp_workspace):
    path = os.path.join(temp_workspace, "bad_id.gpkg")
    create_mock_gpkg(path, "Auscultation", {"ID_TRC": "INTEGER"}, [(None, 1)], app_id=0x12345678)
    with pytest.raises(ValueError, match="Expected GeoPackage application_id"):
        audit_pavement_condition_file(path, set())


def test_header_alias_normalization():
    assert normalize_header_key("Indice PCI") == "Indice_PCI"
    assert normalize_header_key("Etat PCI") == "Etat_PCI"
    assert normalize_header_key("Indice IRI") == "Indice_IRI"
    assert normalize_header_key("Etat IRI") == "Etat_IRI"


def test_date_parsing():
    assert parse_date("2020-10-15").year == 2020
    assert parse_date("2020/10/15").year == 2020
    assert parse_date("15/10/2020").year == 2020
    assert parse_date("20201015").year == 2020
    assert parse_date("2020-10-15 12:00:00").year == 2020
    assert parse_date("invalid") is None


def test_multi_year_campaign_dates(temp_workspace):
    csv_path = os.path.join(temp_workspace, "multi_year.csv")
    create_mock_csv(
        csv_path,
        ["ID_TRC", "DateReleve"],
        [[1, "2009-10-01"], [2, "2010-05-15"], [3, "2011-06-20"]],
    )
    res = audit_pavement_condition_file(csv_path, set())
    assert res["year_distribution"] == {2009: 1, 2010: 1, 2011: 1}


def test_pci_numerical_range(temp_workspace):
    csv_path = os.path.join(temp_workspace, "pci_range.csv")
    create_mock_csv(
        csv_path,
        ["ID_TRC", "Indice PCI", "Etat PCI"],
        [
            [1, 120, "Bon"],  # out of bounds
            [2, -5, "Mauvais"],  # out of bounds
        ],
    )
    res = audit_pavement_condition_file(csv_path, set())
    assert res["pci_out_of_bounds"] == 2


def test_iri_parsing_and_missing(temp_workspace):
    csv_path = os.path.join(temp_workspace, "iri_test.csv")
    create_mock_csv(
        csv_path,
        ["ID_TRC", "Indice IRI", "Etat IRI"],
        [
            [1, 2.5, "Bon"],
            [2, "-", "N/A"],  # missing
            [3, -1.0, "Mauvais"],  # negative
            [4, 18.2, "Mauvais"],  # extreme
        ],
    )
    res = audit_pavement_condition_file(csv_path, set())
    assert res["iri_missing"] == 1
    assert res["iri_negative"] == 1
    assert res["iri_extreme_count"] == 1


def test_iri_zero_plus_dash_sentinel_detection(temp_workspace):
    csv_path = os.path.join(temp_workspace, "sentinel.csv")
    create_mock_csv(
        csv_path,
        ["ID_TRC", "Indice IRI", "Etat IRI"],
        [
            [1, 0.0, "-"],  # sentinel candidate
            [2, 0.0, "Bon"],  # genuine zero (or not sentinel)
        ],
    )
    res = audit_pavement_condition_file(csv_path, set())
    assert res["iri_sentinel_candidates"] == 1


def test_duplicate_id_detection(temp_workspace):
    csv_path = os.path.join(temp_workspace, "dup_ids.csv")
    create_mock_csv(csv_path, ["ID_TRC"], [[100], [100], [200]])
    res = audit_pavement_condition_file(csv_path, set())
    assert res["duplicate_id_excess"] == 1
    assert res["duplicate_id_groups"] == 1
    assert res["duplicate_participating_rows"] == 2


def test_null_and_invalid_geometry(temp_workspace):
    geojson_path = os.path.join(temp_workspace, "null_geom.json")
    data = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": None, "properties": {"ID_TRC": 1}},
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": "invalid"},
                "properties": {"ID_TRC": 2},
            },
        ],
    }
    create_mock_geojson(geojson_path, data)
    res = audit_pavement_condition_file(geojson_path, set())
    assert res["geom_stats"]["null_geom"] == 1
    assert res["geom_stats"]["invalid_geom"] == 1


def test_crs_reporting(temp_workspace):
    geojson_path = os.path.join(temp_workspace, "crs.json")
    data = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32188"}},
        "features": [],
    }
    create_mock_geojson(geojson_path, data)
    res = audit_pavement_condition_file(geojson_path, set())
    assert res["crs"] == "urn:ogc:def:crs:EPSG::32188"


def test_geobase_id_set_comparison(temp_workspace):
    csv_path = os.path.join(temp_workspace, "geobase_match.csv")
    create_mock_csv(csv_path, ["ID_TRC"], [[10], [20], [30]])
    geobase_ids = {10, 20}
    res = audit_pavement_condition_file(csv_path, geobase_ids)
    assert res["geobase_matched"] == 2
    assert res["geobase_match_rate"] == pytest.approx(66.67, 0.01)


def test_auditor_exit_codes():
    res = subprocess.run(
        [
            ".\\.venv\\Scripts\\python.exe",
            "scripts/audit_pavement_condition.py",
            "non_existent.csv",
            "--geobase",
            "non_existent.json",
        ],
        capture_output=True,
    )
    assert res.returncode == 1


def test_manual_download_verifier_detection_all_six():
    # Test that the verifier utility correctly parses and groups all six files
    from scripts.verify_manual_downloads import _group_files_by_dataset

    datasets = {
        "pavement_condition": {
            "required_status": "required_candidate",
            "download_status": "not_downloaded",
        }
    }
    inventory = [
        {"original_filename": "auscultation-chaussees-2010.csv", "folder": "pavement_condition"},
        {"original_filename": "auscultation-chaussees-2015.csv", "folder": "pavement_condition"},
        {
            "original_filename": "auscultation-chaussees-2018-arteriel.csv",
            "folder": "pavement_condition",
        },
        {
            "original_filename": "auscultation-chaussees-2020-arteriel.json",
            "folder": "pavement_condition",
        },
        {
            "original_filename": "auscultation-chaussees-2022-local.gpkg",
            "folder": "pavement_condition",
        },
        {"original_filename": "auscultation-chaussee-2024.gpkg", "folder": "pavement_condition"},
    ]
    matched, _ = _group_files_by_dataset(inventory, datasets)
    assert len(matched["pavement_condition"]) == 6
