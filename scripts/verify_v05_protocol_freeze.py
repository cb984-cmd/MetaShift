"""Verify the tracked-only v0.5 pre-outcome protocol contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "v05_answerability_protocol.json"
THEORY_PATH = ROOT / "paper" / "upgrade" / "V05_SCOPE_ANSWERABILITY_THEORY.md"
LITERATURE_PATH = ROOT / "paper" / "upgrade" / "V05_LITERATURE_AUDIT.md"
NARRATIVE_PATH = ROOT / "paper" / "upgrade" / "V05_PRE_OUTCOME_PROTOCOL.md"
POWER_PATH = ROOT / "paper" / "upgrade" / "V05_POWER_AND_FEASIBILITY.md"
THEORY_TO_CODE_PATH = ROOT / "paper" / "upgrade" / "V05_THEORY_TO_CODE_AUDIT.md"
CLAIM_LEDGER_PATH = ROOT / "paper" / "upgrade" / "V05_CLAIM_EVIDENCE_LEDGER.md"
CHECKLIST_PATH = ROOT / "paper" / "upgrade" / "V05_EXECUTION_FREEZE_CHECKLIST.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the v0.5 tracked pre-outcome protocol contract."
    )
    parser.add_argument(
        "--allow-existing-outputs",
        action="store_true",
        help="Use only for post-execution contract inspection.",
    )
    return parser.parse_args()


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def no_declared_output_exists(
    output_directory: Path, output_files: list[object], attempt_record: Path | None = None
) -> bool:
    return (
        output_directory.exists()
        or (attempt_record is not None and attempt_record.exists())
        or any(
        (output_directory / str(filename)).exists() for filename in output_files
        )
    )


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required v0.5 document is absent: {path}")
    return path.read_text(encoding="utf-8")


def build_report(*, require_no_outputs: bool = True) -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    theory = _read_text(THEORY_PATH)
    literature = _read_text(LITERATURE_PATH)
    narrative = _read_text(NARRATIVE_PATH)
    power = _read_text(POWER_PATH)
    theory_to_code = _read_text(THEORY_TO_CODE_PATH)
    ledger = _read_text(CLAIM_LEDGER_PATH)
    checklist = _read_text(CHECKLIST_PATH)
    panel = protocol.get("synthetic_panel", {})
    grid = protocol.get("full_cartesian_grid", {})
    estimator = protocol.get("estimator", {})
    definition = protocol.get("answerability_definition", {})
    certificate = protocol.get("structural_certificate", {})
    calibration = protocol.get("calibration_and_evaluation", {})
    output = protocol.get("output_contract", {})
    expected = protocol.get("expected_accounting", {})
    runtime = protocol.get("runtime_environment", {})
    output_directory = ROOT / str(output.get("directory", ""))
    attempt_path = ROOT / str(output.get("attempt_record", ""))
    output_exists = no_declared_output_exists(
        output_directory, list(output.get("files", [])), attempt_path
    )
    factor_order = grid.get("factor_order", [])
    try:
        product_count = math.prod(len(grid[factor]) for factor in factor_order)
    except (KeyError, TypeError):
        product_count = -1
    expected_pair_rows = {
        split: int(panel.get("component_counts", {}).get(split, -1))
        * int(grid.get("cells_per_component", -1))
        for split in ("calibration", "evaluation")
    }
    source_allowlist = protocol.get("data_access", {}).get(
        "execution_input_allowlist", []
    )
    manifest_relative = output.get("execution_manifest")
    manifest_path = ROOT / str(manifest_relative)
    runtime_lock = ROOT / str(runtime.get("requirements_lock", ""))
    lock_versions: dict[str, str] = {}
    if runtime_lock.is_file():
        for raw_line in runtime_lock.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and line.count("==") == 1:
                name, version = line.split("==", maxsplit=1)
                lock_versions[name] = version
    source_files_ready = all(
        (
            relative_path == manifest_relative
            or (ROOT / str(relative_path)).is_file()
        )
        for relative_path in source_allowlist
    )
    manifest_ready = False
    if protocol.get("protocol_state") == "execution_freeze_candidate" and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_paths = set(source_allowlist).difference({manifest_relative})
        manifest_ready = (
            manifest.get("protocol_sha256") == source_sha256(PROTOCOL_PATH)
            and manifest.get("execution_freeze_tag")
            == output.get("execution_freeze_tag")
            and set(manifest.get("bound_input_sha256", {})) == expected_paths
        )
    required_docs = (
        "V05_SCOPE_ANSWERABILITY_THEORY.md",
        "V05_LITERATURE_AUDIT.md",
        "V05_PRE_OUTCOME_PROTOCOL.md",
        "V05_POWER_AND_FEASIBILITY.md",
        "V05_THEORY_TO_CODE_AUDIT.md",
        "V05_CLAIM_EVIDENCE_LEDGER.md",
        "V05_EXECUTION_FREEZE_CHECKLIST.md",
    )
    checks = [
        check(
            "protocol_identity_and_scope",
            protocol.get("protocol_id") == "v0.5-answerability-frontier"
            and protocol.get("schema_version") == 1
            and protocol.get("protocol_state")
            in {"pre_execution_protocol", "execution_freeze_candidate"}
            and protocol.get("immutable_predecessors", {}).get("v032_evidence_tag")
            == "v0.3.2-evidence-final"
            and protocol.get("immutable_predecessors", {}).get("v041_execution_tag")
            == "v0.4.1-execution-freeze",
            "The protocol is an independent v0.5 scope study with frozen predecessors.",
        ),
        check(
            "independent_synthetic_source_boundary",
            "independently generated" in protocol.get("data_access", {}).get(
                "primary_source", ""
            )
            and any(
                "AQS data" in str(item)
                for item in protocol.get("data_access", {}).get(
                    "forbidden_sources", []
                )
            )
            and not any(
                path.startswith(("data/", "artifacts/", "results/"))
                for path in source_allowlist
            ),
            "No historical evidence, AQS input, output, or external data path is allowed.",
        ),
        check(
            "complete_cartesian_grid",
            factor_order
            == [
                "nominal_donor_participation",
                "signal_h",
                "donor_mismatch",
                "availability",
                "donor_contamination",
                "raw_scale_field",
                "bounded_noise",
            ]
            and product_count == 640
            and grid.get("cells_per_component") == 640
            and {
                float(item.get("value", float("nan")))
                for item in grid.get("nominal_donor_participation", [])
            }
            == {0.0, 0.25, 0.5, 0.75, 1.0},
            "Every q endpoint, partial scope level, signal, and nuisance combination is fixed.",
        ),
        check(
            "component_disjointness_and_power",
            panel.get("component_counts") == {"calibration": 120, "evaluation": 360}
            and panel.get("split_seed_offsets") == {"calibration": 0, "evaluation": 1000000}
            and "component" in calibration.get("component_split", "")
            and "1-0.05^{1/360}=0.00829" in power,
            "Calibration and evaluation use disjoint component seed streams and fixed planning dimensions.",
        ),
        check(
            "target_fixed_pair_and_side_channel_contract",
            "identical" in protocol.get("matched_scope_construction", {}).get(
                "target_rule", ""
            )
            and "q=0" in protocol.get("matched_scope_construction", {}).get(
                "q0_negative_control", ""
            )
            and len(
                protocol.get("matched_scope_construction", {}).get(
                    "forbidden_side_channels", []
                )
            )
            >= 8
            and "Target digest" in narrative,
            "The target is fixed between scope arms, q=0 is a negative control, and leakage fields are forbidden.",
        ),
        check(
            "residual_and_partial_scope_semantics",
            estimator.get("analysis_transform") == "log1p(max(raw, 0))"
            and "normalized" in estimator.get(
                "availability_normalization", ""
            )
            and "signed mean" in estimator.get("scope_score", "")
            and "q_t" in theory
            and "overline{q_th_t}" in theory,
            "The affine score is explicitly distinct from the v0.4 median and uses normalized donor availability.",
        ),
        check(
            "certificate_repair_and_raw_boundary",
            certificate.get("status") == "simulation_design_information_assisted_only"
            and "structural_margin > 0" in certificate.get("answer_rule", "")
            and "shared_error_bound - local_error_bound" in certificate.get(
                "answer_rule", ""
            )
            and "nominal midpoint" in theory
            and "Raw-scale boundary" in theory,
            "The certificate uses the interval-safe threshold and does not claim raw-scale exactness.",
        ),
        check(
            "calibration_only_policy_contract",
            calibration.get("outcome_blindness", "").startswith("The runner")
            and calibration.get("no_retuning_rule", "").startswith("Evaluation outcomes")
            and definition.get("error_tolerances") == [0.01, 0.05, 0.1, 0.2]
            and len(definition.get("policies", [])) == 4,
            "Thresholds are calibration-only, tolerances and policies are fixed, and retuning is prohibited.",
        ),
        check(
            "answerability_gain_and_q0_reporting",
            "Scope Answerability Gain" in protocol.get("reporting", {}).get(
                "primary_metrics", []
            )
            and "q=0" in str(protocol.get("reporting", {}).get("primary_metrics", []))
            and "descriptive" in definition.get("empirical_frontier", "")
            and "q=0" in definition.get("ambiguous_partial_region", ""),
            "The gain has a declared finite-policy meaning and q=0 cannot be hidden.",
        ),
        check(
            "expected_accounting_and_schemas",
            expected.get("pair_rows")
            == {
                "calibration": expected_pair_rows["calibration"],
                "evaluation": expected_pair_rows["evaluation"],
                "total": sum(expected_pair_rows.values()),
            }
            and expected.get("scope_arm_events", {}).get("total")
            == 2 * sum(expected_pair_rows.values())
            and len(output.get("files", [])) == 8
            and all(
                len(columns) > 0
                for columns in output.get("schemas", {}).values()
            ),
            "All expected rows, arm events, outputs, and artifact schemas are predeclared.",
        ),
        check(
            "one_time_execution_and_source_binding_contract",
            output.get("attempt_record")
            == "artifacts/.v05_answerability_frontier_attempt.json"
            and output.get("execution_freeze_tag") == "v0.5.0-answerability-freeze"
            and output.get("execution_claim_tag")
            == "v0.5.0-answerability-execution-claim"
            and output.get("execution_manifest")
            == "configs/v05_answerability_execution_manifest.json"
            and "exclusive creation" in output.get("overwrite_rule", "")
            and "atomically push" in output.get("overwrite_rule", "")
            and "annotated tag" in " ".join(output.get("execution_preconditions", []))
            and PRE_OUTCOME_VERIFIER_PATH_IN_ALLOWLIST(source_allowlist),
            "A source-bound, remote-tagged, one-time executor and pre-outcome verifier are required.",
        ),
        check(
            "runtime_lock_contract",
            runtime.get("python_implementation") == "CPython"
            and runtime.get("python_major") == 3
            and runtime.get("python_minor") == 13
            and runtime.get("requirements_lock") == "requirements-lock.txt"
            and "requirements-lock.txt" in source_allowlist
            and runtime.get("required_distribution_versions") == lock_versions,
            "The execution source set binds the exact lockfile and configured CPython/runtime package contract.",
        ),
        check(
            "source_bundle_readiness",
            source_files_ready
            and (
                protocol.get("protocol_state") == "pre_execution_protocol"
                or manifest_ready
            ),
            "Every non-self execution source exists; an execution-freeze candidate also has a complete hash manifest.",
        ),
        check(
            "literature_and_claim_boundaries",
            "Blackwell" in literature
            and "Chow" in literature
            and "Synthetic control" in literature
            and "Residual signatures" in literature
            and "not proof" in literature
            and "not a deployable" in theory
            and "Explicit nonclaim" in theory,
            "The focused source audit separates established ingredients from bounded contribution claims.",
        ),
        check(
            "theory_code_and_claim_crosswalk",
            "anchor_residual_windows" in theory_to_code
            and "Structural separation" in theory_to_code
            and "Scope Answerability Gain" in ledger
            and "No weak result" in checklist,
            "Theory/code mapping, claim boundaries, and no-rerun checklist are explicit.",
        ),
        check(
            "pre_outcome_output_absence",
            not require_no_outputs or not output_exists,
            (
                "No declared v0.5 output directory, file, or attempt record exists."
                if require_no_outputs
                else "Output absence is not required for post-execution inspection."
            ),
        ),
    ]
    return {
        "protocol_id": protocol.get("protocol_id"),
        "protocol_sha256": source_sha256(PROTOCOL_PATH),
        "scope": "Tracked-only pre-outcome protocol verification.",
        "required_documents": required_docs,
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def PRE_OUTCOME_VERIFIER_PATH_IN_ALLOWLIST(allowlist: list[object]) -> bool:
    return PRE_OUTCOME_VERIFIER_RELATIVE_PATH in allowlist


PRE_OUTCOME_VERIFIER_RELATIVE_PATH = "scripts/verify_v05_protocol_freeze.py"


def main() -> None:
    args = parse_args()
    report = build_report(require_no_outputs=not args.allow_existing_outputs)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
