"""Client artifact hash verification helper.

Reads manifests/client_artifact_manifest.csv relative to package root,
verifies each listed file using RAW_SHA256 or CANONICAL_TEXT_SHA256,
and reports PASS/FAIL per file. Exits nonzero for missing files,
unsupported hash types, hash mismatches, or malformed rows.

Per Safeguard 2:
  Imports and uses montreal_road_risk.io.checksums.calculate_canonical_sha256
  for CANONICAL_TEXT_SHA256.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

from montreal_road_risk.io.checksums import calculate_canonical_sha256


def sha256_raw(path: Path) -> str:
    """Compute raw binary streaming SHA-256 checksum."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify client artifact hashes.")
    parser.add_argument(
        "--package-root",
        default=None,
        help="Path to extracted client package root (default: script directory)",
    )
    args = parser.parse_args()

    root = (
        Path(args.package_root).resolve()
        if args.package_root
        else Path(__file__).resolve().parent
    )
    manifest_path = root / "manifests" / "client_artifact_manifest.csv"

    if not manifest_path.exists():
        print(f"[ERROR] Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    total = passed = failed = 0
    required_cols = {
        "package_relative_path",
        "artifact_category",
        "size_bytes",
        "hash_type",
        "expected_sha256",
        "required_for_dashboard",
        "required_for_model_loading",
        "required_for_interpretation",
        "required_for_survival",
        "status",
        "notes",
    }

    with open(manifest_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            missing_cols = required_cols - set(reader.fieldnames or [])
            print(f"[ERROR] Malformed manifest. Missing columns: {missing_cols}", file=sys.stderr)
            sys.exit(1)

        for row in reader:
            total += 1
            rel = row.get("package_relative_path", "").strip()
            expected = row.get("expected_sha256", "").strip()
            htype = row.get("hash_type", "").strip()
            target = root / rel

            if not rel or not expected or not htype:
                print(f"[FAIL] MALFORMED ROW: {row}", file=sys.stderr)
                failed += 1
                continue

            if not target.exists():
                print(f"[FAIL] MISSING  : {rel}")
                failed += 1
                continue

            if htype == "RAW_SHA256":
                actual = sha256_raw(target)
            elif htype == "CANONICAL_TEXT_SHA256":
                actual = calculate_canonical_sha256(target)
            else:
                print(f"[FAIL] UNSUPPORTED hash_type={htype!r}: {rel}")
                failed += 1
                continue

            if actual.lower() == expected.lower():
                print(f"[PASS] {rel}")
                passed += 1
            else:
                print(f"[FAIL] MISMATCH : {rel}")
                print(f"       expected : {expected}")
                print(f"       actual   : {actual}")
                failed += 1

    print(f"\n{total} files checked — {passed} passed, {failed} failed")
    if failed > 0:
        print("ARTIFACT VERIFICATION FAILED")
        sys.exit(1)
    print("ARTIFACT VERIFICATION COMPLETE")


if __name__ == "__main__":
    main()
