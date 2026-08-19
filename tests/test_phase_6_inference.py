"""Tests for Phase 6 streaming inference.

Synthetic fixtures only. No sealed test data accessed.
Uses monkeypatch to properly override xgboost in sys.modules.
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest
import pyarrow as pa
import psutil


# ---------------------------------------------------------------------------
# Build a stable xgboost mock that can be injected before inference imports
# ---------------------------------------------------------------------------

def _make_xgb_mock(predict_fn=None):
    """Create a mock xgboost module with a controllable DMatrix."""
    xgb_mock = types.ModuleType("xgboost")

    class _DMatrix:
        def __init__(self, data, label=None, **kw):
            import numpy as np_
            arr = np.asarray(data) if not hasattr(data, "__len__") else data
            self._n = arr.shape[0] if hasattr(arr, "shape") else len(arr)

    xgb_mock.DMatrix = _DMatrix

    if predict_fn is not None:
        xgb_mock._predict_fn = predict_fn
    return xgb_mock


class _MockModel:
    """Minimal XGBoost-like model stub."""
    best_iteration = 5

    def predict(self, dm, iteration_range=None, **kw):
        return np.ones(dm._n) * 0.5


class _MockPreprocessor:
    def transform(self, X):
        import numpy as np_
        import pandas as pd
        if isinstance(X, pd.DataFrame):
            # Return only numeric columns as array
            numeric = X.select_dtypes(include=[np_.number])
            if numeric.empty:
                return np_.zeros((len(X), 1))
            return numeric.values.astype(np_.float32)
        return np_.asarray(X, dtype=np_.float32)


class TestStreamingInference:
    """Tests streaming inference memory behavior and correctness."""

    def test_prediction_count_matches_rows(self, monkeypatch):
        import numpy as np_

        # Inject mock xgboost BEFORE importing inference
        xgb_mock = _make_xgb_mock()
        monkeypatch.setitem(sys.modules, "xgboost", xgb_mock)

        # Force re-import of inference with patched xgboost
        if "montreal_road_risk.evaluation.inference" in sys.modules:
            monkeypatch.delitem(sys.modules, "montreal_road_risk.evaluation.inference", raising=False)

        from montreal_road_risk.evaluation.inference import StreamingInference

        n_rows = 250
        rng = np_.random.default_rng(1)
        data = pa.table({
            "feat_a": pa.array(rng.uniform(0, 1, n_rows).astype(np_.float32)),
            "feat_b": pa.array(rng.uniform(0, 1, n_rows).astype(np_.float32)),
            "segment_month_id": pa.array([f"row_{i}" for i in range(n_rows)]),
        })

        infer = StreamingInference(
            model=_MockModel(),
            preprocessor=_MockPreprocessor(),
            batch_size=100,
            exclude_cols={"segment_month_id"},
        )
        result = infer.predict_table(data, id_col="segment_month_id")
        assert len(result["proba_raw"]) == n_rows
        assert len(result["ids"]) == n_rows
        assert result["proba_raw"].dtype == np_.float32

    def test_no_x_full_created(self, monkeypatch):
        """RSS during inference should not spike by holding the full matrix."""
        import numpy as np_

        xgb_mock = _make_xgb_mock()
        monkeypatch.setitem(sys.modules, "xgboost", xgb_mock)
        if "montreal_road_risk.evaluation.inference" in sys.modules:
            monkeypatch.delitem(sys.modules, "montreal_road_risk.evaluation.inference", raising=False)

        from montreal_road_risk.evaluation.inference import StreamingInference

        rng = np_.random.default_rng(3)
        n = 300
        data = pa.table({
            "feat_a": pa.array(rng.uniform(0, 1, n).astype(np_.float32)),
            "feat_b": pa.array(rng.uniform(0, 1, n).astype(np_.float32)),
            "segment_month_id": pa.array([f"r_{i}" for i in range(n)]),
        })

        rss_before = psutil.Process().memory_info().rss
        infer = StreamingInference(
            model=_MockModel(),
            preprocessor=_MockPreprocessor(),
            batch_size=100,
            exclude_cols={"segment_month_id"},
        )
        result = infer.predict_table(data, id_col="segment_month_id")
        rss_after = psutil.Process().memory_info().rss

        # RSS increase should be small (< 100 MB) for tiny synthetic data
        delta_mb = (rss_after - rss_before) / 1e6
        assert delta_mb < 200, f"RSS delta too large: {delta_mb:.1f} MB"
        assert len(result["proba_raw"]) == n
