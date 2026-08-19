# Montreal Road Risk — Feasibility Risk Register

| Field | Value |
| :--- | :--- |
| **Document purpose** | Project Feasibility Risk Log |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 0 — Definition, Requirements and Feasibility |
| **Status** | Ready for Supervisor Re-review |
| **Last updated** | 2026-07-15 |
| **Source of truth** | Submitted Proposal and Data Inventory |
| **Next review** | Phase 2 Data Quality Audit |

---

## Executive Summary

This risk register evaluates technical, spatial, temporal, and schedule risks that could affect the feasibility of the project. It provides specific mitigations, fallbacks, and decision gates for each risk.

---

## Feasibility Risk Register Table

| Risk ID | Risk | Evidence Status | Likelihood | Impact | Mitigation | Fallback | Decision Phase | Owner/Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R0.1** | Incomplete intervention records | Verified from proposal proxy limits | Medium | High | Define target strictly as municipal mechanized repairs | Add general road permits as auxiliary target | Phase 3 | Pending |
| **R0.2** | Inaccurate or missing coordinates | Pending real-data inspection | Low | Medium | Clean coordinate fields and drop null geometry rows | Use street name matching or borough assignment | Phase 3 | Pending |
| **R0.3** | Road-identifier changes | Pending real-data inspection | Medium | High | Build translation mapping based on spatial overlay | Aggregate to spatial grid cells (e.g. 100m grid) | Phase 4 | Pending |
| **R0.4** | Unsuccessful spatial matching | Pending real-data inspection | Medium | Medium | Test candidate snapping tolerances (10m, 25m, 50m) | Use nearest segment without class constraints | Phase 3 | Pending |
| **R0.5** | Invalid geometries | Pending real-data inspection | Low | Medium | Apply GeoPandas validation (`is_valid`) & buffer fix | Drop invalid segments and log exclusions | Phase 3 | Pending |
| **R0.6** | Incomplete pavement age | Coverage & missingness unknown | High | High | Impute using functional class and borough medians | Treat age as categorical; add "Unknown" class | Phase 5 | Pending |
| **R0.7** | Unavailable PCI or IRI data | Coverage & missingness unknown | High | Medium | Check condition campaigns; temporal forward-carry | Exclude PCI/IRI; use age and class proxies | Phase 5 | Pending |
| **R0.8** | Sparse traffic counts | Coverage & missingness unknown | High | Medium | Match adjacent segments sharing name and class | Impute with functional road class average | Phase 5 | Pending |
| **R0.9** | Weather-station coverage | Verified station counts (ECCC) | Low | Low | Evaluate aggregation candidates (nearest, airport, IDW) | Use Trudeau Airport station weather uniformly | Phase 5 | Pending |
| **R0.10** | Class imbalance | Target prevalence unknown | High | High | Evaluate via PR-AUC and Precision-at-K | Apply downsampling to training partition only | Phase 7 | Pending |
| **R0.11** | Seasonal variation | Verified weather seasonality | High | Medium | Include calendar month or season as feature | Train seasonal models for peak repair periods | Phase 5 | Pending |
| **R0.12** | Right-edge truncation | Verified target definition constraint | High | High | Exclude the final 90 days of the dataset | Shorten target window to 30 days for testing | Phase 6 | Pending |
| **R0.13** | Temporal leakage | Verified methodology constraint | Medium | High | Enforce chronological features and splits | No fallback; temporal leakage must be zero | Phase 6 | Pending |
| **R0.14** | Insufficient historical coverage | Verified ECCC and municipal archives | Low | Medium | Establish a burn-in year (e.g., 2018) for lags | Shorten lookback window (e.g., to 6 months) | Phase 4 | Pending |
| **R0.15** | Biased geographic coverage | Verified borough administration | Medium | Medium | Include borough identifier as categorical feature | Stratify split partitions by borough | Phase 6 | Pending |
| **R0.16** | Project schedule | Verified deadline (Aug 7, 2026) | High | High | Prioritize MVP classification pipeline & dashboard | Defer optional survival analysis stretch goal | Phase 0 | Approved |
| **R0.17** | Survival-analysis feasibility | Verified metadata constraints | High | High | Test RSF only if segment age is available | Aggregate survival to grid/area or drop | Phase 8 | Pending |

---

## Limitations and Pending Verification

* Coverage and missingness of traffic, pavement condition (PCI/IRI), and asset resurfacing are **currently unknown** and must be measured in Phase 2.
* Target prevalence is **unknown** until the processed modeling table is built and audited in Phase 2.
* The physical identifier for `segment_id` will be verified during Phase 2 schema inspection.

---

## Phase Gate

To transition to Phase 1, the risk register must be reviewed and approved.

* [ ] All 17 feasibility risks logged.
* [ ] Mitigations and fallbacks defined.
* [ ] No implementation started.
* [ ] Supervisor approval received.
