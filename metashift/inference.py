"""Deterministic block-bootstrap inference for fixed-counterfactual effects."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from scipy.optimize import minimize


@dataclass(frozen=True)
class BootstrapInterval:
    """A conditional bootstrap interval for an anchored residual effect."""

    point_estimate: float
    lower_95: float
    upper_95: float
    repetitions: int
    block_length: int
    random_seed: int


@dataclass(frozen=True)
class NestedSelectionInterval:
    """A selection-aware interval with donor re-selection in every replicate."""

    point_estimate: float
    lower_95: float
    upper_95: float
    valid_repetitions: int
    invalid_reselection_or_refit_repetitions: int
    invalid_effect_repetitions: int
    median_selected_donor_count: float
    random_seed: int
    block_length: int


def seed_from_identifier(identifier: str, base_seed: int = 20_260_830) -> int:
    """Derive an OS-independent deterministic random seed from an event ID."""

    digest = hashlib.sha256(identifier.encode("utf-8")).digest()
    return base_seed + int.from_bytes(digest[:4], byteorder="big")


def _block_resample(
    values: np.ndarray, repetitions: int, block_length: int, rng: np.random.Generator
) -> np.ndarray:
    """Return circular moving-block bootstrap samples of a one-dimensional series."""

    if values.ndim != 1 or len(values) == 0:
        raise ValueError("Bootstrap values must be a nonempty one-dimensional array.")
    blocks = int(np.ceil(len(values) / block_length))
    starts = rng.integers(0, len(values), size=(repetitions, blocks))
    offsets = np.arange(block_length)
    indices = (
        (starts[:, :, np.newaxis] + offsets) % len(values)
    ).reshape(repetitions, -1)
    return values[indices[:, : len(values)]]


def circular_block_indices(
    length: int, block_length: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw one circular moving-block index sequence with the original length."""

    if length <= 0 or block_length <= 0:
        raise ValueError("Block-bootstrap lengths must be positive.")
    blocks = int(np.ceil(length / block_length))
    starts = rng.integers(0, length, size=blocks)
    offsets = np.arange(block_length)
    return ((starts[:, np.newaxis] + offsets) % length).reshape(-1)[:length]


def _log_matrix(values: np.ndarray) -> np.ndarray:
    return np.log1p(np.maximum(values.astype(float), 0.0))


def _select_and_fit_weights(
    calibration: np.ndarray,
    distances_km: np.ndarray,
    *,
    minimum_pair_days: int,
    minimum_correlation: float,
    minimum_selected_donors: int,
    maximum_selected_donors: int,
    ridge_penalty: float,
    prior_penalty: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Select donors and fit weights from a resampled pre-event matrix.

    Column 0 is the target; the remaining columns correspond one-to-one to
    `distances_km`. This function sees no anchor-post data.
    """

    if calibration.ndim != 2 or calibration.shape[1] != len(distances_km) + 1:
        raise ValueError("Calibration matrix and distance vector dimensions disagree.")
    target = calibration[:, 0]
    donor_matrix = calibration[:, 1:]
    correlations = np.full(donor_matrix.shape[1], np.nan)
    pair_counts = np.zeros(donor_matrix.shape[1], dtype=int)
    target_log = _log_matrix(target)
    for index in range(donor_matrix.shape[1]):
        donor = donor_matrix[:, index]
        paired = np.isfinite(target) & np.isfinite(donor)
        pair_counts[index] = int(paired.sum())
        if pair_counts[index] < minimum_pair_days:
            continue
        donor_log = _log_matrix(donor[paired])
        paired_target = target_log[paired]
        if np.std(paired_target) == 0 or np.std(donor_log) == 0:
            continue
        correlations[index] = np.corrcoef(paired_target, donor_log)[0, 1]

    eligible = np.flatnonzero(
        np.isfinite(correlations) & (correlations >= minimum_correlation)
    )
    if len(eligible) < minimum_selected_donors:
        return None
    order = eligible[
        np.lexsort((distances_km[eligible], -correlations[eligible]))
    ]
    selected = order[:maximum_selected_donors]
    selected_values = donor_matrix[:, selected]
    complete = np.isfinite(target) & np.isfinite(selected_values).all(axis=1)
    if int(complete.sum()) < minimum_pair_days:
        return None

    target_fit = _log_matrix(target[complete])
    donor_fit = _log_matrix(selected_values[complete])
    target_fit = target_fit - target_fit.mean()
    donor_fit = donor_fit - donor_fit.mean(axis=0)
    prior = np.clip(correlations[selected], 0.0, None) ** 2 * np.exp(
        -distances_km[selected] / 50.0
    )
    prior_total = float(prior.sum())
    if prior_total <= 0 or not np.isfinite(prior_total):
        return None
    prior /= prior_total

    def objective(weights: np.ndarray) -> float:
        residual = target_fit - donor_fit @ weights
        return float(
            np.mean(np.square(residual))
            + ridge_penalty * np.square(weights).sum()
            + prior_penalty * np.square(weights - prior).sum()
        )

    solution = minimize(
        objective,
        x0=prior,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * len(selected),
        constraints={"type": "eq", "fun": lambda weights: weights.sum() - 1.0},
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not solution.success:
        return None
    return selected, solution.x


def _effect_for_weights(
    calibration: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
    selected: np.ndarray,
    weights: np.ndarray,
    *,
    minimum_effect_observations: int,
) -> float | None:
    """Estimate a calibrated post-minus-pre residual effect from three matrices."""

    def residuals(values: np.ndarray) -> np.ndarray:
        target = values[:, 0]
        donors = values[:, selected + 1]
        target_log = _log_matrix(target)
        donor_log = _log_matrix(donors)
        available = np.isfinite(donors)
        weight_sums = available @ weights
        composite = np.divide(
            np.where(available, donor_log, 0.0) @ weights,
            weight_sums,
            out=np.full(len(target), np.nan),
            where=weight_sums > 0,
        )
        valid = np.isfinite(target) & (available.sum(axis=1) >= 2)
        output = target_log - composite
        output[~valid] = np.nan
        return output

    calibration_residuals = residuals(calibration)
    pre_residuals = residuals(pre)
    post_residuals = residuals(post)
    calibration_residuals = calibration_residuals[np.isfinite(calibration_residuals)]
    pre_residuals = pre_residuals[np.isfinite(pre_residuals)]
    post_residuals = post_residuals[np.isfinite(post_residuals)]
    if (
        len(calibration_residuals) < minimum_effect_observations
        or len(pre_residuals) < minimum_effect_observations
        or len(post_residuals) < minimum_effect_observations
    ):
        return None
    calibration_offset = float(np.median(calibration_residuals))
    return float(
        np.median(post_residuals - calibration_offset)
        - np.median(pre_residuals - calibration_offset)
    )


def nested_selection_block_bootstrap(
    calibration: np.ndarray,
    pre: np.ndarray,
    post: np.ndarray,
    distances_km: np.ndarray,
    *,
    repetitions: int = 1_000,
    block_length: int = 7,
    minimum_pair_days: int = 60,
    minimum_correlation: float = 0.60,
    minimum_selected_donors: int = 3,
    maximum_selected_donors: int = 5,
    minimum_effect_observations: int = 30,
    ridge_penalty: float = 0.1,
    prior_penalty: float = 0.1,
    random_seed: int = 20_260_830,
) -> NestedSelectionInterval:
    """Bootstrap selection, fitting, and residual effects without post-event fitting.

    Candidate donors must have been defined from geography, method stability,
    and data availability before this function runs. Each repetition jointly
    block-resamples target and candidate donor observations in the calibration
    period, recomputes correlation eligibility, selects up to five donors,
    refits nonnegative reliability-constrained weights, and independently
    block-resamples pre/post comparison windows for the effect calculation.
    """

    for name, matrix in (("calibration", calibration), ("pre", pre), ("post", post)):
        if matrix.ndim != 2 or matrix.shape[1] != len(distances_km) + 1:
            raise ValueError(f"{name} matrix and distance vector dimensions disagree.")
    if repetitions <= 0 or block_length <= 0:
        raise ValueError("Bootstrap repetitions and block length must be positive.")
    if not 0 < minimum_selected_donors <= maximum_selected_donors:
        raise ValueError("Selected donor bounds are invalid.")

    point_fit = _select_and_fit_weights(
        calibration,
        distances_km,
        minimum_pair_days=minimum_pair_days,
        minimum_correlation=minimum_correlation,
        minimum_selected_donors=minimum_selected_donors,
        maximum_selected_donors=maximum_selected_donors,
        ridge_penalty=ridge_penalty,
        prior_penalty=prior_penalty,
    )
    if point_fit is None:
        raise ValueError("Observed data cannot select and fit the nested donor model.")
    point_selected, point_weights = point_fit
    point_estimate = _effect_for_weights(
        calibration,
        pre,
        post,
        point_selected,
        point_weights,
        minimum_effect_observations=minimum_effect_observations,
    )
    if point_estimate is None:
        raise ValueError("Observed data cannot estimate the nested donor-model effect.")

    rng = np.random.default_rng(random_seed)
    effects: list[float] = []
    selected_counts: list[int] = []
    invalid_reselection_or_refit = 0
    invalid_effect = 0
    for _ in range(repetitions):
        calibration_sample = calibration[
            circular_block_indices(len(calibration), block_length, rng)
        ]
        pre_sample = pre[circular_block_indices(len(pre), block_length, rng)]
        post_sample = post[circular_block_indices(len(post), block_length, rng)]
        fitted = _select_and_fit_weights(
            calibration_sample,
            distances_km,
            minimum_pair_days=minimum_pair_days,
            minimum_correlation=minimum_correlation,
            minimum_selected_donors=minimum_selected_donors,
            maximum_selected_donors=maximum_selected_donors,
            ridge_penalty=ridge_penalty,
            prior_penalty=prior_penalty,
        )
        if fitted is None:
            invalid_reselection_or_refit += 1
            continue
        selected, weights = fitted
        effect = _effect_for_weights(
            calibration_sample,
            pre_sample,
            post_sample,
            selected,
            weights,
            minimum_effect_observations=minimum_effect_observations,
        )
        if effect is None:
            invalid_effect += 1
            continue
        effects.append(effect)
        selected_counts.append(len(selected))

    if len(effects) < max(20, repetitions // 2):
        raise ValueError(
            "Too few valid nested-bootstrap repetitions after donor selection."
        )
    lower, upper = np.quantile(effects, [0.025, 0.975])
    return NestedSelectionInterval(
        point_estimate=point_estimate,
        lower_95=float(lower),
        upper_95=float(upper),
        valid_repetitions=len(effects),
        invalid_reselection_or_refit_repetitions=invalid_reselection_or_refit,
        invalid_effect_repetitions=invalid_effect,
        median_selected_donor_count=float(np.median(selected_counts)),
        random_seed=random_seed,
        block_length=block_length,
    )


def block_bootstrap_median_difference(
    pre_values: np.ndarray | list[float],
    post_values: np.ndarray | list[float],
    *,
    repetitions: int = 1_000,
    block_length: int = 7,
    random_seed: int = 20_260_830,
) -> BootstrapInterval:
    """Bootstrap the post-minus-pre median difference with circular time blocks.

    This is conditional on already fitted pre-event donor weights. It accounts
    for residual serial dependence through contiguous blocks but does not
    represent uncertainty from donor selection or model specification.
    """

    pre = np.asarray(pre_values, dtype=float)
    post = np.asarray(post_values, dtype=float)
    pre = pre[np.isfinite(pre)]
    post = post[np.isfinite(post)]
    if len(pre) < 2 or len(post) < 2:
        raise ValueError("Bootstrap requires at least two finite pre and post values.")
    if repetitions <= 0 or block_length <= 0:
        raise ValueError("Bootstrap repetitions and block length must be positive.")

    rng = np.random.default_rng(random_seed)
    sampled_pre = _block_resample(pre, repetitions, block_length, rng)
    sampled_post = _block_resample(post, repetitions, block_length, rng)
    effects = np.median(sampled_post, axis=1) - np.median(sampled_pre, axis=1)
    lower, upper = np.quantile(effects, [0.025, 0.975])
    return BootstrapInterval(
        point_estimate=float(np.median(post) - np.median(pre)),
        lower_95=float(lower),
        upper_95=float(upper),
        repetitions=repetitions,
        block_length=block_length,
        random_seed=random_seed,
    )
