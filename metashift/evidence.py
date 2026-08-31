"""Transparent descriptive evidence tiers for observational metadata anchors."""

from __future__ import annotations

from enum import StrEnum
from math import isfinite


class EvidenceTier(StrEnum):
    SUPPORTED_CANDIDATE = "supported_candidate_discontinuity"
    NOT_SUPPORTED = "not_supported_by_available_evidence"
    INCONCLUSIVE = "inconclusive_insufficient_evidence"


def evidence_tier(
    *,
    audit_complete: bool,
    quality_gate_passed: bool,
    ci_excludes_zero: bool,
    placebo_available: bool,
    placebo_p_value: float | None,
    donor_sensitivity_available: bool,
    donor_direction_stable: bool,
    placebo_cutoff: float = 0.10,
) -> tuple[EvidenceTier, list[str]]:
    """Classify an observational anchor without asserting physical causality."""

    if not audit_complete:
        return EvidenceTier.INCONCLUSIVE, ["no_common_comparative_estimate"]
    missing = []
    if not placebo_available:
        missing.append("time_placebo_unavailable")
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
    if not donor_direction_stable:
        failed.append("leave_one_donor_out_direction_unstable")
    if failed:
        return EvidenceTier.NOT_SUPPORTED, failed
    return EvidenceTier.SUPPORTED_CANDIDATE, []
