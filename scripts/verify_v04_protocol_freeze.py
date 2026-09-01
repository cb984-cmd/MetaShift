"""Verify that the tracked v0.4 protocol is complete before outcomes exist."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "v04_identifiability_protocol.json"
NARRATIVE_PATH = ROOT / "paper" / "upgrade" / "V04_PRE_OUTCOME_PROTOCOL.md"
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "v04_protocol_freeze_verification.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the tracked v0.4 pre-outcome protocol contract."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def sha256(path: Path) -> str:
    """Hash tracked protocol text with CRLF normalized to Git's LF representation."""

    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def build_report() -> dict[str, object]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    narrative = NARRATIVE_PATH.read_text(encoding="utf-8")
    panel = protocol.get("synthetic_panel", {})
    estimator = protocol.get("estimator", {})
    evaluation = protocol.get("evaluation", {})
    expected = protocol.get("expected_accounting", {})
    output = protocol.get("output_contract", {})
    output_directory = ROOT / str(output.get("directory", ""))
    output_files = output.get("files", [])
    declared_output_exists = (
        output_directory.is_dir()
        and any((output_directory / str(filename)).exists() for filename in output_files)
    )
    checks = [
        check(
            "pre_outcome_identity",
            protocol.get("protocol_id") == "v0.4.0-identifiability-core"
            and protocol.get("protocol_state")
            == "execution_freeze_candidate"
            and protocol.get("protocol_only_predecessor", {}).get("tag")
            == "v0.4.0-protocol-freeze"
            and protocol.get("execution_freeze_predecessor", {}).get("tag")
            == "v0.4.0-execution-freeze"
            and protocol.get("execution_freeze_predecessor", {}).get("commit")
            == "9f4660a88beef829e6c3cac72e0d59134b929add",
            "The protocol has the declared v0.4 identity, preserved predecessors, and honest pre-execution state.",
        ),
        check(
            "independent_source_and_protected_baseline",
            "independently generated" in str(protocol.get("data_access", {}))
            and protocol.get("immutable_baseline", {}).get("evidence_tag")
            == "v0.3.2-evidence-final"
            and "v0.3.2" in narrative,
            "The protocol protects the frozen baseline and excludes its outcomes.",
        ),
        check(
            "complete_synthetic_panel_contract",
            panel.get("component_counts") == {"calibration": 120, "evaluation": 240}
            and panel.get("days") == 300
            and panel.get("anchor_day_index") == 180
            and panel.get("donor_count") == 4
            and panel.get("donor_availability", {}).get(
                "minimum_available_donors_guaranteed"
            )
            == 3,
            "Panel size, anchor, donor count, and availability contract are fixed.",
        ),
        check(
            "exact_pair_and_provenance_contract",
            "pair_id_template" in protocol.get("matched_pairs", {})
            and "scope arm is not an input"
            in protocol.get("matched_pairs", {}).get("schedule_seed_rule", "")
            and "schedule_hash_rule" in protocol.get("matched_pairs", {})
            and estimator.get("numerical_invariance_tolerance") == 1e-12,
            "Exact-pair target identity, arm-invariant seeds, schedule hashes, and tolerance are fixed.",
        ),
        check(
            "calibration_only_selection_contract",
            "calibration" in evaluation.get("detection_threshold_selection", "")
            and "calibration" in evaluation.get("scope_threshold_selection", "")
            and "higher threshold" in evaluation.get("detection_threshold_selection", "")
            and "nonfinite_score_policy" in evaluation
            and evaluation.get("selective_policy", {}).get("operating_quantiles")
            == [0.0, 0.25, 0.5, 0.75],
            "Threshold and selective cutoff rules use calibration only.",
        ),
        check(
            "complete_accounting_and_stress_contract",
            expected.get("core_events", {}).get("total") == 2160
            and expected.get("core_scope_events", {}).get("total") == 1440
            and expected.get("stress_events") == 1800
            and len(protocol.get("raw_scale_stress_suite", {}).get("families", [])) == 5,
            "Expected counts, failure rule, and separate raw-scale stress suite are fixed.",
        ),
        check(
            "generator_and_stress_randomness_are_fully_declared",
            "component_seed_rule" in panel
            and "availability_seed_rule" in panel
            and len(panel.get("analysis_scale_generator", {}).get("draw_order", [])) == 4
            and "stress_seed_rule" in protocol.get("raw_scale_stress_suite", {})
            and "180 pre-anchor" in str(protocol.get("raw_scale_stress_suite", {})),
            "Panel recurrence, draw order, availability, and raw-variance stress seeds are fixed.",
        ),
        check(
            "execution_input_allowlist_is_enforced_by_contract",
            protocol.get("data_access", {}).get("execution_input_allowlist")
            == [
                "configs/v04_identifiability_execution_manifest.json",
                "configs/v04_identifiability_protocol.json",
                "metashift/counterfactual.py",
                "metashift/identifiability.py",
                "metashift/metrics.py",
                "metashift/synthetic.py",
                "scripts/run_v04_identifiability_benchmark.py",
                "scripts/verify_v04_identifiability_results.py",
            ]
            and "must not call a CSV loader"
            in protocol.get("data_access", {}).get("input_access_enforcement", ""),
            "The only allowed execution inputs are declared tracked source and configuration files.",
        ),
        check(
            "one_time_output_contract",
            output.get("overwrite_rule", "").startswith("The execution entrypoint must atomically")
            and len(output_files) == 6
            and output.get("execution_freeze_tag") == "v0.4.1-execution-freeze"
            and output.get("execution_manifest")
            == "configs/v04_identifiability_execution_manifest.json"
            and output.get("attempt_record")
            == "artifacts/.v04_identifiability_core_attempt.json"
            and not declared_output_exists,
            "Declared v0.4 result files do not exist before the execution freeze.",
        ),
        check(
            "post_execution_result_validation_contract",
            output.get("post_execution_verifier")
            == "scripts/verify_v04_identifiability_results.py"
            and output.get("post_execution_verification_path")
            == "artifacts/v04_identifiability_core/v04_result_verification.json"
            and "replay the deterministic core and stress suite in memory"
            in output.get("post_execution_verifier_behavior", "")
            and "post-execution result verifier" in narrative,
            "A tagged verifier is required to validate all completed-result claims.",
        ),
        check(
            "narrative_boundaries",
            "does not test whether MetaShift is superior to standard synthetic"
            in narrative
            and "No candidate AQS signal array" in narrative
            and "One-time execution rule" in narrative
            and "10^{-12}" in narrative,
            "The human-readable protocol states the no-overclaim and two-stage freeze boundaries.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "scope": "Tracked-only pre-outcome protocol verification.",
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
