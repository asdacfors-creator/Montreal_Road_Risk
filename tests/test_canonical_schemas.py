import pandas as pd
from montreal_road_risk.spatial.schema import add_provenance_fields, map_canonical_columns


def test_add_provenance_fields():
    df = pd.DataFrame({"dummy": [1, 2]})
    res = add_provenance_fields(
        df,
        dataset_id="test_ds",
        filename="test.csv",
        file_format="CSV",
        year_or_campaign=2021,
        crs_status="declared",
        crs_value="EPSG:4326",
        working_crs="EPSG:32188",
        version="1.0.0",
    )

    assert "source_dataset" in res.columns
    assert res["source_dataset"].iloc[0] == "test_ds"
    assert res["source_file"].iloc[0] == "test.csv"
    assert res["source_format"].iloc[0] == "CSV"
    assert res["source_year"].iloc[0] == 2021
    assert res["campaign_label"].iloc[0] == "2021"
    assert res["source_record_number"].iloc[0] == 1
    assert res["source_record_number"].iloc[1] == 2
    assert res["source_crs_status"].iloc[0] == "declared"
    assert res["source_crs_value"].iloc[0] == "EPSG:4326"
    assert res["working_crs"].iloc[0] == "EPSG:32188"
    assert res["preprocessing_version"].iloc[0] == "1.0.0"


def test_map_canonical_columns():
    # Setup dataframe with provenance fields
    df = pd.DataFrame(
        {
            "OldName1": [10, 20],
            "OldName2": [30, 40],
            "Unmapped": [100, 200],
            "source_dataset": ["test_ds", "test_ds"],
        }
    )

    field_mapping = {"OldName1": "new_name_1", "OldName2": "new_name_2"}

    res = map_canonical_columns(df, field_mapping, keep_additional_fields=["Unmapped"])

    # Check mapped fields exist and have correct names
    assert "new_name_1" in res.columns
    assert "new_name_2" in res.columns
    # Check unmapped was dropped if not in keep_additional_fields, but since it is in, it should be kept
    assert "Unmapped" in res.columns
    # Check provenance fields are kept
    assert "source_dataset" in res.columns

    # Let's test without keeping additional fields
    res2 = map_canonical_columns(df, field_mapping)
    assert "Unmapped" not in res2.columns
