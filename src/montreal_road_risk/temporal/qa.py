import json
import os

from montreal_road_risk.io.checksums import scan_raw_files

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")


def verify_raw_immutability(pre_snap_path):
    """
    Scan raw files and assert that they match a cached pre-run inventory.
    """
    post_inventory = scan_raw_files(RAW_DIR, PROJECT_ROOT)

    if not os.path.exists(pre_snap_path):
        return True, "Pre-run snapshot not found to compare."

    with open(pre_snap_path, "r") as f:
        pre_inventory = json.load(f)

    if pre_inventory == post_inventory:
        return True, "Success: Raw files remain completely unchanged."
    else:
        return False, "CRITICAL: Raw files have been modified during temporal processing!"


def reconcile_temporal_counts(
    potholes_count,
    pavement_count,
    assets_count,
    mctavish_count,
    trudeau_count,
    canonical_weather_count
):
    """
    Verify temporal zero-row-loss target matches.
    """
    expected_potholes = 1027267
    expected_pavement = 121163
    expected_assets = 64025
    expected_weather_daily = 6209  # Days from 2009-01-01 through 2025-12-31

    errors = []

    if potholes_count != expected_potholes:
        errors.append(f"Potholes count mismatch: expected {expected_potholes}, got {potholes_count}")

    if pavement_count != expected_pavement:
        errors.append(f"Pavement count mismatch: expected {expected_pavement}, got {pavement_count}")

    if assets_count != expected_assets:
        errors.append(f"Road assets count mismatch: expected {expected_assets}, got {assets_count}")

    if mctavish_count != expected_weather_daily:
        errors.append(f"McTavish weather count mismatch: expected {expected_weather_daily}, got {mctavish_count}")

    if trudeau_count != expected_weather_daily:
        errors.append(f"Trudeau weather count mismatch: expected {expected_weather_daily}, got {trudeau_count}")

    if canonical_weather_count != expected_weather_daily:
        errors.append(f"Canonical weather count mismatch: expected {expected_weather_daily}, got {canonical_weather_count}")

    if errors:
        raise AssertionError("Zero-row-loss verification FAILED:\n" + "\n".join(errors))

    return True
