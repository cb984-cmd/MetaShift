"""Transparent descriptive evidence tiers for observational metadata anchors."""

from __future__ import annotations

from enum import StrEnum
from math import isfinite

import numpy as np


class EvidenceTier(StrEnum):
    SUPPORTED_CANDIDATE = "supported_candidate_discontinuity"
    NOT_SUPPORTED = "not_supported_by_available_evidence"
    INCONCLUSIVE = "inconclusive_insufficient_evidence"


def benjamini_hochberg(p_values: np.ndarray | list[float]) -> np.ndarray:
    """Return monotone Benjamini-Hochberg q values, preserving missing entries."""

    values = np.asarray(p_values, dtype=float)
    q_values = np.full(values.shape, np.nan, dtype=float)
    valid = np.isfinite(values) & (values >= 0) & (values <= 1)
    if not valid.any():
        return q_values
    valid_indices = np.flatnonzero(valid)
    ordered_indices = valid_indices[np.argsort(values[valid], kind="stable")]
    ordered = values[ordered_indices]
    count = len(ordered)
    adjusted = ordered * count / np.arange(1, count + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    q_values[ordered_indices] = np.minimum(adjusted, 1.0)
    return q_values


def evidence_tier(
    *,
    audit_complete: bool,
    quality_gate_passed: bool,
    selection_interval_available: bool,
    ci_excludes_zero: bool,
    placebo_available: bool,
    placebo_count: int | None,
    placebo_p_value: float | None,
    placebo_q_value: float | None,
    donor_sensitivity_available: bool,
    donor_direction_fraction: float | None,
    min_placebo_count: int = 50,
    placebo_cutoff: float = 0.10,
    q_cutoff: float = 0.10,
    donor_stability_cutoff: float = 0.90,
) -> tuple[EvidenceTier, list[str]]:
    """Classify an observational anchor without asserting physical causality.

    The tier is an exploratory audit label. A supported candidate must survive
    the stated FDR threshold and donor-stability threshold; it is never a
    confirmed instrument-failure label.
    """

    if not audit_complete:
        return EvidenceTier.INCONCLUSIVE, ["no_common_comparative_estimate"]
    missing = []
    if not selection_interval_available:
        missing.append("selection_aware_interval_unavailable")
    if not placebo_available or placebo_count is None or placebo_count < min_placebo_count:
        missing.append("time_placebo_insufficient")
    if placebo_q_value is None or not isfinite(placebo_q_value):
        missing.append("fdr_adjusted_placebo_probability_missing")
    if not donor_sensitivity_available:
        missing.append("donor_sensitivity_unavailable")
    if missing:
        return EvidenceTier.INCONCLUSIVE, missing

    failed = []
    if not quality_gate_passed:
        failed.append("pre_event_quality_gate_failed")
    if not ci_excludes_zero:
        failed.append("conditional_interval_includes_zero")
    if placebo_p_value is None or not isfinite(placebo_p_value):
        failed.append("placebo_probability_missing")
    elif placebo_p_value > placebo_cutoff:
        failed.append(f"placebo_p_value_above_{placebo_cutoff:.2f}")
    if placebo_q_value is not None and placebo_q_value > q_cutoff:
        failed.append(f"placebo_q_value_above_{q_cutoff:.2f}")
    if (
        donor_direction_fraction is None
        or not isfinite(donor_direction_fraction)
        or donor_direction_fraction < donor_stability_cutoff
    ):
        failed.append(
            f"leave_one_donor_out_stability_below_{donor_stability_cutoff:.2f}"
        )
    if failed:
        return EvidenceTier.NOT_SUPPORTED, failed
    return EvidenceTier.SUPPORTED_CANDIDATE, []
