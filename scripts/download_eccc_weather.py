#!/usr/bin/env python3
"""Download ECCC weather data.

Downloads the official station inventory and the annual daily weather files
for McTavish (Station ID 10761) and Montréal-Trudeau (Station ID 30165)
for the years 2009 through 2025 inclusive.
"""

import argparse
import hashlib
import os
import re
import sys
import time
import urllib.parse
import urllib.request


def calculate_sha256(filepath):
    """Calculate the SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def validate_csv_header(data_bytes):
    """Validate that the first bytes of the response look like a CSV header and not HTML."""
    try:
        header_text = data_bytes[:1024].decode("utf-8", errors="ignore")
    except Exception:
        return False
    if "<html" in header_text.lower() or "<!doctype html" in header_text.lower():
        return False
    return True


def _resolve_dest_path(dest_path, url, headers):
    """Resolve final destination path using Content-Disposition when necessary."""
    cd = headers.get("Content-Disposition")
    filename_from_cd = None
    if cd:
        fnames = re.findall(r'filename="?([^";]+)"?', cd)
        if fnames:
            filename_from_cd = fnames[0].strip()

    if os.path.isdir(dest_path) and filename_from_cd:
        return os.path.join(dest_path, filename_from_cd)
    elif os.path.isdir(dest_path):
        fallback_name = os.path.basename(urllib.parse.urlparse(url).path)
        if not fallback_name or fallback_name == "bulk_data_e.html":
            fallback_name = "weather_data.csv"
        return os.path.join(dest_path, fallback_name)
    return dest_path


def download_url(url, dest_path, retries=3, timeout=30):
    """Download a URL to a file with retries and validation."""
    print(f"Downloading: {url}")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    raise ValueError("HTML response received instead of data.")

                data = response.read()
                if not validate_csv_header(data):
                    raise ValueError("Downloaded content is not a valid CSV.")

                final_dest = _resolve_dest_path(dest_path, url, response.headers)
                with open(final_dest, "wb") as f:
                    f.write(data)

                size = os.path.getsize(final_dest)
                sha256 = calculate_sha256(final_dest)
                print(f"Saved to: {final_dest} ({size} bytes, SHA-256: {sha256})")
                return final_dest, size, sha256

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise RuntimeError("Download failed after exhausting all retries.") from e


def main():  # noqa: C901
    """Main execution entry point."""
    parser = argparse.ArgumentParser(description="Download ECCC daily weather data.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip downloading if the file already exists locally.",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(project_root, "data", "raw", "eccc_weather")

    # 1. Download Station Inventory
    inventory_url = "https://collaboration.cmc.ec.gc.ca/cmc/climate/Get_More_Data_Plus_de_donnees/Station%20Inventory%20EN.csv"
    inventory_dest = os.path.join(raw_dir, "station_inventory", "Station Inventory EN.csv")

    if os.path.exists(inventory_dest) and args.skip_existing:
        print(f"Station Inventory already exists at {inventory_dest}. Skipping.")
    else:
        try:
            download_url(inventory_url, inventory_dest)
        except Exception as e:
            print(f"Failed to download Station Inventory: {str(e)}")
            sys.exit(1)

    # 2. Download McTavish yearly daily files (2009–2025)
    mctavish_dir = os.path.join(raw_dir, "mctavish")
    mctavish_station_id = 10761
    mctavish_climate_id = "7024745"

    for year in range(2009, 2026):
        dest_filename = f"en_climate_daily_QC_{mctavish_climate_id}_{year}_P1D.csv"
        dest_path = os.path.join(mctavish_dir, dest_filename)

        if os.path.exists(dest_path) and args.skip_existing:
            print(f"McTavish {year} already exists. Skipping.")
            continue

        url = f"https://climate.weather.gc.ca/climate_data/bulk_data_e.html?format=csv&stationID={mctavish_station_id}&Year={year}&Month=1&Day=14&timeframe=2&submit=Download+Data"
        try:
            download_url(url, dest_path)
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"Failed to download McTavish data for {year}: {str(e)}")
            sys.exit(1)

    # 3. Download Montreal-Trudeau yearly daily files (2009–2025)
    trudeau_dir = os.path.join(raw_dir, "montreal_trudeau")
    trudeau_station_id = 30165
    trudeau_climate_id = "702S006"

    for year in range(2009, 2026):
        dest_filename = f"en_climate_daily_QC_{trudeau_climate_id}_{year}_P1D.csv"
        dest_path = os.path.join(trudeau_dir, dest_filename)

        if os.path.exists(dest_path) and args.skip_existing:
            print(f"Montréal-Trudeau {year} already exists. Skipping.")
            continue

        url = f"https://climate.weather.gc.ca/climate_data/bulk_data_e.html?format=csv&stationID={trudeau_station_id}&Year={year}&Month=1&Day=14&timeframe=2&submit=Download+Data"
        try:
            download_url(url, dest_path)
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"Failed to download Montréal-Trudeau data for {year}: {str(e)}")
            sys.exit(1)

    print("All ECCC downloads completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
