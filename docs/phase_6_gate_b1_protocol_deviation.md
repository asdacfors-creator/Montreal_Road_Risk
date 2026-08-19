# Protocol Deviation Report: Phase 6 Gate B1 Source-Path and Target-Access Deviation

**Date:** 2026-07-21  
**Phase/Gate:** Phase 6 Gate B1  
**Status:** DEVIATION RECORDED & REMEDIATED (Gate B2 Locked)  
**Assigned AI:** Antigravity  

---

## 1. Summary of Deviation

During the audit of Phase 6 Gate B1 execution, a critical path and target-access deviation was discovered. The initial script `scratch/run_gate_b1.py` utilized incorrect, contaminated baseline directories instead of the remediated directories generated in Phase 6 Gate A:

1. **Feature Source Contamination:** The script read `data/processed/phase_5/test.parquet` instead of the remediated, target-free sealed features `data/processed/phase_5_remediated_01/sealed_features_90d.parquet`.
2. **Target Source Contamination:** The script loaded target data from the unremediated panel directory `data/processed/phase_4` instead of the remediated directory `data/processed/phase_4_remediated_01`.
3. **Unauthorized Target Decoding (Procedural Breach):** Because the script executed an unrestricted `pd.read_parquet()` call on `data/processed/phase_5/test.parquet`, the column `target_repair_180d` (which represents the 180-day outcome target) was loaded and decoded into memory for all test rows, including those belonging to embargo and B2 partitions.

This event is classified as a **B. PROCEDURAL BREACH** under project guidelines: target columns existed in the read file and were decoded for embargo/B2 rows, though they were not printed, visualized, scored, or used for model training or decisions.

---

## 2. Root Cause Analysis

During Phase 6 Gate A, model and data remediation occurred, creating new, corrected partitions:
* Features: `data/processed/phase_5_remediated_01/sealed_features_90d.parquet`
* Remediated panel directory: `data/processed/phase_4_remediated_01`

However, the path constants at the top of `scratch/run_gate_b1.py` were not updated to point to these new, remediated directories. Instead, they retained the original Phase 5 paths:

```python
SEALED_PATH = Path("data/processed/phase_5/test.parquet")
PANEL_DIR = Path("data/processed/phase_4")
```

This error caused the script to load contaminated features and targets, and inadvertently decode the un-remediated `target_repair_180d` column present in `data/processed/phase_5/test.parquet`.

---

## 3. Impact Assessment

* **Old B1 Features Contaminated:** The B1 feature inputs used for model inference were contaminated.
* **Feature Value Differences:** `28,607` rows out of `143,949` B1 rows differed in `prior_repair_months_12m` between contaminated and remediated datasets.
* **Target Decoding:** The `target_repair_180d` column was procedurally decoded for all test rows during feature loading.
* **No B2 Target Access:** No B2 `target_repair_90d` values were decoded, loaded, or evaluated.
* **No Final-Test Metrics:** No final-test (B2) metrics were produced.
* **180-Day Final-Test Seal Compromised:** The 180-day final-test seal is procedurally compromised due to the decoding of `target_repair_180d` across the full test set.
* **Gate B2 Status:** Gate B2 remains locked pending a later supervisor decision.

---

## 4. Quarantined Artifacts & Fingerprints

The invalid B1 artifacts have been moved to `models/phase_6/quarantine/gate_b1_contaminated_01/`:

* `calibration_manifest.json` (SHA-256: `f540b45f2bc17be39afa363f6ae14e663305707000eb87e3e194e54a5715a464`)
* `threshold_manifest.json` (SHA-256: `8d88b6007e43817c236b5f8a22ab594f1939b211105fa66ceab3a8145fc4363d`)
* `gate_b1_access_record.json` (SHA-256: `14b998f31082f9b0b5d4ce5d86456853ab78ded4a23bc2d36969ca1dccb18d1f`)
* `calibrator_90d.joblib` (SHA-256: `b1597c6b5f07b6d3dabe874b0cda5f42b22e87e2a03e21d930e36982f89c779b`)

---

## 5. Partition Mutation & Restoration Incident

During the initial clean rerun (commit f67860d), three remediated Phase 4 partitions (`panel_year=2024/panel_month=01`, `02`, `03`) were accidentally written back in place with `target_repair_90d` added.

**Remediation & Restoration:**

* The mutated partitions were fully restored and rebuilt as target-free feature panels.
* All 102 remediated Phase 4 partitions were verified: matching count = 102, changed count = 0, missing count = 0.
* Target labels were extracted strictly from the legacy Phase 4 directory into a separate, isolated, target-only artifact: `data/processed/phase_6/gate_b1_authorized_targets_90d.parquet`.
* The quarantined `calibrator_90d.joblib` was removed from Git tracking using `git rm --cached`.

---

## 6. Target Provenance & Clean Rerun

* **Authorized Target Artifact:** `data/processed/phase_6/gate_b1_authorized_targets_90d.parquet`
* **Target Columns:** `segment_month_id`, `canonical_segment_id`, `as_of_date`, `target_repair_90d`
* **Row Count:** `143,949` (47,983 per anchor)
* **B1 Positives:** `12,081` (Prevalence: `0.083926`)
* **Normalized Target Array SHA-256:** `de775524ecc80221760f24120869664f722544eaa04fdf7ff7361f44dfeea5dc`
* **Clean Prediction Fingerprint:** `33788c952d629ae51faf8ecc2a0528200ae05b757b4553e96805748f130e89f7` (identical to f67860d)
