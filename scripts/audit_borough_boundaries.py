#!/usr/bin/env python3
"""Audit Montreal administrative boundaries.

Reads the raw administrative-boundaries GeoJSON file, verifies schema,
metadata, CRS, property completeness, identifier uniqueness, and geometric properties.
"""

import argparse
import hashlib
import json
import math
import os
import sys

import shapely.geometry
import shapely.ops
import shapely.validation


def calculate_sha256(filepath):
    """Calculate the SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def audit_file_integrity(file_path):
    """Audit file existence, size, hash, and JSON parsing."""
    file_size = os.path.getsize(file_path)
    sha256_val = calculate_sha256(file_path)

    # Check UTF-8 encoding compatibility
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            f.read(1024)
        encoding_status = "Compatible with UTF-8"
    except UnicodeDecodeError:
        encoding_status = "Not UTF-8 compatible"

    # JSON parsing
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        json_status = "JSON parses successfully"
    except Exception as e:
        print(f"Error parsing JSON: {str(e)}", file=sys.stderr)
        sys.exit(1)

    root_type = data.get("type")
    root_keys = list(data.keys())
    is_feature_collection = (root_type == "FeatureCollection") and ("features" in data)

    print("=== BOUNDARY FILE INTEGRITY AUDIT ===")
    print(f"File Path: {file_path}")
    print(f"File Size: {file_size} bytes")
    print(f"SHA-256: {sha256_val}")
    print(f"Encoding: {encoding_status}")
    print(f"Parsing Status: {json_status}")
    print(f"Root Object Type: {root_type}")
    print(f"Root Keys: {root_keys}")
    print(f"FeatureCollection Valid: {is_feature_collection}")
    print("")

    if not is_feature_collection:
        print("Error: Input is not a valid FeatureCollection.", file=sys.stderr)
        sys.exit(1)

    return data


def audit_crs(data):
    """Audit Coordinate Reference System (CRS) declaration."""
    crs_decl = data.get("crs")
    crs_present = crs_decl is not None
    crs_name = ""
    resolves_epsg_32188 = False

    if crs_present:
        if isinstance(crs_decl, dict) and "properties" in crs_decl:
            crs_name = crs_decl["properties"].get("name", "")
            if "32188" in crs_name:
                resolves_epsg_32188 = True

    print("=== COORDINATE REFERENCE SYSTEM (CRS) AUDIT ===")
    print(f"CRS Present: {crs_present}")
    print(f"Exact CRS Declaration: {crs_decl}")
    print(f"CRS Name/URI: {crs_name}")
    print(f"Resolves to EPSG:32188: {resolves_epsg_32188}")
    print("Project Working CRS Status: UNDECIDED (Phase 2 constraint)")
    print("Source CRS: NAD83 / MTM zone 8 (urn:ogc:def:crs:EPSG::32188)")
    print("Candidate working CRS: EPSG:32188 or EPSG:2950")
    print("")


def audit_features_schema(features):
    """Audit features count and schema property completeness."""
    properties = sorted(
        {
            k
            for f in features
            if "properties" in f and f["properties"]
            for k in f["properties"].keys()
        }
    )

    print("=== FEATURE AND SCHEMA AUDIT ===")
    print(f"Total Feature Count: {len(features)}")
    print(f"Properties Found: {properties}")
    print("")

    print("--- Property Completeness (Missingness) ---")
    for p_name in properties:
        null_count = 0
        blank_count = 0
        populated_count = 0
        type_dist = {}
        for f in features:
            p_val = f["properties"].get(p_name) if "properties" in f else None
            if p_val is None:
                null_count += 1
            elif str(p_val).strip() == "":
                blank_count += 1
            else:
                populated_count += 1
                t_str = type(p_val).__name__
                type_dist[t_str] = type_dist.get(t_str, 0) + 1

        print(f"Property: {p_name}")
        print(f"  Null count: {null_count}")
        print(f"  Blank count: {blank_count}")
        print(f"  Populated count: {populated_count}")
        print(f"  Value type distribution: {type_dist}")

    # DATEMODIF distribution
    datemodif_vals = [
        str(f["properties"]["DATEMODIF"])
        for f in features
        if "properties" in f and f["properties"].get("DATEMODIF") is not None
    ]
    print("\nDATEMODIF Parseability:")
    print(f"  Distinct values: {set(datemodif_vals)}")
    print("")


def audit_identifiers(features):
    """Audit property identifiers unique-check."""
    print("=== IDENTIFIER UNIQUE-CHECK AUDIT ===")
    ids_to_check = ["CODEID", "CODEMAMH", "CODE_3C", "NUM", "ABREV", "NOM", "NOM_OFFICIEL"]
    for identifier in ids_to_check:
        vals = []
        for f in features:
            if "properties" in f:
                vals.append(f["properties"].get(identifier))
        null_count = sum(1 for v in vals if v is None)
        blank_count = sum(1 for v in vals if str(v).strip() == "")
        unique_vals = set(vals)
        dups = len(vals) - len(unique_vals)
        print(f"Identifier: {identifier}")
        print(f"  Null count: {null_count}")
        print(f"  Blank count: {blank_count}")
        print(f"  Unique count: {len(unique_vals)}")
        print(f"  Duplicate count: {dups}")
        if dups > 0:
            dup_items = {x for x in vals if vals.count(x) > 1}
            print(f"  Duplicate values: {dup_items}")
    print("")


def audit_entity_types(features):
    """Audit TYPE frequencies and borough vs related-municipality distinction."""
    print("=== ENTITY-TYPE AUDIT ===")
    types_found = {}
    names_by_type = {}
    for f in features:
        p = f.get("properties", {})
        t = p.get("TYPE")
        name = p.get("NOM")
        types_found[t] = types_found.get(t, 0) + 1
        names_by_type.setdefault(t, []).append(name)

    print(f"Entity TYPE Frequencies: {types_found}")
    for t, names in names_by_type.items():
        print(f"Type '{t}': Count={len(names)}")
        print(f"  Names: {sorted(names)}")
    print("")


def _check_rings(coords, g_type):
    """Helper to check unclosed rings, insufficient coordinates, and non-finite coords."""
    polys = coords if g_type == "MultiPolygon" else ([coords] if g_type == "Polygon" else [])
    polygon_count = len(polys)
    ring_count = 0
    unclosed_rings = 0
    insufficient_positions = 0
    non_finite_coords = 0

    for poly in polys:
        for ring in poly:
            ring_count += 1
            if len(ring) < 4:
                insufficient_positions += 1
            if ring and ring[0] != ring[-1]:
                unclosed_rings += 1
            for pt in ring:
                if not all(isinstance(val, (int, float)) and math.isfinite(val) for val in pt):
                    non_finite_coords += 1

    return polygon_count, ring_count, unclosed_rings, insufficient_positions, non_finite_coords


def _check_overlaps(geoms):
    """Helper to compute overlapping polygon pairs in memory."""
    overlaps = []
    for i in range(len(geoms)):
        _, name1, geom1 = geoms[i]
        if geom1 is None:
            continue
        for j in range(i + 1, len(geoms)):
            _, name2, geom2 = geoms[j]
            if geom2 is None:
                continue
            if geom1.intersects(geom2):
                inter = geom1.intersection(geom2)
                if not inter.is_empty and inter.area > 1e-3:
                    overlaps.append((name1, name2, inter.area))
    return overlaps


def _process_feature_geometry(idx, f):
    """Parse shapes from GeoJSON feature, handling missingness and errors."""
    name = f["properties"].get("NOM") if "properties" in f else f"Feature_{idx}"
    g_json = f.get("geometry")
    if g_json is None:
        return name, None, None, None
    g_type = g_json.get("type")
    try:
        geom = shapely.geometry.shape(g_json)
        return name, geom, g_type, None
    except Exception as e:
        return name, None, g_type, str(e)


def _extract_geometries(features):
    """Loop through features and compile geometric parameters."""
    geom_types = {}
    null_geoms = 0
    empty_geoms = 0
    invalid_geoms = []
    valid_geoms = 0
    polygon_count = 0
    ring_count = 0
    unclosed_rings = 0
    insufficient_positions = 0
    non_finite_coords = 0
    zero_area_geoms = 0
    coordinate_bounds = [float("inf"), float("inf"), float("-inf"), float("-inf")]
    total_area = 0.0
    feature_areas = []
    geoms = []

    for idx, f in enumerate(features):
        name, geom, g_type, err = _process_feature_geometry(idx, f)
        if err:
            invalid_geoms.append((idx, name, err))
            geoms.append((idx, name, None))
            continue
        if geom is None:
            null_geoms += 1
            geoms.append((idx, name, None))
            continue

        geom_types[g_type] = geom_types.get(g_type, 0) + 1
        geoms.append((idx, name, geom))

        if geom.is_empty:
            empty_geoms += 1
            continue
        if not geom.is_valid:
            reason = shapely.validation.explain_validity(geom)
            invalid_geoms.append((idx, name, reason))
        else:
            valid_geoms += 1

        # Bounds check
        bx1, by1, bx2, by2 = geom.bounds
        coordinate_bounds[0] = min(coordinate_bounds[0], bx1)
        coordinate_bounds[1] = min(coordinate_bounds[1], by1)
        coordinate_bounds[2] = max(coordinate_bounds[2], bx2)
        coordinate_bounds[3] = max(coordinate_bounds[3], by2)

        # Area
        f_area = geom.area
        total_area += f_area
        feature_areas.append((name, f_area))
        if f_area == 0.0:
            zero_area_geoms += 1

        # Ring and Coordinate check
        coords = f.get("geometry", {}).get("coordinates", [])
        p_c, r_c, u_r, i_p, n_f = _check_rings(coords, g_type)
        polygon_count += p_c
        ring_count += r_c
        unclosed_rings += u_r
        insufficient_positions += i_p
        non_finite_coords += n_f

    return (
        geoms,
        geom_types,
        null_geoms,
        empty_geoms,
        invalid_geoms,
        valid_geoms,
        polygon_count,
        ring_count,
        unclosed_rings,
        insufficient_positions,
        non_finite_coords,
        zero_area_geoms,
        coordinate_bounds,
        total_area,
        feature_areas,
    )


def audit_geometries(features):
    """Audit geometry shapes, component polygons, areas, and intersections."""
    print("=== GEOMETRY AND TOPOLOGY AUDIT ===")
    (
        geoms,
        geom_types,
        null_geoms,
        empty_geoms,
        invalid_geoms,
        valid_geoms,
        polygon_count,
        ring_count,
        unclosed_rings,
        insufficient_positions,
        non_finite_coords,
        zero_area_geoms,
        coordinate_bounds,
        total_area,
        feature_areas,
    ) = _extract_geometries(features)

    # Duplicate geometries check
    geom_wkb_list = [(name, geom.wkb) for (_, name, geom) in geoms if geom is not None]
    dup_geoms_count = 0
    seen_wkb = set()
    for _, wkb in geom_wkb_list:
        if wkb in seen_wkb:
            dup_geoms_count += 1
        else:
            seen_wkb.add(wkb)

    # Overlaps check
    overlaps = _check_overlaps(geoms)

    print(f"Geometry Types Found: {geom_types}")
    print(f"Null Geometries: {null_geoms}")
    print(f"Empty Geometries: {empty_geoms}")
    print(f"Invalid Geometries Count: {len(invalid_geoms)}")
    for idx, name, reason in invalid_geoms:
        print(f"  Feature [{idx}] {name} invalid: {reason}")
    print(f"Valid Geometries Count: {valid_geoms}")
    print(f"Total Component Polygons: {polygon_count}")
    print(f"Total Component Rings: {ring_count}")
    print(f"Unclosed Rings: {unclosed_rings}")
    print(f"Rings with Insufficient Positions (<4): {insufficient_positions}")
    print(f"Non-finite Coordinate Values: {non_finite_coords}")
    print(f"Zero-area Geometries: {zero_area_geoms}")
    print(f"Duplicate Geometries Count: {dup_geoms_count}")
    print(
        f"Coordinate Bounds: Min X={coordinate_bounds[0]}, Min Y={coordinate_bounds[1]}, Max X={coordinate_bounds[2]}, Max Y={coordinate_bounds[3]}"
    )
    print(f"Total Area: {total_area:.2f} m^2")
    if feature_areas:
        sorted_areas = sorted(feature_areas, key=lambda x: x[1])
        print(f"  Smallest Area Outlier: {sorted_areas[0][0]} ({sorted_areas[0][1]:.2f} m^2)")
        print(f"  Largest Area Outlier: {sorted_areas[-1][0]} ({sorted_areas[-1][1]:.2f} m^2)")
    print(f"Overlapping Polygon Pairs Count: {len(overlaps)}")
    for n1, n2, area in sorted(overlaps, key=lambda x: x[2], reverse=True):
        print(f"  {n1} overlaps with {n2} by {area:.4f} m^2")
    print("")


def audit_warnings():
    """Print project coverage, temporal limitations, and official CRS warnings."""
    print("=== COVERAGE AND TEMPORAL LIMITATIONS WARNING ===")
    print("1. This is a current administrative-boundary snapshot (updated late 2023).")
    print("2. Administrative boundaries may change over time due to municipal reorganizations.")
    print("3. Historical road-repair observations in this project extend back to 2016.")
    print("4. DATEMODIF does not provide a complete historical version history of boundaries.")
    print(
        "5. Applying current boundary polygons to older historical road segments may introduce temporal geographic mismatches."
    )
    print(
        "6. Any spatial joining of these boundaries to historical data must record this temporal constraint as an active limitation."
    )
    print("")

    print("=== OFFICIAL CRS METHODOLOGY WARNING ===")
    print(
        "1. The Ville de Montréal states that administrative boundaries were constituted in NAD83 / MTM Zone 8."
    )
    print(
        "2. The portal recommends using this native reference system to preserve coordinate homogeneity."
    )
    print(
        "3. Alternative coordinate reference systems (e.g. WGS 84 GeoJSON transformations) have not been validated by the city's geomatics division."
    )
    print(
        "4. This finding does not automatically approve EPSG:32188 as the final project working CRS. The final working CRS remains UNDECIDED."
    )
    print("")


def audit_geojson(file_path):
    """Orchestrate the full audit workflow."""
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}", file=sys.stderr)
        return 1

    data = audit_file_integrity(file_path)
    features = data.get("features", [])

    audit_crs(data)
    audit_features_schema(features)
    audit_identifiers(features)
    audit_entity_types(features)
    audit_geometries(features)
    audit_warnings()

    return 0


def main():  # noqa: C901
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Audit Montreal administrative boundaries GeoJSON."
    )
    parser.add_argument(
        "geojson_path", help="Path to the raw administrative-boundaries GeoJSON file."
    )
    args = parser.parse_args()

    sys.exit(audit_geojson(args.geojson_path))


if __name__ == "__main__":
    main()
