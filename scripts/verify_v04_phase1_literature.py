"""Verify structural and claim-boundary requirements for the Phase 1 audit."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "paper" / "upgrade" / "CLOSEST_WORK_MATRIX.csv"
AUDIT_PATH = ROOT / "paper" / "upgrade" / "NOVELTY_AUDIT.md"
SEARCH_LOG_PATH = ROOT / "paper" / "upgrade" / "LITERATURE_SEARCH_LOG.md"
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "v04_phase1_literature_verification.json"

REQUIRED_WORK_IDS = {
    "MW09",
    "WMT12",
    "BCF18",
    "TS17",
    "A21",
    "EYW10",
    "GE17",
    "CGAD24",
    "AR24",
    "JR25",
    "VW20",
    "EPA-AQS",
    "LC86",
}
REQUIRED_COLUMNS = {
    "work_id",
    "strongest_closest_work",
    "citation",
    "primary_url",
    "doi_or_identifier",
    "verification_status",
    "formal_problem",
    "inputs",
    "assumptions",
    "ground_truth",
    "local_common_distinction",
    "metadata_anchors",
    "physical_control_independence",
    "complete_event_universe",
    "synthetic_real_truth_separation",
    "risk_coverage",
    "explicit_abstention",
    "missing_negative_evidence",
    "post_selection_uncertainty",
    "exact_metashift_overlap",
    "exact_unresolved_gap",
    "novelty_effect",
}
REQUIRED_AUDIT_MARKERS = (
    "Gate 1 decision: PASS",
    "not a claim of priority",
    "pending Gate A",
    "weak metadata",
    "explicit abstention",
)
REQUIRED_SEARCH_MARKERS = (
    "Search date:** 2026-09-01",
    "Inclusion criteria",
    "Exclusion criteria",
    "Access and interpretation limits",
)
PROHIBITED_NOVELTY_PHRASES = ("first ever", "first-ever", "globally new")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Phase 1 closest-work evidence and bounded claims."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def load_rows() -> list[dict[str, str]]:
    with MATRIX_PATH.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def build_report() -> dict[str, object]:
    rows = load_rows()
    fieldnames = set(rows[0]) if rows else set()
    work_ids = {row.get("work_id", "") for row in rows}
    strongest = [
        row for row in rows if row.get("strongest_closest_work", "").lower() == "true"
    ]
    incomplete_rows = [
        row.get("work_id", "<missing>")
        for row in rows
        if any(not row.get(column, "").strip() for column in REQUIRED_COLUMNS)
    ]
    invalid_urls = [
        row.get("work_id", "<missing>")
        for row in rows
        if not row.get("primary_url", "").startswith("https://")
    ]
    texts = {
        "audit": AUDIT_PATH.read_text(encoding="utf-8"),
        "search_log": SEARCH_LOG_PATH.read_text(encoding="utf-8"),
    }
    prohibited = {
        name: phrase
        for name, text in texts.items()
        for phrase in PROHIBITED_NOVELTY_PHRASES
        if phrase in text.lower()
    }
    checks = [
        check(
            "matrix_schema",
            REQUIRED_COLUMNS.issubset(fieldnames),
            "The closest-work matrix has every required comparison dimension.",
        ),
        check(
            "required_primary_or_official_sources",
            REQUIRED_WORK_IDS.issubset(work_ids),
            "The matrix includes all required closest works and measurement-data context.",
        ),
        check(
            "six_direct_closest_works",
            len(strongest) >= 6,
            f"Matrix marks {len(strongest)} direct closest works; at least six are required.",
        ),
        check(
            "complete_verified_rows",
            not incomplete_rows and not invalid_urls,
            "Every source has a complete comparison row and canonical HTTPS URL.",
        ),
        check(
            "bounded_novelty_claim",
            all(marker in texts["audit"] for marker in REQUIRED_AUDIT_MARKERS)
            and not prohibited,
            "The audit records Gate 1, its pending theory condition, and no first-ever claim.",
        ),
        check(
            "reproducible_search_record",
            all(marker in texts["search_log"] for marker in REQUIRED_SEARCH_MARKERS),
            "The search log records date, criteria, and access limitations.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
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
