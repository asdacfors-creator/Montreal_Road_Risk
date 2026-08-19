# Montreal Road Risk — Target and Panel Definition

| Field | Value |
| :--- | :--- |
| **Document purpose** | Target and Panel Specification |
| **Project** | Montreal Road Pavement Deterioration Risk Assessment |
| **Phase** | Phase 0 — Definition, Requirements and Feasibility |
| **Status** | Ready for Supervisor Re-review |
| **Last updated** | 2026-07-15 |
| **Source of truth** | Submitted Proposal Section 6 |
| **Next review** | Phase 4 Target Labeling |

---

## Executive Summary

This document defines the unit of observation, prediction windows, target variables, and eligibility criteria. It provides synthetic examples and details the automated testing and validation plans.

---

## Target Definition and Wording

* **Formal Target Wording**: The probability that a road segment will receive at least one recorded road-repair intervention during the next 90 days.
* **Deterioration Proxy Caveat**: Recorded road-repair interventions represent municipal administrative decisions and maintenance operations. They do not represent a complete or objective physical measurement of pavement deterioration.

---

## Conceptual Notation

Let $s$ represent a road segment (identified conceptually as `segment_id`) and $t$ represent the observation date corresponding to the first second of the first day of calendar month $m$ (e.g., `2024-05-01 00:00:00`).

The primary target $Y_{s,t}$ is a binary variable defined as:

$$Y_{s,t} = \begin{cases} 1 & \text{if } \sum \text{Interventions}_{s} \text{ in } (t, t + 90\text{ days}] \ge 1 \\ 0 & \text{otherwise} \end{cases}$$

---

## Segment-Month Panel Specification

* **Observation Unit**: The unique pair of `segment_id` and calendar month $m$.
* **Key Format**: A string concatenating the segment identifier and the month (e.g., `segment_id_YYYY-MM`).
* **Target Prevalence**: Unknown until the processed modelling table is built and audited in Phase 2.

---

## Eligibility Rules

A segment-month record `segment_id_YYYY-MM` is eligible for inclusion in the modeling set if:
1. The segment existed in the road network prior to the historical feature lookback period (e.g., 365 days before $t$).
2. The observation date $t$ is chronologically prior to the right-edge exclusion boundary.

---

## Boundary and Exclusion Rules

### 90-Day Boundary Rules

* **Start of Window**: $t + 1\text{ second}$ (exclusive of $t$ to prevent leakage from interventions that occurred on the day of feature extraction).
* **End of Window**: $t + 90\text{ days}$ (inclusive).

### 180-Day Sensitivity

* Evaluated strictly as a sensitivity analysis. The target window is defined as $(t, t + 180\text{ days}]$.

### Right-Edge Exclusion

* If the maximum date in the dataset is $T_{\max}$, then any observation month starting at $t$ where $t + 90\text{ days} > T_{\max}$ must be excluded from training, as the 90-day future window cannot be fully observed.

---

## Synthetic Examples

Assume $T_{\max} =$ **2025-12-31** and we are evaluating the target for the month of **May 2024** ($t =$ **2024-05-01 00:00:00**).

* **Positive 90-Day Target ($Y = 1$)**: A mechanized repair is recorded on **2024-06-15**. This falls within $(2024-05-01, 2024-07-30]$. Label is $1$.
* **Negative 90-Day Target ($Y = 0$)**: No repairs are recorded on the segment between **2024-05-01** and **2024-07-30**. Label is $0$.
* **Excluded Right-Edge Observation**: Evaluating **November 2025** ($t =$ **2025-11-01**). The 90-day window ends on **2026-01-30**, which exceeds $T_{\max}$. The record is excluded.
* **Intervention Occurring Exactly on a Boundary**:
  * An intervention on **2024-05-01 00:00:00** is $\le t$ and is incorporated into the historical features, not the target.
  * An intervention on **2024-07-30 23:59:59** is $\le t + 90\text{ days}$ and results in $Y = 1$.
* **Repeated Interventions**: Repairs occur on **2024-05-10** and **2024-06-15**. The label remains binary: $Y = 1$.

---

## Planned Automated Verification Tests

1. **Temporal Order Test**: Assert that all feature inputs occur strictly before $t$, and target labels occur strictly after $t$.
2. **Right-Edge Leakage Test**: Assert that no training examples are drawn from months where $t + 90\text{ days} > T_{\max}$.
3. **Imbalance Audit**: Automatically log the empirical prevalence of $Y = 1$ upon building the panel.

---

## Limitations and Pending Verification

* The target prevalence is **unknown** and will be determined in Phase 2.
* The physical identifier for `segment_id` will be verified during Phase 2 schema inspection of the Géobase.

---

## Phase Gate

To transition to Phase 1, target definitions must be frozen.

* [ ] Formal target wording approved.
* [ ] Eligibility and boundary rules defined.
* [ ] No implementation started.
* [ ] Supervisor approval received.
