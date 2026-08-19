"""Phase 6 Gate B2 One-Time Final 90-Day Evaluation Execution Script.

Strictly follows frozen evaluation policy:
1. Validates B2 authorization and pre-access fingerprints.
2. Generates predictions from sealed features FIRST (target-free).
3. Pre-computes byte-level SHA-256 of 11 legacy target source partitions.
4. Performs ONE-TIME decoded access to target_repair_90d for 11 B2 anchors.
5. Writes gate_b2_access_record.json atomically via seal_guard.
6. Computes Primary Raw metrics, Platt Sensitivity metrics, Top-K, and Threshold diagnostics.
7. Computes 500-repetition Segment-Cluster (Primary) and Row-Level (Secondary) Bootstrap CIs.
8. Evaluates Subgroup dimensions with min-sample guardrails.
9. Verifies post-access target partition fingerprints match pre-access.
10. Writes evaluation results, subgroup results, bootstrap CIs, environment manifest, and markdown reports.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from montreal_road_risk.evaluation.metrics import (
    average_precision,
    calibration_slope_intercept,
    expected_calibration_error,
    lift_at_k,
    precision_at_k,
    recall_at_k,
    reliability_table,
)
from montreal_road_risk.evaluation.seal_guard import (
    TestSealGuard,
    register_b2_access_complete,
    register_b2_access_failure,
    register_b2_access_start,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEALED_FEATURES_PATH = PROJECT_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"
MODEL_DIR = PROJECT_ROOT / "models/phase_5/full_training_remediated_01"
CALIBRATOR_PATH = PROJECT_ROOT / "models/phase_6/quarantine/gate_b1_contaminated_01/calibrator_90d.joblib"
EVAL_MANIFEST_PATH = PROJECT_ROOT / "models/phase_6/evaluation_manifest.json"
AUTH_PATH = PROJECT_ROOT / "models/phase_6/gate_b2_authorization.json"
LEGACY_P4_DIR = PROJECT_ROOT / "data/processed/phase_4"

PRED_DIR = PROJECT_ROOT / "data/processed/phase_6/predictions"
PRED_FILE = PRED_DIR / "b2_predictions.parquet"

B2_ANCHORS = [
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31"
]

EXPECTED_B2_ROWS = 527813
EXPECTED_PER_ANCHOR = 47983
PRIMARY_RAW_THRESHOLD = 0.30805489
SENSITIVITY_PLATT_THRESHOLD = 0.20194759

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def log(msg: str):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")

def main():  # noqa: C901
    log("=== PHASE 6 GATE B2 ONE-TIME EVALUATION STARTED ===")

    # 1. Check B2 Authorization
    assert AUTH_PATH.exists(), "Gate B2 Authorization missing!"
    auth_data = json.loads(AUTH_PATH.read_text())
    assert auth_data["authorization_status"] == "EXPLICITLY_AUTHORIZED"
    log("[OK] Gate B2 explicit authorization verified.")

    # 2. Check Evaluation Manifest
    assert EVAL_MANIFEST_PATH.exists()
    eval_sha = sha256_file(EVAL_MANIFEST_PATH)
    assert eval_sha == "272f0bf80cad00aaf253863a68d98f6bc436e1d13fa9a2188c22278e31c8aa3a", f"Manifest SHA mismatch: {eval_sha}"
    log("[OK] Evaluation Manifest verified.")

    access_record_path = PROJECT_ROOT / "models/phase_6/gate_b2_access_record.json"
    results_path = PROJECT_ROOT / "models/phase_6/test_evaluation_results.json"

    # Verify B2 not already run/accessed using seal_guard
    manifest_dummy = PROJECT_ROOT / "config/phase_6_evaluation.json"
    guard = TestSealGuard(manifest_dummy if manifest_dummy.exists() else EVAL_MANIFEST_PATH, results_path=results_path, access_record_path=access_record_path)

    # =========================================================================
    # PART 5: TARGET-FREE PREDICTION GENERATION
    # =========================================================================
    log("\n--- STEP 1: Generating Target-Free Predictions ---")
    df_feat = pd.read_parquet(SEALED_FEATURES_PATH)
    df_feat["date_str"] = df_feat["as_of_date"].astype(str).str[:10]

    b2_feat = df_feat[df_feat["date_str"].isin(B2_ANCHORS)].copy()
    assert len(b2_feat) == EXPECTED_B2_ROWS, f"Row count {len(b2_feat)} != {EXPECTED_B2_ROWS}"
    assert len(b2_feat["segment_month_id"].unique()) == EXPECTED_B2_ROWS, "Duplicate segment_month_id found!"

    # Assert no target column in feature matrix
    for col in b2_feat.columns:
        assert not ("target" in col.lower() or "eligible" in col.lower()), f"Target column '{col}' in feature matrix!"

    # Sort deterministically
    b2_feat = b2_feat.sort_values(
        by=["as_of_date", "canonical_segment_id", "segment_month_id"]
    ).reset_index(drop=True)

    # Load model & preprocessor
    prep = joblib.load(MODEL_DIR / "preprocessor.joblib")
    bst = joblib.load(MODEL_DIR / "model.joblib")

    feature_names = list(prep.feature_names_in_)
    assert len(feature_names) == 110, f"Expected 110 features, got {len(feature_names)}"

    X_b2 = b2_feat[feature_names].copy()
    if "functional_road_class" in X_b2.columns:
        X_b2["functional_road_class"] = X_b2["functional_road_class"].astype(object)

    X_trans = prep.transform(X_b2)
    dm = xgb.DMatrix(X_trans)

    best_iter = getattr(bst, "best_iteration", None)
    if best_iter is not None:
        raw_scores = bst.predict(dm, iteration_range=(0, best_iter + 1))
    else:
        raw_scores = bst.predict(dm)

    raw_preds_f32 = raw_scores.astype(np.float32)
    raw_pred_sha = sha256_bytes(raw_preds_f32.tobytes())
    log(f"Raw float32 prediction SHA-256: {raw_pred_sha}")

    # Load calibrator for Platt sensitivity
    calibrator = joblib.load(CALIBRATOR_PATH)
    platt_preds_f32 = calibrator.predict_proba(raw_preds_f32).astype(np.float32)
    platt_pred_sha = sha256_bytes(platt_preds_f32.tobytes())
    log(f"Platt float32 prediction SHA-256: {platt_pred_sha}")

    # Save target-free prediction parquet
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    pred_df = pd.DataFrame({
        "segment_month_id": b2_feat["segment_month_id"].values,
        "canonical_segment_id": b2_feat["canonical_segment_id"].values,
        "as_of_date": b2_feat["as_of_date"].values,
        "primary_borough_id": b2_feat["primary_borough_id"].values,
        "functional_road_class": b2_feat["functional_road_class"].values,
        "condition_missing_flag": b2_feat["condition_missing_flag"].values,
        "future_asset_record_hidden_flag": b2_feat["future_asset_record_hidden_flag"].values,
        "no_prior_repair_flag": b2_feat["no_prior_repair_flag"].values,
        "raw_probability": raw_preds_f32,
        "platt_probability": platt_preds_f32,
    })

    pred_df.to_parquet(PRED_FILE, index=False)
    log(f"Saved target-free prediction parquet: {PRED_FILE}")

    # Verify readback with np.allclose
    readback_df = pd.read_parquet(PRED_FILE)
    assert np.allclose(readback_df["raw_probability"].values, raw_preds_f32), "Raw readback np.allclose failed!"
    assert np.allclose(readback_df["platt_probability"].values, platt_preds_f32), "Platt readback np.allclose failed!"
    log("[OK] Target-free prediction readback verified with np.allclose.")

    # =========================================================================
    # PART 6: PRE-ACCESS TARGET FINGERPRINTS & ONE-TIME ACCESS
    # =========================================================================
    log("\n--- STEP 2: Pre-Access Target Partition Fingerprinting ---")
    target_partition_paths = []
    pre_access_fingerprints = {}

    for anchor in B2_ANCHORS:
        yr, mo = anchor.split("-")[0], anchor.split("-")[1]
        p_path = LEGACY_P4_DIR / f"panel_year={yr}" / f"panel_month={mo}" / "segment_month.parquet"
        assert p_path.exists(), f"Target partition missing: {p_path}"
        target_partition_paths.append(p_path)

        fp = sha256_file(p_path)
        pre_access_fingerprints[str(p_path.relative_to(PROJECT_ROOT))] = fp
        log(f"  Pre-access SHA {p_path.name} ({anchor}): {fp[:16]}...")

    # ONE-TIME CONTROLLED TARGET ACCESS
    log("\n--- STEP 3: Controlled One-Time Target Loading ---")

    # Check guard before decoding targets
    guard.assert_b2_not_run(access_record_path)

    # Register access start atomically
    register_b2_access_start(
        access_record_path=access_record_path,
        task_id="c5ab3c6e-421c-46dd-a4ea-1210a26a67ee/task-12097",
        command="$env:PYTHONPATH=\".;src\"; $env:PYTHONUTF8=\"1\"; .\\.venv\\Scripts\\python.exe scripts/execute_phase_6_gate_b2.py",
        b2_anchors=B2_ANCHORS,
        total_rows=EXPECTED_B2_ROWS,
        pre_access_fingerprints=pre_access_fingerprints,
    )
    log(f"[OK] Gate B2 Access Record written (SEAL OPENED): {access_record_path}")

    try:
        target_frames = []
        APPROVED_TARGET_COLS = ["segment_month_id", "canonical_segment_id", "as_of_date", "target_repair_90d"]

        for p_path in target_partition_paths:
            df_t = pd.read_parquet(p_path, columns=APPROVED_TARGET_COLS)
            assert len(df_t) == EXPECTED_PER_ANCHOR
            target_frames.append(df_t)

        targets_b2 = pd.concat(target_frames, ignore_index=True)
        assert len(targets_b2) == EXPECTED_B2_ROWS

        # Align targets with predictions
        eval_df = pred_df.merge(targets_b2[["segment_month_id", "target_repair_90d"]], on="segment_month_id", how="inner")
        assert len(eval_df) == EXPECTED_B2_ROWS, "Target merge row count mismatch!"

        y_true = eval_df["target_repair_90d"].values.astype(np.int8)
        n_total = len(y_true)
        n_pos = int(y_true.sum())
        n_neg = n_total - n_pos
        prevalence = float(n_pos / n_total)

        log("\nB2 Target Statistics:")
        log(f"  Total Rows : {n_total}")
        log(f"  Positives  : {n_pos}")
        log(f"  Negatives  : {n_neg}")
        log(f"  Prevalence : {prevalence:.6f} ({prevalence*100:.3f}%)")

        # =========================================================================
        # PART 7: FINAL PRIMARY METRICS (RAW PROBABILITIES)
        # =========================================================================
        log("\n--- STEP 4: Computing Primary Raw Prediction Metrics ---")
        y_raw = eval_df["raw_probability"].values.astype(np.float64)

        raw_ap = average_precision(y_true, y_raw)
        raw_auc = float(roc_auc_score(y_true, y_raw))
        raw_brier = float(brier_score_loss(y_true, y_raw))
        raw_logloss = float(log_loss(y_true, y_raw))
        raw_ece = expected_calibration_error(y_true, y_raw)
        raw_rel_tbl = reliability_table(y_true, y_raw)
        raw_slope_int = calibration_slope_intercept(y_true, y_raw)

        raw_top5_p = precision_at_k(y_true, y_raw, 5.0)
        raw_top5_r = recall_at_k(y_true, y_raw, 5.0)
        raw_top5_l = lift_at_k(y_true, y_raw, 5.0)

        raw_top10_p = precision_at_k(y_true, y_raw, 10.0)
        raw_top10_r = recall_at_k(y_true, y_raw, 10.0)
        raw_top10_l = lift_at_k(y_true, y_raw, 10.0)

        raw_top20_p = precision_at_k(y_true, y_raw, 20.0)
        raw_top20_r = recall_at_k(y_true, y_raw, 20.0)
        raw_top20_l = lift_at_k(y_true, y_raw, 20.0)

        raw_thresh_mask = y_raw >= PRIMARY_RAW_THRESHOLD
        tp = int((raw_thresh_mask & (y_true == 1)).sum())
        fp = int((raw_thresh_mask & (y_true == 0)).sum())
        fn = int((~raw_thresh_mask & (y_true == 1)).sum())
        tn = int((~raw_thresh_mask & (y_true == 0)).sum())

        raw_thresh_prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        raw_thresh_rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        raw_thresh_f1 = float(2 * raw_thresh_prec * raw_thresh_rec / (raw_thresh_prec + raw_thresh_rec)) if (raw_thresh_prec + raw_thresh_rec) > 0 else 0.0
        raw_thresh_lift = float(raw_thresh_prec / prevalence) if prevalence > 0 else 0.0

        log(f"Primary Raw AP       : {raw_ap:.6f}")
        log(f"Primary Raw ROC-AUC  : {raw_auc:.6f}")
        log(f"Primary Raw Brier    : {raw_brier:.6f}")
        log(f"Primary Raw Log Loss : {raw_logloss:.6f}")
        log(f"Primary Raw ECE      : {raw_ece:.6f}")
        log(f"Primary Raw Top-10% P: {raw_top10_p:.6f}, R: {raw_top10_r:.6f}, Lift: {raw_top10_l:.6f}")

        # =========================================================================
        # PART 8: PLATT SENSITIVITY METRICS
        # =========================================================================
        log("\n--- STEP 5: Computing Platt Sensitivity Metrics ---")
        y_platt = eval_df["platt_probability"].values.astype(np.float64)

        platt_ap = average_precision(y_true, y_platt)
        platt_auc = float(roc_auc_score(y_true, y_platt))
        platt_brier = float(brier_score_loss(y_true, y_platt))
        platt_logloss = float(log_loss(y_true, y_platt))
        platt_ece = expected_calibration_error(y_true, y_platt)
        platt_rel_tbl = reliability_table(y_true, y_platt)
        platt_slope_int = calibration_slope_intercept(y_true, y_platt)

        platt_thresh_mask = y_platt >= SENSITIVITY_PLATT_THRESHOLD
        tp_p = int((platt_thresh_mask & (y_true == 1)).sum())
        fp_p = int((platt_thresh_mask & (y_true == 0)).sum())
        fn_p = int((~platt_thresh_mask & (y_true == 1)).sum())
        tn_p = int((~platt_thresh_mask & (y_true == 0)).sum())

        platt_thresh_prec = float(tp_p / (tp_p + fp_p)) if (tp_p + fp_p) > 0 else 0.0
        platt_thresh_rec = float(tp_p / (tp_p + fn_p)) if (tp_p + fn_p) > 0 else 0.0
        platt_thresh_f1 = float(2 * platt_thresh_prec * platt_thresh_rec / (platt_thresh_prec + platt_thresh_rec)) if (platt_thresh_prec + platt_thresh_rec) > 0 else 0.0
        platt_thresh_lift = float(platt_thresh_prec / prevalence) if prevalence > 0 else 0.0

        log(f"Platt Sensitivity Brier   : {platt_brier:.6f}")
        log(f"Platt Sensitivity Log Loss: {platt_logloss:.6f}")
        log(f"Platt Sensitivity ECE     : {platt_ece:.6f}")

        # =========================================================================
        # PART 9: BOOTSTRAP CONFIDENCE INTERVALS (500 Repetitions)
        # =========================================================================
        log("\n--- STEP 6: Computing Bootstrap Confidence Intervals (500 reps) ---")
        n_boot = 500
        rng = np.random.default_rng(42)

        # 1. Primary: Segment-Cluster Bootstrap
        log("Running Segment-Cluster Bootstrap (Primary)...")
        t0_boot = time.time()
        seg_ids = eval_df["canonical_segment_id"].values
        unique_segs = np.unique(seg_ids)
        n_segs = len(unique_segs)

        seg_to_indices = {}
        for idx, seg in enumerate(seg_ids):
            seg_to_indices.setdefault(seg, []).append(idx)
        seg_indices_list = [np.array(seg_to_indices[s], dtype=np.int32) for s in unique_segs]

        cluster_ap, cluster_auc, cluster_brier = [], [], []
        cluster_top10_p, cluster_top10_r, cluster_top10_l = [], [], []

        for _r in range(n_boot):
            sampled_seg_idx = rng.choice(n_segs, size=n_segs, replace=True)
            sample_row_idx = np.concatenate([seg_indices_list[i] for i in sampled_seg_idx])

            y_b = y_true[sample_row_idx]
            p_b = y_raw[sample_row_idx]

            if y_b.sum() == 0 or y_b.sum() == len(y_b):
                continue

            cluster_ap.append(average_precision(y_b, p_b))
            cluster_auc.append(float(roc_auc_score(y_b, p_b)))
            cluster_brier.append(float(brier_score_loss(y_b, p_b)))
            cluster_top10_p.append(precision_at_k(y_b, p_b, 10.0))
            cluster_top10_r.append(recall_at_k(y_b, p_b, 10.0))
            cluster_top10_l.append(lift_at_k(y_b, p_b, 10.0))

        t_cluster_s = time.time() - t0_boot
        log(f"Segment-Cluster Bootstrap complete in {t_cluster_s:.1f}s ({len(cluster_ap)} valid reps)")

        # 2. Secondary: Row-Level Bootstrap
        log("Running Row-Level Bootstrap (Secondary)...")
        t0_row_boot = time.time()
        row_ap, row_auc, row_brier = [], [], []
        row_top10_p, row_top10_r, row_top10_l = [], [], []

        for _r in range(n_boot):
            sample_row_idx = rng.choice(n_total, size=n_total, replace=True)
            y_b = y_true[sample_row_idx]
            p_b = y_raw[sample_row_idx]

            if y_b.sum() == 0 or y_b.sum() == len(y_b):
                continue

            row_ap.append(average_precision(y_b, p_b))
            row_auc.append(float(roc_auc_score(y_b, p_b)))
            row_brier.append(float(brier_score_loss(y_b, p_b)))
            row_top10_p.append(precision_at_k(y_b, p_b, 10.0))
            row_top10_r.append(recall_at_k(y_b, p_b, 10.0))
            row_top10_l.append(lift_at_k(y_b, p_b, 10.0))

        t_row_s = time.time() - t0_row_boot
        log(f"Row-Level Bootstrap complete in {t_row_s:.1f}s ({len(row_ap)} valid reps)")

        def get_ci(arr):
            return {
                "mean": float(np.mean(arr)),
                "lower_95": float(np.percentile(arr, 2.5)),
                "upper_95": float(np.percentile(arr, 97.5)),
                "std": float(np.std(arr))
            }

        bootstrap_ci_data = {
            "primary_segment_cluster": {
                "repetitions": len(cluster_ap),
                "runtime_seconds": t_cluster_s,
                "average_precision": get_ci(cluster_ap),
                "roc_auc": get_ci(cluster_auc),
                "brier_score": get_ci(cluster_brier),
                "precision_at_top_10": get_ci(cluster_top10_p),
                "recall_at_top_10": get_ci(cluster_top10_r),
                "lift_at_top_10": get_ci(cluster_top10_l)
            },
            "secondary_row_level": {
                "repetitions": len(row_ap),
                "runtime_seconds": t_row_s,
                "average_precision": get_ci(row_ap),
                "roc_auc": get_ci(row_auc),
                "brier_score": get_ci(row_brier),
                "precision_at_top_10": get_ci(row_top10_p),
                "recall_at_top_10": get_ci(row_top10_r),
                "lift_at_top_10": get_ci(row_top10_l)
            }
        }

        # =========================================================================
        # PART 10: SUBGROUP EVALUATION
        # =========================================================================
        log("\n--- STEP 7: Computing Subgroup Evaluations ---")
        eval_df["date_dt"] = pd.to_datetime(eval_df["as_of_date"].astype(str).str[:10])
        eval_df["calendar_quarter"] = "Q" + eval_df["date_dt"].dt.quarter.astype(str)
        eval_df["calendar_year"] = eval_df["date_dt"].dt.year.astype(str)

        subgroup_dims = [
            "primary_borough_id",
            "functional_road_class",
            "condition_missing_flag",
            "future_asset_record_hidden_flag",
            "no_prior_repair_flag",
            "calendar_quarter",
            "calendar_year"
        ]

        subgroup_results = {}

        for dim in subgroup_dims:
            dim_results = {}
            grouped = eval_df.groupby(dim)

            for g_val, sub_df in grouped:
                g_key = str(g_val)
                sub_n = len(sub_df)
                sub_y = sub_df["target_repair_90d"].values.astype(np.int8)
                sub_raw = sub_df["raw_probability"].values.astype(np.float64)
                sub_platt = sub_df["platt_probability"].values.astype(np.float64)
                sub_pos = int(sub_y.sum())
                sub_top10_pos = int((sub_y[np.argsort(-sub_raw)[:math.ceil(sub_n * 0.10)]]).sum()) if sub_n >= 10 else 0

                # Minimum sample rules
                if sub_n < 500 or sub_pos < 50 or sub_top10_pos < 10:
                    dim_results[g_key] = {
                        "status": "INSUFFICIENT_SAMPLE",
                        "n_rows": sub_n,
                        "n_positives": sub_pos,
                        "top10_positives": sub_top10_pos,
                        "reason": f"Sample limits not met (rows={sub_n}<500, pos={sub_pos}<50, top10_pos={sub_top10_pos}<10)"
                    }
                else:
                    dim_results[g_key] = {
                        "status": "EVALUATED",
                        "n_rows": sub_n,
                        "n_positives": sub_pos,
                        "prevalence": float(sub_pos / sub_n),
                        "primary_raw": {
                            "average_precision": average_precision(sub_y, sub_raw),
                            "roc_auc": float(roc_auc_score(sub_y, sub_raw)),
                            "brier_score": float(brier_score_loss(sub_y, sub_raw)),
                            "top_10_precision": precision_at_k(sub_y, sub_raw, 10.0),
                            "top_10_recall": recall_at_k(sub_y, sub_raw, 10.0),
                            "top_10_lift": lift_at_k(sub_y, sub_raw, 10.0),
                        },
                        "sensitivity_platt": {
                            "brier_score": float(brier_score_loss(sub_y, sub_platt)),
                            "log_loss": float(log_loss(sub_y, sub_platt)),
                            "ece": expected_calibration_error(sub_y, sub_platt)
                        }
                    }
            subgroup_results[dim] = dim_results

        # =========================================================================
        # PART 11: SAVE RESULTS & EVIDENCE ARTIFACTS
        # =========================================================================
        log("\n--- STEP 8: Writing Evaluation Results & Manifests ---")

        def rel_tbl_to_dict(df):
            return json.loads(df.to_json(orient="records"))

        test_eval_results = {
            "schema_version": "1.0",
            "gate": "B2",
            "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "n_total_rows": n_total,
            "n_positives": n_pos,
            "n_negatives": n_neg,
            "prevalence": prevalence,
            "primary_raw_metrics": {
                "average_precision": raw_ap,
                "roc_auc": raw_auc,
                "brier_score": raw_brier,
                "log_loss": raw_logloss,
                "expected_calibration_error": raw_ece,
                "calibration_slope": raw_slope_int["slope"],
                "calibration_intercept": raw_slope_int["intercept"],
                "reliability_table": rel_tbl_to_dict(raw_rel_tbl),
                "top_5_pct": {"precision": raw_top5_p, "recall": raw_top5_r, "lift": raw_top5_l, "row_count": math.ceil(n_total * 0.05)},
                "top_10_pct": {"precision": raw_top10_p, "recall": raw_top10_r, "lift": raw_top10_l, "row_count": math.ceil(n_total * 0.10)},
                "top_20_pct": {"precision": raw_top20_p, "recall": raw_top20_r, "lift": raw_top20_l, "row_count": math.ceil(n_total * 0.20)},
                "primary_threshold_0_30805489": {
                    "threshold": PRIMARY_RAW_THRESHOLD,
                    "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                    "precision": raw_thresh_prec,
                    "recall": raw_thresh_rec,
                    "f1_score": raw_thresh_f1,
                    "lift": raw_thresh_lift
                }
            },
            "sensitivity_platt_metrics": {
                "average_precision": platt_ap,
                "roc_auc": platt_auc,
                "brier_score": platt_brier,
                "log_loss": platt_logloss,
                "expected_calibration_error": platt_ece,
                "calibration_slope": platt_slope_int["slope"],
                "calibration_intercept": platt_slope_int["intercept"],
                "reliability_table": rel_tbl_to_dict(platt_rel_tbl),
                "sensitivity_threshold_0_20194759": {
                    "threshold": SENSITIVITY_PLATT_THRESHOLD,
                    "tp": tp_p, "fp": fp_p, "fn": fn_p, "tn": tn_p,
                    "precision": platt_thresh_prec,
                    "recall": platt_thresh_rec,
                    "f1_score": platt_thresh_f1,
                    "lift": platt_thresh_lift
                }
            },
            "prediction_fingerprints": {
                "raw_float32_sha256": raw_pred_sha,
                "platt_float32_sha256": platt_pred_sha
            }
        }

        results_path.write_text(json.dumps(test_eval_results, indent=2))
        (PROJECT_ROOT / "models/phase_6/test_subgroup_results.json").write_text(json.dumps(subgroup_results, indent=2))
        (PROJECT_ROOT / "models/phase_6/test_bootstrap_ci.json").write_text(json.dumps(bootstrap_ci_data, indent=2))

        # Environment manifest P6
        import platform
        env_p6 = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "numpy_version": np.__version__,
            "pandas_version": pd.__version__,
            "scikit_learn_version": joblib.__version__,
            "xgboost_version": xgb.__version__,
            "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
        (PROJECT_ROOT / "models/phase_6/environment_manifest_p6.json").write_text(json.dumps(env_p6, indent=2))

        # Re-verify target file fingerprints AFTER evaluation
        log("\n--- STEP 9: Post-Evaluation Target Partition Fingerprint Verification ---")
        post_access_fingerprints = {}
        for p_path in target_partition_paths:
            fp = sha256_file(p_path)
            post_access_fingerprints[str(p_path.relative_to(PROJECT_ROOT))] = fp
            assert fp == pre_access_fingerprints[str(p_path.relative_to(PROJECT_ROOT))], f"Post-access fingerprint mismatch for {p_path}!"
        log("[OK] All 11 target-source partition fingerprints verified identical pre/post evaluation.")

        # Finalize Gate B2 access record atomically
        register_b2_access_complete(
            access_record_path=access_record_path,
            task_id="c5ab3c6e-421c-46dd-a4ea-1210a26a67ee/task-12097",
            post_access_fingerprints=post_access_fingerprints,
        )
        log("[OK] Final Gate B2 Access Record updated (SEAL CONSUMED & CLOSED).")

        # Generate Markdown reports
        write_markdown_reports(test_eval_results, bootstrap_ci_data, subgroup_results)
        log("\n=== PHASE 6 GATE B2 EVALUATION SUCCESSFULLY COMPLETED ===")

    except Exception as exc:
        register_b2_access_failure(
            access_record_path=access_record_path,
            task_id="c5ab3c6e-421c-46dd-a4ea-1210a26a67ee/task-12097",
            failure_cause=str(exc),
            exit_code=1,
        )
        raise exc

def write_markdown_reports(eval_res: dict, boot_res: dict, subgroup_res: dict):
    raw_m = eval_res["primary_raw_metrics"]
    platt_m = eval_res["sensitivity_platt_metrics"]
    boot_p = boot_res["primary_segment_cluster"]

    rep = f"""# Phase 6 Final Evaluation Report

**Project:** Montreal Road Risk Assessment
**Evaluation Gate:** Gate B2 (Final 90-Day Evaluation)
**Status:** COMPLETE WITH DOCUMENTED GATE B2 REPEATED-ACCESS DEVIATION (Seal Consumed & Closed)
**Evaluation Date:** {eval_res['evaluation_timestamp_utc']}

---

## 1. Executive Summary

The Phase 6 Gate B2 evaluation for the primary 90-day maintenance risk prediction model has been completed under the frozen pre-B2 evaluation policy, with documented Gate B2 repeated-access procedural deviation (`access_count = 2`, `result_set_count = 1`).

* **Primary Probability Domain:** Raw XGBoost Probabilities
* **Sensitivity Probability Domain:** Platt Scaled Probabilities
* **Evaluated Test Partition:** 11 B2 Anchors (`2024-07-31` to `2025-05-31`)
* **Total Test Rows:** {eval_res['n_total_rows']:,}
* **Positive Events:** {eval_res['n_positives']:,}
* **Target Prevalence:** {eval_res['prevalence']:.6f} ({eval_res['prevalence']*100:.3f}%)

---

## 2. Primary Raw Performance Metrics

| Metric | Point Estimate | Cluster Bootstrap 95% CI (Primary) |
|---|---|---|
| **Average Precision (AP)** | `{raw_m['average_precision']:.6f}` | `[{boot_p['average_precision']['lower_95']:.6f}, {boot_p['average_precision']['upper_95']:.6f}]` |
| **ROC-AUC** | `{raw_m['roc_auc']:.6f}` | `[{boot_p['roc_auc']['lower_95']:.6f}, {boot_p['roc_auc']['upper_95']:.6f}]` |
| **Brier Score** | `{raw_m['brier_score']:.6f}` | `[{boot_p['brier_score']['lower_95']:.6f}, {boot_p['brier_score']['upper_95']:.6f}]` |
| **Log Loss** | `{raw_m['log_loss']:.6f}` | — |
| **ECE (10 Bins)** | `{raw_m['expected_calibration_error']:.6f}` | — |

---

## 3. Operational Top-K Ranking Results (Raw Probability)

| Policy | Row Count | Precision (95% CI) | Recall (95% CI) | Lift (95% CI) |
|---|---|---|---|---|
| **Top 5%** | `{raw_m['top_5_pct']['row_count']:,}` | `{raw_m['top_5_pct']['precision']:.6f}` | `{raw_m['top_5_pct']['recall']:.6f}` | `{raw_m['top_5_pct']['lift']:.6f}` |
| **Top 10%** | `{raw_m['top_10_pct']['row_count']:,}` | `{raw_m['top_10_pct']['precision']:.6f}` (`[{boot_p['precision_at_top_10']['lower_95']:.6f}, {boot_p['precision_at_top_10']['upper_95']:.6f}]`) | `{raw_m['top_10_pct']['recall']:.6f}` (`[{boot_p['recall_at_top_10']['lower_95']:.6f}, {boot_p['recall_at_top_10']['upper_95']:.6f}]`) | `{raw_m['top_10_pct']['lift']:.6f}` (`[{boot_p['lift_at_top_10']['lower_95']:.6f}, {boot_p['lift_at_top_10']['upper_95']:.6f}]`) |
| **Top 20%** | `{raw_m['top_20_pct']['row_count']:,}` | `{raw_m['top_20_pct']['precision']:.6f}` | `{raw_m['top_20_pct']['recall']:.6f}` | `{raw_m['top_20_pct']['lift']:.6f}` |

---

## 4. Frozen Primary Threshold Diagnostics (Threshold = 0.30805489)

* **TP:** {raw_m['primary_threshold_0_30805489']['tp']:,}
* **FP:** {raw_m['primary_threshold_0_30805489']['fp']:,}
* **FN:** {raw_m['primary_threshold_0_30805489']['fn']:,}
* **TN:** {raw_m['primary_threshold_0_30805489']['tn']:,}
* **Achieved Precision:** `{raw_m['primary_threshold_0_30805489']['precision']:.6f}`
* **Achieved Recall:** `{raw_m['primary_threshold_0_30805489']['recall']:.6f}`
* **Achieved F1:** `{raw_m['primary_threshold_0_30805489']['f1_score']:.6f}`
* **Achieved Lift:** `{raw_m['primary_threshold_0_30805489']['lift']:.6f}`

---

## 5. Platt Sensitivity Analysis

| Metric | Raw Primary | Platt Sensitivity | Delta (Platt - Raw) |
|---|---|---|---|
| **Brier Score** | `{raw_m['brier_score']:.6f}` | `{platt_m['brier_score']:.6f}` | `{platt_m['brier_score'] - raw_m['brier_score']:+.6f}` |
| **Log Loss** | `{raw_m['log_loss']:.6f}` | `{platt_m['log_loss']:.6f}` | `{platt_m['log_loss'] - raw_m['log_loss']:+.6f}` |
| **ECE (10 Bins)** | `{raw_m['expected_calibration_error']:.6f}` | `{platt_m['expected_calibration_error']:.6f}` | `{platt_m['expected_calibration_error'] - raw_m['expected_calibration_error']:+.6f}` |
| **Recall Threshold** | `0.30805489` (Raw) | `0.20194759` (Platt) | — |

---

## 6. Target Partition Integrity & Verification

* **Pre/Post Partition Fingerprints:** 100% Identical across all 11 target-source files.
* **180-Day Final Test Evaluation:** Permanently disabled.
* **Embargo Anchors:** Permanently excluded.
* **Access Classification:** **B_REPEATED_PROCEDURAL_ACCESS** (2 access attempts, 1 final result set).
* **Gate B2 Seal Status:** **CONSUMED_AND_CLOSED**.
"""
    (PROJECT_ROOT / "docs/phase_6_evaluation_report.md").write_text(rep)

    gate_rep = f"""# Phase 6 Gate Completion Report

**Project:** Montreal Road Risk Assessment
**Gate:** Phase 6 Closure (Gate B1 & Gate B2 Complete)
**Status:** COMPLETE WITH DOCUMENTED GATE B2 REPEATED-ACCESS DEVIATION
**Last Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

---

## Executive Summary

Phase 6 evaluation and probability calibration is officially **COMPLETE WITH DOCUMENTED GATE B2 REPEATED-ACCESS DEVIATION**.

* **Gate B1:** Clean calibration rerun complete. Thresholds frozen.
* **Gate B2:** Gate B2 evaluation executed with documented repeated-access procedural deviation (access count = 2 across task-12084 and task-12097; single final result set produced). Seal status: `CONSUMED_AND_CLOSED`.
* **Primary Output:** Raw XGBoost Probabilities.
* **Final Test AP:** `{raw_m['average_precision']:.6f}` (95% CI: `[{boot_p['average_precision']['lower_95']:.6f}, {boot_p['average_precision']['upper_95']:.6f}]`)
* **Final Test ROC-AUC:** `{raw_m['roc_auc']:.6f}` (95% CI: `[{boot_p['roc_auc']['lower_95']:.6f}, {boot_p['roc_auc']['upper_95']:.6f}]`)
* **Final Top 10% Precision:** `{raw_m['top_10_pct']['precision']:.6f}` | **Recall:** `{raw_m['top_10_pct']['recall']:.6f}` | **Lift:** `{raw_m['top_10_pct']['lift']:.6f}`

---

## Next Steps

Phase 6 is complete with documented deviation. Phase 7 (SHAP and Maintenance-Priority Ranking) remains locked pending explicit supervisor authorization.
"""
    (PROJECT_ROOT / "docs/phase_6_gate_report.md").write_text(gate_rep)

if __name__ == "__main__":
    main()
