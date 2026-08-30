"""Quality-gated, placebo-calibrated residual attribution for MetaShift v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from metashift.counterfactual import weighted_donor_series


class AttributionShape(StrEnum):
    LEVEL = "level"
    DRIFT = "drift"
    VARIANCE = "variance"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class QualityGate:
    """Pre-event reliability diagnostics and the abstention decision."""

    passed: bool
    reason: str | None
    paired_pre_observations: int
    effective_donor_count: float
    maximum_donor_weight: float
    pre_residual_scale: float
    pre_residual_rmse: float


@dataclass(frozen=True)
class ResidualAttribution:
    """A shape score based solely on counterfactual residuals at one anchor."""

    shape: AttributionShape
    level_effect: float
    drift_per_day: float
    log_variance_ratio: float
    score: float
    persistence: float


def _robust_scale(values: pd.Series) -> float:
    values = values.dropna().to_numpy(dtype=float)
    if len(values) == 0:
        raise ValueError("Cannot calculate scale for an empty residual series.")
    median = float(np.median(values))
    return max(1.4826 * float(np.median(np.abs(values - median))), 1e-8)


def residual_series(
    target: pd.Series, donors: pd.DataFrame, weights: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Build calibrated log residuals and available-donor counts without leakage."""

    target = target.astype(float).sort_index()
    donors = donors.astype(float).sort_index()
    if not isinstance(target.index, pd.DatetimeIndex):
        raise TypeError("Target index must be a DatetimeIndex.")
    donor_log, donor_count = weighted_donor_series(donors, weights, logarithmic=True)
    target_log = np.log1p(target.clip(lower=0.0))
    return (target_log - donor_log).rename("log_residual"), donor_count


def evaluate_quality_gate(
    target: pd.Series,
    donors: pd.DataFrame,
    weights: pd.Series,
    anchor_date: pd.Timestamp | str,
    *,
    calibration_days: int = 180,
    calibration_buffer_days: int = 15,
    min_paired_observations: int = 60,
    min_effective_donors: float = 2.0,
    max_donor_weight: float = 0.80,
    max_pre_residual_rmse: float = 0.25,
) -> QualityGate:
    """Gate an event using pre-anchor fit only; failures return abstention evidence."""

    if not 0 < max_donor_weight <= 1:
        raise ValueError("max_donor_weight must be in (0, 1].")
    date = pd.Timestamp(anchor_date)
    residuals, donor_count = residual_series(target, donors, weights)
    start = date - pd.Timedelta(days=calibration_days)
    end = date - pd.Timedelta(days=calibration_buffer_days)
    pre = pd.concat(
        [residuals.rename("residual"), donor_count.rename("donors")],
        axis="columns",
        sort=False,
    ).loc[start:end]
    pre = pre.loc[pre["donors"] >= min_effective_donors].dropna()
    paired = len(pre)
    effective_donors = float(1 / np.square(weights).sum())
    maximum_weight = float(weights.max())
    if paired == 0:
        return QualityGate(
            False, "no_complete_pre_event_residuals", 0, effective_donors,
            maximum_weight, np.nan, np.nan
        )
    scale = _robust_scale(pre["residual"])
    rmse = float(np.sqrt(np.mean(np.square(pre["residual"] - np.median(pre["residual"])))))
    if paired < min_paired_observations:
        reason = "insufficient_paired_pre_event_observations"
    elif effective_donors < min_effective_donors:
        reason = "too_few_effective_donors"
    elif maximum_weight > max_donor_weight:
        reason = "dominant_donor_weight"
    elif rmse > max_pre_residual_rmse:
        reason = "poor_pre_event_counterfactual_fit"
    else:
        reason = None
    return QualityGate(
        reason is None, reason, paired, effective_donors, maximum_weight, scale, rmse
    )


def attribute_residual_shape(
    residuals: pd.Series,
    anchor_date: pd.Timestamp | str,
    *,
    pre_days: int = 60,
    post_days: int = 60,
    min_observations: int = 30,
) -> ResidualAttribution:
    """Fit transparent level, drift, and variance evidence scores at an anchor."""

    if pre_days <= 0 or post_days <= 0:
        raise ValueError("Residual comparison windows must be positive.")
    date = pd.Timestamp(anchor_date)
    residuals = residuals.sort_index().dropna()
    pre = residuals.loc[date - pd.Timedelta(days=pre_days) : date - pd.Timedelta(days=1)]
    post = residuals.loc[date : date + pd.Timedelta(days=post_days - 1)]
    if len(pre) < min_observations or len(post) < min_observations:
        raise ValueError("Insufficient residual observations for shape attribution.")
    pre_median = float(np.median(pre))
    post_median = float(np.median(post))
    scale = _robust_scale(pre)
    level_effect = post_median - pre_median

    post_elapsed = (post.index - date).days.to_numpy(dtype=float)
    drift_per_day = float(np.polyfit(post_elapsed, post.to_numpy(dtype=float), 1)[0])
    pre_scale = _robust_scale(pre)
    post_scale = _robust_scale(post)
    log_variance_ratio = float(np.log(post_scale / pre_scale))

    thirds = np.array_split(post.to_numpy(dtype=float), 3)
    level_sign = np.sign(level_effect)
    persistence = float(
        np.mean(
            [
                np.sign(float(np.median(segment) - pre_median)) == level_sign
                for segment in thirds
                if len(segment) > 0
            ]
        )
    )
    candidates = {
        AttributionShape.LEVEL: abs(level_effect) / scale * persistence,
        AttributionShape.DRIFT: abs(drift_per_day) * post_days / scale,
        AttributionShape.VARIANCE: abs(log_variance_ratio),
    }
    shape, score = max(candidates.items(), key=lambda item: item[1])
    return ResidualAttribution(
        shape=shape,
        level_effect=level_effect,
        drift_per_day=drift_per_day,
        log_variance_ratio=log_variance_ratio,
        score=float(score),
        persistence=persistence,
    )


def placebo_p_value(observed_score: float, placebo_scores: np.ndarray | list[float]) -> float:
    """Compute the finite-sample upper-tail placebo probability."""

    scores = np.asarray(placebo_scores, dtype=float)
    scores = scores[np.isfinite(scores)]
    if len(scores) == 0:
        raise ValueError("At least one finite placebo score is required.")
    return float((1 + np.count_nonzero(scores >= observed_score)) / (1 + len(scores)))
