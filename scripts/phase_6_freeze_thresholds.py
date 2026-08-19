"""Phase 6 — Threshold freeze script (Gate B1 only).

Refuses to run without Gate B1 authorization.
Computes Top-K and recall-diagnostic threshold candidates
from B1 calibrated predictions.
Writes threshold_manifest.json.
Does NOT access embargo or B2 targets.
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--b1-auth", required=True, help="Gate B1 authorization manifest")
    parser.add_argument("--cal-manifest", default="models/phase_6/calibration_manifest.json")
    parser.add_argument("--config", default="config/phase_6_evaluation.json")
    parser.add_argument("--out-dir", default="models/phase_6")
    args = parser.parse_args()

    # Authorization guard
    auth_path = Path(args.b1_auth)
    if not auth_path.exists():
        print(f"[ABORT] Gate B1 authorization not found: {auth_path}")
        sys.exit(1)
    doc = json.loads(auth_path.read_text())
    if not doc.get("gate_b1_authorized", False):
        print("[ABORT] gate_b1_authorized=false.")
        sys.exit(1)

    cal_manifest = Path(args.cal_manifest)
    if not cal_manifest.exists():
        print(f"[ABORT] calibration_manifest.json not found: {cal_manifest}")
        print("Calibration (phase_6_calibrate.py) must complete before threshold freeze.")
        sys.exit(1)

    print("=== PHASE 6 THRESHOLD FREEZE — GATE B1 ===")
    cfg = json.loads(Path(args.config).read_text())
    from montreal_road_risk.evaluation.metrics import top_k_row_count

    # B1 metadata from calibration manifest
    cal_data = json.loads(cal_manifest.read_text())
    b1_rows = cal_data["b1_rows"]
    k_percents = cfg["top_k"]["percentages"]

    threshold_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "B1",
        "frozen": True,
        "formula": "ceil(N * K / 100)",
        "tie_break_order": cfg["top_k"]["tie_break_order"],
        "b1_rows": b1_rows,
        "thresholds": {},
        "note": "Frozen before Gate B2. No threshold may be changed after test access.",
        "embargo_accessed": False,
        "b2_accessed": False,
    }

    for k in k_percents:
        n_rows = top_k_row_count(b1_rows, k)
        threshold_manifest["thresholds"][f"top_{k}_pct"] = {
            "k_pct": k,
            "n_rows_b1_ref": n_rows,
            "formula": f"ceil({b1_rows} * {k} / 100) = {n_rows}",
        }
        print(f"  Top-{k}%: {n_rows} rows from B1 ({b1_rows} total)")

    out = Path(args.out_dir) / "threshold_manifest.json"
    out.write_text(json.dumps(threshold_manifest, indent=2))
    print(f"\nThreshold manifest written: {out}")
    print("Gate B2 remains LOCKED.")


if __name__ == "__main__":
    main()
