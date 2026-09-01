"""Validate each v0.5 manuscript number against receipt-bound frozen evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
LEDGER_PATH = LATEX_ROOT / "V05_CLAIM_EVIDENCE_LEDGER.csv"
VALUE_MANIFEST_PATH = LATEX_ROOT / "generated" / "v05_claim_value_manifest.json"
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "v05_answerability_asset_manifest.json"
FROZEN_MANIFEST_PATH = ROOT / "configs" / "v05_frozen_result_manifest.json"
FROZEN_OUTPUT_DIRECTORY = ROOT / "artifacts" / "v05_answerability_frontier"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "v05_claim_ledger_validation.json"
VERIFIED_STATUS = "verified_frozen_v05_evidence"
REQUIRED_COLUMNS = (
    "claim_id",
    "manuscript_section",
    "manuscript_file",
    "manuscript_assertion",
    "claim_text",
    "evidence_file",
    "evidence_role",
    "generated_asset",
    "verification_status",
    "notes",
)
REQUIRED_CLAIM_IDS = frozenset(f"V05-{index:02d}" for index in range(1, 13))
MANUSCRIPT_LOCATIONS = {
    "Abstract": ("sections/frontmatter.tex", r"\section*{Abstract}"),
    "Experiments": ("sections/experiments.tex", r"\section{Experimental design}"),
    "Framework": (
        "sections/framework.tex",
        r"\section{MetaShift-Bench audit framework}",
    ),
    "Results RQ0": (
        "sections/results.tex",
        r"\subsection{RQ0: Scope Answerability Frontier and information gain}",
    ),
    "Results RQ0a": (
        "sections/results.tex",
        r"\subsection{RQ0a: Structural certificate and retained failure boundary}",
    ),
    "Reproducibility": (
        "sections/reproducibility.tex",
        r"\section{Reproducibility, integrity, and contributions}",
    ),
    "Appendix": (
        "sections/appendix.tex",
        r"\section{Supplementary protocol details}",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate v0.5 formal-paper claims against frozen result evidence."
    )
    parser.add_argument(
        "--require-assets",
        action="store_true",
        help="Require each receipt-bound manuscript asset named by the ledger.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output report path, relative to the LaTeX project by default.",
    )
    return parser.parse_args()


def resolve_from_latex(path: Path) -> Path:
    return path if path.is_absolute() else LATEX_ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_rows() -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with LEDGER_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), tuple(reader.fieldnames or ())


def _format_probability(value: object) -> str:
    return f"{float(value):.6f}"


def _format_count(value: object) -> str:
    return f"{int(float(value)):,}"


def _frozen_csv_rows(filename: str) -> list[dict[str, str]]:
    with (FROZEN_OUTPUT_DIRECTORY / filename).open(
        encoding="utf-8", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def _frozen_single_row(
    rows: list[dict[str, str]], description: str, **conditions: object
) -> dict[str, str]:
    def matches(row: dict[str, str]) -> bool:
        for key, expected in conditions.items():
            actual = row.get(key)
            if isinstance(expected, float):
                if actual is None or abs(float(actual) - expected) > 1e-12:
                    return False
            elif actual != str(expected):
                return False
        return True

    selected = [row for row in rows if matches(row)]
    if len(selected) != 1:
        raise ValueError(
            f"Expected exactly one frozen {description} row for {conditions}, "
            f"found {len(selected)}."
        )
    return selected[0]


def receipt_bound_display_values() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Independently derive every generated display value from frozen inputs."""

    receipt_path = FROZEN_OUTPUT_DIRECTORY / "v05_execution_receipt.json"
    receipt = load_json(receipt_path)
    policy = _frozen_csv_rows("v05_policy_metrics.csv")
    frontier = _frozen_csv_rows("v05_answerability_frontier.csv")
    certificate = _frozen_csv_rows("v05_certificate_validity.csv")
    failure = _frozen_csv_rows("v05_failure_mode_map.csv")
    bootstrap = _frozen_csv_rows("v05_component_bootstrap.csv")

    overall = {"split": "evaluation", "group_type": "overall", "group_value": "all"}
    target_forced = _frozen_single_row(
        policy, "target-only forced policy", **overall, policy="target_only_forced"
    )
    comparative_forced = _frozen_single_row(
        policy, "comparative forced policy", **overall, policy="comparative_forced"
    )
    comparative_frontier = _frozen_single_row(
        frontier,
        "comparative alpha=.20 frontier",
        **overall,
        alpha=0.20,
        channel="comparative",
    )
    target_frontier = _frozen_single_row(
        frontier,
        "target-only alpha=.20 frontier",
        **overall,
        alpha=0.20,
        channel="target_only",
    )
    gain_bootstrap = _frozen_single_row(
        bootstrap,
        "scope-answerability-gain bootstrap",
        metric="scope_answerability_gain",
        alpha=0.20,
    )
    overall_certificate = _frozen_single_row(
        certificate, "overall certificate diagnostic", **overall
    )
    q_zero_certificate = _frozen_single_row(
        certificate,
        "q=0 certificate diagnostic",
        split="evaluation",
        group_type="nominal_q",
        group_value="q0.00",
    )
    strict_confidence = [
        row
        for row in policy
        if row.get("split") == "evaluation"
        and row.get("group_type") == "overall"
        and row.get("group_value") == "all"
        and row.get("policy") == "confidence_selective"
        and row.get("alpha") in {"0.01", "0.05", "0.1", "0.10"}
    ]
    strict_alpha_values = {float(row["alpha"]) for row in strict_confidence}
    if strict_alpha_values != {0.01, 0.05, 0.10} or len(strict_confidence) != 3:
        raise ValueError("Frozen strict-confidence policy rows are incomplete.")
    evaluation_failure = [
        row for row in failure if row.get("split") == "evaluation"
    ]
    if not evaluation_failure:
        raise ValueError("Frozen failure map lacks evaluation rows.")

    accounting = receipt["observed_accounting"]
    evaluation_pairs = int(accounting["expected_pair_rows"]["evaluation"])
    calibration_pairs = int(accounting["expected_pair_rows"]["calibration"])
    evaluation_arms = int(accounting["expected_scope_arm_events"]["evaluation"])
    total_pairs = int(accounting["expected_pair_rows"]["total"])
    total_arms = int(accounting["expected_scope_arm_events"]["total"])
    grid_cells_per_component = int(accounting["expected_grid_cells_per_component"])
    q_zero_pairs = sum(
        int(row["q0_observational_identity_pair_rows"]) for row in evaluation_failure
    )
    nonpositive_margin_pairs = sum(
        int(row["nonpositive_structural_margin_pair_rows"])
        for row in evaluation_failure
    )
    envelope_violations = sum(
        int(row["envelope_violation_pair_rows"]) for row in evaluation_failure
    )
    comparative_forced_errors = sum(
        int(row["comparative_forced_error_events"]) for row in evaluation_failure
    )
    if comparative_forced_errors != int(comparative_forced["error_events"]):
        raise ValueError("Frozen comparative forced-error accounting disagrees.")

    macro_values = {
        "VFiveProtocolID": str(receipt["protocol_id"]),
        "VFiveFreezeTag": str(receipt["execution_tag"]),
        "VFiveExecutionCommit": str(receipt["execution_git_commit"]),
        "VFiveEvaluationComponents": _format_count(
            evaluation_pairs // grid_cells_per_component
        ),
        "VFiveCalibrationComponents": _format_count(
            calibration_pairs // grid_cells_per_component
        ),
        "VFiveCalibrationPairs": _format_count(calibration_pairs),
        "VFiveEvaluationPairs": _format_count(evaluation_pairs),
        "VFiveTotalPairs": _format_count(total_pairs),
        "VFiveEvaluationArms": _format_count(evaluation_arms),
        "VFiveTotalArms": _format_count(total_arms),
        "VFiveTargetFrontier": _format_probability(
            target_frontier["frontier_coverage"]
        ),
        "VFiveTargetForcedCoverage": _format_probability(
            target_forced["coverage"]
        ),
        "VFiveTargetForcedRisk": _format_probability(
            target_forced["conditional_error"]
        ),
        "VFiveComparativeForcedCoverage": _format_probability(
            comparative_forced["coverage"]
        ),
        "VFiveComparativeForcedRisk": _format_probability(
            comparative_forced["conditional_error"]
        ),
        "VFiveComparativeForcedErrors": _format_count(
            comparative_forced["error_events"]
        ),
        "VFiveStrictConfidenceAnsweredArms": _format_count(
            sum(int(row["answered_events"]) for row in strict_confidence)
        ),
        "VFiveComparativeFrontierTwenty": _format_probability(
            comparative_frontier["frontier_coverage"]
        ),
        "VFiveComparativeRiskTwenty": _format_probability(
            comparative_frontier["frontier_conditional_error"]
        ),
        "VFiveComparativeGainLower": _format_probability(gain_bootstrap["lower_95"]),
        "VFiveComparativeGainUpper": _format_probability(gain_bootstrap["upper_95"]),
        "VFiveCertificateCoverage": _format_probability(
            overall_certificate["certificate_pair_coverage"]
        ),
        "VFiveCertificateEfficiency": _format_probability(
            overall_certificate["certificate_efficiency"]
        ),
        "VFiveCertificateAnsweredPairs": _format_count(
            overall_certificate["certificate_answered_pair_rows"]
        ),
        "VFiveCertificateAnsweredArms": _format_count(
            overall_certificate["certificate_answered_events"]
        ),
        "VFiveCertificateObservedError": _format_probability(
            overall_certificate["certificate_conditional_error"]
        ),
        "VFiveNonpositiveMarginPairs": _format_count(nonpositive_margin_pairs),
        "VFiveEnvelopeViolations": _format_count(envelope_violations),
        "VFiveQZeroPairs": _format_count(q_zero_pairs),
        "VFiveQZeroCertificateAnsweredPairs": _format_count(
            q_zero_certificate["certificate_answered_pair_rows"]
        ),
        "VFiveReceiptSHA": sha256(receipt_path)[:16] + r"\ldots",
    }
    q_certificate_rows = {
        row["group_value"]: row
        for row in certificate
        if row.get("split") == "evaluation"
        and row.get("group_type") == "nominal_q"
    }
    q_groups = ("q0.00", "q0.25", "q0.50", "q0.75", "q1.00")
    if set(q_certificate_rows) != set(q_groups):
        raise ValueError("Frozen certificate participation rows are incomplete.")
    claim_fragments = {
        "V05-01": [
            macro_values["VFiveEvaluationPairs"],
            macro_values["VFiveEvaluationArms"],
            macro_values["VFiveEvaluationComponents"],
            macro_values["VFiveCalibrationComponents"],
            macro_values["VFiveCalibrationPairs"],
            macro_values["VFiveTotalArms"],
        ],
        "V05-02": [
            macro_values["VFiveTargetForcedCoverage"],
            macro_values["VFiveTargetForcedRisk"],
        ],
        "V05-03": [
            macro_values["VFiveComparativeForcedCoverage"],
            macro_values["VFiveComparativeForcedRisk"],
            macro_values["VFiveComparativeForcedErrors"],
        ],
        "V05-04": ["0.01", "0.05", "0.10", "0"],
        "V05-05": [
            macro_values["VFiveComparativeFrontierTwenty"],
            macro_values["VFiveComparativeRiskTwenty"],
            macro_values["VFiveComparativeGainLower"],
            macro_values["VFiveComparativeGainUpper"],
        ],
        "V05-06": [
            macro_values["VFiveComparativeFrontierTwenty"],
            macro_values["VFiveComparativeRiskTwenty"],
        ],
        "V05-07": [
            macro_values["VFiveCertificateAnsweredPairs"],
            macro_values["VFiveCertificateAnsweredArms"],
            macro_values["VFiveCertificateCoverage"],
            macro_values["VFiveCertificateObservedError"],
        ],
        "V05-08": [macro_values["VFiveCertificateEfficiency"]],
        "V05-09": [macro_values["VFiveQZeroPairs"], "0"],
        "V05-10": [
            macro_values["VFiveNonpositiveMarginPairs"],
            macro_values["VFiveEnvelopeViolations"],
        ],
        "V05-11": [
            _format_probability(q_certificate_rows[group]["certificate_pair_coverage"])
            for group in q_groups
        ],
        "V05-12": [
            macro_values["VFiveFreezeTag"],
            str(receipt["execution_claim_tag"]),
            macro_values["VFiveExecutionCommit"],
            sha256(receipt_path),
        ],
    }
    return macro_values, claim_fragments


def macro_definitions(source: str) -> tuple[dict[str, str], bool]:
    matches = re.findall(
        r"^\\newcommand\{\\(VFive[A-Za-z]+)\}\{(.*)\}$",
        source,
        flags=re.MULTILINE,
    )
    definitions = {name: value for name, value in matches}
    return definitions, len(definitions) == len(matches)


def assertion_bindings(row: dict[str, str]) -> list[tuple[str, str]]:
    raw_manuscript_files = row["manuscript_file"].split("||")
    raw_assertions = row["manuscript_assertion"].split("||")
    if any(not part.strip() for part in [*raw_manuscript_files, *raw_assertions]):
        raise ValueError("empty")
    manuscript_files = [part.strip() for part in raw_manuscript_files]
    assertions = [part.strip() for part in raw_assertions]
    if len(manuscript_files) == 1:
        return [(manuscript_files[0], assertion) for assertion in assertions]
    if len(manuscript_files) == len(assertions):
        return list(zip(manuscript_files, assertions, strict=True))
    raise ValueError("arity")


def latex_relative_path(relative_path: str) -> Path:
    path = (LATEX_ROOT / relative_path).resolve()
    latex_root = LATEX_ROOT.resolve()
    if path == latex_root or latex_root not in path.parents:
        raise ValueError(f"Manuscript path escapes the LaTeX root: {relative_path}")
    return path


def frozen_artifact_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = manifest.get("artifacts", [])
    if not isinstance(records, list):
        return {}
    return {
        str(record["path"]): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }


def check_schema(
    rows: list[dict[str, str]], fieldnames: tuple[str, ...]
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    if fieldnames != REQUIRED_COLUMNS:
        violations.append(
            {
                "issue": "unexpected_columns",
                "expected": list(REQUIRED_COLUMNS),
                "actual": list(fieldnames),
            }
        )
    claim_ids = [row.get("claim_id", "") for row in rows]
    if not rows:
        violations.append({"issue": "empty_ledger"})
    if len(claim_ids) != len(set(claim_ids)) or any(not claim_id for claim_id in claim_ids):
        violations.append({"issue": "claim_ids_not_unique_and_nonempty"})
    if set(claim_ids) != REQUIRED_CLAIM_IDS:
        violations.append(
            {
                "issue": "required_claim_ids_mismatch",
                "missing": sorted(REQUIRED_CLAIM_IDS - set(claim_ids)),
                "unexpected": sorted(set(claim_ids) - REQUIRED_CLAIM_IDS),
            }
        )
    for line_number, row in enumerate(rows, start=2):
        missing = [
            column for column in REQUIRED_COLUMNS if not row.get(column, "").strip()
        ]
        if missing:
            violations.append(
                {
                    "issue": "missing_required_field",
                    "line": line_number,
                    "claim_id": row.get("claim_id", ""),
                    "fields": missing,
                }
            )
        if row.get("verification_status") != VERIFIED_STATUS:
            violations.append(
                {
                    "issue": "unexpected_verification_status",
                    "line": line_number,
                    "claim_id": row.get("claim_id", ""),
                    "actual": row.get("verification_status", ""),
                }
            )
    return violations


def check_manuscript_locations_and_assertions(
    rows: list[dict[str, str]], macro_source: str
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for line_number, row in enumerate(rows, start=2):
        for location in (part.strip() for part in row["manuscript_section"].split(";")):
            location_record = MANUSCRIPT_LOCATIONS.get(location)
            if location_record is None:
                violations.append(
                    {
                        "issue": "unknown_manuscript_location",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "location": location,
                    }
                )
                continue
            path, anchor = location_record
            text = (LATEX_ROOT / path).read_text(encoding="utf-8")
            if anchor not in text:
                violations.append(
                    {
                        "issue": "manuscript_location_anchor_missing",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "location": location,
                    }
                )
        try:
            bindings = assertion_bindings(row)
        except ValueError as error:
            violations.append(
                {
                    "issue": (
                        "empty_manuscript_assertion_binding"
                        if str(error) == "empty"
                        else "manuscript_assertion_binding_arity_mismatch"
                    ),
                    "line": line_number,
                    "claim_id": row["claim_id"],
                }
            )
            continue
        for assertion_file, assertion in bindings:
            try:
                assertion_path = latex_relative_path(assertion_file)
            except ValueError as error:
                violations.append(
                    {
                        "issue": "unsafe_manuscript_assertion_path",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "path": assertion_file,
                        "error": str(error),
                    }
                )
                continue
            if not assertion_path.is_file():
                violations.append(
                    {
                        "issue": "manuscript_assertion_file_missing",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "path": assertion_file,
                    }
                )
                continue
            assertion_source = assertion_path.read_text(encoding="utf-8")
            if normalize(assertion) not in normalize(assertion_source):
                violations.append(
                    {
                        "issue": "manuscript_assertion_missing",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "file": assertion_file,
                        "assertion": assertion,
                    }
                )
            for macro in re.findall(r"\\(VFive[A-Za-z]+)", assertion):
                if rf"\newcommand{{\{macro}}}" not in macro_source:
                    violations.append(
                        {
                            "issue": "manuscript_assertion_uses_undefined_macro",
                            "line": line_number,
                            "claim_id": row["claim_id"],
                            "macro": macro,
                        }
                    )
        for assertion_file in {assertion_file for assertion_file, _ in bindings}:
            if not assertion_file.startswith("generated/tables/"):
                continue
            input_token = r"\input{" + assertion_file.removesuffix(".tex") + "}"
            section_files = {
                MANUSCRIPT_LOCATIONS[location.strip()][0]
                for location in row["manuscript_section"].split(";")
                if location.strip() in MANUSCRIPT_LOCATIONS
            }
            if not any(
                input_token in (LATEX_ROOT / section_file).read_text(encoding="utf-8")
                for section_file in section_files
            ):
                violations.append(
                    {
                        "issue": "generated_table_not_input_by_declared_section",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "table": assertion_file,
                    }
                )
    return violations


def check_all_manuscript_v05_macro_uses_bound(
    rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    """Ensure every report-facing v0.5 macro use has a concrete ledger binding."""

    bindings_by_file: dict[str, list[str]] = {}
    for row in rows:
        try:
            bindings = assertion_bindings(row)
        except ValueError:
            continue
        for assertion_file, assertion in bindings:
            if assertion_file.startswith("sections/") or assertion_file == "metadata.tex":
                bindings_by_file.setdefault(assertion_file, []).append(assertion)

    violations: list[dict[str, object]] = []
    source_paths = [
        LATEX_ROOT / "metadata.tex",
        *(LATEX_ROOT / "sections").glob("*.tex"),
    ]
    for path in source_paths:
        relative_path = str(path.relative_to(LATEX_ROOT)).replace("\\", "/")
        assertions = bindings_by_file.get(relative_path, [])
        source = path.read_text(encoding="utf-8")
        for paragraph_index, paragraph in enumerate(
            re.split(r"\n\s*\n", source), start=1
        ):
            macros = set(re.findall(r"\\(VFive[A-Za-z]+)", paragraph))
            for macro in macros:
                if any(
                    rf"\{macro}" in assertion
                    and normalize(assertion) in normalize(paragraph)
                    for assertion in assertions
                ):
                    continue
                violations.append(
                    {
                        "issue": "unbound_manuscript_v05_macro_paragraph",
                        "file": relative_path,
                        "paragraph": paragraph_index,
                        "macro": macro,
                    }
                )
    return violations


def check_generated_value_manifest(
    value_manifest: dict[str, Any], expected_claim_fragments: dict[str, list[str]]
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    claims = value_manifest.get("claims")
    if (
        value_manifest.get("schema_version") != 1
        or value_manifest.get("protocol_id") != "v0.5-answerability-frontier"
        or not isinstance(claims, dict)
        or set(claims) != REQUIRED_CLAIM_IDS
    ):
        return [{"issue": "invalid_claim_value_manifest"}]
    for claim_id, expected in expected_claim_fragments.items():
        actual = claims.get(claim_id, {}).get("expected_ledger_fragments")
        if actual != expected:
            violations.append(
                {
                    "issue": "claim_value_manifest_disagrees_with_frozen_evidence",
                    "claim_id": claim_id,
                    "expected": expected,
                    "actual": actual,
                }
            )
    return violations


def check_generated_macros(
    source: str, expected_macros: dict[str, str]
) -> list[dict[str, object]]:
    actual_macros, names_are_unique = macro_definitions(source)
    violations: list[dict[str, object]] = []
    if not names_are_unique:
        violations.append({"issue": "duplicate_generated_v05_macro"})
    if set(actual_macros) != set(expected_macros):
        violations.append(
            {
                "issue": "generated_v05_macro_inventory_mismatch",
                "missing": sorted(set(expected_macros) - set(actual_macros)),
                "unexpected": sorted(set(actual_macros) - set(expected_macros)),
            }
        )
    for name in sorted(set(actual_macros) & set(expected_macros)):
        if actual_macros[name] != expected_macros[name]:
            violations.append(
                {
                    "issue": "generated_v05_macro_disagrees_with_frozen_evidence",
                    "macro": name,
                    "expected": expected_macros[name],
                    "actual": actual_macros[name],
                }
            )
    return violations


def check_generated_table_assertion_values(
    rows: list[dict[str, str]],
    expected_macros: dict[str, str],
    expected_claim_fragments: dict[str, list[str]],
) -> list[dict[str, object]]:
    """Require every ledger-bound generated-table number to be receipt-derived."""

    receipt_bound_values = {
        value
        for value in expected_macros.values()
        if re.fullmatch(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
    }
    receipt_bound_values.update(
        fragment
        for fragments in expected_claim_fragments.values()
        for fragment in fragments
        if re.fullmatch(r"\d+(?:,\d{3})*(?:\.\d+)?", fragment)
    )
    receipt_bound_values.update(
        {
            "0",
            "0.00",
            "0.01",
            "0.05",
            "0.10",
            "0.20",
            "0.25",
            "0.50",
            "0.75",
            "1.00",
        }
    )
    violations: list[dict[str, object]] = []
    numeric_token = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+\.\d+|\d+)(?![\w.,])")
    for line_number, row in enumerate(rows, start=2):
        try:
            bindings = assertion_bindings(row)
        except ValueError:
            continue
        for assertion_file, assertion in bindings:
            if not assertion_file.startswith("generated/tables/"):
                continue
            for value in numeric_token.findall(assertion):
                if value not in receipt_bound_values:
                    violations.append(
                        {
                            "issue": "generated_table_assertion_uses_unbound_number",
                            "line": line_number,
                            "claim_id": row["claim_id"],
                            "file": assertion_file,
                            "value": value,
                        }
                    )
    return violations


def check_no_manual_frozen_result_numbers(
    rows: list[dict[str, str]], expected_macros: dict[str, str]
) -> list[dict[str, object]]:
    protected_values = {
        value
        for value in expected_macros.values()
        if (
            re.fullmatch(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
            and value not in {"0", "1"}
        )
    }
    violations: list[dict[str, object]] = []
    for path in [LATEX_ROOT / "metadata.tex", *(LATEX_ROOT / "sections").glob("*.tex")]:
        text = path.read_text(encoding="utf-8")
        for value in protected_values:
            if re.search(
                rf"(?<![\w.,]){re.escape(value)}(?![\w.,])",
                text,
            ):
                violations.append(
                    {
                        "issue": "manual_frozen_v05_result_number",
                        "file": str(path.relative_to(LATEX_ROOT)).replace("\\", "/"),
                        "value": value,
                    }
                )
    for line_number, row in enumerate(rows, start=2):
        try:
            bindings = assertion_bindings(row)
        except ValueError:
            continue
        for assertion_file, assertion in bindings:
            if not assertion_file.startswith("sections/"):
                continue
            referenced = re.findall(r"\\(VFive[A-Za-z]+)", assertion)
            if not referenced:
                continue
            expanded = assertion
            for macro in referenced:
                if macro not in expected_macros:
                    continue
                expanded = expanded.replace(
                    rf"\{macro}{{}}", expected_macros[macro]
                )
            source = (LATEX_ROOT / assertion_file).read_text(encoding="utf-8")
            if normalize(expanded) in normalize(source):
                violations.append(
                    {
                        "issue": "manuscript_assertion_manually_expands_frozen_macro",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "file": assertion_file,
                        "assertion": expanded,
                    }
                )
    return violations


def check_recomputed_values(
    rows: list[dict[str, str]], value_manifest: dict[str, Any]
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    claims = value_manifest.get("claims", {})
    if (
        value_manifest.get("schema_version") != 1
        or value_manifest.get("protocol_id") != "v0.5-answerability-frontier"
        or set(claims) != REQUIRED_CLAIM_IDS
    ):
        violations.append({"issue": "invalid_claim_value_manifest"})
        return violations
    for line_number, row in enumerate(rows, start=2):
        fragments = claims.get(row["claim_id"], {}).get(
            "expected_ledger_fragments", []
        )
        if not isinstance(fragments, list):
            violations.append(
                {
                    "issue": "invalid_claim_value_fragments",
                    "line": line_number,
                    "claim_id": row["claim_id"],
                }
            )
            continue
        for fragment in fragments:
            if normalize(str(fragment)) not in normalize(row["claim_text"]):
                violations.append(
                    {
                        "issue": "claim_text_missing_recomputed_fragment",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "fragment": fragment,
                    }
                )
    return violations


def check_frozen_evidence(
    rows: list[dict[str, str]], artifact_records: dict[str, dict[str, Any]]
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for line_number, row in enumerate(rows, start=2):
        for relative_path in (part.strip() for part in row["evidence_file"].split(";")):
            record = artifact_records.get(relative_path)
            path = ROOT / relative_path
            if record is None:
                violations.append(
                    {
                        "issue": "evidence_not_in_frozen_result_manifest",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "path": relative_path,
                    }
                )
            elif (
                not path.is_file()
                or record.get("bytes") != path.stat().st_size
                or record.get("sha256") != sha256(path)
            ):
                violations.append(
                    {
                        "issue": "frozen_evidence_hash_or_size_mismatch",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "path": relative_path,
                    }
                )
    return violations


def check_assets(
    rows: list[dict[str, str]], asset_manifest: dict[str, Any]
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    records = {
        str(record["path"]): record
        for record in asset_manifest.get("outputs", [])
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    for line_number, row in enumerate(rows, start=2):
        for relative_path in (part.strip() for part in row["generated_asset"].split(";")):
            record = records.get(relative_path)
            path = LATEX_ROOT / relative_path
            if (
                record is None
                or not path.is_file()
                or record.get("bytes") != path.stat().st_size
                or record.get("sha256") != sha256(path)
            ):
                violations.append(
                    {
                        "issue": "receipt_bound_asset_missing_or_mismatched",
                        "line": line_number,
                        "claim_id": row["claim_id"],
                        "path": relative_path,
                    }
                )
    return violations


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    rows, fieldnames = load_rows()
    frozen_manifest = load_json(FROZEN_MANIFEST_PATH)
    value_manifest = load_json(VALUE_MANIFEST_PATH)
    asset_manifest = load_json(ASSET_MANIFEST_PATH)

    schema_violations = check_schema(rows, fieldnames)
    macro_source = (
        LATEX_ROOT / "generated" / "v05_answerability_macros.tex"
    ).read_text(encoding="utf-8")
    expected_macros, expected_claim_fragments = receipt_bound_display_values()
    location_violations = check_manuscript_locations_and_assertions(
        rows, macro_source
    )
    macro_line_violations = check_all_manuscript_v05_macro_uses_bound(rows)
    macro_violations = check_generated_macros(macro_source, expected_macros)
    generated_value_manifest_violations = check_generated_value_manifest(
        value_manifest, expected_claim_fragments
    )
    table_value_violations = check_generated_table_assertion_values(
        rows, expected_macros, expected_claim_fragments
    )
    manual_number_violations = check_no_manual_frozen_result_numbers(
        rows, expected_macros
    )
    value_violations = check_recomputed_values(rows, value_manifest)
    evidence_violations = check_frozen_evidence(
        rows, frozen_artifact_records(frozen_manifest)
    )
    asset_violations = check_assets(rows, asset_manifest) if args.require_assets else []
    receipt_record = frozen_artifact_records(frozen_manifest).get(
        "artifacts/v05_answerability_frontier/v05_execution_receipt.json", {}
    )
    binding_violations = []
    if (
        frozen_manifest.get("manifest_id") != "v0.5.0-frozen-result-provenance"
        or frozen_manifest.get("evidence_status") != "frozen_one_time_execution_verified"
        or value_manifest.get("source_receipt_sha256") != receipt_record.get("sha256")
        or asset_manifest.get("source_receipt", {}).get("sha256")
        != receipt_record.get("sha256")
    ):
        binding_violations.append({"issue": "receipt_binding_mismatch"})

    checks = [
        {"name": "ledger_schema_and_status", "passed": not schema_violations, "violations": schema_violations},
        {"name": "manuscript_locations_and_assertions", "passed": not location_violations, "violations": location_violations},
        {"name": "all_manuscript_v05_macro_uses_bound", "passed": not macro_line_violations, "violations": macro_line_violations},
        {"name": "receipt_derived_generated_macros", "passed": not macro_violations, "violations": macro_violations},
        {"name": "receipt_derived_claim_value_manifest", "passed": not generated_value_manifest_violations, "violations": generated_value_manifest_violations},
        {"name": "receipt_derived_generated_table_assertions", "passed": not table_value_violations, "violations": table_value_violations},
        {"name": "no_manual_frozen_result_numbers", "passed": not manual_number_violations, "violations": manual_number_violations},
        {"name": "claim_text_matches_recomputed_values", "passed": not value_violations, "violations": value_violations},
        {"name": "frozen_evidence_hashes", "passed": not evidence_violations, "violations": evidence_violations},
        {"name": "receipt_bound_asset_mapping", "passed": not asset_violations, "violations": asset_violations},
        {"name": "frozen_receipt_binding", "passed": not binding_violations, "violations": binding_violations},
    ]
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ledger": str(LEDGER_PATH.relative_to(ROOT)).replace("\\", "/"),
        "claim_count": len(rows),
        "asset_reference_count": sum(
            len([part for part in row["generated_asset"].split(";") if part.strip()])
            for row in rows
        ),
        "verification_status_counts": dict(
            sorted(Counter(row["verification_status"] for row in rows).items())
        ),
        "all_checks_passed": all(bool(check["passed"]) for check in checks),
        "checks": checks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
