"""Target-free stability analysis for Phase 7 SHAP feature importance.

Evaluates global feature importance stability across three deterministic stratified samples
(seeds 42, 137, 2026) using risk deciles, quarter, and borough stratification.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from montreal_road_risk.interpretation.reconciliation import (
    aggregate_importance_by_source_feature,
    build_feature_name_mapping,
)
from montreal_road_risk.interpretation.shap_engine import (
    StreamingSHAPAccumulator,
    compute_tree_contributions_batch,
)


def draw_stratified_sample(
    df: pd.DataFrame,
    sample_size: int,
    seed: int,
    strat_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Draw a reproducible stratified sample from target-free features / predictions DataFrame."""
    if strat_cols is None:
        strat_cols = ["risk_decile", "calendar_quarter", "primary_borough_id"]

    df_sample_pool = df.copy()
    # Create composite stratification key
    df_sample_pool["_strat_key"] = ""
    for col in strat_cols:
        df_sample_pool["_strat_key"] += df_sample_pool[col].astype(str) + "_"

    n_pool = len(df_sample_pool)
    frac = min(1.0, sample_size / n_pool)

    sampled = df_sample_pool.groupby("_strat_key", group_keys=False).apply(
        lambda g: g.sample(frac=frac, random_state=seed),
        include_groups=False,
    ).reset_index()

    if len(sampled) > sample_size:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(sampled), size=sample_size, replace=False)
        sampled = sampled.iloc[idx].reset_index(drop=True)

    sampled = sampled.drop(columns=["_strat_key"], errors="ignore")
    return sampled


def compute_sample_stability(
    booster: Any,
    prep: Any,
    b2_features_df: pd.DataFrame,
    b2_predictions_df: pd.DataFrame,
    seeds: list[int] | None = None,
    sample_size: int = 50000,
) -> dict[str, Any]:
    """Compute SHAP feature importance stability across deterministic stratified samples."""
    if seeds is None:
        seeds = [42, 137, 2026]
    # Build combined dataframe for stratification
    combined_df = b2_features_df.copy()
    combined_df["raw_probability"] = b2_predictions_df["raw_probability"].values
    combined_df["risk_decile"] = pd.qcut(
        combined_df["raw_probability"], q=10, labels=False, duplicates="drop"
    )
    combined_df["date_dt"] = pd.to_datetime(combined_df["as_of_date"].astype(str).str[:10])
    combined_df["calendar_quarter"] = "Q" + combined_df["date_dt"].dt.quarter.astype(str)

    feature_names = list(prep.feature_names_in_)
    tf_names = list(prep.get_feature_names_out())
    mapping = build_feature_name_mapping(tf_names, feature_names)

    best_iter = getattr(booster, "best_iteration", None)

    sample_importances: dict[int, pd.DataFrame] = {}
    sample_fingerprints: dict[int, str] = {}

    for seed in seeds:
        sample_df = draw_stratified_sample(combined_df, sample_size=sample_size, seed=seed)

        # Compute fingerprint of segment_month_ids
        import hashlib
        ids_str = "".join(sample_df["segment_month_id"].values)
        fp = hashlib.sha256(ids_str.encode("utf-8")).hexdigest()
        sample_fingerprints[seed] = fp

        X = sample_df[feature_names].copy()
        if "functional_road_class" in X.columns:
            X["functional_road_class"] = X["functional_road_class"].astype(object)

        X_trans = prep.transform(X)
        contribs = compute_tree_contributions_batch(booster, X_trans, best_iteration=best_iter)

        acc = StreamingSHAPAccumulator(n_features=len(tf_names))
        acc.update(contribs)
        tf_imp = acc.finalize(tf_names)
        src_imp = aggregate_importance_by_source_feature(tf_imp, mapping)
        sample_importances[seed] = src_imp

    # Compute Spearman rank correlations between seeds
    source_features = list(sample_importances[seeds[0]]["source_feature"])
    rank_df = pd.DataFrame({"source_feature": source_features})

    for seed in seeds:
        imp_df = sample_importances[seed]
        rank_dict = dict(zip(imp_df["source_feature"], imp_df["importance_rank"], strict=False))
        rank_df[f"rank_seed_{seed}"] = rank_df["source_feature"].map(rank_dict)

    rank_cols = [f"rank_seed_{seed}" for seed in seeds]

    corr_matrix = {}
    for i, s1 in enumerate(seeds):
        for s2 in seeds[i:]:
            r1 = rank_df[f"rank_seed_{s1}"].values
            r2 = rank_df[f"rank_seed_{s2}"].values
            rho, _ = spearmanr(r1, r2)
            key = f"seed_{s1}_vs_seed_{s2}"
            corr_matrix[key] = float(rho)

    # Compute top-10 and top-20 feature overlaps
    top10_sets = [set(sample_importances[s].head(10)["source_feature"]) for s in seeds]
    top20_sets = [set(sample_importances[s].head(20)["source_feature"]) for s in seeds]

    top10_intersection = len(set.intersection(*top10_sets))
    top20_intersection = len(set.intersection(*top20_sets))

    # Identify unstable features (rank std > 3.0 in top 30)
    rank_df["rank_mean"] = rank_df[rank_cols].mean(axis=1)
    rank_df["rank_std"] = rank_df[rank_cols].std(axis=1)
    rank_df["rank_min"] = rank_df[rank_cols].min(axis=1)
    rank_df["rank_max"] = rank_df[rank_cols].max(axis=1)

    unstable_features = rank_df[
        (rank_df["rank_mean"] <= 30) & (rank_df["rank_std"] > 3.0)
    ]["source_feature"].tolist()

    return {
        "seeds": seeds,
        "sample_size": sample_size,
        "sample_fingerprints": sample_fingerprints,
        "spearman_rank_correlations": corr_matrix,
        "top_10_overlap_count": top10_intersection,
        "top_20_overlap_count": top20_intersection,
        "unstable_top30_features": unstable_features,
        "rank_summary": rank_df.to_dict(orient="records"),
    }
