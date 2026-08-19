import json
from pathlib import Path

res = json.loads(Path('models/phase_6/test_evaluation_results.json').read_text())
sub = json.loads(Path('models/phase_6/test_subgroup_results.json').read_text())
boot = json.loads(Path('models/phase_6/test_bootstrap_ci.json').read_text())
access = json.loads(Path('models/phase_6/gate_b2_access_record.json').read_text())

print('=== EVALUATION SUMMARY ===')
print('N Total Rows:', res['n_total_rows'])
print('N Positives :', res['n_positives'])
print('Prevalence  :', res['prevalence'])

print('\n=== PRIMARY RAW METRICS ===')
raw_m = res['primary_raw_metrics']
print('AP        :', raw_m['average_precision'])
print('ROC-AUC   :', raw_m['roc_auc'])
print('Brier     :', raw_m['brier_score'])
print('Log Loss  :', raw_m['log_loss'])
print('ECE       :', raw_m['expected_calibration_error'])
print('Slope/Int :', raw_m['calibration_slope'], raw_m['calibration_intercept'])
print('Top 5%    :', raw_m['top_5_pct'])
print('Top 10%   :', raw_m['top_10_pct'])
print('Top 20%   :', raw_m['top_20_pct'])
print('Raw Thresh:', raw_m['primary_threshold_0_30805489'])

print('\n=== PLATT SENSITIVITY METRICS ===')
platt_m = res['sensitivity_platt_metrics']
print('Brier     :', platt_m['brier_score'])
print('Log Loss  :', platt_m['log_loss'])
print('ECE       :', platt_m['expected_calibration_error'])
print('Slope/Int :', platt_m['calibration_slope'], platt_m['calibration_intercept'])
print('Platt Thresh:', platt_m['sensitivity_threshold_0_20194759'])

print('\n=== BOOTSTRAP CIs (Cluster Primary) ===')
for k, v in boot['primary_segment_cluster'].items():
    if isinstance(v, dict):
        print(f"  {k:22s}: mean={v['mean']:.6f}, 95% CI=[{v['lower_95']:.6f}, {v['upper_95']:.6f}]")

print('\n=== BOOTSTRAP CIs (Row Secondary) ===')
for k, v in boot['secondary_row_level'].items():
    if isinstance(v, dict):
        print(f"  {k:22s}: mean={v['mean']:.6f}, 95% CI=[{v['lower_95']:.6f}, {v['upper_95']:.6f}]")

print('\n=== SUBGROUP SUMMARY ===')
for dim, dim_res in sub.items():
    evaluated = [k for k, v in dim_res.items() if v['status'] == 'EVALUATED']
    insufficient = [k for k, v in dim_res.items() if v['status'] == 'INSUFFICIENT_SAMPLE']
    print(f"  {dim:35s}: {len(evaluated)} evaluated, {len(insufficient)} insufficient ({insufficient})")
