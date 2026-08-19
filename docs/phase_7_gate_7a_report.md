# Phase 7 Gate 7A Report — Target-Free Model Interpretation

**Project:** Montreal Road Risk Assessment
**Gate:** Phase 7 Gate 7A (Target-Free Model Interpretation & Operational Analysis)
**Status:** COMPLETE (Engineering Gate 7A Closed)
**Commit Basis:** `edec87e8ae10d2bcab81eb5cfa8ffbe8eefedfd5`
**Execution Date:** 2026-07-21T11:13:14.435604+00:00

---

## 1. Executive Summary

Phase 7 Gate 7A target-free model interpretation has been executed for the primary 90-day XGBoost risk prediction model across the complete set of 527,813 B2 evaluation rows (11 anchors).

* **Target Access:** **ZERO target values read or accessed.**
* **Interpretation Method:** Exact XGBoost Tree Contributions (`pred_contribs=True`, raw-margin scale)
* **Additivity QA:** `base_value + sum(contribs) == raw_margin` verified exact (max absolute residual: `3.814697e-06`)
* **Prediction Agreement:** Sigmoid of raw margin matches `b2_predictions.parquet` exact (`0.000000e+00`)
* **Operational Explanation Records:** 52,782 Top-10% risk-priority candidates exported to Parquet.

---

## 2. Mandatory Causality Limitation Notice

> [!CAUTION]
> **"SHAP values describe model behavior and association. They do not establish causal effects or prove that changing a feature will change repair risk."**

The operational output of Phase 7 identifies **"risk-priority candidates"** based on trained model attributions. It does not constitute a causal maintenance recommendation or proof of physical intervention efficacy.

---

## 3. Global Feature Importance (Grouped Source Features)

| Rank | Source Feature | Mean Absolute SHAP | Transformed Count | Notes |
|---|---|---|---|---|
| `1` | `mean_temp_mean_30d` | `0.872462` | `1` | Standard feature |
| `2` | `repair_active_days_365d` | `0.356345` | `1` | Standard feature |
| `3` | `repair_event_count_collapsed_365d` | `0.344590` | `1` | Standard feature |
| `4` | `days_since_last_repair` | `0.263997` | `1` | Temporal maintenance recency indicator. High values indicate extended period without recorded repair events. |
| `5` | `total_precip_sum_90d` | `0.252832` | `1` | Standard feature |
| `6` | `min_temp_min_365d` | `0.246584` | `1` | Standard feature |
| `7` | `max_temp_max_30d` | `0.241482` | `1` | Standard feature |
| `8` | `official_administrative_name` | `0.230675` | `35` | Standard feature |
| `9` | `functional_road_class` | `0.228638` | `10` | Standard feature |
| `10` | `administrative_category` | `0.219481` | `3` | Standard feature |
| `11` | `days_since_condition_survey` | `0.164241` | `1` | Standard feature |
| `12` | `mean_temp_mean_180d` | `0.123861` | `1` | Standard feature |
| `13` | `max_temp_max_180d` | `0.115198` | `1` | Standard feature |
| `14` | `segment_length_m` | `0.107852` | `1` | Structural segment proxy. Highly correlated with road category and network geometry; its SHAP contribution reflects physical exposure and length-dependent opportunity. |
| `15` | `min_temp_min_30d` | `0.092426` | `1` | Standard feature |
| `16` | `latest_pci` | `0.085291` | `1` | Standard feature |
| `17` | `mean_temp_mean_90d` | `0.075886` | `1` | Standard feature |
| `18` | `condition_campaign_scope` | `0.069354` | `4` | Standard feature |
| `19` | `freeze_thaw_strict_sum_180d` | `0.063941` | `1` | Standard feature |
| `20` | `min_temp_min_180d` | `0.061186` | `1` | Standard feature |

---

## 4. Feature Importance Stability Analysis

Global feature importance rank stability was evaluated across 3 deterministic stratified samples (50,000 rows each; seeds 42, 137, 2026):

* **Spearman Rank Correlations:**
  * Seed 42 vs 137: `0.999946`
  * Seed 42 vs 2026: `0.999991`
  * Seed 137 vs 2026: `0.999964`
* **Top-10 Feature Overlap:** `10/10`
* **Top-20 Feature Overlap:** `20/20`
* **Unstable Features (Top 30):** `[]`

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

* **Batch Size:** 50,000 rows
* **Peak Process RSS:** 2329.7 MB
* **Peak System Memory:** 45.4%
* **Total Runtime:** 1776.23 s (~29.6 min)

---

## 8. Artifact Verification & Immutability

* **Phase 6 Immutability:** `models/phase_6/test_evaluation_results.json` hash verified unchanged.
* **Manifest Artifact:** `models/phase_7/gate_7a_manifest.json`
* **Top-10% Parquet Export:** `data/processed/phase_7/b2_top10_explanation_records.parquet`
* **Plots Directory:** `outputs/phase_7/plots/`
