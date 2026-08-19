import os

import geopandas as gpd
import pandas as pd


def build_static_features(config, project_root):
    """
    Extracts static features for all canonical segments in the Geobase,
    joining with boundary crosswalks and administrative boundary properties.
    """
    geobase_path = os.path.join(project_root, config["inputs"]["geobase"])
    boundary_cross_path = os.path.join(project_root, config["inputs"]["road_boundary_links"])
    admin_bounds_path = os.path.join(project_root, config["inputs"]["boundaries"])

    print(f"Loading static Base Geobase from: {geobase_path}")
    geobase_df = pd.read_parquet(geobase_path)

    # 1. Compute segment length in meters (MTM 8 is a conformal projected system in meters)
    # We load geometry and get length. Since geobase is a parquet, if it's stored as WKB or GeoPandas
    if "geometry" in geobase_df.columns:
        # Convert to GeoDataFrame if not already
        if not isinstance(geobase_df, gpd.GeoDataFrame):
            # Try reading with geopandas
            geobase_gdf = gpd.read_parquet(geobase_path)
        else:
            geobase_gdf = geobase_df
        segment_lengths = geobase_gdf.geometry.length
    else:
        raise ValueError("Geometry column not found in Geobase!")

    # 2. Extract Geobase static attributes
    # Canonical road segment ID is in 'segment_id' or 'ID_TRC'. Let's check what ID is used.
    # In the plan, segment_id = canonical representation of ID_TRC.
    # Let's map 'segment_id' = geobase_df['ID_TRC'] or the column name 'canonical_segment_id'.
    # In the diagnostic run, geobase_32188 has 'ID_TRC'. Let's rename ID_TRC to canonical_segment_id.
    static_df = pd.DataFrame({
        "canonical_segment_id": geobase_gdf["ID_TRC"].astype(str),
        "functional_road_class": geobase_gdf["CLASSE"].fillna(-1).astype(int),
        "road_type": geobase_gdf["TYP_VOIE"].fillna("not_stated").astype(str),
        "road_category": geobase_gdf["LIE_VOIE"].fillna("not_stated").astype(str),
        "segment_length_m": segment_lengths.astype(float)
    })

    # 3. Join with road boundary crosswalk
    print(f"Loading road boundary crosswalk from: {boundary_cross_path}")
    cross_df = pd.read_parquet(boundary_cross_path)
    # cross_df has canonical_segment_id, primary_borough_id, overlap_length_m, etc.
    # Convert keys to string for safe join
    cross_df["canonical_segment_id"] = cross_df["canonical_segment_id"].astype(str)

    # Select necessary columns
    cross_cols = [
        "canonical_segment_id",
        "primary_borough_id",
        "candidate_count",
        "ambiguity_flag"
    ]
    cross_sub = cross_df[cross_cols].copy()

    # Merge with static properties
    static_df = static_df.merge(cross_sub, on="canonical_segment_id", how="left")

    # 4. Join with admin boundary details to get NOM_OFFICIEL and TYPE (Arrondissement/Ville liee)
    print(f"Loading administrative boundary properties from: {admin_bounds_path}")
    admin_df = pd.read_parquet(admin_bounds_path)

    # Ensure types match
    admin_df["CODEID"] = admin_df["CODEID"].astype(float)
    static_df["primary_borough_id"] = static_df["primary_borough_id"].astype(float)

    admin_sub = admin_df[["CODEID", "NOM_OFFICIEL", "TYPE"]].copy()
    admin_sub = admin_sub.rename(columns={
        "NOM_OFFICIEL": "official_administrative_name",
        "TYPE": "administrative_category"
    })

    static_df = static_df.merge(admin_sub, left_on="primary_borough_id", right_on="CODEID", how="left")
    static_df = static_df.drop(columns=["CODEID"])

    # Standardize the administrative category text to Arrondissement / Ville liée / unresolved
    def clean_category(val):
        if pd.isna(val):
            return "unresolved"
        val_str = str(val).strip().lower()
        if "arrondissement" in val_str:
            return "Arrondissement"
        elif "ville" in val_str:
            return "Ville liée"
        return "unresolved"

    static_df["administrative_category"] = static_df["administrative_category"].apply(clean_category)
    static_df["official_administrative_name"] = static_df["official_administrative_name"].fillna("unresolved").astype(str)

    # Fill remaining crosswalk flags/fields for missing/unmatched
    static_df["primary_borough_id"] = static_df["primary_borough_id"].fillna(-1).astype(int)
    static_df["boundary_candidate_count"] = static_df["candidate_count"].fillna(0).astype(int)
    static_df["boundary_crossing_flag"] = (static_df["boundary_candidate_count"] > 1).astype(int)
    static_df["boundary_ambiguity_flag"] = static_df["ambiguity_flag"].fillna(0).astype(int)
    static_df["unmatched_boundary_flag"] = (static_df["primary_borough_id"] == -1).astype(int)

    static_df = static_df.drop(columns=["candidate_count", "ambiguity_flag"])

    # Audit unmatched segment ID 4017818
    seg_4017818 = static_df[static_df["canonical_segment_id"] == "4017818"]
    if len(seg_4017818) > 0:
        assert int(seg_4017818["unmatched_boundary_flag"].iloc[0]) == 1
        assert int(seg_4017818["primary_borough_id"].iloc[0]) == -1
        assert seg_4017818["administrative_category"].iloc[0] == "unresolved"
        print("Segment 4017818 checked and remains correctly unmatched.")

    # Unique check
    assert static_df["canonical_segment_id"].is_unique, "canonical_segment_id is not unique in static features!"
    print(f"Generated static features for {len(static_df)} road segments.")
    return static_df
