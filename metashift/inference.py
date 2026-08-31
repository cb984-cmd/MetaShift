"""Deterministic block-bootstrap inference for fixed-counterfactual effects."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np


@dataclass(frozen=True)
class BootstrapInterval:
    """A conditional bootstrap interval for an anchored residual effect."""

    point_estimate: float
    lower_95: float
    upper_95: float
    repetitions: int
    block_length: int
    random_seed: int


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
