# Viva Defense Q&A Preparation Matrix — INSE 6311
## Montreal Road Risk Assessment & Predictive Maintenance

**Project:** Predictive Road Pavement Deterioration Risk Assessment — Montréal  
**Course:** INSE 6311 · Concordia University · Supervisor: Prof. Amin Hammad  
**Commit:** `fa2e5b1` · Phases 0–11 Complete  

---

> **Preparation Note:** Each answer below is designed to be delivered in 60–90 seconds orally.
> The key principle is: **lead with the technical mechanism, then cite the specific data or metric.**

---

## Q1: How did you mathematically prevent data leakage across the 11 test anchor months?

### Professor's Intent
Testing understanding of temporal validation discipline, chronological boundary enforcement, and information leakage prevention.

### Model Answer

Data leakage prevention was enforced at three independent levels:

**Level 1 — Chronological Feature Boundary:** Every feature join used a strict `event_date ≤ as_of_date` guard. For example, a segment's weather features for anchor `2024-07-31` could only include weather observations through July 31, 2024. Pavement condition surveys, repair history counts, and road asset ages all obeyed this same chronological wall.

**Level 2 — Training/Validation/Test Split:** The three partitions were defined by anchor date ranges with an explicit embargo period:
- **Training:** Dec 2016 – Oct 2022 (71 anchors, 3,406,793 rows)
- **Validation:** January–October 2023 (10 anchors, 479,830 rows) — used for early stopping and hyperparameter evaluation
- **Gate B1 Calibration:** January–March 2024 (3 anchors, 143,949 rows)
- **Embargo:** April–June 2024 — permanently excluded
- **B2 Final Test:** July 2024–May 2025 (527,813 rows, 11 anchors)

The embargo zone ensures that no validation-period information bleeds into the test period through gradient signals or threshold optimization.

**Level 3 — Preprocessor Discipline:** The `sklearn` preprocessing pipeline (imputation medians, one-hot encoder category lists) was fitted **exclusively** on the training partition before any transformation. Validation and test sets received only `.transform()` calls — never `.fit_transform()`.

**Verification:** We ran deterministic regeneration audits and SHA-256 fingerprint checks proving all 55 raw input files remained unchanged across all pipeline runs.

---

## Q2: Why did raw XGBoost probabilities outperform Platt scaling on Brier score and log loss?

### Professor's Intent
Testing understanding of calibration theory, proper scoring rules, and the Platt scaling trade-off.

### Model Answer

This is a nuanced but important empirical result. Platt scaling (Sigmoid Logistic Regression) improved Expected Calibration Error (ECE) from `0.022` to `0.010` — but simultaneously *degraded* Brier score from `0.040` to `0.042` and log loss from `0.144` to `0.163`.

The explanation lies in the mathematical structure of these metrics:

- **ECE** measures mean absolute error between predicted bin probabilities and observed bin frequencies. Platt scaling compresses the predicted probability range and redistributes probability mass in ways that reduce this specific bin-wise error.
- **Brier score** ($BS = \frac{1}{n}\sum (p_i - y_i)^2$) and **log loss** ($LL = -\frac{1}{n}\sum y_i \log p_i + (1-y_i)\log(1-p_i)$) are *strictly proper scoring rules* — they reward exact probability truth without approximation.

In our case, the XGBoost raw probabilities are already **reasonably well-calibrated** for a gradient-boosted model. Platt scaling on the B1 calibration data (143,949 rows, 8.39% prevalence) improved the bin-level appearance but introduced slight miscalibration for the B2 test distribution (5.79% prevalence), likely because the B1 prevalence differed from B2.

**Decision:** The proper scoring rules (Brier, log loss) are more robust indicators of true calibration than ECE, so raw probabilities were adopted as the primary output. Platt scaling is retained for sensitivity analysis.

---

## Q3: Why do SHAP attributions express statistical association and not physical causality?

### Professor's Intent
Testing ethical and epistemological rigour — a mandatory non-causal disclaimer.

### Model Answer

SHAP (Shapley Additive Explanations) values are derived entirely from the **learned XGBoost model** — not from physical pavement engineering experiments. They answer the question: *"How much did feature $j$ contribute to this model's prediction for this observation?"* — not: *"What would happen to the road if we changed feature $j$?"*

Three fundamental reasons why SHAP ≠ causality:

1. **Observational Data Only:** Our training data is historical administrative records. The model learns associations that held in the past — it cannot distinguish whether a feature *caused* increased repair activity or was merely *correlated* with it through confounders (e.g., high-traffic arterials are simultaneously high-temperature exposure AND high-repair-frequency, making both features positively correlated with the outcome through different mechanisms).

2. **Confounding:** `mean_temp_mean_30d` ranks #1 globally. But Montréal's repair activity peaks in spring — when frozen pavement cracks open AND when maintenance crews return from winter pause. The model cannot separate temperature's physical effect on pavement from the administrative scheduling seasonality of repair crews.

3. **No Counterfactual Validity:** Changing a single SHAP feature value in isolation (e.g., artificially reducing temperature) does not correspond to a real-world intervention that holds all else equal. Without randomized control trial (RCT) or a valid causal identification strategy (e.g., instrumental variables, difference-in-differences), causal claims are inadmissible.

This is why we included mandatory non-causal disclaimers on every dashboard page and in the technical report.

---

## Q4: How did you handle right-censoring (19.12% intervals; 63.7% non-recurrent segments) in the mixed first-event/recurrent-event survival cohort?

### Professor's Intent
Testing survival analysis methodological rigour and understanding of censored data.

### Model Answer

Right-censoring is a fundamental property of any survival analysis on observational administrative data — it is not a data quality failure, but a structural feature that must be handled correctly.

In our cohort, **30,559 segments (63.7%)** have zero observed recurrent repair events in the constructed cohort. At the interval level, 47,900 of 250,495 records are right-censored (19.12%).
- **Zero-repair segments (55.1%):** Never received a recorded repair during the study window (2016–2025). Their true time-to-first-repair is unknown — we only know it exceeds the study duration.
- **Single-repair segments (8.6%):** Received exactly one repair date, after which no subsequent repair was recorded. Their next inter-repair interval is right-censored at the study end date.

**How we handled this correctly:**

1. **Censoring Indicator:** Every cohort record carries `event_observed ∈ {0, 1}`. A censored record ($E=0$) with `duration_days = 3,086` means "this segment was observed for 3,086 days without a re-repair."

2. **Kaplan-Meier Estimator:** The KM estimator correctly handles censoring through the product-limit formula:
$$\hat{S}(t) = \prod_{t_i \le t}\!\left(1 - \frac{d_i}{n_i}\right)$$
   where $n_i$ includes censored observations in the at-risk set until their censoring time, after which they are removed. Censored observations contribute information about survival *up to* their censoring time.

3. **Weibull AFT Log-Likelihood:** For censored observations, the log-likelihood term is $\log S(t_i \mid \mathbf{x}_i) = -\exp(z_i)$ — contributing information that the segment survived at least to time $t_i$.

The critical assumption we made is **non-informative censoring** — segments that left observation (were censored at study end) were not censored for reasons related to their true failure risk. This is a standard assumption in administrative data survival analysis that we explicitly document as a limitation.

---

## Q5: How did the spatial panel prevent data contamination across borough boundaries?

### Professor's Intent
Testing understanding of spatial data governance and cross-contamination risks.

### Model Answer

The spatial containment protocol operated at three levels:

**Level 1 — Observation Unit Design:** The observation unit is `(canonical_segment_id, as_of_date)`. Each segment is a fixed spatial entity — a single road centreline from GéoBase. No spatial interpolation, spatial joins that cross segment boundaries, or neighbourhood aggregation features were used. Each segment's features are computed exclusively from events spatially snapped to that segment.

**Level 2 — Spatial Snapping Controls:** Repair events were matched to segments using a nearest-neighbour spatial snap with a **15-metre tolerance**. For ambiguous matches (multiple candidate segments within tolerance), we used strict disambiguation protocols: the `linkage_status` field records `accepted`, `unmatched`, or `review_required` for every event. Only `accepted` events entered the panel. A total of **6,810 ambiguous events** were documented and excluded in the exclusion audit.

**Level 3 — Borough-Level Feature Isolation:** Borough identity is represented through a **static OHE categorical join** on `canonical_segment_id`. We do NOT compute cross-borough rolling aggregates (e.g., "number of repairs within 500m regardless of borough"). This ensures that a repair event in Borough A cannot inflate the feature signal for a segment in Borough B.

**Administrative Boundary Crosswalk:** The `road_boundary_crosswalk.parquet` artifact assigns each segment to its primary borough using a spatial containment test. Segments crossing borough boundaries are assigned to their majority-area borough. This crosswalk was built once and applied deterministically across all panel years.

---

## Q6: Why did the validation AP (0.806) drop so significantly to the test AP (0.506)?

### Professor's Intent
Testing understanding of temporal distribution shift, train-test generalization, and realistic deployment expectations.

### Model Answer

The AP drop from `0.806` (validation) to `0.506` (final test) is a **real and expected phenomenon** — not a modelling error. It reflects three compounding factors:

**1. Temporal Distribution Shift:** The validation set (Jan–Oct 2023, 10 anchors) evaluates generalizability following the 2016–2022 training partition. The model learned patterns from Montréal's repair history through a period of stable municipal operations. The test set (Jul 2024 – May 2025) spans a full year of future data, during which seasonal patterns, repair budgets, and operational priorities may have shifted.

**2. Prevalence Shift:** Validation prevalence was `5.49%`. Test prevalence was `5.79%`. While similar, Average Precision is highly sensitive to the positive class distribution at the operating threshold.

**3. Anchor Distance:** Validation anchors (3 months ahead of training) are far closer in time than test anchors (9–19 months ahead). Models naturally degrade as temporal distance from training data increases.

**Context for the AP = 0.506 result:** Under a naïve historical-frequency baseline with 5.79% prevalence, AP ≈ `0.058–0.150`. Our AP of `0.506` represents **8.7× improvement over the baseline** and a **Top-10% Lift of 6.58×** — strong operational utility even under distribution shift. The ROC-AUC of `0.921` shows that the model's **rank ordering capability** remains excellent even when absolute probability magnitudes shift.

---

## Q7: How did you verify that the XGBoost null controls confirmed no data leakage?

### Professor's Intent
Testing understanding of the negative control experiment design (Phase 6 Gate A).

### Model Answer

We conducted a **formal seed isolation negative control experiment** in Phase 6 (Gate A) to verify that the model's validation performance reflects genuine feature-label association and not a data artefact.

**Protocol:** We shuffled training labels randomly using `np.random.default_rng(seed).permutation()` to destroy all genuine label-feature correlation. A model trained on shuffled labels should achieve AP ≈ prevalence and ROC-AUC ≈ 0.5 if the pipeline is leak-free.

**Results:**

| Configuration | Null AP | ROC-AUC |
|---|---|---|
| perm=42 + model=42 | 0.069 | 0.529 |
| perm=137 + model=42 | 0.091 | 0.641 |
| perm=2026 + model=42 | 0.069 | 0.548 |

**Key diagnostic:** `perm=137` produced a spurious elevated AUC of `0.641`. We investigated using a **full-sampling diagnostic** (subsample=1.0, colsample_bytree=1.0):
- With 80% subsampling: AUC = 0.641
- With 100% full sampling: AUC = **0.522** (essentially null result)

This proves the `perm=137` elevation is a **stochastic subsampling artefact** from one specific label permutation — not data leakage. The gap between our real model (AP=0.806) and the best null model (AP=0.099) is **8.1×** — only genuine feature-label association explains real model performance.

---

## Q8: What does the Concordance Index (C-index) measure and how does it differ from ROC-AUC?

### Professor's Intent
Testing understanding of survival analysis evaluation metrics and the distinction from classification metrics.

### Model Answer

The **Concordance Index (C-index)** and **ROC-AUC** both measure rank-ordering performance, but on different outcome types.

**ROC-AUC (Classification):**
$$AUC = P(\hat{p}_{i+} > \hat{p}_{j-})$$
Probability that a random positive observation receives a higher predicted probability than a random negative observation. Requires binary event indicators.

**Harrell's C-index (Survival):**
$$C = P(\hat{T}_{50,i} < \hat{T}_{50,j} \mid T_i < T_j, E_i = 1)$$
Probability that for two randomly selected segments where segment $i$ experienced the next repair sooner, the model correctly assigns segment $i$ a shorter predicted median survival time $\hat{T}_{50}$. Only eligible pairs where $T_i < T_j$ AND event $E_i = 1$ are compared — pairs where both observations are censored or where the ordering is ambiguous due to censoring are excluded.

**Key difference:** The C-index handles **right-censored observations** correctly. If segment $j$'s follow-up time is censored at 500 days and segment $i$ had a repair at 100 days, the pair (i, j) is eligible ($T_j > T_i$, $E_i = 1$). But if both are censored, the pair is ineligible — we cannot determine true ordering.

**In our survival model:** The C-index evaluates whether the Weibull AFT model's predicted median time-to-repair correctly rank-orders segments by their observed inter-repair intervals. A C-index of 1.0 would be perfect ordering; 0.5 is random.

---

## Q9: How did you select the Top-10% operational policy over the Top-5% or Top-20% alternatives?

### Professor's Intent
Testing understanding of precision-recall trade-offs and operational deployment context.

### Model Answer

The Top-10% policy (`52,782 segment-months per anchor`) was not selected by us — it is presented as one of three standardized Top-K evaluation benchmarks that operators can choose based on their budget and operational context.

The three policies represent different precision-recall trade-offs:

| Policy | Precision | Recall | Lift | Operational Meaning |
|---|---|---|---|---|
| **Top 5%** | 53.97% | 46.59% | 9.32× | High precision — fewer false alarms, lower recall |
| **Top 10%** | 38.12% | 65.81% | 6.58× | Balanced — captures 2/3 of true repair sites |
| **Top 20%** | 23.77% | 82.08% | 4.10× | High recall — catches 4/5 of repairs, lower precision |

**Decision framework for operators:**
- If budget is **very constrained** (limited inspection teams): use **Top-5%** to maximize precision
- If the goal is **high coverage** of deteriorating segments: use **Top-20%** for 82% recall
- If **balanced operational utility** is desired: **Top-10%** is the standard academic benchmark

The **frozen threshold policy** (HIGH ≥ 0.177, MEDIUM ≥ 0.089) provides an absolute probability threshold alternative to the relative Top-K ranking. Both are available to planners in the dashboard.

---

## Q10: Why did you choose Weibull AFT over Cox Proportional Hazards for the survival model?

### Professor's Intent
Testing knowledge of parametric vs. semi-parametric survival model selection.

### Model Answer

Both Cox Proportional Hazards (Cox PH) and Weibull AFT are appropriate for our survival data. We selected **Weibull AFT** for three reasons:

**1. Interpretability:** Weibull AFT directly models *log-duration* as a linear function of covariates:
$$\log T = \mathbf{x}^\top\boldsymbol{\beta} + \sigma W$$
This gives us a **directly interpretable median time-to-failure prediction** for any segment:
$$\hat{T}_{50}(\mathbf{x}) = \exp(\mathbf{x}^\top\boldsymbol{\beta} + \sigma\log\log 2)$$
Cox PH models the *hazard ratio* — a relative measure that requires a non-parametric baseline hazard for absolute time predictions.

**2. Implementation Stability in Pure NumPy/SciPy:** Cox PH requires computing the partial likelihood over all risk sets $\mathcal{R}(t_i)$ — an $O(n^2)$ operation that scales poorly without specialized software (`lifelines`, `scikit-survival`). Weibull AFT's log-likelihood is fully vectorised in $O(n)$ and maps cleanly to `scipy.optimize.minimize`. Our Log-Sum-Exp numerical stabilization (to prevent `float64` overflow in exponential evaluations) is straightforward to implement for the Weibull scale.

**3. Model Assumptions Check:** We verified that the Weibull distribution is a reasonable fit for our inter-repair interval data. The daily-deduplicated interval distribution showed a right-skewed, heavy-tailed profile consistent with Weibull shape parameters $k > 1$ (increasing hazard over time for repeatedly repaired segments), supporting the parametric assumption.

**Trade-off acknowledged:** Cox PH makes fewer distributional assumptions (semi-parametric). If distributional fit were poor, Cox PH would be preferred. A future study could formally compare using log-likelihood ratio tests or AIC.

---

## Rapid-Fire Questions — Short Answers

| Question | 20-Second Answer |
|---|---|
| "What is your observation unit?" | Segment-month: (canonical_segment_id, as_of_date) — 47,983 × 102 = 4,894,266 total rows |
| "Why XGBoost over Random Forest?" | XGBoost achieved AP=0.806 vs baseline ~0.15 on validation set; sequential boosting vs. bagging produces stronger signal on imbalanced tabular data |
| "What does a Brier Score of 0.040 mean?" | Mean squared error between predicted probability and 0/1 outcome. Under 5.79% prevalence, a naïve all-zeros classifier scores 0.0579 — our 0.040 is better calibrated |
| "How many SHAP values did you compute?" | 527,813 rows × 110 features = ~58M Shapley contributions, using exact Tree Contributions |
| "Why is AP more important than accuracy?" | Accuracy is misleading at 5.79% prevalence — a model predicting all-negatives achieves 94.21% accuracy. AP (PR-AUC) properly rewards precision at each recall threshold |
| "What is your test-set target prevalence?" | 5.792% — 30,572 positive segment-months out of 527,813 total |
| "How many phase gate reports exist?" | 10 gate reports (Phase 2 through Phase 10), each with immutable SHA-256 artifact fingerprints |
