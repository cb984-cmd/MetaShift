"""Verify public-document consistency for the MetaShift public repository.

Two-layer design:
  Layer 1 (CI-safe): Reads only git-tracked files (configs/current_evidence_summary_v2.json,
    public docs, configs). No dependency on gitignored artifacts/ or results/.
  Layer 2 (local release gate): evaluate_release_gate.py verifies the tracked summary
    matches the actual generated artifacts.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "results" / "document_consistency.json"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"

V2_PATH_FILES = [
    ROOT / "README.md",
    ROOT / "REPRODUCIBILITY.md",
    ROOT / "paper" / "MANUSCRIPT_DRAFT.md",
    ROOT / "paper" / "CLAIM_EVIDENCE_MAP.csv",
    ROOT / "paper" / "SUBMISSION_CHECKLIST.md",
]

STALE_COUNT_FILES = [
    ROOT / "README.md",
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
    ],
}

ACTIVE_SECTION_BLOCKERS = ("superseded", "historical", "archived", "v0.1", "v0.2")
V2_PATH_TOKENS = [
    "stable_full_v1",
    "benchmark_release_v1",
    "benchmark_ablation_alignment.json",
    "synthetic_risk_coverage_curve.csv",
    "real_event_coverage_summary.json",
    "evidence_tier_sensitivity_summary.csv",
]
STALE_COUNT_PATTERNS = [r"\b261\b", r"\b292\b", r"\b113\b", r"\b414\b"]
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
    if any(token in line for token in ACTIVE_SECTION_BLOCKERS):
        return True
    start = max(0, index - 6)
    for cursor in range(start, index):
        previous = lines[cursor].strip().lower()
        if not previous:
            continue
        if "historical" in previous or "superseded" in previous:
            return True
        if previous.startswith("#") and not (
            "historical" in previous or "superseded" in previous
        ):
            break
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
        "eligible_anchors": summary["data_gate"]["eligible_anchors"],
        "anchors_3donors": summary["data_gate"]["anchors_with_three_distinct_physical_donors"],
        "complete": summary["real_event_audit"]["complete_comparisons"],
        "insufficient_donors": summary["real_event_audit"]["insufficient_geographic_donors"],
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
    files_to_check = [
        ROOT / "README.md",
        ROOT / "paper" / "MANUSCRIPT_DRAFT.md",
    ]
    violations: list[dict[str, object]] = []
    for path in files_to_check:
        text = path.read_text(encoding="utf-8")
        # Check the file contains the correct ratio
        if expected_pattern not in text:
            # Check if it has a wrong ratio like 0/30
            wrong = re.findall(r"\b\d+/\d+\b", text)
            doc_review_wrong = [w for w in wrong if w.endswith(f"/{reviewed}") is False
                                and "document" in text[max(0, text.find(w)-100):text.find(w)+100].lower()
                                and "/" in w]
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
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    violations: list[dict[str, object]] = []
    # Check README mentions the correct gate count
    gate_pattern = rf"\b{target}/{target}\b"
    if not re.search(gate_pattern, readme):
        violations.append({
            "file": "README.md",
            "expected": f"{target}/{target}",
            "issue": "README does not show current release gate check count",
        })
    return make_check(
        "release_gate_count_consistency",
        not violations,
        f"README must reference {target}/{target} release gate.",
        violations,
    )


def check_evidence_version_consistency() -> dict[str, object]:
    """Current evidence version must be consistent in README."""
    summary = load_summary()
    version = summary["evidence_version"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    violations: list[dict[str, object]] = []
    if version not in readme:
        violations.append({
            "file": "README.md",
            "expected_version": version,
            "issue": f"Evidence version {version} not found in README",
        })
    return make_check(
        "evidence_version_consistency",
        not violations,
        f"README must reference evidence version {version}.",
        violations,
    )


def check_interval_coverage_status() -> dict[str, object]:
    """Manuscript must document interval coverage status correctly."""
    summary = load_summary()
    fixed_status = summary["interval_coverage"]["fixed_weight_status"]
    selection_status = summary["interval_coverage"]["selection_aware_status"]
    manuscript = (ROOT / "paper" / "MANUSCRIPT_DRAFT.md").read_text(encoding="utf-8").lower()
    violations: list[dict[str, object]] = []
    if fixed_status == "complete" and "coverage" not in manuscript:
        violations.append({"issue": "Manuscript does not discuss coverage"})
    if selection_status == "infeasible_within_deadline":
        if "selection" not in manuscript and "donor-selection" not in manuscript:
            violations.append({"issue": "Manuscript does not mention selection-aware limitation"})
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
    readme_lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(readme_lines, start=1):
        if "v0.2" not in line.lower():
            continue
        lowered = line.lower()
        if in_historical_context(readme_lines, line_number - 1):
            continue
        if any(token in lowered for token in ("current", "active", "latest")):
            violations.append(
                {
                    "file": "README.md",
                    "line": line_number,
                    "content": line.strip(),
                    "issue": "v0.2 presented as current/active",
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
        "README must not present v0.2 as current, and reproducibility guidance must point to v2 configs.",
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
    return make_check(
        "claim_evidence_map_v2_paths",
        not violations,
        "CLAIM_EVIDENCE_MAP.csv must not reference v1 result paths.",
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
    report = build_report()
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
