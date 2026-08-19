import os

import numpy as np
import pandas as pd


def build_pothole_targets(config, project_root, panel_df):
    """
    Computes primary (90d) and sensitivity (180d) target variables for each segment-month.

    Returns:
    --------
    panel_df : pd.DataFrame
        Panel with target columns joined.
    """
    # 1. Load accepted links and preprocessed potholes
    pothole_links_path = os.path.join(project_root, config["inputs"]["pothole_links"])
    potholes_path = os.path.join(project_root, config["inputs"]["potholes"])

    print(f"Loading pothole links from: {pothole_links_path}")
    links_df = pd.read_parquet(pothole_links_path)

    # 2. Reconcile categories to all 1,027,267 events
    counts = links_df["linkage_status"].value_counts()
    print("Reconciling linkage categories:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    # Create target exclusion audit containing only unmatched and review_required
    exclusion_df = links_df[links_df["linkage_status"].isin(["unmatched", "review_required"])].copy()
    exclusion_path = os.path.join(project_root, config["outputs"]["target_exclusion_audit"])
    os.makedirs(os.path.dirname(exclusion_path), exist_ok=True)
    exclusion_df.to_parquet(exclusion_path, index=False)
    print(f"Saved {len(exclusion_df)} event exclusions to {exclusion_path}")

    # 3. Filter accepted links
    accepted_links = links_df[links_df["linkage_status"] == "accepted"].copy()
    accepted_links["canonical_segment_id"] = accepted_links["canonical_segment_id"].astype(str)

    # Join with potholes to get event_timestamp_naive
    print(f"Loading pothole temporal details from: {potholes_path}")
    potholes_df = pd.read_parquet(potholes_path)

    potholes_df["source_row_number"] = potholes_df["source_row_number"].astype(int)
    accepted_links["source_row_number"] = accepted_links["source_row_number"].astype(int)

    # Safe join: avoid column suffix collisions by selecting only non-overlapping columns from potholes_df
    overlapping_cols = accepted_links.columns.intersection(potholes_df.columns).difference(["source_file", "source_row_number"])
    potholes_sub = potholes_df.drop(columns=overlapping_cols)

    accepted_base = accepted_links.merge(
        potholes_sub,
        on=["source_file", "source_row_number"],
        how="inner"
    )

    # Join with repairs by year to get vehicle_id_raw, latitude_raw, longitude_raw
    print("Joining accepted events with temporal details and raw columns by year...")
    events_list = []

    for year, group in accepted_base.groupby("source_year"):
        year_val = int(year)
        rep_path = os.path.join(project_root, f"data/interim/phase_3a/pothole_repairs/pothole_repairs_{year_val}_32188.parquet")
        print(f"  Loading raw columns for year {year_val} from: {rep_path}")
        rep_year_df = pd.read_parquet(rep_path)

        merged_year = group.merge(
            rep_year_df[[
                "source_record_number",
                "vehicle_id_raw",
                "latitude_raw",
                "longitude_raw"
            ]],
            left_on="source_row_number",
            right_on="source_record_number",
            how="inner"
        )
        merged_year = merged_year.drop(columns=["source_record_number"])

        # Explicit type conversion to prevent Arrow serialization issues
        merged_year["vehicle_id_raw"] = merged_year["vehicle_id_raw"].astype(str)
        merged_year["event_timestamp_raw"] = merged_year["event_timestamp_raw"].astype(str)
        merged_year["event_date_raw"] = merged_year["event_date_raw"].astype(str)
        merged_year["event_time_raw"] = merged_year["event_time_raw"].astype(str)
        merged_year["latitude_raw"] = merged_year["latitude_raw"].astype(float)
        merged_year["longitude_raw"] = merged_year["longitude_raw"].astype(float)

        events_list.append(merged_year)

    accepted_events = pd.concat(events_list, ignore_index=True)

    # Write accepted raw events
    accepted_raw_path = os.path.join(project_root, config["outputs"]["accepted_repair_events_raw"])
    accepted_events.to_parquet(accepted_raw_path, index=False)
    print(f"Saved {len(accepted_events)} accepted raw events to {accepted_raw_path}")

    # 4. Save target event ledger
    ledger_path = os.path.join(project_root, config["outputs"]["target_event_ledger"])
    accepted_events.to_parquet(ledger_path, index=False)

    # 5. Build daily coverage calendar
    calendar_dates = pd.date_range("2016-12-01", "2025-12-31", freq="D")

    def get_published_status(d):
        dt = pd.Timestamp(d)
        if pd.Timestamp("2016-12-07") <= dt <= pd.Timestamp("2025-12-31"):
            return "published_resource_observed_assumption"
        return "outside_resource_period"

    calendar_rows = []
    for d in calendar_dates:
        calendar_rows.append({
            "date": d,
            "coverage_policy": "published_resource_observation_universe",
            "coverage_status": get_published_status(d),
            "source_resource": "published_annual_resources",
            "evidence_type": "verified_resource_semantics",
            "evidence_reference": "L2.2 / L2.4",
            "assumption_flag": 1,
            "limitation_id": "L2.4"
        })
    df_cal = pd.DataFrame(calendar_rows)
    cal_path = os.path.join(project_root, config["outputs"]["outcome_observation_calendar"])
    df_cal.to_parquet(cal_path, index=False)
    print(f"Saved outcome_observation_calendar.parquet to {cal_path}")

    # 6. Optimized Vectorized Target construction
    # Initialize targets
    panel_df["target_eligible_90d"] = 1
    panel_df["target_repair_90d"] = 0
    panel_df["target_eligible_180d"] = 1
    panel_df["target_repair_180d"] = 0
    panel_df["target_repair_90d_strict"] = np.nan
    panel_df["target_repair_180d_strict"] = np.nan
    panel_df["positive_observed_in_incomplete_window_90d"] = 0
    panel_df["positive_observed_in_incomplete_window_180d"] = 0

    print("Computing target flags using vectorized anchor slicing...")
    anchors = panel_df["as_of_date"].unique()

    accepted_events["event_timestamp_naive"] = pd.to_datetime(accepted_events["event_timestamp_naive"])

    for t in anchors:
        t_ts = pd.Timestamp(t)

        # 90d window: (t, t + 90 days]
        w90_end = t_ts + pd.Timedelta(days=90)
        events_90 = accepted_events[
            (accepted_events["event_timestamp_naive"] > t_ts) &
            (accepted_events["event_timestamp_naive"] <= w90_end)
        ]
        segs_90 = events_90["canonical_segment_id"].unique()

        # 180d window: (t, t + 180 days]
        w180_end = t_ts + pd.Timedelta(days=180)
        events_180 = accepted_events[
            (accepted_events["event_timestamp_naive"] > t_ts) &
            (accepted_events["event_timestamp_naive"] <= w180_end)
        ]
        segs_180 = events_180["canonical_segment_id"].unique()

        # Assign to panel rows matching this anchor
        panel_df.loc[
            (panel_df["as_of_date"] == t_ts) &
            (panel_df["canonical_segment_id"].isin(segs_90)),
            "target_repair_90d"
        ] = 1

        panel_df.loc[
            (panel_df["as_of_date"] == t_ts) &
            (panel_df["canonical_segment_id"].isin(segs_180)),
            "target_repair_180d"
        ] = 1

    # Write target window eligibility audit (empty placeholder since all are eligible)
    audit_path = os.path.join(project_root, config["outputs"]["target_window_eligibility_audit"])
    pd.DataFrame(columns=["as_of_date", "segment_id", "policy", "horizon", "eligible_flag", "reason"]).to_parquet(audit_path, index=False)
    print(f"Saved target_window_eligibility_audit.parquet to {audit_path}")

    print(f"Finished building targets for {len(panel_df)} panel rows.")
    return panel_df
