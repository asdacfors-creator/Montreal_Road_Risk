import numpy as np
import pandas as pd


def build_cartesian_panel(config, segments_list):
    """
    Constructs the Cartesian product of segments and month-end anchors.

    Parameters:
    -----------
    config : dict
        Loaded feature_engineering.json config.
    segments_list : list of str
        The unique segment IDs in the Geobase population.

    Returns:
    --------
    pd.DataFrame
        Cartesian panel containing:
        - segment_month_id (index/key)
        - canonical_segment_id
        - panel_year
        - panel_month
        - as_of_date (last calendar day of the month)
    """
    # 1. Generate the 102 anchors
    start_anchor = pd.Timestamp(config["panel_settings"]["start_month"] + "-01")
    end_anchor = pd.Timestamp(config["panel_settings"]["end_month"] + "-31")
    anchors = pd.date_range(start=start_anchor, end=end_anchor, freq="ME")

    print(f"Generating Cartesian panel for {len(segments_list)} segments and {len(anchors)} month anchors...")

    # 2. Build Cartesian index
    # We repeat segments for each anchor
    seg_array = np.repeat(segments_list, len(anchors))
    anchor_array = np.tile(anchors, len(segments_list))

    panel_df = pd.DataFrame({
        "canonical_segment_id": seg_array.astype(str),
        "as_of_date": pd.to_datetime(anchor_array).astype("datetime64[ns]")
    })

    # 3. Add derived panel columns
    panel_df["panel_year"] = panel_df["as_of_date"].dt.year.astype(int)
    panel_df["panel_month"] = panel_df["as_of_date"].dt.month.astype(int)

    # Create segment_month_id: {canonical_segment_id}_{YYYY-MM}
    month_str = panel_df["as_of_date"].dt.strftime("%Y-%m")
    panel_df["segment_month_id"] = panel_df["canonical_segment_id"] + "_" + month_str

    # Set segment_month_id as index or column
    panel_df = panel_df.set_index("segment_month_id", drop=False)

    # Sort panel chronologically by as_of_date to optimize as-of merges
    panel_df = panel_df.sort_values(by="as_of_date")

    expected_rows = len(segments_list) * len(anchors)
    assert len(panel_df) == expected_rows, f"Expected {expected_rows} panel rows, got {len(panel_df)}"

    print(f"Constructed panel with {len(panel_df)} rows.")
    return panel_df
