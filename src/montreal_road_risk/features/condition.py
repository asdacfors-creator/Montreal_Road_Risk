import os

import numpy as np
import pandas as pd


def build_condition_features(config, project_root, panel_df):  # noqa: C901
    """
    Performs dynamic as-of joining of pavement condition survey features relative to as_of_date.
    Uses pd.merge_asof for vectorization.
    """
    pavement_path = os.path.join(project_root, config["inputs"]["pavement"])
    print(f"Loading pavement condition from: {pavement_path}")
    pav_df = pd.read_parquet(pavement_path)

    # 1. Filter accepted pavement links (direct_id or spatial_fallback)
    accepted_pav = pav_df[pav_df["linkage_status"].isin(["direct_id", "spatial_fallback"])].copy()
    accepted_pav["canonical_segment_id"] = accepted_pav["canonical_segment_id"].astype(str)
    accepted_pav["survey_date"] = pd.to_datetime(accepted_pav["survey_date"])

    # Cast raw condition metrics to float to allow statistical aggregations
    accepted_pav["pci_raw"] = pd.to_numeric(accepted_pav["pci_raw"], errors="coerce")
    accepted_pav["iri_raw"] = pd.to_numeric(accepted_pav["iri_raw"], errors="coerce")

    # Classify campaign scope
    def classify_campaign_scope(row):
        lbl = str(row["campaign_label"]).strip()
        if lbl in ["2018", "2024"]:
            return "arterial"
        elif lbl == "2022":
            return "local"
        elif lbl in ["2010", "2015", "2020"]:
            return "mixed_or_citywide"
        return "unknown"

    accepted_pav["condition_campaign_scope"] = accepted_pav.apply(classify_campaign_scope, axis=1)

    # 2. Group by canonical_segment_id and survey_date to resolve duplicates deterministically
    print("Collapsing same-day pavement surveys using the median...")
    grouped_pav = accepted_pav.groupby(["canonical_segment_id", "survey_date"]).agg(
        latest_pci=("pci_raw", "median"),
        pci_min=("pci_raw", "min"),
        pci_max=("pci_raw", "max"),
        pci_std=("pci_raw", lambda x: np.std(x) if len(x) > 1 else 0.0),
        latest_iri=("iri_raw", "median"),
        iri_min=("iri_raw", "min"),
        iri_max=("iri_raw", "max"),
        iri_std=("iri_raw", lambda x: np.std(x) if len(x) > 1 else 0.0),
        condition_candidate_count=("pci_raw", "count"),
        condition_campaign_scope=("condition_campaign_scope", "first")
    ).reset_index()

    # 3. Sort grouped_pav before merge_asof (panel_df is already pre-sorted by as_of_date)
    grouped_pav = grouped_pav.sort_values(by="survey_date").copy()

    # survey_date will act as latest_condition_survey_date
    grouped_pav["latest_condition_survey_date"] = grouped_pav["survey_date"]

    # Cast merge keys explicitly to datetime64[ns] to avoid Arrow/NumPy mismatch errors
    panel_df["as_of_date"] = panel_df["as_of_date"].astype("datetime64[ns]")
    grouped_pav["survey_date"] = grouped_pav["survey_date"].astype("datetime64[ns]")

    print("Performing vectorized as-of join for pavement condition...")
    merged = pd.merge_asof(
        panel_df,
        grouped_pav,
        left_on="as_of_date",
        right_on="survey_date",
        by="canonical_segment_id",
        direction="backward"
    )

    # 4. Compute derived columns
    merged["condition_missing_flag"] = merged["survey_date"].isna().astype(int)
    merged["days_since_condition_survey"] = (merged["as_of_date"] - merged["survey_date"]).dt.days

    # Format latest_condition_survey_date to string
    merged["latest_condition_survey_date_str"] = np.where(
        merged["survey_date"].notna(),
        merged["survey_date"].dt.strftime("%Y-%m-%d"),
        "None"
    )

    # Clean up columns
    merged = merged.drop(columns=["survey_date", "latest_condition_survey_date"])
    merged = merged.rename(columns={"latest_condition_survey_date_str": "latest_condition_survey_date"})

    # Fill remaining NaNs with defaults
    merged["condition_campaign_scope"] = merged["condition_campaign_scope"].fillna("unknown")
    merged["condition_candidate_count"] = merged["condition_candidate_count"].fillna(0).astype(int)

    # Reset index to match original segment_month_id
    merged = merged.set_index("segment_month_id", drop=False)

    print(f"Computed pavement condition features for {len(merged)} panel rows.")
    return merged
