"""Transparent single-station change-point baselines used by MetaShift."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChangePointResult:
    """Detected split indices in the chronological input series."""

    change_indices: tuple[int, ...]
    strongest_score: float | None


@dataclass(frozen=True)
class AnchoredBaselineResult:
    """An effect estimate and evidence score evaluated at a fixed event date."""

    effect: float
    score: float


def _as_signal(values: np.ndarray | list[float], min_size: int) -> np.ndarray:
    signal = np.asarray(values, dtype=float)
    if signal.ndim != 1 or len(signal) < 2 * min_size:
        raise ValueError("Signal must be one-dimensional with two valid segments.")
    if not np.isfinite(signal).all():
        raise ValueError("Signal contains non-finite values.")
    return signal


def cusum_change_point(
    values: np.ndarray | list[float], min_size: int = 15
) -> ChangePointResult:
    """Find the strongest single mean-shift candidate using CUSUM."""

    signal = _as_signal(values, min_size)
    centered = signal - signal.mean()
    cumulative = np.concatenate([[0.0], np.cumsum(centered)])
    indices = np.arange(min_size, len(signal) - min_size + 1)
    denominator = np.sqrt(indices * (len(signal) - indices) / len(signal))
    scores = np.abs(cumulative[indices]) / denominator
    strongest = int(indices[int(np.argmax(scores))])
    return ChangePointResult((strongest,), float(np.max(scores)))


def rolling_median_change_point(
    values: np.ndarray | list[float], window: int = 30, min_size: int = 15
) -> ChangePointResult:
    """Find the largest robust before/after shift in fixed rolling windows."""

    signal = _as_signal(values, min_size)
    if window < min_size:
        raise ValueError("window must be at least min_size.")

    candidates: list[tuple[int, float]] = []
    for index in range(window, len(signal) - window + 1):
        before = signal[index - window : index]
        after = signal[index : index + window]
        delta = float(np.median(after) - np.median(before))
        scale = 1.4826 * float(np.median(np.abs(before - np.median(before))))
        candidates.append((index, abs(delta) / max(scale, 1e-8)))
    strongest_index, strongest_score = max(candidates, key=lambda value: value[1])
    return ChangePointResult((strongest_index,), strongest_score)


def pelt_change_points(
    values: np.ndarray | list[float], min_size: int = 15, penalty_scale: float = 3.0
) -> ChangePointResult:
    """Run the PELT L2 baseline with a BIC-style variance-scaled penalty."""

    signal = _as_signal(values, min_size)
    if penalty_scale <= 0:
        raise ValueError("penalty_scale must be positive.")
    try:
        import ruptures as rpt
    except ImportError as error:
        raise RuntimeError(
            "PELT requires the 'ruptures' package. Install requirements.txt first."
        ) from error

    variance = float(np.var(signal))
    penalty = penalty_scale * np.log(len(signal)) * max(variance, 1e-8)
    breakpoints = rpt.Pelt(model="l2", min_size=min_size).fit(signal).predict(
        pen=penalty
    )
    change_indices = tuple(index for index in breakpoints if index < len(signal))
    return ChangePointResult(change_indices, None)


def before_after_median(
    values: np.ndarray | list[float], split_index: int, min_size: int = 15
) -> AnchoredBaselineResult:
    """Estimate an anchored level effect from robust before/after medians."""

    signal = _as_signal(values, min_size)
    if not min_size <= split_index <= len(signal) - min_size:
        raise ValueError("split_index leaves an undersized before or after segment.")
    before = signal[:split_index]
    after = signal[split_index:]
    effect = float(np.median(after) - np.median(before))
    scale = 1.4826 * float(np.median(np.abs(before - np.median(before))))
    return AnchoredBaselineResult(effect, abs(effect) / max(scale, 1e-8))


def bayesian_mean_shift(
    values: np.ndarray | list[float],
    split_index: int,
    min_size: int = 15,
    prior_variance_multiplier: float = 10.0,
) -> AnchoredBaselineResult:
    """Score a known-date Gaussian mean shift with a conjugate normal prior.

    The returned score is the log Bayes factor for separate pre/post means over
    a shared mean, using a pooled variance estimated from the observed window.
    It is an anchored change-point baseline, not a causal attribution method.
    """

    signal = _as_signal(values, min_size)
    if not min_size <= split_index <= len(signal) - min_size:
        raise ValueError("split_index leaves an undersized before or after segment.")
    if prior_variance_multiplier <= 0:
        raise ValueError("prior_variance_multiplier must be positive.")

    before = signal[:split_index]
    after = signal[split_index:]
    noise_variance = max(float(np.var(signal, ddof=1)), 1e-8)
    prior_variance = prior_variance_multiplier * noise_variance
    prior_mean = float(np.mean(signal))

    def log_marginal(segment: np.ndarray) -> float:
        count = len(segment)
        sample_mean = float(np.mean(segment))
        squared_error = float(np.square(segment - sample_mean).sum())
        posterior_variance = 1 / (1 / prior_variance + count / noise_variance)
        mean_penalty = (sample_mean - prior_mean) ** 2 / (
            noise_variance / count + prior_variance
        )
        return float(
            -0.5 * count * np.log(2 * np.pi * noise_variance)
            - 0.5 * squared_error / noise_variance
            - 0.5 * np.log(prior_variance / posterior_variance)
            - 0.5 * mean_penalty
        )

    log_bayes_factor = log_marginal(before) + log_marginal(after) - log_marginal(
        signal
    )
    effect = float(np.mean(after) - np.mean(before))
    return AnchoredBaselineResult(effect, max(log_bayes_factor, 0.0))
