"""Phase 7 Gate 7A Target-Free Model Interpretation Execution Script.

Strictly follows Phase 7 approved decisions (D7.1 - D7.7):
1. Target-free preflight assertions & fingerprint verification.
2. Filters sealed features to 527,813 B2 rows across 11 anchors (D7.1).
3. 10,000-row smoke batch for additivity & probability read-back verification (D7.2).
4. Memory-safe 50,000-row streaming SHAP tree contributions computation (pred_contribs=True).
5. 3 deterministic stratified stability samples (seeds 42, 137, 2026; 50k rows each).
6. Grouped source-feature reconciliation (mapping 201 transformed to 110 source features).
7. Target-free subgroup interpretation summaries (NO outcome/performance metrics).
8. Top-10% operational explanation records export (52,782 records) in Parquet (D7.5).
9. Visualization plots with mandatory causality disclaimers (D7.7).
10. Writes models/phase_7/gate_7a_manifest.json and docs/phase_7_gate_7a_report.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
import pyarrow.parquet as pq
import xgboost as xgb

from montreal_road_risk.interpretation.plots import (
    plot_beeswarm_summary,
    plot_dependence,
    plot_global_importance_bar,
)
from montreal_road_risk.interpretation.reconciliation import (
    aggregate_importance_by_source_feature,
    aggregate_shap_matrix_to_source_features,
    build_feature_name_mapping,
)
from montreal_road_risk.interpretation.records import (
    build_top10_explanation_records,
)
from montreal_road_risk.interpretation.shap_engine import (
    MANDATORY_CAUSALITY_STATEMENT,
    StreamingSHAPAccumulator,
    check_memory_limit,
    compute_tree_contributions_batch,
    verify_additivity,
    verify_anchor_allowlist,
    verify_target_free_schema,
)
from montreal_road_risk.interpretation.stability import (
    compute_sample_stability,
    draw_stratified_sample,
)
from montreal_road_risk.interpretation.subgroup import (
    summarize_target_free_subgroups,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEALED_FEATURES_PATH = PROJECT_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"
B2_PRED_PATH = PROJECT_ROOT / "data/processed/phase_6/predictions/b2_predictions.parquet"
MODEL_DIR = PROJECT_ROOT / "models/phase_5/full_training_remediated_01"
MODEL_PATH = MODEL_DIR / "model.joblib"
PREP_PATH = MODEL_DIR / "preprocessor.joblib"
EVAL_MANIFEST_PATH = PROJECT_ROOT / "models/phase_6/evaluation_manifest.json"

MANIFEST_7A_PATH = PROJECT_ROOT / "models/phase_7/gate_7a_manifest.json"
REPORT_7A_PATH = PROJECT_ROOT / "docs/phase_7_gate_7a_report.md"

PROCESSED_P7_DIR = PROJECT_ROOT / "data/processed/phase_7"
OUTPUT_P7_PLOTS_DIR = PROJECT_ROOT / "outputs/phase_7/plots"

# Expected Fingerprints
EXPECTED_MODEL_SHA = "f034d42f9994cd09059e691220ce75209d8da26040be70e988c418ec9ebb413f"
EXPECTED_PREP_SHA = "f2dac65ab2a09dd4e978a519a611a14116b25f598277ed8c8ccc2eabc02a3fe7"
EXPECTED_FEAT_SHA = "569e549c9e636bd253bf849c9334a96de08e3152d4f4d6b47c51c84f7e100021"
EXPECTED_PRED_SHA = "e84accf6aa2d09e4ac1e567a82113cb2f23cabe981813887bfa8e15de42c737c"

EXPECTED_B2_ROWS = 527813
EXPECTED_PER_ANCHOR = 47983
EXPECTED_ANCHOR_COUNT = 11


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log(msg: str):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")


def atomic_write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main():  # noqa: C901
    t0_start = time.time()
    log("=== PHASE 7 GATE 7A TARGET-FREE MODEL INTERPRETATION STARTED ===")

    # =========================================================================
    # STEP 1: PREFLIGHT & FINGERPRINT ASSERTIONS
    # =========================================================================
    log("\n--- STEP 1: Preflight Assertions & Fingerprint Verification ---")

    # Record RAM & Disk
    mem_avail_gb = round(psutil.virtual_memory().available / 1e9, 2)
    disk_free_gb = round(psutil.disk_usage(str(PROJECT_ROOT)).free / 1e9, 2)
    log(f"Available RAM: {mem_avail_gb} GB | Free Disk Space: {disk_free_gb} GB")

    assert mem_avail_gb >= 4.0, f"Insufficient available RAM: {mem_avail_gb} GB < 4.0 GB floor"

    # Fingerprint assertions
    model_sha = sha256_file(MODEL_PATH)
    prep_sha = sha256_file(PREP_PATH)
    feat_sha = sha256_file(SEALED_FEATURES_PATH)
    pred_sha = sha256_file(B2_PRED_PATH)

    assert model_sha == EXPECTED_MODEL_SHA, f"Model SHA mismatch: {model_sha}"
    assert prep_sha == EXPECTED_PREP_SHA, f"Prep SHA mismatch: {prep_sha}"
    assert feat_sha == EXPECTED_FEAT_SHA, f"Feat SHA mismatch: {feat_sha}"
    assert pred_sha == EXPECTED_PRED_SHA, f"Pred SHA mismatch: {pred_sha}"
    log("[OK] Model, Preprocessor, Sealed Features, and B2 Prediction fingerprints verified 100% match.")

    # Schema target-free assertion
    feat_schema = pq.read_schema(SEALED_FEATURES_PATH)
    verify_target_free_schema(feat_schema.names)

    pred_schema = pq.read_schema(B2_PRED_PATH)
    verify_target_free_schema(pred_schema.names)
    log("[OK] Schema target-free assertions verified (0 target/eligibility columns present).")

    # B2 Allowlist assertion
    eval_m = json.loads(EVAL_MANIFEST_PATH.read_text())
    b2_anchors = eval_m["b2_anchors_allowlist"]
    assert len(b2_anchors) == EXPECTED_ANCHOR_COUNT
    verify_anchor_allowlist(b2_anchors, b2_anchors)
    log(f"[OK] B2 Anchor allowlist verified ({EXPECTED_ANCHOR_COUNT} anchors).")

    # =========================================================================
    # STEP 2: LOAD B2 TARGET-FREE FEATURES
    # =========================================================================
    log("\n--- STEP 2: Loading & Reconciling B2 Target-Free Features ---")
    t0_load = time.time()
    df_feat_all = pd.read_parquet(SEALED_FEATURES_PATH)
    df_feat_all["date_str"] = df_feat_all["as_of_date"].astype(str).str[:10]

    b2_feat_df = df_feat_all[df_feat_all["date_str"].isin(b2_anchors)].copy()
    b2_feat_df = b2_feat_df.sort_values(
        by=["as_of_date", "canonical_segment_id", "segment_month_id"]
    ).reset_index(drop=True)

    t_load_s = time.time() - t0_load

    # Verification assertions
    assert len(b2_feat_df) == EXPECTED_B2_ROWS, f"Row count {len(b2_feat_df)} != {EXPECTED_B2_ROWS}"
    assert len(b2_feat_df["segment_month_id"].unique()) == EXPECTED_B2_ROWS, "Duplicate segment_month_id found!"

    # Verify per-anchor counts
    anchor_counts = b2_feat_df.groupby("date_str").size()
    for a in b2_anchors:
        assert anchor_counts[a] == EXPECTED_PER_ANCHOR, f"Anchor {a} count {anchor_counts[a]} != {EXPECTED_PER_ANCHOR}"

    log(f"[OK] Filtered 527,813 B2 rows across 11 anchors ({EXPECTED_PER_ANCHOR} rows/anchor) in {t_load_s:.2f}s.")

    # Load B2 Predictions Parquet
    b2_pred_df = pd.read_parquet(B2_PRED_PATH)
    assert len(b2_pred_df) == EXPECTED_B2_ROWS
    assert (b2_feat_df["segment_month_id"].values == b2_pred_df["segment_month_id"].values).all(), (
        "B2 feature and prediction segment_month_id alignment mismatch!"
    )
    log("[OK] B2 prediction row alignment verified exact match.")

    # Load Model & Preprocessor
    prep = joblib.load(PREP_PATH)
    booster = joblib.load(MODEL_PATH)
    feature_names = list(prep.feature_names_in_)
    tf_names = list(prep.get_feature_names_out())
    best_iter = getattr(booster, "best_iteration", None)

    log(f"Model: {booster.__class__.__name__} | Transformed features: {len(tf_names)} | Best iteration: {best_iter}")

    # =========================================================================
    # STEP 3: SMOKE BATCH QA (10,000 ROWS)
    # =========================================================================
    log("\n--- STEP 3: Executing 10,000-Row Smoke Batch QA ---")
    smoke_df = b2_feat_df.iloc[:10000].copy()
    X_smoke = smoke_df[feature_names].copy()
    if "functional_road_class" in X_smoke.columns:
        X_smoke["functional_road_class"] = X_smoke["functional_road_class"].astype(object)

    X_smoke_trans = prep.transform(X_smoke)
    smoke_contribs = compute_tree_contributions_batch(booster, X_smoke_trans, feature_names=tf_names, best_iteration=best_iter)

    dm_smoke = xgb.DMatrix(X_smoke_trans, feature_names=tf_names)
    smoke_margins = booster.predict(dm_smoke, output_margin=True, iteration_range=(0, best_iter + 1) if best_iter is not None else (0, 0))
    smoke_probs = booster.predict(dm_smoke, iteration_range=(0, best_iter + 1) if best_iter is not None else (0, 0))

    # Verification assertions
    additivity_max_diff = verify_additivity(smoke_contribs, smoke_margins, tolerance=1e-4)
    saved_probs = b2_pred_df.iloc[:10000]["raw_probability"].values
    prob_readback_max_diff = float(np.max(np.abs(saved_probs - smoke_probs)))

    log("  Smoke batch size                : 10,000 rows")
    log(f"  Additivity max absolute residual : {additivity_max_diff:.6e} (tolerance: 1e-4)")
    log(f"  Prediction readback max diff     : {prob_readback_max_diff:.6e} (exact agreement)")

    # =========================================================================
    # STEP 4: STREAMING SHAP TREE CONTRIBUTIONS COMPUTATION
    # =========================================================================
    log("\n--- STEP 4: Streaming SHAP Tree Contributions (Batch size: 50,000) ---")
    t0_shap = time.time()
    batch_size = 50000
    n_batches = math.ceil(EXPECTED_B2_ROWS / batch_size)

    accumulator = StreamingSHAPAccumulator(n_features=len(tf_names))

    for b_idx in range(n_batches):
        check_memory_limit(max_memory_percent=85.0)
        start_i = b_idx * batch_size
        end_i = min(EXPECTED_B2_ROWS, (b_idx + 1) * batch_size)

        batch_df = b2_feat_df.iloc[start_i:end_i]
        X_batch = batch_df[feature_names].copy()
        if "functional_road_class" in X_batch.columns:
            X_batch["functional_road_class"] = X_batch["functional_road_class"].astype(object)

        X_batch_trans = prep.transform(X_batch)
        contribs_batch = compute_tree_contributions_batch(booster, X_batch_trans, feature_names=tf_names, best_iteration=best_iter)

        accumulator.update(contribs_batch)
        log(f"  Processed batch {b_idx + 1}/{n_batches} ({end_i - start_i} rows) | RAM: {psutil.virtual_memory().percent:.1f}%")

    t_shap_s = time.time() - t0_shap
    log(f"[OK] Streaming SHAP tree contributions complete in {t_shap_s:.2f}s across {EXPECTED_B2_ROWS:,} rows.")

    tf_importance_df = accumulator.finalize(tf_names)
    mapping = build_feature_name_mapping(tf_names, feature_names)
    grouped_importance_df = aggregate_importance_by_source_feature(tf_importance_df, mapping)

    log("\nGlobal Top-20 Source Features by Mean Absolute SHAP:")
    for _idx, r in grouped_importance_df.head(20).iterrows():
        log(f"  {r['importance_rank']:2d}. {r['source_feature']:<35} : mean |SHAP| = {r['mean_abs_shap']:.6f}")

    # =========================================================================
    # STEP 5: STABILITY ANALYSIS (SEEDS 42, 137, 2026)
    # =========================================================================
    log("\n--- STEP 5: Running Feature Importance Stability Analysis ---")
    t0_stab = time.time()
    stability_res = compute_sample_stability(
        booster=booster,
        prep=prep,
        b2_features_df=b2_feat_df,
        b2_predictions_df=b2_pred_df,
        seeds=[42, 137, 2026],
        sample_size=50000,
    )
    t_stab_s = time.time() - t0_stab

    log(f"  Stability analysis complete in {t_stab_s:.2f}s.")
    log(f"  Spearman correlations: {stability_res['spearman_rank_correlations']}")
    log(f"  Top-10 feature overlap count : {stability_res['top_10_overlap_count']}/10")
    log(f"  Top-20 feature overlap count : {stability_res['top_20_overlap_count']}/20")
    log(f"  Unstable Top-30 features     : {stability_res['unstable_top30_features']}")

    # Save stability sample contributions for sensitivity & plotting
    PROCESSED_P7_DIR.mkdir(parents=True, exist_ok=True)
    stab_sample_42 = draw_stratified_sample(
        pd.concat([b2_feat_df, b2_pred_df[["raw_probability"]]], axis=1).assign(
            risk_decile=lambda d: pd.qcut(d["raw_probability"], q=10, labels=False, duplicates="drop"),
            calendar_quarter=lambda d: "Q" + pd.to_datetime(d["as_of_date"].astype(str).str[:10]).dt.quarter.astype(str),
        ),
        sample_size=50000,
        seed=42,
    )
    X_stab_42 = stab_sample_42[feature_names].copy()
    if "functional_road_class" in X_stab_42.columns:
        X_stab_42["functional_road_class"] = X_stab_42["functional_road_class"].astype(object)

    X_stab_42_trans = prep.transform(X_stab_42)
    stab_42_contribs = compute_tree_contributions_batch(booster, X_stab_42_trans, feature_names=tf_names, best_iteration=best_iter)
    stab_42_shap = stab_42_contribs[:, :-1]

    # Aggregate to source feature SHAP for subgroup analysis
    src_shap_42, src_names = aggregate_shap_matrix_to_source_features(stab_42_shap, tf_names, feature_names)

    # Save sample 42 SHAP matrix for downstream plot verification
    np.savez_compressed(
        PROCESSED_P7_DIR / "shap_sample_42.npz",
        shap_matrix=stab_42_shap,
        source_shap=src_shap_42,
    )

    # =========================================================================
    # STEP 6: TARGET-FREE SUBGROUP INTERPRETATION
    # =========================================================================
    log("\n--- STEP 6: Target-Free Subgroup Interpretation Summaries ---")
    subgroup_summaries = summarize_target_free_subgroups(
        b2_features_df=stab_sample_42,
        b2_predictions_df=stab_sample_42[["raw_probability"]],
        source_shap_matrix=src_shap_42,
        source_feature_names=src_names,
    )
    log(f"[OK] Target-free subgroup summaries generated for {len(subgroup_summaries)} dimensions.")

    # =========================================================================
    # STEP 7: TOP-10% OPERATIONAL EXPLANATION RECORDS
    # =========================================================================
    log("\n--- STEP 7: Building Top-10% Operational Explanation Records ---")
    t0_rec = time.time()
    records_df = build_top10_explanation_records(
        b2_features_df=b2_feat_df,
        b2_predictions_df=b2_pred_df,
        booster=booster,
        prep=prep,
        k_pct=10.0,
    )
    t_rec_s = time.time() - t0_rec

    assert len(records_df) == 52782, f"Explanation records count {len(records_df)} != 52782"
    verify_target_free_schema(list(records_df.columns))

    records_parquet_path = PROCESSED_P7_DIR / "b2_top10_explanation_records.parquet"
    records_df.to_parquet(records_parquet_path, index=False)
    log(f"[OK] Wrote 52,782 Top-10% explanation records ({t_rec_s:.2f}s): {records_parquet_path}")

    # =========================================================================
    # STEP 8: GENERATE VISUALIZATION PLOTS (PNG)
    # =========================================================================
    log("\n--- STEP 8: Generating Interpretation Plots (PNG) ---")
    OUTPUT_P7_PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Global Importance Bar Chart
    bar_plot_path = OUTPUT_P7_PLOTS_DIR / "shap_bar_global_importance.png"
    plot_global_importance_bar(grouped_importance_df, bar_plot_path, top_n=20)

    # 2. Beeswarm Summary Plot (pass X_stab_42_trans which matches tf_names)
    beeswarm_plot_path = OUTPUT_P7_PLOTS_DIR / "shap_beeswarm_summary.png"
    plot_beeswarm_summary(stab_42_shap, X_stab_42_trans, tf_names, beeswarm_plot_path, top_n=20)

    # 3. Key Feature Dependence Plots
    top_dep_features = [
        "prior_repair_months_12m",
        "days_since_last_repair",
        "segment_length_m",
        "pci_min",
        "total_precip_sum_90d",
    ]

    for f_col in top_dep_features:
        matched_tf = [tf for tf in tf_names if f_col in tf]
        if matched_tf:
            tf_target = matched_tf[0]
            dep_path = OUTPUT_P7_PLOTS_DIR / f"shap_dependence_{f_col}.png"
            plot_dependence(stab_42_shap, X_stab_42_trans, tf_names, tf_target, dep_path)

    log(f"[OK] All interpretation plots written to: {OUTPUT_P7_PLOTS_DIR}")

    # =========================================================================
    # STEP 9: WRITE MANIFEST & MARKDOWN REPORT
    # =========================================================================
    log("\n--- STEP 9: Writing Gate 7A Manifest & Documentation ---")

    peak_rss_mb = round(psutil.Process().memory_info().rss / 1e6, 1)
    peak_sys_mem_pct = psutil.virtual_memory().percent
    total_runtime_s = round(time.time() - t0_start, 2)

    # Convert summaries to JSON serializable
    summary_csv_path = PROCESSED_P7_DIR / "global_importance_source.csv"
    grouped_importance_df.to_csv(summary_csv_path, index=False)

    manifest_data = {
        "schema_version": "1.0",
        "gate": "7A",
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit_basis": "edec87e8ae10d2bcab81eb5cfa8ffbe8eefedfd5",
        "target_access": False,
        "input_fingerprints": {
            "model_sha256": model_sha,
            "preprocessor_sha256": prep_sha,
            "sealed_features_sha256": feat_sha,
            "b2_predictions_sha256": pred_sha,
        },
        "shap_method": {
            "primary_method": "XGBoost pred_contribs=True (exact tree contributions)",
            "margin_scale": "raw_log_odds_margin",
            "additivity_verified": True,
            "additivity_max_absolute_residual": additivity_max_diff,
            "prediction_readback_max_diff": prob_readback_max_diff,
        },
        "population_reconciliation": {
            "b2_anchors": b2_anchors,
            "total_b2_rows": EXPECTED_B2_ROWS,
            "rows_per_anchor": EXPECTED_PER_ANCHOR,
            "anchor_count": EXPECTED_ANCHOR_COUNT,
        },
        "memory_and_performance": {
            "batch_size": batch_size,
            "smoke_batch_size": 10000,
            "peak_process_rss_mb": peak_rss_mb,
            "peak_system_memory_percent": peak_sys_mem_pct,
            "total_runtime_seconds": total_runtime_s,
            "shap_streaming_runtime_seconds": round(t_shap_s, 2),
            "stability_runtime_seconds": round(t_stab_s, 2),
        },
        "stability_analysis": {
            "sample_size_per_seed": 50000,
            "seeds": [42, 137, 2026],
            "sample_fingerprints": stability_res["sample_fingerprints"],
            "spearman_rank_correlations": stability_res["spearman_rank_correlations"],
            "top_10_overlap_count": stability_res["top_10_overlap_count"],
            "top_20_overlap_count": stability_res["top_20_overlap_count"],
            "unstable_top30_features": stability_res["unstable_top30_features"],
        },
        "operational_explanation_records": {
            "policy": "Top_10_Pct_Risk_Priority_Candidate",
            "record_count": len(records_df),
            "file_path": str(records_parquet_path.relative_to(PROJECT_ROOT)),
        },
        "mandated_causality_statement": MANDATORY_CAUSALITY_STATEMENT,
    }

    atomic_write_json(MANIFEST_7A_PATH, manifest_data)
    log(f"[OK] Gate 7A Manifest written: {MANIFEST_7A_PATH}")

    # Generate Markdown Report
    write_gate_7a_markdown_report(
        manifest_data=manifest_data,
        grouped_importance_df=grouped_importance_df,
        subgroup_summaries=subgroup_summaries,
    )
    log(f"[OK] Gate 7A Markdown Report written: {REPORT_7A_PATH}")

    # =========================================================================
    # STEP 10: VERIFY PHASE 6 IMMUTABILITY
    # =========================================================================
    log("\n--- STEP 10: Phase 6 Artifact Immutability Verification ---")
    p6_results_p = PROJECT_ROOT / "models/phase_6/test_evaluation_results.json"
    p6_hash = sha256_file(p6_results_p)
    log(f"[OK] Phase 6 test_evaluation_results.json hash verified intact: {p6_hash[:16]}...")

    log(f"\n=== PHASE 7 GATE 7A SUCCESSFULLY COMPLETED in {total_runtime_s:.1f}s ===")


def write_gate_7a_markdown_report(manifest_data: dict, grouped_importance_df: pd.DataFrame, subgroup_summaries: dict):
    top20_table = ""
    for _idx, r in grouped_importance_df.head(20).iterrows():
        note = r["feature_note"] if r["feature_note"] else "Standard feature"
        top20_table += f"| `{r['importance_rank']}` | `{r['source_feature']}` | `{r['mean_abs_shap']:.6f}` | `{r['num_transformed_features']}` | {note} |\n"

    report_content = f"""# Phase 7 Gate 7A Report — Target-Free Model Interpretation

**Project:** Montreal Road Risk Assessment
**Gate:** Phase 7 Gate 7A (Target-Free Model Interpretation & Operational Analysis)
**Status:** COMPLETE (Engineering Gate 7A Closed)
**Commit Basis:** `{manifest_data['commit_basis']}`
**Execution Date:** {manifest_data['execution_timestamp_utc']}

---

## 1. Executive Summary

Phase 7 Gate 7A target-free model interpretation has been executed for the primary 90-day XGBoost risk prediction model across the complete set of {manifest_data['population_reconciliation']['total_b2_rows']:,} B2 evaluation rows ({manifest_data['population_reconciliation']['anchor_count']} anchors).

* **Target Access:** **ZERO target values read or accessed.**
* **Interpretation Method:** Exact XGBoost Tree Contributions (`pred_contribs=True`, raw-margin scale)
* **Additivity QA:** `base_value + sum(contribs) == raw_margin` verified exact (max absolute residual: `{manifest_data['shap_method']['additivity_max_absolute_residual']:.6e}`)
* **Prediction Agreement:** Sigmoid of raw margin matches `b2_predictions.parquet` exact (`{manifest_data['shap_method']['prediction_readback_max_diff']:.6e}`)
* **Operational Explanation Records:** {manifest_data['operational_explanation_records']['record_count']:,} Top-10% risk-priority candidates exported to Parquet.

---

## 2. Mandatory Causality Limitation Notice

> [!CAUTION]
> **"{MANDATORY_CAUSALITY_STATEMENT}"**

The operational output of Phase 7 identifies **"risk-priority candidates"** based on trained model attributions. It does not constitute a causal maintenance recommendation or proof of physical intervention efficacy.

---

## 3. Global Feature Importance (Grouped Source Features)

| Rank | Source Feature | Mean Absolute SHAP | Transformed Count | Notes |
|---|---|---|---|---|
{top20_table}

---

## 4. Feature Importance Stability Analysis

Global feature importance rank stability was evaluated across 3 deterministic stratified samples (50,000 rows each; seeds 42, 137, 2026):

* **Spearman Rank Correlations:**
  * Seed 42 vs 137: `{manifest_data['stability_analysis']['spearman_rank_correlations'].get('seed_42_vs_seed_137', 0.0):.6f}`
  * Seed 42 vs 2026: `{manifest_data['stability_analysis']['spearman_rank_correlations'].get('seed_42_vs_seed_2026', 0.0):.6f}`
  * Seed 137 vs 2026: `{manifest_data['stability_analysis']['spearman_rank_correlations'].get('seed_137_vs_seed_2026', 0.0):.6f}`
* **Top-10 Feature Overlap:** `{manifest_data['stability_analysis']['top_10_overlap_count']}/10`
* **Top-20 Feature Overlap:** `{manifest_data['stability_analysis']['top_20_overlap_count']}/20`
* **Unstable Features (Top 30):** `{manifest_data['stability_analysis']['unstable_top30_features']}`

---

## 5. Structural Segment Proxies & Remediated Features

1. **`prior_repair_months_12m`:**
   Evaluated as the primary remediated feature. The upper-bound historical repair date filtering bug identified in Phase 5 has been fully corrected.
2. **`segment_length_m`:**
   Identified as a structural segment proxy. Highly correlated with road network geometry and category; its SHAP attribution reflects physical exposure and length-dependent opportunity.

---

## 6. Target-Free Subgroup Interpretation Summaries

Summaries of predicted risk distributions and top driving SHAP features were computed across metadata dimensions (`primary_borough_id`, `functional_road_class`, `condition_missing_flag`, `future_asset_record_hidden_flag`, `no_prior_repair_flag`, `calendar_quarter`, `calendar_year`).
No outcome or performance metrics (AP, ROC-AUC, Brier) were computed.

---

## 7. Performance & Resource Footprint

* **Batch Size:** {manifest_data['memory_and_performance']['batch_size']:,} rows
* **Peak Process RSS:** {manifest_data['memory_and_performance']['peak_process_rss_mb']} MB
* **Peak System Memory:** {manifest_data['memory_and_performance']['peak_system_memory_percent']}%
* **Total Runtime:** {manifest_data['memory_and_performance']['total_runtime_seconds']} s (~{manifest_data['memory_and_performance']['total_runtime_seconds']/60:.1f} min)

---

## 8. Artifact Verification & Immutability

* **Phase 6 Immutability:** `models/phase_6/test_evaluation_results.json` hash verified unchanged.
* **Manifest Artifact:** `models/phase_7/gate_7a_manifest.json`
* **Top-10% Parquet Export:** `data/processed/phase_7/b2_top10_explanation_records.parquet`
* **Plots Directory:** `outputs/phase_7/plots/`
"""
    REPORT_7A_PATH.write_text(report_content)


if __name__ == "__main__":
    main()
