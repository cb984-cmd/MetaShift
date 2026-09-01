"""Verify the unreviewed taxonomy handoff packet against its frozen source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "configs/method_transition_taxonomy_v1.csv"
PACKET_PATH = ROOT / "paper/upgrade/TAXONOMY_HUMAN_REVIEW_PACKET.csv"
EXPECTED_SOURCE_SHA256 = "31485dc86fd1d3dd9715bc9f1057856dab8d89e399ebbaaff206374f76b4fcf2"
SOURCE_FIELDS = [
    "old_method_code",
    "old_method_name",
    "new_method_code",
    "new_method_name",
    "old_analyzer_family",
    "new_analyzer_family",
    "transition_class",
    "nda_related",
    "same_hardware_family",
    "classification_basis",
    "official_source",
    "review_status",
]
PACKET_FIELDS = [
    "review_row_id",
    "old_method_code",
    "old_method_name",
    "new_method_code",
    "new_method_name",
    "frozen_proposed_old_analyzer_family",
    "frozen_proposed_new_analyzer_family",
    "frozen_proposed_transition_class",
    "frozen_proposed_nda_related",
    "frozen_proposed_same_hardware_family",
    "frozen_classification_basis",
    "frozen_official_source",
    "frozen_source_review_status",
    "frozen_taxonomy_sha256",
    "human_review_decision",
    "human_evidence_locator",
    "human_source_accessed_at_utc",
    "student_reviewer_initials",
    "teacher_reviewer_initials",
    "review_date",
    "reviewer_notes",
]
EMPTY_HUMAN_FIELDS = [
    "human_evidence_locator",
    "human_source_accessed_at_utc",
    "student_reviewer_initials",
    "teacher_reviewer_initials",
    "review_date",
    "reviewer_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the unreviewed human taxonomy packet without outcomes."
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Write the canonical unreviewed packet CSV to stdout without changing files.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    # Git stores this tracked text file with LF; normalize a Windows checkout
    # before comparing its portable frozen-source identity.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def read_records(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames or [], list(reader)


def packet_rows(
    source_rows: list[dict[str, str]], source_sha256: str
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, source in enumerate(source_rows, start=1):
        rows.append(
            {
                "review_row_id": f"TAX-{index:03d}",
                "old_method_code": source["old_method_code"],
                "old_method_name": source["old_method_name"],
                "new_method_code": source["new_method_code"],
                "new_method_name": source["new_method_name"],
                "frozen_proposed_old_analyzer_family": source["old_analyzer_family"],
                "frozen_proposed_new_analyzer_family": source["new_analyzer_family"],
                "frozen_proposed_transition_class": source["transition_class"],
                "frozen_proposed_nda_related": source["nda_related"],
                "frozen_proposed_same_hardware_family": source[
                    "same_hardware_family"
                ],
                "frozen_classification_basis": source["classification_basis"],
                "frozen_official_source": source["official_source"],
                "frozen_source_review_status": source["review_status"],
                "frozen_taxonomy_sha256": source_sha256,
                "human_review_decision": "pending_human_review",
                **{field: "" for field in EMPTY_HUMAN_FIELDS},
            }
        )
    return rows


def build_report(root: Path = ROOT) -> dict[str, object]:
    source_path = root / SOURCE_PATH.relative_to(ROOT)
    packet_path = root / PACKET_PATH.relative_to(ROOT)
    source_header, source_rows = read_records(source_path)
    packet_header, actual_rows = read_records(packet_path)
    source_hash = sha256(source_path)
    expected_rows = packet_rows(source_rows, source_hash)
    checks = [
        check(
            "frozen_taxonomy_source_identity",
            source_header == SOURCE_FIELDS
            and len(source_rows) == 34
            and source_hash == EXPECTED_SOURCE_SHA256,
            "The packet source is the 34-row frozen metadata-only taxonomy.",
        ),
        check(
            "packet_schema_and_row_inventory",
            packet_header == PACKET_FIELDS and len(actual_rows) == 34,
            "The handoff packet contains exactly one row for every frozen transition.",
        ),
        check(
            "packet_exactly_copies_frozen_metadata",
            actual_rows == expected_rows,
            "All proposal fields and official-source locators match the frozen source.",
        ),
        check(
            "packet_remains_unreviewed",
            all(
                row["human_review_decision"] == "pending_human_review"
                and all(row[field] == "" for field in EMPTY_HUMAN_FIELDS)
                for row in actual_rows
            ),
            "No student or teacher review decision, initials, date, or evidence was auto-filled.",
        ),
        check(
            "no_outcome_fields_are_present",
            set(packet_header) == set(PACKET_FIELDS),
            "The packet carries only transition metadata and human-review placeholders.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Frozen metadata-only taxonomy handoff verification.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    source_header, source_rows = read_records(SOURCE_PATH)
    if args.render:
        if source_header != SOURCE_FIELDS:
            raise ValueError("Frozen taxonomy source schema is not recognized.")
        writer = csv.DictWriter(sys.stdout, fieldnames=PACKET_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(packet_rows(source_rows, sha256(SOURCE_PATH)))
        return
    report = build_report()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
