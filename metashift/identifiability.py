"""Theorem-aligned contracts for the v0.4 identifiability benchmark.

These helpers are deliberately separate from the frozen v0.3.2 raw-scale
perturbation generator.  They construct matched local/regional alternatives on
the estimator's log scale, where their algebraic properties are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AnalysisScaleScopePair:
    """Matched local and regional alternatives sharing one target realization."""

    pair_id: str
    anchor_date: pd.Timestamp
    schedule: pd.Series
    schedule_sha256: str
    random_seed: int | None
    local_target: pd.Series
    local_donors: pd.DataFrame
    regional_target: pd.Series
    regional_donors: pd.DataFrame


def _validate_index(index: pd.DatetimeIndex, name: str) -> None:
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex.")
    if not index.is_monotonic_increasing:
        raise ValueError(f"{name} must be sorted by date.")


def paired_schedule_seed(pair_id: str, *, base_seed: int = 20_260_901) -> int:
    """Derive an arm-invariant random seed from a declared pair identifier."""

    if not isinstance(pair_id, str) or not pair_id.strip():
        raise ValueError("pair_id must be nonempty.")
    if base_seed < 0:
        raise ValueError("base_seed cannot be negative.")
    payload = f"{base_seed}:{pair_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % (2**32)


def schedule_sha256(schedule: pd.Series) -> str:
    """Return a canonical hash for a declared analysis-scale schedule."""

    if not isinstance(schedule, pd.Series):
        raise TypeError("schedule must be a pandas Series.")
    _validate_index(schedule.index, "schedule")
    values = schedule.astype(float)
    if values.isna().any() or not np.isfinite(values.to_numpy()).all():
        raise ValueError("schedule must contain only finite values.")
    payload = "\n".join(
        f"{date.isoformat()}:{float(value).hex()}"
        for date, value in values.items()
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def shared_analysis_scale_noise(
    index: pd.DatetimeIndex,
    anchor_date: pd.Timestamp | str,
    pair_id: str,
    standard_deviation: float,
    *,
    base_seed: int = 20_260_901,
) -> tuple[pd.Series, int]:
    """Create one paired, zero-pre-anchor stochastic analysis-scale schedule.

    The caller passes the resulting schedule to both arms of
    :func:`build_analysis_scale_scope_pair`; the arm label is intentionally not
    an input to the seed rule.
    """

    _validate_index(index, "index")
    date = pd.Timestamp(anchor_date)
    if date not in index:
        raise ValueError("anchor_date must be observed in the schedule index.")
    if standard_deviation <= 0:
        raise ValueError("standard_deviation must be positive.")

    seed = paired_schedule_seed(pair_id, base_seed=base_seed)
    schedule = pd.Series(0.0, index=index, name="analysis_scale_increment")
    post_mask = index >= date
    schedule.loc[post_mask] = np.random.default_rng(seed).normal(
        0.0, standard_deviation, int(post_mask.sum())
    )
    return schedule, seed


def clipped_log(values: pd.Series | pd.DataFrame | np.ndarray) -> object:
    """Mirror the primary estimator's ``log1p(clip(lower=0))`` transform."""

    if isinstance(values, (pd.Series, pd.DataFrame)):
        return np.log1p(values.clip(lower=0.0))
    return np.log1p(np.maximum(np.asarray(values, dtype=float), 0.0))


def raw_additive_log_increment(
    values: pd.Series | pd.DataFrame | np.ndarray, magnitude: float
) -> object:
    """Return the implemented-scale increment from a raw additive change."""

    if not np.isfinite(magnitude):
        raise ValueError("magnitude must be finite.")
    return clipped_log(np.asarray(values, dtype=float) + magnitude) - clipped_log(values)


def raw_proportional_log_increment(
    values: pd.Series | pd.DataFrame | np.ndarray, proportion: float
) -> object:
    """Return the implemented-scale increment from a raw proportional change."""

    if proportion < 0 or not np.isfinite(proportion):
        raise ValueError("proportion must be finite and nonnegative.")
    return clipped_log((1.0 + proportion) * np.asarray(values, dtype=float)) - clipped_log(
        values
    )


def additive_increment_lipschitz_constant(
    magnitude: float, *, nonnegative_lower_bound: float | None = None
) -> float:
    """Return a valid Lipschitz constant for the raw additive log increment.

    With the estimator's clipping rule, one is globally valid for every finite
    raw input.  When all compared raw values are known nonnegative and bounded
    below by ``nonnegative_lower_bound``, the sharper differentiable-domain
    constant is valid.
    """

    if not np.isfinite(magnitude):
        raise ValueError("magnitude must be finite.")
    if nonnegative_lower_bound is None:
        return 1.0
    if magnitude < 0:
        raise ValueError(
            "The sharper nonnegative-domain constant requires a nonnegative magnitude."
        )
    if nonnegative_lower_bound < 0:
        raise ValueError("nonnegative_lower_bound cannot be negative.")
    return magnitude / (
        (1.0 + nonnegative_lower_bound + magnitude)
        * (1.0 + nonnegative_lower_bound)
    )


def proportional_increment_lipschitz_constant(proportion: float) -> float:
    """Return a global Lipschitz constant for a nonnegative proportional change."""

    if proportion < 0 or not np.isfinite(proportion):
        raise ValueError("proportion must be finite and nonnegative.")
    return proportion


def _validate_scope_inputs(
    target: pd.Series, donors: pd.DataFrame, anchor_date: pd.Timestamp | str
) -> tuple[pd.Series, pd.DataFrame, pd.Timestamp]:
    _validate_index(target.index, "target")
    _validate_index(donors.index, "donors")
    if not target.index.equals(donors.index):
        raise ValueError(
            "The exact analysis-scale contract requires aligned target and donor dates."
        )
    if donors.empty:
        raise ValueError("At least one donor is required.")
    date = pd.Timestamp(anchor_date)
    if date not in target.index:
        raise ValueError("anchor_date must be observed in the target index.")
    return target.astype(float).copy(), donors.astype(float).copy(), date


def build_analysis_scale_scope_pair(
    target: pd.Series,
    donors: pd.DataFrame,
    anchor_date: pd.Timestamp | str,
    schedule: pd.Series,
    pair_id: str,
    *,
    random_seed: int | None = None,
) -> AnalysisScaleScopePair:
    """Build a matched local/regional pair with exact log-residual cancellation.

    ``schedule`` is added to the target's analysis-scale path in both arms.  It
    is also added to every donor's analysis-scale path in the regional arm.
    The schedule must be zero before the anchor, and the inverse transform must
    remain in the valid nonnegative raw domain for every observed affected value.
    """

    if not isinstance(pair_id, str) or not pair_id.strip():
        raise ValueError("pair_id must be nonempty.")
    target, donors, date = _validate_scope_inputs(target, donors, anchor_date)
    if not schedule.index.equals(target.index):
        raise ValueError("schedule index must exactly match the target index.")
    schedule = schedule.astype(float).copy()
    schedule_hash = schedule_sha256(schedule)
    if random_seed is not None and random_seed != paired_schedule_seed(pair_id):
        raise ValueError(
            "random_seed must equal the pair_id-derived seed when it is recorded."
        )
    if (schedule.loc[schedule.index < date] != 0.0).any():
        raise ValueError("schedule must be exactly zero before the anchor.")

    target_log = clipped_log(target)
    donor_log = clipped_log(donors)
    assert isinstance(target_log, pd.Series)
    assert isinstance(donor_log, pd.DataFrame)
    shifted_target = target_log.add(schedule)
    shifted_donors = donor_log.add(schedule, axis="index")
    invalid_target = shifted_target.notna() & (shifted_target < 0.0)
    invalid_donors = shifted_donors.notna() & (shifted_donors < 0.0)
    if invalid_target.any() or invalid_donors.to_numpy().any():
        raise ValueError(
            "schedule would leave the exact analysis-scale inverse-transform domain."
        )

    changed = schedule != 0.0
    changed_target = target.copy()
    changed_target.loc[changed] = np.expm1(shifted_target.loc[changed])
    changed_regional_donors = donors.copy()
    changed_regional_donors.loc[changed, :] = np.expm1(
        shifted_donors.loc[changed, :]
    )

    return AnalysisScaleScopePair(
        pair_id=pair_id,
        anchor_date=date,
        schedule=schedule,
        schedule_sha256=schedule_hash,
        random_seed=random_seed,
        local_target=changed_target.copy(),
        local_donors=donors.copy(),
        regional_target=changed_target.copy(),
        regional_donors=changed_regional_donors,
    )
