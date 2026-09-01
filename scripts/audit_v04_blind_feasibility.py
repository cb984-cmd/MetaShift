"""Assess v0.4 candidate feasibility using metadata only, never signal outcomes."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from scipy.optimize import brentq
from scipy.stats import nct, t

if __package__:
    from .audit_v04_candidate_components import audit_candidate_components
else:
    from audit_v04_candidate_components import audit_candidate_components


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assess v0.4 candidate physical-footprint and precision feasibility "
            "without loading candidate time-series values or outcomes."
        )
    )
    parser.add_argument("--gate-dir", type=Path, default=Path("artifacts/data_gate"))
    parser.add_argument(
        "--cases-path",
        type=Path,
        default=Path("artifacts/stable_synthetic_cases.csv"),
    )
    parser.add_argument(
        "--donors-path",
        type=Path,
        default=Path("artifacts/stable_synthetic_case_donors.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/v04_blind_set_power_and_feasibility.json"),
    )
    return parser.parse_args()


def paired_t_power(effect_size: float, cluster_count: int, alpha: float = 0.05) -> float:
    """Return two-sided paired t-test power for a planned standardized effect."""

    if cluster_count < 2:
        raise ValueError("At least two independent clusters are required.")
    if effect_size < 0:
        raise ValueError("effect_size cannot be negative.")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one.")
    degrees_of_freedom = cluster_count - 1
    critical = t.ppf(1.0 - alpha / 2.0, degrees_of_freedom)
    alternative = nct(degrees_of_freedom, effect_size * cluster_count**0.5)
    return float(alternative.sf(critical) + alternative.cdf(-critical))


def standardized_mde(
    cluster_count: int, target_power: float = 0.8, alpha: float = 0.05
) -> float:
    """Solve the paired-t standardized minimum detectable effect."""

    if not 0 < target_power < 1:
        raise ValueError("target_power must be between zero and one.")
    upper = 1.0
    while paired_t_power(upper, cluster_count, alpha) < target_power:
        upper *= 2.0
        if upper > 4.0:
            raise RuntimeError("Could not bracket the planned minimum detectable effect.")
    return float(
        brentq(
            lambda effect_size: paired_t_power(effect_size, cluster_count, alpha)
            - target_power,
            0.0,
            upper,
        )
    )


def cluster_power_design(cluster_count: int) -> dict[str, object]:
    """Return explicitly conditional precision diagnostics for components."""

    if cluster_count < 2:
        return {
            "nonoverlapping_metadata_component_count": cluster_count,
            "status": "insufficient_for_paired_cluster_precision",
        }
    sign_test_power = {
        f"{probability:.2f}": probability**cluster_count
        + (1.0 - probability) ** cluster_count
        for probability in (0.60, 0.70, 0.80, 0.90, 0.95)
    }
    return {
        "nonoverlapping_metadata_component_count": cluster_count,
        "independence_status": "not_established_by_physical-footprint separation",
        "paired_t_assumptions": (
            "Optimistic planning scenario: independent component-level paired "
            "differences, approximately normal standardized differences, "
            "two-sided alpha 0.05. Physical-footprint separation alone does not "
            "establish this independence."
        ),
        "paired_t_standardized_mde_at_80_percent_power": standardized_mde(
            cluster_count
        ),
        "two_sided_sign_test_assumptions": (
            "Optimistic planning scenario: independent nonzero component-level "
            "signs and a symmetric sign null. Ties are discarded and the "
            "effective component count must be reported; the two-sided test can "
            "reject at alpha 0.05 only when every one of six effective components "
            "has the same sign."
            if cluster_count == 6
            else (
                "Optimistic planning scenario: independent nonzero component-level "
                "signs and a symmetric sign null; ties are discarded and the "
                "effective component count must be reported."
            )
        ),
        "sign_test_tie_handling": (
            "Discard exact-zero component differences, report the effective "
            "component count, and do not claim two-sided sign-test rejection at "
            "alpha 0.05 when fewer than six nonzero components remain."
        ),
        "two_sided_sign_test_minimum_p_at_all_same_direction": 2.0
        * (0.5**cluster_count),
        "two_sided_sign_test_power_by_direction_probability": sign_test_power,
    }


def build_report(
    anchors: pd.DataFrame,
    controls: pd.DataFrame,
    cases: pd.DataFrame,
    donors: pd.DataFrame,
) -> dict[str, object]:
    """Build a metadata-only candidate-source feasibility report."""

    components = audit_candidate_components(anchors, controls, cases, donors)
    disjoint = [
        row
        for row in components["components"]
        if not row["overlaps_prior_stable_input_footprint"]
    ]
    cluster_count = len(disjoint)
    return {
        "schema_version": 1,
        "scope": (
            "Metadata-only feasibility audit. It reads anchor, donor, and prior "
            "input-footprint identifiers only; it does not open candidate signal "
            "arrays, post-window observations, fitted weights, residuals, scores, "
            "or classification outcomes."
        ),
        "candidate_88101_components": {
            "component_count": cluster_count,
            "anchor_count": components["anchors_in_disjoint_components"],
            "target_physical_site_count": components[
                "target_physical_sites_in_disjoint_components"
            ],
            "physical_site_count": components["physical_sites_in_disjoint_components"],
            "prior_input_overlap": False,
            "intended_scope": (
                "Non-confirmatory AQS realism-stress feasibility only, pending a "
                "separate pre-outcome eligibility protocol."
            ),
            "reason_not_selected_for_confirmatory_inference": (
                "There are only six non-overlapping connected components; repeated "
                "anchors within a component do not create distinct physical input "
                "footprints, and physical separation alone does not establish "
                "outcome independence."
            ),
        },
        "precision_planning": cluster_power_design(cluster_count),
        "candidate_source_decisions": [
            {
                "source": "new independently generated analysis-scale synthetic core",
                "decision": "selected_for_pre_outcome_protocol",
                "claim_scope": (
                    "Theorem-to-code contract and calibrated synthetic selective "
                    "risk/coverage only; not an external real-monitoring claim."
                ),
                "reason": (
                    "It can be fully specified, physically independent of v0.3.2, "
                    "and generated only after a committed protocol freeze."
                ),
            },
            {
                "source": "six disjoint 88101 metadata components",
                "decision": "stress_feasibility_only",
                "claim_scope": (
                    "A future descriptive or stress layer with component-clustered "
                    "uncertainty; no broad confirmatory performance claim."
                ),
                "reason": (
                    "The metadata audit provides only six non-overlapping components "
                    "and has not screened data eligibility or outcomes."
                ),
            },
            {
                "source": "2026 forward 88101 observations",
                "decision": "not_selected",
                "claim_scope": "None until an independent pre-outcome source catalog exists.",
                "reason": (
                    "No forward-time full-footprint provenance or eligibility "
                    "manifest has been frozen."
                ),
            },
            {
                "source": "v0.3.2 stable benchmark and 88502 sensitivity outputs",
                "decision": "rejected_as_previously_viewed",
                "claim_scope": "Frozen retrospective evidence only.",
                "reason": "Their outcomes or input footprints are already used.",
            },
        ],
        "selection": {
            "selected_core": "new independently generated analysis-scale synthetic core",
            "backup": "none; no external source currently meets confirmatory precision",
            "required_before_outcome_access": (
                "Commit the generator, component split, seed rule, pair IDs, "
                "threshold-selection rule, metrics, bootstrap unit, failure rules, "
                "and output schema."
            ),
        },
    }


def main() -> None:
    args = parse_args()
    anchors = pd.read_csv(args.gate_dir / "anchor_inventory.csv", dtype="string")
    controls = pd.read_csv(args.gate_dir / "geographic_controls.csv", dtype="string")
    cases = pd.read_csv(args.cases_path, dtype="string")
    donors = pd.read_csv(args.donors_path, dtype="string")
    report = build_report(anchors, controls, cases, donors)
    report["generated_at_utc"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
