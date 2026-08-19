"""Build Phase 8 Simplified Geometry GeoJSON script.

Procedure:
1. Loads verified spatial base: data/interim/spatial_base/geobase_32188.parquet (47,983 rows, EPSG:32188)
2. Simplifies geometries in MTM8 metric CRS using tolerance=10.0m and preserve_topology=True
3. Verifies geometry validity after simplification
4. Reprojects to EPSG:4326 (WGS 84) for Folium Leaflet rendering
5. Sorts deterministically by canonical_segment_id
6. Writes target-free attributes to data/processed/phase_8/geobase_simplified.geojson
7. Audits original & final file sizes, length changes, and join coverage against data mart
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEOBASE_SRC_PATH = PROJECT_ROOT / "data/interim/spatial_base/geobase_32188.parquet"
DATA_MART_PATH = PROJECT_ROOT / "data/processed/phase_8/dashboard_data_mart.parquet"
GEOJSON_OUT_PATH = PROJECT_ROOT / "data/processed/phase_8/geobase_simplified.geojson"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    t0 = time.time()
    print("=== BUILDING PHASE 8 SIMPLIFIED GEOMETRY GEOJSON ===")

    # 1. Load source spatial base
    src_sha = sha256_file(GEOBASE_SRC_PATH)
    gdf_src = gpd.read_parquet(GEOBASE_SRC_PATH)
    orig_rows = len(gdf_src)
    orig_crs = str(gdf_src.crs)

    print(f"Source SHA-256: {src_sha[:16]}...")
    print(f"Original Row Count: {orig_rows:,} | Original CRS: {orig_crs}")

    # Standardize canonical_segment_id string key
    gdf_src["canonical_segment_id"] = gdf_src["ID_TRC"].astype(str).str.strip()

    # Original geometry lengths in metric CRS (EPSG:32188)
    orig_lengths = gdf_src.geometry.length.values

    # 2. Simplify in metric CRS with 10m tolerance & preserve_topology=True
    gdf_simplified = gdf_src.copy()
    gdf_simplified["geometry"] = gdf_simplified.geometry.simplify(tolerance=10.0, preserve_topology=True)

    # Metric length change analysis
    simplified_lengths = gdf_simplified.geometry.length.values
    length_diffs_m = np.abs(orig_lengths - simplified_lengths)
    median_length_diff_m = float(np.median(length_diffs_m))
    max_length_diff_m = float(np.max(length_diffs_m))

    # 3. Geometry Validity Check
    is_empty_cnt = int(gdf_simplified.geometry.is_empty.sum())
    is_invalid_cnt = int((~gdf_simplified.geometry.is_valid).sum())

    print(f"Post-Simplification Null/Empty Geometries: {is_empty_cnt}")
    print(f"Post-Simplification Invalid Geometries: {is_invalid_cnt}")
    print(f"Median length change: {median_length_diff_m:.3f} m | Max length change: {max_length_diff_m:.3f} m")

    assert is_empty_cnt == 0, "Empty geometries created during simplification!"
    assert is_invalid_cnt == 0, "Invalid geometries created during simplification!"

    # 4. Transform to EPSG:4326 (WGS 84)
    gdf_wgs84 = gdf_simplified.to_crs(epsg=4326)

    # 5. Sort deterministically by canonical_segment_id
    gdf_wgs84 = gdf_wgs84.sort_values(by="canonical_segment_id").reset_index(drop=True)

    # 6. Select approved target-free attributes
    attr_cols = ["canonical_segment_id", "NOM_VOIE", "CLASSE", "geometry"]
    gdf_out = gdf_wgs84[[c for c in attr_cols if c in gdf_wgs84.columns]].copy()

    # 7. Write GeoJSON
    GEOJSON_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gdf_out.to_file(GEOJSON_OUT_PATH, driver="GeoJSON")

    out_sha = sha256_file(GEOJSON_OUT_PATH)
    out_size_mb = GEOJSON_OUT_PATH.stat().st_size / 1e6

    # 8. Audit Join Coverage against Dashboard Data Mart
    df_mart = pd.read_parquet(DATA_MART_PATH)
    mart_ids = set(df_mart["canonical_segment_id"].unique())
    geo_ids = set(gdf_out["canonical_segment_id"].unique())

    matched_ids = mart_ids.intersection(geo_ids)
    coverage_pct = (len(matched_ids) / len(mart_ids)) * 100.0

    assert len(mart_ids) == len(geo_ids) == len(matched_ids) == 47983, "Geometry join coverage mismatch!"

    t_s = time.time() - t0
    print(f"\n[OK] Simplified GeoJSON written in {t_s:.2f}s: {GEOJSON_OUT_PATH}")
    print(f"     Output SHA-256: {out_sha[:16]}...")
    print(f"     Output File Size: {out_size_mb:.2f} MB")
    print(f"     Geometry Join Coverage: {len(matched_ids):,}/47,983 ({coverage_pct:.2f}%)")


if __name__ == "__main__":
    main()
