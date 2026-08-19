"""
Machine Learning & Parametric Survival Modeling module.
Implements Weibull Accelerated Failure Time (AFT) survival regression
using SciPy optimization with Log-Sum-Exp numerical stabilization and gradient bounds.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize


class WeibullAFTModel:
    """
    Weibull Accelerated Failure Time (AFT) Survival Model.

    Log-duration formulation:
        log T = X * beta + sigma * W
    where W follows extreme value distribution with density f(w) = exp(w - exp(w)).

    Hazard function:
        h(t | X) = (1 / (sigma * t)) * exp((log t - X*beta) / sigma)
    Survival function:
        S(t | X) = exp(- exp((log t - X*beta) / sigma))
    """

    def __init__(self, l2_reg: float = 1e-4):
        self.l2_reg = l2_reg
        self.beta_ = None
        self.log_sigma_ = None
        self.sigma_ = None
        self.is_fitted_ = False
        self.feature_names_ = None

    def fit(
        self,
        durations: np.ndarray | pd.Series,
        events: np.ndarray | pd.Series,
        X: np.ndarray | pd.DataFrame | None = None,
    ) -> "WeibullAFTModel":
        """
        Fits the Weibull AFT model parameters (beta, log_sigma) via Maximum Likelihood.

        Parameters
        ----------
        durations : Array of positive event/censor durations (days)
        events : Binary event indicators (1 = event, 0 = right-censored)
        X : Feature matrix (n_samples, n_features) or None for baseline model

        Returns
        -------
        self : WeibullAFTModel
        """
        durations = np.asarray(durations, dtype=float)
        events = np.asarray(events, dtype=int)

        # Filter out invalid durations (<= 0)
        valid_mask = durations > 0
        durations = durations[valid_mask]
        events = events[valid_mask]

        log_t = np.log(durations)

        if X is None:
            X_mat = np.ones((len(durations), 1))
            self.feature_names_ = ["intercept"]
        else:
            if isinstance(X, pd.DataFrame):
                self.feature_names_ = list(X.columns)
                X_mat = X.values[valid_mask]
            else:
                self.feature_names_ = [f"x{i}" for i in range(X.shape[1])]
                X_mat = X[valid_mask]
            # Prepend intercept column
            X_mat = np.column_stack([np.ones(len(durations)), X_mat])

        n_samples, n_features = X_mat.shape

        # Initial parameters: beta = 0 (except intercept = mean(log_t)), log_sigma = 0
        init_beta = np.zeros(n_features)
        init_beta[0] = np.mean(log_t)
        init_log_sigma = 0.0
        init_params = np.append(init_beta, init_log_sigma)

        # Objective function: Negative Log-Likelihood with Log-Sum-Exp & clipping
        def neg_log_likelihood(params):
            beta = params[:n_features]
            log_sigma = params[n_features]
            sigma = np.exp(np.clip(log_sigma, -10.0, 10.0))

            # Linear predictor X*beta with numeric clipping [-30, 30]
            mu = np.clip(X_mat @ beta, -30.0, 30.0)

            # Standardised log-duration z = (log t - mu) / sigma
            z = np.clip((log_t - mu) / sigma, -50.0, 50.0)

            exp_z = np.exp(z)

            # Log-likelihood terms:
            # For observed events (E=1): log h(t) + log S(t) = - log(sigma) - log(t) + z - exp(z)
            # For censored events (E=0): log S(t) = - exp(z)
            ll_events = events * (-log_sigma - log_t + z) - exp_z

            total_ll = np.sum(ll_events)

            # L2 regularization on non-intercept betas
            reg_penalty = 0.5 * self.l2_reg * np.sum(beta[1:] ** 2)

            return -total_ll + reg_penalty

        res = minimize(
            neg_log_likelihood,
            init_params,
            method="L-BFGS-B",
            options={"maxiter": 500, "ftol": 1e-7},
        )

        fitted_params = res.x
        self.beta_ = fitted_params[:n_features]
        self.log_sigma_ = fitted_params[n_features]
        self.sigma_ = float(np.exp(self.log_sigma_))
        self.is_fitted_ = True

        return self

    def predict_median_survival(
        self,
        X: np.ndarray | pd.DataFrame | None = None,
    ) -> np.ndarray:
        """
        Predicts median survival time T_50 (days) for given feature matrix X.
        T_50 = exp(X * beta + sigma * log(log(2)))
        """
        if not self.is_fitted_:
            raise RuntimeError("Model is not fitted yet.")

        if X is None:
            X_mat = np.ones((1, 1))
        else:
            if isinstance(X, pd.DataFrame):
                X_mat = X.values
            else:
                X_mat = np.asarray(X)
            X_mat = np.column_stack([np.ones(len(X_mat)), X_mat])

        mu = np.clip(X_mat @ self.beta_, -30.0, 30.0)
        log_median = mu + self.sigma_ * np.log(np.log(2.0))
        return np.exp(log_median)

    def predict_survival_probability(
        self,
        times: np.ndarray | float,
        X: np.ndarray | pd.DataFrame | None = None,
    ) -> np.ndarray:
        """
        Predicts survival probability S(t | X) = exp(- exp((log t - X*beta) / sigma)).
        """
        if not self.is_fitted_:
            raise RuntimeError("Model is not fitted yet.")

        times = np.atleast_1d(times)
        if X is None:
            X_mat = np.ones((1, 1))
        else:
            if isinstance(X, pd.DataFrame):
                X_mat = X.values
            else:
                X_mat = np.asarray(X)
            X_mat = np.column_stack([np.ones(len(X_mat)), X_mat])

        n_samples = len(X_mat)
        n_times = len(times)
        surv_matrix = np.zeros((n_samples, n_times))

        mu = np.clip(X_mat @ self.beta_, -30.0, 30.0)

        for j, t in enumerate(times):
            if t <= 0:
                surv_matrix[:, j] = 1.0
            else:
                log_t = np.log(t)
                z = np.clip((log_t - mu) / self.sigma_, -50.0, 50.0)
                surv_matrix[:, j] = np.exp(-np.exp(z))

        return surv_matrix if n_samples > 1 else surv_matrix[0]
