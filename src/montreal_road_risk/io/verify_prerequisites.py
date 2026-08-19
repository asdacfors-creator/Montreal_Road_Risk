"""Prerequisite Hash Verification Tool for INSE 6311 Project Reproducibility.

Reads external prerequisites manifest or pre-package manifest and verifies
file existence and SHA-256 hash digests. Exits with code 0 on success or code 1 on failure.
"""

import sys
import hashlib
import json
import csv
from pathlib import Path

# Ensure src is in sys.path if invoked directly
file_path = Path(__file__).resolve()
src_dir = file_path.parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from montreal_road_risk.io.checksums import calculate_canonical_sha256

def calculate_raw_sha256(path: Path) -> str:
    """Calculate raw binary SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def verify_manifest(manifest_path: Path, root_dir: Path) -> bool:
    """Verify all files in manifest against expected SHA-256 digests."""
    if not manifest_path.exists():
        print(f"[ERROR] Manifest file not found: {manifest_path}")
        return False

    print(f"=== Verifying Prerequisites from {manifest_path.name} ===")
    total = 0
    passed = 0
    failed = 0

    with open(manifest_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            rel_p = row.get('relative_path') or row.get('package_relative_path') or row.get('source_relative_path')
            if not rel_p:
                continue

            target_file = root_dir / rel_p
            if not target_file.exists():
                print(f"[FAIL] Missing file: {rel_p}")
                failed += 1
                continue

            is_txt = rel_p.endswith(('.json', '.csv', '.md', '.txt', '.py', '.toml', '.yaml', '.yml'))

            exp_canon = row.get('canonical_text_sha256')
            exp_raw = row.get('expected_sha256') or row.get('sha256') or row.get('raw_sha256')

            # Prefer canonical text check for text files if available
            if is_txt and exp_canon and exp_canon != 'N/A':
                act_h = calculate_canonical_sha256(target_file)
                exp_h = exp_canon
            else:
                act_h = calculate_raw_sha256(target_file)
                exp_h = exp_raw if exp_raw and exp_raw != 'N/A' else exp_canon

            if exp_h and exp_h != 'N/A' and act_h.lower() != exp_h.lower():
                # Fall back to checking alternative hash representation
                alt_h = calculate_raw_sha256(target_file) if is_txt else calculate_canonical_sha256(target_file)
                if alt_h.lower() == exp_h.lower():
                    act_h = alt_h

            if exp_h and exp_h != 'N/A' and act_h.lower() == exp_h.lower():
                passed += 1
                print(f"[PASS] {rel_p}")
            elif not exp_h or exp_h == 'N/A':
                passed += 1
                print(f"[PASS] {rel_p} (File exists)")
            else:
                failed += 1
                print(f"[FAIL] Hash mismatch for {rel_p}:\n  Expected: {exp_h}\n  Actual:   {act_h}")

    print(f"\nVerification Summary: {passed}/{total} files verified successfully.")
    return failed == 0

def main():
    root_dir = Path('.').resolve()
    default_manifests = [
        root_dir / 'report_assets/phase12_reproducibility_package_pre_manifest.csv',
        root_dir / 'report_assets/phase12_external_prerequisites_manifest.csv'
    ]

    manifest_to_use = None
    if len(sys.argv) > 1:
        manifest_to_use = Path(sys.argv[1]).resolve()
    else:
        for m in default_manifests:
            if m.exists():
                manifest_to_use = m
                break

    if not manifest_to_use:
        print("[ERROR] No valid prerequisite manifest found.")
        sys.exit(1)

    success = verify_manifest(manifest_to_use, root_dir)
    if not success:
        print("\n[VERIFICATION FAILED] One or more prerequisites failed existence or SHA-256 verification.")
        sys.exit(1)
    else:
        print("\n[VERIFICATION SUCCESSFUL] All prerequisites verified cleanly.")
        sys.exit(0)

if __name__ == '__main__':
    main()
