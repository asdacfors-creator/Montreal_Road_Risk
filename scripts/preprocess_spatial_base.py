#!/usr/bin/env python3
"""Phase 3A Spatial Preprocessing Integration Script.

Performs canonical data loading, CRS selection/reprojection, coordinate validation,
schema mapping, and geometry QA. Outputs derived interim GeoParquet/Parquet datasets.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

import geopandas as gpd
import pandas as pd
import pyproj

# Import from our custom package
from montreal_road_risk.io.checksums import scan_raw_files
from montreal_road_risk.io.loaders import load_csv, load_geojson, load_gpkg_layer
from montreal_road_risk.io.writers import verify_parquet_roundtrip, write_geoparquet, write_parquet
from montreal_road_risk.spatial.crs import reproject_gdf
from montreal_road_risk.spatial.qa import perform_spatial_qa
from montreal_road_risk.spatial.schema import add_provenance_fields, map_canonical_columns

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
INTERIM_DIR = os.path.join(PROJECT_ROOT, "data", "interim")
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "outputs", "evidence", "phase_3a")


def parse_asset_date(date_val):
    """Parse construction and resurfacing dates, returning parsed date, precision, and imprecise flag."""
    if pd.isna(date_val) or str(date_val).strip().lower() in ("inconnu", "none", "", "nan", "0"):
        return None, "unknown", 1

    val_str = str(date_val).strip()

    # Try common precise formats including %Y%m%d%H%M%S
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt, "precise", 0
        except ValueError:
            pass

    # Try extracting a 4-digit year
    match = re.search(r"\b(18|19|20)\d{2}\b", val_str)
    if not match:
        match = re.match(r"^(18|19|20)\d{2}", val_str)
    if match:
        year = int(match.group(0)[:4])
        return datetime(year, 1, 1), "imprecise_year", 0

    return None, "unparseable", 1


def _normalize_df_columns(df):
    """Normalize column names by replacing spaces with underscores and converting accents to ASCII."""
    df = df.copy()
    new_cols = {}
    for col in df.columns:
        if col == "geometry":
            continue
        k = str(col).strip().replace(" ", "_")
        k = (
            k.replace("é", "e")
            .replace("è", "e")
            .replace("à", "a")
            .replace("ù", "u")
            .replace("ç", "c")
        )
        k = (
            k.replace("É", "E")
            .replace("È", "E")
            .replace("À", "A")
            .replace("Ù", "U")
            .replace("Ç", "C")
        )
        new_cols[col] = k
    return df.rename(columns=new_cols)


def process_geobase(rules, working_crs, version, admin_bbox):
    """Load, reproject, and canonicalize Montreal Géobase."""
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path"])
    print(f"Processing Géobase: {raw_path}")

    gdf = load_geojson(raw_path)
    gdf = _normalize_df_columns(gdf)
    gdf.crs = rules["interpreted_source_crs"]

    dest_gdf = reproject_gdf(gdf, working_crs)

    # Run QA
    qa_results = perform_spatial_qa(
        gdf, dest_gdf, admin_bbox, rules["interpreted_source_crs"], working_crs
    )

    # Add provenance and filter columns
    filename = os.path.basename(raw_path)
    dest_gdf = add_provenance_fields(
        dest_gdf,
        "geobase",
        filename,
        "GeoJSON",
        2026,
        rules["crs_status"],
        rules["interpreted_source_crs"],
        working_crs,
        version,
    )

    # Keep requested columns
    dest_gdf = map_canonical_columns(
        dest_gdf,
        {col: col for col in rules["canonical_fields_keep"]},
        keep_additional_fields=list(gdf.columns),  # preserve other original columns
    )

    # Write GeoParquet
    out_path = os.path.join(PROJECT_ROOT, rules["interim_path"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_geoparquet(dest_gdf, out_path)

    # Verify roundtrip
    verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

    return dest_gdf, qa_results


def process_borough_boundaries(rules, working_crs, version):
    """Load and canonicalize Montreal Administrative Boundaries."""
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path"])
    print(f"Processing Administrative Boundaries: {raw_path}")

    gdf = load_geojson(raw_path)
    gdf = _normalize_df_columns(gdf)
    gdf.crs = rules["declared_source_crs"]

    # We do not transform it, we keep it as is
    dest_gdf = gdf.copy()

    # Run QA (no transformation, so bounds and geometry are identical)
    qa_results = perform_spatial_qa(gdf, dest_gdf, None, rules["declared_source_crs"], working_crs)

    # Add provenance and filter columns
    filename = os.path.basename(raw_path)
    dest_gdf = add_provenance_fields(
        dest_gdf,
        "borough_boundaries",
        filename,
        "GeoJSON",
        2023,
        rules["crs_status"],
        rules["declared_source_crs"],
        working_crs,
        version,
    )

    dest_gdf = map_canonical_columns(
        dest_gdf,
        {col: col for col in rules["canonical_fields_keep"]},
        keep_additional_fields=list(gdf.columns),
    )

    # Write GeoParquet
    out_path = os.path.join(PROJECT_ROOT, rules["interim_path"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_geoparquet(dest_gdf, out_path)

    verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

    return dest_gdf, qa_results


def calculate_construction_interval(c_dt, c_prec_ref):
    """Calculate the lower and upper bounds for construction date based on precision reference."""
    if c_dt is None:
        return None, None

    c_prec_ref_l = str(c_prec_ref).strip().lower()
    if "précise" in c_prec_ref_l:
        if "mois courant" in c_prec_ref_l:
            c_min = pd.Timestamp(c_dt).replace(day=1)
            c_max = (pd.Timestamp(c_dt).replace(day=28) + pd.Timedelta(days=4)).replace(day=1) - pd.Timedelta(days=1)
        else:
            c_min = pd.Timestamp(c_dt)
            c_max = pd.Timestamp(c_dt)
    elif "année courante" in c_prec_ref_l:
        c_min = pd.Timestamp(c_dt.year, 1, 1)
        c_max = pd.Timestamp(c_dt.year, 12, 31)
    elif "6 mois" in c_prec_ref_l:
        c_min = pd.Timestamp(c_dt) - pd.DateOffset(months=6)
        c_max = pd.Timestamp(c_dt) + pd.DateOffset(months=6)
    elif "5 ans" in c_prec_ref_l:
        c_min = pd.Timestamp(c_dt) - pd.DateOffset(years=5)
        c_max = pd.Timestamp(c_dt) + pd.DateOffset(years=5)
    elif "10 ans" in c_prec_ref_l:
        c_min = pd.Timestamp(c_dt) - pd.DateOffset(years=10)
        c_max = pd.Timestamp(c_dt) + pd.DateOffset(years=10)
    elif "25 ans" in c_prec_ref_l:
        c_min = pd.Timestamp(c_dt) - pd.DateOffset(years=25)
        c_max = pd.Timestamp(c_dt) + pd.DateOffset(years=25)
    elif "100 ans" in c_prec_ref_l:
        c_min = pd.Timestamp(c_dt) - pd.DateOffset(years=100)
        c_max = pd.Timestamp(c_dt) + pd.DateOffset(years=100)
    else:
        c_min = pd.Timestamp(c_dt.year, 1, 1)
        c_max = pd.Timestamp(c_dt.year, 12, 31)

    return c_min.date(), c_max.date()


def calculate_resurfacing_interval(r_dt, r_prec):
    """Calculate the lower and upper bounds for resurfacing date based on precision type."""
    if r_dt is None:
        return None, None

    if r_prec == "imprecise_year":
        r_max_d = datetime(r_dt.year, 12, 31).date()
    else:
        r_max_d = r_dt.date()

    return r_dt.date(), r_max_d


def classify_date_contradiction(c_val, r_val, c_prec, r_prec, c_dt, r_dt, c_min_d, c_max_d, r_max_d):
    """Classify the date contradiction status and return the flag."""
    if c_prec == "missing" or r_prec == "missing" or c_val is None or r_val is None or c_dt is None or r_dt is None:
        status = "missing_date"
    elif c_prec == "unknown" or r_prec == "unknown":
        status = "unresolved_precision"
    else:
        if r_max_d < c_min_d:
            status = "confirmed_contradiction"
        elif r_dt.date() < c_dt.date():
            status = "possible_contradiction"
        else:
            status = "no_contradiction"

    flag = 1 if status in ("confirmed_contradiction", "possible_contradiction") else 0
    return status, flag


def process_road_assets(rules, working_crs, version, admin_bbox):
    """Load, reproject, and canonicalize Road-Assets Pavement Polygons."""
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path"])
    print(f"Processing Road Assets: {raw_path}")

    # Load using zip protocol
    gdf = load_geojson(f"zip://{raw_path}")
    gdf = _normalize_df_columns(gdf)
    gdf.crs = rules["interpreted_source_crs"]

    dest_gdf = reproject_gdf(gdf, working_crs)

    # Run QA
    qa_results = perform_spatial_qa(
        gdf, dest_gdf, admin_bbox, rules["interpreted_source_crs"], working_crs
    )

    # Parse dates and calculate precision/flags
    construction_date_lower_bounds = []
    construction_date_upper_bounds = []
    construction_year_starts = []
    construction_precisions = []
    construction_is_proxies = []
    construction_unknowns = []

    resurfacing_date_lower_bounds = []
    resurfacing_date_upper_bounds = []
    resurfacing_year_starts = []
    resurfacing_precisions = []
    resurfacing_is_proxies = []
    resurfacing_unknowns = []

    resurfacing_before_construction_flags = []
    date_contradiction_statuses = []

    for _, row in dest_gdf.iterrows():
        c_val = row.get("DATECONSTRUCTION")
        c_prec_ref = str(row.get("DATECONSTRUCTIONPREC_REF")).strip() if row.get("DATECONSTRUCTIONPREC_REF") else ""

        # Parse construction date
        c_dt, _, _ = parse_asset_date(c_val)

        # Classify precision based on DATECONSTRUCTIONPREC_REF
        if pd.isna(c_val) or str(c_val).strip().lower() in ("inconnu", "none", "", "nan", "0"):
            c_prec = "missing"
            c_dt = None
        elif "précise" in c_prec_ref.lower():
            c_prec = "precise"
        elif "100 ans" in c_prec_ref.lower():
            c_prec = "approximate_interval"
        elif "inconnu" in c_prec_ref.lower():
            c_prec = "unknown"
            c_dt = None
        else:
            c_prec = "imprecise_year"

        # Calculate bounds using helper
        c_min_d, c_max_d = calculate_construction_interval(c_dt, c_prec_ref)

        if c_dt is not None:
            c_year_start = datetime(c_dt.year, 1, 1).date()
            c_lower_bound = c_dt.date()
            c_is_proxy = 1 if c_prec in ("imprecise_year", "approximate_interval", "unknown") else 0
            c_unknown = 0
        else:
            c_year_start = None
            c_lower_bound = None
            c_is_proxy = 1
            c_unknown = 1

        construction_date_lower_bounds.append(c_lower_bound)
        construction_date_upper_bounds.append(c_max_d)
        construction_year_starts.append(c_year_start)
        construction_precisions.append(c_prec)
        construction_is_proxies.append(c_is_proxy)
        construction_unknowns.append(c_unknown)

        # Parse resurfacing date
        r_val = row.get("DATERESURFACAGE")
        r_dt, _, _ = parse_asset_date(r_val)

        if pd.isna(r_val) or str(r_val).strip().lower() in ("inconnu", "none", "", "nan", "0"):
            r_prec = "missing"
            r_dt = None
        else:
            val_str = str(r_val).strip()
            if val_str.endswith("0101000000") or val_str.endswith("0701000000"):
                r_prec = "imprecise_year"
            else:
                r_prec = "precise"

        # Calculate bounds using helper
        r_min_d, r_max_d = calculate_resurfacing_interval(r_dt, r_prec)

        if r_dt is not None:
            r_year_start = datetime(r_dt.year, 1, 1).date()
            r_lower_bound = r_dt.date()
            r_is_proxy = 1 if r_prec in ("imprecise_year", "unknown") else 0
            r_unknown = 0
        else:
            r_year_start = None
            r_lower_bound = None
            r_is_proxy = 1
            r_unknown = 1

        resurfacing_date_lower_bounds.append(r_lower_bound)
        resurfacing_date_upper_bounds.append(r_max_d)
        resurfacing_year_starts.append(r_year_start)
        resurfacing_precisions.append(r_prec)
        resurfacing_is_proxies.append(r_is_proxy)
        resurfacing_unknowns.append(r_unknown)

        # Categorize date contradiction status using helper
        status, flag = classify_date_contradiction(
            c_val, r_val, c_prec, r_prec, c_dt, r_dt, c_min_d, c_max_d, r_max_d
        )

        date_contradiction_statuses.append(status)
        resurfacing_before_construction_flags.append(flag)

    dest_gdf["construction_date_lower_bound"] = construction_date_lower_bounds
    dest_gdf["construction_date_upper_bound"] = construction_date_upper_bounds
    dest_gdf["construction_year_start"] = construction_year_starts
    dest_gdf["construction_date_precision"] = construction_precisions
    dest_gdf["construction_date_is_proxy"] = construction_is_proxies
    dest_gdf["construction_date_unknown"] = construction_unknowns

    dest_gdf["resurfacing_date_lower_bound"] = resurfacing_date_lower_bounds
    dest_gdf["resurfacing_date_upper_bound"] = resurfacing_date_upper_bounds
    dest_gdf["resurfacing_year_start"] = resurfacing_year_starts
    dest_gdf["resurfacing_date_precision"] = resurfacing_precisions
    dest_gdf["resurfacing_date_is_proxy"] = resurfacing_is_proxies
    dest_gdf["resurfacing_date_unknown"] = resurfacing_unknowns

    dest_gdf["resurfacing_before_construction_candidate_flag"] = (
        resurfacing_before_construction_flags
    )
    dest_gdf["date_contradiction_status"] = date_contradiction_statuses

    # Add WKT of raw geometry
    dest_gdf["original_geometry"] = gdf.geometry.apply(lambda g: g.wkt if g else None)

    # Add provenance and map columns
    filename = os.path.basename(raw_path)
    dest_gdf = add_provenance_fields(
        dest_gdf,
        "road_assets_pavement",
        filename,
        "ZIP GeoJSON",
        2026,
        rules["crs_status"],
        rules["interpreted_source_crs"],
        working_crs,
        version,
    )

    dest_gdf = map_canonical_columns(
        dest_gdf,
        rules["field_mapping"],
        keep_additional_fields=[
            "construction_date_lower_bound",
            "construction_date_upper_bound",
            "construction_year_start",
            "construction_date_precision",
            "construction_date_is_proxy",
            "construction_date_unknown",
            "resurfacing_date_lower_bound",
            "resurfacing_date_upper_bound",
            "resurfacing_year_start",
            "resurfacing_date_precision",
            "resurfacing_date_is_proxy",
            "resurfacing_date_unknown",
            "resurfacing_before_construction_candidate_flag",
            "date_contradiction_status",
        ],
    )

    # Write GeoParquet
    out_path = os.path.join(PROJECT_ROOT, rules["interim_path"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_geoparquet(dest_gdf, out_path)

    verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

    return dest_gdf, qa_results


def _extract_pothole_datetime_fields(df, is_gpkg=False):
    """Unified helper to parse dates, times, and timestamps for potholes."""
    df = df.copy()
    if is_gpkg:
        # Preserve original raw Date string verbatim
        df["event_timestamp_raw"] = df["Date"].astype(str)

        # Parse using mixed format to support all audited formats
        if pd.api.types.is_datetime64_any_dtype(df["Date"]):
            ts = df["Date"]
        else:
            ts = pd.to_datetime(df["Date"], errors="coerce", format="mixed")
        df["event_timestamp"] = ts
        df["event_timestamp_naive"] = ts

        # Parse event_date_raw and event_time_raw directly from raw text string
        date_parts = []
        time_parts = []
        for val in df["event_timestamp_raw"]:
            val_clean = val.strip()
            if not val_clean or val_clean.lower() in ("nan", "none", "nat"):
                date_parts.append("unknown")
                time_parts.append("00:00:00")
                continue
            if "T" in val_clean:
                parts = val_clean.split("T")
                date_part = parts[0]
                time_part = parts[1]
            else:
                parts = val_clean.split()
                if len(parts) == 2:
                    date_part = parts[0]
                    time_part = parts[1]
                elif len(parts) == 1:
                    date_part = parts[0]
                    time_part = "00:00:00"
                else:
                    date_part = "unknown"
                    time_part = "00:00:00"
            date_parts.append(date_part)
            time_parts.append(time_part)
        df["event_date_raw"] = date_parts
        df["event_time_raw"] = time_parts
    else:
        df["event_timestamp_raw"] = df["DateJour"].astype(str) + " " + df["DateHeure"].astype(str)
        df["event_date_raw"] = df["DateJour"].astype(str)
        df["event_time_raw"] = df["DateHeure"].astype(str)
        ts = pd.to_datetime(df["event_timestamp_raw"], errors="coerce")
        df["event_timestamp"] = ts
        df["event_timestamp_naive"] = ts
    return df


def _compute_pothole_flags(df, year):
    """Compute duplicate and out-of-year flags for potholes."""
    # Out of year
    parsed_year = pd.to_datetime(df["event_date_raw"], errors="coerce").dt.year
    df["out_of_source_year_flag"] = (parsed_year != year).astype(int)

    # Duplicates (preserve all, just flag)
    df["exact_duplicate_candidate_flag"] = df.duplicated(
        subset=[
            "vehicle_id_raw",
            "event_date_raw",
            "event_time_raw",
            "latitude_raw",
            "longitude_raw",
        ],
        keep="first",
    ).astype(int)

    df["spatial_temporal_duplicate_candidate_flag"] = df.duplicated(
        subset=["event_date_raw", "event_time_raw", "latitude_raw", "longitude_raw"], keep="first"
    ).astype(int)
    return df


def process_potholes_csv(rules, year, working_crs, version, admin_bbox):
    """Load, reproject, and canonicalize a single Pothole Repairs CSV file."""
    filename = rules["csv_sources"][str(year)]
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path_pattern"], filename)
    print(f"Processing Pothole CSV: {raw_path}")

    df = load_csv(raw_path)
    df = _normalize_df_columns(df)
    df = _extract_pothole_datetime_fields(df, is_gpkg=False)

    # Validate coordinate range
    valid_mask = (df["Longitude"].between(-74.8, -73.0)) & (df["Latitude"].between(45.0, 46.5))
    invalid_coords_count = len(df) - valid_mask.sum()
    if invalid_coords_count > 0:
        print(
            f"Warning: {invalid_coords_count} records have out-of-bounds coordinates in {filename}."
        )

    # Construct Point geometries
    geom = gpd.points_from_xy(df["Longitude"], df["Latitude"])
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs=rules["csv_source_crs"])

    dest_gdf = reproject_gdf(gdf, working_crs)

    # Run QA
    qa_results = perform_spatial_qa(gdf, dest_gdf, admin_bbox, rules["csv_source_crs"], working_crs)

    dest_gdf["original_geometry"] = gdf.geometry.apply(lambda g: g.wkt if g else None)

    dest_gdf = add_provenance_fields(
        dest_gdf,
        "mechanized_pothole_repairs",
        filename,
        "CSV",
        year,
        rules["csv_crs_status"],
        rules["csv_source_crs"],
        working_crs,
        version,
    )

    dest_gdf = map_canonical_columns(
        dest_gdf,
        rules["csv_field_mapping"],
        keep_additional_fields=["event_timestamp", "event_date_raw", "event_time_raw", "event_timestamp_raw", "event_timestamp_naive"],
    )
    dest_gdf = _compute_pothole_flags(dest_gdf, year)

    # Write GeoParquet
    out_path = os.path.join(PROJECT_ROOT, rules["interim_path_pattern"].format(YEAR=year))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_geoparquet(dest_gdf, out_path)

    verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

    return dest_gdf, qa_results


def process_potholes_2021(rules, working_crs, version, admin_bbox):
    """Load, reproject, and canonicalize 2021 GPKG Pothole Repairs."""
    gpkg_rules = rules["gpkg_2021"]
    filename = gpkg_rules["filename"]
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path_pattern"], filename)
    print(f"Processing 2021 Pothole GPKG: {raw_path}")

    gdf = load_gpkg_layer(raw_path)
    gdf = _normalize_df_columns(gdf)

    # Normalize vehicle column name
    for col in gdf.columns:
        if "hicule" in col:
            gdf = gdf.rename(columns={col: "Véhicule"})

    gdf.crs = gpkg_rules["interpreted_source_crs"]
    gdf = _extract_pothole_datetime_fields(gdf, is_gpkg=True)

    dest_gdf = reproject_gdf(gdf, working_crs)

    # Run QA
    qa_results = perform_spatial_qa(
        gdf, dest_gdf, admin_bbox, gpkg_rules["interpreted_source_crs"], working_crs
    )

    # Obtain geographic coordinates from geometry (which is EPSG:4326 in raw)
    dest_gdf["latitude_raw"] = gdf.geometry.y
    dest_gdf["longitude_raw"] = gdf.geometry.x
    dest_gdf["original_geometry"] = gdf.geometry.apply(lambda g: g.wkt if g else None)

    dest_gdf = add_provenance_fields(
        dest_gdf,
        "mechanized_pothole_repairs",
        filename,
        "GPKG",
        2021,
        gpkg_rules["crs_status"],
        gpkg_rules["interpreted_source_crs"],
        working_crs,
        version,
    )

    dest_gdf = map_canonical_columns(
        dest_gdf,
        gpkg_rules["field_mapping"],
        keep_additional_fields=[
            "event_timestamp",
            "event_date_raw",
            "event_time_raw",
            "latitude_raw",
            "longitude_raw",
            "event_timestamp_raw",
            "event_timestamp_naive",
        ],
    )
    dest_gdf = _compute_pothole_flags(dest_gdf, 2021)

    # Write GeoParquet
    out_path = os.path.join(PROJECT_ROOT, rules["interim_path_pattern"].format(YEAR=2021))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_geoparquet(dest_gdf, out_path)

    verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

    return dest_gdf, qa_results


def process_potholes_projected(rules, year, working_crs, version, admin_bbox):
    """Load, reproject, and canonicalize projected GPKG Potholes (2022-2025)."""
    gpkg_rules = rules["gpkg_projected"]
    filename = f"remplissage_niddepoule_{year}.gpkg"
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path_pattern"], filename)
    print(f"Processing Projected GPKG {year}: {raw_path}")

    gdf = load_gpkg_layer(raw_path)
    gdf = _normalize_df_columns(gdf)

    # Normalize vehicle column name
    for col in gdf.columns:
        if "hicule" in col:
            gdf = gdf.rename(columns={col: "Véhicule"})

    gdf.crs = gpkg_rules["declared_source_crs"]
    gdf = _extract_pothole_datetime_fields(gdf, is_gpkg=True)

    dest_gdf = reproject_gdf(gdf, working_crs)

    # Run QA
    qa_results = perform_spatial_qa(
        gdf, dest_gdf, admin_bbox, gpkg_rules["declared_source_crs"], working_crs
    )

    # Transform coordinates from EPSG:32188 to EPSG:4326 for lat/lon raw using pyproj
    transformer_geographic = pyproj.Transformer.from_crs(working_crs, "EPSG:4326", always_xy=True)
    lons = []
    lats = []
    for geom in dest_gdf.geometry:
        if geom is None or geom.is_empty:
            lons.append(None)
            lats.append(None)
        else:
            pt = geom.centroid
            lon, lat = transformer_geographic.transform(pt.x, pt.y)
            lons.append(lon)
            lats.append(lat)

    dest_gdf["latitude_raw"] = lats
    dest_gdf["longitude_raw"] = lons
    dest_gdf["original_geometry"] = gdf.geometry.apply(lambda g: g.wkt if g else None)

    dest_gdf = add_provenance_fields(
        dest_gdf,
        "mechanized_pothole_repairs",
        filename,
        "GPKG",
        year,
        gpkg_rules["crs_status"],
        gpkg_rules["declared_source_crs"],
        working_crs,
        version,
    )

    dest_gdf = map_canonical_columns(
        dest_gdf,
        gpkg_rules["field_mapping"],
        keep_additional_fields=[
            "event_timestamp",
            "event_date_raw",
            "event_time_raw",
            "latitude_raw",
            "longitude_raw",
            "event_timestamp_raw",
            "event_timestamp_naive",
        ],
    )
    dest_gdf = _compute_pothole_flags(dest_gdf, year)

    # Write GeoParquet
    out_path = os.path.join(PROJECT_ROOT, rules["interim_path_pattern"].format(YEAR=year))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_geoparquet(dest_gdf, out_path)

    verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

    return dest_gdf, qa_results


def _compute_pavement_flags(df):
    """Compute duplicate and sentinel flags for pavement campaigns."""
    df["candidate_missing_sentinel_flag"] = (
        ((df["iri_raw"] == 0.0) | (df["iri_raw"] == 0))
        & (df["etat_iri_raw"].astype(str).str.strip() == "-")
    ).astype(int)

    df["duplicate_candidate_flag"] = df.duplicated(
        subset=["source_segment_id"], keep="first"
    ).astype(int)
    return df


def process_pavement_condition(rules, year_str, working_crs, version, admin_bbox):
    """Load, reproject, and canonicalize a single Pavement Condition Campaign."""
    camp_rules = rules["campaigns"][year_str]
    filename = camp_rules["filename"]
    raw_path = os.path.join(PROJECT_ROOT, rules["raw_path_pattern"], filename)
    print(f"Processing Pavement Campaign {year_str}: {raw_path}")

    has_geom = camp_rules["has_geometry"]

    if not has_geom:
        df = load_csv(raw_path)
        df = _normalize_df_columns(df)
        df["etat_iri_raw"] = df["Etat_IRI"] if "Etat_IRI" in df.columns else ""

        df = add_provenance_fields(
            df,
            "pavement_condition",
            filename,
            "CSV",
            f"Campaign {year_str}",
            camp_rules["crs_status"],
            camp_rules["source_crs"],
            working_crs,
            version,
        )

        df = map_canonical_columns(
            df, camp_rules["field_mapping"], keep_additional_fields=["etat_iri_raw"]
        )
        df = _compute_pavement_flags(df)

        out_path = os.path.join(PROJECT_ROOT, rules["interim_path_pattern"].format(YEAR=year_str))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        write_parquet(df, out_path)
        verify_parquet_roundtrip(out_path, df, is_spatial=False)

        qa_results = {
            "source_row_count": len(df),
            "destination_row_count": len(df),
            "source_geometry_types": {"None": len(df)},
            "destination_geometry_types": {"None": len(df)},
            "warnings": "No geometry in campaign",
        }
        return df, qa_results

    else:
        if filename.endswith(".json") or filename.endswith(".geojson"):
            gdf = load_geojson(raw_path)
        else:
            gdf = load_gpkg_layer(raw_path)

        gdf = _normalize_df_columns(gdf)

        gdf.crs = camp_rules["source_crs"]
        dest_gdf = reproject_gdf(gdf, working_crs)

        # Run QA
        qa_results = perform_spatial_qa(
            gdf, dest_gdf, admin_bbox, camp_rules["source_crs"], working_crs
        )

        dest_gdf["original_geometry"] = gdf.geometry.apply(lambda g: g.wkt if g else None)
        dest_gdf["etat_iri_raw"] = dest_gdf["Etat_IRI"] if "Etat_IRI" in dest_gdf.columns else ""

        dest_gdf = add_provenance_fields(
            dest_gdf,
            "pavement_condition",
            filename,
            filename.split(".")[-1].upper(),
            f"Campaign {year_str}",
            camp_rules["crs_status"],
            camp_rules["source_crs"],
            working_crs,
            version,
        )

        dest_gdf = map_canonical_columns(
            dest_gdf, camp_rules["field_mapping"], keep_additional_fields=["etat_iri_raw"]
        )
        dest_gdf = _compute_pavement_flags(dest_gdf)

        out_path = os.path.join(PROJECT_ROOT, rules["interim_path_pattern"].format(YEAR=year_str))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        write_geoparquet(dest_gdf, out_path)
        verify_parquet_roundtrip(out_path, dest_gdf, is_spatial=True)

        return dest_gdf, qa_results


def _run_dataset_pipelines(datasets_to_run, config, working_crs, version, pipeline_qa):
    """Run all dataset preprocessing pipelines in order."""
    # A. Administrative Boundaries (First to get bounding box for containment check)
    admin_gdf = None
    admin_bbox = None
    if "borough_boundaries" in datasets_to_run:
        rules = config["dataset_rules"]["borough_boundaries"]
        admin_gdf, qa = process_borough_boundaries(rules, working_crs, version)
        pipeline_qa["borough_boundaries"] = qa
        admin_bbox = tuple(admin_gdf.total_bounds)
        print(f"Administrative boundaries bounding box: {admin_bbox}")

    # B. Géobase
    if "geobase" in datasets_to_run:
        rules = config["dataset_rules"]["geobase"]
        _, qa = process_geobase(rules, working_crs, version, admin_bbox)
        pipeline_qa["geobase"] = qa

    # C. Road Assets
    if "road_assets_pavement" in datasets_to_run:
        rules = config["dataset_rules"]["road_assets_pavement"]
        _, qa = process_road_assets(rules, working_crs, version, admin_bbox)
        pipeline_qa["road_assets_pavement"] = qa

    # D. Potholes Repairs
    if "pothole_repairs" in datasets_to_run:
        rules = config["dataset_rules"]["pothole_repairs"]
        pipeline_qa["pothole_repairs"] = {}
        for yr in [int(y) for y in rules["csv_sources"].keys()]:
            _, qa = process_potholes_csv(rules, yr, working_crs, version, admin_bbox)
            pipeline_qa["pothole_repairs"][str(yr)] = qa
        _, qa2021 = process_potholes_2021(rules, working_crs, version, admin_bbox)
        pipeline_qa["pothole_repairs"]["2021"] = qa2021
        for yr in rules["gpkg_projected"]["years"]:
            _, qa = process_potholes_projected(rules, yr, working_crs, version, admin_bbox)
            pipeline_qa["pothole_repairs"][str(yr)] = qa

    # E. Pavement Condition
    if "pavement_condition" in datasets_to_run:
        rules = config["dataset_rules"]["pavement_condition"]
        pipeline_qa["pavement_condition"] = {}
        for yr_str in rules["campaigns"].keys():
            _, qa = process_pavement_condition(rules, yr_str, working_crs, version, admin_bbox)
            pipeline_qa["pavement_condition"][yr_str] = qa


def main():  # noqa: C901
    """Main execution block."""
    parser = argparse.ArgumentParser(
        description="Phase 3A Spatial Preprocessing Integration Pipeline"
    )
    parser.add_argument(
        "--config",
        default="config/spatial_preprocessing.json",
        help="Path to preprocessing JSON config",
    )
    parser.add_argument("--dataset", help="Comma-separated datasets to process")
    parser.add_argument("--force", action="store_true", help="Force overwrite files")
    parser.add_argument(
        "--validate-only", action="store_true", help="Perform integrity preflight checks only"
    )
    args = parser.parse_args()

    config_path = os.path.join(PROJECT_ROOT, args.config)
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    version = config["version"]
    working_crs = config["approved_working_crs"]

    print(f"Loaded config version {version} targeting working CRS: {working_crs}")

    # 1. Integrity check preflight
    evidence_path = os.path.join(PROJECT_ROOT, "outputs", "evidence", "phase_3a")
    os.makedirs(evidence_path, exist_ok=True)
    before_inventory = scan_raw_files(RAW_DIR, PROJECT_ROOT)

    before_json_path = os.path.join(evidence_path, "raw_immutability_before.json")
    with open(before_json_path, "w", encoding="utf-8") as f:
        json.dump(before_inventory, f, indent=2)

    print(f"Pre-run raw immutability snapshot created at {before_json_path}")

    if args.validate_only:
        print("Preflight validation complete (--validate-only). Exiting.")
        sys.exit(0)

    datasets_to_run = [
        "geobase",
        "borough_boundaries",
        "road_assets_pavement",
        "pothole_repairs",
        "pavement_condition",
    ]
    if args.dataset:
        datasets_to_run = [d.strip() for d in args.dataset.split(",")]

    pipeline_qa = {}
    _run_dataset_pipelines(datasets_to_run, config, working_crs, version, pipeline_qa)

    # Save Pipeline QA results to ignored evidence folder
    qa_report_path = os.path.join(evidence_path, "pipeline_qa_results.json")
    with open(qa_report_path, "w", encoding="utf-8") as f:
        json.dump(pipeline_qa, f, indent=2)

    print(f"Preprocessing Pipeline QA results compiled at {qa_report_path}")

    # 2. Immutability verification postflight
    after_inventory = scan_raw_files(RAW_DIR, PROJECT_ROOT)
    after_json_path = os.path.join(evidence_path, "raw_immutability_after.json")
    with open(after_json_path, "w", encoding="utf-8") as f:
        json.dump(after_inventory, f, indent=2)

    print(f"Post-run raw immutability snapshot created at {after_json_path}")

    # Assert completely unchanged
    before_map = {
        item["relative_path"]: (item["size_bytes"], item["sha256"]) for item in before_inventory
    }
    for item in after_inventory:
        path = item["relative_path"]
        assert path in before_map, f"Prohibited raw file added: {path}"
        assert before_map[path] == (item["size_bytes"], item["sha256"]), (
            f"Prohibited raw file modification: {path}"
        )

    print("Verification complete: Raw files remain completely unchanged.")

    # Create the run manifest
    run_manifest = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "config_version": version,
        "working_crs": working_crs,
        "raw_immutability_before_sha256": before_inventory[0]["sha256"] if before_inventory else "",
        "datasets_processed": datasets_to_run,
        "status": "success",
    }

    manifest_out = os.path.join(INTERIM_DIR, "phase_3a", "manifests", "preprocessing_manifest.json")
    os.makedirs(os.path.dirname(manifest_out), exist_ok=True)
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2)

    print(f"Run manifest generated at {manifest_out}")


if __name__ == "__main__":
    main()
