#!/usr/bin/env python3
"""Phase 3C Temporal Preprocessing Integration Script.

Performs temporal normalization across all datasets, implements timezone localization,
ECCC weather allowlist same-day fallback, and dataset coverage calculations.
"""

import datetime
import json
import os
import sys

import geopandas as gpd
import pandas as pd

# Import custom packages
from montreal_road_risk.io.checksums import scan_raw_files
from montreal_road_risk.temporal.coverage import (
    calculate_right_edge_eligibility,
    calculate_temporal_coverage,
)
from montreal_road_risk.temporal.parsing import (
    classify_precision,
    localize_series_to_toronto,
    parse_date_time,
)
from montreal_road_risk.temporal.qa import (
    reconcile_temporal_counts,
    verify_raw_immutability,
)
from montreal_road_risk.temporal.weather import (
    combine_weather_stations,
    standardize_weather_df,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "temporal_preprocessing.json")
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "outputs", "evidence", "phase_3c")


def _process_potholes_temporal(config, config_version, qa_summary):
    print("Normalizing pothole repairs temporal data...")
    potholes_pattern = config["inputs"]["potholes_pattern"]
    pothole_years = config["inputs"]["potholes_years"]
    potholes_links_path = os.path.join(PROJECT_ROOT, config["inputs"]["potholes_links"])

    combined_links = pd.read_parquet(potholes_links_path)

    # Load and concatenate Phase 3A preprocessed potholes in year order
    dfs_3a = []
    for yr in pothole_years:
        fpath = os.path.join(PROJECT_ROOT, potholes_pattern.format(YEAR=yr))
        df_yr = pd.read_parquet(fpath)
        dfs_3a.append(df_yr)
    combined_3a = pd.concat(dfs_3a, ignore_index=True)

    # Assert row alignment
    assert len(combined_links) == len(combined_3a), "Potholes row count mismatch between links and 3A"
    assert (combined_links["source_year"] == combined_3a["source_year"]).all(), "Potholes source_year mismatch"
    assert (combined_links["source_row_number"] == combined_3a["source_record_number"]).all(), "Potholes row number mismatch"

    # Merge columns
    cols_to_use = [
        "event_date_raw",
        "event_time_raw",
        "event_timestamp_raw",
        "event_timestamp_naive",
        "out_of_source_year_flag",
        "exact_duplicate_candidate_flag",
        "spatial_temporal_duplicate_candidate_flag"
    ]
    potholes_df = pd.concat([combined_links, combined_3a[cols_to_use]], axis=1)

    # Localize timestamps (vectorized) using event_timestamp_naive
    localized, loc_status = localize_series_to_toronto(potholes_df["event_timestamp_naive"])

    potholes_df["event_date"] = potholes_df["event_timestamp_naive"].dt.date
    potholes_df["event_time"] = potholes_df["event_timestamp_naive"].dt.time
    potholes_df["event_timestamp_local"] = localized
    potholes_df["event_timestamp_localized"] = localized
    potholes_df["event_year"] = potholes_df["event_timestamp_naive"].dt.year
    potholes_df["event_month"] = potholes_df["event_timestamp_naive"].dt.month
    potholes_df["event_month_start"] = pd.to_datetime(potholes_df["event_timestamp_naive"].dt.to_period("M").dt.start_time).dt.date

    # Determine parse status
    is_null = potholes_df["event_timestamp_naive"].isna()
    is_raw_not_null = potholes_df["event_timestamp_raw"].notna() & (potholes_df["event_timestamp_raw"].str.strip() != "") & (potholes_df["event_timestamp_raw"].str.strip().str.lower() != "nan")
    parse_status = pd.Series("precise", index=potholes_df.index)
    parse_status[is_null] = "missing"
    parse_status[is_null & is_raw_not_null] = "parse_failure"

    potholes_df["timestamp_parse_status"] = parse_status
    potholes_df["timestamp_precision"] = parse_status.apply(classify_precision)
    potholes_df["timezone_assumption"] = "America/Toronto"
    potholes_df["timezone_localization_status"] = loc_status

    # Recalculate source year mismatch
    mismatch_mask = potholes_df["event_year"].notna() & (potholes_df["event_year"] != potholes_df["source_year"])
    potholes_df["source_year_mismatch_flag"] = mismatch_mask.astype(int)

    # Add source_year_status category
    source_year_status = pd.Series("match", index=potholes_df.index)
    source_year_status[potholes_df["timestamp_parse_status"] == "missing"] = "unknown_missing"
    source_year_status[potholes_df["timestamp_parse_status"] == "parse_failure"] = "unknown_parse_failure"
    source_year_status[mismatch_mask] = "mismatch"
    potholes_df["source_year_status"] = source_year_status

    # Save to parquet
    out_path = os.path.join(PROJECT_ROOT, config["outputs"]["pothole_temporal"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    potholes_df.to_parquet(out_path)

    # Compile QA stats
    tot = len(potholes_df)
    qa_summary["potholes"] = {
        "total_records": tot,
        "successfully_localized": int((loc_status == "successfully_localized").sum()),
        "ambiguous_dst": int((loc_status == "ambiguous_dst").sum()),
        "nonexistent_dst": int((loc_status == "nonexistent_dst").sum()),
        "missing_timestamp": int((potholes_df["timestamp_parse_status"] == "missing").sum()),
        "parse_failure": int((potholes_df["timestamp_parse_status"] == "parse_failure").sum()),
        "source_year_mismatch": int(potholes_df["source_year_mismatch_flag"].sum()),
    }
    return potholes_df


def _process_pavement_temporal(config, config_version, qa_summary):
    print("Normalizing pavement condition campaign temporal data...")
    pavement_links_path = os.path.join(PROJECT_ROOT, config["inputs"]["pavement_links"])
    pavement_df = gpd.read_parquet(pavement_links_path)

    dates_parsed = []
    times_parsed = []
    parse_statuses = []

    for val in pavement_df["survey_date_raw"]:
        d, t, st = parse_date_time(val)
        dates_parsed.append(d)
        times_parsed.append(t)
        parse_statuses.append(st)

    pavement_df["survey_date"] = dates_parsed
    pavement_df["survey_time"] = times_parsed
    pavement_df["survey_date_parse_status"] = parse_statuses
    pavement_df["survey_date_precision"] = [classify_precision(st) for st in parse_statuses]

    # Timezone localization components
    dt_list = []
    for d, t in zip(dates_parsed, times_parsed, strict=True):
        if d is not None:
            dt_list.append(datetime.datetime.combine(d, t or datetime.time(0, 0)))
        else:
            dt_list.append(pd.NaT)

    dt_series = pd.Series(dt_list)
    localized, loc_status = localize_series_to_toronto(dt_series)

    pavement_df["survey_year"] = [d.year if d is not None else None for d in dates_parsed]
    pavement_df["survey_month"] = [d.month if d is not None else None for d in dates_parsed]
    pavement_df["survey_month_start"] = [datetime.date(d.year, d.month, 1) if d is not None else None for d in dates_parsed]
    pavement_df["survey_timestamp_local"] = localized
    pavement_df["timezone_assumption"] = "America/Toronto"
    pavement_df["timezone_localization_status"] = loc_status

    out_path = os.path.join(PROJECT_ROOT, config["outputs"]["pavement_temporal"])
    # Pavement contains geometry, so write as GeoDataFrame to preserve spatial fields
    pavement_gdf = gpd.GeoDataFrame(pavement_df, geometry="geometry", crs=pavement_df.crs if hasattr(pavement_df, "crs") else None)
    pavement_gdf.to_parquet(out_path)

    tot = len(pavement_df)
    qa_summary["pavement_condition"] = {
        "total_records": tot,
        "successfully_localized": int((loc_status == "successfully_localized").sum()),
        "ambiguous_dst": int((loc_status == "ambiguous_dst").sum()),
        "nonexistent_dst": int((loc_status == "nonexistent_dst").sum()),
        "missing_timestamp": int((loc_status == "missing").sum()),
        "parse_failure": int((loc_status == "parse_failure").sum()),
    }
    return pavement_df


def _process_assets_temporal(config, config_version, qa_summary):
    print("Normalizing road assets temporal uncertainty attributes...")
    assets_3a_path = os.path.join(PROJECT_ROOT, config["inputs"]["road_assets"])

    preprocessed_assets = gpd.read_parquet(assets_3a_path)

    road_assets_df = preprocessed_assets.copy()
    road_assets_df["timezone_assumption"] = "America/Toronto"

    out_path = os.path.join(PROJECT_ROOT, config["outputs"]["road_assets_temporal"])
    road_assets_df.to_parquet(out_path)

    tot = len(road_assets_df)
    c_prec = road_assets_df["construction_date_precision"].value_counts().to_dict()
    r_prec = road_assets_df["resurfacing_date_precision"].value_counts().to_dict()

    qa_summary["road_assets"] = {
        "total_records": tot,
        "construction_date_precision_counts": {k: int(v) for k, v in c_prec.items()},
        "resurfacing_date_precision_counts": {k: int(v) for k, v in r_prec.items()},
        "resurfacing_before_construction_count": int((road_assets_df["resurfacing_before_construction_candidate_flag"] == 1).sum()),
    }
    return road_assets_df


def _process_weather_temporal(config, config_version, qa_summary):
    print("Processing weather datasets daily temporal fallbacks...")
    raw_dir = os.path.join(PROJECT_ROOT, config["inputs"]["weather"]["raw_dir"])
    stations_config = config["inputs"]["weather"]["stations"]
    weather_years = config["inputs"]["weather"]["years"]
    allowlist_vars = config["inputs"]["weather"]["variable_allowlist"]
    # Defensive normalization of allowlisted names (handling both raw and standardized names)
    name_map = {
        "Mean Temp (°C)": "mean_temp",
        "Min Temp (°C)": "min_temp",
        "Max Temp (°C)": "max_temp",
        "Total Precip (mm)": "total_precip",
        "Mean Temp": "mean_temp",
        "Min Temp": "min_temp",
        "Max Temp": "max_temp",
        "Total Precip": "total_precip"
    }
    allowlist_vars = [name_map.get(v, v.lower().replace(" (°c)", "").replace(" (mm)", "").replace(" ", "_")) for v in allowlist_vars]

    # Load McTavish
    mctavish_dfs = []
    mct_sid = stations_config["mctavish"]["station_id"]
    for yr in weather_years:
        fname = f"en_climate_daily_QC_{mct_sid}_{yr}_P1D.csv"
        fpath = os.path.join(raw_dir, "mctavish", fname)
        mctavish_dfs.append(pd.read_csv(fpath))
    mctavish_raw = pd.concat(mctavish_dfs, ignore_index=True)
    df_mctavish_std = standardize_weather_df(mctavish_raw, "MCTAVISH")

    # Load Trudeau
    trudeau_dfs = []
    tru_sid = stations_config["montreal_trudeau"]["station_id"]
    for yr in weather_years:
        fname = f"en_climate_daily_QC_{tru_sid}_{yr}_P1D.csv"
        fpath = os.path.join(raw_dir, "montreal_trudeau", fname)
        trudeau_dfs.append(pd.read_csv(fpath))
    trudeau_raw = pd.concat(trudeau_dfs, ignore_index=True)
    df_trudeau_std = standardize_weather_df(trudeau_raw, "MONTREAL_TRUDEAU")

    # Assert row sizes
    assert len(df_mctavish_std) == 6209, f"McTavish rows expected 6209, got {len(df_mctavish_std)}"
    assert len(df_trudeau_std) == 6209, f"Trudeau rows expected 6209, got {len(df_trudeau_std)}"

    # Save stations daily
    weather_station_daily = pd.concat([df_mctavish_std, df_trudeau_std], ignore_index=True)
    station_daily_out = os.path.join(PROJECT_ROOT, config["outputs"]["weather_station_daily"])
    weather_station_daily.to_parquet(station_daily_out)

    # Combine with allowlist same-day fallback
    df_canonical = combine_weather_stations(
        df_mctavish_std,
        df_trudeau_std,
        datetime.date(2009, 1, 1),
        datetime.date(2025, 12, 31),
        allowlist_vars,
    )

    canonical_out = os.path.join(PROJECT_ROOT, config["outputs"]["weather_daily_canonical"])
    df_canonical.to_parquet(canonical_out)

    # Compile fallback stats
    qa_summary["weather"] = {
        "mctavish_records": len(df_mctavish_std),
        "trudeau_records": len(df_trudeau_std),
        "canonical_records": len(df_canonical),
    }

    # Add fallback counts per variable
    for var in ["mean_temp", "min_temp", "max_temp", "total_precip"]:
        qa_summary["weather"][f"{var}_fallback_used_count"] = int(df_canonical[f"{var}_fallback_used"].sum())
        qa_summary["weather"][f"{var}_original_mctavish_missing_count"] = int(df_canonical[f"{var}_original_mctavish_missing"].sum())

    return weather_station_daily, df_canonical


def _generate_coverage_report(config, potholes, pavement, assets, weather, qa_summary):
    print("Generating temporal coverage report...")

    # Calculate coverage metrics for each dataset
    potholes_cov = calculate_temporal_coverage(potholes, "event_date", "timestamp_parse_status")
    pavement_cov = calculate_temporal_coverage(pavement, "survey_date", "survey_date_parse_status")

    # Weather is canonical
    weather_cov = calculate_temporal_coverage(weather, "date", "date")
    weather_cov["parse_failure_count"] = 0

    # Assets coverage (based on construction dates)
    dates = pd.to_datetime(assets["construction_date_lower_bound"], errors="coerce").dropna()
    earliest_date = dates.min().date().isoformat() if not dates.empty else None
    latest_date = dates.max().date().isoformat() if not dates.empty else None

    tot_assets = len(assets)
    missing_count = int((assets["construction_date_precision"] == "missing").sum())
    unknown_count = int((assets["construction_date_precision"] == "unknown").sum())
    approximate_count = int((assets["construction_date_precision"] == "approximate_interval").sum())
    year_only_count = int((assets["construction_date_precision"] == "imprecise_year").sum())
    precise_count = int((assets["construction_date_precision"] == "precise").sum())

    assets_cov = {
        "total_records": tot_assets,
        "earliest_observed_date": earliest_date,
        "latest_observed_date": latest_date,
        "missing_date_count": missing_count,
        "unknown_date_count": unknown_count,
        "approximate_date_count": approximate_count,
        "year_only_date_count": year_only_count,
        "precise_date_count": precise_count,
        "distinct_repeated_dates": int(len(dates.value_counts()[dates.value_counts() > 1])),
        "rows_in_repeated_dates": int(dates.value_counts()[dates.value_counts() > 1].sum()) if not dates.empty else 0,
        "excess_rows_repeated_dates": int(dates.value_counts()[dates.value_counts() > 1].sum() - len(dates.value_counts()[dates.value_counts() > 1])) if not dates.empty else 0,
    }

    # Build coverage table DataFrame
    datasets_cov = [
        {"dataset": "pothole_repairs", **potholes_cov},
        {"dataset": "pavement_condition", **pavement_cov},
        {"dataset": "road_assets", **assets_cov},
        {"dataset": "weather_daily", **weather_cov}
    ]
    df_cov = pd.DataFrame(datasets_cov)

    # Right-edge target eligibility horizon analysis (coverage analysis only)
    latest_potholes = potholes_cov["latest_observed_date"]
    latest_pavement = pavement_cov["latest_observed_date"]
    latest_weather = weather_cov["latest_observed_date"]

    right_edges = {
        "potholes": calculate_right_edge_eligibility(latest_potholes),
        "pavement_condition": calculate_right_edge_eligibility(latest_pavement),
        "weather": calculate_right_edge_eligibility(latest_weather)
    }

    qa_summary["temporal_coverage"] = {
        "datasets": datasets_cov,
        "right_edge_target_eligibility": right_edges
    }

    out_path = os.path.join(PROJECT_ROOT, config["outputs"]["dataset_temporal_coverage"])
    df_cov.to_parquet(out_path)
    return df_cov


def _verify_roundtrip(config, potholes, pavement, assets, weather_station, weather_canonical, coverage):
    print("Verifying serialization roundtrip read-back...")

    # Read-back and check row count & column equality
    r_potholes = pd.read_parquet(os.path.join(PROJECT_ROOT, config["outputs"]["pothole_temporal"]))
    assert len(r_potholes) == len(potholes), "Potholes size mismatch"
    assert list(r_potholes.columns) == list(potholes.columns), "Potholes schema mismatch"

    r_pavement = gpd.read_parquet(os.path.join(PROJECT_ROOT, config["outputs"]["pavement_temporal"]))
    assert len(r_pavement) == len(pavement), "Pavement size mismatch"
    assert list(r_pavement.columns) == list(pavement.columns), "Pavement schema mismatch"

    r_assets = gpd.read_parquet(os.path.join(PROJECT_ROOT, config["outputs"]["road_assets_temporal"]))
    assert len(r_assets) == len(assets), "Assets size mismatch"
    assert list(r_assets.columns) == list(assets.columns), "Assets schema mismatch"

    r_weather_station = pd.read_parquet(os.path.join(PROJECT_ROOT, config["outputs"]["weather_station_daily"]))
    assert len(r_weather_station) == len(weather_station), "Weather station daily size mismatch"
    assert list(r_weather_station.columns) == list(weather_station.columns), "Weather station daily schema mismatch"

    r_weather_canonical = pd.read_parquet(os.path.join(PROJECT_ROOT, config["outputs"]["weather_daily_canonical"]))
    assert len(r_weather_canonical) == len(weather_canonical), "Weather canonical size mismatch"
    assert list(r_weather_canonical.columns) == list(weather_canonical.columns), "Weather canonical schema mismatch"

    r_coverage = pd.read_parquet(os.path.join(PROJECT_ROOT, config["outputs"]["dataset_temporal_coverage"]))
    assert len(r_coverage) == len(coverage), "Coverage size mismatch"
    assert list(r_coverage.columns) == list(coverage.columns), "Coverage schema mismatch"


def main():  # noqa: C901
    print("Initializing Phase 3C temporal normalization pipeline...")

    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    config_version = config["version"]
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # 1. Raw file immutability pre-run snapshot
    print("Scanning raw files for pre-run integrity snapshot...")
    pre_inventory = scan_raw_files(RAW_DIR, PROJECT_ROOT)
    pre_snap_path = os.path.join(EVIDENCE_DIR, "raw_immutability_before.json")
    with open(pre_snap_path, "w") as f:
        json.dump(pre_inventory, f, indent=2)

    qa_summary = {
        "config_version": config_version,
        "timezone_assumption": config["timezone_assumption"],
        "potholes": {},
        "pavement_condition": {},
        "road_assets": {},
        "weather": {},
        "temporal_coverage": {}
    }

    # 2. Run normalization steps
    potholes = _process_potholes_temporal(config, config_version, qa_summary)
    pavement = _process_pavement_temporal(config, config_version, qa_summary)
    assets = _process_assets_temporal(config, config_version, qa_summary)
    weather_station, weather_canonical = _process_weather_temporal(config, config_version, qa_summary)
    coverage = _generate_coverage_report(config, potholes, pavement, assets, weather_canonical, qa_summary)

    # 3. Serialization Roundtrip read-back check
    _verify_roundtrip(config, potholes, pavement, assets, weather_station, weather_canonical, coverage)

    # 4. Zero-row-loss reconciliation
    reconcile_temporal_counts(
        len(potholes),
        len(pavement),
        len(assets),
        len(weather_station) // 2,  # McTavish count is half of concatenated daily station rows
        len(weather_station) // 2,  # Trudeau count
        len(weather_canonical)
    )

    # 5. Output QA summary
    qa_summary_path = os.path.join(PROJECT_ROOT, config["outputs"]["qa_summary"])
    with open(qa_summary_path, "w") as f:
        json.dump(qa_summary, f, indent=2)
    print(f"QA Summary exported to {qa_summary_path}")

    # 6. Generate run manifest
    run_manifest = {
        "pipeline": "Phase 3C Temporal Normalization and QA",
        "timestamp": pd.Timestamp.now().isoformat(),
        "config_version": config_version,
        "output_files": {
            "pothole_temporal": os.path.join(PROJECT_ROOT, config["outputs"]["pothole_temporal"]),
            "pavement_temporal": os.path.join(PROJECT_ROOT, config["outputs"]["pavement_temporal"]),
            "road_assets_temporal": os.path.join(PROJECT_ROOT, config["outputs"]["road_assets_temporal"]),
            "weather_station_daily": os.path.join(PROJECT_ROOT, config["outputs"]["weather_station_daily"]),
            "weather_daily_canonical": os.path.join(PROJECT_ROOT, config["outputs"]["weather_daily_canonical"]),
            "dataset_temporal_coverage": os.path.join(PROJECT_ROOT, config["outputs"]["dataset_temporal_coverage"]),
            "qa_summary": qa_summary_path,
        }
    }
    manifest_path = os.path.join(PROJECT_ROOT, config["outputs"]["run_manifest"])
    with open(manifest_path, "w") as f:
        json.dump(run_manifest, f, indent=2)
    print(f"Run manifest generated at {manifest_path}")

    # 7. Raw file immutability post-run check
    print("Checking post-run raw file immutability...")
    is_raw_unchanged, msg = verify_raw_immutability(pre_snap_path)
    print(msg)
    if not is_raw_unchanged:
        sys.exit(1)

    print("Phase 3C temporal preprocessing build completed successfully.")


if __name__ == "__main__":
    main()
