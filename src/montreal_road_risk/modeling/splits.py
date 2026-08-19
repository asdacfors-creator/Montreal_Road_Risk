"""
src/montreal_road_risk/modeling/splits.py

Purged chronological split construction for the Phase 5 modeling panel.

Key design rules
----------------
* Train target windows must end strictly before val as_of_date.
* Val target windows must end strictly before test as_of_date.
* Embargo rows are preserved in the manifest with per-horizon exclusion reasons.
* All arithmetic assertions are hard errors — no silent approximations.
* Streaming file-by-file implementation keeps peak memory to one partition file.
"""

from __future__ import annotations

import datetime
import glob
import hashlib
import json
import logging
import os
from collections import defaultdict
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

HORIZON_90  = 90
HORIZON_180 = 180

ALLOWED_STATUSES = frozenset([
    "train", "validation", "sealed_test",
    "embargo_train_validation", "embargo_validation_test",
])

# Columns always written to partition files regardless of exclude_from_X.
# Baselines need canonical_segment_id; temporal analysis needs as_of_date.
PARTITION_ALWAYS_KEEP: frozenset[str] = frozenset([
    "canonical_segment_id",
    "as_of_date",
    "segment_month_id",
])


# ---------------------------------------------------------------------------
# Anchor-date helpers
# ---------------------------------------------------------------------------

def _parse_anchor(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def _anchor_from_path(fpath: str) -> pd.Timestamp:
    """Extract the month-end anchor date from a Hive parquet path."""
    parts = fpath.replace("\\", "/").split("/")
    year_part  = next(p for p in parts if p.startswith("panel_year="))
    month_part = next(p for p in parts if p.startswith("panel_month="))
    year  = int(year_part.split("=")[1])
    month = int(month_part.split("=")[1])
    # Last calendar day of the month
    if month == 12:
        last_day = pd.Timestamp(f"{year+1}-01-01") - pd.Timedelta(days=1)
    else:
        last_day = pd.Timestamp(f"{year}-{month+1:02d}-01") - pd.Timedelta(days=1)
    return last_day


# ---------------------------------------------------------------------------
# Split-label assignment (pure date math — no data loading)
# ---------------------------------------------------------------------------

def build_anchor_split_map(cfg: dict) -> dict[pd.Timestamp, dict]:  # noqa: C901
    """
    Return a dict mapping each anchor Timestamp → {split_90d, split_180d,
    exclusion_reason_90d, exclusion_reason_180d, target_end_date_90d,
    target_end_date_180d}.
    Covers all 102 possible anchors in the panel range.
    """
    c90  = cfg["split_90d"]
    c180 = cfg["split_180d"]

    train_end_90    = _parse_anchor(c90["train_end_anchor"])
    val_start_90    = _parse_anchor(c90["val_start_anchor"])
    val_end_90      = _parse_anchor(c90["val_end_anchor"])
    test_start_90   = _parse_anchor(c90["test_start_anchor"])
    emb_tv_90 = {_parse_anchor(a) for a in c90["embargo_tv_anchors"]}
    emb_vt_90 = {_parse_anchor(a) for a in c90["embargo_vt_anchors"]}

    train_end_180   = _parse_anchor(c180["train_end_anchor"])
    emb_tv_start_180 = _parse_anchor(c180["embargo_tv_start"])
    emb_tv_end_180   = _parse_anchor(c180["embargo_tv_end"])
    val_start_180   = _parse_anchor(c180["val_start_anchor"])
    val_end_180     = _parse_anchor(c180["val_end_anchor"])
    emb_vt_start_180 = _parse_anchor(c180["embargo_vt_start"])
    emb_vt_end_180   = _parse_anchor(c180["embargo_vt_end"])
    test_start_180  = _parse_anchor(c180["test_start_anchor"])

    # Generate all month-end anchors in the panel range
    anchors = pd.date_range("2016-12-31", "2025-05-31", freq="ME")
    result = {}
    for dt in anchors:
        dt = pd.Timestamp(dt)
        ted90  = dt + pd.Timedelta(days=HORIZON_90)
        ted180 = dt + pd.Timedelta(days=HORIZON_180)

        # 90d label
        if dt in emb_tv_90:
            s90 = "embargo_train_validation"
            r90 = f"90d target window ends >= {val_start_90.date()}"
        elif dt in emb_vt_90:
            s90 = "embargo_validation_test"
            r90 = f"90d target window ends >= {test_start_90.date()}"
        elif dt <= train_end_90:
            s90, r90 = "train", None
        elif val_start_90 <= dt <= val_end_90:
            s90, r90 = "validation", None
        elif dt >= test_start_90:
            s90, r90 = "sealed_test", None
        else:
            raise ValueError(f"Anchor {dt.date()} unclassifiable in 90d split")

        # 180d label
        if emb_tv_start_180 <= dt <= emb_tv_end_180:
            s180 = "embargo_train_validation"
            r180 = f"180d target window ends >= {val_start_180.date()}"
        elif emb_vt_start_180 <= dt <= emb_vt_end_180:
            s180 = "embargo_validation_test"
            r180 = f"180d target window ends >= {test_start_180.date()}"
        elif dt <= train_end_180:
            s180, r180 = "train", None
        elif val_start_180 <= dt <= val_end_180:
            s180, r180 = "validation", None
        elif dt >= test_start_180:
            s180, r180 = "sealed_test", None
        else:
            raise ValueError(f"Anchor {dt.date()} unclassifiable in 180d split")

        result[dt] = {
            "split_90d":              s90,
            "split_180d":             s180,
            "exclusion_reason_90d":   r90,
            "exclusion_reason_180d":  r180,
            "target_end_date_90d":    ted90,
            "target_end_date_180d":   ted180,
        }
    return result


# ---------------------------------------------------------------------------
# Streaming split builder — core of Phase 5 data preparation
# ---------------------------------------------------------------------------

def build_splits_streaming(cfg: dict, out_dir: str) -> dict:  # noqa: C901
    """
    Stream each of 102 parquet files one at a time.

    For each file:
    1. Read it with pd.read_parquet
    2. Look up the split labels from the anchor-date map
    3. Append rows to the appropriate output partition file

    Keeps peak memory to one file (~20-30 MB uncompressed) plus
    accumulated partition writers.

    Returns a summary dict with row counts, fingerprints, and seal info.
    """
    panel_dir = cfg["panel_dir"]
    files = sorted(glob.glob(
        os.path.join(panel_dir, "panel_year=*/panel_month=*/segment_month.parquet")
    ))
    if not files:
        raise FileNotFoundError(f"No panel files found in {panel_dir}")
    assert len(files) == 102, f"Expected 102 panel files, found {len(files)}"

    anchor_map = build_anchor_split_map(cfg)
    exclude    = set(cfg["exclude_from_X"])
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Partition output paths
    partition_paths = {
        ("90d",  "train"):               os.path.join(out_dir, "train_90d.parquet"),
        ("90d",  "validation"):          os.path.join(out_dir, "val_90d.parquet"),
        ("180d", "train"):               os.path.join(out_dir, "train_180d.parquet"),
        ("180d", "validation"):          os.path.join(out_dir, "val_180d.parquet"),
        ("test", "sealed_test"):         os.path.join(out_dir, "test.parquet"),
    }

    # Accumulators — we write per-anchor chunks and concatenate at end
    partition_chunks: dict = defaultdict(list)
    manifest_rows: list = []

    # For test seal: collect content for fingerprinting
    test_rows_for_seal: list = []

    row_counts: dict = defaultdict(int)
    anchor_counts: dict = defaultdict(set)

    for i, fpath in enumerate(files):
        anchor = _anchor_from_path(fpath)
        info   = anchor_map.get(anchor)
        if info is None:
            raise ValueError(f"Anchor {anchor.date()} from {fpath} not in anchor map")

        chunk = pd.read_parquet(fpath)
        n     = len(chunk)

        s90  = info["split_90d"]
        s180 = info["split_180d"]
        ted90  = info["target_end_date_90d"]
        ted180 = info["target_end_date_180d"]
        r90    = info["exclusion_reason_90d"]
        r180   = info["exclusion_reason_180d"]

        # Track counts
        row_counts[s90]  += n
        anchor_counts[s90].add(anchor)
        row_counts[f"180d_{s180}"] += n
        anchor_counts[f"180d_{s180}"].add(anchor)

        # Build manifest rows (lightweight — just metadata columns)
        manifest_rows.append(pd.DataFrame({
            "segment_month_id":       chunk["segment_month_id"],
            "as_of_date":             anchor,
            "split_90d":              s90,
            "split_180d":             s180,
            "exclusion_reason_90d":   r90,
            "exclusion_reason_180d":  r180,
            "target_end_date_90d":    ted90,
            "target_end_date_180d":   ted180,
        }))

        # Route to partition accumulators (drop excluded cols, always keep metadata)
        if s90 in ("train", "validation", "sealed_test"):
            key90 = ("90d", s90)
            keep90 = [c for c in chunk.columns
                      if c not in exclude or c == "target_repair_90d" or c in PARTITION_ALWAYS_KEEP]
            partition_chunks[key90].append(chunk[keep90])
        if s180 in ("train", "validation", "sealed_test"):
            key180 = ("180d", s180)
            keep180 = [c for c in chunk.columns
                       if c not in exclude or c == "target_repair_180d" or c in PARTITION_ALWAYS_KEEP]
            partition_chunks[key180].append(chunk[keep180])
        if s90 == "sealed_test":
            key_test = ("test", "sealed_test")
            keep_test = [c for c in chunk.columns
                         if c not in exclude or c == "target_repair_180d" or c in PARTITION_ALWAYS_KEEP]
            partition_chunks[key_test].append(chunk[keep_test])
            test_rows_for_seal.append(chunk[
                ["canonical_segment_id", "as_of_date", "target_repair_90d", "target_repair_180d"]
            ])

        if (i + 1) % 20 == 0 or (i + 1) == len(files):
            log.info("  Processed %d / %d files", i + 1, len(files))

    # Write partition parquet files
    log.info("Writing partition parquet files ...")
    for key, path in partition_paths.items():
        chunks = partition_chunks.get(key, [])
        if chunks:
            pd.concat(chunks, ignore_index=True).to_parquet(path, index=False)
            log.info("  Wrote %s: %s", key, path)

    # Write split manifest
    log.info("Writing split manifest ...")
    manifest_df = pd.concat(manifest_rows, ignore_index=True)
    manifest_path = os.path.join(out_dir, "split_assignment_manifest.parquet")
    manifest_df.to_parquet(manifest_path, index=False)
    log.info("Split manifest: %d rows → %s", len(manifest_df), manifest_path)

    # Write test seal
    seal = _write_test_seal_from_rows(test_rows_for_seal, out_dir)

    # Compute summary row counts
    total = sum(v for k, v in row_counts.items() if not k.startswith("180d_"))
    summary = {
        "n_train_90d":        row_counts.get("train", 0),
        "n_embargo_tv_90d":   row_counts.get("embargo_train_validation", 0),
        "n_val_90d":          row_counts.get("validation", 0),
        "n_embargo_vt_90d":   row_counts.get("embargo_validation_test", 0),
        "n_test_90d":         row_counts.get("sealed_test", 0),
        "n_total_90d":        total,
        "n_train_180d":       row_counts.get("180d_train", 0),
        "n_embargo_tv_180d":  row_counts.get("180d_embargo_train_validation", 0),
        "n_val_180d":         row_counts.get("180d_validation", 0),
        "n_embargo_vt_180d":  row_counts.get("180d_embargo_validation_test", 0),
        "n_test_180d":        row_counts.get("180d_sealed_test", 0),
        "seal_n_rows":        seal["n_rows"],
        "seal_content_fp":    seal["content_fingerprint_sha256"],
    }
    return summary


# ---------------------------------------------------------------------------
# Arithmetic assertions (from summary dict — no full-panel groupby)
# ---------------------------------------------------------------------------

def assert_split_arithmetic_from_summary(summary: dict, cfg: dict) -> None:
    """Assert exact partition sizes from the streaming summary dict."""
    c90  = cfg["split_90d"]
    c180 = cfg["split_180d"]

    checks = [
        ("90d train rows",        summary["n_train_90d"],        c90["expected_train_rows"]),
        ("90d embargo_tv rows",   summary["n_embargo_tv_90d"],   c90["expected_embargo_tv_rows"]),
        ("90d val rows",          summary["n_val_90d"],          c90["expected_val_rows"]),
        ("90d embargo_vt rows",   summary["n_embargo_vt_90d"],   c90["expected_embargo_vt_rows"]),
        ("90d test rows",         summary["n_test_90d"],         c90["expected_test_rows"]),
        ("90d total rows",        summary["n_total_90d"],        c90["expected_total_rows"]),
        ("180d train rows",       summary["n_train_180d"],       c180["expected_train_rows"]),
        ("180d embargo_tv rows",  summary["n_embargo_tv_180d"],  c180["expected_embargo_tv_rows"]),
        ("180d val rows",         summary["n_val_180d"],         c180["expected_val_rows"]),
        ("180d embargo_vt rows",  summary["n_embargo_vt_180d"],  c180["expected_embargo_vt_rows"]),
        ("180d test rows",        summary["n_test_180d"],        c180["expected_test_rows"]),
    ]
    failures = [f"  {name}: expected {exp}, got {actual}" for name, actual, exp in checks if actual != exp]
    if failures:
        raise AssertionError("Split arithmetic FAILED:\n" + "\n".join(failures))
    log.info("Split arithmetic: ALL CHECKS PASSED")


# ---------------------------------------------------------------------------
# Purge condition assertions (from anchor map — no data loading)
# ---------------------------------------------------------------------------

def assert_purge_conditions_from_map(cfg: dict) -> None:
    """Assert purge conditions from the anchor-date map alone."""
    anchor_map = build_anchor_split_map(cfg)

    train_90  = [dt for dt, v in anchor_map.items() if v["split_90d"]  == "train"]
    val_90    = [dt for dt, v in anchor_map.items() if v["split_90d"]  == "validation"]
    test_90   = [dt for dt, v in anchor_map.items() if v["split_90d"]  == "sealed_test"]
    train_180 = [dt for dt, v in anchor_map.items() if v["split_180d"] == "train"]
    val_180   = [dt for dt, v in anchor_map.items() if v["split_180d"] == "validation"]
    test_180  = [dt for dt, v in anchor_map.items() if v["split_180d"] == "sealed_test"]

    max_train_ted90 = max(anchor_map[dt]["target_end_date_90d"]  for dt in train_90)
    min_val_aod     = min(val_90)
    max_val_ted90   = max(anchor_map[dt]["target_end_date_90d"]  for dt in val_90)
    min_test_aod    = min(test_90)

    assert max_train_ted90 < min_val_aod, (
        f"90d purge FAIL: max train TED {max_train_ted90.date()} >= min val AOD {min_val_aod.date()}"
    )
    assert max_val_ted90 < min_test_aod, (
        f"90d purge FAIL: max val TED {max_val_ted90.date()} >= min test AOD {min_test_aod.date()}"
    )

    max_train_ted180 = max(anchor_map[dt]["target_end_date_180d"] for dt in train_180)
    min_val_aod_180  = min(val_180)
    max_val_ted180   = max(anchor_map[dt]["target_end_date_180d"] for dt in val_180)
    min_test_aod_180 = min(test_180)

    assert max_train_ted180 < min_val_aod_180, (
        f"180d purge FAIL: max train TED {max_train_ted180.date()} >= min val AOD {min_val_aod_180.date()}"
    )
    assert max_val_ted180 < min_test_aod_180, (
        f"180d purge FAIL: max val TED {max_val_ted180.date()} >= min test AOD {min_test_aod_180.date()}"
    )
    log.info("Purge conditions: ALL CHECKS PASSED")


# ---------------------------------------------------------------------------
# Test seal (called only during split building — only place test targets read)
# ---------------------------------------------------------------------------

def _write_test_seal_from_rows(test_rows: list, out_dir: str) -> dict:
    """
    Write test_seal_manifest.json from accumulated test-partition rows.
    Fingerprints both target_repair_90d and target_repair_180d.
    """
    test_df = pd.concat(test_rows, ignore_index=True).sort_values(
        ["canonical_segment_id", "as_of_date"]
    )
    content_str = (
        test_df["canonical_segment_id"].astype(str)
        + "|" + test_df["as_of_date"].astype(str)
        + "|" + test_df["target_repair_90d"].astype(str)
        + "|" + test_df["target_repair_180d"].astype(str)
    ).str.cat(sep="\n")
    content_fp = hashlib.sha256(content_str.encode()).hexdigest()
    schema_fp  = hashlib.sha256(str(sorted(test_df.columns.tolist())).encode()).hexdigest()

    n_anchors = int(test_df["as_of_date"].nunique())
    manifest = {
        "partition": "sealed_test",
        "anchor_start": str(test_df["as_of_date"].min().date()),
        "anchor_end":   str(test_df["as_of_date"].max().date()),
        "n_anchors":    n_anchors,
        "n_rows":       int(len(test_df)),
        "target_column_included_in_file": True,
        "fingerprints_include_90d_and_180d": True,
        "schema_fingerprint_sha256":  schema_fp,
        "content_fingerprint_sha256": content_fp,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "sealed_by":  "src/montreal_road_risk/modeling/splits.py",
    }
    seal_path = os.path.join(out_dir, "test_seal_manifest.json")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(seal_path, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Test seal written: %d rows, fp=%s...", len(test_df), content_fp[:16])
    return manifest


# ---------------------------------------------------------------------------
# Split-manifest fingerprint helper
# ---------------------------------------------------------------------------

def fingerprint_split_manifest(manifest_path: str) -> str:
    h = hashlib.sha256()
    with open(manifest_path, "rb") as f:
        for chunk_bytes in iter(lambda: f.read(65536), b""):
            h.update(chunk_bytes)
    return h.hexdigest()
