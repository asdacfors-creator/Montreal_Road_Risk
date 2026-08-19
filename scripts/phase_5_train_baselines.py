"""
scripts/phase_5_train_baselines.py

Step 10 — Train and validate three baseline models.

Three baselines (90d and 180d):
  BL1 — PrevalenceBaseline (global training rate)
  BL2 — FunctionalClassPriorBaseline (per-road-class prior)
  BL3 — SegmentHistoryBaseline (Laplace-smoothed per-segment rate)

Fitted exclusively on training partition, scored on validation partition.
No calibration. No test-set access.
"""

import json
import logging
import os
import sys
import time

import pandas as pd

sys.path.insert(0, "src")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load_partition(path: str, needed_cols: list[str] | None = None) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=needed_cols)
    log.info("Loaded %s: %d rows", os.path.basename(path), len(df))
    return df


def main() -> None:  # noqa: C901
    from montreal_road_risk.modeling.baselines import (
        FunctionalClassPriorBaseline,
        PrevalenceBaseline,
        SegmentHistoryBaseline,
    )
    from montreal_road_risk.modeling.metrics import compute_validation_metrics

    cfg_path = "config/phase_5_modeling.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    phase5_dir = cfg["phase5_dir"]
    models_dir = cfg["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    all_results = []

    for horizon, target_col, train_file, val_file in [
        ("90d",  "target_repair_90d",  "train_90d.parquet", "val_90d.parquet"),
        ("180d", "target_repair_180d", "train_180d.parquet", "val_180d.parquet"),
    ]:
        log.info("=== Baselines for %s ===", horizon)

        # Load minimal columns for baselines
        train_cols = [target_col, "functional_road_class", "canonical_segment_id", target_col]
        train_cols = list(dict.fromkeys(train_cols))  # deduplicate

        train_df = load_partition(os.path.join(phase5_dir, train_file))
        val_df   = load_partition(os.path.join(phase5_dir, val_file))

        # Filter to eligible rows only
        elig_col = f"target_eligible_{horizon}"
        if elig_col in train_df.columns:
            train_df = train_df[train_df[elig_col] == 1]
            val_df   = val_df[val_df[elig_col] == 1]
            log.info("After eligibility filter — train: %d, val: %d", len(train_df), len(val_df))

        y_train = train_df[target_col].values.astype(int)
        y_val   = val_df[target_col].values.astype(int)

        seg_ids_val = val_df["canonical_segment_id"].values if "canonical_segment_id" in val_df.columns else None
        aod_val     = val_df["as_of_date"].values if "as_of_date" in val_df.columns else None

        for bl_cls, bl_name, X_train_cols, X_val_cols in [
            (PrevalenceBaseline,         "BL1_Prevalence",       train_df, val_df),
            (FunctionalClassPriorBaseline, "BL2_FuncClassPrior", train_df, val_df),
            (SegmentHistoryBaseline,     "BL3_SegmentHistory",   train_df, val_df),
        ]:
            t0 = time.time()
            bl = bl_cls()
            bl.fit(X_train_cols, pd.Series(y_train))
            proba = bl.predict_proba(X_val_cols)
            elapsed = time.time() - t0

            metrics = compute_validation_metrics(
                y_val, proba,
                k_pcts=cfg["metrics"]["at_k_percents"],
                segment_ids=seg_ids_val,
                as_of_dates=aod_val,
                model_name=f"{bl_name}_{horizon}",
            )
            metrics["horizon"]  = horizon
            metrics["elapsed_s"] = round(elapsed, 3)
            all_results.append(metrics)
            log.info(
                "  %s_%s  AP=%.4f  ROC-AUC=%.4f  n_val=%d",
                bl_name, horizon, metrics["Average Precision (AP)"],
                metrics["ROC-AUC"], metrics["n_total"],
            )

        # Release memory
        del train_df, val_df

    # Save results
    out_path = os.path.join(models_dir, "baseline_validation_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    log.info("Baseline results saved: %s", out_path)

    # Print summary table
    print("\n=== BASELINE VALIDATION SUMMARY ===")
    for r in all_results:
        print(
            f"  {r['model']:<40s}  "
            f"AP={r['Average Precision (AP)']:.4f}  "
            f"ROC={r['ROC-AUC']:.4f}  "
            f"Brier={r['Brier']:.4f}"
        )


if __name__ == "__main__":
    main()
