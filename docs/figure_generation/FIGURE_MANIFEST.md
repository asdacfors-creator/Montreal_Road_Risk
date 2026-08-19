# FIGURE MANIFEST — INSE 6311 Report Visual Package
## Predictive Road Pavement Deterioration Risk Assessment and Maintenance Prioritization for Montréal

**Generated:** 2026-07-25 (UTC)  
**Pipeline Commit:** `77136d8` (Phase 11 complete)  
**Report Target:** `docs/reports/INSE_6311_Technical_Report.md`

---

## Figure 01 — End-to-End System Workflow

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_01_System_Workflow.png` |
| **Figure Number** | 1 |
| **Report Section** | Section 3 – System Architecture |
| **Data/Artifact Used** | Architecture documented in code; no dynamic data |
| **Generation Script** | `source/generate_figures.py` → `fig01()` |
| **Verification** | Visual inspection; consistent with Phase 0–11 pipeline |

**Caption:** *Figure 1. End-to-end system workflow for the Montréal Road Risk Assessment pipeline. Data sources progress through spatial harmonization to 47,983 canonical road segments, temporal integration (102 anchors), panel assembly (4.89M rows), and a leakage-safe chronological split before XGBoost training. Gate B2 evaluation, SHAP attributions, maintenance prioritization, and the GIS dashboard form the downstream inference chain. A parallel Phase 9 branch applies survival analysis (mixed first-event/recurrent-event cohort) to 250,495 inter-repair intervals.*

**Alt text:** Flowchart showing ten pipeline stages from open data sources to GIS dashboard, with a survival-analysis branch.

---

## Figure 02 — Chronological Data Split

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_02_Chronological_Split.png` |
| **Figure Number** | 2 |
| **Report Section** | Section 4.1 – Data Partitioning |
| **Data/Artifact Used** | `models/phase_6/test_split_manifest.json` |
| **Generation Script** | `source/generate_figures.py` → `fig02()` |
| **Verification** | Dates confirmed against frozen split manifest |

> [!NOTE]
> A documented gap exists between the training partition end (October 2022) and the validation partition start (January 2024). November and December 2023 are present in the raw panel but were excluded from all model partitions. This is recorded in `DATA_ISSUES.md`.

**Caption:** *Figure 2. Chronological data split showing Training (Dec 2016–Oct 2022, 3,406,793 rows), Validation (Jan–Oct 2023, 479,830 rows), Gate B1 (Jan–Mar 2024, 143,949 rows), Embargo (Apr–Jun 2024, excluded), and Gate B2 Final Test (Jul 2024–May 2025, 527,813 rows). A Nov–Dec 2023 gap between training and validation is documented but does not constitute leakage.*

**Alt text:** Horizontal timeline bar chart showing four colour-coded partitions from 2017 to 2025.

---

## Figure 03 — Gate B2 Model Performance Curves

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_03_B2_Performance_Curves.png` |
| **Figure Number** | 3 |
| **Report Section** | Section 5 – Model Evaluation |
| **Data/Artifact Used** | `data/processed/phase_6/predictions/b2_predictions.parquet` + `data/processed/phase_4/panel_year=*/panel_month=*/segment_month.parquet` (B2 anchors only) |
| **Generation Script** | `source/generate_figures.py` → `fig03()` |
| **Verification** | AP=0.505693, AUC=0.920953 verified against `models/phase_6/test_evaluation_results.json` |

> [!IMPORTANT]
> Curves are computed from actual frozen predictions and actual frozen labels. No reconstruction from point estimates.

**Caption:** *Figure 3. Gate B2 model performance across 527,813 held-out evaluation rows (5.79% positive prevalence). Left: Precision–Recall curve (AP = 0.5057; 95% CI [0.4972, 0.5143]). Centre: ROC curve (AUC = 0.9210; 95% CI [0.9194, 0.9227]). Right: Calibration reliability diagram comparing mean predicted probability to mean observed repair fraction per bin (Brier score = 0.0398; ECE = 0.0216). All metrics derived from raw XGBoost probabilities.*

**Alt text:** Three-panel figure showing precision-recall curve, ROC curve, and calibration reliability diagram.

---

## Figure 04 — Top-K Maintenance Policy Comparison

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_04_TopK_Policy_Comparison.png` |
| **Figure Number** | 4 |
| **Report Section** | Section 5.3 – Operational Policy |
| **Data/Artifact Used** | `models/phase_6/test_evaluation_results.json` (frozen metrics) |
| **Generation Script** | `source/generate_figures.py` → `fig04()` |
| **Verification** | Exact values match frozen JSON artifact |

**Caption:** *Figure 4. Top-K operational maintenance policy comparison across three selection thresholds. Precision, Recall, and Lift shown on separate panels to avoid misleading shared-axis distortion. Top 5% (26,391 selected): Precision=54.0%, Recall=46.6%, Lift=9.3×. Top 10% (52,782 selected): Precision=38.1%, Recall=65.8%, Lift=6.6×. Top 20% (105,563 selected): Precision=23.8%, Recall=82.1%, Lift=4.1×.*

**Alt text:** Three bar charts comparing precision, recall, and lift for top-5%, top-10%, and top-20% selection policies.

---

## Figure 05 — Frozen-Threshold Confusion Matrix

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_05_Confusion_Matrix.png` |
| **Figure Number** | 5 |
| **Report Section** | Section 5.2 – Threshold Policy |
| **Data/Artifact Used** | `models/phase_6/test_evaluation_results.json` (frozen threshold metrics) |
| **Generation Script** | `source/generate_figures.py` → `fig05()` |
| **Verification** | TP=10,949 FP=6,702 FN=19,623 TN=490,539 verified against frozen JSON |

**Caption:** *Figure 5. Confusion matrix at the operational deployment threshold of 0.30805489 (raw XGBoost probability). Left: absolute counts. Right: row-normalized percentages (recall-based normalization). Precision = 0.620, Recall = 0.358, F1 = 0.454, Lift = 10.71×. The relatively low recall reflects the conservative threshold chosen to minimize false positives in budget-constrained maintenance operations.*

**Alt text:** Two heatmaps side by side showing raw counts and row-normalised percentages for true positives, false positives, false negatives, and true negatives.

---

## Figure 06 — Global SHAP Feature Importance

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_06_SHAP_Importance.png` |
| **Figure Number** | 6 |
| **Report Section** | Section 6 – Model Explainability |
| **Data/Artifact Used** | `data/processed/phase_7/global_importance_source.csv` |
| **Generation Script** | `source/generate_figures.py` → `fig06()` |
| **Verification** | Rank #1 feature `mean_temp_mean_30d` (mean|φ|=0.872) consistent with `models/phase_7/gate_7a_manifest.json` |

> [!WARNING]
> SHAP values are **non-causal statistical attributions** from the trained XGBoost model. They describe associations in historical administrative repair records and do not establish physical causal mechanisms. Rank stability confirmed: Spearman ρ = 0.999946 across three independent 50,000-row samples.

**Caption:** *Figure 6. Global SHAP feature importance for the top 20 source features, computed using exact XGBoost TreeContributions across 527,813 Gate B2 evaluation rows. Mean absolute SHAP values shown in log-odds scale. Climate features (teal) dominate, led by mean temperature (30-day rolling mean, mean|φ| = 0.872), followed by repair history features (orange) and pavement condition indicators (amber). All attributions reflect statistical associations in historical administrative records; causal interpretation is not supported.*

**Alt text:** Horizontal bar chart of top 20 features ranked by mean absolute SHAP value, colour-coded by feature category.

---

## Figure 07 — Subgroup / Equity Audit

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_07_Subgroup_Equity_Audit.png` |
| **Figure Number** | 7 |
| **Report Section** | Section 5.4 – Subgroup Analysis |
| **Data/Artifact Used** | `models/phase_6/test_subgroup_results.json` |
| **Generation Script** | `source/generate_figures.py` → `fig07()` |
| **Verification** | Only EVALUATED groups (n≥500, positives≥50) are plotted; INSUFFICIENT_SAMPLE groups documented |

> [!NOTE]
> No discrimination or fairness conclusions are implied. Variation in AP across functional road classes reflects differences in segment characteristics and prevalence, not model bias.

**Caption:** *Figure 7. Subgroup algorithmic equity audit across four stratification dimensions. Top row: AP and Top-10% Lift by Functional Road Class (only evaluated strata with n≥500 and ≥50 positives shown). Bottom left: AP by pavement condition data availability. Bottom right: AP by calendar quarter (seasonality). Orange dashed lines show overall Gate B2 baselines. Results from frozen Gate B2 labels only.*

**Alt text:** Four-panel figure showing average precision and lift metrics disaggregated by road class, PCI availability, and calendar quarter.

---

## Figure 08 — GIS Dashboard Architecture

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_08_Dashboard_Architecture.png` |
| **Figure Number** | 8 |
| **Report Section** | Section 7 – Dashboard Design |
| **Data/Artifact Used** | Architecture documented in `app.py`, `pages/`, `src/montreal_road_risk/dashboard/` |
| **Generation Script** | `source/generate_figures.py` → `fig08()` |
| **Verification** | Component names verified against actual source files |

**Caption:** *Figure 8. GIS dashboard architecture illustrating the target-free deployment boundary (red dashed border). Processed predictions, SHAP explanations, and segment metadata feed a central data mart (527,813 rows, zero target columns). A security.py layer enforces hard rejection of any outcome column on load. The Streamlit application routes to five pages; Page 2 renders a Folium GIS choropleth map. Cold startup: 1.43s; warm: 1.30s; peak RSS: 680 MB.*

**Alt text:** Architecture diagram showing data flow from predictions and SHAP artifacts through data mart, security layer, Streamlit app, and five dashboard pages to municipal planner.

---

## Figure 09 — Montréal Risk-Map Dashboard Screenshot

| Field | Value |
|---|---|
| **Filename** | `screenshots/Figure_09_Dashboard_Risk_Map.png` |
| **Figure Number** | 9 |
| **Report Section** | Section 7.2 – Dashboard Demonstration |
| **Data/Artifact Used** | Live dashboard at `http://localhost:8501` — Page 2 Interactive Risk Map |
| **Generation Script** | Browser capture via `browser_subagent` |
| **Anchor Month** | Most recently selected anchor in HIGH-band filter |
| **Verification** | Captured from real dashboard; HIGH-band filter applied (≈2,400 HIGH-priority segments) |

> [!NOTE]
> Screenshot shows the Folium Leaflet map with HIGH priority band filter applied. Map tiles are OpenStreetMap. No private information, tokens, or dev overlays visible.

**Caption:** *Figure 9. Live dashboard screenshot of the Interactive Risk Map (Page 2), showing Montréal road network segments filtered to the HIGH priority band (probability ≥ 0.177). Segment coloring reflects predicted probability of a mechanized repair intervention in the next 90 days. Filters (borough, road class, risk band, anchor month) are accessible in the left sidebar. Screenshot captured from the real deployed dashboard using actual Gate B2 predictions.*

**Alt text:** Screenshot of Streamlit dashboard showing a Folium choropleth map of Montréal roads coloured by risk priority, with sidebar filters visible.

---

## Figure 10 — Segment Explanation Dashboard Screenshot

| Field | Value |
|---|---|
| **Filename** | `screenshots/Figure_10_Segment_Details.png` |
| **Figure Number** | 10 |
| **Report Section** | Section 7.3 – Segment-Level Explainability |
| **Data/Artifact Used** | Live dashboard at `http://localhost:8501` — Page 3 Segment Details |
| **Generation Script** | Browser capture via `browser_subagent` |
| **Segment Shown** | Canonical segment ID `4019039` |
| **Verification** | Captured from real dashboard; segment details and predicted probability visible |

> [!NOTE]
> Non-causal decision-support disclaimer visible within the dashboard UI. No private paths or tokens visible.

**Caption:** *Figure 10. Live dashboard screenshot of the Segment Details page (Page 3) for a selected high-priority road segment. The panel displays the canonical segment ID, predicted probability of a recorded repair intervention, assigned priority band, relevant segment metadata, and local SHAP feature contributions. A non-causal decision-support disclaimer is displayed to inform operators that predictions are statistical and non-prescriptive.*

**Alt text:** Screenshot of Streamlit dashboard segment detail page showing predicted probability, priority band, and SHAP contributions for a single road segment.

---

## Figure 11 — Kaplan–Meier Survival Analysis

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_11_KaplanMeier_Survival.png` |
| **Figure Number** | 11 |
| **Report Section** | Section 8 – Survival Analysis |
| **Data/Artifact Used** | `data/processed/phase_9/survival_cohort.parquet` |
| **Generation Script** | `source/generate_figures.py` → `fig11()` |
| **Verification** | Cohort: 250,495 rows · 202,595 observed · 47,900 censored (matches frozen Phase 9 audit) |

**Caption:** *Figure 11. Kaplan–Meier survival curves for the mixed first-event/recurrent-event survival cohort. Left: Overall survival curve with 95% Greenwood confidence band (n=250,495 intervals; 202,595 observed events; 47,900 right-censored). Right: Stratified KM curves by functional road class for classes with ≥300 observed events. Right-censoring reflects segments reaching the study end date without a subsequent repair; censoring is treated as non-informative.*

**Alt text:** Two-panel survival curve figure showing overall KM estimate with confidence band and stratified curves by road class.

---

## Figure 12 — Weibull AFT Predicted Survival Curves

| Field | Value |
|---|---|
| **Filename** | `figures/Figure_12_Weibull_AFT.png` |
| **Figure Number** | 12 |
| **Report Section** | Section 8.3 – Parametric Survival Regression |
| **Data/Artifact Used** | `data/processed/phase_9/survival_cohort.parquet` (50,000-row stratified sample) |
| **Generation Script** | `source/generate_figures.py` → `fig12()` |
| **Verification** | Fitted on representative sample; covariates: segment length, functional road class |

> [!WARNING]
> Weibull AFT curves are **predictive estimates, not causal effects**. Covariates are observational; no intervention interpretation is supported.

**Caption:** *Figure 12. Weibull AFT survival regression predictions for four representative segment profiles defined by segment length and functional road class. Left: Predicted survival curves S(t|x) up to 2,000 days. Right: Predicted median time-to-next-repair by functional road class (median segment length used for each class). Model fitted on a 50,000-row stratified sample with covariates standardized to zero mean unit variance. Estimates are non-causal.*

**Alt text:** Two-panel figure showing predicted Weibull survival curves for four segment profiles and a bar chart of predicted median survival days by road class.

---

## Generation Summary

| Figure | Status | Verification |
|---|---|---|
| Fig 1 — System Workflow | GENERATED | Visual inspection |
| Fig 2 — Chronological Split | GENERATED | Dates verified against split manifest |
| Fig 3 — B2 Performance Curves | GENERATED | AP/AUC verified vs frozen JSON |
| Fig 4 — Top-K Policy | GENERATED | Values verified vs frozen JSON |
| Fig 5 — Confusion Matrix | GENERATED | Counts verified vs frozen JSON |
| Fig 6 — SHAP Importance | GENERATED | Rank #1 feature verified |
| Fig 7 — Subgroup Audit | GENERATED | Only evaluated groups shown |
| Fig 8 — Dashboard Architecture | GENERATED | Components verified vs source |
| Fig 9 — Risk Map Screenshot | GENERATED (browser capture) | Real dashboard, real data |
| Fig 10 — Segment Detail Screenshot | GENERATED (browser capture) | Real dashboard, real data |
| Fig 11 — Kaplan-Meier | GENERATED | Cohort statistics verified |
| Fig 12 — Weibull AFT | GENERATED | Sample-based fit, non-causal |
