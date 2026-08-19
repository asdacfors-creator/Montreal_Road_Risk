"""Phase 6 calibration script — Gate B1 authorized access only.

This script REFUSES to run without a valid Gate B1 authorization manifest.
Gate B1 authorization does NOT imply Gate B2 authorization.

Fits the prespecified Platt/sigmoid calibrator on B1 targets only.
Writes calibrator_90d.joblib and calibration_manifest.json.
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
    parser = argparse.ArgumentParser(description="Phase 6 — Gate B1 calibration (authorized access only)")
    parser.add_argument("--b1-auth", required=True, help="Path to Gate B1 authorization manifest")
    parser.add_argument("--config", default="config/phase_6_evaluation.json")
    parser.add_argument("--manifest", default="models/phase_6/test_split_manifest.json")
    parser.add_argument("--out-dir", default="models/phase_6")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Authorization check — MUST be first
    # -----------------------------------------------------------------------
    from montreal_road_risk.evaluation.seal_guard import SealViolationError, TestSealGuard

    auth_path = Path(args.b1_auth)
    if not auth_path.exists():
        print(f"[ABORT] Gate B1 authorization manifest not found: {auth_path}")
        print("This script requires a SEPARATE explicit supervisor authorization for Gate B1.")
        sys.exit(1)

    doc = json.loads(auth_path.read_text())
    if not doc.get("gate_b1_authorized", False):
        print("[ABORT] gate_b1_authorized=false in authorization manifest.")
        sys.exit(1)

    print("=== PHASE 6 CALIBRATION — GATE B1 ===")
    print(f"Authorization manifest: {auth_path}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    cfg = json.loads(Path(args.config).read_text())
    guard = TestSealGuard(args.manifest)
    seal_path = Path(cfg["sealed_test_file"])

    # -----------------------------------------------------------------------
    # Load B1 targets only
    # -----------------------------------------------------------------------
    try:
        b1_table = guard.load_b1_only(seal_path, auth_path)
    except SealViolationError as e:
        print(f"[ABORT] Seal violation: {e}")
        sys.exit(1)

    print(f"B1 rows loaded: {len(b1_table)}")

    import joblib
    import numpy as np

    from montreal_road_risk.evaluation.calibration import PlattCalibrator
    from montreal_road_risk.evaluation.metrics import (
        calibration_slope_intercept,
        expected_calibration_error,
    )
    preprocessor = joblib.load("models/phase_5/full_training_external_memory_candidate/preprocessor.joblib")

    # Features only — target extracted separately
    target_col = "target_repair_90d"
    y_b1 = b1_table.column(target_col).to_pylist()
    y_b1 = np.array(y_b1, dtype=float)

    feature_cols = [c for c in b1_table.schema.names if c != target_col]
    X_b1 = b1_table.select(feature_cols).to_pandas()
    import xgboost as xgb
    bst = xgb.Booster()
    bst.load_model("models/phase_5/full_training_external_memory_candidate/model.joblib")

    X_trans = preprocessor.transform(X_b1)
    dm = xgb.DMatrix(X_trans)
    raw_scores = bst.predict(dm, iteration_range=(0, bst.best_iteration + 1))

    # -----------------------------------------------------------------------
    # Fit Platt calibrator (D6.2: fixed)
    # -----------------------------------------------------------------------
    cal = PlattCalibrator(
        C=cfg["calibration"]["logistic_C"],
        max_iter=cfg["calibration"]["logistic_max_iter"],
        epsilon=cfg["calibration"]["epsilon"],
    )
    cal.fit(raw_scores, y_b1)
    proba_cal = cal.predict_proba(raw_scores)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cal_path = out_dir / "calibrator_90d.joblib"
    sha = cal.save(cal_path)
    rb = cal.readback_check(cal_path, raw_scores)

    ece = expected_calibration_error(y_b1, proba_cal)
    slope_res = calibration_slope_intercept(y_b1, proba_cal)

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "B1",
        "method": "platt_sigmoid",
        "calibrator_sha256": sha,
        "readback_allclose": rb["allclose"],
        "b1_rows": int(len(y_b1)),
        "b1_n_positive": int(y_b1.sum()),
        "b1_ece": ece,
        "b1_slope": slope_res["slope"],
        "b1_intercept": slope_res["intercept"],
        "b1_converged": slope_res["converged"],
        "b1_calibration_in_the_large": slope_res["calibration_in_the_large"],
        "embargo_accessed": False,
        "b2_accessed": False,
        "note": "D6.2 approved: Fixed Platt/sigmoid only. Isotonic deferred.",
    }
    manifest_path = out_dir / "calibration_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Calibration manifest: {manifest_path}")
    print("Gate B2 remains LOCKED. Separate authorization required.")


if __name__ == "__main__":
    main()
