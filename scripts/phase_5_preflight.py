"""
scripts/phase_5_preflight.py

Step 1 — Protected-input snapshot, environment manifest, XGBoost preflight.

Must complete before any split, model, or checkpoint output is created.
"""

import json
import logging
import os
import sys

sys.path.insert(0, "src")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:  # noqa: C901
    from montreal_road_risk.modeling.qa import (
        build_protected_snapshot,
        check_system_memory,
        write_environment_manifest,
        xgboost_preflight,
    )

    cfg_path = "config/phase_5_modeling.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    # 1. System memory baseline check
    mem = check_system_memory(baseline_max_pct=cfg["benchmark_limits"]["baseline_memory_max_pct"])
    log.info(
        "System memory: %.1f%% used | %.2f GB available | process RSS %.2f GB",
        mem["system_pct"], mem["available_gb"], mem["process_rss_gb"],
    )
    if mem["system_pct"] > cfg["benchmark_limits"]["baseline_memory_max_pct"]:
        log.warning(
            "System memory %.1f%% exceeds baseline limit %.1f%% — "
            "recommend closing applications before running full grid.",
            mem["system_pct"], cfg["benchmark_limits"]["baseline_memory_max_pct"],
        )

    # 2. Protected-input snapshot (must be written BEFORE any Phase 5 outputs)
    snap = build_protected_snapshot(cfg, state_dir="state")
    log.info("Protected-input snapshot: %d files", snap["n_protected_files"])

    # 3. Environment manifest
    env = write_environment_manifest(
        models_dir=cfg["models_dir"],
        config=cfg,
        config_path=cfg_path,
    )
    log.info(
        "Environment: Python %s | numpy %s | sklearn %s | pandas %s",
        env["python_version"], env["numpy_version"],
        env["sklearn_version"], env["pandas_version"],
    )

    # 4. XGBoost preflight
    xgb = xgboost_preflight(models_dir=cfg["models_dir"], seed=cfg["seed"])
    if xgb["xgboost_available"]:
        log.info("XGBoost AVAILABLE: version=%s", xgb["xgboost_version"])
    else:
        log.info(
            "XGBoost NOT available: %s — will proceed with LogReg + RF only",
            xgb.get("failure_reason", "unknown"),
        )

    # 5. Validate Phase 4 panel files exist
    import glob
    files = sorted(glob.glob(os.path.join(cfg["panel_dir"], "panel_year=*/panel_month=*/segment_month.parquet")))
    log.info("Phase 4 panel files: %d", len(files))
    assert len(files) == 102, f"Expected 102 panel files, got {len(files)}"

    # Write preflight summary
    os.makedirs(cfg["models_dir"], exist_ok=True)
    summary = {
        "protected_file_count": snap["n_protected_files"],
        "system_memory_pct":    mem["system_pct"],
        "process_rss_gb":       mem["process_rss_gb"],
        "xgboost_available":    xgb["xgboost_available"],
        "xgboost_version":      xgb.get("xgboost_version"),
        "panel_files":          len(files),
        "preflight_passed":     True,
    }
    out = os.path.join(cfg["models_dir"], "preflight_summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    log.info("Preflight PASSED. Summary: %s", out)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
