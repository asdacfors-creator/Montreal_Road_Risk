# Phase 5 Validation Report — Baselines and Classification Models

| Field | Value |
| :--- | :--- |
| **Document purpose** | Phase 5 Validation Report |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 5 — Baselines and Classification Models |
| **Status** | Complete |
| **Last updated** | 2026-07-19 |
| **Primary horizon** | 90 days |
| **Sealed test** | Not evaluated (Phase 6 task) |

---

## 1. Data Splits

| Partition | Rows | Notes |
|-----------|------|-------|
| Train (90d) | 3,406,793 | Purged, embargo-safe, used for model training |
| Validation (90d) | 479,830 | Chronological hold-out, used for early stopping and metric reporting |
| Test (90d) | **SEALED** | A non-analytic target-column integrity comparison occurred during remediation. Target values were not printed, summarized, scored, passed to a model or used for any modeling decision. under any Phase 5 authorization |

All metrics in this report are **validation-set only**. Generalization to the test set is
unknown and will be measured in Phase 6 under separate supervisor authorization.

---

## 2. Feature Schema

| Item | Value |
|------|-------|
| Feature count | 110 |
| Feature order file | `models/phase_5/feature_names_90d.json` |
| Preprocessor type | Frozen sklearn Pipeline (ColumnTransformer → OHE + imputation) |
| Preprocessor fitted on | 1M deterministic stratified training subset (seed=42) |
| Frozen preprocessor path | `models/phase_5/full_training_external_memory_candidate/preprocessor.joblib` |
| Preprocessing: days_since_last_repair | Null → sentinel -1 |
| Preprocessing: categoricals | Null → "missing"; cast to object dtype |

---

## 3. Baseline Model Results

| Model | AP | ROC-AUC | Brier |
|-------|-----|---------|-------|
| Historical-frequency baseline | ~0.15 | ~0.65 | — |

> Exact baseline figures from `models/phase_5/baseline_validation_results.json`.

---

## 4. Classifier Grid Results (90-day horizon)

| Model | AP | ROC-AUC | Brier | Notes |
|-------|-----|---------|-------|-------|
| Logistic Regression | — | — | — | From classifier_validation_results.json |
| XGBoost (1M, best_iter=90) | 0.795903 | 0.984231 | 0.029220 | 1M subsample |
| **XGBoost (3.4M, best_iter=184)** | **0.806207** | **0.986180** | **0.029702** | **Selected — full-data** |

> Detailed grid results in `models/phase_5/classifier_validation_results.json`.

---

## 5. Selected Model — Full Details

### Identity
- **Name:** `XGB_fulldata_3406793_ne500_md4_lr0.1_90d`
- **Status:** Full-training Phase 5 validation candidate
- **Artifact:** `models/phase_5/full_training_external_memory_candidate/`

### Hyperparameters
| Parameter | Value |
|-----------|-------|
| objective | binary:logistic |
| tree_method | hist |
| eval_metric | aucpr |
| max_depth | 4 |
| learning_rate | 0.1 |
| subsample | 0.8 |
| colsample_bytree | 0.8 |
| early_stopping_rounds | 20 |
| seed | 42 |
| nthread | 1 |

### Training
| Item | Value |
|------|-------|
| Training rows | 3,406,793 |
| Training method | `xgb.ExtMemQuantileDMatrix` (true out-of-core streaming) |
| Batch size | 50,000 rows |
| DMatrix build time | 140.3s |
| Training time | 596.0s |
| Total elapsed | 744.6s |
| Rounds trained | 204 |
| best_iteration | **184** |
| best_score (val-aucpr) | **0.806205** |

### Memory
| Item | Value |
|------|-------|
| Peak process RSS | **2.16 GB** |
| Peak system % | **68.4%** |
| Watchdog abort | NOT fired |
| D: free (min) | 40.1 GB |
| Cache (D drive) | 1,485 MB peak, 0 MB after training |

### Validation Metrics
| Metric | Value |
|--------|-------|
| **Average Precision (AP)** | **0.806207** |
| **ROC-AUC** | **0.986180** |
| **Brier score** | 0.029702 |
| n_total (val) | 479,830 |
| n_positive (val) | 26,358 |
| Prevalence | 5.49% |
| Lift @ top 5% | 13.486× |
| Lift @ top 10% | 9.416× |
| Lift @ top 20% | 5.000× |

### Artifact Fingerprints
| File | SHA-256 |
|------|---------|
| preprocessor.joblib | `6bfe7209f95b86e962e50249ea2492bc7630f9a37d1700f350e4d748a64492ff` |
| model.joblib | `f9fab0ec1d8e257f8f201085aa62123056a424552a05e4aa3da9c0affff70c07` |
| Prediction fingerprint | `05e0665789e2d9741114aad35461ee33cf3add6887114157e91f1df4dd2b55cc` |

---

## 6. Comparison — Full-data vs 1M Candidate

| Metric | Full-data | 1M Fallback | Delta |
|--------|-----------|-------------|-------|
| AP | **0.806207** | 0.795903 | **+0.010304** |
| ROC-AUC | **0.986180** | 0.984231 | **+0.001949** |
| Brier | 0.029702 | **0.029220** | +0.000481 |
| best_iter | **184** | 90 | +94 |

---

## 7. Artifact Read-Back Verification (Part 2)

| Check | Result |
|-------|--------|
| Artifacts present | ✅ |
| File fingerprints match stored | ✅ |
| Val rows loaded | 479,830 ✅ |
| Prediction fingerprint match | ✅ |
| AP recalculated | 0.806207 ✅ |
| ROC-AUC recalculated | 0.986180 ✅ |
| Brier recalculated | 0.029702 ✅ |
| Feature order matches feature_names_90d.json | ✅ |
| Overall | **PASS** |

> This is artifact read-back determinism only. No retraining was performed.
> An independent full-training rerun requires separate authorization.

---

## 8. Limitations

| ID | Summary |
|----|---------|
| L5.1 | External-memory streaming required on 16 GB machine |
| L5.2 | No independent full-training rerun performed |
| L5.3 | Preprocessor fitted on 1M subset, not all 3.4M rows |
| L5.4 | Brier score marginally worse (+0.000481); calibration deferred to Phase 6 |
| L5.5 | 180-day results not re-evaluated under this authorization |
| L5.6 | Sealed test not evaluated; all metrics are validation-set only |

Full details in `docs/limitations_log.md`.

---

## 9. Protected Inputs and Test Seal

- **Protected inputs:** 224/224 files UNCHANGED ✅
- **1M fallback candidate:** All 4 files UNCHANGED ✅
- **Sealed test partition:** A non-analytic target-column integrity comparison occurred during remediation. Target values were not printed, summarized, scored, passed to a model or used for any modeling decision. ✅
- **Nothing staged / committed / pushed** before QA ✅

---

## 10. Phase 6 Prerequisites

| Requirement | Status |
|-------------|--------|
| Primary candidate selected | ✅ |
| Artifact verified | ✅ |
| Phase 5 documentation complete | ✅ |
| Supervisor authorization for Phase 6 | ⏳ Required |
| Sealed test evaluation plan | ⏳ Phase 6 |
| Calibration | ⏳ Phase 6 |
