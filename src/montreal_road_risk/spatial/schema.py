import numpy as np


def add_provenance_fields(
    df,
    dataset_id,
    filename,
    file_format,
    year_or_campaign,
    crs_status,
    crs_value,
    working_crs,
    version,
):
    """Add standardized provenance fields to a DataFrame or GeoDataFrame."""
    df = df.copy()
    df["source_dataset"] = dataset_id
    df["source_file"] = filename
    df["source_format"] = file_format

    if isinstance(year_or_campaign, int):
        df["source_year"] = year_or_campaign
        df["campaign_label"] = str(year_or_campaign)
    else:
        df["campaign_label"] = str(year_or_campaign)
        df["source_year"] = -1  # Placeholder for campaigns without single year

    df["source_record_number"] = np.arange(1, len(df) + 1)
    df["source_crs_status"] = crs_status
    df["source_crs_value"] = crs_value
    df["working_crs"] = working_crs
    df["preprocessing_version"] = version
    return df


def map_canonical_columns(df, field_mapping, keep_additional_fields=None):
    """Map raw columns to canonical column names, dropping unmapped columns unless explicitly kept."""
    df = df.copy()

    # Perform renaming
    df = df.rename(columns=field_mapping)

    # Identify which columns to keep
    canonical_fields = list(field_mapping.values())

    # Provenance fields to always keep
    provenance_fields = [
        "source_dataset",
        "source_file",
        "source_format",
        "source_year",
        "campaign_label",
        "source_record_number",
        "source_crs_status",
        "source_crs_value",
        "working_crs",
        "preprocessing_version",
    ]

    fields_to_keep = set(canonical_fields + provenance_fields)

    # Special columns for specific datasets
    special_fields = [
        "geometry",
        "original_geometry",
        "out_of_source_year_flag",
        "exact_duplicate_candidate_flag",
        "spatial_temporal_duplicate_candidate_flag",
        "candidate_missing_sentinel_flag",
        "duplicate_candidate_flag",
    ]
    for f in special_fields:
        if f in df.columns:
            fields_to_keep.add(f)

    if keep_additional_fields:
        for f in keep_additional_fields:
            if f in df.columns:
                fields_to_keep.add(f)

    # Keep only the resolved list
    keep_cols = [c for c in df.columns if c in fields_to_keep]
    return df[keep_cols]
