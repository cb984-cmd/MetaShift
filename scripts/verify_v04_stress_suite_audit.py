"""Verify that the tracked v0.4 stress audit transcribes frozen diagnostics."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_v04_frozen_result_provenance import (
    MANIFEST_PATH,
    artifact_check,
)


STRESS_PATH = ROOT / "artifacts/v04_identifiability_core/v04_stress_results.csv"
TABLE_PATH = ROOT / "paper/upgrade/V04_ASSUMPTION_FAILURE_MATRIX.csv"
TABLE_FIELDS = [
    "stress_family",
    "split",
    "event_count",
    "bound_satisfied_count",
    "bound_failure_count",
    "median_residual_leakage_bound",
    "maximum_residual_leakage_bound",
    "median_absolute_effect_leakage",
    "maximum_absolute_effect_leakage",
    "bound_basis",
    "exact_cancellation_status",
    "classification_risk_coverage_status",
    "source_artifact_path",
    "source_artifact_sha256",
]
SOURCE_FIELDS = {
    "protocol_id",
    "component_id",
    "split",
    "stress_family",
    "stress_seed",
    "maximum_residual_leakage_bound",
    "absolute_median_effect_leakage",
    "bound_satisfied",
}
STRESS_BOUNDARIES = {
    "raw_additive_step": (
        "sharp_nonnegative_additive_bound",
        "outside_exact_core_raw_increment_value_dependent",
    ),
    "raw_proportional_step": (
        "global_proportional_lipschitz_bound_a_0.15",
        "outside_exact_core_raw_increment_value_dependent",
    ),
    "raw_gradual_drift": (
        "pointwise_sharp_nonnegative_additive_bound",
        "outside_exact_core_raw_increment_value_dependent",
    ),
    "raw_temporary_step": (
        "affected_date_sharp_nonnegative_additive_bound",
        "outside_exact_core_raw_increment_value_dependent",
    ),
    "raw_variance_increase": (
        "global_signed_clipping_aware_one_lipschitz_bound",
        "outside_exact_core_no_frozen_L_R_target_equivalence",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify v0.4 stress-audit transcription without recomputation."
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Write the canonical stress audit CSV to stdout without changing files.",
    )
    return parser.parse_args()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def read_records(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames or [], list(reader)


def float_text(value: float) -> str:
    return format(value, ".17g")


def matrix_rows(
    records: list[dict[str, str]], source_path: str, source_sha256: str
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for family, (bound_basis, cancellation_status) in STRESS_BOUNDARIES.items():
        for split in ("calibration", "evaluation"):
            group = [
                record
                for record in records
                if record["stress_family"] == family and record["split"] == split
            ]
            bounds = [
                float(record["maximum_residual_leakage_bound"]) for record in group
            ]
            leakage = [
                float(record["absolute_median_effect_leakage"]) for record in group
            ]
            satisfied = [
                record["bound_satisfied"].strip().lower() == "true" for record in group
            ]
            rows.append(
                {
                    "stress_family": family,
                    "split": split,
                    "event_count": str(len(group)),
                    "bound_satisfied_count": str(sum(satisfied)),
                    "bound_failure_count": str(len(group) - sum(satisfied)),
                    "median_residual_leakage_bound": float_text(median(bounds)),
                    "maximum_residual_leakage_bound": float_text(max(bounds)),
                    "median_absolute_effect_leakage": float_text(median(leakage)),
                    "maximum_absolute_effect_leakage": float_text(max(leakage)),
                    "bound_basis": bound_basis,
                    "exact_cancellation_status": cancellation_status,
                    "classification_risk_coverage_status": "unavailable_in_frozen_output",
                    "source_artifact_path": source_path,
                    "source_artifact_sha256": source_sha256,
                }
            )
    return rows


def stress_entry(manifest: dict[str, Any]) -> dict[str, Any]:
    matches = [
        entry
        for entry in manifest["artifacts"]
        if entry["path"] == "artifacts/v04_identifiability_core/v04_stress_results.csv"
    ]
    if len(matches) != 1:
        raise ValueError("Frozen manifest must contain exactly one stress-results entry.")
    return matches[0]


def build_report(root: Path = ROOT) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = stress_entry(manifest)
    source_passed, source_detail = artifact_check(entry, root)
    header, records = read_records(root / STRESS_PATH.relative_to(ROOT))
    table_header, actual = read_records(root / TABLE_PATH.relative_to(ROOT))
    expected = matrix_rows(records, entry["path"], entry["sha256"])
    expected_counter = Counter(
        tuple(row[field] for field in TABLE_FIELDS) for row in expected
    )
    actual_counter = Counter(
        tuple(row.get(field, "") for field in TABLE_FIELDS) for row in actual
    )
    group_counts = Counter(
        (record["stress_family"], record["split"]) for record in records
    )
    expected_group_counts = {
        (family, "calibration"): 120 for family in STRESS_BOUNDARIES
    } | {(family, "evaluation"): 240 for family in STRESS_BOUNDARIES}
    bound_satisfied = [
        record["bound_satisfied"].strip().lower() == "true" for record in records
    ]
    checks = [
        check(
            "stress_artifact_matches_frozen_manifest",
            source_passed,
            source_detail,
        ),
        check(
            "stress_schema_has_only_diagnostic_fields",
            set(header) == SOURCE_FIELDS,
            "The frozen source has bound and leakage fields, not classification metrics.",
        ),
        check(
            "complete_unfiltered_family_split_accounting",
            len(records) == 1800 and dict(group_counts) == expected_group_counts,
            "All five families retain 120 calibration and 240 evaluation cases.",
        ),
        check(
            "every_frozen_bound_is_satisfied",
            len(bound_satisfied) == 1800 and all(bound_satisfied),
            "No frozen stress row has a failed declared residual-leakage bound.",
        ),
        check(
            "assumption_failure_matrix_has_complete_canonical_cells",
            table_header == TABLE_FIELDS and len(actual) == len(expected) == 10,
            "The tracked matrix has one complete aggregate for every family and split.",
        ),
        check(
            "assumption_failure_matrix_matches_frozen_rows",
            actual_counter == expected_counter,
            "Every tracked summary value is an unfiltered aggregate of frozen diagnostics.",
        ),
        check(
            "classification_metrics_are_explicitly_unavailable",
            all(
                row["classification_risk_coverage_status"]
                == "unavailable_in_frozen_output"
                for row in actual
            ),
            "The audit does not manufacture stress classification, risk, or coverage metrics.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Read-only v0.4 stress-suite transcription validation.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    if args.render:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        entry = stress_entry(manifest)
        _, records = read_records(STRESS_PATH)
        writer = csv.DictWriter(sys.stdout, fieldnames=TABLE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(matrix_rows(records, entry["path"], entry["sha256"]))
        return
    report = build_report()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
