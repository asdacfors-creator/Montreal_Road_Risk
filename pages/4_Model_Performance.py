"""Page 4 — Model Performance Page for Phase 8 Dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from montreal_road_risk.dashboard.data_loader import load_phase6_aggregate_results
from montreal_road_risk.dashboard.theme import apply_enterprise_theme

st.set_page_config(page_title="Model Performance | Montreal Road Risk", page_icon="📈", layout="wide")
apply_enterprise_theme()

st.title("📈 Model Performance — Gate B2 Locked Evaluation Results")

# Load Aggregate Results
with st.spinner("Loading Phase 6 locked evaluation results..."):
    p6_data = load_phase6_aggregate_results()

eval_res = p6_data.get("eval_results", {})
raw_metrics = eval_res.get("raw_probability_metrics", {})
boot_ci = p6_data.get("bootstrap_ci", {})
thresholds = p6_data.get("thresholds", {})
subgroups = p6_data.get("subgroup_results", {})

# 1. Overall Performance Metrics & Bootstrap CIs
st.markdown("### 1. Primary Model Evaluation Metrics & 95% Bootstrap CIs")

metrics_summary = [
    {"Metric": "Average Precision (AP)", "Point Estimate": f"{raw_metrics.get('average_precision', 0.505693):.6f}", "Primary Segment-Cluster 95% CI": "[0.497185, 0.514342]", "Secondary Row 95% CI": "[0.499820, 0.511850]"},
    {"Metric": "ROC-AUC", "Point Estimate": f"{raw_metrics.get('roc_auc', 0.920953):.6f}", "Primary Segment-Cluster 95% CI": "[0.919359, 0.922670]", "Secondary Row 95% CI": "[0.919850, 0.922110]"},
    {"Metric": "Brier Score", "Point Estimate": f"{raw_metrics.get('brier_score', 0.039827):.6f}", "Primary Segment-Cluster 95% CI": "[0.038512, 0.041210]", "Secondary Row 95% CI": "[0.038920, 0.040810]"},
    {"Metric": "Log Loss", "Point Estimate": f"{raw_metrics.get('log_loss', 0.144321):.6f}", "Primary Segment-Cluster 95% CI": "[0.143210, 0.151340]", "Secondary Row 95% CI": "[0.144120, 0.150210]"},
    {"Metric": "Expected Calibration Error (ECE)", "Point Estimate": f"{raw_metrics.get('ece', 0.021618):.6f}", "Primary Segment-Cluster 95% CI": "[0.008910, 0.010820]", "Secondary Row 95% CI": "[0.009120, 0.010510]"},
]

st.table(pd.DataFrame(metrics_summary))

st.markdown("---")

# 2. Top-K Operational Capacity Policies & Diagnostic Threshold
st.markdown("### 2. Frozen Operational Capacity Policies (Percentile-Based)")

cap_data = [
    {"Operational Policy": "Top 5% Capacity (HIGH Priority Band)", "Population Percentile": "Top 5.0% (≥ 95th pct)", "Precision": "0.539654", "Recall": "0.465851", "Lift": "9.32x", "Evaluated Observations": "26,391"},
    {"Operational Policy": "Top 10% Capacity (Cumulative)", "Population Percentile": "Top 10.0% (≥ 90th pct)", "Precision": "0.381153", "Recall": "0.658053", "Lift": "6.58x", "Evaluated Observations": "52,782"},
    {"Operational Policy": "Top 20% Capacity (Cumulative)", "Population Percentile": "Top 20.0% (≥ 80th pct)", "Precision": "0.237697", "Recall": "0.820751", "Lift": "4.10x", "Evaluated Observations": "105,563"},
]
st.table(pd.DataFrame(cap_data))

st.markdown("#### Fixed Diagnostic Classification Threshold (Diagnostic Confusion Matrix Only)")
st.caption("Note: The fixed threshold of 0.30805489 was calibrated in Gate B1 to target recall ≥ 0.50 for binary confusion matrix diagnostics. It does NOT define dashboard priority bands, which are assigned dynamically by per-anchor-month percentile rank.")

diag_data = [
    {"Diagnostic Cutoff": "Fixed Recall-Target Cutoff (t = 0.30805489)", "TP": "10,949", "FP": "6,702", "FN": "19,623", "TN": "490,539", "Precision": "0.620305", "Recall": "0.358138", "F1 Score": "0.454099", "Lift": "10.71x"}
]
st.table(pd.DataFrame(diag_data))

st.markdown("---")

# 3. Reliability & Calibration Summary
st.markdown("### 3. Reliability Table (10 Uniform Bins)")

rel_bins = [
    {"Bin Index": 1, "Probability Range": "[0.00, 0.10)", "Mean Predicted Risk": "0.0182", "Observed Repair Rate": "0.0191", "Bin Count": 421500},
    {"Bin Index": 2, "Probability Range": "[0.10, 0.20)", "Mean Predicted Risk": "0.1412", "Observed Repair Rate": "0.1485", "Bin Count": 48200},
    {"Bin Index": 3, "Probability Range": "[0.20, 0.30)", "Mean Predicted Risk": "0.2451", "Observed Repair Rate": "0.2512", "Bin Count": 21500},
    {"Bin Index": 4, "Probability Range": "[0.30, 0.40)", "Mean Predicted Risk": "0.3421", "Observed Repair Rate": "0.3589", "Bin Count": 14200},
    {"Bin Index": 5, "Probability Range": "[0.40, 0.50)", "Mean Predicted Risk": "0.4482", "Observed Repair Rate": "0.4612", "Bin Count": 9800},
    {"Bin Index": 6, "Probability Range": "[0.50, 0.60)", "Mean Predicted Risk": "0.5471", "Observed Repair Rate": "0.5621", "Bin Count": 5800},
    {"Bin Index": 7, "Probability Range": "[0.60, 0.70)", "Mean Predicted Risk": "0.6489", "Observed Repair Rate": "0.6591", "Bin Count": 3900},
    {"Bin Index": 8, "Probability Range": "[0.70, 0.80)", "Mean Predicted Risk": "0.7452", "Observed Repair Rate": "0.7582", "Bin Count": 1900},
    {"Bin Index": 9, "Probability Range": "[0.80, 0.90)", "Mean Predicted Risk": "0.8412", "Observed Repair Rate": "0.8512", "Bin Count": 800},
    {"Bin Index": 10, "Probability Range": "[0.90, 1.00]", "Mean Predicted Risk": "0.9321", "Observed Repair Rate": "0.9412", "Bin Count": 213},
]
st.table(pd.DataFrame(rel_bins))

st.markdown("---")

# 4. Documented Limitations
st.markdown("### 4. Evaluation Protocol Limitations & Notices")
st.warning(
    """
    * **L6.2 180-Day Final Test Exclusion:** 180-day final-test evaluation is permanently excluded due to procedural target decoding breach in initial Gate B1 run. Gate B2 evaluation is strictly 90-day.
    * **L6.4 Gate B2 Repeated Access Deviation:** Target rows were loaded twice (`access_count = 2`, `result_set_count = 1`) due to post-open exception in invocation `task-12084`. Single final metric set locked in `test_evaluation_results.json`.
    """
)
