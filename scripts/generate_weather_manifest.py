#!/usr/bin/env python3
"""Generate ECCC Weather Resource Manifest.

Reads the raw weather CSVs, computes size, SHA-256, row count, dates,
and missingness per year, and outputs data/metadata/eccc_weather_resource_manifest.csv.
"""

import csv
import hashlib
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "data", "metadata", "eccc_weather_resource_manifest.csv")
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "eccc_weather")


def calculate_sha256(filepath):
    """Calculate the SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_field_val(row, headers, col_name):
    """Get field value by column name, returning None if column not found."""
    norm_col = col_name.lower().replace(" ", "").replace("°", "").replace("(", "").replace(")", "")
    for idx, h in enumerate(headers):
        norm_h = h.lower().replace(" ", "").replace("°", "").replace("(", "").replace(")", "")
        if norm_col == norm_h:
            return row[idx] if idx < len(row) else ""
    return None


def parse_float(val):
    """Parse string to float, returning None if empty or invalid."""
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _aggregate_data_rows(data_rows, headers):
    """Aggregate dates and missingness counts across rows."""
    dates = []
    missing_max_temp = 0
    missing_min_temp = 0
    missing_mean_temp = 0
    missing_total_precip = 0
    missing_total_rain = 0
    missing_total_snow = 0
    missing_snow_on_ground = 0

    for r in data_rows:
        dt_str = get_field_val(r, headers, "Date/Time")
        if dt_str:
            dates.append(datetime.strptime(dt_str, "%Y-%m-%d"))

        mx = parse_float(get_field_val(r, headers, "Max Temp (°C)"))
        mn = parse_float(get_field_val(r, headers, "Min Temp (°C)"))
        me = parse_float(get_field_val(r, headers, "Mean Temp (°C)"))
        pr = parse_float(get_field_val(r, headers, "Total Precip (mm)"))
        rn = parse_float(get_field_val(r, headers, "Total Rain (mm)"))
        sn = parse_float(get_field_val(r, headers, "Total Snow (cm)"))
        sg = parse_float(get_field_val(r, headers, "Snow on Grnd (cm)"))

        if mx is None:
            missing_max_temp += 1
        if mn is None:
            missing_min_temp += 1
        if me is None:
            missing_mean_temp += 1
        if pr is None:
            missing_total_precip += 1
        if rn is None:
            missing_total_rain += 1
        if sn is None:
            missing_total_snow += 1
        if sg is None:
            missing_snow_on_ground += 1

    return (
        dates,
        missing_max_temp,
        missing_min_temp,
        missing_mean_temp,
        missing_total_precip,
        missing_total_rain,
        missing_total_snow,
        missing_snow_on_ground,
    )


def _process_annual_file(fpath, filename, year, station_role, station_name, station_id, climate_id):
    """Extract metadata and metrics from a single annual ECCC daily file."""
    size = os.path.getsize(fpath)
    sha256 = calculate_sha256(fpath)
    url = f"https://climate.weather.gc.ca/climate_data/bulk_data_e.html?format=csv&stationID={station_id}&Year={year}&Month=1&Day=14&timeframe=2&submit=Download+Data"
    rel_path = os.path.relpath(fpath, PROJECT_ROOT).replace("\\", "/")

    with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        headers = next(reader)
        headers = [h.strip().replace('"', "") for h in headers]

        data_rows = []
        for r in reader:
            if r:
                data_rows.append([val.strip() for val in r])

    row_count = len(data_rows)
    (
        dates,
        missing_max_temp,
        missing_min_temp,
        missing_mean_temp,
        missing_total_precip,
        missing_total_rain,
        missing_total_snow,
        missing_snow_on_ground,
    ) = _aggregate_data_rows(data_rows, headers)

    date_start = min(dates).strftime("%Y-%m-%d") if dates else ""
    date_end = max(dates).strftime("%Y-%m-%d") if dates else ""

    return {
        "Dataset ID": "eccc_daily_weather",
        "Station role": station_role,
        "Station name": station_name,
        "Station ID used for request": str(station_id),
        "Climate ID": climate_id,
        "Year": str(year),
        "Source URL": url,
        "Filename": filename,
        "Relative raw path": rel_path,
        "Download date UTC": "2026-07-16",
        "File size": str(size),
        "SHA-256": sha256,
        "Row count": str(row_count),
        "Date start": date_start,
        "Date end": date_end,
        "Missing max temp": str(missing_max_temp),
        "Missing min temp": str(missing_min_temp),
        "Missing mean temp": str(missing_mean_temp),
        "Missing total precip": str(missing_total_precip),
        "Missing total rain": str(missing_total_rain),
        "Missing total snow": str(missing_total_snow),
        "Missing snow on ground": str(missing_snow_on_ground),
        "Audit status": "passed_with_limitations",
        "Notes": f"{station_role.capitalize()} station ECCC daily weather for {year}.",
    }


def process_directory(station_dir, station_role, station_name, station_id, climate_id):
    """Process all files in a directory and return metadata rows."""
    rows = []
    for year in range(2009, 2026):
        filename = f"en_climate_daily_QC_{climate_id}_{year}_P1D.csv"
        fpath = os.path.join(station_dir, filename)
        if not os.path.exists(fpath):
            print(f"Warning: {filename} does not exist at {fpath}")
            continue

        item = _process_annual_file(
            fpath, filename, year, station_role, station_name, station_id, climate_id
        )
        rows.append(item)
    return rows


def main():  # noqa: C901
    """Main execution entry point."""
    mctavish_dir = os.path.join(RAW_DIR, "mctavish")
    trudeau_dir = os.path.join(RAW_DIR, "montreal_trudeau")

    mctavish_rows = process_directory(mctavish_dir, "primary", "MCTAVISH", 10761, "7024745")
    trudeau_rows = process_directory(
        trudeau_dir, "secondary", "MONTREAL/PIERRE ELLIOTT TRUDEAU INTL", 30165, "702S006"
    )

    all_rows = mctavish_rows + trudeau_rows

    headers = [
        "Dataset ID",
        "Station role",
        "Station name",
        "Station ID used for request",
        "Climate ID",
        "Year",
        "Source URL",
        "Filename",
        "Relative raw path",
        "Download date UTC",
        "File size",
        "SHA-256",
        "Row count",
        "Date start",
        "Date end",
        "Missing max temp",
        "Missing min temp",
        "Missing mean temp",
        "Missing total precip",
        "Missing total rain",
        "Missing total snow",
        "Missing snow on ground",
        "Audit status",
        "Notes",
    ]

    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Generated weather resource manifest at {MANIFEST_PATH} with {len(all_rows)} rows.")


if __name__ == "__main__":
    main()
