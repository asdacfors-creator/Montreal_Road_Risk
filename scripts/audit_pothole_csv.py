#!/usr/bin/env python
"""Audit utility for pothole repair CSV resources.

Calculates file integrity, structure, temporal bounds, device distributions,
coordinates quality, and duplicate patterns. Supports both 12-hour AM/PM
and 24-hour time formats, and alphanumeric device patterns.
"""

import argparse
import csv
import datetime
import hashlib
import os
import sys

import pandas as pd


def check_file_properties(filepath):
    """Detect encoding, delimiter, and line endings."""
    file_size = os.path.getsize(filepath)

    # Read first 10KB to analyze properties
    with open(filepath, "rb") as f:
        content_bytes = f.read(10240)

    # Check encoding (UTF-8 or Latin-1)
    try:
        content_bytes.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        encoding = "latin-1"

    content_str = content_bytes.decode(encoding, errors="ignore")

    # Detect line ending
    if "\r\n" in content_str:
        line_ending = "CRLF (Windows)"
    elif "\n" in content_str:
        line_ending = "LF (Unix)"
    else:
        line_ending = "CR (Mac)"

    # Detect delimiter
    delimiters = [",", ";", "\t"]
    delim_counts = {d: content_str.count(d) for d in delimiters}
    delimiter = max(delim_counts, key=delim_counts.get)
    if delim_counts[delimiter] == 0:
        delimiter = ","

    return file_size, encoding, delimiter, line_ending


def calculate_sha256(filepath):
    """Calculate SHA-256 hash of the file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _count_decimal_digits(val_str):
    """Count number of decimal digits in a coordinate string."""
    val_str = val_str.strip()
    if "." in val_str:
        return len(val_str.split(".")[1])
    return 0


def _classify_device_id(appareil_str):
    """Classify Appareil identifier into pattern categories."""
    appareil_clean = appareil_str.strip()
    if not appareil_clean:
        return "blank"
    if appareil_clean.isdigit():
        return "numeric_only"
    if appareil_clean.startswith("NP-") and appareil_clean[3:].isdigit():
        return "np_hyphen_number"
    return "other_non_empty"


def _parse_row_values(date_str, time_str, lat_str, lon_str):
    """Parse date, time, and coordinates from raw row values."""
    date_ok = True
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        date_ok = False

    time_fmt_detected = None
    for fmt in ["%I:%M:%S %p", "%H:%M:%S"]:
        try:
            datetime.datetime.strptime(time_str, fmt)
            time_fmt_detected = fmt
            break
        except ValueError:
            continue

    coords_ok = True
    try:
        float(lat_str)
        float(lon_str)
    except ValueError:
        coords_ok = False

    return date_ok, time_fmt_detected, coords_ok


def audit_raw_csv(filepath, delimiter):
    """Perform a raw structural and parsing pass using python's csv.reader.

    Validates header, row widths, missing values, date formats, time formats,
    and coordinate float values. Returns a dict of counts and a boolean pass flag.
    """
    header = None
    data_rows = 0
    malformed_rows = 0
    blank_rows = 0
    missing_value_errors = 0
    date_parse_errors = 0
    time_parse_errors = 0
    coordinate_parse_errors = 0

    time_format_counts = {
        "%I:%M:%S %p": 0,  # 12-hour AM/PM
        "%H:%M:%S": 0,  # 24-hour
    }

    device_pattern_counts = {
        "numeric_only": 0,
        "np_hyphen_number": 0,
        "other_non_empty": 0,
        "blank": 0,
    }

    lat_precision_counts = {}
    lon_precision_counts = {}

    expected_header = ["Appareil", "DateJour", "DateHeure", "Latitude", "Longitude"]

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return None, False, {}

        if header != expected_header:
            print(
                f"Error: Header mismatch. Expected {expected_header}, got {header}", file=sys.stderr
            )
            return header, False, {}

        expected_cols = len(header)

        for _row_idx, row in enumerate(reader, start=2):
            if not row:
                blank_rows += 1
                continue

            if len(row) != expected_cols:
                malformed_rows += 1
                continue

            data_rows += 1

            appareil_str = row[0]
            dev_pat = _classify_device_id(appareil_str)
            device_pattern_counts[dev_pat] += 1

            # Check missing or blank values
            has_missing = any(not val or val.strip() == "" for val in row)

            if has_missing:
                missing_value_errors += 1
                continue

            _, date_str, time_str, lat_str, lon_str = row

            date_ok, time_fmt, coords_ok = _parse_row_values(date_str, time_str, lat_str, lon_str)

            if not date_ok:
                date_parse_errors += 1
            if time_fmt:
                time_format_counts[time_fmt] += 1
            else:
                time_parse_errors += 1

            if not coords_ok:
                coordinate_parse_errors += 1
            else:
                # Calculate decimal precision from raw string
                lat_digits = _count_decimal_digits(lat_str)
                lon_digits = _count_decimal_digits(lon_str)
                lat_precision_counts[lat_digits] = lat_precision_counts.get(lat_digits, 0) + 1
                lon_precision_counts[lon_digits] = lon_precision_counts.get(lon_digits, 0) + 1

    passed = (
        malformed_rows == 0
        and missing_value_errors == 0
        and date_parse_errors == 0
        and time_parse_errors == 0
        and coordinate_parse_errors == 0
    )

    stats = {
        "header": header,
        "data_rows": data_rows,
        "malformed_rows": malformed_rows,
        "blank_rows": blank_rows,
        "missing_value_errors": missing_value_errors,
        "date_parse_errors": date_parse_errors,
        "time_parse_errors": time_parse_errors,
        "coordinate_parse_errors": coordinate_parse_errors,
        "time_format_counts": time_format_counts,
        "lat_precision_counts": lat_precision_counts,
        "lon_precision_counts": lon_precision_counts,
        "device_pattern_counts": device_pattern_counts,
    }

    return stats, passed


def analyze_duplicates(df):
    """Calculate duplicate patterns separately as requested."""
    patterns = {
        "exact_duplicates": ["Appareil", "DateJour", "DateHeure", "Latitude", "Longitude"],
        "same_datetime": ["DateJour", "DateHeure"],
        "same_coordinates": ["Latitude", "Longitude"],
        "same_datetime_coords": ["DateJour", "DateHeure", "Latitude", "Longitude"],
        "same_device_datetime": ["Appareil", "DateJour", "DateHeure"],
        "same_device_datetime_coords": [
            "Appareil",
            "DateJour",
            "DateHeure",
            "Latitude",
            "Longitude",
        ],
    }

    results = {}
    for name, cols in patterns.items():
        # Identify rows that are duplicates (including the first occurrence)
        dups = df.duplicated(subset=cols, keep=False)
        total_rows_in_groups = dups.sum()

        # Group by the specified columns
        groups = df[dups].groupby(cols)
        num_groups = len(groups)

        # Calculate excess rows beyond the first in each group
        excess_rows = df.duplicated(subset=cols, keep="first").sum()

        # Maximum group size
        max_group_size = groups.size().max() if num_groups > 0 else 0

        results[name] = {
            "groups": num_groups,
            "total_rows": total_rows_in_groups,
            "excess_rows": excess_rows,
            "max_group_size": max_group_size,
        }

    return results


def run_audit(filepath):
    """Run the complete content audit."""
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        return None

    file_size, encoding, delimiter, line_ending = check_file_properties(filepath)
    checksum = calculate_sha256(filepath)

    raw_stats, raw_passed = audit_raw_csv(filepath, delimiter)
    if raw_stats is None:
        return None

    # Load with pandas for attribute audits and duplicate checks
    df = pd.read_csv(filepath, delimiter=delimiter, on_bad_lines="skip")

    # Column missingness (based on pandas DataFrame)
    missingness = {}
    for col in df.columns:
        null_count = df[col].isnull().sum()
        blank_count = 0
        if df[col].dtype == object:
            blank_count = (df[col].astype(str).str.strip() == "").sum()
        missingness[col] = {
            "null": int(null_count),
            "blank": int(blank_count),
            "total": int(null_count + blank_count),
        }

    # Temporal Audit using pandas parsed columns (coerced)
    df["parsed_date"] = pd.to_datetime(df["DateJour"], format="%Y-%m-%d", errors="coerce")

    # Parse time trying both formats
    t1 = pd.to_datetime(df["DateHeure"], format="%I:%M:%S %p", errors="coerce")
    t2 = pd.to_datetime(df["DateHeure"], format="%H:%M:%S", errors="coerce")
    df["parsed_time"] = t1.fillna(t2)

    min_date = df["parsed_date"].min()
    max_date = df["parsed_date"].max()

    min_time = df["parsed_time"].dt.time.min()
    max_time = df["parsed_time"].dt.time.max()

    # Combine datetime
    df["combined_dt"] = pd.to_datetime(df["DateJour"] + " " + df["DateHeure"], errors="coerce")
    min_combined = df["combined_dt"].min()
    max_combined = df["combined_dt"].max()

    unique_dates = df["parsed_date"].dropna().dt.date.unique()
    num_unique_dates = len(unique_dates)

    counts_per_date = df["parsed_date"].dropna().dt.date.value_counts().sort_index()

    # Monthly counts
    counts_per_month = df["parsed_date"].dropna().dt.to_period("M").value_counts().sort_index()

    # Find missing dates within range
    missing_dates = []
    if num_unique_dates > 1:
        full_range = pd.date_range(start=min_date, end=max_date).date
        missing_dates = [str(d) for d in full_range if d not in unique_dates]

    # Device Audit
    unique_devices = df["Appareil"].dropna().nunique()
    device_freq = df["Appareil"].dropna().value_counts()
    device_nulls = df["Appareil"].isnull().sum()

    # Check for text or non-integer values
    non_int_devices = 0
    try:
        pd.to_numeric(df["Appareil"], errors="raise")
    except (ValueError, TypeError):
        non_int_devices = df["Appareil"].apply(lambda x: not str(x).isdigit()).sum()

    rare_devices = device_freq[device_freq == 1].index.tolist()

    # Coordinate Audit
    lat_numeric = pd.to_numeric(df["Latitude"], errors="coerce")
    lon_numeric = pd.to_numeric(df["Longitude"], errors="coerce")

    lat_parse_fails = lat_numeric.isnull().sum()
    lon_parse_fails = lon_numeric.isnull().sum()

    zero_coords = ((lat_numeric == 0) | (lon_numeric == 0)).sum()

    lat_min, lat_max = lat_numeric.min(), lat_numeric.max()
    lon_min, lon_max = lon_numeric.min(), lon_numeric.max()

    outside_world = (
        (lat_numeric < -90) | (lat_numeric > 90) | (lon_numeric < -180) | (lon_numeric > 180)
    ).sum()

    # Montreal sanity box: lat 45.0 to 46.0, lon -75.0 to -72.0
    outside_montreal = (
        (lat_numeric < 45.0) | (lat_numeric > 46.0) | (lon_numeric < -75.0) | (lon_numeric > -72.0)
    ).sum()

    unique_coords = df.groupby(["Latitude", "Longitude"]).ngroups

    # Duplicates Audit
    dup_results = analyze_duplicates(df)

    audit_results = {
        "file_integrity": {
            "size_bytes": file_size,
            "sha256": checksum,
            "encoding": encoding,
            "delimiter": delimiter,
            "line_ending": line_ending,
        },
        "raw_pass": raw_passed,
        "structure": {
            "header": raw_stats["header"],
            "data_rows": raw_stats["data_rows"],
            "malformed_rows": raw_stats["malformed_rows"],
            "blank_rows": raw_stats["blank_rows"],
            "missing_value_errors": raw_stats["missing_value_errors"],
            "date_parse_errors": raw_stats["date_parse_errors"],
            "time_parse_errors": raw_stats["time_parse_errors"],
            "coordinate_parse_errors": raw_stats["coordinate_parse_errors"],
            "time_format_counts": raw_stats["time_format_counts"],
            "missingness": missingness,
        },
        "temporal": {
            "min_date": str(min_date.date()) if pd.notnull(min_date) else None,
            "max_date": str(max_date.date()) if pd.notnull(max_date) else None,
            "min_time": str(min_time) if min_time else None,
            "max_time": str(max_time) if max_time else None,
            "min_combined": str(min_combined) if pd.notnull(min_combined) else None,
            "max_combined": str(max_combined) if pd.notnull(max_combined) else None,
            "unique_dates_count": num_unique_dates,
            "counts_per_date": counts_per_date.to_dict(),
            "counts_per_month": {str(k): int(v) for k, v in counts_per_month.items()},
            "missing_dates": missing_dates,
        },
        "device": {
            "unique_count": int(unique_devices),
            "null_count": int(device_nulls),
            "non_integer_count": int(non_int_devices),
            "frequencies": {str(k): int(v) for k, v in device_freq.items()},
            "rare_identifiers": [str(x) for x in rare_devices],
            "pattern_counts": raw_stats["device_pattern_counts"],
        },
        "coordinate": {
            "lat_parse_fails": int(lat_parse_fails),
            "lon_parse_fails": int(lon_parse_fails),
            "zero_coords": int(zero_coords),
            "lat_min": float(lat_min) if pd.notnull(lat_min) else None,
            "lat_max": float(lat_max) if pd.notnull(lat_max) else None,
            "lon_min": float(lon_min) if pd.notnull(lon_min) else None,
            "lon_max": float(lon_max) if pd.notnull(lon_max) else None,
            "outside_world": int(outside_world),
            "outside_montreal": int(outside_montreal),
            "unique_pairs_count": int(unique_coords),
            "lat_precision_counts": raw_stats["lat_precision_counts"],
            "lon_precision_counts": raw_stats["lon_precision_counts"],
        },
        "duplicates": dup_results,
    }

    return audit_results


def print_audit_report(results):
    """Print clean report to console."""
    fi = results["file_integrity"]
    st = results["structure"]
    te = results["temporal"]
    de = results["device"]
    co = results["coordinate"]
    du = results["duplicates"]

    print("=== POTHOLE CSV AUDIT RESULTS ===")
    print(f"File Size: {fi['size_bytes']} bytes")
    print(f"SHA-256 Checksum: {fi['sha256']}")
    print(f"Encoding: {fi['encoding']}")
    print(f"Delimiter: '{fi['delimiter']}'")
    print(f"Line Endings: {fi['line_ending']}")
    print("")
    print(f"Header: {st['header']}")
    print(f"Data Rows: {st['data_rows']}")
    print(f"Malformed Rows: {st['malformed_rows']}")
    print(f"Blank Rows: {st['blank_rows']}")
    print(f"Missing Value Rows: {st['missing_value_errors']}")
    print(f"Date Parse Errors: {st['date_parse_errors']}")
    print(f"Time Parse Errors: {st['time_parse_errors']}")
    print(f"Coordinate Parse Errors: {st['coordinate_parse_errors']}")
    print(f"Time Formats Parsed: {st['time_format_counts']}")
    print("")
    print("Temporal Bounds:")
    print(f"  DateJour Range: {te['min_date']} to {te['max_date']}")
    print(f"  DateHeure Time Range: {te['min_time']} to {te['max_time']}")
    print(f"  Combined Timestamp Range: {te['min_combined']} to {te['max_combined']}")
    print(f"  Unique Calendar Dates: {te['unique_dates_count']}")
    print(f"  Missing Dates in Range (Count): {len(te['missing_dates'])}")
    print(f"  Monthly Counts: {te['counts_per_month']}")
    print("")
    print("Device Distribution:")
    print(f"  Unique Devices: {de['unique_count']}")
    print(f"  Rare Devices: {de['rare_identifiers']}")
    print(f"  Device Pattern Counts: {de['pattern_counts']}")
    print("")
    print("Coordinate Quality:")
    print(f"  Latitude Range: {co['lat_min']} to {co['lat_max']}")
    print(f"  Longitude Range: {co['lon_min']} to {co['lon_max']}")
    print(f"  Outside Montreal Sanity Box: {co['outside_montreal']}")
    print(f"  Unique Coordinate Pairs: {co['unique_pairs_count']}")
    print(f"  Latitude Precision Distribution: {co['lat_precision_counts']}")
    print(f"  Longitude Precision Distribution: {co['lon_precision_counts']}")
    print(
        "  Note: Decimal-place precision describes how coordinate values are stored; it does not establish their real-world positional accuracy."
    )
    print("")
    print("Duplicate Patterns:")
    for name, metrics in du.items():
        print(
            f"  {name}: Groups={metrics['groups']}, Total Rows={metrics['total_rows']}, Excess Rows={metrics['excess_rows']}, Max Group Size={metrics['max_group_size']}"
        )


def main():  # noqa: C901
    """Main execution entry point."""
    parser = argparse.ArgumentParser(description="Audit a pothole repair CSV file.")
    parser.add_argument("csv_path", help="Path to the pothole repair CSV file.")
    args = parser.parse_args()

    results = run_audit(args.csv_path)
    if not results:
        return 1

    print_audit_report(results)

    # Return exit code based on structural pass failures
    if not results["raw_pass"]:
        print("\nStructural or parsing failures detected!", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
