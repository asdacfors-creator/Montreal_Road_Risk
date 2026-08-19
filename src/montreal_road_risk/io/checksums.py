import hashlib
import os
from pathlib import Path

TEXT_EXTENSIONS = {
    ".json",
    ".md",
    ".txt",
    ".csv",
    ".toml",
    ".yaml",
    ".yml",
    ".py",
    ".gitkeep",
    ".gitignore",
}


def calculate_sha256(filepath):
    """Calculate the SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def calculate_canonical_sha256(filepath_or_bytes, filename_hint=None):
    """Calculate SHA-256 digest.
    If the file is a recognized text file (.json, .md, .txt, .csv, .toml, .yaml, .yml, .py, .gitkeep, .gitignore),
    canonicalize line endings (CRLF and standalone CR -> LF) before computing the digest.
    For binary files, compute the exact raw-byte SHA-256 digest.
    """
    if isinstance(filepath_or_bytes, (str, Path)):
        p = Path(filepath_or_bytes)
        ext = p.suffix.lower()
        if ext in TEXT_EXTENSIONS or p.name in {".gitkeep", ".gitignore"}:
            b = p.read_bytes()
            b_norm = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            return hashlib.sha256(b_norm).hexdigest()
        else:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
    else:
        ext = Path(filename_hint).suffix.lower() if filename_hint else ""
        name = Path(filename_hint).name if filename_hint else ""
        b = filepath_or_bytes
        if ext in TEXT_EXTENSIONS or name in {".gitkeep", ".gitignore"}:
            b_norm = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            return hashlib.sha256(b_norm).hexdigest()
        return hashlib.sha256(b).hexdigest()


def scan_raw_files(data_dir, project_root):
    """Create a read-only integrity inventory of every raw file in the directory."""
    inventory = []

    # Map subdirectories to categories
    category_mapping = {
        "geobase": "montreal_geobase",
        "pothole_repairs": "mechanized_pothole_repairs",
        "road_assets": "road_assets_pavement",
        "pavement_condition": "pavement_condition",
        "borough_boundaries": "borough_boundaries",
        "mctavish": "eccc_daily_weather",
        "montreal_trudeau": "eccc_daily_weather",
        "station_inventory": "eccc_daily_weather",
    }

    for root, _, files in os.walk(data_dir):
        for filename in files:
            if filename == ".gitkeep":
                continue
            fpath = os.path.join(root, filename)
            rel_path = os.path.relpath(fpath, project_root).replace(os.sep, "/")
            size_bytes = os.path.getsize(fpath)
            sha256_val = calculate_canonical_sha256(fpath)
            mtime = os.path.getmtime(fpath)

            # Find category based on path parts
            category = "unknown"
            parts = rel_path.split("/")
            for part in parts:
                if part in category_mapping:
                    category = category_mapping[part]
                    break

            inventory.append(
                {
                    "relative_path": rel_path,
                    "size_bytes": size_bytes,
                    "sha256": sha256_val,
                    "modified_timestamp": mtime,
                    "dataset_category": category,
                }
            )
    return inventory
