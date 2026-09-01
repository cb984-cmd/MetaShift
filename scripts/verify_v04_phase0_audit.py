"""Verify the tracked and local evidence-boundary checks for v0.4 Phase 0."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
BENCHMARK_PATH = ROOT / "configs" / "benchmark_release_v2.json"
AUDIT_PATH = ROOT / "paper" / "upgrade" / "PHASE_0_EVIDENCE_AND_CONTAMINATION_AUDIT.md"
CANDIDATE_AUDIT_PATH = ROOT / "artifacts" / "v04_candidate_component_audit.json"
ARCHIVE_PATH = ROOT / "evidence_bundle" / "MetaShift-Bench-evidence-57d678ecabeb.zip"
ARCHIVE_MANIFEST_PATH = (
    ROOT / "evidence_bundle" / "MetaShift-Bench-evidence-57d678ecabeb-manifest.json"
)
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "v04_phase0_verification.json"

FROZEN_TAG = "v0.3.2-evidence-final"
FROZEN_COMMIT = "57d678ecabebff724d898abe626c9ef80538775b"
FROZEN_CASE_SHA256 = (
    "065b1b65c231c5298fb4969a7b5669f3ae8850b9228d50afee7d98422575e099"
)
ARCHIVE_SHA256 = "4cc5293ad3dc5725c49d8804ed3782b434df2b408e4143f99fc9176c322163bf"
ARCHIVE_MANIFEST_SHA256 = (
    "76a4de7748e31b2c7c5f08b76cf1fdb1d609ec997842bf336d7d0506bfb383b9"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the CI-safe tracked Phase 0 audit; optionally verify local "
            "ignored evidence artifacts."
        )
    )
    parser.add_argument(
        "--verify-local-artifacts",
        action="store_true",
        help="Also require local ignored artifacts and the immutable release tag.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def source_hash(summary: dict[str, object], path: str) -> str | None:
    sources = summary.get("artifact_sources", [])
    if not isinstance(sources, list):
        return None
    for source in sources:
        if isinstance(source, dict) and source.get("path") == path:
            value = source.get("sha256")
            return value if isinstance(value, str) else None
    return None


def tracked_checks() -> list[dict[str, object]]:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    required_audit_markers = (
        "Gate 0 decision: PASS",
        "no candidate post-window observations",
        "six components",
        "nine eligible anchors",
        "35 physical sites",
        "294-site",
        "not eligibility or blindness",
        "v0.3.2-evidence-final",
    )
    expected_source_hashes = {
        "artifacts/data_gate/summary.json": (
            "10a0117f6a1debc664795705008002e91be9d1783315efbe30dc717804d2d906"
        ),
        "artifacts/stable_synthetic_case_manifest.json": (
            "77b695d3e8e7a230512fd4b697b93d3ce0f920116fb15286ea20cce5d9e123e7"
        ),
        "artifacts/stable_synthetic_case_split_audit.json": (
            "56671b8d44ed2581d7be3a181178551bece2daecdf6357a9d91fceb0806956d5"
        ),
    }
    return [
        check(
            "frozen_evidence_identity",
            summary.get("evidence_version") == "v0.3.2"
            and summary.get("frozen_evidence", {}).get("tag") == FROZEN_TAG
            and summary.get("frozen_evidence", {}).get("commit") == FROZEN_COMMIT
            and summary.get("algorithm_superiority_claim") is False,
            "Tracked authority preserves the v0.3.2 immutable evidence identity.",
        ),
        check(
            "frozen_benchmark_binding",
            summary.get("case_manifest_sha256") == FROZEN_CASE_SHA256
            and benchmark.get("result_label") == "stable_full_v2"
            and benchmark.get("stable_synthetic_cases", {}).get(
                "case_and_donor_sha256"
            )
            == FROZEN_CASE_SHA256,
            "Tracked frozen summary and benchmark config bind the same v2 case manifest.",
        ),
        check(
            "tracked_source_hash_index",
            all(source_hash(summary, path) == expected for path, expected in expected_source_hashes.items()),
            "Tracked evidence summary indexes the required ignored local artifacts by SHA-256.",
        ),
        check(
            "phase_zero_scope_recorded",
            all(marker in audit_text for marker in required_audit_markers),
            "Phase 0 record states the protected baseline, metadata-only candidate audit, and no-outcome boundary.",
        ),
    ]


def local_checks() -> list[dict[str, object]]:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    expected_local_hashes = {
        ROOT / "artifacts" / "data_gate" / "summary.json": source_hash(
            summary, "artifacts/data_gate/summary.json"
        ),
        ROOT / "artifacts" / "stable_synthetic_case_manifest.json": source_hash(
            summary, "artifacts/stable_synthetic_case_manifest.json"
        ),
        ROOT / "artifacts" / "stable_synthetic_case_split_audit.json": source_hash(
            summary, "artifacts/stable_synthetic_case_split_audit.json"
        ),
    }
    artifacts_match = all(
        expected is not None and path.is_file() and sha256(path) == expected
        for path, expected in expected_local_hashes.items()
    )
    candidate_report: dict[str, object] = {}
    if CANDIDATE_AUDIT_PATH.is_file():
        candidate_report = json.loads(CANDIDATE_AUDIT_PATH.read_text(encoding="utf-8"))
    tag_commit = subprocess.check_output(
        ["git", "rev-parse", FROZEN_TAG], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    return [
        check(
            "immutable_tag_resolution",
            tag_commit == FROZEN_COMMIT,
            "Local immutable v0.3.2 tag resolves to the frozen evidence commit.",
        ),
        check(
            "ignored_artifact_hashes",
            artifacts_match,
            "Local ignored artifacts match the hashes recorded in the tracked summary.",
        ),
        check(
            "evidence_archive_hashes",
            ARCHIVE_PATH.is_file()
            and ARCHIVE_MANIFEST_PATH.is_file()
            and sha256(ARCHIVE_PATH) == ARCHIVE_SHA256
            and sha256(ARCHIVE_MANIFEST_PATH) == ARCHIVE_MANIFEST_SHA256,
            "Local public-safe evidence archive and manifest match their recorded SHA-256 values.",
        ),
        check(
            "metadata_candidate_component_audit",
            candidate_report.get("eligible_anchor_count") == 238
            and candidate_report.get("prior_stable_input_physical_site_count") == 294
            and candidate_report.get("component_count") == 25
            and candidate_report.get("components_disjoint_from_prior_stable_input")
            == 6
            and candidate_report.get("anchors_in_disjoint_components") == 9
            and candidate_report.get("physical_sites_in_disjoint_components") == 35
            and candidate_report.get("all_eligible_anchors_accounted_for") is True,
            "The local metadata-only graph audit reproduces the Phase 0 candidate counts.",
        ),
    ]


def build_report(verify_local_artifacts: bool = False) -> dict[str, object]:
    checks = tracked_checks()
    if verify_local_artifacts:
        checks.extend(local_checks())
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": (
            "CI-safe tracked verification"
            if not verify_local_artifacts
            else "CI-safe tracked verification plus local ignored-artifact verification"
        ),
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = build_report(args.verify_local_artifacts)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
