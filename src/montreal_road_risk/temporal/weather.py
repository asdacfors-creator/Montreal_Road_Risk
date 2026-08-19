import numpy as np
import pandas as pd


def standardize_weather_df(df, station_label):
    """
    Standardize raw ECCC daily weather DataFrame columns and data types.
    """
    # Map raw headers
    col_mapping = {
        "Date/Time": "date",
        "Station Name": "raw_station_name",
        "Climate ID": "raw_climate_id",
        "Mean Temp (°C)": "mean_temp",
        "Min Temp (°C)": "min_temp",
        "Max Temp (°C)": "max_temp",
        "Total Precip (mm)": "total_precip",
        "Total Rain (mm)": "total_rain",
        "Total Snow (cm)": "total_snow",
        "Snow on Grnd (cm)": "snow_on_ground"
    }

    # Rename existing columns
    df_clean = df.rename(columns=col_mapping).copy()

    # Required columns
    req_cols = [
        "date", "mean_temp", "min_temp", "max_temp",
        "total_precip", "total_rain", "total_snow", "snow_on_ground"
    ]
    for col in req_cols:
        if col not in df_clean.columns:
            df_clean[col] = np.nan

    # Parse dates
    df_clean["date"] = pd.to_datetime(df_clean["date"]).dt.date

    # Standardize numeric values (coerce to float, preserve 0.0, do not treat 0.0 as missing)
    num_cols = ["mean_temp", "min_temp", "max_temp", "total_precip", "total_rain", "total_snow", "snow_on_ground"]
    for col in num_cols:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").astype(float)

    # Keep only standardized fields and add label
    df_clean = df_clean[["date"] + num_cols].copy()
    df_clean["station_label"] = station_label
    return df_clean


def combine_weather_stations(df_mctavish, df_trudeau, start_date, end_date, allowlist_vars):
    """
    Combine McTavish and Montreal-Trudeau datasets daily from start_date to end_date.
    Applies same-day fallback only for variables in allowlist_vars.
    """
    # Create complete daily index
    date_idx = pd.date_range(start=start_date, end=end_date, freq="D").date
    df_canonical = pd.DataFrame({"date": date_idx})

    # Set index for fast joins
    df_m = df_mctavish.set_index("date")
    df_t = df_trudeau.set_index("date")

    # Target variables
    vars_all = ["mean_temp", "min_temp", "max_temp", "total_precip", "total_rain", "total_snow", "snow_on_ground"]

    # Map output fields
    for var in vars_all:
        primary_vals = []
        fallback_used_flags = []
        mctavish_missing_flags = []
        source_stations = []

        is_fallback_allowed = var in allowlist_vars

        for dt in date_idx:
            # McTavish value
            m_val = df_m.loc[dt, var] if dt in df_m.index else np.nan
            t_val = df_t.loc[dt, var] if dt in df_t.index else np.nan

            if not pd.isna(m_val):
                primary_vals.append(m_val)
                fallback_used_flags.append(0)
                mctavish_missing_flags.append(0)
                source_stations.append("MCTAVISH")
            elif is_fallback_allowed and not pd.isna(t_val):
                primary_vals.append(t_val)
                fallback_used_flags.append(1)
                mctavish_missing_flags.append(1)
                source_stations.append("MONTREAL_TRUDEAU")
            else:
                primary_vals.append(np.nan)
                fallback_used_flags.append(0)
                mctavish_missing_flags.append(1)
                source_stations.append("MCTAVISH")

        df_canonical[var] = primary_vals
        df_canonical[f"{var}_fallback_used"] = fallback_used_flags
        df_canonical[f"{var}_original_mctavish_missing"] = mctavish_missing_flags
        df_canonical[f"{var}_source_station_used"] = source_stations

    return df_canonical
