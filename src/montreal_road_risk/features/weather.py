import os

import numpy as np
import pandas as pd


def build_weather_features(config, project_root, panel_df):  # noqa: C901
    """
    Computes rolling weather window aggregates relative to each panel row's as_of_date.
    """
    weather_path = os.path.join(project_root, config["inputs"]["weather"])
    print(f"Loading canonical daily weather from: {weather_path}")
    weather_df = pd.read_parquet(weather_path)

    # Ensure index is datetime
    weather_df["date"] = pd.to_datetime(weather_df["date"])
    weather_df = weather_df.set_index("date").sort_index()

    # Check column names in daily weather
    # In Phase 3C weather_daily_canonical: columns could be lowercase or containing spaces.
    # Let's inspect columns or print them in build pipeline.
    # We can write a flexible dictionary mapper to handle slight naming changes.
    cols = list(weather_df.columns)
    print("Daily weather columns:", cols)

    # Maps config names to actual columns
    col_map = {}
    for c in cols:
        c_lower = c.lower().replace("_", " ")
        if "mean temp" in c_lower:
            col_map["mean_temp"] = c
        elif "min temp" in c_lower:
            col_map["min_temp"] = c
        elif "max temp" in c_lower:
            col_map["max_temp"] = c
        elif "total precip" in c_lower:
            col_map["total_precip"] = c
        elif "mean temp fallback used" in c_lower:
            col_map["mean_temp_fb"] = c
        elif "min temp fallback used" in c_lower:
            col_map["min_temp_fb"] = c
        elif "max temp fallback used" in c_lower:
            col_map["max_temp_fb"] = c
        elif "total precip fallback used" in c_lower:
            col_map["total_precip_fb"] = c

    mean_col_act = col_map.get("mean_temp", "Mean Temp (°C)")
    min_col_act = col_map.get("min_temp", "Min Temp (°C)")
    max_col_act = col_map.get("max_temp", "Max Temp (°C)")
    precip_col_act = col_map.get("total_precip", "Total Precip (mm)")

    # Cast weather values to float
    weather_df[mean_col_act] = pd.to_numeric(weather_df[mean_col_act], errors="coerce")
    weather_df[min_col_act] = pd.to_numeric(weather_df[min_col_act], errors="coerce")
    weather_df[max_col_act] = pd.to_numeric(weather_df[max_col_act], errors="coerce")
    weather_df[precip_col_act] = pd.to_numeric(weather_df[precip_col_act], errors="coerce")

    # Cast fallback columns to int
    fb_keys = ["mean_temp_fb", "min_temp_fb", "max_temp_fb", "total_precip_fb"]
    for fb_key in fb_keys:
        if fb_key in col_map:
            col_name = col_map[fb_key]
            weather_df[col_name] = pd.to_numeric(weather_df[col_name], errors="coerce").fillna(0).astype(int)

    # Calculate freeze-thaw indicators daily
    # 1. Strict: min_temp < 0 and max_temp > 0
    # 2. Min le zero: min_temp <= 0 and max_temp > 0
    # 3. Max ge zero: min_temp < 0 and max_temp >= 0

    # Indicators
    weather_df["ft_strict"] = ((weather_df[min_col_act] < 0) & (weather_df[max_col_act] > 0)).astype(float)
    weather_df["ft_min_le"] = ((weather_df[min_col_act] <= 0) & (weather_df[max_col_act] > 0)).astype(float)
    weather_df["ft_max_ge"] = ((weather_df[min_col_act] < 0) & (weather_df[max_col_act] >= 0)).astype(float)

    # Null out freeze-thaw indicators if either temperature is null
    null_mask = weather_df[min_col_act].isna() | weather_df[max_col_act].isna()
    weather_df.loc[null_mask, ["ft_strict", "ft_min_le", "ft_max_ge"]] = np.nan

    print("Computing rolling weather aggregates for unique month-end anchors...")
    anchors = panel_df["as_of_date"].unique()

    weather_anchors = []

    for t in anchors:
        t_ts = pd.Timestamp(t)
        anchor_features = {"as_of_date": t_ts}

        for W in config["features"]["weather_rolling_windows"]:
            w_start = t_ts - pd.Timedelta(days=W)

            # Slice weather data for the window (w_start, t_ts]
            window_df = weather_df.loc[w_start + pd.Timedelta(days=1) : t_ts]

            # Calculations
            precip_sum = window_df[precip_col_act].sum(min_count=1) # Returns NaN if all values are NaN
            mean_temp_avg = window_df[mean_col_act].mean()
            min_temp_val = window_df[min_col_act].min()
            max_temp_val = window_df[max_col_act].max()

            ft_strict_sum = window_df["ft_strict"].sum(min_count=1)
            ft_min_le_sum = window_df["ft_min_le"].sum(min_count=1)
            ft_max_ge_sum = window_df["ft_max_ge"].sum(min_count=1)

            # Counts of valid days (exclude NaNs)
            valid_precip = int(window_df[precip_col_act].notna().sum())

            # Coverage ratio and completeness
            cov_ratio = float(valid_precip) / W
            complete_flag = int(cov_ratio == 1.0)

            # Fallback counts inside the window
            mean_fb_cnt = int(window_df[col_map.get("mean_temp_fb", "mean_temp_fallback_used")].sum()) if "mean_temp_fb" in col_map else 0
            min_fb_cnt = int(window_df[col_map.get("min_temp_fb", "min_temp_fallback_used")].sum()) if "min_temp_fb" in col_map else 0
            max_fb_cnt = int(window_df[col_map.get("max_temp_fb", "max_temp_fallback_used")].sum()) if "max_temp_fb" in col_map else 0
            precip_fb_cnt = int(window_df[col_map.get("total_precip_fb", "total_precip_fallback_used")].sum()) if "total_precip_fb" in col_map else 0

            # Assign features
            anchor_features[f"total_precip_sum_{W}d"] = precip_sum
            anchor_features[f"mean_temp_mean_{W}d"] = mean_temp_avg
            anchor_features[f"min_temp_min_{W}d"] = min_temp_val
            anchor_features[f"max_temp_max_{W}d"] = max_temp_val

            anchor_features[f"freeze_thaw_strict_sum_{W}d"] = ft_strict_sum
            anchor_features[f"freeze_thaw_min_le_zero_sum_{W}d"] = ft_min_le_sum
            anchor_features[f"freeze_thaw_max_ge_zero_sum_{W}d"] = ft_max_ge_sum

            anchor_features[f"weather_valid_days_{W}d"] = valid_precip
            anchor_features[f"weather_coverage_ratio_{W}d"] = cov_ratio
            anchor_features[f"weather_complete_{W}d"] = complete_flag

            # Fallback counts
            anchor_features[f"mean_temp_fallback_days_{W}d"] = mean_fb_cnt
            anchor_features[f"min_temp_fallback_days_{W}d"] = min_fb_cnt
            anchor_features[f"max_temp_fallback_days_{W}d"] = max_fb_cnt
            anchor_features[f"total_precip_fallback_days_{W}d"] = precip_fb_cnt

        weather_anchors.append(anchor_features)

    weather_features_df = pd.DataFrame(weather_anchors)

    # Merge back into panel_df using as_of_date
    panel_df = panel_df.merge(weather_features_df, on="as_of_date", how="left")

    # Re-establish segment_month_id as index
    panel_df = panel_df.set_index("segment_month_id", drop=False)

    print(f"Computed weather features for {len(panel_df)} panel rows.")
    return panel_df
