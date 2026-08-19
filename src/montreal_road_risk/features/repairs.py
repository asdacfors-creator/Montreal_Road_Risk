import json
import os

import numpy as np
import pandas as pd


def build_duplicate_collapsed_events(config, project_root):
    """
    Groups raw accepted repair events using native keys and saves:
    - accepted_repair_events_collapsed.parquet
    - duplicate_group_membership.parquet
    - duplicate_sensitivity_summary.json
    """
    raw_path = os.path.join(project_root, config["outputs"]["accepted_repair_events_raw"])
    print(f"Loading raw accepted events from: {raw_path}")
    raw_df = pd.read_parquet(raw_path)

    # 1. Collapse duplicates using audited native keys
    raw_df["vehicle_id_raw"] = raw_df["vehicle_id_raw"].fillna("UNKNOWN")
    raw_df["latitude_raw"] = raw_df["latitude_raw"].fillna(0.0)
    raw_df["longitude_raw"] = raw_df["longitude_raw"].fillna(0.0)

    def get_group_tuple(row):
        vehicle = str(row["vehicle_id_raw"])
        lat = float(row["latitude_raw"])
        lon = float(row["longitude_raw"])
        sf = str(row["source_file"])
        if sf.endswith(".gpkg"):
            timestamp = str(row["event_timestamp_raw"])
            return (sf, vehicle, timestamp, lon, lat)
        else:
            date_raw = str(row["event_date_raw"])
            time_raw = str(row["event_time_raw"])
            return (sf, vehicle, date_raw, time_raw, lat, lon)

    print("Generating native duplicate keys...")
    raw_df["dup_group_key"] = raw_df.apply(get_group_tuple, axis=1)

    print("Grouping duplicates...")
    grouped = raw_df.groupby("dup_group_key")

    group_map = {}
    group_idx = 0
    for key, _group in grouped:
        group_map[key] = f"dup_group_{group_idx}"
        group_idx += 1

    raw_df["duplicate_group_id"] = raw_df["dup_group_key"].map(group_map)
    raw_df["duplicate_multiplicity"] = raw_df["duplicate_group_id"].map(raw_df["duplicate_group_id"].value_counts())

    # 2. Write duplicate group membership
    membership_df = raw_df[[
        "source_file",
        "source_row_number",
        "duplicate_group_id",
        "duplicate_multiplicity",
        "canonical_segment_id"
    ]].copy()
    membership_path = os.path.join(project_root, config["outputs"]["duplicate_group_membership"])
    membership_df.to_parquet(membership_path, index=False)
    print(f"Saved duplicate membership to {membership_path}")

    # 3. Create collapsed events representation
    collapsed_df = raw_df.drop_duplicates(subset=["duplicate_group_id"], keep="first").copy()
    collapsed_df = collapsed_df.drop(columns=["dup_group_key"])

    collapsed_path = os.path.join(project_root, config["outputs"]["accepted_repair_events_collapsed"])
    collapsed_df.to_parquet(collapsed_path, index=False)
    print(f"Saved {len(collapsed_df)} collapsed events to {collapsed_path}")

    # 4. Generate duplicate sensitivity summary
    summary_data = {
        "total_raw_accepted_events": len(raw_df),
        "total_collapsed_events": len(collapsed_df),
        "duplicate_events_removed": len(raw_df) - len(collapsed_df),
        "multiplicity_distribution": raw_df["duplicate_multiplicity"].value_counts().to_dict()
    }
    summary_path = os.path.join(project_root, config["outputs"]["duplicate_sensitivity_summary"])
    with open(summary_path, 'w') as f:
        json.dump(summary_data, f, indent=2)
    print(f"Saved duplicate sensitivity summary to {summary_path}")


def build_historical_repairs(config, project_root, panel_df):
    """
    Computes rolling historical repair features strictly on or before as_of_date.
    Optimized via anchor-sliced groupings.
    """
    raw_path = os.path.join(project_root, config["outputs"]["accepted_repair_events_raw"])
    collapsed_path = os.path.join(project_root, config["outputs"]["accepted_repair_events_collapsed"])

    print(f"Loading accepted raw events from: {raw_path}")
    raw_events = pd.read_parquet(raw_path)
    print(f"Loading accepted collapsed events from: {collapsed_path}")
    collapsed_events = pd.read_parquet(collapsed_path)

    raw_events["canonical_segment_id"] = raw_events["canonical_segment_id"].astype(str)
    collapsed_events["canonical_segment_id"] = collapsed_events["canonical_segment_id"].astype(str)

    raw_events["event_timestamp_naive"] = pd.to_datetime(raw_events["event_timestamp_naive"])
    collapsed_events["event_timestamp_naive"] = pd.to_datetime(collapsed_events["event_timestamp_naive"])

    # Add helper event date
    raw_events["event_date"] = raw_events["event_timestamp_naive"].dt.date
    raw_events["event_month_start"] = raw_events["event_timestamp_naive"].dt.to_period("M").dt.to_timestamp()

    # List unique anchors and segments
    anchors = panel_df["as_of_date"].unique()
    segments = panel_df["canonical_segment_id"].unique()

    # 1. Pre-calculate valid days mapping for the windows
    # Since under primary policy all anchors are eligible, we count valid days from 2016-12-07 onwards
    valid_days_map = {}
    for anchor in anchors:
        anchor_ts = pd.Timestamp(anchor)
        for W in config["features"]["historical_repair_windows"]:
            w_start = anchor_ts - pd.Timedelta(days=W)
            window_days = pd.date_range(w_start + pd.Timedelta(days=1), anchor_ts)
            valid_days = sum(d >= pd.Timestamp("2016-12-07") for d in window_days)
            valid_days_map[(anchor_ts, W)] = valid_days

    print("Computing repair history features for each anchor...")

    anchor_features_list = []

    for t in anchors:
        t_ts = pd.Timestamp(t)

        # 1. Subset events <= t
        raw_hist = raw_events[raw_events["event_timestamp_naive"] <= t_ts]
        col_hist = collapsed_events[collapsed_events["event_timestamp_naive"] <= t_ts]

        # 2. Days since last repair
        # Group by segment to find max timestamp <= t
        last_rep = raw_hist.groupby("canonical_segment_id")["event_timestamp_naive"].max()

        # Build features for this anchor
        anchor_df = pd.DataFrame({"canonical_segment_id": segments})
        anchor_df["as_of_date"] = t_ts

        # Map last repair details
        anchor_df["last_repair_dt"] = anchor_df["canonical_segment_id"].map(last_rep)
        anchor_df["days_since_last_repair"] = (t_ts - anchor_df["last_repair_dt"]).dt.days

        anchor_df["last_repair_date"] = np.where(
            anchor_df["last_repair_dt"].notna(),
            anchor_df["last_repair_dt"].dt.strftime("%Y-%m-%d"),
            "None"
        )
        anchor_df["no_prior_repair_flag"] = anchor_df["last_repair_dt"].isna().astype(int)
        anchor_df = anchor_df.drop(columns=["last_repair_dt"])

        # 3. Rolling window aggregates
        for W in config["features"]["historical_repair_windows"]:
            w_start = t_ts - pd.Timedelta(days=W)
            valid_days = valid_days_map[(t_ts, W)]
            cov_ratio = float(valid_days) / W
            complete_flag = int(cov_ratio == 1.0)

            # Slices events in window (w_start, t_ts]
            raw_w = raw_hist[(raw_hist["event_timestamp_naive"] > w_start)]
            col_w = col_hist[(col_hist["event_timestamp_naive"] > w_start)]

            # Counts
            cnt_raw = raw_w.groupby("canonical_segment_id").size()
            cnt_col = col_w.groupby("canonical_segment_id").size()

            # Active days: unique dates per segment in window
            act_days = raw_w.drop_duplicates(subset=["canonical_segment_id", "event_date"]).groupby("canonical_segment_id").size()

            # Map columns
            anchor_df[f"repair_active_days_{W}d"] = anchor_df["canonical_segment_id"].map(act_days).fillna(0).astype(int)
            anchor_df[f"repair_event_count_raw_{W}d"] = anchor_df["canonical_segment_id"].map(cnt_raw).fillna(0).astype(int)
            anchor_df[f"repair_event_count_collapsed_{W}d"] = anchor_df["canonical_segment_id"].map(cnt_col).fillna(0).astype(int)
            anchor_df[f"repair_history_valid_days_{W}d"] = valid_days
            anchor_df[f"repair_history_coverage_ratio_{W}d"] = cov_ratio
            anchor_df[f"repair_history_complete_{W}d"] = complete_flag

        # 4. prior_repair_months_12m: number of unique month starts in [t - 11 months, t]
        # We find month starts
        m_start_bound = t_ts - pd.offsets.DateOffset(months=11)
        m_start_bound = m_start_bound.replace(day=1) # month start of 11 months ago

        raw_12m = raw_hist[raw_hist["event_timestamp_naive"] >= m_start_bound]
        cnt_12m_months = raw_12m.drop_duplicates(subset=["canonical_segment_id", "event_month_start"]).groupby("canonical_segment_id").size()

        anchor_df["prior_repair_months_12m"] = anchor_df["canonical_segment_id"].map(cnt_12m_months).fillna(0).astype(int)

        anchor_features_list.append(anchor_df)

    print("Combining anchor features...")
    features_all_df = pd.concat(anchor_features_list, ignore_index=True)

    # Generate segment_month_id to join
    month_str = features_all_df["as_of_date"].dt.strftime("%Y-%m")
    features_all_df["segment_month_id"] = features_all_df["canonical_segment_id"] + "_" + month_str

    features_all_df = features_all_df.set_index("segment_month_id")
    features_all_df = features_all_df.drop(columns=["canonical_segment_id", "as_of_date"])

    # Join back into panel
    panel_df = panel_df.join(features_all_df)

    print(f"Computed historical repair features for {len(panel_df)} panel rows.")
    return panel_df



def rolling_repairs_for_anchor(
    t: pd.Timestamp,
    segments: list[str],
    raw_daily: pd.DataFrame,
    col_daily: pd.DataFrame,
    last_repair_all: pd.Series,
    windows: list[int],
    first_obs: pd.Timestamp,
) -> pd.DataFrame:
    """
    For each window W, filters pre-aggregated daily counts to (t-W, t].
    All operations are vectorised over segments.
    """
    result = pd.DataFrame({"canonical_segment_id": segments})

    # Days since last repair (using all historical data <= t)
    hist_raw = raw_daily[raw_daily["event_date"] <= t]
    last_rep_t = (
        hist_raw.groupby("canonical_segment_id")["event_date"].max().rename("last_repair_dt")
    )
    result = result.merge(last_rep_t, on="canonical_segment_id", how="left")
    result["days_since_last_repair"] = (t - result["last_repair_dt"]).dt.days
    result["last_repair_date"] = result["last_repair_dt"].dt.strftime("%Y-%m-%d").fillna("None")
    result["no_prior_repair_flag"] = result["last_repair_dt"].isna().astype(int)
    result = result.drop(columns=["last_repair_dt"])

    for W in windows:
        w_start = t - pd.Timedelta(days=W)
        # raw
        raw_w = raw_daily[(raw_daily["event_date"] > w_start) & (raw_daily["event_date"] <= t)]
        cnt_raw = raw_w.groupby("canonical_segment_id")["raw_count"].sum().rename(f"repair_event_count_raw_{W}d")
        act_days = raw_w.groupby("canonical_segment_id")["event_date"].nunique().rename(f"repair_active_days_{W}d")
        # collapsed
        col_w = col_daily[(col_daily["event_date"] > w_start) & (col_daily["event_date"] <= t)]
        cnt_col = col_w.groupby("canonical_segment_id")["col_count"].sum().rename(f"repair_event_count_collapsed_{W}d")

        # valid days in window
        window_days = pd.date_range(w_start + pd.Timedelta(days=1), t)
        valid_days = int(sum(d >= first_obs for d in window_days))
        cov_ratio = float(valid_days) / W

        result = result.merge(cnt_raw, on="canonical_segment_id", how="left")
        result = result.merge(act_days, on="canonical_segment_id", how="left")
        result = result.merge(cnt_col, on="canonical_segment_id", how="left")
        result[f"repair_event_count_raw_{W}d"] = result[f"repair_event_count_raw_{W}d"].fillna(0).astype(int)
        result[f"repair_active_days_{W}d"]     = result[f"repair_active_days_{W}d"].fillna(0).astype(int)
        result[f"repair_event_count_collapsed_{W}d"] = result[f"repair_event_count_collapsed_{W}d"].fillna(0).astype(int)
        result[f"repair_history_valid_days_{W}d"]    = valid_days
        result[f"repair_history_coverage_ratio_{W}d"] = cov_ratio
        result[f"repair_history_complete_{W}d"]       = int(cov_ratio == 1.0)

    # prior_repair_months_12m
    m_start = (t - pd.offsets.DateOffset(months=11)).replace(day=1)
    raw_12m = raw_daily[
        (raw_daily["event_date"] >= pd.Timestamp(m_start)) & (raw_daily["event_date"] <= t)
    ]
    raw_12m = raw_12m.copy()
    raw_12m["month_start"] = raw_12m["event_date"].dt.to_period("M")
    cnt_12m = (
        raw_12m.drop_duplicates(["canonical_segment_id", "month_start"])
        .groupby("canonical_segment_id")
        .size()
        .rename("prior_repair_months_12m")
    )
    result = result.merge(cnt_12m, on="canonical_segment_id", how="left")
    result["prior_repair_months_12m"] = result["prior_repair_months_12m"].fillna(0).astype(int)
    return result
