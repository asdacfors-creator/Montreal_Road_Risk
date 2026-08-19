#!/usr/bin/env python3
"""Audit ECCC weather data.

Reads all annual daily weather files for McTavish and Montreal-Trudeau,
computes completeness, temperature, precipitation, freeze-thaw metrics,
and performs cross-station comparison.
"""

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime


def calculate_sha256(filepath):
    """Calculate SHA-256 of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv_data(filepath):
    """Load and parse weather CSV file returning headers and rows."""
    with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration as e:
            raise ValueError(f"Empty file: {filepath}") from e
        headers = [h.strip().replace('"', "") for h in headers]
        rows = []
        for r in reader:
            if not r:
                continue
            rows.append([val.strip() for val in r])
    return headers, rows


def check_file_encoding(filepath):
    """Verify if file is compatible with UTF-8."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            f.read(4096)
        return "UTF-8"
    except UnicodeDecodeError:
        return "Unknown"


def parse_float(val):
    """Parse string to float, returning None if empty or invalid."""
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def get_field_val(row, headers, col_name):
    """Get field value by column name, returning None if column not found."""
    norm_col = col_name.lower().replace(" ", "").replace("°", "").replace("(", "").replace(")", "")
    for idx, h in enumerate(headers):
        norm_h = h.lower().replace(" ", "").replace("°", "").replace("(", "").replace(")", "")
        if norm_col == norm_h:
            return row[idx] if idx < len(row) else ""
    return None


def is_leap_year(year):
    """Check if a year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def get_expected_days(year):
    """Get expected calendar days in a year."""
    return 366 if is_leap_year(year) else 365


def analyze_station_files(files, expected_station_id, expected_climate_id):
    """Audit annual files for a specific station."""
    file_audits = {}
    all_data = []

    for fpath in sorted(files):
        filename = os.path.basename(fpath)
        size = os.path.getsize(fpath)
        sha256 = calculate_sha256(fpath)
        encoding = check_file_encoding(fpath)

        try:
            headers, rows = load_csv_data(fpath)
            parse_success = True
            err_msg = ""
        except Exception as e:
            headers, rows = [], []
            parse_success = False
            err_msg = str(e)

        year_match = re.search(r"_(\d{4})_", filename)
        req_year = int(year_match.group(1)) if year_match else None

        malformed_rows = 0
        expected_width = len(headers)
        for r in rows:
            if len(r) != expected_width:
                malformed_rows += 1

        seen_rows = set()
        duplicate_rows = 0
        for r in rows:
            r_tuple = tuple(r)
            if r_tuple in seen_rows:
                duplicate_rows += 1
            seen_rows.add(r_tuple)

        station_name = ""
        climate_id = ""
        latitude = None
        longitude = None
        if rows:
            station_name = get_field_val(rows[0], headers, "Station Name")
            climate_id = get_field_val(rows[0], headers, "Climate ID")
            latitude = parse_float(get_field_val(rows[0], headers, "Latitude (y)"))
            longitude = parse_float(get_field_val(rows[0], headers, "Longitude (x)"))

        for r in rows:
            date_str = get_field_val(r, headers, "Date/Time")
            all_data.append(
                {
                    "date": date_str,
                    "year": req_year,
                    "max_temp": parse_float(get_field_val(r, headers, "Max Temp (°C)")),
                    "max_temp_flag": get_field_val(r, headers, "Max Temp Flag"),
                    "min_temp": parse_float(get_field_val(r, headers, "Min Temp (°C)")),
                    "min_temp_flag": get_field_val(r, headers, "Min Temp Flag"),
                    "mean_temp": parse_float(get_field_val(r, headers, "Mean Temp (°C)")),
                    "mean_temp_flag": get_field_val(r, headers, "Mean Temp Flag"),
                    "total_precip": parse_float(get_field_val(r, headers, "Total Precip (mm)")),
                    "total_precip_flag": get_field_val(r, headers, "Total Precip Flag"),
                    "total_rain": parse_float(get_field_val(r, headers, "Total Rain (mm)")),
                    "total_rain_flag": get_field_val(r, headers, "Total Rain Flag"),
                    "total_snow": parse_float(get_field_val(r, headers, "Total Snow (cm)")),
                    "total_snow_flag": get_field_val(r, headers, "Total Snow Flag"),
                    "snow_on_ground": parse_float(get_field_val(r, headers, "Snow on Grnd (cm)")),
                    "snow_on_ground_flag": get_field_val(r, headers, "Snow on Grnd Flag"),
                }
            )

        file_audits[filename] = {
            "size": size,
            "sha256": sha256,
            "encoding": encoding,
            "parse_success": parse_success,
            "error_message": err_msg,
            "headers": headers,
            "physical_row_count": len(rows) + 1 if parse_success else 0,
            "data_row_count": len(rows),
            "malformed_rows": malformed_rows,
            "duplicate_rows": duplicate_rows,
            "station_name": station_name,
            "climate_id": climate_id,
            "latitude": latitude,
            "longitude": longitude,
            "year": req_year,
        }

    return file_audits, all_data


def _audit_dates(all_data):
    """Audit date correctness and coverage."""
    parsed_dates = []
    out_of_year_dates = 0
    duplicate_dates = 0
    seen_dates = set()
    non_monotonic = 0
    prev_date = None

    for item in all_data:
        d_str = item["date"]
        try:
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            parsed_dates.append(dt)
            if dt.year != item["year"]:
                out_of_year_dates += 1
            if d_str in seen_dates:
                duplicate_dates += 1
            seen_dates.add(d_str)

            if prev_date and dt < prev_date:
                non_monotonic += 1
            prev_date = dt
        except Exception:
            pass

    start_date = min(parsed_dates).strftime("%Y-%m-%d") if parsed_dates else None
    end_date = max(parsed_dates).strftime("%Y-%m-%d") if parsed_dates else None

    missing_dates = 0
    if parsed_dates:
        all_expected = set()
        years = {item["year"] for item in all_data if item["year"] is not None}
        for y in sorted(years):
            expected_days = get_expected_days(y)
            start_y = datetime(y, 1, 1)
            for d in range(expected_days):
                curr = (
                    start_y.replace(day=d + 1)
                    if d < 28
                    else datetime.fromordinal(start_y.toordinal() + d)
                )
                all_expected.add(curr.strftime("%Y-%m-%d"))
        missing_dates = len(all_expected - seen_dates)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_parsed": len(parsed_dates),
        "unique_dates": len(seen_dates),
        "missing_dates": missing_dates,
        "duplicate_dates": duplicate_dates,
        "out_of_year_dates": out_of_year_dates,
        "non_monotonic": non_monotonic,
    }


def _audit_field_inventory(all_data):
    """Audit fields completeness and quality flags."""
    fields = [
        "max_temp",
        "min_temp",
        "mean_temp",
        "total_precip",
        "total_rain",
        "total_snow",
        "snow_on_ground",
    ]
    inventory = {}
    for f in fields:
        non_missing = sum(1 for item in all_data if item[f] is not None)
        missing = len(all_data) - non_missing
        pct = (missing / len(all_data) * 100) if all_data else 0.0

        flag_col = f + "_flag"
        flags = [item[flag_col] for item in all_data if item[flag_col]]
        unique_flags = sorted(set(flags))
        trace_count = sum(1 for fl in flags if fl == "T")
        est_count = sum(1 for fl in flags if fl == "E")

        inventory[f] = {
            "non_missing": non_missing,
            "missing": missing,
            "missing_pct": round(pct, 4),
            "unique_flags": unique_flags,
            "trace_flags": trace_count,
            "estimated_flags": est_count,
        }
    return inventory


def _audit_temperatures(all_data):
    """Audit temperatures distribution and anomalies."""
    temps = {}
    for f in ["max_temp", "min_temp", "mean_temp"]:
        vals = [item[f] for item in all_data if item[f] is not None]
        if vals:
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            temps[f] = {
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "mean": round(sum(sorted_vals) / n, 2),
                "median": sorted_vals[n // 2],
                "q25": sorted_vals[int(n * 0.25)],
                "q75": sorted_vals[int(n * 0.75)],
            }
        else:
            temps[f] = None

    max_lower_than_min = 0
    mean_outside_bounds = 0
    for item in all_data:
        mx, mn, me = item["max_temp"], item["min_temp"], item["mean_temp"]
        if mx is not None and mn is not None and mx < mn:
            max_lower_than_min += 1
        if mx is not None and mn is not None and me is not None:
            if not (mn <= me <= mx):
                mean_outside_bounds += 1

    return {
        "metrics": temps,
        "max_lower_than_min_anomalies": max_lower_than_min,
        "mean_outside_bounds_anomalies": mean_outside_bounds,
    }


def _audit_freeze_thaw(all_data):
    """Audit freeze-thaw counts based on candidate definitions."""
    freeze_thaw = {}
    years = {item["year"] for item in all_data if item["year"] is not None}
    for y in sorted(years):
        y_data = [item for item in all_data if item["year"] == y]
        missing_temp_days = sum(
            1 for item in y_data if item["min_temp"] is None or item["max_temp"] is None
        )

        def1 = sum(
            1
            for item in y_data
            if item["min_temp"] is not None
            and item["max_temp"] is not None
            and item["min_temp"] < 0
            and item["max_temp"] > 0
        )
        def2 = sum(
            1
            for item in y_data
            if item["min_temp"] is not None
            and item["max_temp"] is not None
            and item["min_temp"] <= 0
            and item["max_temp"] > 0
        )
        def3 = sum(
            1
            for item in y_data
            if item["min_temp"] is not None
            and item["max_temp"] is not None
            and item["min_temp"] < 0
            and item["max_temp"] >= 0
        )

        freeze_thaw[y] = {
            "missing_temp_days": missing_temp_days,
            "def1_strict": def1,
            "def2_le_zero": def2,
            "def3_ge_zero": def3,
        }
    return freeze_thaw


def _audit_precipitation(all_data):
    """Audit precipitation fields completeness and distribution."""
    precip = {}
    for f in ["total_rain", "total_snow", "total_precip", "snow_on_ground"]:
        vals = [item[f] for item in all_data if item[f] is not None]
        non_missing = len(vals)
        zero_counts = sum(1 for v in vals if v == 0.0)
        non_zero_counts = non_missing - zero_counts

        flag_col = f + "_flag"
        trace_flags = sum(1 for item in all_data if item[flag_col] == "T")
        negative_anomalies = sum(1 for v in vals if v < 0.0)

        if vals:
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            stats = {
                "max": sorted_vals[-1],
                "q25": sorted_vals[int(n * 0.25)],
                "q50_median": sorted_vals[n // 2],
                "q75": sorted_vals[int(n * 0.75)],
                "zero_count": zero_counts,
                "non_zero_count": non_zero_counts,
                "trace_flags": trace_flags,
                "negative_anomalies": negative_anomalies,
            }
        else:
            stats = {
                "max": None,
                "q25": None,
                "q50_median": None,
                "q75": None,
                "zero_count": zero_counts,
                "non_zero_count": non_zero_counts,
                "trace_flags": trace_flags,
                "negative_anomalies": negative_anomalies,
            }
        precip[f] = stats
    return precip


def audit_station_data(station_name, all_data):
    """Execute quality, temperature, precipitation, and date audits on station data."""
    return {
        "date_audit": _audit_dates(all_data),
        "field_inventory": _audit_field_inventory(all_data),
        "temperature_audit": _audit_temperatures(all_data),
        "freeze_thaw_audit": _audit_freeze_thaw(all_data),
        "precipitation_audit": _audit_precipitation(all_data),
    }


def _pearson_corr(x, y):
    """Compute Pearson correlation coefficient between two lists."""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    den_y = sum((y[i] - mean_y) ** 2 for i in range(n))
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / ((den_x * den_y) ** 0.5)


def compare_stations(mctavish_data, trudeau_data):
    """Perform cross-station correlation and missingness overlap analysis."""
    m_dict = {item["date"]: item for item in mctavish_data if item["date"]}
    t_dict = {item["date"]: item for item in trudeau_data if item["date"]}

    common_dates = sorted(set(m_dict.keys()) & set(t_dict.keys()))

    temp_diffs = []
    m_temp_vals, t_temp_vals = [], []
    m_precip_vals, t_precip_vals = [], []

    missing_temp_both = 0
    missing_precip_both = 0
    missing_temp_m_only = 0
    missing_temp_t_only = 0

    for d in common_dates:
        m_item = m_dict[d]
        t_item = t_dict[d]

        m_mean = m_item["mean_temp"]
        t_mean = t_item["mean_temp"]
        if m_mean is not None and t_mean is not None:
            temp_diffs.append(m_mean - t_mean)
            m_temp_vals.append(m_mean)
            t_temp_vals.append(t_mean)

        if m_mean is None and t_mean is None:
            missing_temp_both += 1
        elif m_mean is None:
            missing_temp_m_only += 1
        elif t_mean is None:
            missing_temp_t_only += 1

        m_prec = m_item["total_precip"]
        t_prec = t_item["total_precip"]
        if m_prec is not None and t_prec is not None:
            m_precip_vals.append(m_prec)
            t_precip_vals.append(t_prec)

        if m_prec is None and t_prec is None:
            missing_precip_both += 1

    temp_corr = _pearson_corr(m_temp_vals, t_temp_vals)
    precip_corr = _pearson_corr(m_precip_vals, t_precip_vals)

    return {
        "overlapping_dates_count": len(common_dates),
        "mean_temp_difference": round(sum(temp_diffs) / len(temp_diffs), 3) if temp_diffs else 0.0,
        "median_temp_difference": sorted(temp_diffs)[len(temp_diffs) // 2] if temp_diffs else 0.0,
        "temp_correlation": round(temp_corr, 4),
        "precip_correlation": round(precip_corr, 4),
        "missing_temp_both_stations": missing_temp_both,
        "missing_precip_both_stations": missing_precip_both,
        "missing_temp_mctavish_only": missing_temp_m_only,
        "missing_temp_trudeau_only": missing_temp_t_only,
    }


def main():  # noqa: C901
    """Main entry point for weather auditing script."""
    parser = argparse.ArgumentParser(description="Audit downloaded ECCC weather data.")
    parser.add_argument(
        "--inventory",
        default="data/raw/eccc_weather/station_inventory/Station Inventory EN.csv",
        help="Path to station inventory CSV.",
    )
    parser.add_argument(
        "--mctavish-dir",
        default="data/raw/eccc_weather/mctavish",
        help="Directory containing McTavish files.",
    )
    parser.add_argument(
        "--trudeau-dir",
        default="data/raw/eccc_weather/montreal_trudeau",
        help="Directory containing Trudeau files.",
    )
    parser.add_argument(
        "--output-json",
        default="outputs/reports/eccc_weather_audit_results.json",
        help="Path to write JSON results.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.inventory):
        print(f"Error: Inventory file not found at {args.inventory}")
        sys.exit(1)

    mctavish_files = glob.glob(os.path.join(args.mctavish_dir, "en_climate_daily_QC_*.csv"))
    trudeau_files = glob.glob(os.path.join(args.trudeau_dir, "en_climate_daily_QC_*.csv"))

    if not mctavish_files or not trudeau_files:
        print("Error: Missing daily weather files. Please run downloader first.")
        sys.exit(1)

    print("=== WEATHER FILE INTEGRITY AUDIT ===")
    m_file_audits, m_data = analyze_station_files(mctavish_files, 10761, "7024745")
    t_file_audits, t_data = analyze_station_files(trudeau_files, 30165, "702S006")

    print(f"Loaded {len(m_data)} McTavish rows from {len(mctavish_files)} files.")
    print(f"Loaded {len(t_data)} Trudeau rows from {len(trudeau_files)} files.")

    m_report = audit_station_data("MCTAVISH", m_data)
    t_report = audit_station_data("MONTREAL_TRUDEAU", t_data)
    cross_report = compare_stations(m_data, t_data)

    results = {
        "mctavish_files": m_file_audits,
        "trudeau_files": t_file_audits,
        "mctavish_metrics": m_report,
        "trudeau_metrics": t_report,
        "cross_station_comparison": cross_report,
    }

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Audit completed successfully. Results written to {args.output_json}")

    print("\n--- Summary completeness ---")
    print(f"McTavish Mean Temp Missing: {m_report['field_inventory']['mean_temp']['missing']}")
    print(f"Trudeau Mean Temp Missing: {t_report['field_inventory']['mean_temp']['missing']}")
    print(f"Missing Temp Both Stations: {cross_report['missing_temp_both_stations']}")
    print(f"Temp Correlation: {cross_report['temp_correlation']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
