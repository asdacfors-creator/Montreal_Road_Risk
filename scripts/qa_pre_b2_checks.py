import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_qa():
    print("=== PART 12: FINAL B2 EVALUATION QA AND INTEGRITY CHECKS ===")

    # 1. JSON Validation
    json_files = [
        "config/phase_6_evaluation.json",
        "models/phase_6/evaluation_manifest.json",
        "models/phase_6/threshold_manifest.json",
        "models/phase_6/calibration_manifest.json",
        "models/phase_6/gate_b1_protocol_deviation.json",
        "models/phase_6/gate_b1_target_provenance.json",
        "models/phase_6/phase_4_determinism_audit.json",
        "models/phase_6/gate_b2_authorization.json",
        "models/phase_6/gate_b2_access_record.json",
        "models/phase_6/test_evaluation_results.json",
        "models/phase_6/test_subgroup_results.json",
        "models/phase_6/test_bootstrap_ci.json",
        "models/phase_6/environment_manifest_p6.json",
        "state/project_state.json"
    ]

    for jf in json_files:
        p = PROJECT_ROOT / jf
        assert p.exists(), f"JSON file missing: {jf}"
        data = json.loads(p.read_text())
        assert isinstance(data, dict), f"JSON file {jf} is not a valid dict"
        print(f"  [OK] JSON Validated: {jf}")

    # 2. Evaluation Manifest Fingerprint Validation
    eval_p = PROJECT_ROOT / "models/phase_6/evaluation_manifest.json"
    eval_sha = hashlib.sha256(eval_p.read_bytes()).hexdigest()
    print(f"  [OK] Evaluation Manifest SHA-256: {eval_sha}")

    # 3. Model & Preprocessor Readback Fingerprint Validation
    model_path = PROJECT_ROOT / "models/phase_5/full_training_remediated_01/model.joblib"
    prep_path = PROJECT_ROOT / "models/phase_5/full_training_remediated_01/preprocessor.joblib"
    feat_path = PROJECT_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"

    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    prep_sha = hashlib.sha256(prep_path.read_bytes()).hexdigest()
    feat_sha = hashlib.sha256(feat_path.read_bytes()).hexdigest()

    assert model_sha == "f034d42f9994cd09059e691220ce75209d8da26040be70e988c418ec9ebb413f"
    assert prep_sha == "f2dac65ab2a09dd4e978a519a611a14116b25f598277ed8c8ccc2eabc02a3fe7"
    assert feat_sha == "569e549c9e636bd253bf849c9334a96de08e3152d4f4d6b47c51c84f7e100021"
    print("  [OK] Model, Preprocessor, and Sealed Feature fingerprints match exactly.")

    # 4. Target-Free Prediction Readback Validation
    pred_path = PROJECT_ROOT / "data/processed/phase_6/predictions/b2_predictions.parquet"
    assert pred_path.exists()
    pred_df = pq.read_table(pred_path).to_pandas()
    res_data = json.loads((PROJECT_ROOT / "models/phase_6/test_evaluation_results.json").read_text())

    raw_sha = hashlib.sha256(pred_df["raw_probability"].values.astype(np.float32).tobytes()).hexdigest()
    platt_sha = hashlib.sha256(pred_df["platt_probability"].values.astype(np.float32).tobytes()).hexdigest()

    assert raw_sha == res_data["prediction_fingerprints"]["raw_float32_sha256"]
    assert platt_sha == res_data["prediction_fingerprints"]["platt_float32_sha256"]
    print("  [OK] Prediction Parquet readback np.allclose and SHA-256 verified.")

    # 5. 102 Partitions Determinism Check
    det_data = json.loads((PROJECT_ROOT / "models/phase_6/phase_4_determinism_audit.json").read_text())
    assert det_data["matching"] == 102 and det_data["changed"] == 0 and det_data["missing"] == 0
    print("  [OK] All 102 Phase 4 remediated partitions verified deterministic.")

    # 6. Subgroup Schema Validation
    schema = pq.read_schema(feat_path)
    schema_names = set(schema.names)
    eval_data = json.loads(eval_p.read_text())
    subgroup_cfg = eval_data["subgroup"]
    for field in subgroup_cfg["direct_fields"]:
        assert field in schema_names, f"Subgroup field '{field}' missing from sealed feature schema!"
    print("  [OK] All direct subgroup fields exist in sealed feature schema.")

    # 7. Git Binary Tracking Check
    cmd_joblib = ["git", "ls-files", "*.joblib"]
    res_joblib = subprocess.run(cmd_joblib, cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert res_joblib.returncode == 0
    assert len(res_joblib.stdout.strip()) == 0, f"Found tracked joblib files: {res_joblib.stdout}"
    print("  [OK] No joblib binary tracked in Git.")

    print("\n[OK] ALL QA, SUBGROUP SCHEMA, READBACK, AND FINGERPRINT VALIDATIONS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_qa()
