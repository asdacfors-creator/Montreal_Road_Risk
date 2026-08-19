#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime

import shapely.geometry
import shapely.wkb


def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def normalize_header_key(key):
    """Normalize headers in memory only."""
    k = key.strip().replace(" ", "_")
    replacements = {"é": "e", "è": "e", "à": "a", "ù": "u", "ç": "c"}
    for old, new in replacements.items():
        k = k.replace(old, new)
    return k


def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            pass
    try:
        clean = date_str.strip().split()[0]
        return datetime.strptime(clean, "%Y-%m-%d")
    except Exception:
        return None


def unpack_gpkg_geom(binary_data):
    """Unpack OGC GeoPackage geometry binary header to extract standard WKB."""
    if not binary_data or len(binary_data) < 8:
        return None
    magic = binary_data[0:2]
    if magic != b"GP":
        return None
    flags = binary_data[3]
    envelope_indicator = (flags & 0x0E) >> 1
    header_size = 8
    if envelope_indicator == 1:
        header_size = 40
    elif envelope_indicator == 2:
        header_size = 56
    elif envelope_indicator == 3:
        header_size = 72
    wkb_data = binary_data[header_size:]
    return wkb_data


def get_percentile(data, pct):
    if not data:
        return None
    sorted_data = sorted(data)
    n = len(sorted_data)
    idx = (n - 1) * pct / 100.0
    floor_idx = int(idx)
    ceil_idx = min(floor_idx + 1, n - 1)
    if floor_idx == ceil_idx:
        return sorted_data[floor_idx]
    return sorted_data[floor_idx] + (sorted_data[ceil_idx] - sorted_data[floor_idx]) * (
        idx - floor_idx
    )


def calculate_numeric_stats(vals):
    if not vals:
        return {
            "min": None,
            "max": None,
            "median": None,
            "mean": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
        }
    n = len(vals)
    s_vals = sorted(vals)
    mean_val = sum(vals) / n
    return {
        "min": s_vals[0],
        "max": s_vals[-1],
        "median": get_percentile(vals, 50),
        "mean": mean_val,
        "p10": get_percentile(vals, 10),
        "p25": get_percentile(vals, 25),
        "p50": get_percentile(vals, 50),
        "p75": get_percentile(vals, 75),
        "p90": get_percentile(vals, 90),
    }


def audit_pci(pci, etat_pci, stats):
    if pci is None or str(pci).strip() in ("", "None", "-"):
        stats["pci_missing"] += 1
    else:
        try:
            p_val = float(pci)
            stats["pci_vals"].append(p_val)
            stats["pci_parsed"] += 1
            if p_val < 0 or p_val > 100:
                stats["pci_out_of_bounds"] += 1
            if not etat_pci or str(etat_pci).strip() in ("", "None", "-"):
                stats["pci_index_exists_but_state_missing"] += 1
        except ValueError:
            stats["pci_missing"] += 1

    if (
        (pci is None or str(pci).strip() in ("", "None", "-"))
        and etat_pci
        and str(etat_pci).strip() not in ("", "None", "-")
    ):
        stats["pci_state_exists_but_index_missing"] += 1


def audit_iri(iri, etat_iri, stats):
    if iri is None or str(iri).strip() in ("", "None", "-"):
        stats["iri_missing"] += 1
    else:
        try:
            i_val = float(iri)
            stats["iri_parsed"] += 1
            if i_val == 0.0 and str(etat_iri).strip() == "-":
                stats["iri_sentinel_candidates"] += 1
            else:
                stats["iri_vals"].append(i_val)
                if i_val < 0:
                    stats["iri_negative"] += 1
                if i_val > 15.0:
                    stats["iri_extreme_count"] += 1
            if not etat_iri or str(etat_iri).strip() in ("", "None", "-"):
                stats["iri_index_exists_but_state_missing"] += 1
        except ValueError:
            stats["iri_missing"] += 1

    if (
        (iri is None or str(iri).strip() in ("", "None", "-"))
        and etat_iri
        and str(etat_iri).strip() not in ("", "None", "-")
    ):
        stats["iri_state_exists_but_index_missing"] += 1


def audit_pci_iri_ranges_and_sentinels(norm_props, stats):
    pci = norm_props.get("Indice_PCI")
    etat_pci = norm_props.get("Etat_PCI")
    iri = norm_props.get("Indice_IRI")
    etat_iri = norm_props.get("Etat_IRI")
    audit_pci(pci, etat_pci, stats)
    audit_iri(iri, etat_iri, stats)


def update_value_distributions(norm_props, stats):
    e_pci = norm_props.get("Etat_PCI")
    e_iri = norm_props.get("Etat_IRI")
    if e_pci:
        stats["etat_pci_dist"][e_pci] = stats["etat_pci_dist"].get(e_pci, 0) + 1
    if e_iri:
        stats["etat_iri_dist"][e_iri] = stats["etat_iri_dist"].get(e_iri, 0) + 1

    de_val = norm_props.get("De")
    if de_val is None or str(de_val).strip() == "":
        stats["de_missing"] += 1
    a_val = norm_props.get("A")
    if a_val is None or str(a_val).strip() == "":
        stats["a_missing"] += 1


def process_feature_record(norm_props, stats, ids, dates):
    trc = norm_props.get("ID_TRC")
    if trc is not None:
        try:
            ids.append(int(trc))
        except ValueError:
            pass

    dt_str = norm_props.get("DateReleve")
    dt = parse_date(dt_str)
    if dt:
        dates.append(dt)

    audit_pci_iri_ranges_and_sentinels(norm_props, stats)
    update_value_distributions(norm_props, stats)


def analyze_attribute_schema(norm_props, schema_stats):
    for k, v in norm_props.items():
        if k not in schema_stats:
            schema_stats[k] = {
                "types": set(),
                "nulls": 0,
                "blanks": 0,
                "total": 0,
                "uniques": set(),
            }
        s = schema_stats[k]
        s["total"] += 1
        if v is None:
            s["nulls"] += 1
        else:
            s["types"].add(type(v).__name__)
            s_val = str(v).strip()
            if s_val == "":
                s["blanks"] += 1
            else:
                s["uniques"].add(v)


def read_and_audit_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as e:
            raise ValueError("CSV file is empty") from e
        rows = list(reader)

    width = len(header)
    for idx, r in enumerate(rows):
        if len(r) != width:
            raise ValueError(f"Row {idx + 2} width mismatch: expected {width}, got {len(r)}")

    norm_header = [normalize_header_key(h) for h in header]

    features_props = []
    for r in rows:
        props = {}
        for h, val in zip(norm_header, r, strict=False):
            if h in ("ID_TRC", "Longueur", "Indice_PCI", "Indice_IRI"):
                try:
                    props[h] = float(val) if "." in val else int(val)
                except ValueError:
                    props[h] = val
            else:
                props[h] = val
        features_props.append(props)

    return {
        "format": "CSV",
        "header": header,
        "norm_header": norm_header,
        "physical_rows": len(rows) + 1,
        "features_props": features_props,
        "geoms": None,
        "crs": "No source geometry is included in this selected campaign resource.",
    }


def read_and_audit_geojson(path):
    with open(path, "r", encoding="windows-1252") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {str(e)}") from e

    if not isinstance(data, dict):
        raise ValueError("Top-level JSON is not an object")
    if data.get("type") != "FeatureCollection":
        raise ValueError("Expected top-level object type 'FeatureCollection'")

    crs_info = data.get("crs", {})
    crs_name = crs_info.get("properties", {}).get("name") if crs_info else None
    features = data.get("features", [])

    features_props = []
    geoms = []
    for feat in features:
        props = feat.get("properties", {})
        norm_props = {normalize_header_key(k): v for k, v in props.items()}
        features_props.append(norm_props)
        geoms.append(feat.get("geometry"))

    return {
        "format": "GeoJSON",
        "header": list(features[0].get("properties", {}).keys()) if features else [],
        "norm_header": [normalize_header_key(k) for k in features[0].get("properties", {}).keys()]
        if features
        else [],
        "physical_rows": len(features),
        "features_props": features_props,
        "geoms": geoms,
        "crs": crs_name or "urn:ogc:def:crs:OGC:1.3:CRS84",
    }


def read_and_audit_gpkg(path):
    conn = None
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        if cursor.fetchone()[0] != "ok":
            raise ValueError("GeoPackage PRAGMA integrity_check failed")
        cursor.execute("PRAGMA application_id;")
        app_id = cursor.fetchone()[0]
        cursor.execute("PRAGMA user_version;")
        user_ver = cursor.fetchone()[0]
        if app_id != 0x47504B47:
            raise ValueError(f"Expected GeoPackage application_id 0x47504B47, got {hex(app_id)}")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        main_table = [
            t
            for t in tables
            if "auscultation" in t.lower() or "chauss" in t.lower() and "rtree" not in t.lower()
        ][0]

        cursor.execute(f"PRAGMA table_info('{main_table}');")
        cols = cursor.fetchall()
        header = [c[1] for c in cols if c[1] not in ("fid", "geom")]
        norm_header = [normalize_header_key(h) for h in header]

        cursor.execute(f"SELECT * FROM '{main_table}';")
        col_names = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        cursor.execute(
            "SELECT srs_id FROM gpkg_geometry_columns WHERE table_name=?;", (main_table,)
        )
        srs_res = cursor.fetchone()
        srs_id = srs_res[0] if srs_res else 4326

        cursor.execute("SELECT srs_name FROM gpkg_spatial_ref_sys WHERE srs_id=?;", (srs_id,))
        srs_name_res = cursor.fetchone()
        srs_name = srs_name_res[0] if srs_name_res else "EPSG:4326"

        features_props = []
        geoms = []
        for r in rows:
            props = {}
            geom_binary = None
            for col_name, val in zip(col_names, r, strict=False):
                if col_name == "fid":
                    continue
                if col_name == "geom":
                    geom_binary = val
                    continue
                norm_k = normalize_header_key(col_name)
                props[norm_k] = val
            features_props.append(props)
            geoms.append(geom_binary)

        return {
            "format": "GeoPackage",
            "header": header,
            "norm_header": norm_header,
            "physical_rows": len(rows),
            "features_props": features_props,
            "geoms": geoms,
            "crs": f"EPSG:{srs_id}" if srs_name == "EPSG:4326" else f"EPSG:{srs_id} ({srs_name})",
            "app_id": app_id,
            "user_ver": user_ver,
            "main_table": main_table,
        }
    except sqlite3.Error as e:
        raise ValueError(f"SQLite database error: {str(e)}") from e
    finally:
        if conn:
            conn.close()


def process_single_geometry(
    gb, idx, format_type, features_props, geom_stats, unique_wkbs, feature_strs
):
    props_str = json.dumps(features_props[idx], sort_keys=True)
    if gb is None:
        geom_stats["null_geom"] += 1
        return None

    wkb_data = unpack_gpkg_geom(gb) if format_type == "GeoPackage" else None
    try:
        if format_type == "GeoPackage":
            geom = shapely.wkb.loads(wkb_data) if wkb_data else None
        else:
            geom = shapely.geometry.shape(gb)
    except Exception:
        geom_stats["invalid_geom"] += 1
        return None

    if geom is None:
        geom_stats["null_geom"] += 1
        return None
    if geom.is_empty:
        geom_stats["empty_geom"] += 1
        return None

    g_type = geom.geom_type
    geom_stats["geom_types"][g_type] = geom_stats["geom_types"].get(g_type, 0) + 1

    if not geom.is_valid:
        geom_stats["invalid_geom"] += 1
    else:
        geom_stats["valid_geom"] += 1

    bounds = geom.bounds

    geom_wkb = geom.wkb
    if geom_wkb in unique_wkbs:
        geom_stats["exact_duplicate_geom"] += 1
    else:
        unique_wkbs.add(geom_wkb)

    geom_coords_str = geom.wkt
    feature_strs.append(props_str + "||" + geom_coords_str)
    return bounds


def audit_geometries(geoms, features_props, format_type):
    geom_stats = {
        "geom_types": {},
        "null_geom": 0,
        "empty_geom": 0,
        "invalid_geom": 0,
        "valid_geom": 0,
        "exact_duplicate_geom": 0,
        "exact_duplicate_features": 0,
        "bbox": None,
    }
    if not geoms:
        return geom_stats

    minx, miny, maxx, maxy = float("inf"), float("inf"), float("-inf"), float("-inf")
    unique_wkbs = set()
    feature_strs = []

    for idx, gb in enumerate(geoms):
        bounds = process_single_geometry(
            gb, idx, format_type, features_props, geom_stats, unique_wkbs, feature_strs
        )
        if bounds:
            minx = min(minx, bounds[0])
            miny = min(miny, bounds[1])
            maxx = max(maxx, bounds[2])
            maxy = max(maxy, bounds[3])

    if minx != float("inf"):
        geom_stats["bbox"] = [minx, miny, maxx, maxy]

    unique_feat_strs = set(feature_strs)
    geom_stats["exact_duplicate_features"] = len(features_props) - len(unique_feat_strs)
    return geom_stats


def audit_pavement_condition_file(path, geobase_ids):
    _, ext = os.path.splitext(path.lower())
    if ext == ".csv":
        data_info = read_and_audit_csv(path)
    elif ext in (".json", ".geojson"):
        data_info = read_and_audit_geojson(path)
    elif ext == ".gpkg":
        data_info = read_and_audit_gpkg(path)
    else:
        raise ValueError(f"Unsupported file format extension: {ext}")

    features_props = data_info["features_props"]
    geoms = data_info["geoms"]

    stats = {
        "pci_parsed": 0,
        "pci_missing": 0,
        "pci_out_of_bounds": 0,
        "iri_parsed": 0,
        "iri_missing": 0,
        "iri_negative": 0,
        "iri_extreme_count": 0,
        "iri_sentinel_candidates": 0,
        "pci_index_exists_but_state_missing": 0,
        "pci_state_exists_but_index_missing": 0,
        "iri_index_exists_but_state_missing": 0,
        "iri_state_exists_but_index_missing": 0,
        "de_missing": 0,
        "a_missing": 0,
        "etat_pci_dist": {},
        "etat_iri_dist": {},
        "pci_vals": [],
        "iri_vals": [],
    }

    ids = []
    dates = []
    schema_stats = {}

    for props in features_props:
        process_feature_record(props, stats, ids, dates)
        analyze_attribute_schema(props, schema_stats)

    unique_ids = set(ids)
    dup_excess = len(ids) - len(unique_ids)

    dup_groups = 0
    dup_participating_rows = 0
    largest_dup_group_size = 0
    if dup_excess > 0:
        id_counts = {i: ids.count(i) for i in unique_ids}
        dup_ids = [i for i, c in id_counts.items() if c > 1]
        dup_groups = len(dup_ids)
        dup_participating_rows = sum(id_counts[i] for i in dup_ids)
        largest_dup_group_size = max(id_counts.values())

    geom_stats = audit_geometries(geoms, features_props, data_info["format"])

    min_date = min(dates).date().isoformat() if dates else None
    max_date = max(dates).date().isoformat() if dates else None

    year_dist = {}
    for d in dates:
        year_dist[d.year] = year_dist.get(d.year, 0) + 1

    matched_ids = unique_ids.intersection(geobase_ids)
    match_rate = len(matched_ids) / len(unique_ids) * 100 if unique_ids else 0.0

    pci_stats = calculate_numeric_stats(stats["pci_vals"])
    iri_stats = calculate_numeric_stats(stats["iri_vals"])

    return {
        "file_size": os.path.getsize(path),
        "sha256": calculate_sha256(path),
        "format": data_info["format"],
        "crs": data_info["crs"],
        "physical_rows": data_info["physical_rows"],
        "data_rows": len(features_props),
        "min_date": min_date,
        "max_date": max_date,
        "year_distribution": year_dist,
        "unique_id_count": len(unique_ids),
        "duplicate_id_excess": dup_excess,
        "duplicate_id_groups": dup_groups,
        "duplicate_participating_rows": dup_participating_rows,
        "largest_duplicate_group_size": largest_dup_group_size,
        "pci_stats": pci_stats,
        "iri_stats": iri_stats,
        "pci_missing": stats["pci_missing"],
        "iri_missing": stats["iri_missing"],
        "iri_sentinel_candidates": stats["iri_sentinel_candidates"],
        "pci_out_of_bounds": stats["pci_out_of_bounds"],
        "iri_negative": stats["iri_negative"],
        "iri_extreme_count": stats["iri_extreme_count"],
        "pci_index_exists_but_state_missing": stats["pci_index_exists_but_state_missing"],
        "pci_state_exists_but_index_missing": stats["pci_state_exists_but_index_missing"],
        "iri_index_exists_but_state_missing": stats["iri_index_exists_but_state_missing"],
        "iri_state_exists_but_index_missing": stats["iri_state_exists_but_index_missing"],
        "de_missing": stats["de_missing"],
        "a_missing": stats["a_missing"],
        "etat_pci_dist": stats["etat_pci_dist"],
        "etat_iri_dist": stats["etat_iri_dist"],
        "geom_stats": geom_stats,
        "geobase_matched": len(matched_ids),
        "geobase_match_rate": match_rate,
        "schema_stats": schema_stats,
        "header": data_info["header"],
        "norm_header": data_info["norm_header"],
    }


def main():  # noqa: C901
    parser = argparse.ArgumentParser(description="Read-only Pavement Condition Campaigns Auditor")
    parser.add_argument("files", nargs="+", help="One or multiple files to audit")
    parser.add_argument("--geobase", required=True, help="Path to current audited Geobase GeoJSON")
    args = parser.parse_args()

    geobase_ids = set()
    if os.path.exists(args.geobase):
        with open(args.geobase, "r", encoding="utf-8") as f:
            geobase_data = json.load(f)
        for feat in geobase_data.get("features", []):
            trc = feat.get("properties", {}).get("ID_TRC")
            if trc is not None:
                geobase_ids.add(int(trc))

    for path in args.files:
        if not os.path.exists(path):
            print(f"File not found: {path}")
            sys.exit(1)
        print(f"\nProcessing: {path}")
        try:
            res = audit_pavement_condition_file(path, geobase_ids)
            print("Format:", res["format"])
            print("Size (bytes):", res["file_size"])
            print("SHA-256:", res["sha256"])
            print("Rows:", res["data_rows"])
            print("Min Date:", res["min_date"], "Max Date:", res["max_date"])
            print(
                "Unique IDs:",
                res["unique_id_count"],
                "Duplicate excess:",
                res["duplicate_id_excess"],
            )
            print("PCI range:", res["pci_stats"]["min"], "to", res["pci_stats"]["max"])
            print(
                "IRI range:",
                res["iri_stats"]["min"],
                "to",
                res["iri_stats"]["max"],
                "Missing:",
                res["iri_missing"],
                "Sentinel candidates:",
                res["iri_sentinel_candidates"],
            )
            print(
                "Geobase matched:",
                res["geobase_matched"],
                "Match rate:",
                f"{res['geobase_match_rate']:.2f}%",
            )
            if res["geom_stats"]["bbox"]:
                print("Geometry bounds:", res["geom_stats"]["bbox"])
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"Failed to audit {path}: {str(e)}")
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
