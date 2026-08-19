"""Phase 6 — Sampling isolation (Part 1, configs B & C) +
              Feature-family ablation (Part 4, 6 models).

Part 1: Separates row vs column subsampling effect (perm=137, model=42)
  A: sub=0.8, col=0.8  [reference — already done]
  B: sub=1.0, col=0.8  [NEW — row subsampling removed]
  C: sub=0.8, col=1.0  [NEW — column subsampling removed]
  D: sub=1.0, col=1.0  [reference — already done]

Part 4: Feature-family ablation (perm=137, model=42, sub=0.8, col=0.8)
  1. repair_history only
  2. static_admin only
  3. pavement_asset only
  4. weather_temporal only
  5. all EXCEPT repair_history
  6. all EXCEPT static_admin

Diagnostic only — does not replace the selected Phase 5 model.
No sealed targets accessed.
"""
from __future__ import annotations

import gc
import hashlib
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.preprocessing import OrdinalEncoder

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

TRAIN_PATH   = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
VAL_PATH     = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
MODEL_DIR    = _REPO_ROOT / "models/phase_5/full_training_external_memory_candidate"
FIXED_ROUNDS = 184
PERM_SEED    = 137
MODEL_SEED   = 42

SEALED_ANCHORS = {
    "2024-01-31","2024-02-29","2024-03-31",
    "2024-04-30","2024-05-31","2024-06-30",
    "2024-07-31","2024-08-31","2024-09-30","2024-10-31","2024-11-30",
    "2024-12-31","2025-01-31","2025-02-28","2025-03-31",
    "2025-04-30","2025-05-31",
}

# ---------------------------------------------------------------------------
# Feature families (all 110 features)
# ---------------------------------------------------------------------------
REPAIR_HISTORY = [
    "days_since_last_repair", "no_prior_repair_flag", "prior_repair_months_12m",
    "repair_active_days_30d", "repair_active_days_90d",
    "repair_active_days_180d", "repair_active_days_365d",
    "repair_event_count_collapsed_30d", "repair_event_count_collapsed_90d",
    "repair_event_count_collapsed_180d", "repair_event_count_collapsed_365d",
    "repair_history_complete_30d", "repair_history_complete_90d",
    "repair_history_complete_180d", "repair_history_complete_365d",
    "repair_history_coverage_ratio_30d", "repair_history_coverage_ratio_90d",
    "repair_history_coverage_ratio_180d", "repair_history_coverage_ratio_365d",
    "repair_history_valid_days_30d", "repair_history_valid_days_90d",
    "repair_history_valid_days_180d", "repair_history_valid_days_365d",
]  # 23 features

STATIC_ADMIN = [
    "administrative_category", "boundary_candidate_count", "boundary_crossing_flag",
    "functional_road_class", "future_asset_record_hidden_flag",
    "official_administrative_name", "resurfacing_before_construction_candidate_flag",
    "road_category", "road_type", "segment_length_m", "unmatched_boundary_flag",
]  # 11 features

PAVEMENT_ASSET = [
    "age_interval_crosses_as_of_flag", "asset_temporal_eligibility_status",
    "condition_campaign_scope", "condition_candidate_count", "condition_missing_flag",
    "date_contradiction_status", "days_since_condition_survey",
    "iri_max", "iri_min", "iri_std", "latest_iri", "latest_pci",
    "pci_max", "pci_min", "pci_std",
    "resurfacing_interval_crosses_as_of_flag",
    "years_since_construction_lower", "years_since_construction_upper",
    "years_since_resurfacing_lower", "years_since_resurfacing_upper",
]  # 20 features

WEATHER_TEMPORAL = [
    "freeze_thaw_max_ge_zero_sum_30d","freeze_thaw_max_ge_zero_sum_90d",
    "freeze_thaw_max_ge_zero_sum_180d","freeze_thaw_max_ge_zero_sum_365d",
    "freeze_thaw_min_le_zero_sum_30d","freeze_thaw_min_le_zero_sum_90d",
    "freeze_thaw_min_le_zero_sum_180d","freeze_thaw_min_le_zero_sum_365d",
    "freeze_thaw_strict_sum_30d","freeze_thaw_strict_sum_90d",
    "freeze_thaw_strict_sum_180d","freeze_thaw_strict_sum_365d",
    "max_temp_fallback_days_30d","max_temp_fallback_days_90d",
    "max_temp_fallback_days_180d","max_temp_fallback_days_365d",
    "max_temp_max_30d","max_temp_max_90d","max_temp_max_180d","max_temp_max_365d",
    "mean_temp_fallback_days_30d","mean_temp_fallback_days_90d",
    "mean_temp_fallback_days_180d","mean_temp_fallback_days_365d",
    "mean_temp_mean_30d","mean_temp_mean_90d","mean_temp_mean_180d","mean_temp_mean_365d",
    "min_temp_fallback_days_30d","min_temp_fallback_days_90d",
    "min_temp_fallback_days_180d","min_temp_fallback_days_365d",
    "min_temp_min_30d","min_temp_min_90d","min_temp_min_180d","min_temp_min_365d",
    "total_precip_fallback_days_30d","total_precip_fallback_days_90d",
    "total_precip_fallback_days_180d","total_precip_fallback_days_365d",
    "total_precip_sum_30d","total_precip_sum_90d",
    "total_precip_sum_180d","total_precip_sum_365d",
    "weather_complete_30d","weather_complete_90d",
    "weather_complete_180d","weather_complete_365d",
    "weather_coverage_ratio_30d","weather_coverage_ratio_90d",
    "weather_coverage_ratio_180d","weather_coverage_ratio_365d",
    "weather_valid_days_30d","weather_valid_days_90d",
    "weather_valid_days_180d","weather_valid_days_365d",
]  # 56 features

ALL_FEATURES = REPAIR_HISTORY + STATIC_ADMIN + PAVEMENT_ASSET + WEATHER_TEMPORAL


def sha256_arr(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()


def section(msg: str) -> None:
    print(f"\n{'─'*70}\n  {msg}\n{'─'*70}")


def check_sealed() -> None:
    tbl = pq.read_table(VAL_PATH, columns=["as_of_date"])
    dates = {str(d)[:10] for d in tbl.column("as_of_date").to_pylist()}
    bad = dates & SEALED_ANCHORS
    if bad:
        raise RuntimeError(f"ABORT: sealed anchors in val: {bad}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_shared_data(cfg: dict) -> tuple:
    """Load val table, train labels, permuted labels. Cached across runs."""
    val_tbl = pq.read_table(VAL_PATH)
    y_val   = np.array(val_tbl.column("target_repair_90d").to_pylist(), dtype=float)

    train_lbl = pq.read_table(TRAIN_PATH,
                               columns=["segment_month_id", "target_repair_90d"])
    y_orig  = np.array(train_lbl.column("target_repair_90d").to_pylist(),
                        dtype=np.int8)
    del train_lbl

    rng    = np.random.default_rng(PERM_SEED)
    perm   = rng.permutation(len(y_orig))
    y_shuf = y_orig[perm]

    assert y_shuf.sum() == y_orig.sum()
    assert not np.array_equal(y_shuf, y_orig)

    target_col = "target_repair_90d"
    id_cols    = {"segment_month_id", "canonical_segment_id", "as_of_date"}
    cat_cols   = set(cfg.get("categorical_cols", []))
    excl       = set(cfg.get("exclude_from_X", []))
    feat_cols  = [
        c for c in val_tbl.schema.names
        if c != target_col and c not in id_cols and c not in excl
    ]
    return val_tbl, y_val, y_orig, y_shuf, feat_cols, cat_cols


def normalize_df(df, cat_cols_feat):
    df = df.copy()
    if "days_since_last_repair" in df.columns:
        df["days_since_last_repair"] = df["days_since_last_repair"].fillna(-1)
    for c in cat_cols_feat:
        if c in df.columns:
            df[c] = df[c].fillna("missing").astype(object)
    return df


def make_simple_preprocessor(feature_subset: list[str], cat_cols: set[str]):
    """Ordinal encoder for categoricals + passthrough for numerics."""
    cat_in = [c for c in feature_subset if c in cat_cols]
    num_in = [c for c in feature_subset if c not in cat_cols]
    transformers = []
    if cat_in:
        transformers.append((
            "cat",
            OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
            cat_in,
        ))
    if num_in:
        transformers.append(("num", "passthrough", num_in))
    return ColumnTransformer(transformers, sparse_threshold=0.0)


def run_sampling_config(
    subsample: float,
    colsample_bytree: float,
    label: str,
    preprocessor,
    feat_cols: list[str],
    cat_cols_feat: list[str],
    y_shuf: np.ndarray,
    val_tbl,
    y_val: np.ndarray,
    shuf_sha: str,
) -> dict:
    """Part 1: full-preprocessor run, varying subsample/colsample."""
    section(f"SAMPLING CONFIG: {label}")
    cache_dir = tempfile.mkdtemp(
        prefix=f"samp_{label.replace('.', '_').replace('=', '')}_"
    )
    cache_fp = hashlib.sha256(cache_dir.encode()).hexdigest()
    print(f"  cache_dir: {cache_dir}")
    try:
        cfg_json = json.loads(
            (_REPO_ROOT / "config/phase_5_modeling.json").read_text()
        )
        cat_cols_feat_local = [c for c in feat_cols
                                if c in set(cfg_json.get("categorical_cols", []))]

        # Load + transform train features
        chunks = []
        for batch in pq.ParquetFile(TRAIN_PATH).iter_batches(
            batch_size=200_000, columns=feat_cols
        ):
            df = batch.to_pandas()
            chunks.append(
                preprocessor.transform(
                    normalize_df(df, cat_cols_feat_local)
                ).astype(np.float32)
            )
            del df, batch
            gc.collect()
        X_train = np.vstack(chunks)
        del chunks
        gc.collect()

        dm_train = xgb.DMatrix(X_train, label=y_shuf.astype(np.float32))
        del X_train
        gc.collect()

        meta   = json.loads((MODEL_DIR / "metadata.json").read_text())
        params = dict(meta["params"])
        params["seed"]             = MODEL_SEED
        params["nthread"]          = 1
        params["subsample"]        = subsample
        params["colsample_bytree"] = colsample_bytree
        params.pop("eval_metric", None)
        params["eval_metric"] = "aucpr"

        t0 = time.perf_counter()
        bst = xgb.train(params, dm_train, num_boost_round=FIXED_ROUNDS)
        elapsed = time.perf_counter() - t0
        del dm_train
        gc.collect()

        X_val_df = val_tbl.select(feat_cols).to_pandas()
        X_val    = preprocessor.transform(
            normalize_df(X_val_df, cat_cols_feat_local)
        ).astype(np.float32)
        del X_val_df

        preds   = bst.predict(xgb.DMatrix(X_val), iteration_range=(0, FIXED_ROUNDS))
        del bst, X_val
        gc.collect()

        pred_sha = sha256_arr(preds.astype(np.float32))
        ap    = float(average_precision_score(y_val, preds))
        auc   = float(roc_auc_score(y_val, preds))
        brier = float(brier_score_loss(y_val, preds))
        pstd  = float(preds.std())
        prev  = float(y_val.mean())

        print(f"  AP={ap:.6f}  AUC={auc:.6f}  Brier={brier:.6f}  "
              f"pred_std={pstd:.4f}  time={elapsed:.1f}s")

        return {
            "label": label, "type": "sampling",
            "perm_seed": PERM_SEED, "model_seed": MODEL_SEED,
            "subsample": subsample, "colsample_bytree": colsample_bytree,
            "feature_count": len(feat_cols),
            "cache_fingerprint": cache_fp,
            "shuf_label_sha256": shuf_sha,
            "pred_sha256": pred_sha,
            "val_prevalence": round(prev, 8),
            "null_ap": round(ap, 8),
            "ap_minus_prevalence": round(ap - prev, 8),
            "ap_ratio": round(ap / prev, 4),
            "null_roc_auc": round(auc, 8),
            "auc_minus_half": round(auc - 0.5, 8),
            "null_brier": round(brier, 8),
            "pred_std": round(pstd, 6),
            "train_time_s": round(elapsed, 1),
            "b1_accessed": False, "embargo_accessed": False, "b2_accessed": False,
        }
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def run_ablation(  # noqa: C901
    family_label: str,
    feature_subset: list[str],
    y_shuf: np.ndarray,
    y_orig: np.ndarray,
    val_tbl,
    y_val: np.ndarray,
    cat_cols: set[str],
    shuf_sha: str,
) -> dict:
    """Part 4: ablation run with simple preprocessor on feature subset."""
    section(f"ABLATION: {family_label} ({len(feature_subset)} features)")
    cache_dir = tempfile.mkdtemp(prefix=f"abl_{family_label[:20]}_")
    cache_fp  = hashlib.sha256(cache_dir.encode()).hexdigest()
    print(f"  cache_dir: {cache_dir}")

    # Verify subset contains no forbidden columns
    forbidden_kw = ["target", "future_", "_id", "as_of_date"]
    for c in feature_subset:
        for kw in forbidden_kw:
            if kw in c and c != "future_asset_record_hidden_flag":
                raise RuntimeError(f"ABORT: suspicious col in ablation: {c}")

    try:
        cat_in_sub = [c for c in feature_subset if c in cat_cols]

        def prep_df(df):
            df = df.copy()
            if "days_since_last_repair" in df.columns:
                df["days_since_last_repair"] = \
                    df["days_since_last_repair"].fillna(-1)
            for c in cat_in_sub:
                if c in df.columns:
                    df[c] = df[c].fillna("missing").astype(str)
            num_in_sub = [c for c in feature_subset if c not in cat_cols]
            for c in num_in_sub:
                if c in df.columns:
                    df[c] = df[c].fillna(-1)
            return df

        # Fit simple preprocessor on first chunk
        print("  Fitting simple preprocessor...")
        first_chunk = next(iter(
            pq.ParquetFile(TRAIN_PATH).iter_batches(
                batch_size=200_000, columns=feature_subset
            )
        ))
        first_df = prep_df(first_chunk.to_pandas())
        pre = make_simple_preprocessor(feature_subset, cat_cols)
        pre.fit(first_df)
        del first_chunk, first_df
        gc.collect()

        # Transform all train chunks
        chunks = []
        for batch in pq.ParquetFile(TRAIN_PATH).iter_batches(
            batch_size=200_000, columns=feature_subset
        ):
            df = batch.to_pandas()
            chunks.append(pre.transform(prep_df(df)).astype(np.float32))
            del df, batch
            gc.collect()
        X_train = np.vstack(chunks)
        del chunks
        gc.collect()

        dm_train = xgb.DMatrix(X_train, label=y_shuf.astype(np.float32))
        del X_train
        gc.collect()

        meta   = json.loads((MODEL_DIR / "metadata.json").read_text())
        params = dict(meta["params"])
        params["seed"]             = MODEL_SEED
        params["nthread"]          = 1
        params["subsample"]        = 0.8
        params["colsample_bytree"] = 0.8
        params.pop("eval_metric", None)
        params["eval_metric"] = "aucpr"

        t0  = time.perf_counter()
        bst = xgb.train(params, dm_train, num_boost_round=FIXED_ROUNDS)
        elapsed = time.perf_counter() - t0
        del dm_train
        gc.collect()

        X_val_df = val_tbl.select(feature_subset).to_pandas()
        X_val    = pre.transform(prep_df(X_val_df)).astype(np.float32)
        del X_val_df

        preds   = bst.predict(xgb.DMatrix(X_val), iteration_range=(0, FIXED_ROUNDS))
        del bst, X_val
        gc.collect()

        pred_sha = sha256_arr(preds.astype(np.float32))
        ap    = float(average_precision_score(y_val, preds))
        auc   = float(roc_auc_score(y_val, preds))
        brier = float(brier_score_loss(y_val, preds))
        pstd  = float(preds.std())
        prev  = float(y_val.mean())

        print(f"  AP={ap:.6f}  AUC={auc:.6f}  Brier={brier:.6f}  "
              f"pred_std={pstd:.4f}  time={elapsed:.1f}s")

        return {
            "label": family_label, "type": "ablation",
            "perm_seed": PERM_SEED, "model_seed": MODEL_SEED,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "feature_count": len(feature_subset),
            "feature_names": feature_subset,
            "cache_fingerprint": cache_fp,
            "shuf_label_sha256": shuf_sha,
            "pred_sha256": pred_sha,
            "val_prevalence": round(prev, 8),
            "null_ap": round(ap, 8),
            "ap_minus_prevalence": round(ap - prev, 8),
            "ap_ratio": round(ap / prev, 4),
            "null_roc_auc": round(auc, 8),
            "auc_minus_half": round(auc - 0.5, 8),
            "null_brier": round(brier, 8),
            "pred_std": round(pstd, 6),
            "train_time_s": round(elapsed, 1),
            "b1_accessed": False, "embargo_accessed": False, "b2_accessed": False,
        }
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def main() -> None:  # noqa: C901
    print("=" * 70)
    print("PHASE 6 SAMPLING ISOLATION + FEATURE ABLATION")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("perm_seed=137, model_seed=42")
    print("=" * 70)

    check_sealed()

    cfg = json.loads((_REPO_ROOT / "config/phase_5_modeling.json").read_text())
    cat_cols = set(cfg.get("categorical_cols", []))

    print("\nLoading shared data (val + train labels)...")
    val_tbl, y_val, y_orig, y_shuf, feat_cols, _ = load_shared_data(cfg)
    shuf_sha = sha256_arr(y_shuf.astype(np.int8))
    prev = float(y_val.mean())
    print(f"  val_prev={prev:.6f}  shuf_sha={shuf_sha[:16]}...")
    print(f"  n_train={len(y_orig):,}  n_val={len(y_val):,}  n_feats={len(feat_cols)}")

    # Verify all family features are in feat_cols
    feat_set = set(feat_cols)
    for name, fam in [("repair_history", REPAIR_HISTORY),
                       ("static_admin", STATIC_ADMIN),
                       ("pavement_asset", PAVEMENT_ASSET),
                       ("weather_temporal", WEATHER_TEMPORAL)]:
        missing = [f for f in fam if f not in feat_set]
        if missing:
            raise RuntimeError(f"Family {name} has cols not in feat_cols: {missing}")
    print(f"  Family totals: repair={len(REPAIR_HISTORY)}, admin={len(STATIC_ADMIN)}, "
          f"pave={len(PAVEMENT_ASSET)}, weather={len(WEATHER_TEMPORAL)}, "
          f"total={len(ALL_FEATURES)}")

    results = {}

    # -----------------------------------------------------------------------
    # PART 1 — Sampling isolation (B and C only; A and D from prior experiment)
    # -----------------------------------------------------------------------
    preprocessor = joblib.load(MODEL_DIR / "preprocessor.joblib")
    cat_cols_feat = [c for c in feat_cols if c in cat_cols]

    for sub, col, lbl in [
        (1.0, 0.8, "B_sub1.0_col0.8"),
        (0.8, 1.0, "C_sub0.8_col1.0"),
    ]:
        results[lbl] = run_sampling_config(
            subsample=sub, colsample_bytree=col, label=lbl,
            preprocessor=preprocessor, feat_cols=feat_cols,
            cat_cols_feat=cat_cols_feat,
            y_shuf=y_shuf, val_tbl=val_tbl, y_val=y_val,
            shuf_sha=shuf_sha,
        )

    # -----------------------------------------------------------------------
    # PART 4 — Feature-family ablation (6 models)
    # -----------------------------------------------------------------------
    ablation_configs = [
        ("abl1_repair_history_only",       REPAIR_HISTORY),
        ("abl2_static_admin_only",         STATIC_ADMIN),
        ("abl3_pavement_asset_only",       PAVEMENT_ASSET),
        ("abl4_weather_temporal_only",     WEATHER_TEMPORAL),
        ("abl5_all_except_repair_history", STATIC_ADMIN + PAVEMENT_ASSET + WEATHER_TEMPORAL),
        ("abl6_all_except_static_admin",   REPAIR_HISTORY + PAVEMENT_ASSET + WEATHER_TEMPORAL),
    ]
    for lbl, feats in ablation_configs:
        results[lbl] = run_ablation(
            family_label=lbl, feature_subset=feats,
            y_shuf=y_shuf, y_orig=y_orig,
            val_tbl=val_tbl, y_val=y_val,
            cat_cols=cat_cols, shuf_sha=shuf_sha,
        )

    # -----------------------------------------------------------------------
    # Summary tables
    # -----------------------------------------------------------------------
    # Include A and D from prior experiment
    prior = json.loads(
        (_REPO_ROOT / "models/phase_6/seed_isolation_experiment.json").read_text()
    )["runs"]
    ref_a = prior.get("part3_perm137_model42_fullsample") or {}
    # Find A (sub=0.8/col=0.8 at perm=137)
    for v in prior.values():
        if (v.get("perm_seed") == 137 and v.get("model_seed") == 42
                and v.get("subsample") == 0.8 and v.get("colsample_bytree") == 0.8):
            ref_a = v
            break
    ref_d = None
    for v in prior.values():
        if (v.get("perm_seed") == 137 and v.get("model_seed") == 42
                and v.get("subsample") == 1.0):
            ref_d = v
            break

    print("\n" + "=" * 70)
    print("  PART 1 — Sampling isolation (perm=137, model=42)")
    print("=" * 70)
    print(f"  {'Config':<22}  {'sub':>5}  {'col':>5}  {'AP':>10}  "
          f"{'AUC':>10}  {'AUC-0.5':>8}")
    configs_ordered = [
        ("A_sub0.8_col0.8 [ref]", ref_a.get("null_ap"), ref_a.get("null_roc_auc"),
         0.8, 0.8),
        ("B_sub1.0_col0.8",
         results["B_sub1.0_col0.8"]["null_ap"],
         results["B_sub1.0_col0.8"]["null_roc_auc"], 1.0, 0.8),
        ("C_sub0.8_col1.0",
         results["C_sub0.8_col1.0"]["null_ap"],
         results["C_sub0.8_col1.0"]["null_roc_auc"], 0.8, 1.0),
        ("D_sub1.0_col1.0 [ref]", ref_d.get("null_ap") if ref_d else None,
         ref_d.get("null_roc_auc") if ref_d else None, 1.0, 1.0),
    ]
    for name, ap, auc, sub, col in configs_ordered:
        if ap is None:
            print(f"  {name:<22}  {sub:>5.1f}  {col:>5.1f}  {'N/A':>10}  {'N/A':>10}")
        else:
            print(f"  {name:<22}  {sub:>5.1f}  {col:>5.1f}  {ap:>10.6f}  "
                  f"{auc:>10.6f}  {auc-0.5:>+8.6f}")

    print("\n" + "=" * 70)
    print("  PART 4 — Feature-family ablation (perm=137, model=42, sub=0.8, col=0.8)")
    print("=" * 70)
    print(f"  {'Family':<36}  {'N':>4}  {'AP':>10}  {'AUC':>10}  {'AUC-0.5':>8}")
    all_auc = {"A_full": ref_a.get("null_roc_auc", 0.0)}
    for lbl, _ in ablation_configs:
        r = results[lbl]
        print(f"  {lbl:<36}  {r['feature_count']:>4}  "
              f"{r['null_ap']:>10.6f}  {r['null_roc_auc']:>10.6f}  "
              f"{r['null_roc_auc']-0.5:>+8.6f}")
        all_auc[lbl] = r["null_roc_auc"]

    # Interpretation
    print("\n" + "=" * 70)
    print("  INTERPRETATION")
    print("=" * 70)
    b_auc = results["B_sub1.0_col0.8"]["null_roc_auc"]
    c_auc = results["C_sub0.8_col1.0"]["null_roc_auc"]
    ref_auc = ref_a.get("null_roc_auc", 0.0)
    d_auc   = ref_d.get("null_roc_auc", 0.0) if ref_d else 0.0
    print(f"\n  Sampling effect on AUC (reference A = {ref_auc:.4f}):")
    print(f"    B (no row sub)   : {b_auc:.4f}  delta={b_auc-ref_auc:+.4f}")
    print(f"    C (no col sub)   : {c_auc:.4f}  delta={c_auc-ref_auc:+.4f}")
    print(f"    D (no sampling)  : {d_auc:.4f}  delta={d_auc-ref_auc:+.4f}")
    if b_auc < 0.58 and c_auc > 0.58:
        print("\n  Row subsampling is the dominant driver.")
    elif c_auc < 0.58 and b_auc > 0.58:
        print("\n  Column subsampling is the dominant driver.")
    elif b_auc < 0.58 and c_auc < 0.58:
        print("\n  Both row and column subsampling are necessary for the elevation.")
    else:
        print("\n  Neither row nor column subsampling alone reduces the elevation.")

    # Highest ablation AUC
    abl_aucs = {lbl: results[lbl]["null_roc_auc"] for lbl, _ in ablation_configs}
    top_fam  = max(abl_aucs, key=abl_aucs.get)
    print(f"\n  Highest ablation AUC: {top_fam}  AUC={abl_aucs[top_fam]:.4f}")
    if abl_aucs[top_fam] > 0.60:
        print("  This family reproduces the elevated AUC — primary driver candidate.")
    else:
        print("  No single family reproduces the full elevation.")

    # Write report
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "perm_seed": PERM_SEED, "model_seed": MODEL_SEED,
        "shuf_label_sha256": shuf_sha,
        "val_prevalence": round(prev, 8),
        "sampling_refs": {
            "A_sub0.8_col0.8": {"null_ap": ref_a.get("null_ap"),
                                  "null_roc_auc": ref_a.get("null_roc_auc")},
            "D_sub1.0_col1.0": {"null_ap": ref_d.get("null_ap") if ref_d else None,
                                  "null_roc_auc": ref_d.get("null_roc_auc") if ref_d else None},
        },
        "runs": results,
        "b1_accessed": False, "embargo_accessed": False, "b2_accessed": False,
    }
    out = _REPO_ROOT / "models/phase_6/sampling_ablation_experiment.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
