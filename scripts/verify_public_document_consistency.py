"""Verify public-document consistency for the MetaShift public repository.

Two-layer design:
  Layer 1 (CI-safe): Reads only git-tracked files (configs/current_evidence_summary_v2.json,
    public docs, configs). No dependency on gitignored artifacts/ or results/.
  Layer 2 (local release gate): evaluate_release_gate.py verifies the tracked summary
    matches the actual generated artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "results" / "document_consistency.json"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"

PUBLIC_DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "PROJECT_PLAN.md",
    ROOT / "PAPER_OPTIMIZATION_PLAN.md",
    ROOT / "REPRODUCIBILITY.md",
    ROOT / "MODEL_DECISION.md",
    ROOT / "docs" / "study_protocol.md",
    ROOT / "paper" / "MANUSCRIPT_DRAFT.md",
    ROOT / "paper" / "CLAIM_EVIDENCE_MAP.csv",
    ROOT / "paper" / "SUBMISSION_CHECKLIST.md",
]

V2_PATH_FILES = PUBLIC_DOCUMENTS

STALE_COUNT_FILES = PUBLIC_DOCUMENTS

CURRENT_RELEASE_DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "PROJECT_PLAN.md",
    ROOT / "PAPER_OPTIMIZATION_PLAN.md",
    ROOT / "REPRODUCIBILITY.md",
    ROOT / "paper" / "MANUSCRIPT_DRAFT.md",
    ROOT / "paper" / "SUBMISSION_CHECKLIST.md",
]

EXTERNAL_REVIEW_DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "PAPER_OPTIMIZATION_PLAN.md",
    ROOT / "paper" / "MANUSCRIPT_DRAFT.md",
    ROOT / "paper" / "CLAIM_EVIDENCE_MAP.csv",
]

STALE_LANGUAGE_FILES = {
    ROOT / "README.md": [
        "paused pending rebuild",
        "paused while",
        "awaiting rebuild",
        "results are paused",
        "superseded for scientific use",
        "ready for evidence release tag",
    ],
    ROOT / "MODEL_DECISION.md": [
        "paused pending rebuild",
        "paused while",
        "awaiting rebuild",
        "results are paused",
    ],
    ROOT / "paper" / "MANUSCRIPT_DRAFT.md": [
        "paused pending rebuild",
        "paused while",
        "awaiting rebuild",
        "results are paused",
        "not a submission-ready report",
    ],
    ROOT / "PROJECT_PLAN.md": [
        "ready for evidence release tag",
        "awaiting evidence release",
        "awaiting donor rebuild",
        "waiting for donor rebuild",
    ],
    ROOT / "PAPER_OPTIMIZATION_PLAN.md": [
        "ready for evidence release tag",
        "awaiting evidence release",
        "awaiting rebuild",
    ],
    ROOT / "docs" / "study_protocol.md": [
        "ready for evidence release tag",
        "awaiting evidence release",
        "awaiting rebuild",
    ],
}

HISTORICAL_SECTION_MARKERS = (
    "superseded",
    "historical",
    "archived",
    "pre-remediation",
)
V2_PATH_TOKENS = [
    "stable_full_v1",
    "benchmark_release_v1",
    "benchmark_ablation_alignment.json",
    "synthetic_risk_coverage_curve.csv",
    "real_event_coverage_summary.json",
    "evidence_tier_sensitivity_summary.csv",
]
STALE_COUNT_PATTERNS = [
    r"\b261\s*[- ]event",
    r"\b271\s+events with at least three",
    r"\b1,050\s+records",
    r"\b0\.46802\b",
    r"\b26/26\b",
    r"\b34/34\b",
    r"\b56/56\b",
    r"\b0/34/53\b",
    r"\b62\.47%--67\.56%\b",
    r"\b98\.22%--99\.56%\b",
]
SENSITIVE_GIT_PATTERNS = [
    "*.env",
    "*credentials*",
    "*secret*",
    "*api_key*",
    "*password*",
    "daily_88101_*.zip",
    "daily_88502_*.zip",
    "*.pickle",
    "*venv*",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify tracked MetaShift public-document consistency."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_PATH,
        help="Report path, relative to the repository root by default.",
    )
    return parser.parse_args()


def resolve_from_root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def make_check(
    name: str, passed: bool, detail: str, violations: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "name": name,
        "passed": bool(passed),
        "detail": detail,
        "violations": violations or [],
    }


def load_summary() -> dict:
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def in_historical_context(lines: list[str], index: int) -> bool:
    line = lines[index].lower()
    if any(token in line for token in HISTORICAL_SECTION_MARKERS):
        return True
    start = max(0, index - 6)
    for cursor in range(index - 1, start - 1, -1):
        previous = lines[cursor].strip().lower()
        if not previous:
            continue
        if any(token in previous for token in HISTORICAL_SECTION_MARKERS):
            return True
        if previous.startswith("#") and not (
            any(token in previous for token in HISTORICAL_SECTION_MARKERS)
        ):
            break
    for cursor in range(index + 1, min(len(lines), index + 3)):
        following = lines[cursor].strip().lower()
        if any(token in following for token in HISTORICAL_SECTION_MARKERS):
            return True
    return False


def collect_line_violations(path: Path, patterns: list[str]) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if in_historical_context(lines, line_number - 1):
            continue
        for pattern in patterns:
            if re.search(pattern, line):
                violations.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                        "pattern": pattern,
                        "content": line.strip(),
                    }
                )
    return violations


def check_v2_path_consistency() -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for path in V2_PATH_FILES:
        for violation in collect_line_violations(
            path, [re.escape(token) for token in V2_PATH_TOKENS]
        ):
            token = re.search(
                "|".join(re.escape(item) for item in V2_PATH_TOKENS),
                violation["content"],
            )
            if token is not None:
                violation["token"] = token.group(0)
            violations.append(violation)
    return make_check(
        "v2_path_consistency",
        not violations,
        "Active public documents should not reference superseded non-v2 result paths.",
        violations,
    )


def check_stale_count_consistency() -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for path in STALE_COUNT_FILES:
        violations.extend(collect_line_violations(path, STALE_COUNT_PATTERNS))
    return make_check(
        "stale_count_consistency",
        not violations,
        "Active public documents should not contain stale benchmark or evidence counts.",
        violations,
    )


def check_current_numbers_from_summary() -> dict[str, object]:
    """Verify core numbers from the tracked summary appear in the manuscript."""
    summary = load_summary()
    manuscript = (ROOT / "paper" / "MANUSCRIPT_DRAFT.md").read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", manuscript)
    required = {
        "canonical_records": summary["data_gate"]["canonical_records"],
        "monitor_series": summary["data_gate"]["monitor_series"],
        "eligible_anchors": summary["data_gate"]["eligible_anchors"],
        "anchors_1donor": summary["data_gate"][
            "anchors_with_one_distinct_physical_donor"
        ],
        "anchors_3donors": summary["data_gate"]["anchors_with_three_distinct_physical_donors"],
        "complete": summary["real_event_audit"]["complete_comparisons"],
        "insufficient_donors": summary["real_event_audit"]["insufficient_geographic_donors"],
        "input_failure": summary["real_event_audit"]["estimator_input_failure"],
        "supported": summary["evidence_tiers"]["supported_candidate_discontinuity"],
        "not_supported": summary["evidence_tiers"]["not_supported_by_available_evidence"],
        "inconclusive": summary["evidence_tiers"]["inconclusive_insufficient_evidence"],
    }
    violations: list[dict[str, object]] = []
    for key, value in required.items():
        pattern = rf"\b{value:,}\b|\b{value}\b"
        if not re.search(pattern, normalized):
            violations.append({"key": key, "expected_value": value, "type": "missing_in_manuscript"})
    return make_check(
        "current_numbers_in_manuscript",
        not violations,
        f"All {len(required)} core numbers from tracked summary must appear in manuscript.",
        violations,
    )


def check_external_audit_consistency() -> dict[str, object]:
    """External document review sample count must be consistent across all public docs."""
    summary = load_summary()
    reviewed = summary["external_document_review"]["reviewed_events"]
    confirmations = summary["external_document_review"]["site_specific_dated_confirmations"]
    expected_pattern = rf"{confirmations}/{reviewed}"  # e.g. "0/20"
    violations: list[dict[str, object]] = []
    for path in EXTERNAL_REVIEW_DOCUMENTS:
        text = path.read_text(encoding="utf-8")
        if expected_pattern not in text:
            violations.append({
                "file": str(path.relative_to(ROOT)),
                "expected": expected_pattern,
                "issue": f"Pattern '{expected_pattern}' not found",
            })
    return make_check(
        "external_audit_count_consistency",
        not violations,
        f"External document review must show {confirmations}/{reviewed} consistently.",
        violations,
    )


def check_release_gate_count() -> dict[str, object]:
    """Public docs must reference the correct release gate check count."""
    summary = load_summary()
    target = summary["release_gate_target_checks"]
    violations: list[dict[str, object]] = []
    gate_pattern = rf"\b{target}/{target}\b"
    for path in CURRENT_RELEASE_DOCUMENTS:
        if not re.search(gate_pattern, path.read_text(encoding="utf-8")):
            violations.append({
                "file": str(path.relative_to(ROOT)),
                "expected": f"{target}/{target}",
                "issue": "Document does not show current release-gate check count",
            })
    return make_check(
        "release_gate_count_consistency",
        not violations,
        f"All current release documents must reference {target}/{target}.",
        violations,
    )


def check_evidence_version_consistency() -> dict[str, object]:
    """Current tag and release URL must be consistent across public entry points."""
    summary = load_summary()
    version = summary["evidence_version"]
    frozen = summary["frozen_evidence"]
    tag = frozen["tag"]
    release_url = frozen["release_url"]
    violations: list[dict[str, object]] = []
    for path in CURRENT_RELEASE_DOCUMENTS:
        text = path.read_text(encoding="utf-8")
        if tag not in text or release_url not in text:
            violations.append({
                "file": str(path.relative_to(ROOT)),
                "expected_version": version,
                "expected_tag": tag,
                "expected_release_url": release_url,
                "issue": "Current frozen evidence tag or release URL is missing",
            })
    return make_check(
        "evidence_version_consistency",
        not violations,
        f"Current release documents must reference {tag}.",
        violations,
    )


def check_interval_coverage_status() -> dict[str, object]:
    """Manuscript must document interval coverage status correctly."""
    summary = load_summary()
    fixed_status = summary["interval_coverage"]["fixed_weight_status"]
    selection_status = summary["interval_coverage"]["selection_aware_status"]
    required_ranges = [
        f"{100 * summary['interval_coverage']['conditional_bootstrap_95_eval_coverage_range'][0]:.3f}%",
        f"{100 * summary['interval_coverage']['conditional_bootstrap_95_eval_coverage_range'][1]:.3f}%",
        f"{100 * summary['interval_coverage']['split_conformal_90_eval_coverage_range'][0]:.4f}%",
        f"{100 * summary['interval_coverage']['split_conformal_90_eval_coverage_range'][1]:.4f}%",
    ]
    documents = [
        ROOT / "PROJECT_PLAN.md",
        ROOT / "PAPER_OPTIMIZATION_PLAN.md",
        ROOT / "docs" / "study_protocol.md",
        ROOT / "paper" / "MANUSCRIPT_DRAFT.md",
    ]
    violations: list[dict[str, object]] = []
    for path in documents:
        text = path.read_text(encoding="utf-8")
        if fixed_status == "complete" and not all(token in text for token in required_ranges):
            violations.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "issue": "Fixed-weight interval coverage values are missing or stale",
                }
            )
    if selection_status == "infeasible_within_deadline":
        for path in documents:
            text = path.read_text(encoding="utf-8").lower()
            if "selection-aware" not in text or "infeasible" not in text:
                violations.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "issue": "Selection-aware coverage infeasibility is missing",
                    }
                )
    return make_check(
        "interval_coverage_documented",
        not violations,
        f"Fixed-weight: {fixed_status}; selection-aware: {selection_status}",
        violations,
    )


def check_stale_status_language() -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for path, phrases in STALE_LANGUAGE_FILES.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        lines = text.splitlines()
        for phrase in phrases:
            for match in re.finditer(re.escape(phrase.lower()), lowered):
                line_number = lowered[: match.start()].count("\n") + 1
                line_text = lines[line_number - 1] if line_number <= len(lines) else ""
                if in_historical_context(lines, line_number - 1):
                    continue
                violations.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                        "phrase": phrase,
                        "content": line_text.strip(),
                    }
                )
    return make_check(
        "stale_status_language",
        not violations,
        "Deprecated paused/rebuild/awaiting status language should be absent from active sections.",
        violations,
    )


def check_v02_not_presented_as_current() -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for path in PUBLIC_DOCUMENTS:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not any(version in line.lower() for version in ("v0.2", "v0.3.0", "v0.3.1")):
                continue
            if in_historical_context(lines, line_number - 1):
                continue
            violations.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "line": line_number,
                    "content": line.strip(),
                    "issue": "Superseded evidence version lacks historical marker",
                }
            )
    reproducibility = (ROOT / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
    primary_path_ok = (
        "configs/benchmark_release_v2.json" in reproducibility
        and "benchmark_release_v1" not in reproducibility
    )
    if not primary_path_ok:
        violations.append(
            {
                "file": "REPRODUCIBILITY.md",
                "issue": "primary reproduction path does not clearly reference v2 configs",
            }
        )
    return make_check(
        "v0_2_not_presented_as_current",
        not violations,
        "Superseded releases must be explicitly historical, and reproducibility guidance must point to v2 configs.",
        violations,
    )


def check_no_sensitive_files_in_git() -> dict[str, object]:
    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8"
    ).splitlines()
    regexes = [
        (
            pattern,
            re.compile(
                "^"
                + re.escape(pattern)
                .replace(r"\*", ".*")
                .replace(r"\?", ".")
                + "$",
                re.IGNORECASE,
            ),
        )
        for pattern in SENSITIVE_GIT_PATTERNS
    ]
    violations: list[dict[str, object]] = []
    for file_path in tracked:
        normalized = file_path.replace("\\", "/")
        for pattern, regex in regexes:
            if regex.search(normalized):
                violations.append({"file": normalized, "pattern": pattern})
                break
    return make_check(
        "no_sensitive_files_in_git",
        not violations,
        "Tracked files must exclude credentials, secrets, raw archives, pickles, and virtual environments.",
        violations,
    )


def check_claim_evidence_map_v2() -> dict[str, object]:
    path = ROOT / "paper" / "CLAIM_EVIDENCE_MAP.csv"
    text = path.read_text(encoding="utf-8")
    violations: list[dict[str, object]] = []
    if "stable_full_v1" in text:
        violations.append({"issue": "CLAIM_EVIDENCE_MAP contains stale v1 paths"})
    if "configs/current_evidence_summary_v2.json" not in text:
        violations.append({"issue": "CLAIM_EVIDENCE_MAP does not reference frozen v2 summary"})
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(
        not row.get("claim_id") or not row.get("evidence_artifact") or not row.get("status")
        for row in rows
    ):
        violations.append({"issue": "CLAIM_EVIDENCE_MAP has an incomplete claim row"})
    return make_check(
        "claim_evidence_map_v2_paths",
        not violations,
        "CLAIM_EVIDENCE_MAP.csv must use current sources and complete claim rows.",
        violations,
    )


def check_evidence_tier_config_reference() -> dict[str, object]:
    path = ROOT / "paper" / "CLAIM_EVIDENCE_MAP.csv"
    violations: list[dict[str, object]] = []
    target = "configs/evidence_tier_primary_v1.json"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            artifacts = row.get("evidence_artifact", "")
            if "evidence_tier_primary_v1.json" not in artifacts:
                continue
            if not (ROOT / target).exists():
                violations.append(
                    {
                        "file": "paper/CLAIM_EVIDENCE_MAP.csv",
                        "row": row_number,
                        "claim_id": row.get("claim_id"),
                        "missing_artifact": target,
                    }
                )
    return make_check(
        "evidence_tier_config_reference",
        not violations,
        "If CLAIM_EVIDENCE_MAP references evidence_tier_primary_v1.json, that config must exist.",
        violations,
    )


def build_report() -> dict[str, object]:
    checks = [
        check_v2_path_consistency(),
        check_stale_count_consistency(),
        check_current_numbers_from_summary(),
        check_external_audit_consistency(),
        check_release_gate_count(),
        check_evidence_version_consistency(),
        check_interval_coverage_status(),
        check_stale_status_language(),
        check_v02_not_presented_as_current(),
        check_no_sensitive_files_in_git(),
        check_claim_evidence_map_v2(),
        check_evidence_tier_config_reference(),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "all_checks_passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    output_path = resolve_from_root(args.output)
    report = build_report()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
