"""
scripts/phase_5_build_splits.py

Step 8 — Build purged splits and write test seal.

Uses the streaming anchor-by-anchor approach to keep peak memory to one
parquet file at a time (~25 MB uncompressed) rather than loading the full
4.9 GB panel into pandas.
"""

import json
import logging
import os
import sys
import time

sys.path.insert(0, "src")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:  # noqa: C901
    from montreal_road_risk.modeling.splits import (
        assert_purge_conditions_from_map,
        assert_split_arithmetic_from_summary,
        build_splits_streaming,
    )

    cfg_path = "config/phase_5_modeling.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    out_dir = cfg["phase5_dir"]
    models_dir = cfg["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    # Step 1: Assert purge conditions from pure date math (no I/O)
    log.info("Asserting purge conditions ...")
    assert_purge_conditions_from_map(cfg)

    # Step 2: Stream-build all partitions
    t0 = time.time()
    log.info("Streaming split build → %s", out_dir)
    summary = build_splits_streaming(cfg, out_dir)
    elapsed = time.time() - t0
    log.info("Split build complete in %.1f s", elapsed)

    # Step 3: Assert arithmetic from summary dict (no groupby on full panel)
    log.info("Asserting split arithmetic ...")
    assert_split_arithmetic_from_summary(summary, cfg)

    # Step 4: Write summary to disk
    summary["elapsed_s"] = round(elapsed, 1)
    summary_path = os.path.join(models_dir, "split_build_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info("Split build summary: %s", summary_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
