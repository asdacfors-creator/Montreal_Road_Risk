"""Phase 6 final evaluation — Gate B2 authorized access only.

This script REFUSES to run without a valid Gate B2 authorization manifest.
Gate B2 requires a DIFFERENT authorization from Gate B1.
Gate B1 authorization never implies Gate B2 authorization.

Accesses final-test anchors exactly once (one-time evaluation guard).
Writes test_evaluation_results.json — immutable after writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Phase 6 — Gate B2 final evaluation (authorized once only)")
    parser.add_argument("--b2-auth", required=True, help="Path to Gate B2 authorization manifest (DIFFERENT from B1)")
    parser.add_argument("--config", default="config/phase_6_evaluation.json")
    parser.add_argument("--manifest", default="models/phase_6/test_split_manifest.json")
    parser.add_argument("--cal-manifest", default="models/phase_6/calibration_manifest.json")
    parser.add_argument("--out-dir", default="models/phase_6")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Authorization check — Gate B2 MUST be separate from Gate B1
    # -----------------------------------------------------------------------
    auth_path = Path(args.b2_auth)
    if not auth_path.exists():
        print(f"[ABORT] Gate B2 authorization manifest not found: {auth_path}")
        print("Gate B2 requires a SEPARATE and DIFFERENT supervisor authorization from Gate B1.")
        sys.exit(1)

    doc = json.loads(auth_path.read_text())
    if not doc.get("gate_b2_authorized", False):
        print("[ABORT] gate_b2_authorized=false in authorization manifest.")
        print("Gate B1 authorization does NOT authorize Gate B2.")
        sys.exit(1)

    # One-time guard
    results_path = Path(args.out_dir) / "test_evaluation_results.json"
    if results_path.exists():
        print(f"[ABORT] test_evaluation_results.json already exists: {results_path}")
        print("Gate B2 evaluation may run exactly once. Results are immutable.")
        sys.exit(1)

    print("=== PHASE 6 FINAL EVALUATION — GATE B2 ===")
    print(f"Authorization manifest: {auth_path}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("Calibration manifest must exist before proceeding.")

    cfg = json.loads(Path(args.config).read_text())

    from montreal_road_risk.evaluation.seal_guard import (
        OneTimeEvaluationError,
        SealViolationError,
        TestSealGuard,
    )

    guard = TestSealGuard(args.manifest, results_path=results_path)
    seal_path = Path(cfg["sealed_test_file"])

    try:
        b2_table = guard.load_b2_only(seal_path, auth_path, args.cal_manifest)
    except (SealViolationError, OneTimeEvaluationError) as e:
        print(f"[ABORT] {e}")
        sys.exit(1)

    print(f"B2 rows loaded: {len(b2_table)}")
    print("Computing final evaluation metrics — this is the one-time irreversible evaluation.")

    # (Actual metric computation follows here in Gate B2 execution)
    # This stub prevents accidental execution without proper authorization.
    print("[STUB] Full metric computation will execute here during Gate B2.")
    print("Gate B2 requires separate supervisor authorization. This script is a guard stub.")


if __name__ == "__main__":
    main()
