"""Phase 6 probability calibration.

Calibration method (D6.2 approved): fixed Platt/sigmoid only.
Isotonic regression is deferred.

The final :class:`PlattCalibrator` is fitted exclusively on
Gate B1 data (test anchors 2024-01-31 to 2024-03-31).
The val set must not be used to fit the calibrator.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression


class PlattCalibrator:
    """Platt/sigmoid calibration via logistic regression on raw scores.

    Fits:  logit(P(Y=1)) = a + b × score

    Parameters
    ----------
    C : float
        Inverse regularization.  Default 1e9 ≈ unpenalized.
    max_iter : int
        Convergence cap.
    random_state : int
    epsilon : float
        Clipping for internal probability checks.

    Notes
    -----
    This calibrator does NOT use isotonic regression.
    No Platt-vs-isotonic comparison is performed.  Fixed choice (D6.2).
    """

    def __init__(
        self,
        C: float = 1e9,
        max_iter: int = 1000,
        random_state: int = 42,
        epsilon: float = 1e-7,
    ) -> None:
        self.C = C
        self.max_iter = max_iter
        self.random_state = random_state
        self.epsilon = epsilon
        self._lr: LogisticRegression | None = None
        self._fitted = False

    def fit(self, raw_scores: np.ndarray, y_true: np.ndarray) -> "PlattCalibrator":
        """Fit the Platt calibrator on raw model scores and labels.

        Parameters
        ----------
        raw_scores : 1-D array of uncalibrated model predictions.
        y_true : 1-D array of binary labels {0, 1}.

        Raises
        ------
        ValueError
            If data have fewer than 2 positive events (minimum safety check).
        """
        y = np.asarray(y_true, dtype=float)
        s = np.asarray(raw_scores, dtype=float)
        n_pos = int(y.sum())
        if n_pos < 2:
            raise ValueError(
                f"PlattCalibrator requires ≥ 2 positive events; got {n_pos}."
            )
        self._lr = LogisticRegression(
            C=self.C,
            solver="lbfgs",
            max_iter=self.max_iter,
        )
        self._lr.fit(s.reshape(-1, 1), y)
        self._fitted = True
        return self

    def predict_proba(self, raw_scores: np.ndarray) -> np.ndarray:
        """Return calibrated probabilities in [0, 1].

        Parameters
        ----------
        raw_scores : 1-D array of uncalibrated scores.

        Returns
        -------
        np.ndarray of shape (n,) — calibrated probabilities.
        """
        self._check_fitted()
        s = np.asarray(raw_scores, dtype=float)
        return self._lr.predict_proba(s.reshape(-1, 1))[:, 1]

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("PlattCalibrator has not been fitted yet.")

    # ------------------------------------------------------------------
    # Persistence and fingerprinting
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> str:
        """Serialise to disk and return SHA-256 of the written file."""
        self._check_fitted()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return _sha256_file(path)

    @classmethod
    def load(cls, path: str | Path) -> "PlattCalibrator":
        """Load a calibrator and verify it is fitted."""
        cal = joblib.load(path)
        if not isinstance(cal, cls):
            raise TypeError(f"Expected PlattCalibrator, got {type(cal)}")
        if not cal._fitted:
            raise RuntimeError("Loaded calibrator is not fitted.")
        return cal

    def fingerprint(self, path: str | Path) -> str:
        """Return SHA-256 of the serialised calibrator file."""
        return _sha256_file(path)

    def readback_check(
        self, path: str | Path, raw_scores: np.ndarray
    ) -> dict[str, Any]:
        """Load from disk and verify predictions are identical (allclose).

        Parameters
        ----------
        path : Path to the saved calibrator file.
        raw_scores : Sample of raw scores to check against.

        Returns
        -------
        dict with keys: allclose, max_diff, status
        """
        original = self.predict_proba(raw_scores)
        reloaded = self.load(path).predict_proba(raw_scores)
        max_diff = float(np.max(np.abs(original - reloaded)))
        ok = bool(np.allclose(original, reloaded, atol=0, rtol=0))
        return {
            "allclose": ok,
            "max_diff": max_diff,
            "status": "PASS" if ok else "FAIL",
        }


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
