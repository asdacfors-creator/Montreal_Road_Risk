import datetime
import pytest
import numpy as np
import pandas as pd
import geopandas as gpd

from montreal_road_risk.temporal.parsing import (
    parse_date_time,
    classify_precision,
    localize_to_toronto,
    localize_series_to_toronto,
)
from montreal_road_risk.temporal.coverage import (
    calculate_temporal_coverage,
    calculate_right_edge_eligibility,
)
from montreal_road_risk.temporal.weather import (
    standardize_weather_df,
    combine_weather_stations,
)
from montreal_road_risk.temporal.qa import reconcile_temporal_counts


def test_parse_date_time():
    # Precise
    d, t, st = parse_date_time("2023-11-05", "01:30:00")
    assert d == datetime.date(2023, 11, 5)
    assert t == datetime.time(1, 30, 0)
    assert st == "precise"
    assert classify_precision(st) == "precise"

    # Date only
    d, t, st = parse_date_time("2023-11-05", None)
    assert d == datetime.date(2023, 11, 5)
    assert t is None
    assert st == "date_only"
    assert classify_precision(st) == "date_only"

    # Imprecise year
    d, t, st = parse_date_time("Inconnu/1995", None)
    assert d == datetime.date(1995, 1, 1)
    assert t is None
    assert st == "imprecise_year"
    assert classify_precision(st) == "imprecise_year"

    # Missing
    d, t, st = parse_date_time(None, None)
    assert d is None and t is None
    assert st == "missing"
    assert classify_precision(st) == "unknown"


def test_timezone_and_dst_safety():
    # Normal time
    dt = pd.Timestamp("2023-06-15 12:00:00")
    loc_val, status = localize_to_toronto(dt)
    assert status == "successfully_localized"
    assert loc_val.tz is not None
    assert str(loc_val.tz) == "America/Toronto"

    # Ambiguous DST (clocks roll back)
    # 2023-11-05 01:30:00 occurred twice
    ambig_dt = pd.Timestamp("2023-11-05 01:30:00")
    loc_val, status = localize_to_toronto(ambig_dt)
    assert status == "ambiguous_dst"
    assert loc_val.tz is None  # Retains source local time (naive)

    # Nonexistent DST (clocks spring forward)
    # 2023-03-12 02:30:00 never occurred
    nonexist_dt = pd.Timestamp("2023-03-12 02:30:00")
    loc_val, status = localize_to_toronto(nonexist_dt)
    assert status == "nonexistent_dst"
    assert loc_val.tz is None  # Retains source local time (naive)

    # Vectorized test
    s = pd.Series([dt, ambig_dt, nonexist_dt, pd.NaT])
    loc_s, status_s = localize_series_to_toronto(s)
    assert loc_s.iloc[0].tz is not None
    assert loc_s.iloc[1].tz is None
    assert loc_s.iloc[2].tz is None
    assert loc_s.iloc[3] is pd.NaT

    assert status_s.iloc[0] == "successfully_localized"
    assert status_s.iloc[1] == "ambiguous_dst"
    assert status_s.iloc[2] == "nonexistent_dst"
    assert status_s.iloc[3] == "missing"


def test_weather_fallback_allowlist_and_safeguards():
    # Create mock standardized station dataframes
    date_range = pd.date_range("2023-01-01", "2023-01-03").date

    # McTavish: missing min_temp on Jan 2, missing total_precip on Jan 3, min_temp is 0.0 on Jan 1
    df_mct = pd.DataFrame({
        "date": date_range,
        "mean_temp": [5.0, 6.0, 7.0],
        "min_temp": [0.0, np.nan, 2.0],  # 0.0 on Jan 1 must not be treated as missing
        "max_temp": [10.0, 11.0, 12.0],
        "total_precip": [1.0, 2.0, np.nan],
        "total_rain": [0.5, 0.6, np.nan],
        "total_snow": [0.0, 0.0, np.nan],
        "snow_on_ground": [5.0, 5.0, 5.0]
    })

    # Trudeau: has all values
    df_tru = pd.DataFrame({
        "date": date_range,
        "mean_temp": [5.2, 6.2, 7.2],
        "min_temp": [1.1, -1.0, 2.1],
        "max_temp": [10.2, 11.2, 12.2],
        "total_precip": [1.1, 2.1, 3.0],
        "total_rain": [0.6, 0.7, 0.8],
        "total_snow": [0.0, 0.0, 0.0],
        "snow_on_ground": [4.0, 4.0, 4.0]
    })

    allowlist = ["mean_temp", "min_temp", "max_temp", "total_precip"]

    df_canonical = combine_weather_stations(
        df_mct, df_tru, datetime.date(2023, 1, 1), datetime.date(2023, 1, 3), allowlist
    )

    # 1. Zero preservation
    assert df_canonical.loc[0, "min_temp"] == 0.0
    assert df_canonical.loc[0, "min_temp_fallback_used"] == 0
    assert df_canonical.loc[0, "min_temp_source_station_used"] == "MCTAVISH"

    # 2. Allowlisted fallback check (Jan 2 min_temp falls back)
    assert df_canonical.loc[1, "min_temp"] == -1.0
    assert df_canonical.loc[1, "min_temp_fallback_used"] == 1
    assert df_canonical.loc[1, "min_temp_source_station_used"] == "MONTREAL_TRUDEAU"
    assert df_canonical.loc[1, "min_temp_original_mctavish_missing"] == 1

    # 3. Allowlisted fallback check (Jan 3 total_precip falls back)
    assert df_canonical.loc[2, "total_precip"] == 3.0
    assert df_canonical.loc[2, "total_precip_fallback_used"] == 1

    # 4. Excluded fallbacks (Total Rain, Total Snow, Snow on Ground must remain station-specific)
    assert pd.isna(df_canonical.loc[2, "total_rain"])
    assert df_canonical.loc[2, "total_rain_fallback_used"] == 0
    assert df_canonical.loc[2, "total_rain_source_station_used"] == "MCTAVISH"
    assert pd.isna(df_canonical.loc[2, "total_snow"])
    assert df_canonical.loc[2, "total_snow_fallback_used"] == 0

    # Snow on ground must be mctavish only (even if trudeau differs)
    assert df_canonical.loc[0, "snow_on_ground"] == 5.0
    assert df_canonical.loc[0, "snow_on_ground_source_station_used"] == "MCTAVISH"


def test_right_edge_calculations():
    latest_date = "2025-12-31"
    res = calculate_right_edge_eligibility(latest_date)
    assert res["latest_observed_date"] == "2025-12-31"
    # Subtract 90 days: Oct 2, 2025
    assert res["candidate_right_edge_90_days"] == "2025-10-02"
    # Subtract 180 days: Jul 4, 2025
    assert res["candidate_right_edge_180_days"] == "2025-07-04"
    assert "coverage analysis only" in res["note"].lower()


def test_zero_silent_row_loss_reconciliation():
    # Should run successfully
    assert reconcile_temporal_counts(1027267, 121163, 64025, 6209, 6209, 6209)

    # Should raise error on mismatch
    with pytest.raises(AssertionError):
        reconcile_temporal_counts(1027267, 121160, 64025, 6209, 6209, 6209)


def test_source_year_mismatch_and_status(tmp_path):
    # Create a small DataFrame mimicking our potholes data
    df = pd.DataFrame({
        "event_year": [2023, 2022, None, None],
        "source_year": [2023, 2023, 2023, 2023],
        "timestamp_parse_status": ["precise", "precise", "missing", "parse_failure"]
    })

    # Calculate mismatch flags
    mismatch_mask = df["event_year"].notna() & (df["event_year"] != df["source_year"])
    df["source_year_mismatch_flag"] = mismatch_mask.astype(int)

    status = pd.Series("match", index=df.index)
    status[df["timestamp_parse_status"] == "missing"] = "unknown_missing"
    status[df["timestamp_parse_status"] == "parse_failure"] = "unknown_parse_failure"
    status[mismatch_mask] = "mismatch"
    df["source_year_status"] = status

    # Assertions
    assert df.loc[0, "source_year_mismatch_flag"] == 0
    assert df.loc[0, "source_year_status"] == "match"

    assert df.loc[1, "source_year_mismatch_flag"] == 1
    assert df.loc[1, "source_year_status"] == "mismatch"

    assert df.loc[2, "source_year_mismatch_flag"] == 0
    assert df.loc[2, "source_year_status"] == "unknown_missing"

    assert df.loc[3, "source_year_mismatch_flag"] == 0
    assert df.loc[3, "source_year_status"] == "unknown_parse_failure"

    # Test serialization roundtrip
    out_file = tmp_path / "test_serialize.parquet"
    df.to_parquet(out_file)
    df_read = pd.read_parquet(out_file)

    assert list(df_read["source_year_status"]) == ["match", "mismatch", "unknown_missing", "unknown_parse_failure"]
    assert list(df_read["source_year_mismatch_flag"]) == [0, 1, 0, 0]


def test_potholes_total_row_count():
    # If file exists, check total row count
    parquet_path = "data/interim/phase_3c/pothole_events_temporal.parquet"
    import os
    if os.path.exists(parquet_path):
        df = pd.read_parquet(parquet_path)
        assert len(df) == 1027267
        # Mixed format parser successfully parses all populated timestamps
        assert (df["timestamp_parse_status"] == "parse_failure").sum() == 0
        assert (df["source_year_status"] == "match").sum() == 1027262
        assert (df["source_year_status"] == "mismatch").sum() == 5
        # Original raw timestamp matches round-trip
        assert df["event_timestamp_raw"].isna().sum() == 0


def test_regression_timestamp_preservation_and_road_asset_precision(tmp_path):
    # 1. Original raw timestamp string survives roundtrip Parquet serialization unchanged
    df_raw = pd.DataFrame({
        "event_timestamp_raw": ["2021-03-24T10:14:05.123456", "2023-11-07 12:38:43.063", "2025-05-20T00:00:00"]
    })
    temp_p = tmp_path / "test_raw_ts.parquet"
    df_raw.to_parquet(temp_p)
    df_read = pd.read_parquet(temp_p)
    assert list(df_read["event_timestamp_raw"]) == ["2021-03-24T10:14:05.123456", "2023-11-07 12:38:43.063", "2025-05-20T00:00:00"]

    # 2. Audited GPKG datetime strings parse successfully
    from scripts.preprocess_spatial_base import _extract_pothole_datetime_fields
    df_test_gpkg = pd.DataFrame({
        "Date": ["2021-03-24T10:14:05.123456", "2023-11-07 12:38:43.063000", "2025-05-20T00:00:00"]
    })
    res_gpkg = _extract_pothole_datetime_fields(df_test_gpkg, is_gpkg=True)
    assert res_gpkg["event_timestamp_naive"].isna().sum() == 0
    assert list(res_gpkg["event_date_raw"]) == ["2021-03-24", "2023-11-07", "2025-05-20"]
    assert list(res_gpkg["event_time_raw"]) == ["10:14:05.123456", "12:38:43.063000", "00:00:00"]

    # 3. DST ambiguity is separate from parsing status
    from scripts.preprocess_temporal_data import localize_series_to_toronto
    ambig_dt = pd.Series([pd.Timestamp("2023-11-05 01:30:00")])  # ambiguous local time
    _, loc_status = localize_series_to_toronto(ambig_dt)
    assert loc_status.iloc[0] == "ambiguous_dst"


