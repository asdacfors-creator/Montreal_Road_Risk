import datetime
import re

import numpy as np
import pandas as pd


def parse_date_time(date_val, time_val=None):
    """
    Parse date and optional time values, returning parsed date, time, and status.
    """
    if pd.isna(date_val) or str(date_val).strip().lower() in ("inconnu", "none", "", "nan"):
        return None, None, "missing"

    date_str = str(date_val).strip()

    parsed_date = None
    # Try parsing common formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            parsed_date = dt.date()
            break
        except ValueError:
            pass

    if parsed_date is None:
        # Fallback to year extraction for imprecise assets
        match = re.search(r"\b(19|20)\d{2}\b", date_str)
        if match:
            year = int(match.group(0))
            return datetime.date(year, 1, 1), None, "imprecise_year"
        return None, None, "parse_failure"

    parsed_time = None
    if time_val is not None and not pd.isna(time_val):
        time_str = str(time_val).strip()
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"):
            try:
                dt_t = datetime.datetime.strptime(time_str, fmt)
                parsed_time = dt_t.time()
                break
            except ValueError:
                pass

    if parsed_time is None:
        return parsed_date, None, "date_only"

    return parsed_date, parsed_time, "precise"


def classify_precision(status):
    """Map parsing status to precision category."""
    if status == "precise":
        return "precise"
    elif status == "date_only":
        return "date_only"
    elif status == "imprecise_year":
        return "imprecise_year"
    else:
        return "unknown"


def localize_to_toronto(dt_val):
    """
    Localize a naive datetime to America/Toronto timezone with DST safeguards.
    If ambiguous or nonexistent, retains naive local time and returns status.
    """
    if pd.isna(dt_val):
        return pd.NaT, "missing"

    try:
        ts = pd.to_datetime(dt_val)
        if ts is pd.NaT:
            return pd.NaT, "missing"
        if ts.tz is not None:
            return ts, "successfully_localized"

        try:
            localized = ts.tz_localize("America/Toronto", ambiguous="raise", nonexistent="raise")
            return localized, "successfully_localized"
        except ValueError as ve:
            msg = str(ve)
            if "Cannot infer dst time" in msg:
                return ts, "ambiguous_dst"
            elif "nonexistent time" in msg:
                return ts, "nonexistent_dst"
            else:
                return ts, "parse_failure"
    except Exception:
        return pd.NaT, "parse_failure"


def localize_series_to_toronto(ts_series):
    """
    Vectorized localization of a pandas Series of timestamps to America/Toronto timezone.
    Returns:
      - localized_series: pd.Series of localized timestamps (ambiguous/nonexistent remain naive)
      - status_series: pd.Series of localization status strings
    """
    n = len(ts_series)
    status = np.full(n, "missing", dtype=object)

    valid_mask = ts_series.notna()
    status[valid_mask] = "successfully_localized"

    # Convert series to localized with NaT for ambiguous/nonexistent, cast to object
    localized = ts_series.dt.tz_localize("America/Toronto", ambiguous="NaT", nonexistent="NaT").astype(object)

    anomaly_mask = valid_mask & localized.isna()
    if anomaly_mask.any():
        anomaly_indices = np.where(anomaly_mask)[0]
        ts_values = ts_series.iloc[anomaly_indices]

        # Detailed individual resolution for DST anomalies
        for idx, ts_val in zip(anomaly_indices, ts_values, strict=True):
            try:
                # Try raising to see what exception occurs
                ts_val.tz_localize("America/Toronto", ambiguous="raise", nonexistent="raise")
                # If no exception, it localized successfully
                localized.iloc[idx] = ts_val.tz_localize("America/Toronto")
                status[idx] = "successfully_localized"
            except ValueError as ve:
                msg = str(ve)
                if "Cannot infer dst time" in msg:
                    localized.iloc[idx] = ts_val  # Keep naive local time
                    status[idx] = "ambiguous_dst"
                elif "nonexistent time" in msg:
                    localized.iloc[idx] = ts_val  # Keep naive local time
                    status[idx] = "nonexistent_dst"
                else:
                    localized.iloc[idx] = pd.NaT
                    status[idx] = "parse_failure"
            except Exception:
                localized.iloc[idx] = pd.NaT
                status[idx] = "parse_failure"

    return localized, pd.Series(status, index=ts_series.index)
