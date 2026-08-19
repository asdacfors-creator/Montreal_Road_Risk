"""
src/montreal_road_risk/modeling/preprocessing.py

Model-family-specific preprocessing pipelines for Phase 5.

Rules
-----
* Logistic pipeline: impute → OHE → StandardScaler(with_mean=False) → estimator
* Tree pipeline:     impute → OHE → (no scaler)                     → estimator
* Each pipeline is a distinct object; fitted independently on training data.
* days_since_last_repair sentinel (-1) applied before the pipeline.
* Binary passthrough columns are asserted clean before inclusion.
* All fit operations are on training data only.
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

log = logging.getLogger(__name__)

DAYS_SENTINEL = -1  # Replaces null days_since_last_repair


# ---------------------------------------------------------------------------
# Feature resolution
# ---------------------------------------------------------------------------

def resolve_feature_columns(
    df: pd.DataFrame,
    cfg: dict,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Partition actual columns into: numeric, categorical, binary_passthrough,
    and verify none of the excluded columns are present.

    Returns (numeric_cols, categorical_cols, binary_cols, excluded_found)
    where excluded_found should be empty.
    """
    exclude = set(cfg["exclude_from_X"])
    cat_cols_cfg = set(cfg["categorical_cols"])
    bin_cols_cfg = set(cfg["binary_passthrough_cols"])
    allowlist = cfg.get("feature_allowlist", None)

    available = set(df.columns)
    excluded_found = [c for c in available if c in exclude]

    feature_cols = [c for c in df.columns if c not in exclude]

    categorical_cols = [c for c in feature_cols if c in cat_cols_cfg]
    binary_cols      = [c for c in feature_cols if c in bin_cols_cfg]
    numeric_cols     = [
        c for c in feature_cols
        if c not in cat_cols_cfg and c not in bin_cols_cfg
    ]

    if allowlist:
        missing_from_df  = [c for c in allowlist if c not in available and c not in exclude]
        extra_in_df      = [c for c in feature_cols if c not in allowlist]
        if missing_from_df:
            raise ValueError(f"Expected allowlist features missing from panel: {missing_from_df}")
        if extra_in_df:
            raise ValueError(f"Unexpected features not in allowlist: {extra_in_df}")

    return numeric_cols, categorical_cols, binary_cols, excluded_found


def apply_sentinel(df: pd.DataFrame) -> pd.DataFrame:
    """Replace null days_since_last_repair with sentinel -1."""
    df = df.copy()
    if "days_since_last_repair" in df.columns:
        df["days_since_last_repair"] = df["days_since_last_repair"].fillna(DAYS_SENTINEL)
    return df


def fill_missing_categoricals(df: pd.DataFrame, cat_cols: list[str]) -> pd.DataFrame:
    """Replace null categoricals with string 'missing' before encoding."""
    df = df.copy()
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].fillna("missing").astype(object)
    return df


def validate_binary_cols(df: pd.DataFrame, binary_cols: list[str]) -> None:
    """
    Assert binary passthrough columns are:
    - present
    - no nulls
    - contain only 0/1/True/False values
    - integer or boolean dtype
    """
    for c in binary_cols:
        if c not in df.columns:
            log.warning("Binary col %s not found in df; skipping assertion", c)
            continue
        n_null = df[c].isna().sum()
        if n_null > 0:
            raise ValueError(f"Binary column '{c}' has {n_null} null values")
        unique_vals = set(df[c].dropna().unique())
        allowed = {0, 1}
        bad = unique_vals - allowed
        if bad:
            raise ValueError(f"Binary column '{c}' contains non-0/1 values: {bad}")


# ---------------------------------------------------------------------------
# Pipeline builders
# ---------------------------------------------------------------------------

def _build_column_transformer(
    numeric_cols: list[str],
    categorical_cols: list[str],
    binary_cols: list[str],
    apply_scaler: bool,
) -> ColumnTransformer:
    """
    Build a ColumnTransformer for the given feature partition.

    apply_scaler=True  → StandardScaler(with_mean=False) after imputation (LogReg)
    apply_scaler=False → no scaler (tree models)
    """
    numeric_steps: list = [("imputer", SimpleImputer(strategy="median"))]
    if apply_scaler:
        numeric_steps.append(("scaler", StandardScaler(with_mean=False)))

    numeric_pipe = Pipeline(numeric_steps)

    ohe_pipe = Pipeline([
        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])

    transformers = []
    if numeric_cols:
        transformers.append(("numeric", numeric_pipe, numeric_cols))
    if categorical_cols:
        transformers.append(("categorical", ohe_pipe, categorical_cols))
    if binary_cols:
        transformers.append(("binary", "passthrough", binary_cols))

    return ColumnTransformer(transformers=transformers, remainder="drop")


def build_logistic_pipeline(
    estimator,
    numeric_cols: list[str],
    categorical_cols: list[str],
    binary_cols: list[str],
) -> Pipeline:
    """
    Build: impute+scale (numeric) | OHE (categorical) | passthrough (binary) → estimator
    """
    ct = _build_column_transformer(
        numeric_cols, categorical_cols, binary_cols, apply_scaler=True
    )
    return Pipeline([("preprocessor", ct), ("estimator", estimator)])


def build_tree_pipeline(
    estimator,
    numeric_cols: list[str],
    categorical_cols: list[str],
    binary_cols: list[str],
) -> Pipeline:
    """
    Build: impute (numeric) | OHE (categorical) | passthrough (binary) → estimator
    No scaling.
    """
    ct = _build_column_transformer(
        numeric_cols, categorical_cols, binary_cols, apply_scaler=False
    )
    return Pipeline([("preprocessor", ct), ("estimator", estimator)])


# ---------------------------------------------------------------------------
# Prepare X, y from a partition dataframe
# ---------------------------------------------------------------------------

def prepare_Xy(
    df: pd.DataFrame,
    target_col: str,
    cfg: dict,
    cat_cols: list[str],
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Apply sentinel and categorical fill, then return (X, y).
    Excluded columns are dropped here; target is extracted separately.
    """
    df = apply_sentinel(df)
    df = fill_missing_categoricals(df, cat_cols)

    exclude = set(cfg["exclude_from_X"])
    # Keep target_col but drop all other targets
    target_cols_all = {
        "target_repair_90d", "target_repair_180d",
        "target_eligible_90d", "target_eligible_180d",
        "target_repair_90d_strict", "target_repair_180d_strict",
        "positive_observed_in_incomplete_window_90d",
        "positive_observed_in_incomplete_window_180d",
    }
    drop_cols = (exclude | target_cols_all) - {target_col}

    y = df[target_col].copy()
    X = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
    # Also drop split/embargo columns and fingerprint helpers if present
    meta_cols = [
        "split_90d", "split_180d",
        "exclusion_reason_90d", "exclusion_reason_180d",
        "target_end_date_90d", "target_end_date_180d",
    ]
    X = X.drop(columns=[c for c in meta_cols if c in X.columns], errors="ignore")
    X = X.drop(columns=[target_col], errors="ignore")

    return X, y
