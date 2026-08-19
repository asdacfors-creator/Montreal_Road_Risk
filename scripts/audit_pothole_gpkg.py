#!/usr/bin/env python
"""Audit utility for pothole repair GeoPackage (GPKG) resources.

Performs read-only SQLite integrity checks, layer discovery, schema checks,
RTree checks, geometry/coordinate validation, date parsing, vehicle pattern
classification, duplicate analysis, and year mismatches.
"""

import argparse
import hashlib
import os
import re
import sqlite3
import sys

import geopandas as gpd
import pandas as pd


def check_sqlite_properties(filepath):
    """Perform read-only SQLite checks on the file."""
    # Connect using a read-only URI
    db_uri = f"file:{filepath}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    cursor = conn.cursor()

    try:
        integrity = cursor.execute("PRAGMA integrity_check;").fetchone()[0]
        app_id = cursor.execute("PRAGMA application_id;").fetchone()[0]
        user_ver = cursor.execute("PRAGMA user_version;").fetchone()[0]
    finally:
        conn.close()

    return integrity, app_id, user_ver


def get_gpkg_metadata(filepath):
    """Retrieve GPKG metadata tables information."""
    db_uri = f"file:{filepath}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    cursor = conn.cursor()

    metadata = {}
    try:
        # Contents
        cursor.execute("SELECT table_name, data_type, srs_id FROM gpkg_contents;")
        metadata["contents"] = cursor.fetchall()

        # Geometry columns
        cursor.execute(
            "SELECT table_name, column_name, geometry_type_name, srs_id, z, m FROM gpkg_geometry_columns;"
        )
        metadata["geometry_columns"] = cursor.fetchall()

        # Spatial Ref Sys for the layers
        cursor.execute(
            "SELECT srs_name, srs_id, organization, organization_coordsys_id, definition FROM gpkg_spatial_ref_sys;"
        )
        metadata["spatial_ref_sys"] = cursor.fetchall()
    except Exception as e:
        metadata["error"] = str(e)
    finally:
        conn.close()

    return metadata


def get_rtree_count(filepath, table_name, geom_column):
    """Get the row count of the RTree index for the geometry column."""
    db_uri = f"file:{filepath}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    cursor = conn.cursor()
    try:
        rtree_table = f"rtree_{table_name}_{geom_column}"
        cursor.execute(f"SELECT count(*) FROM {rtree_table};")
        count = cursor.fetchone()[0]
    except Exception:
        count = None
    finally:
        conn.close()
    return count


def _classify_vehicle_id(veh_str):
    """Classify Vehicle identifier into pattern categories."""
    if not veh_str:
        return "blank"
    veh_clean = str(veh_str).strip()
    if not veh_clean:
        return "blank"
    if veh_clean.isdigit():
        return "numeric_only"
    if veh_clean.startswith("NP-") and veh_clean[3:].isdigit():
        return "np_hyphen_number"
    if veh_clean.startswith("NP") and veh_clean[2:].isdigit():
        return "np_number"
    if veh_clean.startswith("CT"):
        return "ct_prefixed"
    return "other_non_empty"


def check_duplicate_pattern(df, columns):
    """Calculate duplicate patterns."""
    dups = df.duplicated(subset=columns, keep=False)
    total_rows = dups.sum()
    groups = df[dups].groupby(columns)
    num_groups = len(groups)
    excess_rows = df.duplicated(subset=columns, keep="first").sum()
    max_group_size = groups.size().max() if num_groups > 0 else 0
    return num_groups, total_rows, excess_rows, max_group_size


def parse_date_flexible(date_val):
    """Parse dates with space or T separator, and varying fractional seconds."""
    if pd.isnull(date_val):
        return pd.NaT
    date_str = str(date_val).strip()
    for fmt in [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except Exception:
            continue
    # Fallback to pandas automatic parser if possible
    try:
        return pd.to_datetime(date_str)
    except Exception:
        return pd.NaT


def _audit_geometry_quality(gdf, geom_col_info, crs_declared):
    """Audit the geometries in the GeoDataFrame."""
    geom_nulls = gdf.geometry.isnull().sum()
    geom_empties = gdf.geometry.is_empty.sum()
    geom_invalids = (~gdf.geometry.is_valid).sum()
    geom_types = gdf.geometry.geom_type.dropna().unique().tolist()
    geom_types_ok = all(isinstance(t, str) and t.upper() == "POINT" for t in geom_types)

    z_values = gdf.geometry.apply(lambda g: g.has_z if g else False).sum()
    m_values = 0

    bounds = gdf.total_bounds
    outside_regional_box = 0
    if crs_declared and crs_declared.is_geographic:
        lats = gdf.geometry.y
        lons = gdf.geometry.x
        outside_regional_box = (
            (lats < 45.0) | (lats > 46.0) | (lons < -75.0) | (lons > -72.0)
        ).sum()

    return {
        "null_count": int(geom_nulls),
        "empty_count": int(geom_empties),
        "invalid_count": int(geom_invalids),
        "geometry_types": geom_types,
        "geom_types_ok": geom_types_ok,
        "has_z_count": int(z_values),
        "has_m_count": int(m_values),
        "bounds": [float(x) for x in bounds],
        "outside_regional_box": int(outside_regional_box),
    }


def _audit_fid(filepath, table_name, row_count):
    """Audit the fid primary key column."""
    db_uri = f"file:{filepath}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT fid FROM {table_name} ORDER BY fid;")
        fids = [row[0] for row in cursor.fetchall()]
    except Exception:
        fids = []
    finally:
        conn.close()

    if not fids:
        return {
            "unique": False,
            "starts_at_1": False,
            "ends_at_n": False,
            "contiguous": False,
            "min_val": None,
            "max_val": None,
        }

    fid_unique = len(fids) == len(set(fids))
    fid_min = min(fids)
    fid_max = max(fids)
    fid_starts_1 = fid_min == 1
    fid_ends_n = fid_max == row_count
    fid_contiguous = len(fids) == (fid_max - fid_min + 1) and fid_unique

    return {
        "unique": fid_unique,
        "starts_at_1": fid_starts_1,
        "ends_at_n": fid_ends_n,
        "contiguous": fid_contiguous,
        "min_val": fid_min,
        "max_val": fid_max,
    }


def _audit_temporal(gdf, expected_year):
    """Audit temporal bounds, parse dates, and check calendar missingness."""
    parsed_dates = gdf["Date"].apply(parse_date_flexible)
    date_nulls = gdf["Date"].isnull().sum()
    date_blanks = (gdf["Date"].astype(str).str.strip() == "").sum()
    date_unparseable = (parsed_dates.isnull() & ~gdf["Date"].isnull()).sum()
    tz_aware_count = parsed_dates.apply(
        lambda d: d.tzinfo is not None if pd.notnull(d) else False
    ).sum()

    min_date = parsed_dates.min()
    max_date = parsed_dates.max()

    unique_dates = parsed_dates.dropna().dt.date.unique()
    num_unique_dates = len(unique_dates)

    counts_per_month = parsed_dates.dropna().dt.to_period("M").value_counts().sort_index()

    missing_dates = []
    if num_unique_dates > 1 and pd.notnull(min_date) and pd.notnull(max_date):
        full_range = pd.date_range(start=min_date.date(), end=max_date.date()).date
        missing_dates = [str(d) for d in full_range if d not in unique_dates]

    record_years = parsed_dates.dropna().dt.year.unique().tolist()
    out_of_year_records = parsed_dates.dropna()[parsed_dates.dropna().dt.year != expected_year]

    return {
        "min_date": str(min_date) if pd.notnull(min_date) else None,
        "max_date": str(max_date) if pd.notnull(max_date) else None,
        "unique_dates_count": num_unique_dates,
        "counts_per_month": {str(k): int(v) for k, v in counts_per_month.items()},
        "missing_dates_count": len(missing_dates),
        "missing_dates": missing_dates,
        "tz_aware_count": tz_aware_count,
        "date_nulls": int(date_nulls),
        "date_blanks": int(date_blanks),
        "date_unparseable": int(date_unparseable),
        "record_years": record_years,
        "out_of_year_records_count": len(out_of_year_records),
        "out_of_year_details": out_of_year_records.to_dict(),
    }, parsed_dates


def _audit_vehicle(gdf):
    """Audit vehicle distribution and classifications."""
    vehicle_nulls = gdf["Véhicule"].isnull().sum()
    vehicle_blanks = (gdf["Véhicule"].astype(str).str.strip() == "").sum()

    vehicle_pattern_counts = {
        "numeric_only": 0,
        "np_hyphen_number": 0,
        "np_number": 0,
        "ct_prefixed": 0,
        "other_non_empty": 0,
        "blank": 0,
    }
    for val in gdf["Véhicule"]:
        pat = _classify_vehicle_id(val)
        vehicle_pattern_counts[pat] += 1

    vehicle_freq = gdf["Véhicule"].value_counts()

    return {
        "null_count": int(vehicle_nulls),
        "blank_count": int(vehicle_blanks),
        "pattern_counts": vehicle_pattern_counts,
        "frequencies": {str(k): int(v) for k, v in vehicle_freq.items()},
    }


def _audit_duplicates(gdf, row_count):
    """Audit spatial and temporal duplicate patterns."""
    df_dup = gdf.copy()
    df_dup["X"] = df_dup.geometry.x
    df_dup["Y"] = df_dup.geometry.y
    df_dup_no_geom = df_dup.drop(columns=["geometry"])

    exact_groups, exact_rows, exact_excess, exact_max = check_duplicate_pattern(
        df_dup_no_geom, ["Véhicule", "Date", "X", "Y"]
    )
    dt_groups, dt_rows, dt_excess, dt_max = check_duplicate_pattern(df_dup_no_geom, ["Date"])
    geom_groups, geom_rows, geom_excess, geom_max = check_duplicate_pattern(
        df_dup_no_geom, ["X", "Y"]
    )
    dt_geom_groups, dt_geom_rows, dt_geom_excess, dt_geom_max = check_duplicate_pattern(
        df_dup_no_geom, ["Date", "X", "Y"]
    )
    veh_dt_groups, veh_dt_rows, veh_dt_excess, veh_dt_max = check_duplicate_pattern(
        df_dup_no_geom, ["Véhicule", "Date"]
    )

    adjacent_exact_excess = 0
    if row_count > 1:
        consec_match = (
            (df_dup_no_geom["Véhicule"] == df_dup_no_geom["Véhicule"].shift(1))
            & (df_dup_no_geom["Date"] == df_dup_no_geom["Date"].shift(1))
            & (df_dup_no_geom["X"] == df_dup_no_geom["X"].shift(1))
            & (df_dup_no_geom["Y"] == df_dup_no_geom["Y"].shift(1))
        )
        adjacent_exact_excess = consec_match.sum()

    return {
        "exact": {
            "groups": exact_groups,
            "total_rows": exact_rows,
            "excess_rows": exact_excess,
            "max_group": exact_max,
        },
        "same_datetime": {
            "groups": dt_groups,
            "total_rows": dt_rows,
            "excess_rows": dt_excess,
            "max_group": dt_max,
        },
        "same_geometry": {
            "groups": geom_groups,
            "total_rows": geom_rows,
            "excess_rows": geom_excess,
            "max_group": geom_max,
        },
        "same_datetime_coords": {
            "groups": dt_geom_groups,
            "total_rows": dt_geom_rows,
            "excess_rows": dt_geom_excess,
            "max_group": dt_geom_max,
        },
        "same_vehicle_datetime": {
            "groups": veh_dt_groups,
            "total_rows": veh_dt_rows,
            "excess_rows": veh_dt_excess,
            "max_group": veh_dt_max,
        },
        "adjacent_exact_excess": int(adjacent_exact_excess),
    }


def run_audit(filepath, expected_year):
    """Run read-only audit on GeoPackage."""
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        return None

    file_size = os.path.getsize(filepath)
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    checksum = sha256_hash.hexdigest()

    try:
        integrity, app_id, user_ver = check_sqlite_properties(filepath)
    except Exception as e:
        print(f"Error opening SQLite database: {e}", file=sys.stderr)
        return None

    meta = get_gpkg_metadata(filepath)
    if "error" in meta:
        print(f"Error reading GPKG metadata: {meta['error']}", file=sys.stderr)
        return None

    feature_layers = [r[0] for r in meta["contents"] if r[1] == "features"]
    if len(feature_layers) != 1:
        print(
            f"Error: Expected exactly 1 feature layer, found {len(feature_layers)}: {feature_layers}",
            file=sys.stderr,
        )
        return None

    layer_name = feature_layers[0]

    try:
        gdf = gpd.read_file(filepath, layer=layer_name)
    except Exception as e:
        print(f"Error reading layer {layer_name} with GeoPandas: {e}", file=sys.stderr)
        return None

    row_count = len(gdf)
    geom_col_info = [r for r in meta["geometry_columns"] if r[0] == layer_name]
    if not geom_col_info:
        print(f"Error: Geometry column metadata missing for layer {layer_name}", file=sys.stderr)
        return None

    geom_col_name = geom_col_info[0][1]
    geom_type_name = geom_col_info[0][2]
    geom_srs_id = geom_col_info[0][3]
    has_z = geom_col_info[0][4]
    has_m = geom_col_info[0][5]

    rtree_count = get_rtree_count(filepath, layer_name, geom_col_name)
    actual_cols = list(gdf.columns)
    schema_ok = "geometry" in actual_cols and "Véhicule" in actual_cols and "Date" in actual_cols
    crs_info = [r for r in meta["spatial_ref_sys"] if r[1] == geom_srs_id]
    crs_declared = gdf.crs

    # Run sub-audits
    geom_aud = _audit_geometry_quality(gdf, geom_col_info[0], crs_declared)
    fid_aud = _audit_fid(filepath, layer_name, row_count)
    temp_aud, parsed_dates = _audit_temporal(gdf, expected_year)
    veh_aud = _audit_vehicle(gdf)
    dup_aud = _audit_duplicates(gdf, row_count)

    # Filename / Layer mismatches
    filename_year = None
    fn_match = re.search(r"(\d{4})", os.path.basename(filepath))
    if fn_match:
        filename_year = int(fn_match.group(1))

    layer_year = None
    ln_match = re.search(r"(\d{4})", layer_name)
    if ln_match:
        layer_year = int(ln_match.group(1))

    sqlite_ok = integrity == "ok" and app_id == 0x47504B47 and user_ver in [10200, 10300, 10400]
    geom_ok = (
        geom_aud["null_count"] == 0
        and geom_aud["empty_count"] == 0
        and geom_aud["invalid_count"] == 0
        and geom_aud["geom_types_ok"]
    )
    dates_ok = (
        temp_aud["date_nulls"] == 0
        and temp_aud["date_blanks"] == 0
        and temp_aud["date_unparseable"] == 0
    )
    rtree_ok = rtree_count == row_count

    passed = (
        sqlite_ok
        and schema_ok
        and geom_ok
        and dates_ok
        and rtree_ok
        and fid_aud["unique"]
        and fid_aud["starts_at_1"]
        and fid_aud["ends_at_n"]
        and fid_aud["contiguous"]
    )

    results = {
        "file_integrity": {
            "size_bytes": file_size,
            "sha256": checksum,
            "integrity": integrity,
            "application_id": app_id,
            "user_version": user_ver,
        },
        "layer_info": {
            "discovered_layers": feature_layers,
            "layer_name": layer_name,
            "geometry_type": geom_type_name,
            "has_z": has_z,
            "has_m": has_m,
            "row_count": row_count,
            "rtree_count": rtree_count,
        },
        "schema": {"columns": actual_cols, "schema_ok": schema_ok},
        "fid_audit": fid_aud,
        "geometry_quality": geom_aud,
        "crs": {"declared": str(crs_declared), "srs_id": geom_srs_id, "metadata": crs_info},
        "temporal": temp_aud,
        "vehicle": veh_aud,
        "duplicates": dup_aud,
        "mismatches": {
            "filename_year": filename_year,
            "expected_year": expected_year,
            "layer_year": layer_year,
            "record_years": temp_aud["record_years"],
            "out_of_year_records_count": temp_aud["out_of_year_records_count"],
            "out_of_year_details": temp_aud["out_of_year_details"],
        },
        "raw_pass": passed,
    }

    return results


def print_report(res):
    """Format and print results."""
    fi = res["file_integrity"]
    li = res["layer_info"]
    fa = res["fid_audit"]
    gq = res["geometry_quality"]
    cr = res["crs"]
    te = res["temporal"]
    ve = res["vehicle"]
    du = res["duplicates"]
    mi = res["mismatches"]

    print("=== GEOPACKAGE AUDIT RESULTS ===")
    print(f"File Size: {fi['size_bytes']} bytes")
    print(f"SHA-256 Checksum: {fi['sha256']}")
    print(f"SQLite Integrity: {fi['integrity']}")
    print(f"Application ID: {hex(fi['application_id'])}")
    print(f"User Version: {fi['user_version']}")
    print("")
    print(f"Layer Name: {li['layer_name']}")
    print(f"Geometry Type: {li['geometry_type']} (Z={li['has_z']}, M={li['has_m']})")
    print(f"Row Count: {li['row_count']}")
    print(f"RTree Count: {li['rtree_count']}")
    print("")
    print("FID Audit:")
    print(
        f"  Unique: {fa['unique']}, Contiguous: {fa['contiguous']}, Starts 1: {fa['starts_at_1']}, Ends N: {fa['ends_at_n']}"
    )
    print(f"  Min: {fa['min_val']}, Max: {fa['max_val']}")
    print("")
    print("Geometry Quality:")
    print(f"  Null: {gq['null_count']}, Empty: {gq['empty_count']}, Invalid: {gq['invalid_count']}")
    print(f"  Bounds: {gq['bounds']}")
    print(f"  Outside Regional Box: {gq['outside_regional_box']}")
    print("")
    print("CRS Details:")
    print(f"  Declared: {cr['declared']}")
    print(f"  SRS ID: {cr['srs_id']}")
    print("")
    print("Temporal Audit:")
    print(f"  Range: {te['min_date']} to {te['max_date']}")
    print(f"  Unique Observed Dates: {te['unique_dates_count']}")
    print(f"  Monthly Counts: {te['counts_per_month']}")
    print(f"  Missing Dates inside Range: {te['missing_dates_count']}")
    print(f"  Timezone-Aware Rows: {te['tz_aware_count']}")
    print(
        f"  Null Dates: {te['date_nulls']}, Blank: {te['date_blanks']}, Unparseable: {te['date_unparseable']}"
    )
    print("")
    print("Vehicle Distribution:")
    print(f"  Null: {ve['null_count']}, Blank: {ve['blank_count']}")
    print(f"  Pattern Counts: {ve['pattern_counts']}")
    print(f"  Frequencies (Top 10): {dict(list(ve['frequencies'].items())[:10])}")
    print("")
    print("Duplicate Patterns (groups / rows / excess / max):")
    print(
        f"  Exact: {du['exact']['groups']} / {du['exact']['total_rows']} / {du['exact']['excess_rows']} / {du['exact']['max_group']}"
    )
    print(
        f"  Same Datetime: {du['same_datetime']['groups']} / {du['same_datetime']['total_rows']} / {du['same_datetime']['excess_rows']} / {du['same_datetime']['max_group']}"
    )
    print(
        f"  Same Geometry: {du['same_geometry']['groups']} / {du['same_geometry']['total_rows']} / {du['same_geometry']['excess_rows']} / {du['same_geometry']['max_group']}"
    )
    print(
        f"  Same Datetime + Geometry: {du['same_datetime_coords']['groups']} / {du['same_datetime_coords']['total_rows']} / {du['same_datetime_coords']['excess_rows']} / {du['same_datetime_coords']['max_group']}"
    )
    print(
        f"  Same Vehicle + Datetime: {du['same_vehicle_datetime']['groups']} / {du['same_vehicle_datetime']['total_rows']} / {du['same_vehicle_datetime']['excess_rows']} / {du['same_vehicle_datetime']['max_group']}"
    )
    print(f"  Adjacent Exact Excess: {du['adjacent_exact_excess']}")
    print("")
    print("Year Mismatches:")
    print(
        f"  Filename Year: {mi['filename_year']}, Expected: {mi['expected_year']}, Layer Year: {mi['layer_year']}"
    )
    print(f"  Record Years Found: {mi['record_years']}")
    print(f"  Out of Year Records Count: {mi['out_of_year_records_count']}")


def main():  # noqa: C901
    parser = argparse.ArgumentParser(description="Audit a pothole repair GPKG file.")
    parser.add_argument("--input", required=True, help="Path to GPKG.")
    parser.add_argument("--expected-year", type=int, required=True, help="Expected data year.")
    args = parser.parse_args()

    res = run_audit(args.input, args.expected_year)
    if not res:
        return 1

    print_report(res)

    if not res["raw_pass"]:
        print("\nHard structural failure detected!", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
