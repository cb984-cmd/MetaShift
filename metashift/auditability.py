"""Descriptive helpers for auditability and representativeness analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit


EPA_REGION_BY_STATE_CODE = {
    "01": "EPA Region 4",
    "02": "EPA Region 10",
    "04": "EPA Region 9",
    "05": "EPA Region 6",
    "06": "EPA Region 9",
    "08": "EPA Region 8",
    "09": "EPA Region 1",
    "10": "EPA Region 3",
    "11": "EPA Region 3",
    "12": "EPA Region 4",
    "13": "EPA Region 4",
    "15": "EPA Region 9",
    "16": "EPA Region 10",
    "17": "EPA Region 5",
    "18": "EPA Region 5",
    "19": "EPA Region 7",
    "20": "EPA Region 7",
    "21": "EPA Region 4",
    "22": "EPA Region 6",
    "23": "EPA Region 1",
    "24": "EPA Region 3",
    "25": "EPA Region 1",
    "26": "EPA Region 5",
    "27": "EPA Region 5",
    "28": "EPA Region 4",
    "29": "EPA Region 7",
    "30": "EPA Region 8",
    "31": "EPA Region 7",
    "32": "EPA Region 9",
    "33": "EPA Region 1",
    "34": "EPA Region 2",
    "35": "EPA Region 6",
    "36": "EPA Region 2",
    "37": "EPA Region 4",
    "38": "EPA Region 8",
    "39": "EPA Region 5",
    "40": "EPA Region 6",
    "41": "EPA Region 10",
    "42": "EPA Region 3",
    "44": "EPA Region 1",
    "45": "EPA Region 4",
    "46": "EPA Region 8",
    "47": "EPA Region 4",
    "48": "EPA Region 6",
    "49": "EPA Region 8",
    "50": "EPA Region 1",
    "51": "EPA Region 3",
    "53": "EPA Region 10",
    "54": "EPA Region 3",
    "55": "EPA Region 5",
    "56": "EPA Region 8",
    "60": "EPA Region 9",
    "66": "EPA Region 9",
    "69": "EPA Region 9",
    "72": "EPA Region 2",
    "78": "EPA Region 2",
}


@dataclass(frozen=True)
class RidgeLogisticFit:
    """A standardized descriptive logistic-regression fit."""

    intercept: float
    coefficients: np.ndarray
    feature_means: np.ndarray
    feature_scales: np.ndarray
    observations: int
    positive_outcomes: int
    ridge_penalty: float


def epa_region(state_code: str) -> str:
    """Map a two-digit state/territory code to its fixed EPA region."""

    normalized = str(state_code).zfill(2)
    try:
        return EPA_REGION_BY_STATE_CODE[normalized]
    except KeyError as error:
        raise ValueError(f"No EPA-region mapping for state code {normalized!r}.") from error


def standardized_mean_difference(
    included: np.ndarray | pd.Series, unavailable: np.ndarray | pd.Series
) -> float:
    """Compute complete-minus-unavailable pooled-standard-deviation difference."""

    left = np.asarray(included, dtype=float)
    right = np.asarray(unavailable, dtype=float)
    left = left[np.isfinite(left)]
    right = right[np.isfinite(right)]
    if len(left) < 2 or len(right) < 2:
        raise ValueError("Standardized difference requires at least two values per group.")
    pooled_variance = (np.var(left, ddof=1) + np.var(right, ddof=1)) / 2
    if pooled_variance == 0:
        return 0.0
    return float((np.mean(left) - np.mean(right)) / np.sqrt(pooled_variance))


def fit_ridge_logistic(
    features: pd.DataFrame, outcome: np.ndarray | pd.Series, ridge_penalty: float
) -> RidgeLogisticFit:
    """Fit a deterministic standardized logistic model for descriptive reporting."""

    if ridge_penalty < 0:
        raise ValueError("Ridge penalty cannot be negative.")
    matrix = features.to_numpy(dtype=float)
    labels = np.asarray(outcome, dtype=float)
    if matrix.ndim != 2 or len(matrix) != len(labels):
        raise ValueError("Feature matrix and outcome dimensions disagree.")
    if not np.isfinite(matrix).all() or not np.isfinite(labels).all():
        raise ValueError("Descriptive logistic model requires finite values.")
    if not set(np.unique(labels)).issubset({0.0, 1.0}) or len(np.unique(labels)) != 2:
        raise ValueError("Descriptive logistic outcome must contain both 0 and 1.")
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0, ddof=0)
    scales = np.where(scales > 0, scales, 1.0)
    standardized = (matrix - means) / scales
    design = np.column_stack([np.ones(len(standardized)), standardized])

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        logits = design @ parameters
        loss = float(
            np.logaddexp(0.0, logits).sum()
            - np.dot(labels, logits)
            + 0.5 * ridge_penalty * np.square(parameters[1:]).sum()
        )
        gradient = design.T @ (expit(logits) - labels)
        gradient[1:] += ridge_penalty * parameters[1:]
        return loss, gradient

    solution = minimize(
        lambda parameters: objective(parameters)[0],
        x0=np.zeros(design.shape[1]),
        jac=lambda parameters: objective(parameters)[1],
        method="L-BFGS-B",
    )
    if not solution.success:
        raise RuntimeError(
            f"Descriptive logistic optimization failed: {solution.message}"
        )
    return RidgeLogisticFit(
        intercept=float(solution.x[0]),
        coefficients=solution.x[1:].astype(float),
        feature_means=means.astype(float),
        feature_scales=scales.astype(float),
        observations=len(labels),
        positive_outcomes=int(labels.sum()),
        ridge_penalty=ridge_penalty,
    )
