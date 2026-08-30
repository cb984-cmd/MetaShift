"""Controlled local and regional perturbations for MetaShift evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd


class PerturbationKind(StrEnum):
    ADDITIVE_STEP = "additive_step"
    PROPORTIONAL_STEP = "proportional_step"
    GRADUAL_DRIFT = "gradual_drift"
    TEMPORARY_STEP = "temporary_step"
    VARIANCE_INCREASE = "variance_increase"
    REGIONAL_ADDITIVE_STEP = "regional_additive_step"
    REGIONAL_PROPORTIONAL_STEP = "regional_proportional_step"


@dataclass(frozen=True)
class SyntheticTruth:
    """Known perturbation metadata for one reproducible evaluation event."""

    kind: PerturbationKind
    anchor_date: pd.Timestamp
    affected_columns: tuple[str, ...]
    affected_end_date: pd.Timestamp | None
    magnitude: float
    random_seed: int


def _validate_inputs(
    target: pd.Series, donors: pd.DataFrame, anchor_date: pd.Timestamp | str
) -> tuple[pd.Series, pd.DataFrame, pd.Timestamp]:
    if not isinstance(target.index, pd.DatetimeIndex) or not isinstance(
        donors.index, pd.DatetimeIndex
    ):
        raise TypeError("Synthetic inputs must use a DatetimeIndex.")
    if not target.index.is_monotonic_increasing or not donors.index.is_monotonic_increasing:
        raise ValueError("Synthetic inputs must be sorted by date.")
    date = pd.Timestamp(anchor_date)
    if date not in target.index:
        raise ValueError("The synthetic anchor date must be observed for the target.")
    if target.loc[date:].empty:
        raise ValueError("The target has no observations after the synthetic anchor.")
    return target.astype(float).copy(), donors.astype(float).copy(), date


def inject_perturbation(
    target: pd.Series,
    donors: pd.DataFrame,
    anchor_date: pd.Timestamp | str,
    kind: PerturbationKind | str,
    magnitude: float,
    *,
    duration_days: int = 30,
    drift_days: int = 30,
    random_seed: int = 0,
) -> tuple[pd.Series, pd.DataFrame, SyntheticTruth]:
    """Inject a known target-only or shared regional perturbation.

    `magnitude` is in concentration units for additive steps and standard
    deviation increases; it is a fractional change for proportional effects.
    The original inputs remain unchanged.
    """

    target, donors, date = _validate_inputs(target, donors, anchor_date)
    perturbation = PerturbationKind(kind)
    if magnitude <= 0:
        raise ValueError("Synthetic perturbation magnitude must be positive.")
    if duration_days <= 0 or drift_days <= 0:
        raise ValueError("Synthetic durations must be positive.")

    post_mask = target.index >= date
    donor_post_mask = donors.index >= date
    affected_end_date: pd.Timestamp | None = None
    affected_columns: tuple[str, ...] = ("target",)
    rng = np.random.default_rng(random_seed)

    if perturbation is PerturbationKind.ADDITIVE_STEP:
        target.loc[post_mask] += magnitude
    elif perturbation is PerturbationKind.PROPORTIONAL_STEP:
        target.loc[post_mask] *= 1 + magnitude
    elif perturbation is PerturbationKind.GRADUAL_DRIFT:
        elapsed = (target.index[post_mask] - date).days.to_numpy()
        ramp = np.minimum(elapsed / drift_days, 1.0)
        target.loc[post_mask] += magnitude * ramp
    elif perturbation is PerturbationKind.TEMPORARY_STEP:
        affected_end_date = date + pd.Timedelta(days=duration_days - 1)
        temporary_mask = (target.index >= date) & (target.index <= affected_end_date)
        target.loc[temporary_mask] += magnitude
    elif perturbation is PerturbationKind.VARIANCE_INCREASE:
        pre_values = target.loc[target.index < date].dropna().to_numpy()
        if len(pre_values) < 30:
            raise ValueError("Variance injection requires at least 30 pre-anchor values.")
        noise_scale = magnitude * (1.4826 * np.median(np.abs(pre_values - np.median(pre_values))))
        target.loc[post_mask] += rng.normal(0, noise_scale, post_mask.sum())
    elif perturbation is PerturbationKind.REGIONAL_ADDITIVE_STEP:
        target.loc[post_mask] += magnitude
        donors.loc[donor_post_mask, :] += magnitude
        affected_columns = ("target", *map(str, donors.columns))
    elif perturbation is PerturbationKind.REGIONAL_PROPORTIONAL_STEP:
        target.loc[post_mask] *= 1 + magnitude
        donors.loc[donor_post_mask, :] *= 1 + magnitude
        affected_columns = ("target", *map(str, donors.columns))
    else:
        raise AssertionError(f"Unhandled perturbation kind: {perturbation}")

    truth = SyntheticTruth(
        kind=perturbation,
        anchor_date=date,
        affected_columns=affected_columns,
        affected_end_date=affected_end_date,
        magnitude=magnitude,
        random_seed=random_seed,
    )
    return target, donors, truth
