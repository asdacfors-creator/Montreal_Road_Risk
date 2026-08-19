# Predictive Road Pavement Deterioration Risk Assessment and Maintenance Prioritization for Montréal

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3119/)
[![Tests](https://img.shields.io/badge/tests-445%20passing-brightgreen.svg)]()

Academic reproducibility repository for **INSE 6311 — Sustainable Infrastructure Planning and Management Systems** at **Concordia University**.

---

## 1. Project Overview & Purpose

This project provides an end-to-end predictive quality and risk assessment framework for municipal road pavement management in Montréal, Québec. By integrating multi-year municipal open datasets (historical pothole repair records, pavement auscultation surveys, road asset construction data) with daily weather telemetry from Environment and Climate Change Canada (ECCC), the system forecasts the 90-day probability of at least one recorded mechanized repair intervention for each road-segment month across the entire road network.

The model predicts recorded municipal repair interventions as an administrative outcome proxy. It does not directly diagnose physical pavement failure or structural condition.

---

## 2. Key Verified Results

| Metric / Scope Parameter | Verified Value | Benchmark / Interpretation |
|---|---|---|
| **Canonical Road Segments** | `47,983` | Geobase network harmonized to EPSG:32188 |
| **Segment-Month Observations** | `4,894,266` | 102 monthly panel anchors (Dec 2016 – May 2025) |
| **Monthly Panel Anchors** | `102` | Continuous multi-year panel coverage |
| **Gate B2 Test Observations** | `527,813` | 11 prospective anchors (Jul 2024 – May 2025) |
| **Average Precision (AP)** | `0.505693` | 95% CI: [0.497185, 0.514342] (8.7x over 5.79% baseline) |
| **ROC-AUC** | `0.920953` | 95% CI: [0.918968, 0.922906] |
| **Brier Score** | `0.039827` | Probability calibration error (lower is better) |
| **Log Loss** | `0.144321` | Information-theoretic cross-entropy loss |
| **Expected Calibration Error (ECE)** | `0.021618` | Post-isotonic calibration error (Gate B1 calibration) |

---

## 3. Methodological Boundary & Governance

### Non-Causal Predictive Interpretation
The target label represents recorded municipal repair interventions (`target_repair_90d`). Predictions, feature attributions (TreeSHAP), and survival intervals reflect observational associations rather than structural civil engineering degradation or causal mechanisms.

### Chronological Partition Schedule
To prevent temporal data leakage and respect realistic operational deployment constraints, the 102-anchor panel is divided into 7 governed chronological partitions:

- **Training:** Dec 2016 – Oct 2022 (71 anchors, 3,406,793 rows)
- **Development Gap:** Nov – Dec 2022 (2 anchors, 95,966 rows; unassigned to governed fitting or evaluation)
- **Validation:** Jan – Oct 2023 (10 anchors, 479,830 rows; hyperparameter tuning & early stopping)
- **Excluded Transition:** Nov – Dec 2023 (2 anchors, 95,966 rows; excluded because 90-day outcome windows extend into Gate B1)
- **Gate B1 Calibration:** Jan – Mar 2024 (3 anchors, 143,949 rows; isotonic probability calibration & threshold freezing)
- **Embargo:** Apr – Jun 2024 (3 anchors, 143,949 rows; outcome collection buffer)
- **Gate B2 Final Test:** Jul 2024 – May 2025 (11 anchors, 527,813 rows; prospective out-of-time evaluation)

---

## 4. Pipeline Architecture

```text
+-----------------------------------------------------------------------------------+
| 1. DATA INGESTION & AUDITING                                                      |
|    Municipal Open Data (Potholes, Assets, Auscultation) + ECCC Weather Telemetry  |
+-----------------------------------------------------------------------------------+
                                         |
+-----------------------------------------------------------------------------------+
| 2. SPATIAL & TEMPORAL PREPROCESSING                                               |
|    EPSG:32188 Harmonization, Spatial Buffers (20m/50m), Temporal Rolling Lags     |
+-----------------------------------------------------------------------------------+
                                         |
+-----------------------------------------------------------------------------------+
| 3. PANEL ASSEMBLY & FEATURE ENGINEERING                                           |
|    102 Anchors x 47,983 Segments = 4,894,266 Rows (Lagged Features & Targets)     |
+-----------------------------------------------------------------------------------+
                                         |
+-----------------------------------------------------------------------------------+
| 4. MODEL TRAINING & CALIBRATION                                                   |
|    XGBoost Classifier + Isotonic Probability Calibrator (Gate B1 Frozen)          |
+-----------------------------------------------------------------------------------+
                                         |
+-----------------------------------------------------------------------------------+
| 5. PROSPECTIVE EVALUATION (Gate B2) & INTERPRETABILITY                            |
|    AP: 0.505693 | ROC-AUC: 0.920953 | TreeSHAP Explanations | Survival Cohort     |
+-----------------------------------------------------------------------------------+
                                         |
+-----------------------------------------------------------------------------------+
| 6. INTERACTIVE STREAMLIT / FOLIUM GIS DASHBOARD                                   |
|    Multi-Page Exploration, Risk Choropleths, Capacity Filters, Local SHAP Force   |
+-----------------------------------------------------------------------------------+
```

---

## 5. Repository Structure

```text
├── config/                  # Configuration JSON schemas (spatial, temporal, modeling, evaluation)
├── data/
│   └── processed/           # Selected lightweight evaluation artifacts, SHAP arrays, & marts
│       ├── phase_6/         # Gate B2 predictions (527,813 rows)
│       ├── phase_7/         # TreeSHAP sample matrix & top-10% local explanation records
│       ├── phase_8/         # Dashboard data mart (parquet) & simplified GeoJSON
│       └── phase_9/         # Mixed first-event/recurrent-event survival cohort (250,495 intervals)
├── docs/                    # Architecture reports, data audit specifications, decision logs
│   ├── data_audits/         # 18 municipal source data audit reports
│   ├── evidence/phase_8/    # UI/UX audit screenshots and benchmarks
│   └── figure_generation/   # Standalone figure reproduction scripts & manifest
├── manifests/               # Cryptographic SHA-256 artifact manifest & data lineage register
├── models/                  # Serialized XGBoost model, preprocessor, and evaluation JSONs
├── pages/                   # Streamlit multi-page dashboard modules (Overview, Map, Details, etc.)
├── scripts/                 # 36 reproducible pipeline, modeling, calibration, and audit scripts
├── src/
│   └── montreal_road_risk/  # Core Python package (36 modules across 9 subpackages)
├── tests/                   # 34 pytest automated test suites
├── app.py                   # Streamlit dashboard entry point
├── pyproject.toml           # PEP 517/621 project configuration
├── requirements-locked.txt  # Pinned runtime dependencies (Python 3.11.9)
├── requirements-dev-locked.txt # Pinned development & test dependencies
└── verify_artifacts.py      # Standalone SHA-256 artifact integrity verifier
```

---

## 6. Installation & Environment Setup

### Prerequisites
- Python 3.11.9
- Git

### Setup Instructions
```bash
# Clone the repository
git clone https://github.com/asdacfors-creator/Montreal_Road_Risk.git
cd Montreal_Road_Risk

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# or: .venv\Scripts\activate     # Windows

# Install locked runtime & development dependencies
pip install -r requirements-dev-locked.txt
pip install -e .
```

---

## 7. Artifact Integrity Verification

Verify the cryptographic SHA-256 checksums of all bundled runtime models, predictions, explanations, and data marts:

```bash
python verify_artifacts.py
```

Expected output: `17 files checked — 17 passed, 0 failed`.

---

## 8. Test Suite & Validation Status

### Test Status
- **Full Hydrated Development Environment:** `445/445 automated tests passed.`
- **Lightweight Academic GitHub Repository:** `425 tests execute successfully immediately, 5 are skipped by design, and 15 integration tests require hydration/regeneration of omitted raw and intermediate datasets.`

### Running Tests
```bash
python -m pytest tests -v
```

> **Note on Test Execution:** To comply with GitHub storage constraints, large multi-gigabyte raw datasets (`data/raw/`) and uncompressed intermediate feature panels (`data/processed/phase_4/`, `data/processed/phase_5/`) are omitted from version control. In this lightweight repository, 425 core unit, modeling, evaluation, and dashboard tests pass immediately out of the box.

---

## 9. Launching the Interactive GIS Dashboard

The dashboard provides network risk mapping, segment inspection, model diagnostic curves, and local TreeSHAP explanations:

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.

### Operational Priority Bands
- **HIGH:** Top 5.0% risk within each monthly anchor ($\ge 95\text{th}$ percentile)
- **MEDIUM:** Next 5.0% risk ($90\text{th} \le \text{percentile} < 95\text{th}$)
- **WATCH:** Next 10.0% risk ($80\text{th} \le \text{percentile} < 90\text{th}$)
- **OTHER:** Lower 80.0%

---

## 10. Data Ingestion & Full Panel Regeneration

To reproduce the pipeline from raw public data:
1. **Raw Datasets (`data/raw/`):** Follow download instructions in [`docs/manual_data_download_guide.md`](docs/manual_data_download_guide.md). Download weather telemetry using `python scripts/download_eccc_weather.py`.
2. **Intermediate Panels (`data/processed/phase_4/`):** Build the complete 4.89M panel via `python scripts/build_segment_month_panel.py`.
3. **Model Training:** Retrain the model via `python scripts/phase_5_full_train_xgb_safe.py`.
4. **Prospective Evaluation:** Reproduce Gate B2 metrics via `python scripts/execute_phase_6_gate_b2.py`.

---

## 11. Academic Context

- **Course:** INSE 6311 — Sustainable Infrastructure Planning and Management Systems
