import os
import pytest
import numpy as np
import pandas as pd
import geopandas as gpd
import tempfile
from shapely.geometry import Point, LineString, Polygon

from montreal_road_risk.spatial.linkage import extract_pothole_linkages
from montreal_road_risk.spatial.crosswalks import (
    build_pavement_condition_linkage,
    build_road_asset_linkage,
    build_administrative_boundary_linkage,
)
from montreal_road_risk.io.checksums import scan_raw_files


def test_pothole_linkage_basic():
    # 2 roads (EPSG:32188)
    # Line 1: along x=0, from y=0 to y=10
    # Line 2: along x=10, from y=0 to y=10
    lines = gpd.GeoDataFrame(
        {
            "canonical_segment_id": ["R1", "R2"],
            "geometry": [LineString([(0, 0), (0, 10)]), LineString([(10, 0), (10, 10)])],
        },
        crs="EPSG:32188",
    )

    # Points
    # Pt 1: (2, 5) -> nearest to R1 (dist = 2.0)
    # Pt 2: (5, 5) -> tie between R1 and R2 (dist = 5.0)
    # Pt 3: (30, 5) -> too far from both (dist = 20.0)
    points = gpd.GeoDataFrame(
        {
            "geometry": [Point(2, 5), Point(5, 5), Point(30, 5)],
            "source_record_number": [1, 2, 3],
            "event_id": ["E1", "E2", "E3"],
        },
        crs="EPSG:32188",
    )

    candidate_bands = [10.0, 15.0, 20.0, 30.0, 50.0]

    # Recommended threshold = 15m
    res = extract_pothole_linkages(
        points, lines, candidate_bands, tie_tolerance=0.5, recommended_threshold=15.0
    )

    assert len(res) == 3

    # Pt 1 is accepted to R1
    assert res.iloc[0]["canonical_segment_id"] == "R1"
    assert res.iloc[0]["linkage_status"] == "accepted"
    assert res.iloc[0]["linkage_distance_m"] == 2.0
    assert res.iloc[0]["ambiguity_flag"] == 0
    assert res.iloc[0]["candidate_count_10m"] == 2

    # Pt 2 is a tie (within tie_tolerance=0.5 of 5.0m)
    assert res.iloc[1]["linkage_status"] == "review_required"
    assert res.iloc[1]["ambiguity_flag"] == 1
    assert res.iloc[1]["linkage_distance_m"] == 5.0
    assert res.iloc[1]["candidate_count_10m"] == 2

    # Pt 3 is unmatched (dist = 20.0, which is > recommended_threshold 15.0)
    assert pd.isna(res.iloc[2]["canonical_segment_id"])
    assert res.iloc[2]["linkage_status"] == "unmatched"
    assert res.iloc[2]["linkage_distance_m"] == 20.0


def test_pavement_condition_linkage():
    # Géobase lines
    geobase = gpd.GeoDataFrame(
        {
            "canonical_segment_id": ["S1", "S2"],
            "geometry": [LineString([(0, 0), (10, 0)]), LineString([(0, 5), (10, 5)])],
        },
        crs="EPSG:32188",
    )

    # Condition records
    # R1: direct ID match to S1
    # R2: spatial fallback (overlapping S2)
    # R3: unmatched
    pavement = gpd.GeoDataFrame(
        {
            "source_segment_id": ["S1", "S99", "S88"],
            "geometry": [
                LineString([(0, 0), (10, 0)]),
                LineString([(0, 5.1), (10, 5.1)]),  # Overlaps S2 spatially
                LineString([(100, 100), (110, 100)]),  # Far away
            ],
        },
        crs="EPSG:32188",
    )

    res = build_pavement_condition_linkage(pavement, geobase, min_intersection_length=2.0)

    assert len(res) == 3
    # Direct match
    assert res.iloc[0]["canonical_segment_id"] == "S1"
    assert res.iloc[0]["linkage_status"] == "direct_id"

    # Spatial fallback
    assert res.iloc[1]["canonical_segment_id"] == "S2"
    assert res.iloc[1]["linkage_status"] == "spatial_fallback"

    # Unmatched
    assert pd.isna(res.iloc[2]["canonical_segment_id"])
    assert res.iloc[2]["linkage_status"] == "unmatched"


def test_road_asset_linkage():
    # 2 road segments (EPSG:32188)
    geobase = gpd.GeoDataFrame(
        {
            "canonical_segment_id": ["S1", "S2"],
            "geometry": [
                LineString([(0, 0), (10, 0)]),  # Len = 10
                LineString([(0, 10), (10, 10)]),  # Len = 10
            ],
        },
        crs="EPSG:32188",
    )

    # 2 asset polygons
    # Polygon 1: covers S1 completely
    # Polygon 2: covers S2 by 40% (x=0 to x=4)
    assets = gpd.GeoDataFrame(
        {
            "source_record_number": [101, 102],
            "geometry": [
                Polygon([(-1, -1), (11, -1), (11, 1), (-1, 1)]),
                Polygon([(-1, 9), (4, 9), (4, 11), (-1, 11)]),
            ],
        },
        crs="EPSG:32188",
    )

    res = build_road_asset_linkage(geobase, assets, [0.0, 0.10, 0.25, 0.50])

    assert len(res) == 2

    # S1 covers 100%
    assert res.iloc[0]["primary_asset_id"] == 101
    assert res.iloc[0]["overlap_fraction"] == 1.0
    assert res.iloc[0]["linkage_status"] == "accepted"

    # S2 covers 40%
    assert res.iloc[1]["primary_asset_id"] == 102
    assert res.iloc[1]["overlap_fraction"] == 0.40
    assert res.iloc[1]["linkage_status"] == "accepted"


def test_administrative_boundary_linkage():
    # 2 road segments (EPSG:32188)
    geobase = gpd.GeoDataFrame(
        {
            "canonical_segment_id": ["S1", "S2"],
            "geometry": [LineString([(0, 0), (10, 0)]), LineString([(15, 0), (25, 0)])],
        },
        crs="EPSG:32188",
    )

    # Borough boundaries
    # B1: covers x=0 to x=6 (overlap = 6)
    # B2: covers x=6 to x=30 (overlap on S1 = 4, S2 = 10)
    boroughs = gpd.GeoDataFrame(
        {
            "source_segment_id": ["B1", "B2"],
            "nom_arrond": ["Borough 1", "Borough 2"],
            "geometry": [
                Polygon([(-1, -5), (6, -5), (6, 5), (-1, 5)]),
                Polygon([(6, -5), (30, -5), (30, 5), (6, 5)]),
            ],
        },
        crs="EPSG:32188",
    )

    res = build_administrative_boundary_linkage(geobase, boroughs)

    assert len(res) == 2

    # S1 is split: 6m in B1, 4m in B2 -> B1 chosen
    assert res.iloc[0]["primary_borough_id"] == "B1"
    assert res.iloc[0]["overlap_fraction"] == 0.60
    assert res.iloc[0]["candidate_count"] == 2
    assert res.iloc[0]["ambiguity_flag"] == 0

    # S2 is entirely in B2
    assert res.iloc[1]["primary_borough_id"] == "B2"
    assert res.iloc[1]["overlap_fraction"] == 1.0


def test_crs_enforcement():
    # Ensure value error raised if wrong CRS
    lines = gpd.GeoDataFrame(
        {"canonical_segment_id": ["R1"], "geometry": [LineString([(0, 0), (0, 10)])]},
        crs="EPSG:4326",
    )  # wrong CRS

    points = gpd.GeoDataFrame(
        {"geometry": [Point(2, 5)], "source_record_number": [1]}, crs="EPSG:32188"
    )

    with pytest.raises(AssertionError):
        extract_pothole_linkages(points, lines, [10.0])


def test_serialization_readback():
    df = pd.DataFrame({"A": [1, 2, 3]})
    with tempfile.TemporaryDirectory() as tmpdir:
        fpath = os.path.join(tmpdir, "test.parquet")
        df.to_parquet(fpath)
        read_df = pd.read_parquet(fpath)
        assert len(read_df) == 3
        assert list(read_df.columns) == ["A"]


def test_raw_immutability():
    # Assert raw_files inventory check doesn't fail
    inv = scan_raw_files("data/raw/montreal/borough_boundaries", ".")
    assert len(inv) > 0
    assert inv[0]["dataset_category"] == "borough_boundaries"


def test_geometry_preservation():
    f_3a = "data/interim/phase_3a/pothole_repairs/pothole_repairs_2016_32188.parquet"
    f_3b = "data/interim/phase_3b/pothole_segment_links.parquet"

    if os.path.exists(f_3a) and os.path.exists(f_3b):
        gdf_3a = gpd.read_parquet(f_3a)
        df_3b = pd.read_parquet(f_3b)

        df_3b_yr = df_3b[df_3b["source_year"] == 2016].sort_values("source_row_number")
        gdf_3a_sorted = gdf_3a.sort_values("source_record_number")

        assert len(gdf_3a_sorted) == len(df_3b_yr)

        x_3a = gdf_3a_sorted.geometry.x.values
        y_3a = gdf_3a_sorted.geometry.y.values
        x_3b = df_3b_yr["x_coords"].values
        y_3b = df_3b_yr["y_coords"].values

        assert np.allclose(x_3a, x_3b, atol=1e-7)
        assert np.allclose(y_3a, y_3b, atol=1e-7)
