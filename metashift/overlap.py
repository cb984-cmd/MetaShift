"""Helpers for transparent same-site alternate-POC consistency summaries."""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr


def direction_agreement(left: float, right: float) -> bool | None:
    """Compare signs only where both finite effects have nonzero direction."""

    if not np.isfinite(left) or not np.isfinite(right) or left == 0 or right == 0:
        return None
    return bool(np.sign(left) == np.sign(right))


def paired_spearman(left: np.ndarray, right: np.ndarray) -> tuple[int, float]:
    """Return finite paired count and rank correlation without significance claims."""

    finite = np.isfinite(left) & np.isfinite(right)
    paired_left = left[finite]
    paired_right = right[finite]
    if len(paired_left) < 3:
        return len(paired_left), float("nan")
    return len(paired_left), float(spearmanr(paired_left, paired_right).statistic)
