# Montreal Road Risk — Requirements Alignment

| Field | Value |
| :--- | :--- |
| **Document purpose** | Traceability and Alignment Matrix |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 0 — Definition, Requirements and Feasibility |
| **Status** | Ready for Supervisor Re-review |
| **Last updated** | 2026-07-15 |
| **Source of truth** | Submitted Proposal and Course Guide |
| **Next review** | Phase 0 Gate Approval |

---

## Executive Summary

This document extracts and traces project requirements from the submitted proposal and the course guide to ensure academic and operational alignment. It establishes a defensible interpretation of the project scope and outlines verification milestones.

---

## Input-Document Summary

* **Submitted Proposal**: Authors: Student Group; Date: July 10, 2026; commits the project to predictive modeling, criticality calculations, SHAP explainability, and a dashboard using public data.
* **Course Guide**: Instructor: Prof. Amin Hammad; outlines academic requirements: groups of 3–4, a well-referenced literature review chapter, and the deadline of August 7, 2026.
* **Workflow Diagram**: Conceptual image reviewed for structural corrections.

---

## Proposal and Course Alignment Matrix

| Source Commitment / Course Requirement | Operational Project Response | Required Evidence | Relevant Future Phase | Conflict, Uncertainty, or Missing Information |
| :--- | :--- | :--- | :--- | :--- |
| **Prediction Horizon**: 1–6 months (Proposal Sec 3) | Target is framed as at least one repair intervention in the next 90 days. 180 days is evaluated as sensitivity. | Model metrics computed for 90-day (primary) and 180-day (sensitivity) horizons. | Phase 4 & Phase 6 | None. Primary and sensitivity windows are conceptually defined. |
| **Pavement Condition Data**: PCI/IRI (Proposal Sec 5) | Verify availability of official PCI/IRI values on Montreal open data. | Dataset inventory log showing campaign metadata. | Phase 2 & Phase 3 | Uncertain: PCI/IRI availability and coverage are unknown until Phase 2 download and inspection. |
| **Pavement Age / Inventory**: Installation Year (Proposal Sec 6) | Extract construction and resurfacing years from the asset database. | Presence of asset installation dates in the processed panel. | Phase 3 & Phase 5 | Uncertain: Completeness of historical age fields for local roads is unknown until Phase 2 audit. |
| **Model Selection**: Baselines, tree ensembles, RSF (Proposal Sec 6) | Implement Baseline, Logistic Regression, Random Forest, and XGBoost. RSF is deferred. | Script outputs and model artifacts for each classifier. | Phase 5 & Phase 7 | RSF is locked as a stretch goal until the main classification MVP is approved. |
| **Time-based Testing**: Validation with future years (Proposal Sec 7) | Split data chronologically (e.g. Train: 2018–2023, Validate: 2024, Test: 2025). | Code splitting parameters and separate partition metrics. | Phase 6 | Final split dates are pending real-data inspection. |
| **Explainability**: SHAP explanations (Proposal Sec 4) | Compute SHAP values for tree-based models (RF, XGBoost) and plot in dashboard. | SHAP visualization plots in dashboard. | Phase 7 & Phase 8 | Computational complexity; mitigated by optimization or background sampling. |
| **Evaluation Metrics**: ROC-AUC, PR-AUC, Capture Rate (Proposal Sec 7) | Compute PR-AUC, ROC-AUC, Brier score, Brier calibration, Precision/Capture/Lift at K, False-Alarm Rate. | Evaluation pipeline prints and summary tables. | Phase 6 | Target prevalence is currently unknown; PR-AUC is critical if severe imbalance is present. |
| **Literature Review**: Referenced review chapter (Course Guide Sec 3) | Write a structured literature review chapter on pavement deterioration and ML. | Chapter 2 in final report with peer-reviewed citations. | Phase 10 | Balancing civil engineering physical pavement models with data-driven ML methods. |
| **Deadline**: August 7, 2026 (Course Guide Sec 4) | Implement phased development in Task Tracker. | Deliverables submitted on or before August 7, 2026. | All Phases | Extremely compressed schedule. Requires strict adherence to the MVP scope. |

---

## Research-Question Traceability

* **RQ1: Which (spatially) and when (temporally) are road segments most likely to need repairs within 1–6 months?**
  * *Operationalization*: Modeled via binary classification forecasting a 90-day intervention target. Solved in Phase 5 and Phase 6.
* **RQ2: Which roads should be targeted first to maximize return on maintenance investment under budget?**
  * *Operationalization*: Solved by combining prediction probabilities with criticality metrics to output a ranked prioritization list. Solved in Phase 7.
* **RQ3: Can a model identify and explain key risk drivers (e.g., freeze-thaw count, road age, traffic class)?**
  * *Operationalization*: Solved by computing SHAP values for tree-based models and visualizing feature importance. Solved in Phase 7.

---

## Deliverable Traceability

* **Cleaned Dataset & Pipeline**: Verified in Phase 2 and Phase 3; delivered in Phase 12 reproducibility package.
* **Risk Scores & Ranked List**: Computed in Phase 7; output as CSV/JSON in Phase 12.
* **Interactive Dashboard**: Programmed in Streamlit and Folium in Phase 8.
* **Final Academic Report**: Authored in Phase 10; includes literature review, methodology, and limitations.
* **Presentation Slides**: Created in Phase 11.

---

## Scope Conflicts

* **Pavement Age Availability**: The proposal assumes installation year and pavement surface type are readily available. If they are not present at the segment level, Random Survival Forest cannot be run at the segment level.
* **Intervention Granularity**: The proposal notes that if repair events are not available at the segment level, grid-based units will be used. This project commits to a segment-level panel, pending verification of event geometries in Phase 2.

---

## Final Defensible Interpretation

Recorded road-repair interventions represent municipal administrative decisions and maintenance operations. They do not represent complete physical pavement deterioration. The project predicts the probability of an intervention occurring on a segment in the next 90 days. All metrics, thresholds, and matching parameters are treated as candidates subject to optimization and audit in Phase 2.

---

## Limitations and Pending Verification

* Target prevalence is **unknown** until the processed modeling table is built and audited.
* The physical road segment identifier is conceptually named `segment_id` and must be verified against the real network schema during Phase 2.
* The spatial matching tolerances (e.g. 10m, 25m, 50m) and line-in-polygon overlay thresholds are candidate values; final selections are pending spatial audit results.
* The traffic volume and asset data coverage are currently unknown and must be measured in Phase 2.

---

## Phase Gate

To transition to Phase 1, this document must be approved by the supervisor.

* [ ] Traceability of proposal and course guide requirements verified.
* [ ] No implementation started.
* [ ] Relative links verified.
* [ ] Supervisor approval received.
