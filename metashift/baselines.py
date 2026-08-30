"""Transparent single-station change-point baselines used by MetaShift."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChangePointResult:
    """Detected split indices in the chronological input series."""

    change_indices: tuple[int, ...]
    strongest_score: float | None


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
