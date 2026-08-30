"""Cross-site counterfactual construction and metadata-anchored effect estimates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass(frozen=True)
class MetaShiftEstimate:
    """A local residual discontinuity estimate at one metadata anchor."""

    anchor_date: pd.Timestamp
    calibration_observations: int
    pre_observations: int
    post_observations: int
    mean_available_donors: float
    log_effect: float
    relative_effect: float
    raw_effect: float
    standardized_score: float
    calibration_residual_scale: float
    calibration_residual_rmse: float


def _require_datetime_index(values: pd.Series | pd.DataFrame) -> None:
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("MetaShift inputs must use a DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise ValueError("MetaShift inputs must be sorted by date.")


def _robust_scale(values: pd.Series) -> float:
    finite_values = values.dropna().to_numpy(dtype=float)
    if len(finite_values) == 0:
        raise ValueError("Cannot estimate a scale from an empty residual series.")
    median = float(np.median(finite_values))
    mad = float(np.median(np.abs(finite_values - median)))
    return max(1.4826 * mad, 1e-8)


def donor_weights(
    controls: pd.DataFrame, distance_decay_km: float = 50.0
) -> pd.Series:
    """Compute fixed pre-period donor weights from control-match metadata."""

    required = {"pre_transition_log_correlation", "distance_km"}
    missing = required.difference(controls.columns)
    if missing:
        raise ValueError(f"Control metadata lacks required columns: {sorted(missing)}")
    if distance_decay_km <= 0:
        raise ValueError("distance_decay_km must be positive.")

    correlations = controls["pre_transition_log_correlation"].clip(lower=0.0)
    distances = controls["distance_km"].clip(lower=0.0)
    unnormalized = correlations.pow(2) * np.exp(-distances / distance_decay_km)
    total = float(unnormalized.sum())
    if not np.isfinite(total) or total <= 0:
        raise ValueError("Eligible controls did not yield positive donor weights.")
    return unnormalized / total


def reliability_constrained_weights(
    target: pd.Series,
    donors: pd.DataFrame,
    reliability_prior: pd.Series,
    *,
    ridge_penalty: float = 0.01,
    prior_penalty: float = 0.10,
    min_observations: int = 60,
) -> pd.Series:
    """Fit pre-event synthetic-control weights regularized toward graph reliability.

    The intercept is profiled out by centering each series within the supplied
    pre-event calibration table. Inputs must be restricted to dates before the
    anchor; this function intentionally has no anchor-date argument so callers
    must make the temporal split explicit.
    """

    if ridge_penalty < 0 or prior_penalty < 0:
        raise ValueError("Regularization penalties cannot be negative.")
    _require_datetime_index(target)
    _require_datetime_index(donors)
    columns = donors.columns.intersection(reliability_prior.index)
    if len(columns) < 2:
        raise ValueError("At least two donors with reliability priors are required.")

    table = pd.concat(
        [target.rename("target"), donors.loc[:, columns]], axis="columns", sort=False
    ).dropna()
    if len(table) < min_observations:
        raise ValueError("Insufficient complete pre-event observations for weight fitting.")

    prior = reliability_prior.loc[columns].astype(float)
    if not np.isclose(prior.sum(), 1.0):
        prior = prior / prior.sum()
    target_values = np.log1p(table.pop("target").clip(lower=0.0).to_numpy())
    donor_values = np.log1p(table.clip(lower=0.0).to_numpy())
    target_values = target_values - target_values.mean()
    donor_values = donor_values - donor_values.mean(axis=0)
    prior_values = prior.to_numpy()
    donor_count = len(columns)

    def objective(weights: np.ndarray) -> float:
        error = target_values - donor_values @ weights
        return float(
            np.mean(np.square(error))
            + ridge_penalty * np.square(weights).sum()
            + prior_penalty * np.square(weights - prior_values).sum()
        )

    solution = minimize(
        objective,
        x0=prior_values,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * donor_count,
        constraints={"type": "eq", "fun": lambda weights: weights.sum() - 1.0},
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not solution.success:
        raise RuntimeError(
            f"Reliability-constrained weight optimization failed: {solution.message}"
        )
    return pd.Series(solution.x, index=columns, name="reliability_constrained_weight")


def weighted_donor_series(
    donors: pd.DataFrame, weights: pd.Series, logarithmic: bool
) -> tuple[pd.Series, pd.Series]:
    """Return a donor composite and the effective donor count on each date."""

    _require_datetime_index(donors)
    selected_columns = donors.columns.intersection(weights.index)
    if len(selected_columns) == 0:
        raise ValueError("No donor columns match the supplied weights.")

    values = donors.loc[:, selected_columns].astype(float)
    selected_weights = weights.loc[selected_columns].astype(float)
    if logarithmic:
        # AQS occasionally reports slightly negative concentrations. Retain them
        # in raw-unit estimates; clip only for the log scale used for correlation.
        values = np.log1p(values.clip(lower=0.0))

    available = values.notna()
    effective_weight = available.mul(selected_weights, axis="columns")
    weight_sum = effective_weight.sum(axis="columns")
    composite = values.mul(selected_weights, axis="columns").sum(
        axis="columns", min_count=1
    ) / weight_sum.replace(0.0, np.nan)
    effective_count = available.sum(axis="columns").astype(float)
    return composite.rename("donor_composite"), effective_count.rename(
        "available_donors"
    )


def estimate_metadata_anchor(
    target: pd.Series,
    donors: pd.DataFrame,
    weights: pd.Series,
    anchor_date: pd.Timestamp | str,
    *,
    calibration_days: int = 180,
    calibration_buffer_days: int = 15,
    comparison_days: int = 60,
    min_window_observations: int = 30,
    min_available_donors: int = 2,
) -> MetaShiftEstimate:
    """Estimate the target's local discontinuity relative to fixed donors.

    Donor composition and weights must be selected using only data before the
    anchor. The function makes no causal claim about the mechanism producing a
    residual discontinuity.
    """

    if calibration_days <= calibration_buffer_days:
        raise ValueError("calibration_days must exceed calibration_buffer_days.")
    if comparison_days <= 0 or min_window_observations <= 0:
        raise ValueError("Window sizes must be positive.")

    target = target.astype(float).sort_index()
    donors = donors.sort_index()
    _require_datetime_index(target)
    _require_datetime_index(donors)
    date = pd.Timestamp(anchor_date)

    donor_log, available_donors = weighted_donor_series(donors, weights, True)
    donor_raw, _ = weighted_donor_series(donors, weights, False)
    target_log = np.log1p(target.clip(lower=0.0)).rename("target_log")

    table = pd.concat(
        [
            target.rename("target_raw"),
            target_log,
            donor_raw.rename("donor_raw"),
            donor_log.rename("donor_log"),
            available_donors,
        ],
        axis="columns",
        sort=False,
    )
    table = table.loc[table["available_donors"] >= min_available_donors].dropna(
        subset=["target_raw", "target_log", "donor_raw", "donor_log"]
    )

    calibration_start = date - pd.Timedelta(days=calibration_days)
    calibration_end = date - pd.Timedelta(days=calibration_buffer_days)
    pre_start = date - pd.Timedelta(days=comparison_days)
    pre_end = date - pd.Timedelta(days=1)
    post_end = date + pd.Timedelta(days=comparison_days - 1)

    calibration = table.loc[calibration_start:calibration_end].copy()
    pre = table.loc[pre_start:pre_end].copy()
    post = table.loc[date:post_end].copy()
    if (
        len(calibration) < min_window_observations
        or len(pre) < min_window_observations
        or len(post) < min_window_observations
    ):
        raise ValueError(
            "Insufficient observations for calibration or anchor comparison windows."
        )

    calibration_log_offset = float(
        np.median(calibration["target_log"] - calibration["donor_log"])
    )
    calibration_raw_offset = float(
        np.median(calibration["target_raw"] - calibration["donor_raw"])
    )
    table["log_residual"] = (
        table["target_log"] - table["donor_log"] - calibration_log_offset
    )
    table["raw_residual"] = (
        table["target_raw"] - table["donor_raw"] - calibration_raw_offset
    )

    calibration_residuals = table.loc[
        calibration_start:calibration_end, "log_residual"
    ]
    pre_residuals = table.loc[pre_start:pre_end, "log_residual"]
    post_residuals = table.loc[date:post_end, "log_residual"]
    log_effect = float(np.median(post_residuals) - np.median(pre_residuals))
    raw_effect = float(
        np.median(table.loc[date:post_end, "raw_residual"])
        - np.median(table.loc[pre_start:pre_end, "raw_residual"])
    )
    residual_scale = _robust_scale(calibration_residuals)

    return MetaShiftEstimate(
        anchor_date=date,
        calibration_observations=len(calibration),
        pre_observations=len(pre),
        post_observations=len(post),
        mean_available_donors=float(
            pd.concat([pre["available_donors"], post["available_donors"]]).mean()
        ),
        log_effect=log_effect,
        relative_effect=float(np.expm1(log_effect)),
        raw_effect=raw_effect,
        standardized_score=log_effect / residual_scale,
        calibration_residual_scale=residual_scale,
        calibration_residual_rmse=float(
            np.sqrt(np.mean(np.square(calibration_residuals)))
        ),
    )
