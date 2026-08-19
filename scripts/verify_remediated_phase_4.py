import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
P4_OLD = PROJECT_ROOT / "data/processed/phase_4"
P4_NEW = PROJECT_ROOT / "data/processed/phase_4_remediated_01"

SEALED_ANCHORS = {
    "2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31", "2024-06-30",
    "2024-07-31", "2024-08-31", "2024-09-30", "2024-10-31", "2024-11-30",
    "2024-12-31", "2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31"
}

def verify_all_partitions() -> None:  # noqa: C901
    print("=== Phase 4 Remediated 102 Partitions Determinism Audit ===")
    old_files = sorted(P4_OLD.rglob("segment_month.parquet"))
    new_files = sorted(P4_NEW.rglob("segment_month.parquet"))

    print(f"Old partitions found: {len(old_files)}")
    print(f"New partitions found: {len(new_files)}")

    matching_count = 0
    changed_count = 0
    missing_count = 0

    results = []

    # Map old partitions by anchor string YYYY-MM
    old_map = {}
    for p in old_files:
        parts = p.parts
        yr = [x for x in parts if x.startswith("panel_year=")][0].split("=")[1]
        mo = [x for x in parts if x.startswith("panel_month=")][0].split("=")[1].zfill(2)
        old_map[f"{yr}-{mo}"] = p

    # Map new partitions by anchor string YYYY-MM
    new_map = {}
    for p in new_files:
        parts = p.parts
        yr = [x for x in parts if x.startswith("panel_year=")][0].split("=")[1]
        mo = [x for x in parts if x.startswith("panel_month=")][0].split("=")[1].zfill(2)
        new_map[f"{yr}-{mo}"] = p

    all_keys = sorted(set(old_map.keys()) | set(new_map.keys()))

    for key in all_keys:
        old_path = old_map.get(key)
        new_path = new_map.get(key)

        if not old_path:
            print(f"  [EXTRA] {key} exists in remediated but not in original!")
            changed_count += 1
            continue

        if not new_path:
            print(f"  [MISSING] {key} is missing in remediated!")
            missing_count += 1
            continue

        # Load Parquet schemas
        import pyarrow.parquet as pq
        new_schema = pq.read_schema(new_path)

        # Load data
        df_old = pd.read_parquet(old_path)
        df_new = pd.read_parquet(new_path)

        # Basic validations
        assert len(df_new) == 47983, f"{key}: row count is {len(df_new)}, expected 47983"
        assert df_new["prior_repair_months_12m"].max() <= 12, f"{key}: prior_repair_months_12m max exceeds 12"

        as_of = str(df_new["as_of_date"].iloc[0])[:10]
        is_sealed = as_of in SEALED_ANCHORS

        # Verify target presence/absence
        target_cols = [c for c in new_schema.names if "target" in c.lower() or "eligible" in c.lower()]
        if is_sealed:
            assert len(target_cols) == 0, f"{key}: sealed partition contains target columns: {target_cols}"
        else:
            assert len(target_cols) > 0, f"{key}: non-sealed partition missing target columns"

        # Compare non-remediated features
        common_cols = [c for c in df_old.columns if c in df_new.columns and c != "prior_repair_months_12m" and not ("target" in c.lower() or "eligible" in c.lower())]

        # Check equivalence fast
        identical = True
        for col in common_cols:
            s_old = df_old[col]
            s_new = df_new[col]
            # Fast comparison of pandas series
            if s_old.dtype == object:
                # Fill na for objects/strings before comparison
                eq = (s_old.fillna("None") == s_new.fillna("None")).all()
            else:
                # For floats/ints, check equals or nan-safe comparison
                eq = s_old.equals(s_new)
                if not eq:
                    # check if they differ only by NaNs
                    eq = (s_old.isna() & s_new.isna()) | (s_old == s_new)
                    eq = eq.all()

            if not eq:
                identical = False
                print(f"  [DIFF] {key}: Column '{col}' changed!")
                break

        prior_diff = (df_old["prior_repair_months_12m"].values != df_new["prior_repair_months_12m"].values).sum()

        if identical:
            matching_count += 1
            if prior_diff > 0:
                results.append({"anchor": key, "status": "MATCHING (Remediated)", "prior_diff_rows": int(prior_diff)})
            else:
                results.append({"anchor": key, "status": "MATCHING (Identical)", "prior_diff_rows": 0})
        else:
            changed_count += 1
            results.append({"anchor": key, "status": "CHANGED (Unexpected)", "prior_diff_rows": int(prior_diff)})

    print("\n=== Audit Results ===")
    print(f"  Matching partitions: {matching_count}")
    print(f"  Changed partitions : {changed_count}")
    print(f"  Missing partitions : {missing_count}")

    with open(PROJECT_ROOT / "models/phase_6/phase_4_determinism_audit.json", "w") as f:
        json.dump({
            "anchors_compared": len(all_keys),
            "matching": matching_count,
            "changed": changed_count,
            "missing": missing_count,
            "results": results
        }, f, indent=2)
    print("\nSaved determinism audit results to models/phase_6/phase_4_determinism_audit.json")

if __name__ == "__main__":
    verify_all_partitions()
