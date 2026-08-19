"""Phase 6 subgroup evaluation.

Subgroup cardinality is read from panel metadata at Gate A
without reading sealed targets.
Subgroups below the minimum sample threshold are labelled
INSUFFICIENT_SAMPLE and are never silently suppressed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .metrics import (
    average_precision,
    lift_at_k,
    precision_at_k,
    recall_at_k,
    roc_auc,
)

_INSUFFICIENT = "INSUFFICIENT_SAMPLE"


class SubgroupEvaluator:
    """Compute per-subgroup evaluation metrics.

    Parameters
    ----------
    min_rows : int
        Minimum row count for a reportable subgroup.
    min_positive_events : int
        Minimum positive events for AP to be reported.
    min_top_k_positives : int
        Minimum positives in the top-K bucket for lift to be reported.
    k_percents : list of float
        Percentages for Top-K metrics.
    """

    def __init__(
        self,
        min_rows: int = 500,
        min_positive_events: int = 50,
        min_top_k_positives: int = 10,
        k_percents: list[float] | None = None,
    ) -> None:
        self.min_rows = min_rows
        self.min_positive_events = min_positive_events
        self.min_top_k_positives = min_top_k_positives
        self.k_percents = k_percents if k_percents is not None else [5.0, 10.0, 20.0]

    def evaluate(
        self,
        df: pd.DataFrame,
        group_col: str,
        y_col: str,
        score_col: str,
        segment_id_col: str = "canonical_segment_id",
        date_col: str = "as_of_date",
        row_id_col: str = "segment_month_id",
    ) -> list[dict[str, Any]]:
        """Compute metrics per subgroup level.

        Parameters
        ----------
        df : DataFrame containing at least group_col, y_col, score_col.
        group_col : Column defining subgroups.
        y_col : Binary target column.
        score_col : Calibrated score column.

        Returns
        -------
        list of dicts, one per subgroup level.
        """
        results = []
        for group_val, grp in df.groupby(group_col, dropna=False):
            y = grp[y_col].to_numpy(dtype=float)
            s = grp[score_col].to_numpy(dtype=float)
            n = len(y)
            n_pos = int(y.sum())
            seg_ids = grp[segment_id_col].to_numpy(dtype=str) if segment_id_col in grp else np.arange(n).astype(str)
            dates = grp[date_col].to_numpy(dtype=str) if date_col in grp else np.zeros(n, dtype=str)
            row_ids = grp[row_id_col].to_numpy(dtype=str) if row_id_col in grp else np.arange(n).astype(str)

            rec: dict[str, Any] = {
                "subgroup_col": group_col,
                "subgroup_val": str(group_val),
                "n_rows": n,
                "n_positive": n_pos,
                "prevalence": float(y.mean()) if n > 0 else float("nan"),
            }

            if n < self.min_rows or n_pos < self.min_positive_events:
                rec["ap"] = _INSUFFICIENT
                rec["roc_auc"] = _INSUFFICIENT
                rec["status"] = _INSUFFICIENT
            else:
                try:
                    rec["ap"] = average_precision(y, s)
                    rec["roc_auc"] = roc_auc(y, s)
                    rec["status"] = "ok"
                except Exception as exc:
                    rec["ap"] = f"ERROR: {exc}"
                    rec["roc_auc"] = f"ERROR: {exc}"
                    rec["status"] = "error"

            for k in self.k_percents:
                key = f"top_{int(k)}"
                if n < self.min_rows:
                    rec[f"{key}_precision"] = _INSUFFICIENT
                    rec[f"{key}_recall"] = _INSUFFICIENT
                    rec[f"{key}_lift"] = _INSUFFICIENT
                else:
                    try:
                        p_at_k = precision_at_k(y, s, k, seg_ids, dates, row_ids)
                        r_at_k = recall_at_k(y, s, k, seg_ids, dates, row_ids)
                        l_at_k = lift_at_k(y, s, k)
                        rec[f"{key}_precision"] = p_at_k
                        rec[f"{key}_recall"] = r_at_k
                        rec[f"{key}_lift"] = l_at_k
                    except Exception as exc:
                        rec[f"{key}_precision"] = f"ERROR: {exc}"
                        rec[f"{key}_recall"] = f"ERROR: {exc}"
                        rec[f"{key}_lift"] = f"ERROR: {exc}"

            results.append(rec)
        return results
