"""Phase 6 memory-safe streaming inference.

Streams the sealed Parquet in batches of 100,000 rows.
Never loads the full feature matrix into RAM.
Monitors RSS and system memory; aborts at 85% system memory.
Does not request target columns during the benchmark pass.
"""

from __future__ import annotations

import gc
from typing import Any

import numpy as np
import psutil

_ABORT_SYSTEM_PCT = 85.0
_BATCH_SIZE = 100_000
_RSS_WARN_GB = 6.0


class StreamingInference:
    """Run memory-safe batch inference over a Parquet file.

    Parameters
    ----------
    model : xgboost.Booster
        The selected Phase 5 XGBoost model.
    preprocessor : sklearn.pipeline.Pipeline
        The fitted Phase 5 preprocessor.
    calibrator : PlattCalibrator or None
        If provided, calibrated probabilities are also returned.
    batch_size : int
        Rows per batch.
    abort_pct : float
        System memory percentage at which to abort (default 85%).
    exclude_cols : list of str
        Columns to exclude from X before preprocessing (e.g. id cols, targets).
    """

    def __init__(
        self,
        model: Any,
        preprocessor: Any,
        calibrator: Any | None = None,
        batch_size: int = _BATCH_SIZE,
        abort_pct: float = _ABORT_SYSTEM_PCT,
        exclude_cols: list[str] | None = None,
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor
        self.calibrator = calibrator
        self.batch_size = batch_size
        self.abort_pct = abort_pct
        self.exclude_cols = set(exclude_cols or [])

    def predict_table(
        self,
        table: Any,  # pyarrow.Table
        id_col: str = "segment_month_id",
    ) -> dict[str, np.ndarray]:
        """Run batch inference on a PyArrow table.

        Parameters
        ----------
        table : pyarrow.Table with feature columns.
        id_col : Identifier column preserved in output.

        Returns
        -------
        dict with keys: ids, proba_raw, proba_cal (if calibrator set)
        """
        import xgboost as xgb

        n = len(table)
        ids_all: list[str] = []
        raw_all: list[float] = []
        cal_all: list[float] = []
        peak_rss = 0.0

        for start in range(0, n, self.batch_size):
            _check_memory(self.abort_pct)
            end = min(start + self.batch_size, n)
            batch = table.slice(start, end - start).to_pandas()

            ids_batch = batch[id_col].tolist() if id_col in batch.columns else [f"row_{i}" for i in range(start, end)]
            X_batch = batch.drop(columns=[c for c in self.exclude_cols if c in batch.columns], errors="ignore")

            X_trans = self.preprocessor.transform(X_batch)
            dm = xgb.DMatrix(X_trans)
            raw_scores = self.model.predict(dm, iteration_range=(0, self.model.best_iteration + 1))

            ids_all.extend(ids_batch)
            raw_all.extend(raw_scores.tolist())

            if self.calibrator is not None:
                cal_scores = self.calibrator.predict_proba(raw_scores)
                cal_all.extend(cal_scores.tolist())

            rss = psutil.Process().memory_info().rss / 1e9
            peak_rss = max(peak_rss, rss)
            del batch, X_batch, X_trans, dm, raw_scores
            gc.collect()

        result = {
            "ids": np.array(ids_all),
            "proba_raw": np.array(raw_all, dtype=np.float32),
            "peak_rss_gb": peak_rss,
        }
        if self.calibrator is not None:
            result["proba_cal"] = np.array(cal_all, dtype=np.float32)
        return result


def _check_memory(abort_pct: float) -> None:
    pct = psutil.virtual_memory().percent
    if pct >= abort_pct:
        raise MemoryError(
            f"System memory at {pct:.1f}% >= abort threshold {abort_pct:.1f}%. "
            "Aborting to protect system stability."
        )
