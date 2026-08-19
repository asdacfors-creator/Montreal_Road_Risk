"""
Part 5 — Calculate Final Statistics from the PyArrow Dataset.
"""
import json
from pathlib import Path

import pyarrow.dataset as ds

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main():  # noqa: C901
    print("Loading PyArrow dataset...")
    # Standard PyArrow dataset call with ignore prefixes to bypass metadata/ledger files
    dataset = ds.dataset(
        "data/processed/phase_4",
        format="parquet",
        partitioning="hive",
        ignore_prefixes=[
            "_", "pre_run", "phase_4", "accepted", "duplicate",
            "outcome", "target", "determinism", "panel_statistics", "true"
        ]
    )

    cols = [
        "canonical_segment_id", "as_of_date",
        "target_repair_90d", "target_repair_180d",
        "target_repair_90d_strict", "target_repair_180d_strict",
        "repair_event_count_raw_90d", "repair_event_count_collapsed_90d",
        "condition_missing_flag", "no_prior_repair_flag",
        "asset_temporal_eligibility_status"
    ]

    print("Reading dataset columns to memory...")
    table = dataset.to_table(columns=cols)
    df = table.to_pandas()

    total_rows = len(df)
    unique_segs = len(df["canonical_segment_id"].unique())
    unique_anchors = len(df["as_of_date"].unique())

    # 90-day target prevalence
    pos_90 = int(df["target_repair_90d"].sum())
    neg_90 = int((df["target_repair_90d"] == 0).sum())
    prev_90 = pos_90 / total_rows

    # 180-day target prevalence
    pos_180 = int(df["target_repair_180d"].sum())
    neg_180 = int((df["target_repair_180d"] == 0).sum())
    prev_180 = pos_180 / total_rows

    # Strict policy null counts
    strict_null_90 = int(df["target_repair_90d_strict"].isna().sum())
    strict_null_180 = int(df["target_repair_180d_strict"].isna().sum())

    # Raw vs collapsed target disagreement in history (90d)
    raw_pos = (df["repair_event_count_raw_90d"] > 0).astype(int)
    col_pos = (df["repair_event_count_collapsed_90d"] > 0).astype(int)
    disagree_90 = int((raw_pos != col_pos).sum())

    # Feature missingness
    cond_missing_count = int(df["condition_missing_flag"].sum())
    no_prior_repair_count = int(df["no_prior_repair_flag"].sum())

    # Asset temporal-availability breakdown
    asset_status_counts = df["asset_temporal_eligibility_status"].value_counts().to_dict()

    # Read duplicate summary
    dup_summary_path = PROJECT_ROOT / "data/processed/phase_4/duplicate_sensitivity_summary.json"
    dup_summary = {}
    if dup_summary_path.exists():
        dup_summary = json.loads(dup_summary_path.read_text())

    stats = {
        "total_rows": total_rows,
        "unique_segments": unique_segs,
        "unique_anchors": unique_anchors,
        "target_90d": {
            "positives": pos_90,
            "negatives": neg_90,
            "prevalence": prev_90
        },
        "target_180d": {
            "positives": pos_180,
            "negatives": neg_180,
            "prevalence": prev_180
        },
        "strict_policy_null_counts": {
            "target_90d_strict": strict_null_90,
            "target_180d_strict": strict_null_180
        },
        "disagreement_90d_history": disagree_90,
        "pavement_condition_missing_rows": cond_missing_count,
        "no_prior_repair_rows": no_prior_repair_count,
        "asset_temporal_eligibility_status": asset_status_counts,
        "duplicate_sensitivity": dup_summary,
    }

    # Save statistics
    out_path = PROJECT_ROOT / "data/processed/phase_4/panel_statistics.json"
    out_path.write_text(json.dumps(stats, indent=2))

    print("\n=== PANEL STATISTICS ===")
    print(f"Total Rows: {total_rows}")
    print(f"Unique Segments: {unique_segs}")
    print(f"Unique Anchors: {unique_anchors}")
    print(f"90-Day Target: {pos_90} Pos, {neg_90} Neg, {prev_90*100:.6f}% Prev")
    print(f"180-Day Target: {pos_180} Pos, {neg_180} Neg, {prev_180*100:.6f}% Prev")
    print(f"Strict Target Null Counts: 90d={strict_null_90}, 180d={strict_null_180}")
    print(f"Raw vs Collapsed Disagreement (90d history): {disagree_90}")
    print(f"Pavement Condition Missing Rows: {cond_missing_count} ({cond_missing_count/total_rows*100:.2f}%)")
    print(f"No Prior Repair Rows: {no_prior_repair_count} ({no_prior_repair_count/total_rows*100:.2f}%)")
    print("Asset Temporal Status:")
    for status, count in asset_status_counts.items():
        print(f"  {status}: {count} ({count/total_rows*100:.2f}%)")
    print(f"Statistics saved to {out_path}")

if __name__ == "__main__":
    main()
