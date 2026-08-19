import datetime

import pandas as pd


def calculate_temporal_coverage(df, date_col, parse_status_col):
    """
    Calculate factual temporal coverage statistics for a DataFrame.
    """
    total_records = len(df)
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()

    earliest_date = dates.min().date().isoformat() if not dates.empty else None
    latest_date = dates.max().date().isoformat() if not dates.empty else None

    # Missing counts
    missing_count = int(df[date_col].isna().sum())

    # Parse failure counts
    parse_failure_count = int((df[parse_status_col] == "parse_failure").sum())

    # Duplicate count details (repeated event dates)
    valid_dates_series = df[date_col].dropna()
    date_counts = valid_dates_series.value_counts()
    repeated_dates = date_counts[date_counts > 1]

    distinct_repeated_dates = int(len(repeated_dates))
    rows_in_repeated_dates = int(repeated_dates.sum())
    excess_rows_repeated_dates = int(rows_in_repeated_dates - distinct_repeated_dates)

    return {
        "total_records": total_records,
        "earliest_observed_date": earliest_date,
        "latest_observed_date": latest_date,
        "missing_date_count": missing_count,
        "parse_failure_count": parse_failure_count,
        "distinct_repeated_dates": distinct_repeated_dates,
        "rows_in_repeated_dates": rows_in_repeated_dates,
        "excess_rows_repeated_dates": excess_rows_repeated_dates,
    }


def calculate_right_edge_eligibility(latest_observed_date):
    """
    Calculate candidate right-edge dates for 90-day and 180-day target eligibility.
    This is for coverage analysis ONLY.
    """
    if isinstance(latest_observed_date, str):
        latest_dt = datetime.date.fromisoformat(latest_observed_date)
    elif isinstance(latest_observed_date, (datetime.datetime, datetime.date)):
        latest_dt = latest_observed_date
        if hasattr(latest_dt, "date"):
            latest_dt = latest_dt.date()
    else:
        return {}

    # Subtract 90 and 180 days
    right_edge_90 = latest_dt - datetime.timedelta(days=90)
    right_edge_180 = latest_dt - datetime.timedelta(days=180)

    return {
        "latest_observed_date": latest_dt.isoformat(),
        "candidate_right_edge_90_days": right_edge_90.isoformat(),
        "candidate_right_edge_180_days": right_edge_180.isoformat(),
        "note": "Right-edge calculations are for coverage analysis only. They do not select a modelling window or create labels.",
    }
