"""Verify the CI-safe Gate A theory and feasibility contract for v0.4."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from .audit_v04_blind_feasibility import cluster_power_design
else:
    from audit_v04_blind_feasibility import cluster_power_design


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "paper" / "upgrade" / "PERTURBATION_EQUIVALENCE_MATRIX.csv"
RECOVERY_LOG_PATH = ROOT / "paper" / "upgrade" / "GATE_A_RECOVERY_LOG.md"
THEORY_PATH = ROOT / "paper" / "upgrade" / "THEORY_SPECIFICATION.md"
CLAIM_SCOPE_PATH = ROOT / "paper" / "upgrade" / "CLAIM_SCOPE_TABLE.md"
ROUTE_PATH = ROOT / "paper" / "upgrade" / "THEORY_ROUTE_DECISION.md"
FEASIBILITY_PATH = ROOT / "paper" / "upgrade" / "BLIND_SET_POWER_AND_FEASIBILITY.md"
PROOF_AUDIT_PATH = ROOT / "paper" / "upgrade" / "PROOF_AND_ASSUMPTION_AUDIT.md"
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "v04_phase2_gate_a_verification.json"

REQUIRED_COLUMNS = {
    "perturbation_family",
    "local_target_generator",
    "regional_target_generator",
    "local_seed_rule",
    "regional_seed_rule",
    "pathwise_target_identity",
    "distributional_target_equivalence",
    "deterministic_score_identity",
    "exact_analysis_scale_cancellation",
    "approximate_bound_available",
    "theorem_scope",
    "empirical_scope",
    "code_locations",
    "test_locations",
    "verification_status",
    "notes",
}
DETERMINISTIC_FAMILIES = {
    "additive_step",
    "proportional_step",
    "gradual_drift",
    "temporary_step",
}
REQUIRED_FAMILIES = {*DETERMINISTIC_FAMILIES, "variance_increase"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the tracked-only v0.4 Gate A theory contract."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def load_matrix() -> list[dict[str, str]]:
    with MATRIX_PATH.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def build_report() -> dict[str, object]:
    rows = load_matrix()
    by_family = {row.get("perturbation_family", ""): row for row in rows}
    texts = {
        "recovery_log": RECOVERY_LOG_PATH.read_text(encoding="utf-8"),
        "theory": THEORY_PATH.read_text(encoding="utf-8"),
        "claim_scope": CLAIM_SCOPE_PATH.read_text(encoding="utf-8"),
        "route": ROUTE_PATH.read_text(encoding="utf-8"),
        "feasibility": FEASIBILITY_PATH.read_text(encoding="utf-8"),
        "proof_audit": PROOF_AUDIT_PATH.read_text(encoding="utf-8"),
    }
    power = cluster_power_design(6)
    deterministic_rows = [by_family.get(family, {}) for family in DETERMINISTIC_FAMILIES]
    variance_row = by_family.get("variance_increase", {})
    checks = [
        check(
            "equivalence_matrix_schema_and_coverage",
            bool(rows)
            and REQUIRED_COLUMNS.issubset(set(rows[0]))
            and REQUIRED_FAMILIES.issubset(by_family),
            "The matrix includes every required field and all five frozen families.",
        ),
        check(
            "exact_identity_is_limited_to_verified_subset",
            all(row.get("pathwise_target_identity") == "yes" for row in deterministic_rows)
            and variance_row.get("pathwise_target_identity") == "no"
            and all(
                row.get("deterministic_score_identity", "").startswith("yes")
                for row in deterministic_rows
            ),
            "Only the four deterministic frozen families support exact target-only identity.",
        ),
        check(
            "variance_distributional_scope_is_not_overclaimed",
            "not established for frozen records"
            in variance_row.get("distributional_target_equivalence", "")
            and "different target-noise realizations" in texts["proof_audit"]
            and "Do not claim a distributional result for frozen records"
            in texts["recovery_log"],
            "Fixed unequal variance seeds are recorded as a limitation, not distributional proof.",
        ),
        check(
            "raw_scale_bounds_are_clipping_aware",
            "globally\none-Lipschitz" in texts["theory"]
            and "any finite signed" in texts["theory"]
            and "proportional" in texts["theory"]
            and "median is\nsup-norm stable" in texts["theory"],
            "The retained raw-scale bounds state the clipping, signed-noise, and median conditions.",
        ),
        check(
            "analysis_scale_exact_contract_is_numerically_scoped",
            "over the real numbers" in texts["theory"]
            and r"within \(10^{-12}\)" in texts["theory"]
            and "schedule SHA-256" in texts["theory"]
            and "pair_id" in texts["theory"],
            "The algebraic exact core distinguishes real-number invariance from floating-point tolerance.",
        ),
        check(
            "literature_and_route_are_bounded",
            "10.1007/978-1-4612-4946-7" in texts["theory"]
            and "Route 2 -- selected" in texts["route"]
            and "not a claim" in texts["recovery_log"]
            and "priority" in texts["recovery_log"],
            "Theory is framed as an elementary scoped contract and Route 2 is documented.",
        ),
        check(
            "feasibility_does_not_claim_component_independence",
            "non-overlapping components" in texts["feasibility"]
            and "does not prove component outcome independence" in texts["feasibility"]
            and power.get("nonoverlapping_metadata_component_count") == 6
            and power.get("independence_status")
            == "not_established_by_physical-footprint separation",
            "The candidate source is limited to non-overlapping metadata components.",
        ),
        check(
            "claim_boundaries_and_gate_decision",
            "Bitwise floating-point equality" in texts["claim_scope"]
            and "Gate A: PASS" in texts["route"]
            and "cannot establish external physical validity in a monitoring"
            in texts["feasibility"]
            and "broad confirmatory performance or information-gain"
            in texts["feasibility"],
            "The Gate A pass is scoped to the synthetic contract and explicitly excludes overclaims.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Tracked-only v0.4 Gate A theory, provenance, and feasibility verification.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
