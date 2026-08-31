"""Verify public-document consistency for the MetaShift public repository."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "results" / "document_consistency.json"

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
    name: str, passed: bool, detail: str, violations: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "name": name,
        "passed": bool(passed),
        "detail": detail,
        "violations": violations,
    }


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
        lowered = line.lower()
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


def check_current_numbers_from_artifacts() -> dict[str, object]:
    summary = json.loads(
        (ROOT / "artifacts" / "data_gate" / "summary.json").read_text(encoding="utf-8")
    )
    audit = pd.read_csv(ROOT / "artifacts" / "real_transition_88101_event_audit.csv")
    evidence = json.loads(
        (
            ROOT / "artifacts" / "real_transition_88101_evidence_tier_summary.json"
        ).read_text(encoding="utf-8")
    )
    manuscript = (ROOT / "paper" / "MANUSCRIPT_DRAFT.md").read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", manuscript)
    required = {
        "canonical_records": int(summary["canonical_records"]),
        "monitor_series": int(summary["monitor_series"]),
        "eligible_anchors": int(summary["eligible_anchors"]),
        "anchors_with_three_geographic_controls": int(
            summary["anchors_with_three_geographic_controls"]
        ),
        "complete": int((audit["audit_status"] == "complete").sum()),
        "insufficient_geographic_donors": int(
            (audit["audit_status"] == "insufficient_geographic_donors").sum()
        ),
        "supported_candidate_discontinuity": int(
            evidence["counts"]["supported_candidate_discontinuity"]
        ),
        "not_supported_by_available_evidence": int(
            evidence["counts"]["not_supported_by_available_evidence"]
        ),
        "inconclusive_insufficient_evidence": int(
            evidence["counts"]["inconclusive_insufficient_evidence"]
        ),
    }
    expected_exact = {
        "anchors_with_three_geographic_controls": 238,
        "complete": 228,
        "insufficient_geographic_donors": 325,
        "supported_candidate_discontinuity": 34,
        "not_supported_by_available_evidence": 122,
        "inconclusive_insufficient_evidence": 407,
    }
    violations: list[dict[str, object]] = []
    for key, expected in expected_exact.items():
        actual = required[key]
        if actual != expected:
            violations.append(
                {
                    "artifact_key": key,
                    "expected": expected,
                    "actual": actual,
                    "type": "artifact_value_mismatch",
                }
            )
    for key, value in required.items():
        pattern = rf"\b{value:,}\b|\b{value}\b"
        if re.search(pattern, normalized) is None:
            violations.append(
                {
                    "artifact_key": key,
                    "expected_value": value,
                    "type": "missing_in_manuscript",
                }
            )
    return make_check(
        "current_numbers_from_artifacts",
        not violations,
        "Current artifact-derived headline counts must match expectations and appear in the manuscript.",
        violations,
    )


def check_stale_status_language() -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for path, phrases in STALE_LANGUAGE_FILES.items():
        text = path.read_text(encoding="utf-8").lower()
        for phrase in phrases:
            for match in re.finditer(re.escape(phrase), text):
                line_number = text[: match.start()].count("\n") + 1
                original_line = path.read_text(encoding="utf-8").splitlines()[line_number - 1]
                violations.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                        "phrase": phrase,
                        "content": original_line.strip(),
                    }
                )
    return make_check(
        "stale_status_language",
        not violations,
        "Deprecated paused/rebuild status language should be absent from public-facing documents.",
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


def check_claim_evidence_map_artifact_existence() -> dict[str, object]:
    path = ROOT / "paper" / "CLAIM_EVIDENCE_MAP.csv"
    violations: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            artifacts = [
                item.strip()
                for item in row.get("evidence_artifact", "").split(";")
                if item.strip()
            ]
            for artifact in artifacts:
                artifact_path = ROOT / artifact
                if not artifact_path.exists():
                    violations.append(
                        {
                            "file": "paper/CLAIM_EVIDENCE_MAP.csv",
                            "row": row_number,
                            "claim_id": row.get("claim_id"),
                            "missing_artifact": artifact,
                        }
                    )
    return make_check(
        "claim_evidence_map_artifact_existence",
        not violations,
        "Every evidence_artifact path in CLAIM_EVIDENCE_MAP.csv must exist on disk.",
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
        check_current_numbers_from_artifacts(),
        check_stale_status_language(),
        check_v02_not_presented_as_current(),
        check_claim_evidence_map_artifact_existence(),
        check_no_sensitive_files_in_git(),
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
