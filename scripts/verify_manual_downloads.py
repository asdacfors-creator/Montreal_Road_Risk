#!/usr/bin/env python
"""Verify manual downloads.

Scans the raw data directories, matches files against data_manifest.csv,
calculates file sizes and SHA-256 checksums, and reports missing required datasets.
"""

import argparse
import csv
import hashlib
import os
import sys

# Paths configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "data", "metadata", "data_manifest.csv")
REPORT_DIR = os.path.join(PROJECT_ROOT, "outputs", "evidence", "phase_2")
REPORT_PATH = os.path.join(REPORT_DIR, "manual_download_report.txt")


def calculate_sha256(filepath):
    """Calculate the SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read in blocks of 4KB
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def load_manifest(manifest_path):
    """Load expected datasets from the data manifest CSV."""
    datasets = {}
    if not os.path.exists(manifest_path):
        return datasets

    with open(manifest_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dataset_id = row["dataset_id"]
            datasets[dataset_id] = {
                "required_status": row["required_status"],
                "download_status": row["download_status"],
                "notes": row["notes"],
            }
    return datasets


def scan_raw_directories(data_dir):
    """Scan raw folders recursively and inventory files."""
    inventory = []
    for root, _, files in os.walk(data_dir):
        for filename in files:
            # Skip gitkeep files
            if filename == ".gitkeep":
                continue
            filepath = os.path.join(root, filename)
            try:
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
            except ValueError:
                # Fallback for cross-drive test environments
                rel_path = os.path.relpath(filepath, data_dir)
            size_bytes = os.path.getsize(filepath)
            _, ext = os.path.splitext(filename)
            sha256_val = calculate_sha256(filepath)
            inventory.append(
                {
                    "original_filename": filename,
                    "local_relative_path": rel_path.replace(os.sep, "/"),
                    "file_size_bytes": size_bytes,
                    "sha256": sha256_val,
                    "extension": ext.lower(),
                    "folder": os.path.basename(root),
                }
            )
    return inventory


def _group_files_by_dataset(inventory, datasets):
    """Group file inventory by dataset IDs."""
    folder_mapping = {
        "geobase": "montreal_geobase",
        "pothole_repairs": "mechanized_pothole_repairs",
        "road_assets": "road_assets_pavement",
        "pavement_condition": "pavement_condition",
        "borough_boundaries": "borough_boundaries",
        "eccc_weather": "eccc_daily_weather",
        "traffic_counts": "traffic_counts",
    }

    matched_files = {dataset_id: [] for dataset_id in datasets}
    unmatched_files = []

    for file_info in inventory:
        dataset_id = folder_mapping.get(file_info["folder"])
        if not dataset_id:
            for part in file_info["local_relative_path"].split("/"):
                if part in folder_mapping:
                    dataset_id = folder_mapping[part]
                    break
        if dataset_id and dataset_id in matched_files:
            matched_files[dataset_id].append(file_info)
        else:
            unmatched_files.append(file_info)

    return matched_files, unmatched_files


def generate_report(datasets, inventory, allow_missing):
    """Generate verification report, print to terminal and write to file."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    matched_files, unmatched_files = _group_files_by_dataset(inventory, datasets)

    report_lines = [
        "=== MANUAL DOWNLOAD VERIFICATION REPORT ===",
        f"Project Root: {PROJECT_ROOT}",
        "",
        "--- Dataset Statuses ---",
    ]

    missing_required = []

    for dataset_id, meta in datasets.items():
        files_found = matched_files.get(dataset_id, [])
        required = meta["required_status"]
        report_lines.extend([f"Dataset ID: {dataset_id}", f"  Required Status: {required}"])

        if not files_found:
            report_lines.append("  Status: NOT DOWNLOADED (Missing)")
            if required in ("required", "required_candidate"):
                missing_required.append(dataset_id)
        else:
            report_lines.append(f"  Status: FILE DETECTED ({len(files_found)} file(s))")
            for f in files_found:
                report_lines.extend(
                    [
                        f"    File: {f['original_filename']}",
                        f"    Size: {f['file_size_bytes']} bytes",
                        f"    SHA-256: {f['sha256']}",
                        "    Audit Status: Awaiting content audit",
                    ]
                )
        report_lines.append("")

    if unmatched_files:
        report_lines.append("--- Unmatched Raw Files ---")
        for f in unmatched_files:
            report_lines.append(
                f"  File: {f['local_relative_path']} (Size: {f['file_size_bytes']} bytes)"
            )
        report_lines.append("")

    report_lines.extend(
        [
            "--- Summary ---",
            f"Total datasets defined in manifest: {len(datasets)}",
            f"Total files detected in raw directory: {len(inventory)}",
            f"Missing required datasets: {len(missing_required)}",
        ]
    )

    exit_code = 0
    if missing_required:
        if allow_missing:
            report_lines.append(
                "Warning: Required datasets are missing, but execution continues (--allow-missing)."
            )
        else:
            report_lines.append("Error: Required datasets are missing. Verification failed.")
            exit_code = 1
    else:
        report_lines.append("Success: All required datasets are present.")

    report_lines.extend(
        [
            "",
            "Note: File existence does not declare the data scientifically valid.",
            "A full data quality and schema content audit must be run during Phase 2B.",
        ]
    )

    # Write report file
    report_content = "\n".join(report_lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as rf:
        rf.write(report_content)

    # Print to stdout
    print(report_content)

    return exit_code


def main():  # noqa: C901
    """Main execution block."""
    parser = argparse.ArgumentParser(description="Verify manually downloaded datasets.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow missing required files without exiting with non-zero code (useful for Phase 2A).",
    )
    args = parser.parse_args()

    datasets = load_manifest(MANIFEST_PATH)
    if not datasets:
        print(f"Error: Manifest file not found or empty at {MANIFEST_PATH}", file=sys.stderr)
        return 1

    inventory = scan_raw_directories(DATA_DIR)

    exit_code = generate_report(datasets, inventory, args.allow_missing)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
