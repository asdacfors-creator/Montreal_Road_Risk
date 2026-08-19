"""
Phase 4 â€” Leakage-Safe Labels and Feature Engineering Pipeline

Usage:
    python build_segment_month_panel.py [options]

Options:
    --smoke-test                Run fully synthetic end-to-end smoke test (no real data)
    --benchmark-anchor YYYY-MM  Run a single real-data anchor benchmark
    --start-anchor YYYY-MM      First anchor to process (inclusive)
    --end-anchor   YYYY-MM      Last anchor to process (inclusive)
    --resume                    Skip partitions that pass integrity checks
    --verify-determinism        Re-compute and compare fingerprints
    --workers N                 Number of parallel workers (default 1; use 1 on this machine)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from montreal_road_risk.features.qa import verify_immutability
from montreal_road_risk.features.repairs import rolling_repairs_for_anchor
from montreal_road_risk.features.static import build_static_features

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config/feature_engineering.json"
CACHE_DIR = PROJECT_ROOT / "data/processed/phase_4/_cache"
PANEL_DIR = PROJECT_ROOT / "data/processed/phase_4"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _sha256_df(df: pd.DataFrame) -> str:
    row_hashes = pd.util.hash_pandas_object(df, index=True)
    return hashlib.sha256(row_hashes.values.tobytes()).hexdigest()


def _schema_fp(df: pd.DataFrame) -> str:
    return hashlib.sha256(str(df.dtypes.to_dict()).encode()).hexdigest()


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _config_fp(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def _month_end(year: int, month: int) -> pd.Timestamp:
    return pd.date_range(f"{year}-{month:02d}-01", periods=1, freq="ME")[0]


def _all_anchors(config: dict) -> list[pd.Timestamp]:
    start = pd.Timestamp(config["panel_settings"]["start_month"] + "-01")
    end   = pd.Timestamp(config["panel_settings"]["end_month"]   + "-31")
    return list(pd.date_range(start=start, end=end, freq="ME"))


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------

def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def _cache_meta_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.meta.json"


def _read_cache(name: str, source_fps: dict, config_fp: str) -> pd.DataFrame | None:
    """Return cached DataFrame if all fingerprints match, else None."""
    meta_file = _cache_meta_path(name)
    data_file = _cache_path(name)
    if not meta_file.exists() or not data_file.exists():
        return None
    try:
        meta = json.loads(meta_file.read_text())
        if meta.get("config_fp") != config_fp:
            return None
        for k, v in source_fps.items():
            if meta.get("source_fps", {}).get(k) != v:
                return None
        df = pd.read_parquet(data_file)
        if meta.get("schema_fp") != _schema_fp(df):
            return None
        if meta.get("row_count") != len(df):
            return None
        return df
    except Exception:
        return None


def _write_cache(name: str, df: pd.DataFrame, source_fps: dict, config_fp: str) -> None:
    data_file = _cache_path(name)
    tmp = data_file.with_suffix(".tmp.parquet")
    df.to_parquet(tmp, index=True)
    if data_file.exists():
        data_file.unlink()
    tmp.rename(data_file)
    meta = {
        "config_fp": config_fp,
        "source_fps": source_fps,
        "schema_fp": _schema_fp(df),
        "row_count": len(df),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _cache_meta_path(name).write_text(json.dumps(meta, indent=2))


# ---------------------------------------------------------------------------
# Precomputation (called once, results cached)
# ---------------------------------------------------------------------------

def precompute_all(config: dict, cfg_fp: str, print_prefix: str = "") -> dict:  # noqa: C901
    """
    Precomputes and caches all shared tables.
    Returns a dict of DataFrames ready for the anchor loop.
    """
    t0 = time.perf_counter()

    # --- Source fingerprints ---
    def fp(key):
        return _sha256_file(PROJECT_ROOT / config["inputs"][key])

    src_fps = {k: fp(k) for k in [
        "geobase", "boundaries", "road_boundary_links",
        "potholes", "pothole_links",
        "pavement", "pavement_links",
        "road_assets", "road_assets_links",
        "weather",
    ]}

    # ---- 1. Static segment table ----
    static_df = _read_cache("static_segments.parquet", src_fps, cfg_fp)
    if static_df is None:
        print(f"{print_prefix}Building static segment tableâ€¦")
        static_df = build_static_features(config, str(PROJECT_ROOT))
        _write_cache("static_segments.parquet", static_df, src_fps, cfg_fp)
    else:
        print(f"{print_prefix}Static segment table: cache hit ({len(static_df)} rows)")
    segments = static_df["canonical_segment_id"].tolist()

    # ---- 2. Pothole links: exclusions and accepted ----
    links_cache = _read_cache("pothole_links_full.parquet", src_fps, cfg_fp)
    if links_cache is None:
        print(f"{print_prefix}Loading pothole segment linksâ€¦")
        links_df = pd.read_parquet(PROJECT_ROOT / config["inputs"]["pothole_links"])
        _write_cache("pothole_links_full.parquet", links_df, src_fps, cfg_fp)
    else:
        links_df = links_cache

    exclusion_df = links_df[links_df["linkage_status"].isin(["unmatched", "review_required"])].copy()
    accepted_links = links_df[links_df["linkage_status"] == "accepted"].copy()
    accepted_links["canonical_segment_id"] = accepted_links["canonical_segment_id"].astype(float).astype(int).astype(str)

    # Write target exclusion audit to official output path
    ex_out = PROJECT_ROOT / config["outputs"]["target_exclusion_audit"]
    ex_out.parent.mkdir(parents=True, exist_ok=True)
    if not ex_out.exists():
        exclusion_df.to_parquet(ex_out, index=False)
        print(f"{print_prefix}Target exclusion audit written: {len(exclusion_df):,} rows")


    # ---- 3. Accepted repair events ----
    accepted_events = _read_cache("accepted_events.parquet", src_fps, cfg_fp)
    if accepted_events is None:
        print(f"{print_prefix}Building accepted repair events ledgerâ€¦")
        potholes_df = pd.read_parquet(PROJECT_ROOT / config["inputs"]["potholes"])
        potholes_df["source_row_number"] = potholes_df["source_row_number"].astype(int)
        accepted_links_int = accepted_links.copy()
        accepted_links_int["source_row_number"] = accepted_links_int["source_row_number"].astype(int)

        overlap_cols = accepted_links_int.columns.intersection(potholes_df.columns).difference(
            ["source_file", "source_row_number"]
        )
        potholes_sub = potholes_df.drop(columns=overlap_cols)
        base = accepted_links_int.merge(potholes_sub, on=["source_file", "source_row_number"], how="inner")

        parts = []
        for year, grp in base.groupby("source_year"):
            y = int(year)
            rep_path = (PROJECT_ROOT /
                f"data/interim/phase_3a/pothole_repairs/pothole_repairs_{y}_32188.parquet")
            rep = pd.read_parquet(rep_path, columns=["source_record_number",
                                                       "vehicle_id_raw", "latitude_raw", "longitude_raw"])
            m = grp.merge(rep, left_on="source_row_number",
                          right_on="source_record_number", how="inner").drop(columns=["source_record_number"])
            for c in ["vehicle_id_raw", "event_timestamp_raw", "event_date_raw", "event_time_raw"]:
                if c in m.columns:
                    m[c] = m[c].astype(str)
            for c in ["latitude_raw", "longitude_raw"]:
                if c in m.columns:
                    m[c] = m[c].astype(float)
            parts.append(m)
        accepted_events = pd.concat(parts, ignore_index=True)
        accepted_events["event_timestamp_naive"] = pd.to_datetime(
            accepted_events["event_timestamp_naive"], errors="coerce"
        )
        _write_cache("accepted_events.parquet", accepted_events, src_fps, cfg_fp)
    else:
        accepted_events["event_timestamp_naive"] = pd.to_datetime(
            accepted_events["event_timestamp_naive"], errors="coerce"
        )
        print(f"{print_prefix}Accepted events: cache hit ({len(accepted_events)} rows)")

    # Write raw events ledger to official output path if missing
    raw_out = PROJECT_ROOT / config["outputs"]["accepted_repair_events_raw"]
    if not raw_out.exists():
        raw_out.parent.mkdir(parents=True, exist_ok=True)
        accepted_events.to_parquet(raw_out, index=False)

    # ---- 4. Collapsed events (inlined — does not require a pre-existing raw output file) ----
    collapsed_events = _read_cache("collapsed_events.parquet", src_fps, cfg_fp)
    dup_membership = _read_cache("dup_membership.parquet", src_fps, cfg_fp)
    if collapsed_events is None:
        print(f"{print_prefix}Building duplicate-collapsed events (inline)…")

        # Write raw events ledger to official output path for downstream compatibility
        raw_out = PROJECT_ROOT / config["outputs"]["accepted_repair_events_raw"]
        raw_out.parent.mkdir(parents=True, exist_ok=True)
        accepted_events.to_parquet(raw_out, index=False)

        # Fill native key fields used for deduplication
        ae = accepted_events.copy()
        for c in ["vehicle_id_raw"]:
            if c in ae.columns:
                ae[c] = ae[c].fillna("UNKNOWN")
        for c in ["latitude_raw", "longitude_raw"]:
            if c in ae.columns:
                ae[c] = pd.to_numeric(ae[c], errors="coerce").fillna(0.0)

        def _dup_key(row):
            vehicle = str(row.get("vehicle_id_raw", "UNKNOWN"))
            lat = float(row.get("latitude_raw", 0.0))
            lon = float(row.get("longitude_raw", 0.0))
            sf  = str(row.get("source_file", ""))
            if sf.endswith(".gpkg"):
                return (sf, vehicle, str(row.get("event_timestamp_raw", "")), lon, lat)
            return (sf, vehicle, str(row.get("event_date_raw", "")),
                    str(row.get("event_time_raw", "")), lat, lon)

        ae["dup_group_key"] = ae.apply(_dup_key, axis=1)
        grouped_keys = ae["dup_group_key"].unique()
        group_map = {k: f"dup_group_{i}" for i, k in enumerate(grouped_keys)}
        ae["duplicate_group_id"] = ae["dup_group_key"].map(group_map)
        ae["duplicate_multiplicity"] = ae["duplicate_group_id"].map(
            ae["duplicate_group_id"].value_counts()
        )

        membership_cols = [c for c in [
            "source_file", "source_row_number",
            "duplicate_group_id", "duplicate_multiplicity",
            "canonical_segment_id",
        ] if c in ae.columns]
        dup_membership = ae[membership_cols].copy()

        collapsed_events = ae.drop_duplicates(
            subset=["duplicate_group_id"], keep="first"
        ).drop(columns=["dup_group_key"]).copy()

        # Write to official output paths
        col_path = PROJECT_ROOT / config["outputs"]["accepted_repair_events_collapsed"]
        mem_path = PROJECT_ROOT / config["outputs"]["duplicate_group_membership"]
        dup_path = PROJECT_ROOT / config["outputs"]["duplicate_sensitivity_summary"]
        col_path.parent.mkdir(parents=True, exist_ok=True)
        collapsed_events.drop(columns=["duplicate_group_id", "duplicate_multiplicity"],
                               errors="ignore").to_parquet(col_path, index=False)
        dup_membership.to_parquet(mem_path, index=False)

        import json as _json
        dup_summary = {
            "total_raw_accepted_events": len(ae),
            "total_collapsed_events": len(collapsed_events),
            "duplicate_events_removed": len(ae) - len(collapsed_events),
            "multiplicity_distribution": {
                str(k): int(v)
                for k, v in ae["duplicate_multiplicity"].value_counts().items()
            },
        }
        dup_path.write_text(_json.dumps(dup_summary, indent=2))

        _write_cache("collapsed_events.parquet", collapsed_events, src_fps, cfg_fp)
        _write_cache("dup_membership.parquet", dup_membership, src_fps, cfg_fp)
        print(f"{print_prefix}Collapsed: {len(collapsed_events):,} events "
              f"(from {len(ae):,} raw)")
    else:
        print(f"{print_prefix}Collapsed events: cache hit ({len(collapsed_events)} rows)")
        col_path = PROJECT_ROOT / config["outputs"]["accepted_repair_events_collapsed"]
        mem_path = PROJECT_ROOT / config["outputs"]["duplicate_group_membership"]
        dup_path = PROJECT_ROOT / config["outputs"]["duplicate_sensitivity_summary"]
        col_path.parent.mkdir(parents=True, exist_ok=True)
        if not col_path.exists():
            collapsed_events.drop(columns=["duplicate_group_id", "duplicate_multiplicity"],
                                   errors="ignore").to_parquet(col_path, index=False)
        if not mem_path.exists():
            dup_membership.to_parquet(mem_path, index=False)
        if not dup_path.exists():
            import json as _json
            dup_summary = {
                "total_raw_accepted_events": len(accepted_events),
                "total_collapsed_events": len(collapsed_events),
                "duplicate_events_removed": len(accepted_events) - len(collapsed_events),
                "multiplicity_distribution": {
                    str(k): int(v)
                    for k, v in dup_membership["duplicate_multiplicity"].value_counts().items()
                } if "duplicate_multiplicity" in dup_membership.columns else {}
            }
            dup_path.write_text(_json.dumps(dup_summary, indent=2))

    collapsed_events["event_timestamp_naive"] = pd.to_datetime(
        collapsed_events["event_timestamp_naive"], errors="coerce"
    )
    accepted_events["event_date"] = accepted_events["event_timestamp_naive"].dt.date
    collapsed_events["event_date"] = collapsed_events["event_timestamp_naive"].dt.date

    # ---- 5. Pre-aggregate repair counts by (segment, date) ----
    print(f"{print_prefix}Pre-aggregating segment-day repair countsâ€¦")
    raw_daily = (
        accepted_events.dropna(subset=["event_timestamp_naive"])
        .groupby(["canonical_segment_id", "event_date"])
        .size()
        .rename("raw_count")
        .reset_index()
    )
    raw_daily["event_date"] = pd.to_datetime(raw_daily["event_date"])
    raw_daily = raw_daily.sort_values("event_date").reset_index(drop=True)

    col_daily = (
        collapsed_events.dropna(subset=["event_timestamp_naive"])
        .groupby(["canonical_segment_id", "event_date"])
        .size()
        .rename("col_count")
        .reset_index()
    )
    col_daily["event_date"] = pd.to_datetime(col_daily["event_date"])
    col_daily = col_daily.sort_values("event_date").reset_index(drop=True)

    # Last repair date per segment (all time)
    last_repair_all = (
        accepted_events.dropna(subset=["event_timestamp_naive"])
        .groupby("canonical_segment_id")["event_timestamp_naive"]
        .max()
        .rename("last_repair_dt")
    )

    # ---- 6. Anchor weather table (102 rows) ----
    anchor_weather = _read_cache("anchor_weather.parquet", src_fps, cfg_fp)
    if anchor_weather is None:
        print(f"{print_prefix}Building anchor weather tableâ€¦")
        wdf = pd.read_parquet(PROJECT_ROOT / config["inputs"]["weather"])
        anchor_weather = _build_anchor_weather_table(config, wdf, _all_anchors(config))
        _write_cache("anchor_weather.parquet", anchor_weather, src_fps, cfg_fp)
    else:
        print(f"{print_prefix}Anchor weather table: cache hit ({len(anchor_weather)} rows)")
    anchor_weather["as_of_date"] = pd.to_datetime(anchor_weather["as_of_date"])

    # ---- 7. Pavement condition (normalized once) ----
    pavement_grouped = _read_cache("pavement_grouped.parquet", src_fps, cfg_fp)
    if pavement_grouped is None:
        print(f"{print_prefix}Normalising pavement condition surveysâ€¦")
        pavement_grouped = _build_pavement_grouped(config)
        _write_cache("pavement_grouped.parquet", pavement_grouped, src_fps, cfg_fp)
    else:
        print(f"{print_prefix}Pavement grouped: cache hit ({len(pavement_grouped)} rows)")
    pavement_grouped["survey_date"] = pd.to_datetime(pavement_grouped["survey_date"])

    # ---- 8. Road assets (normalized once) ----
    assets_sub = _read_cache("assets_sub.parquet", src_fps, cfg_fp)
    if assets_sub is None:
        print(f"{print_prefix}Normalising road assetsâ€¦")
        assets_sub = _build_assets_sub(config)
        _write_cache("assets_sub.parquet", assets_sub, src_fps, cfg_fp)
    else:
        print(f"{print_prefix}Road assets: cache hit ({len(assets_sub)} rows)")
    for c in ["construction_date_lower_bound", "construction_date_upper_bound",
              "resurfacing_date_lower_bound", "resurfacing_date_upper_bound"]:
        assets_sub[c] = pd.to_datetime(assets_sub[c], errors="coerce")

    # ---- 9. Outcome anchor eligibility table ----
    elig_path = PANEL_DIR / "outcome_anchor_eligibility_by_policy.csv"
    if not elig_path.exists():
        anchors = _all_anchors(config)
        elig_rows = _build_eligibility_table(anchors)
        elig_df = pd.DataFrame(elig_rows)
        elig_path.parent.mkdir(parents=True, exist_ok=True)
        elig_df.to_csv(elig_path, index=False)

    elapsed = time.perf_counter() - t0
    print(f"{print_prefix}Precomputation complete in {elapsed:.1f}s")

    return {
        "static_df": static_df,
        "segments": segments,
        "exclusion_df": exclusion_df,
        "accepted_events": accepted_events,
        "collapsed_events": collapsed_events,
        "dup_membership": dup_membership,
        "raw_daily": raw_daily,
        "col_daily": col_daily,
        "last_repair_all": last_repair_all,
        "anchor_weather": anchor_weather,
        "pavement_grouped": pavement_grouped,
        "assets_sub": assets_sub,
        "precompute_elapsed": elapsed,
    }


# ---------------------------------------------------------------------------
# Anchor weather (102 rows, computed once, broadcast per partition)
# ---------------------------------------------------------------------------

def _build_anchor_weather_table(config: dict, wdf: pd.DataFrame,
                                 anchors: list[pd.Timestamp]) -> pd.DataFrame:
    wdf = wdf.copy()
    wdf["date"] = pd.to_datetime(wdf["date"])
    wdf = wdf.set_index("date").sort_index()

    for c in ["mean_temp", "min_temp", "max_temp", "total_precip"]:
        wdf[c] = pd.to_numeric(wdf[c], errors="coerce")
    for c in ["mean_temp_fallback_used", "min_temp_fallback_used",
              "max_temp_fallback_used", "total_precip_fallback_used"]:
        if c in wdf.columns:
            wdf[c] = pd.to_numeric(wdf[c], errors="coerce").fillna(0).astype(int)

    wdf["ft_strict"] = ((wdf["min_temp"] < 0) & (wdf["max_temp"] > 0)).astype(float)
    wdf["ft_min_le"] = ((wdf["min_temp"] <= 0) & (wdf["max_temp"] > 0)).astype(float)
    wdf["ft_max_ge"] = ((wdf["min_temp"] < 0) & (wdf["max_temp"] >= 0)).astype(float)
    null_mask = wdf["min_temp"].isna() | wdf["max_temp"].isna()
    wdf.loc[null_mask, ["ft_strict", "ft_min_le", "ft_max_ge"]] = np.nan

    rows = []
    windows = config["features"]["weather_rolling_windows"]
    first_obs = pd.Timestamp("2016-12-07")

    for t in anchors:
        row: dict = {"as_of_date": t}
        for W in windows:
            w_start = t - pd.Timedelta(days=W)
            window_df = wdf.loc[w_start + pd.Timedelta(days=1): t]

            row[f"total_precip_sum_{W}d"]         = window_df["total_precip"].sum(min_count=1)
            row[f"mean_temp_mean_{W}d"]            = window_df["mean_temp"].mean()
            row[f"min_temp_min_{W}d"]              = window_df["min_temp"].min()
            row[f"max_temp_max_{W}d"]              = window_df["max_temp"].max()
            row[f"freeze_thaw_strict_sum_{W}d"]    = window_df["ft_strict"].sum(min_count=1)
            row[f"freeze_thaw_min_le_zero_sum_{W}d"] = window_df["ft_min_le"].sum(min_count=1)
            row[f"freeze_thaw_max_ge_zero_sum_{W}d"] = window_df["ft_max_ge"].sum(min_count=1)

            valid = int(window_df["total_precip"].notna().sum())
            total = W
            window_days = pd.date_range(w_start + pd.Timedelta(days=1), t)
            valid_obs = int(sum(d >= first_obs for d in window_days))
            row[f"weather_valid_days_{W}d"]        = valid
            row[f"weather_coverage_ratio_{W}d"]    = float(valid_obs) / total
            row[f"weather_complete_{W}d"]          = int(float(valid_obs) / total == 1.0)
            for fb in ["mean_temp", "min_temp", "max_temp", "total_precip"]:
                col = f"{fb}_fallback_used"
                row[f"{fb}_fallback_days_{W}d"] = (
                    int(window_df[col].sum()) if col in wdf.columns else 0
                )
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Pavement normalised table
# ---------------------------------------------------------------------------

def _build_pavement_grouped(config: dict) -> pd.DataFrame:
    pav = pd.read_parquet(PROJECT_ROOT / config["inputs"]["pavement"])
    acc = pav[pav["linkage_status"].isin(["direct_id", "spatial_fallback"])].copy()
    acc["canonical_segment_id"] = acc["canonical_segment_id"].astype(float).astype(int).astype(str)
    acc["survey_date"] = pd.to_datetime(acc["survey_date"])
    acc["pci_raw"] = pd.to_numeric(acc["pci_raw"], errors="coerce")
    acc["iri_raw"] = pd.to_numeric(acc["iri_raw"], errors="coerce")

    def _scope(lbl):
        lbl = str(lbl).strip()
        if lbl in ["2018", "2024"]:
            return "arterial"
        if lbl == "2022":
            return "local"
        if lbl in ["2010", "2015", "2020"]:
            return "mixed_or_citywide"
        return "unknown"

    acc["condition_campaign_scope"] = acc["campaign_label"].apply(_scope)

    grouped = (
        acc.groupby(["canonical_segment_id", "survey_date"])
        .agg(
            latest_pci=("pci_raw", "median"),
            pci_min=("pci_raw", "min"),
            pci_max=("pci_raw", "max"),
            pci_std=("pci_raw", lambda x: float(np.std(x)) if len(x) > 1 else 0.0),
            latest_iri=("iri_raw", "median"),
            iri_min=("iri_raw", "min"),
            iri_max=("iri_raw", "max"),
            iri_std=("iri_raw", lambda x: float(np.std(x)) if len(x) > 1 else 0.0),
            condition_candidate_count=("pci_raw", "count"),
            condition_campaign_scope=("condition_campaign_scope", "first"),
        )
        .reset_index()
        .sort_values("survey_date")
    )
    grouped["survey_date"] = grouped["survey_date"].astype("datetime64[ns]")
    return grouped


# ---------------------------------------------------------------------------
# Road assets normalised table
# ---------------------------------------------------------------------------

def _build_assets_sub(config: dict) -> pd.DataFrame:
    assets = pd.read_parquet(PROJECT_ROOT / config["inputs"]["road_assets"])
    cross  = pd.read_parquet(PROJECT_ROOT / config["inputs"]["road_assets_links"])
    acc    = cross[cross["linkage_status"] == "accepted"].copy()
    acc["canonical_segment_id"] = acc["canonical_segment_id"].astype(float).astype(int).astype(str)
    acc["primary_asset_id"]     = acc["primary_asset_id"].astype(float).astype(int).astype(str)
    assets["source_record_number"] = assets["source_record_number"].astype(float).astype(int).astype(str)

    merged = acc.merge(assets, left_on="primary_asset_id", right_on="source_record_number", how="inner")
    cols = [
        "canonical_segment_id",
        "construction_date_lower_bound", "construction_date_upper_bound",
        "resurfacing_date_lower_bound",  "resurfacing_date_upper_bound",
        "resurfacing_before_construction_candidate_flag",
        "date_contradiction_status",
    ]
    sub = merged[[c for c in cols if c in merged.columns]].copy()
    for c in ["construction_date_lower_bound", "construction_date_upper_bound",
              "resurfacing_date_lower_bound", "resurfacing_date_upper_bound"]:
        if c in sub.columns:
            sub[c] = pd.to_datetime(sub[c], errors="coerce")
    return sub


# ---------------------------------------------------------------------------
# Eligibility table
# ---------------------------------------------------------------------------

def _build_eligibility_table(anchors: list[pd.Timestamp]) -> list[dict]:
    rows = []
    for t in anchors:
        for policy in ["strict_verified_completeness", "published_resource_observation_universe"]:
            for horizon in [90, 180]:
                eligible = 1 if policy == "published_resource_observation_universe" else 0
                rows.append({
                    "as_of_date": t.strftime("%Y-%m-%d"),
                    "coverage_policy": policy,
                    "horizon_days": horizon,
                    "eligible_flag": eligible,
                    "evidence_reference": "L2.2 / L2.4" if policy == "published_resource_observation_universe"
                                         else "strict_policy_no_verified_complete_year",
                })
    return rows


# ---------------------------------------------------------------------------
# Vectorised rolling repair features (pre-aggregated daily totals)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Vectorised rolling repair features (pre-aggregated daily totals)
# ---------------------------------------------------------------------------
# (rolling_repairs_for_anchor is imported from montreal_road_risk.features.repairs)


# ---------------------------------------------------------------------------
# Pavement as-of join for anchor
# ---------------------------------------------------------------------------

def _pavement_asof(t: pd.Timestamp, segments: list[str],
                   pavement_grouped: pd.DataFrame) -> pd.DataFrame:
    valid_pav = pavement_grouped[pavement_grouped["survey_date"] <= t]
    latest = (
        valid_pav.sort_values("survey_date")
        .drop_duplicates(subset=["canonical_segment_id"], keep="last")
    )
    base = pd.DataFrame({"canonical_segment_id": segments})
    merged = base.merge(latest, on="canonical_segment_id", how="left")
    merged["condition_missing_flag"] = merged["survey_date"].isna().astype(int)
    merged["days_since_condition_survey"] = (t - merged["survey_date"]).dt.days
    merged["latest_condition_survey_date"] = (
        merged["survey_date"].dt.strftime("%Y-%m-%d").fillna("None")
    )
    merged["condition_campaign_scope"] = merged["condition_campaign_scope"].fillna("unknown")
    merged["condition_candidate_count"] = merged["condition_candidate_count"].fillna(0).astype(int)
    return merged.drop(columns=["survey_date"])


# ---------------------------------------------------------------------------
# Road asset temporal availability for anchor
# ---------------------------------------------------------------------------

def _assets_for_anchor(t: pd.Timestamp, segments: list[str],
                        assets_sub: pd.DataFrame) -> pd.DataFrame:
    base = pd.DataFrame({"canonical_segment_id": segments})
    merged = base.merge(assets_sub, on="canonical_segment_id", how="left")

    t_arr  = pd.Timestamp(t)
    c_lo   = merged["construction_date_lower_bound"]
    c_hi   = merged["construction_date_upper_bound"]
    r_lo   = merged["resurfacing_date_lower_bound"]
    r_hi   = merged["resurfacing_date_upper_bound"]

    has_c  = c_lo.notna() & c_hi.notna()
    has_r  = r_lo.notna() & r_hi.notna()
    c_fut  = has_c & (c_lo > t_arr)
    c_xing = has_c & (c_lo <= t_arr) & (t_arr < c_hi)
    c_act  = has_c & (c_hi <= t_arr)
    r_xing = has_r & (r_lo <= t_arr) & (t_arr < r_hi)
    r_act  = has_r & (r_hi <= t_arr)

    merged["years_since_construction_lower"] = np.where(
        c_act, (t_arr - c_hi).dt.days / 365.25, np.nan)
    merged["years_since_construction_upper"] = np.where(
        c_act, (t_arr - c_lo).dt.days / 365.25, np.nan)
    merged["years_since_resurfacing_lower"]  = np.where(
        r_act, (t_arr - r_hi).dt.days / 365.25, np.nan)
    merged["years_since_resurfacing_upper"]  = np.where(
        r_act, (t_arr - r_lo).dt.days / 365.25, np.nan)

    merged["future_asset_record_hidden_flag"]         = c_fut.astype(int)
    merged["age_interval_crosses_as_of_flag"]         = c_xing.astype(int)
    merged["resurfacing_interval_crosses_as_of_flag"] = r_xing.astype(int)

    merged["asset_temporal_eligibility_status"] = np.select(
        [c_act, c_xing, c_fut], ["active", "crosses", "future"], default="missing"
    )
    if "resurfacing_before_construction_candidate_flag" in merged.columns:
        merged["resurfacing_before_construction_candidate_flag"] = (
            merged["resurfacing_before_construction_candidate_flag"].fillna(0).astype(int)
        )
    if "date_contradiction_status" in merged.columns:
        merged["date_contradiction_status"] = (
            merged["date_contradiction_status"].fillna("no_contradiction").astype(str)
        )

    return merged.drop(columns=[
        "construction_date_lower_bound", "construction_date_upper_bound",
        "resurfacing_date_lower_bound",  "resurfacing_date_upper_bound",
    ], errors="ignore")


# ---------------------------------------------------------------------------
# Build one anchor partition
# ---------------------------------------------------------------------------

def _build_anchor_partition(  # noqa: C901
    t: pd.Timestamp,
    shared: dict,
    config: dict,
    out_dir: Path,
    smoke_test: bool = False,
    timing: dict | None = None,
) -> dict:
    t0 = time.perf_counter()
    segments      = shared["segments"]
    static_df     = shared["static_df"]
    shared["raw_daily"]
    shared["col_daily"]
    anchor_weather= shared["anchor_weather"]
    pavement_grouped = shared["pavement_grouped"]
    assets_sub    = shared["assets_sub"]
    accepted_events = shared["accepted_events"]

    year_str  = str(t.year)
    month_str = f"{t.month:02d}"
    a_key     = f"{year_str}-{month_str}"
    first_obs = pd.Timestamp("2016-12-07")
    windows   = config["features"]["historical_repair_windows"]

    # 1. Base frame
    anchor_df = pd.DataFrame({
        "canonical_segment_id": segments,
        "as_of_date": t,
        "panel_year":  np.int32(t.year),
        "panel_month": np.int32(t.month),
    })
    anchor_df["segment_month_id"] = anchor_df["canonical_segment_id"] + f"_{a_key}"
    anchor_df = anchor_df.set_index("segment_month_id", drop=False)

    # 2. Static attributes
    anchor_df = anchor_df.merge(static_df, on="canonical_segment_id", how="left")
    anchor_df = anchor_df.set_index("segment_month_id", drop=False)

    # 3. Targets (vectorised - ONLY for non-sealed anchors t < 2024-01-01)
    is_sealed = (t >= pd.Timestamp("2024-01-01"))
    if not is_sealed:
        t1_target = time.perf_counter()
        ev_hist = accepted_events[accepted_events["event_timestamp_naive"].notna()]
        w90_end  = t + pd.Timedelta(days=90)
        w180_end = t + pd.Timedelta(days=180)
        segs_90  = set(ev_hist[(ev_hist["event_timestamp_naive"] > t) &
                                (ev_hist["event_timestamp_naive"] <= w90_end)]["canonical_segment_id"])
        segs_180 = set(ev_hist[(ev_hist["event_timestamp_naive"] > t) &
                                (ev_hist["event_timestamp_naive"] <= w180_end)]["canonical_segment_id"])

        anchor_df["target_eligible_90d"]  = 1
        anchor_df["target_repair_90d"]    = anchor_df["canonical_segment_id"].isin(segs_90).astype(int)
        anchor_df["target_eligible_180d"] = 1
        anchor_df["target_repair_180d"]   = anchor_df["canonical_segment_id"].isin(segs_180).astype(int)
        anchor_df["target_repair_90d_strict"]  = np.nan
        anchor_df["target_repair_180d_strict"] = np.nan
        anchor_df["positive_observed_in_incomplete_window_90d"]  = 0
        anchor_df["positive_observed_in_incomplete_window_180d"] = 0
        if timing:
            timing["target"] = time.perf_counter() - t1_target

    # 4. Historical repair features (pre-aggregated, vectorised)
    t1_rep = time.perf_counter()
    rep_df = rolling_repairs_for_anchor(
        t, segments, shared["raw_daily"], shared["col_daily"],
        shared["last_repair_all"], windows, first_obs
    )
    anchor_df = anchor_df.merge(rep_df.drop(columns=[], errors="ignore"),
                                on="canonical_segment_id", how="left")
    anchor_df = anchor_df.set_index("segment_month_id", drop=False)
    if timing:
        timing["repairs"] = time.perf_counter() - t1_rep

    # 5. Weather (broadcast single anchor row)
    t1_wx = time.perf_counter()
    wx_row = anchor_weather[anchor_weather["as_of_date"] == t]
    if len(wx_row) == 1:
        wx_dict = wx_row.iloc[0].drop("as_of_date").to_dict()
        for k, v in wx_dict.items():
            anchor_df[k] = v
    if timing:
        timing["weather"] = time.perf_counter() - t1_wx

    # 6. Pavement as-of join
    t1_pav = time.perf_counter()
    pav_df = _pavement_asof(t, segments, pavement_grouped)
    anchor_df = anchor_df.merge(pav_df, on="canonical_segment_id", how="left")
    anchor_df = anchor_df.set_index("segment_month_id", drop=False)
    if timing:
        timing["pavement"] = time.perf_counter() - t1_pav

    # 7. Road asset temporal availability
    t1_ass = time.perf_counter()
    ass_df = _assets_for_anchor(t, segments, assets_sub)
    anchor_df = anchor_df.merge(ass_df, on="canonical_segment_id", how="left")
    anchor_df = anchor_df.set_index("segment_month_id", drop=False)
    if timing:
        timing["assets"] = time.perf_counter() - t1_ass

    # 8. Sort
    anchor_df = anchor_df.sort_values("canonical_segment_id")

    # 9. Write partition atomically
    t1_io = time.perf_counter()
    part_dir = out_dir / f"panel_year={year_str}" / f"panel_month={month_str}"
    part_dir.mkdir(parents=True, exist_ok=True)
    tmp_path   = part_dir / "segment_month_temp.parquet"
    final_path = part_dir / "segment_month.parquet"
    anchor_df.to_parquet(tmp_path, index=True)

    # 10. Read back and validate
    rb = pd.read_parquet(tmp_path)
    n = len(rb)
    expected = len(segments)
    assert n == expected, f"Row count mismatch: expected {expected}, got {n}"
    assert rb["segment_month_id"].is_unique, "Duplicate segment_month_id detected"
    as_of_vals = pd.to_datetime(rb["as_of_date"].unique())
    assert len(as_of_vals) == 1 and as_of_vals[0] == t, "as_of_date mismatch"
    if not smoke_test and not is_sealed:
        assert rb["target_repair_90d_strict"].isna().all(), "Strict targets must be null"
    if timing:
        timing["io"] = time.perf_counter() - t1_io

    # 11. Fingerprint
    t1_fp = time.perf_counter()
    row_hashes = pd.util.hash_pandas_object(rb, index=True)
    fingerprint = hashlib.sha256(row_hashes.values.tobytes()).hexdigest()
    schema_fp   = _schema_fp(rb)
    if timing:
        timing["fingerprint"] = time.perf_counter() - t1_fp

    # 12. Atomic rename
    if final_path.exists():
        final_path.unlink()
    tmp_path.rename(final_path)

    total_elapsed = time.perf_counter() - t0
    if timing:
        timing["total_partition"] = total_elapsed

    return {
        "anchor": a_key,
        "output_path": str(final_path).replace("\\", "/"),
        "row_count": n,
        "schema_fingerprint": schema_fp,
        "sorted-content SHA-256 fingerprint": fingerprint,
        "target_eligible_90d_count": int(rb["target_eligible_90d"].sum()) if "target_eligible_90d" in rb.columns else 0,
        "target_eligible_180d_count": int(rb["target_eligible_180d"].sum()) if "target_eligible_180d" in rb.columns else 0,
        "target_repair_90d_strict_null_count": int(rb["target_repair_90d_strict"].isna().sum()) if "target_repair_90d_strict" in rb.columns else len(rb),
        "target_repair_180d_strict_null_count": int(rb["target_repair_180d_strict"].isna().sum()) if "target_repair_180d_strict" in rb.columns else len(rb),
        "completion_status": "success",
        "completion_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Synthetic smoke test (Part 5 â€” no real data)
# ---------------------------------------------------------------------------

def run_synthetic_smoke_test() -> None:  # noqa: C901
    t0 = time.perf_counter()
    print("=== Synthetic Smoke Test (no real data) ===")

    # ---- Fixtures ----
    SEG_IDS = [f"S{i:04d}" for i in range(1, 11)]  # S0001..S0010
    ANCHORS = [
        pd.Timestamp("2018-01-31"),
        pd.Timestamp("2018-02-28"),
        pd.Timestamp("2018-03-31"),
    ]
    UNMATCHED_SEG = "S0010"  # unmatched administrative segment (verified: 4017818 pattern)

    # ---- Accepted events: 1 accepted, 1 unmatched, 1 review-required ----
    pothole_events = pd.DataFrame([
        # accepted repair on S0001 on 2018-01-15 (inside anchor 2018-01)
        {"canonical_segment_id": "S0001", "linkage_status": "accepted",
         "event_timestamp_naive": pd.Timestamp("2018-01-15"),
         "event_date": pd.Timestamp("2018-01-15").date(), "source_year": 2018},
        # duplicate accepted repair on S0001 same day (native duplicate group)
        {"canonical_segment_id": "S0001", "linkage_status": "accepted",
         "event_timestamp_naive": pd.Timestamp("2018-01-15"),
         "event_date": pd.Timestamp("2018-01-15").date(), "source_year": 2018},
        # out-of-year mismatch: belongs to 2017 source but event is in 2018
        {"canonical_segment_id": "S0002", "linkage_status": "accepted",
         "event_timestamp_naive": pd.Timestamp("2018-01-20"),
         "event_date": pd.Timestamp("2018-01-20").date(), "source_year": 2017},
        # unmatched
        {"canonical_segment_id": None, "linkage_status": "unmatched",
         "event_timestamp_naive": pd.Timestamp("2018-01-10"),
         "event_date": pd.Timestamp("2018-01-10").date(), "source_year": 2018},
        # review_required
        {"canonical_segment_id": None, "linkage_status": "review_required",
         "event_timestamp_naive": pd.Timestamp("2018-01-12"),
         "event_date": pd.Timestamp("2018-01-12").date(), "source_year": 2018},
    ])
    accepted_events = pothole_events[pothole_events["linkage_status"] == "accepted"].copy()
    exclusion_df    = pothole_events[
        pothole_events["linkage_status"].isin(["unmatched", "review_required"])
    ].copy()

    assert len(exclusion_df) == 2, "Expected 2 exclusion events"

    # ---- Collapsed events (native duplicate collapsed to 1) ----
    collapsed_events = accepted_events.drop_duplicates(
        subset=["canonical_segment_id", "event_date"]
    ).copy()
    assert len(collapsed_events) == 2  # S0001 once + S0002 once

    # ---- Pre-aggregate daily counts ----
    raw_daily = (
        accepted_events.groupby(["canonical_segment_id", "event_date"])
        .size().rename("raw_count").reset_index()
    )
    raw_daily["event_date"] = pd.to_datetime(raw_daily["event_date"])
    col_daily = (
        collapsed_events.groupby(["canonical_segment_id", "event_date"])
        .size().rename("col_count").reset_index()
    )
    col_daily["event_date"] = pd.to_datetime(col_daily["event_date"])
    last_repair_all = (
        accepted_events.groupby("canonical_segment_id")["event_timestamp_naive"]
        .max().rename("last_repair_dt")
    )

    # ---- Static segment table ----
    static_df = pd.DataFrame({
        "canonical_segment_id": SEG_IDS,
        "functional_road_class": ["arterial"] * 10,
        "official_administrative_name": ["TestBorough"] * 9 + ["Unmatched"],
        "unmatched_boundary_flag": [0] * 9 + [1],
    })

    # ---- Synthetic weather (daily for Janâ€“Mar 2018) ----
    dates = pd.date_range("2017-06-01", "2018-03-31")
    rng   = np.random.default_rng(42)
    weather_df = pd.DataFrame({
        "date": dates,
        "mean_temp":    rng.uniform(-10, 15, len(dates)),
        "min_temp":     rng.uniform(-15, 5,  len(dates)),
        "max_temp":     rng.uniform(0,   20, len(dates)),
        "total_precip": rng.uniform(0,   10, len(dates)),
    })
    weather_df["date"] = pd.to_datetime(weather_df["date"])
    weather_df = weather_df.set_index("date").sort_index()

    # Compute anchor weather table for 3 anchors
    anchor_weather_rows = []
    for t in ANCHORS:
        row: dict = {"as_of_date": t}
        for W in [30, 90]:
            w_start = t - pd.Timedelta(days=W)
            sub = weather_df.loc[w_start + pd.Timedelta(days=1): t]
            row[f"total_precip_sum_{W}d"]  = sub["total_precip"].sum()
            row[f"mean_temp_mean_{W}d"]    = sub["mean_temp"].mean()
            row[f"min_temp_min_{W}d"]      = sub["min_temp"].min()
            row[f"max_temp_max_{W}d"]      = sub["max_temp"].max()
            row[f"freeze_thaw_strict_sum_{W}d"] = float(
                ((sub["min_temp"] < 0) & (sub["max_temp"] > 0)).sum()
            )
            row[f"freeze_thaw_min_le_zero_sum_{W}d"] = float(
                ((sub["min_temp"] <= 0) & (sub["max_temp"] > 0)).sum()
            )
            row[f"freeze_thaw_max_ge_zero_sum_{W}d"] = float(
                ((sub["min_temp"] < 0) & (sub["max_temp"] >= 0)).sum()
            )
            valid = int(sub["total_precip"].notna().sum())
            row[f"weather_valid_days_{W}d"]      = valid
            row[f"weather_coverage_ratio_{W}d"]  = float(valid) / W
            row[f"weather_complete_{W}d"]         = int(float(valid) / W == 1.0)
            for fb in ["mean_temp", "min_temp", "max_temp", "total_precip"]:
                row[f"{fb}_fallback_days_{W}d"] = 0
        anchor_weather_rows.append(row)
    anchor_weather = pd.DataFrame(anchor_weather_rows)
    anchor_weather["as_of_date"] = pd.to_datetime(anchor_weather["as_of_date"])

    # ---- Synthetic pavement surveys ----
    # Survey before anchor 2018-01-31: should be visible at that anchor
    # Survey after anchor 2018-01-31: must NOT be visible at 2018-01-31
    # Same-day duplicate surveys on S0003: median must be used
    pavement_grouped = pd.DataFrame([
        {"canonical_segment_id": "S0001", "survey_date": pd.Timestamp("2017-06-01"),
         "latest_pci": 65.0, "pci_min": 65.0, "pci_max": 65.0, "pci_std": 0.0,
         "latest_iri": 2.0,  "iri_min": 2.0,  "iri_max": 2.0,  "iri_std": 0.0,
         "condition_candidate_count": 1, "condition_campaign_scope": "arterial"},
        {"canonical_segment_id": "S0002", "survey_date": pd.Timestamp("2018-04-01"),
         "latest_pci": 70.0, "pci_min": 70.0, "pci_max": 70.0, "pci_std": 0.0,
         "latest_iri": 1.5,  "iri_min": 1.5,  "iri_max": 1.5,  "iri_std": 0.0,
         "condition_candidate_count": 1, "condition_campaign_scope": "arterial"},
        # same-day duplicates already resolved to median in real pipeline
        {"canonical_segment_id": "S0003", "survey_date": pd.Timestamp("2017-12-15"),
         "latest_pci": 75.0, "pci_min": 60.0, "pci_max": 90.0, "pci_std": 15.0,
         "latest_iri": 1.8,  "iri_min": 1.2,  "iri_max": 2.4,  "iri_std": 0.6,
         "condition_candidate_count": 2, "condition_campaign_scope": "local"},
    ])
    pavement_grouped["survey_date"] = pd.to_datetime(pavement_grouped["survey_date"])

    # ---- Synthetic road assets ----
    # S0004: precise construction 2015-06-01..2015-06-01, resurfacing 2017-01-01..2017-01-01
    # S0005: uncertain interval crosses as_of (construction 2017-06-01..2018-06-01)
    # S0006: future asset (construction 2020-01-01..2020-01-01)
    assets_sub = pd.DataFrame([
        {"canonical_segment_id": "S0004",
         "construction_date_lower_bound": pd.Timestamp("2015-06-01"),
         "construction_date_upper_bound": pd.Timestamp("2015-06-01"),
         "resurfacing_date_lower_bound":  pd.Timestamp("2017-01-01"),
         "resurfacing_date_upper_bound":  pd.Timestamp("2017-01-01"),
         "resurfacing_before_construction_candidate_flag": 0,
         "date_contradiction_status": "no_contradiction"},
        {"canonical_segment_id": "S0005",
         "construction_date_lower_bound": pd.Timestamp("2017-06-01"),
         "construction_date_upper_bound": pd.Timestamp("2018-06-01"),
         "resurfacing_date_lower_bound":  pd.NaT,
         "resurfacing_date_upper_bound":  pd.NaT,
         "resurfacing_before_construction_candidate_flag": 0,
         "date_contradiction_status": "no_contradiction"},
        {"canonical_segment_id": "S0006",
         "construction_date_lower_bound": pd.Timestamp("2020-01-01"),
         "construction_date_upper_bound": pd.Timestamp("2020-01-01"),
         "resurfacing_date_lower_bound":  pd.NaT,
         "resurfacing_date_upper_bound":  pd.NaT,
         "resurfacing_before_construction_candidate_flag": 0,
         "date_contradiction_status": "no_contradiction"},
    ])

    # ---- Build synthetic shared dict ----
    shared = {
        "static_df": static_df,
        "segments": SEG_IDS,
        "exclusion_df": exclusion_df,
        "accepted_events": accepted_events,
        "collapsed_events": collapsed_events,
        "dup_membership": pd.DataFrame(),
        "raw_daily": raw_daily,
        "col_daily": col_daily,
        "last_repair_all": last_repair_all,
        "anchor_weather": anchor_weather,
        "pavement_grouped": pavement_grouped,
        "assets_sub": assets_sub,
        "precompute_elapsed": 0.0,
    }
    config_smoke = {
        "features": {
            "historical_repair_windows": [30, 90],
            "weather_rolling_windows": [30, 90],
        }
    }

    # ---- Process 3 anchors into tmp dir ----
    all_entries = {}
    with tempfile.TemporaryDirectory(prefix="phase4_smoke_") as tmpdir:
        out_dir = Path(tmpdir)
        for t in ANCHORS:
            entry = _build_anchor_partition(
                t, shared, config_smoke, out_dir, smoke_test=True
            )
            all_entries[entry["anchor"]] = entry

        # --- Assertions ---
        assert len(all_entries) == 3, "Expected 3 partitions"
        total_rows = sum(e["row_count"] for e in all_entries.values())
        assert total_rows == 30, f"Expected 30 rows, got {total_rows}"

        all_ids: list[str] = []
        for a_key, entry in all_entries.items():
            df = pd.read_parquet(entry["output_path"])
            # Cartesian: 10 segs Ã— 1 anchor
            assert len(df) == 10, f"{a_key}: expected 10 rows"
            # Unique segment_month_id
            assert df["segment_month_id"].is_unique
            all_ids.extend(df["segment_month_id"].tolist())

        assert len(set(all_ids)) == 30, "Duplicate segment_month_ids across anchors"

        # --- Target boundary tests ---
        pd.Timestamp("2018-01-31")
        a_key = "2018-01"
        df = pd.read_parquet(all_entries[a_key]["output_path"])

        # S0001 has accepted repair on 2018-01-15 (inside window 2017-11-02..2018-01-31 for 90d)
        # Target: repair on 2018-01-15 is BEFORE as_of_date=2018-01-31 â†’ in HISTORY not target
        # No repair AFTER 2018-01-31 for S0001 â†’ target_repair_90d = 0 for S0001 at 2018-01
        s1 = df[df["canonical_segment_id"] == "S0001"].iloc[0]
        assert s1["target_repair_90d"] == 0, "S0001 repair is before as_of, not a future target"
        # S0002 has repair on 2018-01-20 (before as_of 2018-01-31) â†’ also target = 0
        s2 = df[df["canonical_segment_id"] == "S0002"].iloc[0]
        assert s2["target_repair_90d"] == 0

        # Strict policy always null
        assert df["target_repair_90d_strict"].isna().all()
        assert df["target_repair_180d_strict"].isna().all()
        # Published resource: all eligible
        assert (df["target_eligible_90d"] == 1).all()
        assert (df["target_eligible_180d"] == 1).all()

        # --- Repair history leakage test ---
        # At 2018-01-31: S0001 had repair on 2018-01-15 â†’ should appear in history
        assert s1["repair_event_count_raw_30d"] >= 1
        # At 2018-02-28: S0001 repair 2018-01-15 within 30d window (2018-01-29..2018-02-28)? No
        # (2018-01-15 < 2018-01-29) â†’ 0
        df_feb = pd.read_parquet(all_entries["2018-02"]["output_path"])
        s1_feb = df_feb[df_feb["canonical_segment_id"] == "S0001"].iloc[0]
        assert s1_feb["repair_event_count_raw_30d"] == 0, (
            "S0001 repair (2018-01-15) should not appear in Feb 30d window"
        )
        # But within 90d window at 2018-02-28 â†’ yes
        assert s1_feb["repair_event_count_raw_90d"] >= 1

        # --- Pavement as-of test ---
        # S0001 survey 2017-06-01 â†’ visible at all 3 anchors
        assert s1["condition_missing_flag"] == 0
        # S0002 survey 2018-04-01 â†’ AFTER all 3 anchors â†’ missing
        s2_feb = df_feb[df_feb["canonical_segment_id"] == "S0002"].iloc[0]
        assert s2_feb["condition_missing_flag"] == 1, (
            "S0002 future survey must not appear at 2018-02 anchor"
        )
        # S0003 same-day duplicate already resolved
        s3 = df[df["canonical_segment_id"] == "S0003"].iloc[0]
        assert s3["latest_pci"] == 75.0  # median

        # --- Road asset tests ---
        s4 = df[df["canonical_segment_id"] == "S0004"].iloc[0]
        assert s4["asset_temporal_eligibility_status"] == "active"
        assert s4["years_since_construction_lower"] > 0

        s5 = df[df["canonical_segment_id"] == "S0005"].iloc[0]
        assert s5["asset_temporal_eligibility_status"] == "crosses"
        assert pd.isna(s5["years_since_construction_lower"])

        s6 = df[df["canonical_segment_id"] == "S0006"].iloc[0]
        assert s6["asset_temporal_eligibility_status"] == "future"
        assert s6["future_asset_record_hidden_flag"] == 1

        # --- Unmatched administrative segment preserved ---
        s10 = df[df["canonical_segment_id"] == UNMATCHED_SEG].iloc[0]
        assert s10["unmatched_boundary_flag"] == 1

        # --- Deterministic fingerprint ---
        fp1 = all_entries["2018-01"]["sorted-content SHA-256 fingerprint"]
        # Rebuild partition into second tmp and compare
        with tempfile.TemporaryDirectory(prefix="phase4_smoke2_") as tmpdir2:
            entry2 = _build_anchor_partition(
                pd.Timestamp("2018-01-31"), shared, config_smoke,
                Path(tmpdir2), smoke_test=True
            )
            fp2 = entry2["sorted-content SHA-256 fingerprint"]
        assert fp1 == fp2, "Fingerprint is not deterministic!"

        # --- Weather uses only dates <= as_of ---
        wx_val = df["total_precip_sum_30d"].iloc[0]
        assert not pd.isna(wx_val), "Weather feature should not be NaN"

        # --- Freeze-thaw present ---
        assert "freeze_thaw_strict_sum_30d" in df.columns

    elapsed = time.perf_counter() - t0
    assert elapsed < 60, f"Smoke test exceeded 60s: {elapsed:.1f}s"
    print(f"Smoke test PASSED in {elapsed:.2f}s")
    print("  Partitions: 3 | Rows: 30 | Unique IDs: 30")


# ---------------------------------------------------------------------------
# Benchmark mode (Part 11)
# ---------------------------------------------------------------------------

def run_benchmark(anchor_str: str, config: dict, cfg_fp: str) -> None:
    print(f"\n=== One-Anchor Benchmark: {anchor_str} ===")
    t_anchor = pd.Timestamp(anchor_str + "-01")
    t_anchor = pd.date_range(t_anchor, periods=1, freq="ME")[0]

    timing: dict = {}
    t0 = time.perf_counter()

    try:
        import psutil
        proc = psutil.Process()
        mem_before = proc.memory_info().rss / 1024**2
    except ImportError:
        mem_before = None

    t1_pre = time.perf_counter()
    shared = precompute_all(config, cfg_fp, print_prefix="  [benchmark] ")
    timing["precompute"] = time.perf_counter() - t1_pre

    try:
        if mem_before is not None:
            proc.memory_info().rss / 1024**2
    except Exception:
        pass

    out_dir = PANEL_DIR / "_benchmark_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        entry = _build_anchor_partition(
            t_anchor, shared, config, out_dir, smoke_test=False, timing=timing
        )
    finally:
        # Clean up benchmark temp partition
        shutil.rmtree(out_dir, ignore_errors=True)

    total_elapsed = time.perf_counter() - t0

    try:
        if mem_before is not None:
            mem_peak = proc.memory_info().rss / 1024**2
        else:
            mem_peak = None
    except Exception:
        mem_peak = None

    os.path.getsize(
        PROJECT_ROOT / "data/processed/phase_4/_benchmark_tmp" /
        f"panel_year={t_anchor.year}" /
        f"panel_month={t_anchor.month:02d}" / "segment_month.parquet"
    ) / 1024**2 if False else entry.get("row_count", 0) * 40 / 1024**2  # estimate

    rows_per_sec = entry["row_count"] / timing.get("total_partition", 1)

    print("\n--- Benchmark Results ---")
    print(f"  Precomputation time : {timing.get('precompute', 0):.2f}s")
    print(f"  Target calc time    : {timing.get('target', 0):.3f}s")
    print(f"  Repair features time: {timing.get('repairs', 0):.3f}s")
    print(f"  Weather time        : {timing.get('weather', 0):.3f}s")
    print(f"  Pavement time       : {timing.get('pavement', 0):.3f}s")
    print(f"  Assets time         : {timing.get('assets', 0):.3f}s")
    print(f"  IO (write+readback) : {timing.get('io', 0):.3f}s")
    print(f"  Fingerprint time    : {timing.get('fingerprint', 0):.3f}s")
    print(f"  Partition total     : {timing.get('total_partition', 0):.3f}s")
    print(f"  Total elapsed       : {total_elapsed:.2f}s")
    if mem_peak:
        print(f"  Peak RAM            : ~{mem_peak:.0f} MB")
    print(f"  Output rows         : {entry['row_count']:,}")
    print(f"  Rows per second     : {rows_per_sec:,.0f}")
    print(f"  Fingerprint         : {entry['sorted-content SHA-256 fingerprint'][:20]}â€¦")


# ---------------------------------------------------------------------------
# Three-anchor resume test (Part 12)
# ---------------------------------------------------------------------------

def run_resume_test(config: dict, cfg_fp: str) -> None:
    print("\n=== Three-Anchor Resume Test ===")
    anchors = [
        pd.Timestamp("2022-01-31"),
        pd.Timestamp("2022-02-28"),
        pd.Timestamp("2022-03-31"),
    ]
    out_dir = PANEL_DIR / "_resume_test"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    shared = precompute_all(config, cfg_fp, print_prefix="  [resume] ")
    manifest: dict = {}

    try:
        # First pass: build all 3
        print("  Pass 1: building all 3 anchorsâ€¦")
        for t in anchors:
            a_key = t.strftime("%Y-%m")
            entry = _build_anchor_partition(t, shared, config, out_dir)
            manifest[a_key] = entry
            print(f"    {a_key}: {entry['row_count']} rows")

        fps_pass1 = {k: v["sorted-content SHA-256 fingerprint"] for k, v in manifest.items()}

        # Corrupt second anchor partition
        a2_key = anchors[1].strftime("%Y-%m")
        corrupt_path = Path(manifest[a2_key]["output_path"])
        corrupt_path.write_bytes(b"CORRUPT_DATA_DO_NOT_USE")
        print(f"  Corrupted partition: {a2_key}")

        # Second pass with --resume: skips valid, rebuilds invalid
        print("  Pass 2 (resume): rebuilding invalid partitionsâ€¦")
        for t in anchors:
            a_key = t.strftime("%Y-%m")
            if a_key in manifest:
                existing_path = Path(manifest[a_key]["output_path"])
                if existing_path.exists():
                    try:
                        df_check = pd.read_parquet(existing_path)
                        row_hashes = pd.util.hash_pandas_object(df_check, index=True)
                        fp_check = hashlib.sha256(row_hashes.values.tobytes()).hexdigest()
                        expected_n = len(shared["segments"])
                        if (len(df_check) == expected_n and df_check["canonical_segment_id"].is_unique
                                and fp_check == manifest[a_key]["sorted-content SHA-256 fingerprint"]):
                            print(f"    {a_key}: skipped (valid)")
                            continue
                    except Exception:
                        pass
            print(f"    {a_key}: rebuildingâ€¦")
            entry = _build_anchor_partition(t, shared, config, out_dir)
            manifest[a_key] = entry

        # Verify all 3 partitions valid
        for t in anchors:
            a_key = t.strftime("%Y-%m")
            df = pd.read_parquet(manifest[a_key]["output_path"])
            assert len(df) == 47983, f"{a_key}: expected 47,983 rows"
            assert df["segment_month_id"].is_unique

        # Verify determinism (pass 1 vs pass 2 fingerprints match)
        for a_key in [anchors[0].strftime("%Y-%m"), anchors[2].strftime("%Y-%m")]:
            fp_now = manifest[a_key]["sorted-content SHA-256 fingerprint"]
            assert fp_now == fps_pass1[a_key], f"Fingerprint mismatch at {a_key}"
        print("  All resume-test checks passed âœ“")
        print("  3 partitions Ã— 47,983 rows = 143,949 rows verified")
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Full pipeline run
# ---------------------------------------------------------------------------

def run_full_pipeline(config: dict, cfg_fp: str, args: argparse.Namespace) -> None:  # noqa: C901
    t0 = time.perf_counter()
    verify_immutability(config, str(PROJECT_ROOT))
    shared = precompute_all(config, cfg_fp)

    anchors = _all_anchors(config)

    # Filter
    filtered = []
    out_dir = Path(args.output_dir) if getattr(args, "output_dir", None) else PANEL_DIR
    for a in anchors:
        a_key = a.strftime("%Y-%m")
        if args.start_anchor and a_key < args.start_anchor:
            continue
        if args.end_anchor and a_key > args.end_anchor:
            continue
        filtered.append(a)

    manifest_path = out_dir / "phase_4_partition_manifest.json"
    manifest: dict = {}
    if args.resume and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            print(f"Resume: {len(manifest)} existing partitions loaded.")
        except Exception as e:
            print(f"Could not load manifest: {e}. Starting fresh.")

    total = len(filtered)
    for idx, t in enumerate(filtered, 1):
        a_key = t.strftime("%Y-%m")

        if args.resume and a_key in manifest:
            entry = manifest[a_key]
            existing_path = Path(entry["output_path"])
            if existing_path.exists():
                try:
                    df_check = pd.read_parquet(existing_path)
                    row_hashes = pd.util.hash_pandas_object(df_check, index=True)
                    fp_check = hashlib.sha256(row_hashes.values.tobytes()).hexdigest()
                    n_exp = len(shared["segments"])
                    if (len(df_check) == n_exp
                            and df_check["canonical_segment_id"].is_unique
                            and pd.to_datetime(df_check["as_of_date"].iloc[0]) == t
                            and fp_check == entry["sorted-content SHA-256 fingerprint"]):
                        print(f"[{idx}/{total}] {a_key} skipped (valid)")
                        continue
                except Exception:
                    pass

        print(f"[{idx}/{total}] {a_key} processing…")
        entry = _build_anchor_partition(t, shared, config, out_dir)
        manifest[a_key] = entry

        # Incremental manifest write
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2))

    # Eligible views
    from montreal_road_risk.features.qa import run_dataset_level_qa
    run_dataset_level_qa(config, str(PROJECT_ROOT), manifest)

    elapsed = time.perf_counter() - t0
    run_manifest = {
        "pipeline": "build_segment_month_panel",
        "phase": "Phase 4",
        "execution_date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(elapsed, 2),
        "total_rows_written": sum(e["row_count"] for e in manifest.values()),
        "status": "success",
    }
    rm_path = PROJECT_ROOT / config["outputs"]["phase_4_run_manifest"]
    rm_path.write_text(json.dumps(run_manifest, indent=2))
    print(f"\nPhase 4 complete in {elapsed:.1f}s. Manifest: {rm_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:  # noqa: C901  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Phase 4 Month-Partitioned Feature Pipeline"
    )
    parser.add_argument("--smoke-test",       action="store_true",
                        help="Run fully synthetic end-to-end smoke test (no real data)")
    parser.add_argument("--benchmark-anchor", metavar="YYYY-MM",
                        help="Run one real-data anchor benchmark")
    parser.add_argument("--start-anchor",     metavar="YYYY-MM")
    parser.add_argument("--end-anchor",       metavar="YYYY-MM")
    parser.add_argument("--resume",           action="store_true")
    parser.add_argument("--verify-determinism", action="store_true")
    parser.add_argument("--workers",          type=int, default=1,
                        help="Number of workers (use 1 on this machine)")
    parser.add_argument("--resume-test",      action="store_true",
                        help="Run three-anchor resume test")
    parser.add_argument("--output-dir",
                        help="Override default output directory for partitioned panel")
    args = parser.parse_args()

    # Smoke test never loads config or real data
    if args.smoke_test:
        try:
            run_synthetic_smoke_test()
        except Exception:
            traceback.print_exc()
            raise SystemExit(1) from None
        return

    config = _load_config()
    cfg_fp = _config_fp(config)

    if args.benchmark_anchor:
        run_benchmark(args.benchmark_anchor, config, cfg_fp)
        return

    if args.resume_test:
        run_resume_test(config, cfg_fp)
        return

    if args.verify_determinism:
        print("Determinism verification not yet implemented in this refactor.")
        return

    # Full pipeline
    run_full_pipeline(config, cfg_fp, args)


if __name__ == "__main__":
    main()


