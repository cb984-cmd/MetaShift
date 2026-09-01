"""Verify that the tracked v0.4 core confusion table transcribes frozen outputs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_v04_frozen_result_provenance import (
    MANIFEST_PATH,
    artifact_check,
)


CORE_PATH = ROOT / "artifacts/v04_identifiability_core/v04_core_event_results.csv"
THRESHOLDS_PATH = ROOT / "artifacts/v04_identifiability_core/v04_core_thresholds.json"
METRICS_PATH = ROOT / "artifacts/v04_identifiability_core/v04_core_metrics.json"
BOOTSTRAP_PATH = ROOT / "artifacts/v04_identifiability_core/v04_core_bootstrap.json"
TABLE_PATH = ROOT / "paper/upgrade/V04_CORE_CONFUSION_MATRICES.csv"
TABLE_FIELDS = [
    "task",
    "split",
    "quantile",
    "truth_label",
    "decision",
    "prediction_label",
    "count",
    "task_denominator",
    "source_artifact_path",
    "source_artifact_sha256",
]
REQUIRED_EVENT_FIELDS = {
    "split",
    "state",
    "detection_prediction",
    "forced_scope_prediction",
    "target_only_scope_prediction",
    "answered_q0.00",
    "answered_q0.25",
    "answered_q0.50",
    "answered_q0.75",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify v0.4 core-audit matrix transcription without recomputation."
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Write the canonical CSV table to stdout without touching tracked files.",
    )
    return parser.parse_args()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def read_records(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames or [], list(reader)


def answered(record: dict[str, str], quantile: str) -> bool:
    return record[f"answered_q{quantile}"].strip().lower() == "true"


def matrix_rows(
    events: list[dict[str, str]],
    quantiles: list[str],
    source_path: str,
    source_sha256: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for split in ("calibration", "evaluation"):
        split_events = [event for event in events if event["split"] == split]
        scope_events = [
            event
            for event in split_events
            if event["state"] in {"local", "regional"}
        ]
        detection_truth = {
            id(event): "no_change" if event["state"] == "no_change" else "change"
            for event in split_events
        }
        for truth_label in ("no_change", "change"):
            for prediction_label in ("no_change", "change"):
                rows.append(
                    canonical_row(
                        "detection",
                        split,
                        "",
                        truth_label,
                        "answered",
                        prediction_label,
                        sum(
                            detection_truth[id(event)] == truth_label
                            and event["detection_prediction"] == prediction_label
                            for event in split_events
                        ),
                        len(split_events),
                        source_path,
                        source_sha256,
                    )
                )
        for task, prediction_field in (
            ("forced_scope", "forced_scope_prediction"),
            ("target_only_scope", "target_only_scope_prediction"),
        ):
            for truth_label in ("local", "regional"):
                for prediction_label in ("local", "regional"):
                    rows.append(
                        canonical_row(
                            task,
                            split,
                            "",
                            truth_label,
                            "answered",
                            prediction_label,
                            sum(
                                event["state"] == truth_label
                                and event[prediction_field] == prediction_label
                                for event in scope_events
                            ),
                            len(scope_events),
                            source_path,
                            source_sha256,
                        )
                    )
        for quantile in quantiles:
            for truth_label in ("local", "regional"):
                for prediction_label in ("local", "regional"):
                    rows.append(
                        canonical_row(
                            "selective_scope",
                            split,
                            quantile,
                            truth_label,
                            "answered",
                            prediction_label,
                            sum(
                                event["state"] == truth_label
                                and answered(event, quantile)
                                and event["forced_scope_prediction"] == prediction_label
                                for event in scope_events
                            ),
                            len(scope_events),
                            source_path,
                            source_sha256,
                        )
                    )
                rows.append(
                    canonical_row(
                        "selective_scope",
                        split,
                        quantile,
                        truth_label,
                        "abstained",
                        "not_answered",
                        sum(
                            event["state"] == truth_label
                            and not answered(event, quantile)
                            for event in scope_events
                        ),
                        len(scope_events),
                        source_path,
                        source_sha256,
                    )
                )
    return rows


def canonical_row(
    task: str,
    split: str,
    quantile: str,
    truth_label: str,
    decision: str,
    prediction_label: str,
    count: int,
    denominator: int,
    source_path: str,
    source_sha256: str,
) -> dict[str, str]:
    return {
        "task": task,
        "split": split,
        "quantile": quantile,
        "truth_label": truth_label,
        "decision": decision,
        "prediction_label": prediction_label,
        "count": str(count),
        "task_denominator": str(denominator),
        "source_artifact_path": source_path,
        "source_artifact_sha256": source_sha256,
    }


def relevant_manifest_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    paths = {
        "core": "artifacts/v04_identifiability_core/v04_core_event_results.csv",
        "thresholds": "artifacts/v04_identifiability_core/v04_core_thresholds.json",
        "metrics": "artifacts/v04_identifiability_core/v04_core_metrics.json",
        "bootstrap": "artifacts/v04_identifiability_core/v04_core_bootstrap.json",
    }
    by_path = {entry["path"]: entry for entry in manifest["artifacts"]}
    return {name: by_path[path] for name, path in paths.items()}


def build_report(root: Path = ROOT) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = relevant_manifest_entries(manifest)
    source_checks = [
        artifact_check(entry, root) for entry in entries.values()
    ]
    header, events = read_records(root / CORE_PATH.relative_to(ROOT))
    thresholds = json.loads(
        (root / THRESHOLDS_PATH.relative_to(ROOT)).read_text(encoding="utf-8")
    )
    metrics = json.loads((root / METRICS_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))
    bootstrap = json.loads(
        (root / BOOTSTRAP_PATH.relative_to(ROOT)).read_text(encoding="utf-8")
    )
    quantiles = list(thresholds["selective_confidence_cutoffs"])
    expected = matrix_rows(
        events,
        quantiles,
        entries["core"]["path"],
        entries["core"]["sha256"],
    )
    table_header, actual = read_records(root / TABLE_PATH.relative_to(ROOT))
    expected_counter = Counter(
        tuple(row[field] for field in TABLE_FIELDS) for row in expected
    )
    actual_counter = Counter(
        tuple(row.get(field, "") for field in TABLE_FIELDS) for row in actual
    )
    evaluation_events = [event for event in events if event["split"] == "evaluation"]
    evaluation_scope_events = [
        event
        for event in evaluation_events
        if event["state"] in {"local", "regional"}
    ]
    checks = [
        check(
            "source_artifacts_match_frozen_manifest",
            all(passed for passed, _ in source_checks),
            " ".join(detail for _, detail in source_checks),
        ),
        check(
            "core_event_schema_is_sufficient",
            REQUIRED_EVENT_FIELDS.issubset(header),
            "The frozen event CSV retains each task, prediction, and selective-answer field.",
        ),
        check(
            "matrix_table_schema_and_complete_cells",
            table_header == TABLE_FIELDS and len(actual) == len(expected) == 72,
            "The tracked table has the canonical schema and all 72 matrix cells.",
        ),
        check(
            "matrix_table_exactly_matches_frozen_event_rows",
            actual_counter == expected_counter,
            "Every tracked matrix cell is the unfiltered task-defined aggregation of frozen rows.",
        ),
        check(
            "evaluation_accounting_matches_frozen_metrics",
            len(evaluation_events) == 1440
            and len(evaluation_scope_events) == 960
            and metrics["complete_event_accounting"]
            == {"local": 480, "no_change": 480, "regional": 480},
            "Evaluation event and L/R denominators agree with the frozen metric payload.",
        ),
        check(
            "threshold_and_bootstrap_contract_is_present",
            quantiles == ["0.00", "0.25", "0.50", "0.75"]
            and bootstrap["repetitions"] == 1000
            and bootstrap["cluster"]
            == "synthetic component_id; resample complete component records with replacement",
            "The table is tied to the frozen calibration cutoffs and component bootstrap contract.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Read-only v0.4 core-audit transcription validation.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    if args.render:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        entries = relevant_manifest_entries(manifest)
        _, events = read_records(CORE_PATH)
        thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
        writer = csv.DictWriter(sys.stdout, fieldnames=TABLE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            matrix_rows(
                events,
                list(thresholds["selective_confidence_cutoffs"]),
                entries["core"]["path"],
                entries["core"]["sha256"],
            )
        )
        return
    report = build_report()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
