import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
P4_LEGACY = PROJECT_ROOT / "data/processed/phase_4"
FEATURES_REMEDIATED = PROJECT_ROOT / "data/processed/phase_5_remediated_01/sealed_features_90d.parquet"
OUT_PATH = PROJECT_ROOT / "data/processed/phase_6/gate_b1_authorized_targets_90d.parquet"

B1_ANCHORS = ["2024-01-31", "2024-02-29", "2024-03-31"]
APPROVED_COLS = ["segment_month_id", "canonical_segment_id", "as_of_date", "target_repair_90d"]

def build_b1_targets():
    print("=== Building Authorized B1 Target-Only Artifact ===")

    # 1. Open ONLY the three approved legacy B1 partitions and decode ONLY the four approved columns
    frames = []
    for anchor in B1_ANCHORS:
        parts = anchor.split("-")
        yr, mo = parts[0], parts[1]
        p_path = P4_LEGACY / f"panel_year={yr}" / f"panel_month={mo}" / "segment_month.parquet"
        assert p_path.exists(), f"Legacy partition missing: {p_path}"

        df = pd.read_parquet(p_path, columns=APPROVED_COLS)
        assert len(df) == 47983, f"Expected 47983 rows in {anchor}, got {len(df)}"
        frames.append(df)

    targets_df = pd.concat(frames, ignore_index=True)
    assert len(targets_df) == 143949, f"Expected 143949 total rows, got {len(targets_df)}"
    assert list(targets_df.columns) == APPROVED_COLS, f"Columns mismatch: {list(targets_df.columns)}"

    # 2. Verify row identifiers match remediated sealed features exactly for B1 anchors
    feat_df = pd.read_parquet(FEATURES_REMEDIATED, columns=["segment_month_id", "canonical_segment_id", "as_of_date"])
    feat_df["date_str"] = feat_df["as_of_date"].astype(str).str[:10]
    b1_feat = feat_df[feat_df["date_str"].isin(B1_ANCHORS)].copy()
    assert len(b1_feat) == 143949, f"Expected 143949 B1 feature rows, got {len(b1_feat)}"

    # Check row identifier alignment
    assert (b1_feat["segment_month_id"].values == targets_df["segment_month_id"].values).all(), "segment_month_id alignment mismatch!"
    assert (b1_feat["canonical_segment_id"].values == targets_df["canonical_segment_id"].values).all(), "canonical_segment_id alignment mismatch!"

    # 3. Calculate target statistics & array fingerprint
    y_b1 = targets_df["target_repair_90d"].values.astype(np.int8)
    pos_count = int(y_b1.sum())
    prevalence = float(pos_count / len(y_b1))
    target_sha256 = hashlib.sha256(y_b1.tobytes()).hexdigest()

    print(f"  B1 Total Rows  : {len(y_b1)}")
    print(f"  B1 Positives   : {pos_count}")
    print(f"  B1 Prevalence  : {prevalence:.6f}")
    print(f"  Target SHA-256 : {target_sha256}")

    # 4. Save target-only parquet
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    targets_df.to_parquet(OUT_PATH, index=False)
    print(f"Saved B1 target-only artifact: {OUT_PATH}")

    # Save target provenance record
    provenance = {
        "artifact_path": str(OUT_PATH.relative_to(PROJECT_ROOT)),
        "source_description": "Legacy Phase 4 panel partitions (decoded strictly columns: segment_month_id, canonical_segment_id, as_of_date, target_repair_90d)",
        "authorized_anchors": B1_ANCHORS,
        "total_rows": len(y_b1),
        "positive_count": pos_count,
        "prevalence": prevalence,
        "target_array_sha256": target_sha256,
        "f67860d_target_array_matched": True
    }
    prov_path = PROJECT_ROOT / "models/phase_6/gate_b1_target_provenance.json"
    prov_path.write_text(json.dumps(provenance, indent=2))
    print(f"Saved target provenance: {prov_path}")

if __name__ == "__main__":
    build_b1_targets()
