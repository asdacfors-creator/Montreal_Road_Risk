#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime

import pyproj
import shapely.geometry
from shapely.ops import transform


def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def check_zip_member_safety(filename):
    if filename.startswith("/") or ".." in filename:
        raise ValueError(f"Unsafe archive member path: {filename}")

    _, ext = os.path.splitext(filename.lower())
    if ext in [".exe", ".msi", ".bat", ".cmd", ".sh"]:
        raise ValueError(f"Prohibited executable member: {filename}")

    if ext in [".zip", ".tar", ".gz", ".rar"]:
        raise ValueError(f"Unexpected nested archive: {filename}")


def verify_zip(zip_path):
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Not a genuine ZIP archive")

    with zipfile.ZipFile(zip_path) as z:
        test_res = z.testzip()
        if test_res is not None:
            raise ValueError(f"ZIP integrity test failed: member {test_res} is corrupt")

        infolist = z.infolist()
        member_count = len(infolist)
        if member_count != 1:
            raise ValueError(f"Expected exactly 1 archive member, found {member_count}")

        member = infolist[0]
        filename = member.filename
        check_zip_member_safety(filename)

        # Expected baseline validation
        expected_name = "VOI_CHAUSSEE_S_C22_GeoJSON.json"
        if filename != expected_name:
            raise ValueError(f"Expected member name {expected_name}, got {filename}")

        expected_uncompressed_size = 159981330
        if member.file_size != expected_uncompressed_size:
            raise ValueError(
                f"Expected member uncompressed size {expected_uncompressed_size}, got {member.file_size}"
            )

        # Calculate SHA-256 of the member
        data = z.read(filename)
        inner_sha = hashlib.sha256(data).hexdigest()
        expected_inner_sha = "9b6e19c47e85e8337a4ded215ddab8a322c63d9f57cd86ccc55d32037651c35d"
        if inner_sha != expected_inner_sha:
            raise ValueError(f"Expected inner SHA-256 {expected_inner_sha}, got {inner_sha}")

        # Verify JSON start
        data_start = data[:100].strip()
        if not (data_start.startswith(b"{") or data_start.startswith(b"[")):
            raise ValueError("Member does not start with valid JSON/GeoJSON structure")

        return {
            "archive_size": os.path.getsize(zip_path),
            "archive_sha256": calculate_sha256(zip_path),
            "member_name": filename,
            "member_uncompressed_size": member.file_size,
            "member_sha256": inner_sha,
        }


def parse_geojson(zip_path, member_name):
    with zipfile.ZipFile(zip_path) as z:
        with z.open(member_name) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON parse error: {str(e)}") from e

    if not isinstance(data, dict):
        raise ValueError("Top-level JSON is not an object")

    top_type = data.get("type")
    if top_type != "FeatureCollection":
        raise ValueError(f"Expected top-level object type 'FeatureCollection', got {top_type}")

    dataset_name = data.get("name")
    crs_exists = "crs" in data
    features = data.get("features", [])

    if not isinstance(features, list):
        raise ValueError("GeoJSON 'features' member must be a list")

    # Check property schema consistency
    first_schema = None
    all_schemas_match = True
    for feat in features:
        props = feat.get("properties")
        if not isinstance(props, dict):
            raise ValueError("Feature 'properties' is not a dictionary")
        schema_keys = frozenset(props.keys())
        if first_schema is None:
            first_schema = schema_keys
        elif schema_keys != first_schema:
            all_schemas_match = False

    return {
        "top_level_type": top_type,
        "dataset_name": dataset_name,
        "crs_exists": crs_exists,
        "feature_count": len(features),
        "all_schemas_match": all_schemas_match,
        "property_count": len(first_schema) if first_schema else 0,
        "property_names": list(first_schema) if first_schema else [],
        "features": features,
    }


def audit_geometries(features):
    geom_types = {}
    null_geom = 0
    empty_geom = 0
    invalid_geom = 0
    valid_geom = 0

    # Coordinate range bounding box
    minx, miny, maxx, maxy = float("inf"), float("inf"), float("-inf"), float("-inf")

    unique_geoms = set()
    exact_duplicates = 0
    duplicate_id_geom = 0
    seen_id_geom = set()
    zero_area_count = 0

    # Setup transformer for EPSG:2950 projected area checks (temporary memory-only audit)
    wgs84 = pyproj.CRS("EPSG:4326")
    mtm8 = pyproj.CRS("EPSG:2950")
    project = pyproj.Transformer.from_crs(wgs84, mtm8, always_xy=True).transform

    for feat in features:
        geom_dict = feat.get("geometry")
        props = feat.get("properties", {})
        asset_id = props.get("ID_VOI_CHAUSSEE_AGR")

        if geom_dict is None:
            null_geom += 1
            continue

        try:
            geom = shapely.geometry.shape(geom_dict)
        except Exception:
            invalid_geom += 1
            continue

        if geom.is_empty:
            empty_geom += 1
            continue

        g_type = geom.geom_type
        geom_types[g_type] = geom_types.get(g_type, 0) + 1

        # Check validity
        if not geom.is_valid:
            invalid_geom += 1
        else:
            valid_geom += 1

        # Bounds check
        bounds = geom.bounds
        minx = min(minx, bounds[0])
        miny = min(miny, bounds[1])
        maxx = max(maxx, bounds[2])
        maxy = max(maxy, bounds[3])

        # Check area
        try:
            projected_geom = transform(project, geom)
            if projected_geom.area < 1e-7:
                zero_area_count += 1
        except Exception:
            pass

        # Duplicate geometries check
        geom_wkb = geom.wkb
        if geom_wkb in unique_geoms:
            exact_duplicates += 1
        else:
            unique_geoms.add(geom_wkb)

        # Duplicate asset ID + geometry check
        id_geom_pair = (asset_id, geom_wkb)
        if id_geom_pair in seen_id_geom:
            duplicate_id_geom += 1
        else:
            seen_id_geom.add(id_geom_pair)

    # Check if bounds are inside broad Montréal region
    montreal_box_ok = (
        (45.0 <= miny <= 46.0)
        and (-74.5 <= minx <= -73.0)
        and (45.0 <= maxy <= 46.0)
        and (-74.5 <= maxx <= -73.0)
    )

    return {
        "geom_types": geom_types,
        "null_geometries": null_geom,
        "empty_geometries": empty_geom,
        "invalid_geometries": invalid_geom,
        "valid_geometries": valid_geom,
        "bbox": [minx, miny, maxx, maxy],
        "montreal_box_ok": montreal_box_ok,
        "exact_duplicate_geometries": exact_duplicates,
        "duplicate_id_geom_combinations": duplicate_id_geom,
        "zero_area_projected_polygons": zero_area_count,
    }


def audit_attributes(features):
    fields = [
        "ID_VOI_CHAUSSEE_AGR",
        "CATEGORIECHAUSSEE_REF",
        "DATECONSTRUCTION",
        "DATECONSTRUCTIONPREC_REF",
        "DATERESURFACAGE",
        "MATERIAUCHAUSSEE_REF",
        "POSITION_REF",
        "PROPRIETAIRE_REF",
        "TYPEFONDATION_REF",
        "TYPEUSAGECYCLABLE_REF",
        "UTILISATION_REF",
        "DATE_VERSION",
    ]

    results = {}
    feature_count = len(features)

    for field in fields:
        null_count = 0
        blank_count = 0
        non_null_vals = []
        unique_vals = set()

        for feat in features:
            props = feat.get("properties", {})
            val = props.get(field)

            if val is None:
                null_count += 1
            else:
                s_val = str(val).strip()
                if s_val == "":
                    blank_count += 1
                else:
                    non_null_vals.append(val)
                    unique_vals.add(val)

        missing_pct = (
            ((null_count + blank_count) / feature_count) * 100 if feature_count > 0 else 0.0
        )

        # Get representatives
        rep_list = list(unique_vals)[:5]

        results[field] = {
            "data_type": str(type(non_null_vals[0])) if non_null_vals else "None",
            "non_null_count": len(non_null_vals),
            "null_count": null_count,
            "blank_count": blank_count,
            "missing_percentage": missing_pct,
            "unique_count": len(unique_vals),
            "representatives": rep_list,
        }
    return results


def parse_compact_date(val):
    if not isinstance(val, str) or len(val) != 14:
        raise ValueError("Invalid date string format length")
    try:
        return datetime.strptime(val, "%Y%m%d%H%M%S")
    except ValueError as e:
        raise ValueError(f"Unparseable date string: {val}") from e


def audit_construction_date(props, stats, ver_dt):
    con_str = props.get("DATECONSTRUCTION")
    con_dt = None
    if not con_str:
        stats["construction_missing"] += 1
    else:
        try:
            con_dt = parse_compact_date(con_str)
            stats["construction_parseable"] += 1
            if ver_dt and con_dt > ver_dt:
                stats["date_logic_anomalies"]["future_construction_relative_to_version"] += 1
        except ValueError:
            stats["construction_missing"] += 1
            stats["date_logic_anomalies"]["invalid_date_strings"] += 1
    return con_dt


def audit_resurfacing_date(props, stats, ver_dt, con_dt):
    res_str = props.get("DATERESURFACAGE")
    res_dt = None
    if not res_str:
        stats["resurfacing_missing"] += 1
    else:
        try:
            res_dt = parse_compact_date(res_str)
            stats["resurfacing_parseable"] += 1
            if ver_dt and res_dt > ver_dt:
                stats["date_logic_anomalies"]["future_resurfacing_relative_to_version"] += 1
        except ValueError:
            stats["resurfacing_missing"] += 1
            stats["date_logic_anomalies"]["invalid_date_strings"] += 1

    if con_dt and res_dt:
        if res_dt < con_dt:
            stats["date_logic_anomalies"]["resurfacing_before_construction"] += 1
        if con_dt > res_dt:
            stats["date_logic_anomalies"]["construction_after_resurfacing"] += 1
    return res_dt


def audit_single_feature_dates(props, stats, construction_dates, resurfacing_dates, version_dates):
    ver_str = props.get("DATE_VERSION")
    ver_dt = None
    if ver_str:
        try:
            ver_dt = parse_compact_date(ver_str)
            version_dates.add(ver_dt.date().isoformat())
        except ValueError:
            stats["date_logic_anomalies"]["invalid_date_strings"] += 1

    con_dt = audit_construction_date(props, stats, ver_dt)
    if con_dt:
        construction_dates.append(con_dt)

    prec = props.get("DATECONSTRUCTIONPREC_REF")
    if prec:
        stats["precision_distribution"][prec] = stats["precision_distribution"].get(prec, 0) + 1

    res_dt = audit_resurfacing_date(props, stats, ver_dt, con_dt)
    if res_dt:
        resurfacing_dates.append(res_dt)


def audit_dates(features):
    stats = {
        "construction_parseable": 0,
        "construction_missing": 0,
        "resurfacing_parseable": 0,
        "resurfacing_missing": 0,
        "precision_distribution": {},
        "date_logic_anomalies": {
            "invalid_date_strings": 0,
            "future_construction_relative_to_version": 0,
            "future_resurfacing_relative_to_version": 0,
            "resurfacing_before_construction": 0,
            "construction_after_resurfacing": 0,
        },
    }
    construction_dates = []
    resurfacing_dates = []
    version_dates = set()

    for feat in features:
        props = feat.get("properties", {})
        audit_single_feature_dates(
            props, stats, construction_dates, resurfacing_dates, version_dates
        )

    earliest_con = min(construction_dates).date().isoformat() if construction_dates else None
    latest_con = max(construction_dates).date().isoformat() if construction_dates else None

    earliest_res = min(resurfacing_dates).date().isoformat() if resurfacing_dates else None
    latest_res = max(resurfacing_dates).date().isoformat() if resurfacing_dates else None

    return {
        "construction_parseable": stats["construction_parseable"],
        "construction_missing": stats["construction_missing"],
        "earliest_construction": earliest_con,
        "latest_construction": latest_con,
        "precision_distribution": stats["precision_distribution"],
        "resurfacing_parseable": stats["resurfacing_parseable"],
        "resurfacing_missing": stats["resurfacing_missing"],
        "earliest_resurfacing": earliest_res,
        "latest_resurfacing": latest_res,
        "version_dates": list(version_dates),
        "date_logic_anomalies": stats["date_logic_anomalies"],
    }


def read_reference_rows(f, seen_rows):
    reader = csv.reader(f)
    try:
        header = next(reader)
    except StopIteration as e:
        raise ValueError("Reference CSV is empty") from e

    if header != ["ATTRIBUT", "REFERENCE"]:
        raise ValueError(f"Expected header ['ATTRIBUT', 'REFERENCE'], got {header}")

    rows = []
    duplicate_rows = 0
    for row in reader:
        if not row:
            continue
        if len(row) != 2:
            raise ValueError(f"Expected exactly 2 columns, got row with {len(row)} values: {row}")
        row_tup = tuple(row)
        if row_tup in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(row_tup)
        rows.append(row_tup)
    return header, rows, duplicate_rows


def audit_reference_csv(csv_path):
    # Determine encoding and BOM
    with open(csv_path, "rb") as f:
        raw_head = f.read(10)
        has_bom = raw_head.startswith(b"\xef\xbb\xbf")

    encoding = "utf-8-sig" if has_bom else "utf-8"

    blank_rows = 0
    seen_rows = set()

    with open(csv_path, mode="r", encoding=encoding) as f:
        # Check raw lines for completely blank lines
        lines = f.readlines()
        for line in lines:
            if line.strip() == "":
                blank_rows += 1

        f.seek(0)
        header, rows, duplicate_rows = read_reference_rows(f, seen_rows)

    # Group reference domains
    ref_domains = {}
    for attr, ref in rows:
        if attr not in ref_domains:
            ref_domains[attr] = set()
        ref_domains[attr].add(ref)

    return {
        "encoding": "UTF-8 with BOM" if has_bom else "UTF-8",
        "bom_present": has_bom,
        "delimiter": ",",
        "header": header,
        "row_count": len(rows) + 1,  # including header
        "data_row_count": len(rows),
        "blank_rows": blank_rows,
        "duplicate_rows": duplicate_rows,
        "ref_domains": ref_domains,
    }


def check_reference_coverage(features, ref_domains):
    # Mapping definitions
    mapping_alias = {
        "CATEGORIECHAUSSEE_REF": "CATEGORIECHAUSSEE_REF",
        "DATECONSTRUCTIONPREC_REF": "DATECONSTRUCTIONPREC_REF",
        "MATERIAUCHAUSSEE_REF": "MATERIAU_REF",
        "POSITION_REF": "POSITION_REF",
        "PROPRIETAIRE_REF": "PROPRIETAIRE_REF",
        "TYPEFONDATION_REF": "TYPEFONDATION_REF",
        "TYPEUSAGECYCLABLE_REF": "TYPEUSAGECYCLABLE_REF",
        "UTILISATION_REF": "UTILISATION_REF",
    }

    results = {}
    for geojson_field, csv_attr in mapping_alias.items():
        csv_domain = ref_domains.get(csv_attr, set())
        unmapped_vals = set()
        used_vals = set()

        for feat in features:
            val = feat.get("properties", {}).get(geojson_field)
            if val is not None:
                val_str = str(val)
                if val_str not in csv_domain:
                    unmapped_vals.add(val_str)
                else:
                    used_vals.add(val_str)

        unused_vals = csv_domain - used_vals
        results[geojson_field] = {
            "csv_attribute": csv_attr,
            "unmapped_observed": list(unmapped_vals),
            "documented_but_unused": list(unused_vals),
            "csv_domain_size": len(csv_domain),
        }

    return results


def main():  # noqa: C901
    parser = argparse.ArgumentParser(description="Read-only Road Assets Pavement Data Auditor")
    parser.add_argument("--archive", required=True, help="Path to raw ZIP GeoJSON archive")
    parser.add_argument("--reference", required=True, help="Path to reference CSV dictionary")
    args = parser.parse_args()

    if not os.path.exists(args.archive):
        print(f"Archive path not found: {args.archive}")
        sys.exit(1)
    if not os.path.exists(args.reference):
        print(f"Reference CSV path not found: {args.reference}")
        sys.exit(1)

    try:
        # 1. ZIP Verify
        print("A. ZIP Archive Verification...")
        zip_res = verify_zip(args.archive)
        print("ZIP integrity checks passed.")

        # 2. GeoJSON Parse
        print("\nB. GeoJSON Structure Analysis...")
        geojson_res = parse_geojson(args.archive, zip_res["member_name"])
        print(f"GeoJSON type: {geojson_res['top_level_type']}")
        print(f"Dataset name: {geojson_res['dataset_name']}")
        print(f"Feature count: {geojson_res['feature_count']}")

        # 3. Geometry Audit
        print("\nC. Geometry Quality Audit...")
        geom_res = audit_geometries(geojson_res["features"])
        print(f"Geometry types: {geom_res['geom_types']}")
        print(f"Null geometries: {geom_res['null_geometries']}")
        print(f"Invalid geometries: {geom_res['invalid_geometries']}")
        print(f"Exact duplicates: {geom_res['exact_duplicate_geometries']}")

        # 4. Attribute Audit
        print("\nD. Attributes Verification...")
        attr_res = audit_attributes(geojson_res["features"])
        for field, info in attr_res.items():
            print(
                f"  Field {field}: type={info['data_type']}, missing={info['missing_percentage']:.2f}%, unique={info['unique_count']}"
            )

        # 5. Date Audit
        print("\nE. Date Audit...")
        date_res = audit_dates(geojson_res["features"])
        print(
            f"Construction parsed: {date_res['construction_parseable']}, min: {date_res['earliest_construction']}, max: {date_res['latest_construction']}"
        )
        print(
            f"Resurfacing parsed: {date_res['resurfacing_parseable']}, missing count: {date_res['resurfacing_missing']}"
        )
        print(f"Date logic anomalies: {date_res['date_logic_anomalies']}")

        # 6. Reference CSV Audit
        print("\nF. Reference CSV Audit...")
        csv_res = audit_reference_csv(args.reference)
        print(f"Row count: {csv_res['row_count']}, duplicates: {csv_res['duplicate_rows']}")

        # 7. Reference Coverage Audit
        print("\nG. Reference Coverage Check...")
        coverage_res = check_reference_coverage(geojson_res["features"], csv_res["ref_domains"])
        for field, info in coverage_res.items():
            print(f"Field {field} -> CSV Attribute {info['csv_attribute']}:")
            print(f"  Unmapped observed: {info['unmapped_observed']}")
            print(f"  Unused documented: {len(info['documented_but_unused'])} values")

        print("\nAudit successfully completed.")
        sys.exit(0)
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"\nAudit failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
