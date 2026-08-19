"""Tests for scripts/audit_pothole_csv.py.

Tests 12-hour AM/PM format, 24-hour time format, mixed formats,
invalid times, malformed rows, non-zero CLI exit conditions,
raw string coordinate precision calculation, and device ID pattern classification.
"""

import os
import tempfile
import pytest

from scripts.audit_pothole_csv import audit_raw_csv, run_audit


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def write_test_csv(filepath, lines):
    """Helper to write CSV lines."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def test_2016_time_format(temp_dir):
    """Test 12-hour AM/PM format (2016)."""
    csv_path = os.path.join(temp_dir, "test_2016.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2016-12-07,11:16:39 AM,45.50000,-73.60000\n",
        "2,2016-12-07,11:22:46 PM,45.50000,-73.60000\n",
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    assert passed is True
    assert stats["time_format_counts"]["%I:%M:%S %p"] == 2
    assert stats["time_format_counts"]["%H:%M:%S"] == 0
    assert stats["time_parse_errors"] == 0


def test_2017_time_format(temp_dir):
    """Test 24-hour time format (2017)."""
    csv_path = os.path.join(temp_dir, "test_2017.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2017-01-11,16:32:47,45.41520,-73.93691\n",
        "2,2017-01-11,08:15:30,45.41520,-73.93691\n",
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    assert passed is True
    assert stats["time_format_counts"]["%I:%M:%S %p"] == 0
    assert stats["time_format_counts"]["%H:%M:%S"] == 2
    assert stats["time_parse_errors"] == 0


def test_mixed_supported_formats(temp_dir):
    """Test mixed time formats in the same file."""
    csv_path = os.path.join(temp_dir, "test_mixed.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2017-01-11,16:32:47,45.41520,-73.93691\n",
        "2,2016-12-07,11:16:39 AM,45.50000,-73.60000\n",
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    assert passed is True
    assert stats["time_format_counts"]["%I:%M:%S %p"] == 1
    assert stats["time_format_counts"]["%H:%M:%S"] == 1
    assert stats["time_parse_errors"] == 0


def test_invalid_time(temp_dir):
    """Test that invalid times fail raw validation."""
    csv_path = os.path.join(temp_dir, "test_invalid_time.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2017-01-11,25:32:47,45.41520,-73.93691\n",  # invalid hour
        "2,2017-01-11,11:61:30 AM,45.41520,-73.93691\n",  # invalid minute
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    assert passed is False
    assert stats["time_parse_errors"] == 2


def test_malformed_width_row(temp_dir):
    """Test that malformed rows with extra or missing fields fail validation."""
    csv_path = os.path.join(temp_dir, "test_malformed.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2017-01-11,16:32:47,45.41520,-73.93691,EXTRA_FIELD\n",  # extra column
        "2,2017-01-11,16:32:47,45.41520\n",  # missing column
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    assert passed is False
    assert stats["malformed_rows"] == 2


def test_nonzero_cli_exit_status_on_malformed_input(temp_dir):
    """Test that run_audit returns passed=False flags, triggering non-zero CLI status."""
    csv_path = os.path.join(temp_dir, "test_cli_fail.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2017-01-11,16:32:47,45.41520,INVALID_COORDINATE\n",  # non-numeric longitude
    ]
    write_test_csv(csv_path, lines)

    results = run_audit(csv_path)
    assert results is not None
    assert results["raw_pass"] is False
    assert results["structure"]["coordinate_parse_errors"] == 1


def test_coordinate_precision_calculation(temp_dir):
    """Test textual coordinate precision calculation logic.

    Checks different lengths, negative longitude values, and integer forms.
    Assures precision is calculated from the original string format.
    """
    csv_path = os.path.join(temp_dir, "test_coords_prec.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "1,2017-01-11,16:32:47,45.5,-73.123\n",  # lat=1 dig (45.5), lon=3 dig (-73.123)
        "2,2017-01-11,16:32:47,45.50000,-73.0\n",  # lat=5 dig (45.50000), lon=1 dig (-73.0)
        "3,2017-01-11,16:32:47,45,-73.12\n",  # lat=0 dig (45), lon=2 dig (-73.12)
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    assert passed is True

    assert stats["lat_precision_counts"][1] == 1
    assert stats["lat_precision_counts"][5] == 1
    assert stats["lat_precision_counts"][0] == 1

    assert stats["lon_precision_counts"][3] == 1
    assert stats["lon_precision_counts"][1] == 1
    assert stats["lon_precision_counts"][2] == 1


def test_device_pattern_classification(temp_dir):
    """Test classification of device pattern identifiers."""
    csv_path = os.path.join(temp_dir, "test_device_pat.csv")
    lines = [
        "Appareil,DateJour,DateHeure,Latitude,Longitude\n",
        "101,2017-01-11,16:32:47,45.5,-73.1\n",  # numeric_only
        "NP-108,2017-01-11,16:32:47,45.5,-73.1\n",  # np_hyphen_number
        "G7C020FD0,2017-01-11,16:32:47,45.5,-73.1\n",  # other_non_empty
        " ,2017-01-11,16:32:47,45.5,-73.1\n",  # blank (whitespace only)
    ]
    write_test_csv(csv_path, lines)

    stats, passed = audit_raw_csv(csv_path, delimiter=",")
    # Note: blank value triggers has_missing which fails audit_raw_csv but still populates stats!
    assert passed is False
    assert stats["device_pattern_counts"]["numeric_only"] == 1
    assert stats["device_pattern_counts"]["np_hyphen_number"] == 1
    assert stats["device_pattern_counts"]["other_non_empty"] == 1
    assert stats["device_pattern_counts"]["blank"] == 1
