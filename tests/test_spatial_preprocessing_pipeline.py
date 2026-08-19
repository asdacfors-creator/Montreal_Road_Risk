import pandas as pd
from datetime import datetime

# Import utilities from the script
from scripts.preprocess_spatial_base import (
    parse_asset_date,
    _normalize_df_columns,
    _extract_pothole_datetime_fields,
    _compute_pothole_flags,
    _compute_pavement_flags,
)


def test_parse_asset_date():
    # Test precise formats
    dt1, prec1, imp1 = parse_asset_date("2020-05-15")
    assert dt1 == datetime(2020, 5, 15)
    assert prec1 == "precise"
    assert imp1 == 0

    # Test imprecise year format
    dt2, prec2, imp2 = parse_asset_date("Année 2012 approx")
    assert dt2 == datetime(2012, 1, 1)
    assert prec2 == "imprecise_year"
    assert imp2 == 0

    # Test unknown format
    dt3, prec3, imp3 = parse_asset_date("Inconnu")
    assert dt3 is None
    assert prec3 == "unknown"
    assert imp3 == 1


def test_normalize_df_columns():
    df = pd.DataFrame({"Indice PCI": [1], "Etat_IRI": [2], "Date Rélevé": [3]})
    res = _normalize_df_columns(df)
    assert list(res.columns) == ["Indice_PCI", "Etat_IRI", "Date_Releve"]


def test_extract_pothole_datetime_fields_csv():
    df = pd.DataFrame({"DateJour": ["2020-05-15"], "DateHeure": ["13:05:00"]})
    res = _extract_pothole_datetime_fields(df, is_gpkg=False)
    assert res["event_date_raw"].iloc[0] == "2020-05-15"
    assert res["event_time_raw"].iloc[0] == "13:05:00"
    assert res["event_timestamp"].iloc[0] == datetime(2020, 5, 15, 13, 5, 0)


def test_extract_pothole_datetime_fields_gpkg():
    # Test datetime series input
    df = pd.DataFrame({"Date": [pd.Timestamp("2021-01-27 13:06:44")]})
    res = _extract_pothole_datetime_fields(df, is_gpkg=True)
    assert res["event_date_raw"].iloc[0] == "2021-01-27"
    assert res["event_time_raw"].iloc[0] == "13:06:44"
    assert res["event_timestamp"].iloc[0] == pd.Timestamp("2021-01-27 13:06:44")


def test_compute_pothole_flags():
    df = pd.DataFrame(
        {
            "vehicle_id_raw": ["V1", "V1", "V1"],
            "event_date_raw": ["2020-05-15", "2020-05-15", "2021-05-15"],
            "event_time_raw": ["13:05:00", "13:05:00", "13:05:00"],
            "latitude_raw": [45.5, 45.5, 45.5],
            "longitude_raw": [-73.5, -73.5, -73.5],
        }
    )

    # Calculate flags for year 2020
    res = _compute_pothole_flags(df, 2020)

    # Check out-of-year flag
    assert list(res["out_of_source_year_flag"]) == [0, 0, 1]

    # Check duplicate flags (first occurrence is 0, subsequent identical is 1)
    assert list(res["exact_duplicate_candidate_flag"]) == [0, 1, 0]
    assert list(res["spatial_temporal_duplicate_candidate_flag"]) == [0, 1, 0]


def test_compute_pavement_flags():
    df = pd.DataFrame(
        {
            "source_segment_id": [100, 100, 200],
            "iri_raw": [0.0, 4.5, 1.2],
            "etat_iri_raw": ["-", "Bon", "Moyen"],
        }
    )

    res = _compute_pavement_flags(df)

    # Missing sentinel is true only for first row (iri == 0.0 and etat_iri == '-')
    assert list(res["candidate_missing_sentinel_flag"]) == [1, 0, 0]

    # Duplicate segment id flag (first is 0, second identical is 1)
    assert list(res["duplicate_candidate_flag"]) == [0, 1, 0]


def test_road_assets_helpers():
    from scripts.preprocess_spatial_base import (
        calculate_construction_interval,
        calculate_resurfacing_interval,
        classify_date_contradiction,
    )

    # Test calculate_construction_interval
    # Precise
    dt = datetime(2020, 5, 15)
    c_min, c_max = calculate_construction_interval(dt, "DATE construction précise")
    assert c_min == datetime(2020, 5, 15).date()
    assert c_max == datetime(2020, 5, 15).date()

    # Year only
    c_min, c_max = calculate_construction_interval(dt, "DATE construction dans année courante")
    assert c_min == datetime(2020, 1, 1).date()
    assert c_max == datetime(2020, 12, 31).date()

    # Test calculate_resurfacing_interval
    # Precise
    r_min, r_max = calculate_resurfacing_interval(dt, "precise")
    assert r_min == datetime(2020, 5, 15).date()
    assert r_max == datetime(2020, 5, 15).date()

    # Imprecise year
    r_min, r_max = calculate_resurfacing_interval(dt, "imprecise_year")
    assert r_min == datetime(2020, 5, 15).date()
    assert r_max == datetime(2020, 12, 31).date()

    # Test classify_date_contradiction
    # Confirmed contradiction
    c_dt = datetime(2020, 5, 15)
    r_dt = datetime(2019, 5, 15)
    c_min_d, c_max_d = calculate_construction_interval(c_dt, "DATE construction précise")
    _, r_max_d = calculate_resurfacing_interval(r_dt, "precise")
    status, flag = classify_date_contradiction(
        "2020-05-15", "2019-05-15", "precise", "precise", c_dt, r_dt, c_min_d, c_max_d, r_max_d
    )
    assert status == "confirmed_contradiction"
    assert flag == 1

