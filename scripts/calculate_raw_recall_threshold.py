import hashlib
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FEATURES_PATH = PROJECT_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"
TARGETS_PATH = PROJECT_ROOT / "data/processed/phase_6/gate_b1_authorized_targets_90d.parquet"
MODEL_DIR = PROJECT_ROOT / "models/phase_5/full_training_remediated_01"

B1_ANCHORS = {"2024-01-31", "2024-02-29", "2024-03-31"}

def compute_raw_recall_threshold():
    print("=== PART 2: CALCULATE PRIMARY RAW RECALL THRESHOLD ===")

    # 1. Load B1 features & target
    df_feat = pd.read_parquet(FEATURES_PATH)
    df_feat["date_str"] = df_feat["as_of_date"].astype(str).str[:10]
    b1_feat = df_feat[df_feat["date_str"].isin(B1_ANCHORS)].copy()
    assert len(b1_feat) == 143949, f"Expected 143949 rows, got {len(b1_feat)}"

    targets_df = pd.read_parquet(TARGETS_PATH)
    assert len(targets_df) == 143949

    merged = b1_feat.merge(targets_df[["segment_month_id", "target_repair_90d"]], on="segment_month_id", how="inner")
    assert len(merged) == 143949

    # 2. Run model inference matching phase_6_gate_b1_remediate_run.py
    prep = joblib.load(MODEL_DIR / "preprocessor.joblib")
    bst = joblib.load(MODEL_DIR / "model.joblib")

    feature_names = list(prep.feature_names_in_)
    assert len(feature_names) == 110, f"Expected 110 features, got {len(feature_names)}"

    X_b1 = merged[feature_names].copy()
    if "functional_road_class" in X_b1.columns:
        X_b1["functional_road_class"] = X_b1["functional_road_class"].astype(object)

    X_trans = prep.transform(X_b1)
    dm = xgb.DMatrix(X_trans)
    best_iter = getattr(bst, "best_iteration", None)
    if best_iter is not None:
        raw_scores = bst.predict(dm, iteration_range=(0, best_iter + 1))
    else:
        raw_scores = bst.predict(dm)

    raw_preds = raw_scores.astype(np.float32)
    pred_sha = hashlib.sha256(raw_preds.tobytes()).hexdigest()
    print(f"Raw float32 prediction SHA-256: {pred_sha}")
    assert pred_sha == "5f616f7bfea2dada377094a0af547ef62824160aace75d132e7a1c6b0c1a65f9", f"Prediction SHA mismatch: {pred_sha}"

    y_true = merged["target_repair_90d"].values.astype(np.int8)
    n_pos = int(y_true.sum())

    # 3. Sort deterministically: descending raw score, canonical_segment_id, as_of_date, segment_month_id
    eval_df = pd.DataFrame({
        "raw_score": raw_preds,
        "target": y_true,
        "canonical_segment_id": merged["canonical_segment_id"].values,
        "as_of_date": merged["as_of_date"].values,
        "segment_month_id": merged["segment_month_id"].values,
    })

    eval_df = eval_df.sort_values(
        by=["raw_score", "canonical_segment_id", "as_of_date", "segment_month_id"],
        ascending=[False, True, True, True]
    ).reset_index(drop=True)

    eval_df["cum_pos"] = eval_df["target"].cumsum()
    eval_df["recall"] = eval_df["cum_pos"] / n_pos

    # Find highest threshold with recall >= 0.50
    eligible_mask = eval_df["recall"] >= 0.50
    eligible_indices = np.where(eligible_mask)[0]

    min_idx = eligible_indices[0]
    chosen_score = float(eval_df.loc[min_idx, "raw_score"])

    # Include complete boundary tie group
    all_ties = eval_df[eval_df["raw_score"] == chosen_score]
    tie_count = len(all_ties)

    last_tie_idx = eval_df[eval_df["raw_score"] == chosen_score].index[-1]
    selected_sub = eval_df.loc[:last_tie_idx]

    selected_rows = len(selected_sub)
    selected_pos = int(selected_sub["target"].sum())
    achieved_recall = float(selected_pos / n_pos)
    precision = float(selected_pos / selected_rows)
    f1 = float(2 * precision * achieved_recall / (precision + achieved_recall))
    prevalence = n_pos / len(y_true)
    lift = float(precision / prevalence)
    recall_overshoot = float(achieved_recall - 0.50)

    print("\n--- Primary Raw Recall Threshold Summary ---")
    print(f"Primary Raw Threshold    : {chosen_score:.8f}")
    print(f"Selected Row Count       : {selected_rows}")
    print(f"Selected Positives       : {selected_pos} / {n_pos}")
    print(f"Achieved Recall          : {achieved_recall:.6f}")
    print(f"Precision                : {precision:.6f}")
    print(f"F1 Score                 : {f1:.6f}")
    print(f"Lift                     : {lift:.6f}")
    print(f"Recall Overshoot         : {recall_overshoot:.6f}")
    print(f"Boundary Tie Count       : {tie_count}")

    # Prove immediately higher attainable threshold fails recall 0.50
    higher_scores = eval_df[eval_df["raw_score"] > chosen_score]
    if len(higher_scores) > 0:
        higher_score = higher_scores["raw_score"].iloc[-1]
        last_higher_idx = eval_df[eval_df["raw_score"] == higher_score].index[-1]
        higher_sub = eval_df.loc[:last_higher_idx]
        higher_pos = int(higher_sub["target"].sum())
        higher_recall = float(higher_pos / n_pos)
        print(f"\nImmediately Higher Distinct Threshold : {higher_score:.8f}")
        print(f"Higher Threshold Achieved Recall      : {higher_recall:.6f} (< 0.50 proved: {higher_recall < 0.50})")
        assert higher_recall < 0.50, f"Higher threshold unexpectedly achieved recall {higher_recall} >= 0.50"

    res = {
        "primary_raw_recall_threshold": chosen_score,
        "selected_row_count": selected_rows,
        "selected_positives": selected_pos,
        "achieved_recall": achieved_recall,
        "precision": precision,
        "f1_score": f1,
        "lift": lift,
        "recall_overshoot": recall_overshoot,
        "boundary_tie_count": tie_count,
        "sensitivity_platt_recall_threshold": 0.20194759
    }
    return res

if __name__ == "__main__":
    compute_raw_recall_threshold()
