"""Scope-answerability helpers for the independent v0.5 synthetic protocol."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

import numpy as np
import pandas as pd

from metashift.counterfactual import anchor_residual_windows
from metashift.identifiability import additive_increment_lipschitz_constant


@dataclass(frozen=True)
class PartialScopePair:
    """Matched local/shared observations with exactly one shared target path."""

    target: pd.Series
    local_donors: pd.DataFrame
    shared_donors: pd.DataFrame
    local_donors_before_raw_field: pd.DataFrame
    shared_donors_before_raw_field: pd.DataFrame


@dataclass(frozen=True)
class StructuralCertificate:
    """A bounded synthetic-design separation decision for one scope arm."""

    lower_gap: float
    structural_margin: float
    threshold: float
    answered: bool
    predicts_local: bool | None


@dataclass(frozen=True)
class ConfidenceCutoff:
    """A calibration-selected confidence cutoff for one risk tolerance."""

    alpha: float
    cutoff: float
    calibration_coverage: float
    calibration_conditional_error: float | None
    status: str


def _require_datetime_index(values: pd.Series | pd.DataFrame, name: str) -> None:
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex.")
    if not values.index.is_monotonic_increasing:
        raise ValueError(f"{name} must be sorted by date.")
    if values.index.has_duplicates:
        raise ValueError(f"{name} must not contain duplicate dates.")


def _validate_raw_panel(target: pd.Series, donors: pd.DataFrame) -> None:
    _require_datetime_index(target, "target")
    _require_datetime_index(donors, "donors")
    if not target.index.equals(donors.index):
        raise ValueError("target and donors must share exactly the same date index.")
    if donors.empty:
        raise ValueError("at least one donor is required.")
    target_values = target.to_numpy(dtype=float)
    donor_values = donors.to_numpy(dtype=float)
    if not np.isfinite(target_values).all() or (target_values < 0.0).any():
        raise ValueError("target must contain finite, nonnegative raw values.")
    if not (np.isnan(donor_values) | np.isfinite(donor_values)).all():
        raise ValueError("donors may be missing but cannot contain infinite values.")
    if (donor_values[np.isfinite(donor_values)] < 0.0).any():
        raise ValueError("finite donor values must be nonnegative.")


def _validate_weights(donors: pd.DataFrame, weights: pd.Series) -> pd.Series:
    if not isinstance(weights, pd.Series):
        raise TypeError("weights must be a pandas Series.")
    if not donors.columns.equals(weights.index):
        raise ValueError("weights index must exactly match donor columns and order.")
    result = weights.astype(float)
    if not np.isfinite(result.to_numpy()).all() or (result < 0.0).any():
        raise ValueError("weights must be finite and nonnegative.")
    if not np.isclose(float(result.sum()), 1.0, rtol=0.0, atol=1e-12):
        raise ValueError("weights must sum to one.")
    return result


def normalized_availability_weights(
    donors: pd.DataFrame, weights: pd.Series
) -> pd.DataFrame:
    """Return the date-specific fixed-weight normalization used by MetaShift."""

    _require_datetime_index(donors, "donors")
    selected_weights = _validate_weights(donors, weights)
    available = donors.notna()
    unnormalized = available.mul(selected_weights, axis="columns")
    totals = unnormalized.sum(axis="columns")
    if (totals <= 0.0).any():
        raise ValueError("at least one donor must be available on every date.")
    return unnormalized.div(totals, axis="index")


def effective_donor_participation(
    donors: pd.DataFrame, weights: pd.Series, participation: pd.DataFrame
) -> pd.Series:
    """Calculate q_t using the estimator's availability-normalized weights."""

    if not participation.index.equals(donors.index) or not participation.columns.equals(
        donors.columns
    ):
        raise ValueError("participation must align exactly with the donor panel.")
    values = participation.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0.0).any() or (values > 1.0).any():
        raise ValueError("participation values must be finite values in [0, 1].")
    normalized = normalized_availability_weights(donors, weights)
    return (normalized * participation).sum(axis="columns").rename(
        "effective_donor_participation"
    )


def _require_schedule(
    schedule: pd.Series, target: pd.Series, anchor_date: pd.Timestamp | str, name: str
) -> tuple[pd.Series, pd.Timestamp]:
    if not schedule.index.equals(target.index):
        raise ValueError(f"{name} must align exactly with the target index.")
    date = pd.Timestamp(anchor_date)
    if date not in target.index:
        raise ValueError("anchor_date must occur in the target index.")
    result = schedule.astype(float)
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError(f"{name} must contain only finite values.")
    if (result.loc[result.index < date] != 0.0).any():
        raise ValueError(f"{name} must be exactly zero before the anchor.")
    return result, date


def _apply_raw_field(values: pd.Series | pd.DataFrame, field: pd.Series) -> pd.Series | pd.DataFrame:
    if isinstance(values, pd.Series):
        return values.where(values.isna(), values + field)
    return values.add(field, axis="index").where(values.notna())


def _apply_log_contamination(
    donors: pd.DataFrame, contamination: pd.DataFrame
) -> pd.DataFrame:
    if not contamination.index.equals(donors.index) or not contamination.columns.equals(
        donors.columns
    ):
        raise ValueError("contamination must align exactly with the donor panel.")
    values = contamination.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("contamination must contain only finite values.")
    transformed = np.log1p(donors)
    changed = transformed.add(contamination)
    return np.expm1(changed).where(donors.notna())


def build_partial_scope_pair(
    target: pd.Series,
    donors: pd.DataFrame,
    anchor_date: pd.Timestamp | str,
    signal_schedule: pd.Series,
    participation: pd.DataFrame,
    raw_field: pd.Series,
    donor_log_contamination: pd.DataFrame,
) -> PartialScopePair:
    """Build target-fixed local and partial/shared raw observations.

    The target's analysis-scale schedule and raw field are constructed once, so
    the local and shared targets are bitwise identical. Donor contamination is
    applied after the raw field as an exact additive log-scale donor nuisance.
    """

    _validate_raw_panel(target, donors)
    schedule, date = _require_schedule(
        signal_schedule, target, anchor_date, "signal_schedule"
    )
    field, _ = _require_schedule(raw_field, target, anchor_date, "raw_field")
    if (field < 0.0).any():
        raise ValueError("raw_field must be nonnegative.")
    if not participation.index.equals(donors.index) or not participation.columns.equals(
        donors.columns
    ):
        raise ValueError("participation must align exactly with the donor panel.")
    participation_values = participation.to_numpy(dtype=float)
    if (
        not np.isfinite(participation_values).all()
        or (participation_values < 0.0).any()
        or (participation_values > 1.0).any()
    ):
        raise ValueError("participation values must be finite values in [0, 1].")
    if not donor_log_contamination.index.equals(donors.index) or not donor_log_contamination.columns.equals(
        donors.columns
    ):
        raise ValueError("donor_log_contamination must align exactly with the donor panel.")
    if (donor_log_contamination.loc[donor_log_contamination.index < date] != 0.0).to_numpy().any():
        raise ValueError("donor_log_contamination must be exactly zero before the anchor.")

    target_log = np.log1p(target)
    donor_log = np.log1p(donors)
    changed_target = np.expm1(target_log + schedule)
    local_before_raw = np.expm1(donor_log)
    shared_before_raw = np.expm1(donor_log + participation.mul(schedule, axis="index"))
    target_after_field = _apply_raw_field(changed_target, field)
    assert isinstance(target_after_field, pd.Series)
    local_after_field = _apply_raw_field(local_before_raw, field)
    shared_after_field = _apply_raw_field(shared_before_raw, field)
    assert isinstance(local_after_field, pd.DataFrame)
    assert isinstance(shared_after_field, pd.DataFrame)
    local_donors = _apply_log_contamination(
        local_after_field, donor_log_contamination
    )
    shared_donors = _apply_log_contamination(
        shared_after_field, donor_log_contamination
    )

    if (participation_values == 0.0).all():
        shared_donors = local_donors.copy()
        shared_before_raw = local_before_raw.copy()
    return PartialScopePair(
        target=target_after_field.copy(),
        local_donors=local_donors,
        shared_donors=shared_donors,
        local_donors_before_raw_field=local_before_raw,
        shared_donors_before_raw_field=shared_before_raw,
    )


def signed_mean_residual_effect(
    target: pd.Series,
    donors: pd.DataFrame,
    weights: pd.Series,
    anchor_date: pd.Timestamp | str,
    *,
    calibration_days: int,
    calibration_buffer_days: int,
    comparison_days: int,
    min_window_observations: int,
    min_available_donors: int,
) -> tuple[float, pd.DatetimeIndex, pd.DatetimeIndex]:
    """Return the v0.5 affine scope score and retained pre/post date indices."""

    windows = anchor_residual_windows(
        target,
        donors,
        weights,
        anchor_date,
        calibration_days=calibration_days,
        calibration_buffer_days=calibration_buffer_days,
        comparison_days=comparison_days,
        min_window_observations=min_window_observations,
        min_available_donors=min_available_donors,
    )
    score = float(
        windows.post["log_residual"].mean() - windows.pre["log_residual"].mean()
    )
    if not np.isfinite(score):
        raise ValueError("signed mean residual effect must be finite.")
    return score, windows.pre.index, windows.post.index


def raw_additive_mean_leakage_bound(
    target_before_field: pd.Series,
    donors_before_field: pd.DataFrame,
    weights: pd.Series,
    post_dates: Iterable[pd.Timestamp],
    magnitude: float,
) -> float:
    """Bound post-mean residual leakage from a nonnegative raw additive field."""

    _validate_raw_panel(target_before_field, donors_before_field)
    if not np.isfinite(magnitude) or magnitude < 0.0:
        raise ValueError("magnitude must be finite and nonnegative.")
    dates = pd.DatetimeIndex(post_dates)
    if dates.empty:
        raise ValueError("post_dates must not be empty.")
    if not dates.isin(target_before_field.index).all():
        raise ValueError("post_dates must be present in the target index.")
    target = target_before_field.loc[dates]
    donors = donors_before_field.loc[dates]
    normalized = normalized_availability_weights(donors, weights)
    available = donors.notna()
    target_array = target.to_numpy(dtype=float)
    donor_array = donors.to_numpy(dtype=float)
    valid_donor_values = donor_array[available.to_numpy()]
    if valid_donor_values.size == 0:
        raise ValueError("at least one donor must be available on every post date.")
    per_date_minimum = np.minimum(
        target_array,
        np.where(available.to_numpy(), donor_array, np.inf).min(axis=1),
    )
    constants = np.asarray(
        [
            additive_increment_lipschitz_constant(
                magnitude, nonnegative_lower_bound=float(lower)
            )
            for lower in per_date_minimum
        ],
        dtype=float,
    )
    mismatch = np.abs(target_array[:, np.newaxis] - donor_array)
    weighted_mismatch = np.nansum(
        normalized.to_numpy(dtype=float) * mismatch, axis=1
    )
    bound = float(np.mean(constants * weighted_mismatch))
    if not np.isfinite(bound) or bound < 0.0:
        raise ValueError("raw leakage bound must be finite and nonnegative.")
    return bound


def structural_error_bound(
    *,
    maximum_absolute_donor_offset: float,
    pre_noise_half_width: float,
    post_noise_half_width: float,
    raw_error_bound: float,
    contamination_error_bound: float,
) -> float:
    """Return the declared deterministic score envelope for one scope arm."""

    values = {
        "maximum_absolute_donor_offset": maximum_absolute_donor_offset,
        "pre_noise_half_width": pre_noise_half_width,
        "post_noise_half_width": post_noise_half_width,
        "raw_error_bound": raw_error_bound,
        "contamination_error_bound": contamination_error_bound,
    }
    for name, value in values.items():
        if not np.isfinite(value) or value < 0.0:
            raise ValueError(f"{name} must be finite and nonnegative.")
    base = 2.0 * maximum_absolute_donor_offset + 2.0 * (
        pre_noise_half_width + post_noise_half_width
    )
    return float(base + raw_error_bound + contamination_error_bound)


def structural_certificate(
    *,
    score: float,
    signal_h: float,
    gap_lower_bound: float,
    local_error_bound: float,
    shared_error_bound: float,
) -> StructuralCertificate:
    """Apply an interval-safe structural certificate to one finite score."""

    values = {
        "score": score,
        "signal_h": signal_h,
        "gap_lower_bound": gap_lower_bound,
        "local_error_bound": local_error_bound,
        "shared_error_bound": shared_error_bound,
    }
    for name, value in values.items():
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite.")
    if signal_h <= 0.0:
        raise ValueError("signal_h must be positive.")
    for name in ("gap_lower_bound", "local_error_bound", "shared_error_bound"):
        if values[name] < 0.0:
            raise ValueError(f"{name} must be nonnegative.")
    margin = gap_lower_bound - (local_error_bound + shared_error_bound)
    threshold = (
        signal_h
        - gap_lower_bound / 2.0
        + (shared_error_bound - local_error_bound) / 2.0
    )
    answered = bool(margin > 0.0)
    return StructuralCertificate(
        lower_gap=float(gap_lower_bound),
        structural_margin=float(margin),
        threshold=float(threshold),
        answered=answered,
        predicts_local=bool(score > threshold) if answered else None,
    )


def series_sha256(values: pd.Series) -> str:
    """Hash a target path canonically, including dates and IEEE float values."""

    _require_datetime_index(values, "values")
    array = values.to_numpy(dtype=float)
    if not np.isfinite(array).all():
        raise ValueError("series digest requires finite values.")
    dates = values.index.asi8.astype("<i8", copy=False)
    payload = dates.tobytes() + array.astype("<f8", copy=False).tobytes()
    return hashlib.sha256(payload).hexdigest()


def comparative_observation_identity(
    local_target: pd.Series,
    local_donors: pd.DataFrame,
    shared_target: pd.Series,
    shared_donors: pd.DataFrame,
) -> bool:
    """Return whether the entire target-plus-donor observation is identical."""

    if not local_target.index.equals(shared_target.index) or not local_donors.index.equals(
        shared_donors.index
    ):
        return False
    if not local_donors.columns.equals(shared_donors.columns):
        return False
    return bool(
        np.array_equal(
            local_target.to_numpy(dtype=float),
            shared_target.to_numpy(dtype=float),
            equal_nan=True,
        )
        and np.array_equal(
            local_donors.to_numpy(dtype=float),
            shared_donors.to_numpy(dtype=float),
            equal_nan=True,
        )
    )


def policy_summary(
    labels_are_local: np.ndarray,
    predictions_are_local: np.ndarray,
    answered: np.ndarray,
) -> dict[str, float | int | str | None]:
    """Summarize a binary scope policy without silently dropping abstentions."""

    labels = np.asarray(labels_are_local, dtype=bool)
    predictions = np.asarray(predictions_are_local, dtype=bool)
    answered_mask = np.asarray(answered, dtype=bool)
    if labels.shape != predictions.shape or labels.shape != answered_mask.shape:
        raise ValueError("labels, predictions, and answered must have matching shapes.")
    if labels.ndim != 1 or labels.size == 0:
        raise ValueError("policy summary requires a nonempty one-dimensional input.")
    total = int(labels.size)
    answered_count = int(answered_mask.sum())
    errors = int(
        (predictions[answered_mask] != labels[answered_mask]).sum()
    )
    if answered_count == 0:
        return {
            "total_events": total,
            "answered_events": answered_count,
            "coverage": 0.0,
            "error_events": errors,
            "conditional_error": None,
            "status": "no_answered_cases",
        }
    return {
        "total_events": total,
        "answered_events": answered_count,
        "coverage": float(answered_count / total),
        "error_events": errors,
        "conditional_error": float(errors / answered_count),
        "status": "complete",
    }


def select_confidence_cutoff(
    labels_are_local: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    alpha: float,
    *,
    quantile_count: int,
) -> ConfidenceCutoff:
    """Choose a calibration-only confidence cutoff with fixed tie-breaking."""

    labels = np.asarray(labels_are_local, dtype=bool)
    score_values = np.asarray(scores, dtype=float)
    if labels.shape != score_values.shape or labels.ndim != 1 or labels.size == 0:
        raise ValueError("labels and scores must be matching nonempty vectors.")
    if not np.isfinite(score_values).all() or not np.isfinite(threshold):
        raise ValueError("scores and threshold must be finite.")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be strictly between zero and one.")
    if quantile_count < 2:
        raise ValueError("quantile_count must be at least two.")
    predictions = score_values >= threshold
    confidence = np.abs(score_values - threshold)
    quantiles = np.linspace(0.0, 1.0, quantile_count)
    candidates = np.unique(np.quantile(confidence, quantiles, method="linear"))
    qualifying: list[tuple[float, float, float]] = []
    for cutoff in candidates:
        summary = policy_summary(labels, predictions, confidence >= cutoff)
        error = summary["conditional_error"]
        if error is not None and float(error) <= alpha:
            qualifying.append(
                (
                    float(summary["coverage"]),
                    float(cutoff),
                    float(error),
                )
            )
    if not qualifying:
        return ConfidenceCutoff(
            alpha=float(alpha),
            cutoff=float("inf"),
            calibration_coverage=0.0,
            calibration_conditional_error=None,
            status="always_abstain",
        )
    coverage, cutoff, error = max(qualifying, key=lambda item: (item[0], item[1]))
    return ConfidenceCutoff(
        alpha=float(alpha),
        cutoff=cutoff,
        calibration_coverage=coverage,
        calibration_conditional_error=error,
        status="complete",
    )
