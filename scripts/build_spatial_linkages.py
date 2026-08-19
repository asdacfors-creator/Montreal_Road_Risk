#!/usr/bin/env python3
"""Phase 3B Spatial Linkage Integration Script.

Loads Phase 3A interim datasets, constructs spatial linkages and crosswalks,
computes QA metrics across multiple candidate thresholds, and saves Parquet outputs.
"""

import json
import os
import sys

import geopandas as gpd
import pandas as pd

# Import custom modules
from montreal_road_risk.io.checksums import scan_raw_files
from montreal_road_risk.spatial.crosswalks import (
    build_administrative_boundary_linkage,
    build_pavement_condition_linkage,
    build_road_asset_linkage,
)
from montreal_road_risk.spatial.linkage import extract_pothole_linkages

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "spatial_linkage.json")
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "outputs", "evidence", "phase_3b")


def _run_pothole_linkage(config, geobase_gdf, working_crs, config_version, qa_summary):
    """Helper to snap potholes and save results."""
    print("Processing pothole repairs spatial linkages...")
    pothole_years = config["inputs"]["potholes_years"]
    pothole_pattern = config["inputs"]["potholes_pattern"]
    tie_tolerance = config["pothole_linkage"]["tie_tolerance_m"]
    candidate_bands = config["pothole_linkage"]["candidate_distance_bands_m"]

    all_pothole_links = []

    for yr in pothole_years:
        fpath = os.path.join(PROJECT_ROOT, pothole_pattern.format(YEAR=yr))
        if not os.path.exists(fpath):
            print(f"Warning: Pothole file not found for year {yr} at {fpath}")
            continue

        potholes_gdf = gpd.read_parquet(fpath)
        assert potholes_gdf.crs.to_string() == working_crs, f"Potholes {yr} CRS must be {working_crs}"

        links = extract_pothole_linkages(
            potholes_gdf,
            geobase_gdf,
            candidate_bands,
            tie_tolerance=tie_tolerance,
            recommended_threshold=20.0,
        )

        links["source_dataset"] = "mechanized_pothole_repairs"
        links["source_file"] = os.path.basename(fpath)
        links["source_year"] = yr
        links["source_row_number"] = potholes_gdf["source_record_number"].values
        links["configuration_version"] = config_version

        # Preserve geometric coordinates (X, Y)
        links["x_coords"] = potholes_gdf.geometry.x.values
        links["y_coords"] = potholes_gdf.geometry.y.values

        all_pothole_links.append(links)

        # QA stats per year
        total_potholes = len(links)
        accepted_cnt = (links["linkage_status"] == "accepted").sum()
        review_cnt = (links["linkage_status"] == "review_required").sum()
        unmatched_cnt = (links["linkage_status"] == "unmatched").sum()
        tie_cnt = (links["ambiguity_flag"] == 1).sum()

        qa_summary["pothole_metrics"][str(yr)] = {
            "total_records": int(total_potholes),
            "accepted_count": int(accepted_cnt),
            "review_required_count": int(review_cnt),
            "unmatched_count": int(unmatched_cnt),
            "tie_count": int(tie_cnt),
            "match_rate": float(accepted_cnt / total_potholes) if total_potholes > 0 else 0.0,
        }

    combined_potholes = pd.concat(all_pothole_links, ignore_index=True)

    # Calculate global distance band counts and stats
    total_combined = len(combined_potholes)
    qa_summary["pothole_metrics"]["overall"] = {
        "total_records": int(total_combined),
        "distance_percentiles": {
            "50th": float(combined_potholes["linkage_distance_m"].dropna().median()),
            "90th": float(combined_potholes["linkage_distance_m"].dropna().quantile(0.90)),
            "95th": float(combined_potholes["linkage_distance_m"].dropna().quantile(0.95)),
            "max": float(combined_potholes["linkage_distance_m"].dropna().max()),
        },
        "candidate_counts": {
            "10m": int((combined_potholes["candidate_count_10m"] > 0).sum()),
            "15m": int((combined_potholes["candidate_count_15m"] > 0).sum()),
            "20m": int((combined_potholes["candidate_count_20m"] > 0).sum()),
            "30m": int((combined_potholes["candidate_count_30m"] > 0).sum()),
            "50m": int((combined_potholes["candidate_count_50m"] > 0).sum()),
        },
        "tie_count": int((combined_potholes["ambiguity_flag"] == 1).sum()),
        "accepted_count": int((combined_potholes["linkage_status"] == "accepted").sum()),
        "review_required_count": int((combined_potholes["linkage_status"] == "review_required").sum()),
        "unmatched_count": int((combined_potholes["linkage_status"] == "unmatched").sum()),
    }

    # Save combined potholes links
    pothole_out_path = os.path.join(PROJECT_ROOT, config["outputs"]["pothole_links"])
    os.makedirs(os.path.dirname(pothole_out_path), exist_ok=True)
    combined_potholes.to_parquet(pothole_out_path)
    return combined_potholes, pothole_out_path


def _run_pavement_linkage(config, geobase_gdf, working_crs, config_version, qa_summary):
    """Helper to snap pavement campaigns and save results."""
    print("Processing pavement condition campaign linkages...")
    pavement_campaigns = config["inputs"]["pavement_campaigns"]
    pavement_pattern = config["inputs"]["pavement_pattern"]

    all_pavement_links = []

    for camp in pavement_campaigns:
        fpath = os.path.join(PROJECT_ROOT, pavement_pattern.format(YEAR=camp))
        if not os.path.exists(fpath):
            print(f"Warning: Pavement condition file not found for campaign {camp} at {fpath}")
            continue

        try:
            pavement_gdf_or_df = gpd.read_parquet(fpath)
        except ValueError:
            pavement_gdf_or_df = pd.read_parquet(fpath)

        # Call pavement linkage (includes direct-ID matching and spatial fallback)
        links = build_pavement_condition_linkage(pavement_gdf_or_df, geobase_gdf)

        # Add provenance
        links["source_file"] = os.path.basename(fpath)
        links["source_year"] = -1
        links["campaign_label"] = camp
        links["configuration_version"] = config_version

        all_pavement_links.append(links)

        # QA stats
        tot = len(links)
        direct_cnt = (links["linkage_status"] == "direct_id").sum()
        spatial_cnt = (links["linkage_status"] == "spatial_fallback").sum()
        ambig_cnt = (links["linkage_status"] == "ambiguous").sum()
        unmatched_cnt = (links["linkage_status"] == "unmatched").sum()

        qa_summary["pavement_condition_metrics"][camp] = {
            "total_records": int(tot),
            "direct_id_count": int(direct_cnt),
            "spatial_fallback_count": int(spatial_cnt),
            "ambiguous_count": int(ambig_cnt),
            "unmatched_count": int(unmatched_cnt),
            "direct_id_match_rate": float(direct_cnt / tot) if tot > 0 else 0.0,
            "overall_match_rate": float((direct_cnt + spatial_cnt) / tot) if tot > 0 else 0.0,
        }

    combined_pavement = pd.concat(all_pavement_links, ignore_index=True)
    for col in combined_pavement.columns:
        if combined_pavement[col].dtype == "object" and col != "geometry":
            combined_pavement[col] = combined_pavement[col].apply(
                lambda x: x.isoformat() if hasattr(x, "isoformat") else x
            )
            combined_pavement[col] = combined_pavement[col].astype(str).replace("nan", None).replace("<NA>", None)
    combined_pavement_cols = [
        "source_dataset",
        "source_file",
        "source_year",
        "campaign_label",
        "source_record_number",
        "source_segment_id",
        "canonical_segment_id",
        "linkage_method",
        "linkage_status",
        "candidate_count",
        "linkage_distance_m",
        "ambiguity_flag",
        "configuration_version",
    ]
    # Check if there are other columns to preserve
    for col in combined_pavement.columns:
        if col not in combined_pavement_cols:
            combined_pavement_cols.append(col)

    combined_pavement = combined_pavement[combined_pavement_cols]
    combined_pavement = gpd.GeoDataFrame(combined_pavement, geometry="geometry", crs=working_crs)

    pavement_out_path = os.path.join(PROJECT_ROOT, config["outputs"]["pavement_links"])
    combined_pavement.to_parquet(pavement_out_path)
    return combined_pavement, pavement_out_path


def _run_road_asset_linkage(
    config, geobase_gdf, road_assets_gdf, road_assets_path, config_version, qa_summary
):
    """Helper to build road asset crosswalk and save results."""
    print("Processing road-asset polygon-to-line linkages...")
    asset_overlap_levels = config["road_asset_linkage"]["candidate_overlap_fractions"]

    road_asset_links = build_road_asset_linkage(geobase_gdf, road_assets_gdf, asset_overlap_levels)

    # Add provenance details
    road_asset_links["source_dataset"] = "road_assets_pavement"
    road_asset_links["source_file"] = os.path.basename(road_assets_path)
    road_asset_links["source_year"] = -1
    road_asset_links["source_record_number"] = road_asset_links.index + 1
    road_asset_links["configuration_version"] = config_version

    road_asset_out_path = os.path.join(PROJECT_ROOT, config["outputs"]["road_asset_crosswalk"])
    road_asset_links.to_parquet(road_asset_out_path)

    # QA Stats for assets at multiple overlap levels (0.0, 0.10, 0.25, 0.50)
    for lvl in asset_overlap_levels:
        lvl_str = f"overlap_ge_{int(lvl * 100)}%"
        # Calculate matched correctly (overlap fraction >= lvl and primary_asset_id not na)
        matched_mask = (road_asset_links["overlap_fraction"] >= lvl) & road_asset_links["primary_asset_id"].notna()
        matched_cnt = matched_mask.sum()
        qa_summary["road_asset_metrics"][lvl_str] = {
            "candidate_threshold": float(lvl),
            "matched_count": int(matched_cnt),
            "unmatched_count": int(len(road_asset_links) - matched_cnt),
            "match_rate": float(matched_cnt / len(road_asset_links)),
        }

    qa_summary["road_asset_metrics"]["overall"] = {
        "total_segments": len(road_asset_links),
        "matched_with_asset_count": int((~road_asset_links["primary_asset_id"].isna()).sum()),
        "average_overlap_fraction": float(road_asset_links["overlap_fraction"].mean()),
        "max_overlap_fraction": float(road_asset_links["overlap_fraction"].max()),
        "tie_count": int((road_asset_links["ambiguity_flag"] == 1).sum()),
    }
    return road_asset_links, road_asset_out_path


def _run_boundary_linkage(config, geobase_gdf, borough_gdf, boundaries_path, config_version, qa_summary):
    """Helper to build arrondissement boundaries crosswalk and save results."""
    print("Processing administrative boundary linkages...")
    boundary_links = build_administrative_boundary_linkage(geobase_gdf, borough_gdf)

    # Add provenance details
    boundary_links["source_dataset"] = "borough_boundaries"
    boundary_links["source_file"] = os.path.basename(boundaries_path)
    boundary_links["source_year"] = -1
    boundary_links["source_record_number"] = boundary_links.index + 1
    boundary_links["configuration_version"] = config_version

    boundary_out_path = os.path.join(PROJECT_ROOT, config["outputs"]["road_boundary_crosswalk"])
    boundary_links.to_parquet(boundary_out_path)

    # QA Stats - boundary crossing segments
    crossing_mask = boundary_links["candidate_count"] > 1
    crossing_cnt = crossing_mask.sum()
    unmatched_b_cnt = (boundary_links["linkage_status"] == "unmatched").sum()

    # Descriptive comparison with ARR_GCH and ARR_DRT from Geobase
    def clean_name(n):
        if not n or pd.isna(n):
            return ""
        s = str(n).strip().lower()
        s = (
            s.replace("l'arrondissement de ", "")
            .replace("l'arrondissement ", "")
            .replace("arrondissement de ", "")
            .replace("arrondissement ", "")
        )
        s = s.replace("é", "e").replace("è", "e").replace("à", "a").replace("ç", "c").replace("-", " ")
        return s

    geobase_arr = geobase_gdf["ARR_GCH"].fillna("").apply(clean_name)
    assigned_arr = boundary_links["primary_borough_name"].fillna("").apply(clean_name)
    agree_mask = (geobase_arr == assigned_arr) & (geobase_arr != "")
    agree_cnt = agree_mask.sum()

    qa_summary["boundary_metrics"] = {
        "total_segments": len(boundary_links),
        "boundary_crossing_segments_count": int(crossing_cnt),
        "unmatched_segments_count": int(unmatched_b_cnt),
        "agreement_with_arr_gch_count": int(agree_cnt),
        "agreement_rate": (
            float(agree_cnt / (geobase_arr != "").sum()) if (geobase_arr != "").sum() > 0 else 0.0
        ),
    }
    return boundary_links, boundary_out_path


def _verify_roundtrip(
    pothole_out_path,
    combined_potholes,
    pavement_out_path,
    combined_pavement,
    road_asset_out_path,
    road_asset_links,
    boundary_out_path,
    boundary_links,
):
    """Helper to verify serialization read-back."""
    print("Verifying serialization roundtrip read-back...")
    read_potholes = pd.read_parquet(pothole_out_path)
    assert len(read_potholes) == len(combined_potholes), "Potholes size mismatch on read-back"
    assert list(read_potholes.columns) == list(combined_potholes.columns), "Potholes schema mismatch on read-back"

    read_pavement = pd.read_parquet(pavement_out_path)
    assert len(read_pavement) == len(combined_pavement), "Pavement size mismatch on read-back"
    assert list(read_pavement.columns) == list(combined_pavement.columns), "Pavement schema mismatch on read-back"

    read_asset = pd.read_parquet(road_asset_out_path)
    assert len(read_asset) == len(road_asset_links), "Asset size mismatch on read-back"
    assert list(read_asset.columns) == list(road_asset_links.columns), "Asset schema mismatch on read-back"

    read_boundary = pd.read_parquet(boundary_out_path)
    assert len(read_boundary) == len(boundary_links), "Boundary size mismatch on read-back"
    assert list(read_boundary.columns) == list(boundary_links.columns), "Boundary schema mismatch on read-back"


def main():  # noqa: C901
    print("Initializing Phase 3B spatial linkage pipeline...")

    # 1. Load config
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    working_crs = config["approved_working_crs"]
    config_version = config["version"]

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # 2. Raw file immutability pre-run snapshot
    print("Scanning raw files for pre-run integrity snapshot...")
    pre_inventory = scan_raw_files(RAW_DIR, PROJECT_ROOT)
    pre_snap_path = os.path.join(EVIDENCE_DIR, "raw_immutability_before.json")
    with open(pre_snap_path, "w") as f:
        json.dump(pre_inventory, f, indent=2)

    # 3. Load Phase 3A interim anchor datasets
    print("Loading anchor datasets...")
    geobase_path = os.path.join(PROJECT_ROOT, config["inputs"]["geobase"])
    boundaries_path = os.path.join(PROJECT_ROOT, config["inputs"]["borough_boundaries"])
    road_assets_path = os.path.join(PROJECT_ROOT, config["inputs"]["road_assets"])

    geobase_gdf = gpd.read_parquet(geobase_path)
    geobase_gdf["canonical_segment_id"] = geobase_gdf["ID_TRC"]
    borough_gdf = gpd.read_parquet(boundaries_path)
    road_assets_gdf = gpd.read_parquet(road_assets_path)

    # Assert CRS
    assert geobase_gdf.crs.to_string() == working_crs, f"Géobase CRS must be {working_crs}"
    assert borough_gdf.crs.to_string() == working_crs, f"Borough boundaries CRS must be {working_crs}"
    assert road_assets_gdf.crs.to_string() == working_crs, f"Road assets CRS must be {working_crs}"

    # QA Metrics dictionary
    qa_summary = {
        "config_version": config_version,
        "working_crs": working_crs,
        "pothole_metrics": {},
        "pavement_condition_metrics": {},
        "road_asset_metrics": {},
        "boundary_metrics": {},
    }

    # 4. Run linkages
    combined_potholes, pothole_out_path = _run_pothole_linkage(
        config, geobase_gdf, working_crs, config_version, qa_summary
    )

    combined_pavement, pavement_out_path = _run_pavement_linkage(
        config, geobase_gdf, working_crs, config_version, qa_summary
    )

    road_asset_links, road_asset_out_path = _run_road_asset_linkage(
        config, geobase_gdf, road_assets_gdf, road_assets_path, config_version, qa_summary
    )

    boundary_links, boundary_out_path = _run_boundary_linkage(
        config, geobase_gdf, borough_gdf, boundaries_path, config_version, qa_summary
    )

    # 5. Serialization Roundtrip Integrity Check
    _verify_roundtrip(
        pothole_out_path,
        combined_potholes,
        pavement_out_path,
        combined_pavement,
        road_asset_out_path,
        road_asset_links,
        boundary_out_path,
        boundary_links,
    )

    # 6. Output QA Summary JSON
    qa_summary_path = os.path.join(PROJECT_ROOT, config["outputs"]["qa_summary"])
    with open(qa_summary_path, "w") as f:
        json.dump(qa_summary, f, indent=2)
    print(f"QA Summary exported to {qa_summary_path}")

    # 7. Generate run manifest
    run_manifest = {
        "pipeline": "Phase 3B Spatial Linkage and Crosswalks",
        "timestamp": pd.Timestamp.now().isoformat(),
        "config_version": config_version,
        "working_crs": working_crs,
        "input_files": {
            "geobase": geobase_path,
            "borough_boundaries": boundaries_path,
            "road_assets": road_assets_path,
        },
        "output_files": {
            "pothole_links": pothole_out_path,
            "pavement_links": pavement_out_path,
            "road_asset_crosswalk": road_asset_out_path,
            "road_boundary_crosswalk": boundary_out_path,
            "qa_summary": qa_summary_path,
        },
    }

    manifest_path = os.path.join(PROJECT_ROOT, config["outputs"]["run_manifest"])
    with open(manifest_path, "w") as f:
        json.dump(run_manifest, f, indent=2)
    print(f"Run manifest generated at {manifest_path}")

    # 8. Raw file immutability post-run check
    print("Checking post-run raw file immutability...")
    post_inventory = scan_raw_files(RAW_DIR, PROJECT_ROOT)
    post_snap_path = os.path.join(EVIDENCE_DIR, "raw_immutability_after.json")
    with open(post_snap_path, "w") as f:
        json.dump(post_inventory, f, indent=2)

    # Check that pre and post are identical
    if pre_inventory == post_inventory:
        print("Success: Raw files remain completely unchanged.")
    else:
        print("CRITICAL WARNING: Raw files have been modified during execution!")
        sys.exit(1)

    print("Phase 3B spatial linkage build completed successfully.")


if __name__ == "__main__":
    main()
