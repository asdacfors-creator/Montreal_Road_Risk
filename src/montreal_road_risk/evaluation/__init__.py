"""Phase 6 evaluation package.

Provides calibration, metrics, subgroup analysis, bootstrap CI,
seal guard, and memory-safe inference for the Montreal Road Risk
Phase 6 evaluation.

Gate authorization is enforced by :class:`~seal_guard.TestSealGuard`.
No sealed targets may be accessed without a valid gate manifest.
"""

from .bootstrap import BootstrapCI
from .calibration import PlattCalibrator
from .inference import StreamingInference
from .metrics import (
    average_precision,
    brier_score,
    calibration_slope_intercept,
    expected_calibration_error,
    lift_at_k,
    log_loss_score,
    precision_at_k,
    recall_at_k,
    reliability_table,
    roc_auc,
    top_k_row_count,
)
from .seal_guard import OneTimeEvaluationError, SealViolationError, TestSealGuard
from .subgroup import SubgroupEvaluator

__all__ = [
    "TestSealGuard",
    "SealViolationError",
    "OneTimeEvaluationError",
    "PlattCalibrator",
    "average_precision",
    "roc_auc",
    "brier_score",
    "log_loss_score",
    "calibration_slope_intercept",
    "expected_calibration_error",
    "reliability_table",
    "precision_at_k",
    "recall_at_k",
    "lift_at_k",
    "top_k_row_count",
    "BootstrapCI",
    "SubgroupEvaluator",
    "StreamingInference",
]
