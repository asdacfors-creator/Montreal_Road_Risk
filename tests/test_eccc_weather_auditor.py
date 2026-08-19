import os
import json
import tempfile
import pytest
from unittest import mock

from scripts.audit_eccc_weather import (
    calculate_sha256,
    load_csv_data,
    check_file_encoding,
    parse_float,
    get_field_val,
    is_leap_year,
    get_expected_days,
    analyze_station_files,
    _audit_dates,
    _audit_field_inventory,
    _audit_temperatures,
    _audit_freeze_thaw,
    _audit_precipitation,
    audit_station_data,
    _pearson_corr,
    compare_stations,
    main,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_is_leap_year():
    assert is_leap_year(2008) is True
    assert is_leap_year(2009) is False
    assert is_leap_year(2000) is True
    assert is_leap_year(1900) is False


def test_get_expected_days():
    assert get_expected_days(2008) == 366
    assert get_expected_days(2009) == 365


def test_parse_float():
    assert parse_float("12.5") == 12.5
    assert parse_float("-5") == -5.0
    assert parse_float("") is None
    assert parse_float("abc") is None


def test_get_field_val():
    headers = ["Date/Time", "Max Temp (°C)", "Min Temp Flag"]
    row = ["2009-01-01", "15.2", "E"]
    assert get_field_val(row, headers, "Date/Time") == "2009-01-01"
    assert get_field_val(row, headers, "max temp flag") is None
    assert get_field_val(row, headers, "Max Temp (°C)") == "15.2"
    assert get_field_val(row, headers, "Min Temp Flag") == "E"


def test_load_csv_data_with_bom(temp_dir):
    csv_path = os.path.join(temp_dir, "bom.csv")
    content = '\ufeff"Col1","Col2"\n"val1","val2"'
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(content)

    headers, rows = load_csv_data(csv_path)
    assert headers == ["Col1", "Col2"]
    assert rows == [["val1", "val2"]]


def test_check_file_encoding(temp_dir):
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Some UTF-8 text")
    assert check_file_encoding(file_path) == "UTF-8"


def test_audit_dates():
    # Simple valid data
    data = [
        {"date": "2009-01-01", "year": 2009},
        {"date": "2009-01-02", "year": 2009},
    ]
    report = _audit_dates(data)
    assert report["start_date"] == "2009-01-01"
    assert report["end_date"] == "2009-01-02"
    assert report["total_parsed"] == 2
    assert report["unique_dates"] == 2
    assert report["duplicate_dates"] == 0
    assert report["out_of_year_dates"] == 0

    # Test out of year and duplicate dates
    bad_data = [
        {"date": "2009-01-01", "year": 2009},
        {"date": "2009-01-01", "year": 2009},
        {"date": "2010-01-01", "year": 2009},
    ]
    report_bad = _audit_dates(bad_data)
    assert report_bad["duplicate_dates"] == 1
    assert report_bad["out_of_year_dates"] == 1


def test_audit_field_inventory():
    data = [
        {
            "max_temp": 10.0,
            "max_temp_flag": "",
            "min_temp": None,
            "min_temp_flag": "M",
            "mean_temp": 5.0,
            "mean_temp_flag": "",
            "total_precip": 0.0,
            "total_precip_flag": "T",
            "total_rain": None,
            "total_rain_flag": "",
            "total_snow": None,
            "total_snow_flag": "",
            "snow_on_ground": 2.0,
            "snow_on_ground_flag": "",
        }
    ]
    inv = _audit_field_inventory(data)
    assert inv["max_temp"]["missing"] == 0
    assert inv["min_temp"]["missing"] == 1
    assert inv["min_temp"]["unique_flags"] == ["M"]
    assert inv["total_precip"]["trace_flags"] == 1


def test_audit_temperatures():
    data = [
        {"max_temp": 10.0, "min_temp": 2.0, "mean_temp": 6.0},
        {"max_temp": 12.0, "min_temp": 4.0, "mean_temp": 8.0},
    ]
    report = _audit_temperatures(data)
    assert report["metrics"]["max_temp"]["max"] == 12.0
    assert report["metrics"]["min_temp"]["min"] == 2.0
    assert report["max_lower_than_min_anomalies"] == 0
    assert report["mean_outside_bounds_anomalies"] == 0

    # Anomalous data
    bad_data = [{"max_temp": 5.0, "min_temp": 10.0, "mean_temp": 15.0}]
    report_bad = _audit_temperatures(bad_data)
    assert report_bad["max_lower_than_min_anomalies"] == 1
    assert report_bad["mean_outside_bounds_anomalies"] == 1


def test_audit_freeze_thaw():
    data = [
        {"year": 2009, "min_temp": -5.0, "max_temp": 5.0},  # Def 1, 2, 3
        {"year": 2009, "min_temp": 0.0, "max_temp": 5.0},  # Def 2 only
        {"year": 2009, "min_temp": -5.0, "max_temp": 0.0},  # Def 3 only
        {"year": 2009, "min_temp": None, "max_temp": 5.0},  # Missing temp
    ]
    report = _audit_freeze_thaw(data)
    assert report[2009]["missing_temp_days"] == 1
    assert report[2009]["def1_strict"] == 1
    assert report[2009]["def2_le_zero"] == 2
    assert report[2009]["def3_ge_zero"] == 2


def test_audit_precipitation():
    data = [
        {
            "total_rain": None,
            "total_rain_flag": "M",
            "total_snow": None,
            "total_snow_flag": "M",
            "total_precip": 5.2,
            "total_precip_flag": "",
            "snow_on_ground": -2.0,
            "snow_on_ground_flag": "",
        },
    ]
    report = _audit_precipitation(data)
    assert report["total_rain"]["non_zero_count"] == 0
    assert report["total_snow"]["max"] is None
    assert report["total_precip"]["max"] == 5.2
    assert report["snow_on_ground"]["negative_anomalies"] == 1


def test_pearson_corr():
    assert _pearson_corr([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert _pearson_corr([1, 2, 3], [6, 4, 2]) == pytest.approx(-1.0)
    assert _pearson_corr([1, 2], [1, 2]) == pytest.approx(1.0)
    assert _pearson_corr([1], [1]) == 0.0


def test_compare_stations():
    m_data = [
        {"date": "2009-01-01", "mean_temp": 5.0, "total_precip": 0.0},
        {"date": "2009-01-02", "mean_temp": None, "total_precip": 5.0},
    ]
    t_data = [
        {"date": "2009-01-01", "mean_temp": 6.0, "total_precip": 0.0},
        {"date": "2009-01-02", "mean_temp": 4.0, "total_precip": None},
    ]
    comp = compare_stations(m_data, t_data)
    assert comp["overlapping_dates_count"] == 2
    assert comp["mean_temp_difference"] == -1.0
    assert comp["missing_temp_mctavish_only"] == 1
    assert comp["missing_temp_trudeau_only"] == 0


def test_main_cli_success(temp_dir):
    # Setup dummy paths and data
    inv_path = os.path.join(temp_dir, "Inventory.csv")
    with open(inv_path, "w", encoding="utf-8") as f:
        f.write("Modified Date: 2026-07-08\nHeader,Test\n")

    mctavish_dir = os.path.join(temp_dir, "mctavish")
    os.makedirs(mctavish_dir)
    with open(
        os.path.join(mctavish_dir, "en_climate_daily_QC_7024745_2009_P1D.csv"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write('Header\n"val"')

    trudeau_dir = os.path.join(temp_dir, "trudeau")
    os.makedirs(trudeau_dir)
    with open(
        os.path.join(trudeau_dir, "en_climate_daily_QC_702S006_2009_P1D.csv"), "w", encoding="utf-8"
    ) as f:
        f.write('Header\n"val"')

    output_json = os.path.join(temp_dir, "report.json")

    with mock.patch(
        "sys.argv",
        [
            "audit_eccc_weather.py",
            "--inventory",
            inv_path,
            "--mctavish-dir",
            mctavish_dir,
            "--trudeau-dir",
            trudeau_dir,
            "--output-json",
            output_json,
        ],
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        assert os.path.exists(output_json)


def test_main_cli_failure_missing_args():
    with mock.patch("sys.argv", ["audit_eccc_weather.py", "--inventory", "nonexistent.csv"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
