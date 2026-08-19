"""
Cohort generation module for Phase 9 Survival Analysis.
Constructs mixed first-event/recurrent-event survival dataset (survival_cohort.parquet).
"""

from pathlib import Path

import pandas as pd

STUDY_START_DATE = pd.Timestamp("2016-12-07")
STUDY_END_DATE = pd.Timestamp("2025-05-20")


def normalize_segment_id(seg_id: str | int | float) -> str:
    """Normalize segment ID to string representation."""
    if pd.isna(seg_id):
        return ""
    try:
        val = str(int(float(seg_id)))
        return val
    except (ValueError, TypeError):
        return str(seg_id).strip()


def build_survival_cohort(
    collapsed_events_path: str | Path = "data/processed/phase_4/accepted_repair_events_collapsed.parquet",
    geobase_path: str | Path = "data/interim/spatial_base/geobase_32188.parquet",
    data_mart_path: str | Path = "data/processed/phase_8/dashboard_data_mart.parquet",
    output_path: str | Path = "data/processed/phase_9/survival_cohort.parquet",
) -> pd.DataFrame:
    """
    Constructs a mixed first-event/recurrent-event survival cohort dataframe.

    Parameters
    ----------
    collapsed_events_path : str | Path
        Path to collapsed repair events parquet file.
    geobase_path : str | Path
        Path to geobase 32188 parquet file for canonical segment universe (47,983 segments).
    data_mart_path : str | Path
        Path to dashboard data mart parquet file for segment spatial metadata.
    output_path : str | Path
        Target destination path for survival_cohort.parquet.

    Returns
    -------
    pd.DataFrame
        Cohort dataset with columns:
        - canonical_segment_id (str)
        - interval_index (int)
        - start_date (datetime)
        - end_date (datetime)
        - duration_days (float)
        - event_observed (int)
        - functional_road_class (int)
        - primary_borough_id (int)
        - segment_length_m (float)
    """
    collapsed_events_path = Path(collapsed_events_path)
    geobase_path = Path(geobase_path)
    data_mart_path = Path(data_mart_path)
    output_path = Path(output_path)

    if not collapsed_events_path.exists():
        raise FileNotFoundError(f"Collapsed repair events file not found: {collapsed_events_path}")
    if not geobase_path.exists():
        raise FileNotFoundError(f"Geobase file not found: {geobase_path}")
    if not data_mart_path.exists():
        raise FileNotFoundError(f"Data mart file not found: {data_mart_path}")

    # Load canonical segment universe (47,983 segments)
    geobase_df = pd.read_parquet(geobase_path)
    all_segment_ids = sorted({normalize_segment_id(x) for x in geobase_df["ID_TRC"] if pd.notna(x)})

    # Load collapsed repair events
    events_df = pd.read_parquet(collapsed_events_path)
    events_df["event_dt"] = pd.to_datetime(events_df["event_timestamp_naive"])
    events_df["event_date_only"] = events_df["event_dt"].dt.normalize()
    events_df["canonical_segment_id"] = events_df["canonical_segment_id"].apply(normalize_segment_id)

    # Deduplicate to unique (canonical_segment_id, event_date_only)
    repair_dates = (
        events_df.groupby(["canonical_segment_id", "event_date_only"])
        .size()
        .reset_index(name="daily_repair_count")[["canonical_segment_id", "event_date_only"]]
        .sort_values(["canonical_segment_id", "event_date_only"])
    )

    # Load spatial metadata from data mart
    dm_df = pd.read_parquet(data_mart_path)
    dm_df["canonical_segment_id"] = dm_df["canonical_segment_id"].apply(normalize_segment_id)
    metadata_cols = ["canonical_segment_id", "functional_road_class", "primary_borough_id", "segment_length_m"]
    segment_meta = (
        dm_df[metadata_cols]
        .drop_duplicates(subset=["canonical_segment_id"])
        .set_index("canonical_segment_id")
    )

    repaired_segment_ids = set(repair_dates["canonical_segment_id"].unique())

    cohort_records = []

    # Process segments with repairs
    for seg_id, group in repair_dates.groupby("canonical_segment_id"):
        dates = group["event_date_only"].tolist()
        m = len(dates)

        # Inter-event repair intervals (observed events, E=1)
        for idx in range(m - 1):
            d_start = dates[idx]
            d_end = dates[idx + 1]
            duration = float((d_end - d_start).days)
            if duration > 0:
                cohort_records.append({
                    "canonical_segment_id": str(seg_id),
                    "interval_index": idx,
                    "start_date": d_start,
                    "end_date": d_end,
                    "duration_days": duration,
                    "event_observed": 1,
                })

        # Right-censored interval from last repair date to STUDY_END_DATE (E=0)
        last_date = dates[-1]
        censor_duration = float((STUDY_END_DATE - last_date).days)
        if censor_duration > 0:
            cohort_records.append({
                "canonical_segment_id": str(seg_id),
                "interval_index": m - 1 if m > 1 else 0,
                "start_date": last_date,
                "end_date": STUDY_END_DATE,
                "duration_days": censor_duration,
                "event_observed": 0,
            })

    # Process 0-repair segments (fully right-censored, E=0)
    zero_repair_ids = [sid for sid in all_segment_ids if sid not in repaired_segment_ids]
    full_censor_duration = float((STUDY_END_DATE - STUDY_START_DATE).days)

    for seg_id in zero_repair_ids:
        cohort_records.append({
            "canonical_segment_id": str(seg_id),
            "interval_index": 0,
            "start_date": STUDY_START_DATE,
            "end_date": STUDY_END_DATE,
            "duration_days": full_censor_duration,
            "event_observed": 0,
        })

    cohort_df = pd.DataFrame(cohort_records)

    # Merge spatial metadata
    cohort_df = cohort_df.merge(
        segment_meta,
        on="canonical_segment_id",
        how="left",
    )

    # Ensure clean dtypes
    cohort_df["canonical_segment_id"] = cohort_df["canonical_segment_id"].astype(str)
    cohort_df["interval_index"] = cohort_df["interval_index"].astype(int)
    cohort_df["duration_days"] = cohort_df["duration_days"].astype(float)
    cohort_df["event_observed"] = cohort_df["event_observed"].astype(int)
    cohort_df["functional_road_class"] = cohort_df["functional_road_class"].fillna(0).astype(int)
    cohort_df["primary_borough_id"] = cohort_df["primary_borough_id"].fillna(0).astype(int)
    cohort_df["segment_length_m"] = cohort_df["segment_length_m"].fillna(0.0).astype(float)

    # Save to parquet
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cohort_df.to_parquet(output_path, index=False)

    return cohort_df
