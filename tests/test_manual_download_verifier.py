"""Tests for manual download verification utility.

Verifies SHA-256 calculation, inventory scanning, manifest loading,
and --allow-missing logic.
"""

import os
import tempfile
import pytest

from scripts.verify_manual_downloads import (
    calculate_sha256,
    load_manifest,
    scan_raw_directories,
    generate_report,
)


@pytest.fixture
def temp_workspace():
    """Fixture to create a temporary mock data structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directories
        raw_dir = os.path.join(tmpdir, "data", "raw")
        os.makedirs(raw_dir)

        # Create mock data files
        geobase_dir = os.path.join(raw_dir, "geobase")
        os.makedirs(geobase_dir)
        mock_file_path = os.path.join(geobase_dir, "mock_road.geojson")
        with open(mock_file_path, "w", encoding="utf-8") as f:
            f.write('{"type": "FeatureCollection", "features": []}')

        # Create manifest
        metadata_dir = os.path.join(tmpdir, "data", "metadata")
        os.makedirs(metadata_dir)
        manifest_path = os.path.join(metadata_dir, "data_manifest.csv")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(
                "dataset_id,required_status,download_status,official_landing_url,selected_resource_name,original_filename,local_relative_path,resource_format,download_date_utc,source_last_modified,file_size_bytes,sha256,license,temporal_coverage_start,temporal_coverage_end,crs,row_count,geometry_type,audit_status,notes\n"
            )
            f.write(
                "montreal_geobase,required,not_downloaded,http://test.url,,,,,,,,,,,,,,not_started,Test Note\n"
            )
            f.write(
                "mechanized_pothole_repairs,required,not_downloaded,http://test.url,,,,,,,,,,,,,,not_started,Test Note\n"
            )

        yield {
            "tmpdir": tmpdir,
            "raw_dir": raw_dir,
            "manifest_path": manifest_path,
            "mock_file_path": mock_file_path,
        }


def test_calculate_sha256(temp_workspace):
    """Test SHA-256 calculation for a file."""
    filepath = temp_workspace["mock_file_path"]
    expected_hash = "7d09e532fc380630caac6b4b1b5174a7a9f7a308f6544bcb79eefb97b1e12306"
    assert calculate_sha256(filepath) == expected_hash


def test_load_manifest(temp_workspace):
    """Test loading expected datasets from the manifest CSV."""
    datasets = load_manifest(temp_workspace["manifest_path"])
    assert len(datasets) == 2
    assert "montreal_geobase" in datasets
    assert datasets["montreal_geobase"]["required_status"] == "required"


def test_scan_raw_directories(temp_workspace):
    """Test inventory scanner scans directory and captures file metadata."""
    raw_dir = temp_workspace["raw_dir"]
    inventory = scan_raw_directories(raw_dir)
    assert len(inventory) == 1
    assert inventory[0]["original_filename"] == "mock_road.geojson"
    assert inventory[0]["file_size_bytes"] > 0
    assert inventory[0]["extension"] == ".geojson"


def test_generate_report_allow_missing(temp_workspace):
    """Test that missing required files are flagged but exit code is 0 when --allow-missing is true."""
    datasets = {
        "montreal_geobase": {"required_status": "required", "download_status": "not_downloaded"},
        "mechanized_pothole_repairs": {
            "required_status": "required",
            "download_status": "not_downloaded",
        },
    }

    # Empty inventory (no files downloaded)
    inventory = []

    # With allow_missing = True, exit code must be 0
    exit_code_allow = generate_report(datasets, inventory, allow_missing=True)
    assert exit_code_allow == 0

    # With allow_missing = False, exit code must be 1
    exit_code_fail = generate_report(datasets, inventory, allow_missing=False)
    assert exit_code_fail == 1
