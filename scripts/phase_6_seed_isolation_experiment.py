"""Phase 6 — Seed isolation experiment (Gate A investigation, Part 2).

Separates permutation_seed (label shuffle) from model_seed (XGBoost sampling).

Configurations run:
  Part 1 — fixed model_seed=42, permutation_seed in {42, 137, 2026}
  Part 2 — fixed permutation_seed=137, model_seed in {42, 137, 2026}
  Part 3 — permutation_seed=137, model_seed=42, subsample=1.0, colsample=1.0

Shared run: (perm=137, model=42) appears in both Part 1 and Part 2 — run once.

Output: models/phase_6/seed_isolation_experiment.json

Rules:
  - No B1, embargo, or B2 targets accessed
  - No real calibrator fitted
  - No push or commit in this script
  - Protected inputs not modified
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
import psutil
import pyarrow.parquet as pq
import xgboost as xgb
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

TRAIN_PATH  = _REPO_ROOT / "data/processed/phase_5/train_90d.parquet"
VAL_PATH    = _REPO_ROOT / "data/processed/phase_5/val_90d.parquet"
MODEL_DIR   = _REPO_ROOT / "models/phase_5/full_training_external_memory_candidate"
FIXED_ROUNDS = 184

SEALED_ANCHORS = {
    "2024-01-31", "2024-02-29", "2024-03-31",
    "2024-04-30", "2024-05-31", "2024-06-30",
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31",
    "2025-04-30", "2025-05-31",
}


def sha256_arr(arr: np.ndarray) -> str:
    return hashlib.sha256(arr.tobytes()).hexdigest()


def check_sealed(partition_path: Path) -> None:
    tbl = pq.read_table(partition_path, columns=["as_of_date"])
    dates = {str(d)[:10] for d in tbl.column("as_of_date").to_pylist()}
    bad = dates & SEALED_ANCHORS
    if bad:
        raise RuntimeError(f"ABORT: sealed anchors found in {partition_path.name}: {bad}")


def section(msg: str) -> None:
    print(f"\n{'─'*70}\n  {msg}\n{'─'*70}")


def run_one(
    perm_seed: int,
    model_seed: int,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    label: str = "",
) -> dict:
    """Run one complete null-control experiment with separated seeds."""
    tag = label or f"perm={perm_seed}_model={model_seed}_sub={subsample}"
    section(f"RUN: {tag}")
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # Isolated cache dir (proves no cross-run cache sharing)
    # ------------------------------------------------------------------
    cache_dir = tempfile.mkdtemp(
        prefix=f"null_p{perm_seed}_m{model_seed}_sub{int(subsample*10)}_"
    )
    cache_fingerprint = hashlib.sha256(cache_dir.encode()).hexdigest()
    print(f"  cache_dir    : {cache_dir}")
    print(f"  cache_fp     : {cache_fingerprint[:16]}...")

    try:
        # ------------------------------------------------------------------
        # Load val — sealed-anchor check
        # ------------------------------------------------------------------
        check_sealed(VAL_PATH)
        val_tbl = pq.read_table(VAL_PATH)
        y_val = np.array(val_tbl.column("target_repair_90d").to_pylist(), dtype=float)
        val_prevalence = float(y_val.mean())
        n_val = len(y_val)
        print(f"  val rows     : {n_val:,}   prevalence: {val_prevalence:.6f}")

        # ------------------------------------------------------------------
        # Load train labels — fresh read per run
        # ------------------------------------------------------------------
        train_lbl = pq.read_table(TRAIN_PATH,
                                   columns=["segment_month_id", "target_repair_90d"])
        y_train_orig = np.array(
            train_lbl.column("target_repair_90d").to_pylist(), dtype=np.int8
        )
        n_train = len(y_train_orig)
        orig_sha = sha256_arr(y_train_orig.astype(np.int8))
        del train_lbl

        # ------------------------------------------------------------------
        # Global permutation — uses perm_seed ONLY
        # ------------------------------------------------------------------
        rng_perm = np.random.default_rng(perm_seed)
        perm_idx = rng_perm.permutation(n_train)
        y_shuf   = y_train_orig[perm_idx]

        perm_sha = sha256_arr(perm_idx.astype(np.int64))
        shuf_sha = sha256_arr(y_shuf.astype(np.int8))

        # Integrity assertions
        assert y_shuf.sum() == y_train_orig.sum(), "multiset not preserved"
        assert not np.array_equal(y_shuf, y_train_orig), "shuffle identical"
        label_corr = float(np.corrcoef(
            y_train_orig.astype(float), y_shuf.astype(float)
        )[0, 1])
        assert abs(label_corr) < 0.01, f"label correlation {label_corr:.4f} too high"

        print(f"  perm_sha     : {perm_sha[:16]}...")
        print(f"  shuf_sha     : {shuf_sha[:16]}...")
        print(f"  label_corr   : {label_corr:.6f}")
        del y_train_orig, perm_idx

        # ------------------------------------------------------------------
        # Load features (chunked, in-memory — no disk cache)
        # ------------------------------------------------------------------
        preprocessor = joblib.load(MODEL_DIR / "preprocessor.joblib")
        cfg = json.loads((_REPO_ROOT / "config/phase_5_modeling.json").read_text())
        cat_cols = set(cfg.get("categorical_cols", []))

        target_col = "target_repair_90d"
        id_cols    = {"segment_month_id", "canonical_segment_id", "as_of_date"}
        feature_cols = [
            c for c in val_tbl.schema.names
            if c != target_col and c not in id_cols
        ]

        # Forbidden-feature assertion
        exclude_x = set(cfg.get("exclude_from_X", []))
        forbidden = [c for c in exclude_x if c in feature_cols]
        assert not forbidden, f"ABORT: forbidden cols in X: {forbidden}"

        cat_feat = [c for c in feature_cols if c in cat_cols]

        def normalize(df):
            df = df.copy()
            if "days_since_last_repair" in df.columns:
                df["days_since_last_repair"] = df["days_since_last_repair"].fillna(-1)
            for c in cat_feat:
                if c in df.columns:
                    df[c] = df[c].fillna("missing").astype(object)
            return df

        chunks = []
        for batch in pq.ParquetFile(TRAIN_PATH).iter_batches(
            batch_size=200_000, columns=feature_cols
        ):
            df = batch.to_pandas()
            chunks.append(
                preprocessor.transform(normalize(df)).astype(np.float32)
            )
            del df, batch
            gc.collect()
        X_train = np.vstack(chunks)
        del chunks
        gc.collect()

        feat_sha = sha256_arr(X_train[:5])
        print(f"  feat[0:5] sha: {feat_sha[:16]}...")
        assert len(X_train) == n_train, "feature/label row mismatch"

        # ------------------------------------------------------------------
        # DMatrix — fresh, in-memory
        # ------------------------------------------------------------------
        dm_train = xgb.DMatrix(X_train, label=y_shuf.astype(np.float32))
        del X_train, y_shuf
        gc.collect()

        # ------------------------------------------------------------------
        # XGBoost params — model_seed ONLY controls XGBoost sampling
        # ------------------------------------------------------------------
        meta   = json.loads((MODEL_DIR / "metadata.json").read_text())
        params = dict(meta["params"])
        params["seed"]            = model_seed     # XGBoost sampling seed
        params["nthread"]         = 1
        params["subsample"]       = subsample
        params["colsample_bytree"]= colsample_bytree
        params.pop("eval_metric", None)
        params["eval_metric"]     = "aucpr"

        print(f"  model_seed   : {model_seed}")
        print(f"  subsample    : {subsample}  colsample_bytree: {colsample_bytree}")

        rss_before = psutil.Process().memory_info().rss / (1024 ** 3)
        t_train = time.perf_counter()
        bst = xgb.train(params, dm_train, num_boost_round=FIXED_ROUNDS)
        train_time = time.perf_counter() - t_train
        del dm_train
        gc.collect()

        rss_after = psutil.Process().memory_info().rss / (1024 ** 3)
        peak_rss  = max(rss_before, rss_after)
        print(f"  train_time   : {train_time:.1f}s   peak_rss: {peak_rss:.2f}GB")

        # ------------------------------------------------------------------
        # Evaluate on val
        # ------------------------------------------------------------------
        X_val_df = val_tbl.select(feature_cols).to_pandas()
        X_val    = preprocessor.transform(normalize(X_val_df)).astype(np.float32)
        del X_val_df

        dm_val = xgb.DMatrix(X_val)
        preds  = bst.predict(dm_val, iteration_range=(0, FIXED_ROUNDS))
        del dm_val, X_val, bst
        gc.collect()

        pred_sha = sha256_arr(preds.astype(np.float32))
        ap    = float(average_precision_score(y_val, preds))
        auc   = float(roc_auc_score(y_val, preds))
        brier = float(brier_score_loss(y_val, preds))
        pred_std = float(preds.std())

        print(f"  pred_sha     : {pred_sha[:16]}...")
        print(f"  AP={ap:.6f}  AP-prev={ap - val_prevalence:+.6f}  "
              f"AP/prev={ap/val_prevalence:.3f}")
        print(f"  ROC-AUC={auc:.6f}  AUC-0.5={auc - 0.5:+.6f}")
        print(f"  Brier={brier:.6f}  pred_std={pred_std:.4f}")

        total_time = time.perf_counter() - t_start

        return {
            "label"               : tag,
            "perm_seed"           : perm_seed,
            "model_seed"          : model_seed,
            "subsample"           : subsample,
            "colsample_bytree"    : colsample_bytree,
            "cache_dir"           : cache_dir,
            "cache_fingerprint"   : cache_fingerprint,
            "orig_label_sha256"   : orig_sha,
            "shuf_label_sha256"   : shuf_sha,
            "perm_index_sha256"   : perm_sha,
            "feat_first5_sha256"  : feat_sha,
            "pred_sha256"         : pred_sha,
            "val_prevalence"      : round(val_prevalence, 8),
            "null_ap"             : round(ap, 8),
            "ap_minus_prevalence" : round(ap - val_prevalence, 8),
            "ap_ratio"            : round(ap / val_prevalence, 4),
            "null_roc_auc"        : round(auc, 8),
            "auc_minus_half"      : round(auc - 0.5, 8),
            "null_brier"          : round(brier, 8),
            "pred_std"            : round(pred_std, 6),
            "label_correlation"   : round(label_corr, 8),
            "train_time_s"        : round(train_time, 1),
            "total_time_s"        : round(total_time, 1),
            "peak_rss_gb"         : round(peak_rss, 3),
            "n_train"             : n_train,
            "n_val"               : n_val,
            "fixed_rounds"        : FIXED_ROUNDS,
            "b1_accessed"         : False,
            "embargo_accessed"    : False,
            "b2_accessed"         : False,
        }
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)


def fmt_cell(r: dict | None) -> str:
    if r is None:
        return "  ——   "
    return f"AP={r['null_ap']:.4f} AUC={r['null_roc_auc']:.4f}"


def main() -> None:  # noqa: C901
    print("=" * 70)
    print("PHASE 6 SEED ISOLATION EXPERIMENT")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Define all unique configurations
    # (perm=137, model=42) is shared between Part1 and Part2
    # ------------------------------------------------------------------
    CONFIGS = [
        # Part 1 — fixed model_seed=42
        {"perm_seed": 42,   "model_seed": 42,  "subsample": 0.8, "colsample_bytree": 0.8,
             "label": "part1_perm42_model42"},
        {"perm_seed": 137,  "model_seed": 42,  "subsample": 0.8, "colsample_bytree": 0.8,
             "label": "part1and2_perm137_model42"},   # shared
        {"perm_seed": 2026, "model_seed": 42,  "subsample": 0.8, "colsample_bytree": 0.8,
             "label": "part1_perm2026_model42"},
        # Part 2 — fixed perm_seed=137 (perm=137/model=42 already above)
        {"perm_seed": 137,  "model_seed": 137, "subsample": 0.8, "colsample_bytree": 0.8,
             "label": "part2_perm137_model137"},
        {"perm_seed": 137,  "model_seed": 2026, "subsample": 0.8, "colsample_bytree": 0.8,
             "label": "part2_perm137_model2026"},
        # Part 3 — diagnostic: full sampling
        {"perm_seed": 137,  "model_seed": 42,  "subsample": 1.0, "colsample_bytree": 1.0,
             "label": "part3_perm137_model42_fullsample"},
    ]

    results: dict[str, dict] = {}
    for cfg in CONFIGS:
        result = run_one(**cfg)
        results[cfg["label"]] = result

    # ------------------------------------------------------------------
    # Comparison matrices
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PART 1 — Fixed model_seed=42, varying perm_seed")
    print("=" * 70)
    print(f"  {'perm_seed':>12}  {'AP':>10}  {'AP-prev':>10}  "
          f"{'AP/prev':>8}  {'ROC-AUC':>10}  {'AUC-0.5':>8}")
    for k in ["part1_perm42_model42", "part1and2_perm137_model42",
              "part1_perm2026_model42"]:
        r = results[k]
        print(f"  {r['perm_seed']:>12}  {r['null_ap']:>10.6f}  "
              f"{r['ap_minus_prevalence']:>+10.6f}  {r['ap_ratio']:>8.3f}  "
              f"{r['null_roc_auc']:>10.6f}  {r['auc_minus_half']:>+8.6f}")

    print("\n" + "=" * 70)
    print("  PART 2 — Fixed perm_seed=137, varying model_seed")
    print("=" * 70)
    print(f"  {'model_seed':>12}  {'AP':>10}  {'AP-prev':>10}  "
          f"{'AP/prev':>8}  {'ROC-AUC':>10}  {'AUC-0.5':>8}")
    for k in ["part1and2_perm137_model42", "part2_perm137_model137",
              "part2_perm137_model2026"]:
        r = results[k]
        print(f"  {r['model_seed']:>12}  {r['null_ap']:>10.6f}  "
              f"{r['ap_minus_prevalence']:>+10.6f}  {r['ap_ratio']:>8.3f}  "
              f"{r['null_roc_auc']:>10.6f}  {r['auc_minus_half']:>+8.6f}")

    print("\n" + "=" * 70)
    print("  PART 3 — perm=137, model=42, full sampling (diagnostic)")
    print("=" * 70)
    r3 = results["part3_perm137_model42_fullsample"]
    print("  subsample=1.0, colsample_bytree=1.0")
    print(f"  AP={r3['null_ap']:.6f}  AP-prev={r3['ap_minus_prevalence']:+.6f}  "
          f"ROC-AUC={r3['null_roc_auc']:.6f}")

    print("\n" + "=" * 70)
    print("  FULL COMPARISON MATRIX (rows=perm_seed, cols=model_seed)")
    print("=" * 70)
    print(f"  {'':>12}  {'model=42':>26}  {'model=137':>26}  {'model=2026':>26}")
    matrix = {
        (42,   42):  results.get("part1_perm42_model42"),
        (137,  42):  results.get("part1and2_perm137_model42"),
        (137,  137): results.get("part2_perm137_model137"),
        (137,  2026):results.get("part2_perm137_model2026"),
        (2026, 42):  results.get("part1_perm2026_model42"),
    }
    for perm in [42, 137, 2026]:
        row = f"  perm={perm:<7}"
        for mseed in [42, 137, 2026]:
            r = matrix.get((perm, mseed))
            if r:
                row += f"  {fmt_cell(r)}"
            else:
                row += f"  {'(not run)':>26}"
        print(row)

    # Decision analysis
    print("\n" + "=" * 70)
    print("  DECISION ANALYSIS")
    print("=" * 70)
    p1_42  = results["part1_perm42_model42"]
    p1_137 = results["part1and2_perm137_model42"]
    p1_2026= results["part1_perm2026_model42"]
    p2_m42 = results["part1and2_perm137_model42"]
    p2_m137= results["part2_perm137_model137"]
    p2_m2026=results["part2_perm137_model2026"]
    p3     = results["part3_perm137_model42_fullsample"]

    # Q1: Is perm=137 elevated vs other perm seeds at fixed model=42?
    perm_effect = p1_137["null_ap"] - max(p1_42["null_ap"], p1_2026["null_ap"])
    auc_perm_effect = p1_137["null_roc_auc"] - max(p1_42["null_roc_auc"],
                                                     p1_2026["null_roc_auc"])
    print("\n  Q1: Permutation effect at fixed model_seed=42")
    print(f"    perm=137 AP elevation vs max(perm=42,2026): {perm_effect:+.6f}")
    print(f"    perm=137 AUC elevation vs max(perm=42,2026): {auc_perm_effect:+.6f}")

    # Q2: Does the anomaly follow the model seed? (perm fixed at 137)
    model_effect_137vs42  = p2_m137["null_ap"] - p2_m42["null_ap"]
    model_effect_2026vs42 = p2_m2026["null_ap"] - p2_m42["null_ap"]
    print("\n  Q2: Model-seed effect at fixed perm_seed=137")
    print(f"    AP(model=137) - AP(model=42): {model_effect_137vs42:+.6f}")
    print(f"    AP(model=2026) - AP(model=42): {model_effect_2026vs42:+.6f}")

    # Q3: Does full sampling reduce or eliminate the anomaly?
    full_vs_sub = p3["null_ap"] - p1_137["null_ap"]
    print("\n  Q3: Full-sampling diagnostic (perm=137, model=42)")
    print(f"    AP(sub=1.0) - AP(sub=0.8): {full_vs_sub:+.6f}")
    print(f"    AUC(sub=1.0)={p3['null_roc_auc']:.6f}  "
          f"AUC(sub=0.8)={p1_137['null_roc_auc']:.6f}")

    if perm_effect > 0.005:
        print("\n  FINDING: Elevated AP follows the LABEL PERMUTATION (perm_seed=137),")
        print("           not the model seed — XGBoost subsampling NOT the primary cause.")
    else:
        print("\n  FINDING: perm_seed=137 does NOT cause elevated AP at fixed model=42.")
        print("           Elevation driven by MODEL SEED (XGBoost subsampling).")

    # Official fixed-model-seed controls (Part 5 decision rule)
    official_results = [p1_42, p1_137, p1_2026]
    worst_auc = max(r["null_roc_auc"] for r in official_results)
    worst_ap  = max(r["null_ap"] for r in official_results)
    print("\n  OFFICIAL FIXED-MODEL-SEED CONTROLS (model_seed=42 for all):")
    print(f"    Max AP  = {worst_ap:.6f}   (threshold: AP/prev <= 2)")
    print(f"    Max AUC = {worst_auc:.6f}  (alert if >> 0.5)")
    gate_clear = worst_auc < 0.6 and worst_ap < 2 * p1_42["val_prevalence"]
    print(f"    Gate A clears: {gate_clear}")
    if not gate_clear:
        print("    Gate A BLOCKED — ROC-AUC or AP materially elevated")
        print("    Relevant feature groups must be investigated.")

    # ------------------------------------------------------------------
    # Write report
    # ------------------------------------------------------------------
    report = {
        "created_utc"    : datetime.now(timezone.utc).isoformat(),
        "experiment"     : "seed_isolation_parts_1_2_3",
        "val_prevalence" : round(float(p1_42["val_prevalence"]), 8),
        "runs"           : results,
        "decision"       : {
            "perm_effect_ap"        : round(perm_effect, 8),
            "perm_effect_auc"       : round(auc_perm_effect, 8),
            "model_effect_ap_137v42": round(model_effect_137vs42, 8),
            "model_effect_ap_2026v42":round(model_effect_2026vs42, 8),
            "full_sample_ap_delta"  : round(full_vs_sub, 8),
            "official_max_ap"       : round(worst_ap, 8),
            "official_max_auc"      : round(worst_auc, 8),
            "gate_a_clears"         : gate_clear,
        },
        "b1_accessed"    : False,
        "embargo_accessed": False,
        "b2_accessed"    : False,
    }

    out = _REPO_ROOT / "models/phase_6/seed_isolation_experiment.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nReport written: {out}")
    print(f"\nGate A status: {'INVESTIGATION IN PROGRESS' if not gate_clear else 'CANDIDATE FOR CLEARANCE'}")


if __name__ == "__main__":
    main()
