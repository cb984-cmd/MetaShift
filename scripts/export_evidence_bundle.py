"""Export a public, auditable evidence bundle without raw data or credentials."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "evidence_bundle"
REQUIRED_SAFE_FILES = (
    Path("MetaShift_项目结果汇总.txt"),
    Path("MODEL_DECISION.md"),
    Path("PROJECT_PLAN.md"),
    Path("REPRODUCIBILITY.md"),
    Path("paper/MANUSCRIPT_DRAFT.md"),
    Path("paper/CLAIM_EVIDENCE_MAP.csv"),
    Path("paper/EXTERNAL_DOCUMENT_REVIEW.csv"),
    Path("docs/EXTERNAL_DOCUMENT_REVIEW.md"),
    Path("PAPER_OPTIMIZATION_PLAN.md"),
    Path("configs/benchmark_release_v1.json"),
    Path("configs/screening_sensitivity_v1.json"),
    Path("configs/effect_window_sensitivity_v1.json"),
    Path("configs/evidence_tier_primary_v1.json"),
    Path("configs/evidence_tier_sensitivity_v1.json"),
    Path("results/release_gate.json"),
    Path("results/manuscript_number_verification.json"),
    Path("artifacts/data_gate/data_manifest.csv"),
    Path("artifacts/data_gate/summary.json"),
    Path("artifacts/data_gate/state_summary.csv"),
    Path("artifacts/data_gate/transition_summary.csv"),
    Path("artifacts/screening_sensitivity_summary.csv"),
    Path("artifacts/stable_synthetic_case_manifest.json"),
    Path("artifacts/stable_synthetic_case_split_audit.json"),
    Path("artifacts/synthetic_perturbation_illustration_case.json"),
    Path("artifacts/stable_synthetic_stable_full_v1_metrics.csv"),
    Path("artifacts/stable_synthetic_stable_full_v1_thresholds.csv"),
    Path("artifacts/stable_synthetic_stable_full_v1_bootstrap.csv"),
    Path("artifacts/reliability_ablation_stable_full_v1_metrics.csv"),
    Path("artifacts/reliability_ablation_stable_full_v1_bootstrap.csv"),
    Path("artifacts/benchmark_ablation_alignment.json"),
    Path("artifacts/synthetic_risk_coverage_curve.csv"),
    Path("artifacts/real_event_coverage_summary.json"),
    Path("artifacts/real_transition_88101_event_audit.csv"),
    Path("artifacts/real_transition_88101_method_results.csv"),
    Path("artifacts/real_transition_88101_event_intervals.csv"),
    Path("artifacts/effect_window_sensitivity_details.csv"),
    Path("artifacts/effect_window_sensitivity_summary.csv"),
    Path("artifacts/reporting_scale_sensitivity_summary.csv"),
    Path("artifacts/nested_bootstrap_candidate_pool.csv"),
    Path("artifacts/nested_bootstrap_candidate_pool_summary.csv"),
    Path("artifacts/real_transition_88101_nested_selection_intervals.csv"),
    Path("artifacts/real_transition_88101_nested_selection_failures.csv"),
    Path("artifacts/leave_one_donor_out_summary.csv"),
    Path("artifacts/time_placebo_summary.csv"),
    Path("artifacts/time_placebo_date_permutation_summary.json"),
    Path("artifacts/real_transition_88101_evidence_tiers.csv"),
    Path("artifacts/real_transition_88101_evidence_tier_summary.json"),
    Path("artifacts/real_transition_88101_case_selection.csv"),
    Path("artifacts/real_transition_88101_case_study_selection.csv"),
    Path("artifacts/evidence_tier_sensitivity_details.csv"),
    Path("artifacts/evidence_tier_sensitivity_summary.csv"),
    Path("artifacts/real_transition_88101_anchor_coordinates.csv"),
    Path("artifacts/external_validation_evidence.csv"),
    Path("artifacts/external_document_review_summary.json"),
    Path("artifacts/hourly_poc_download_manifest.json"),
    Path("artifacts/hourly_poc_validation_summary.csv"),
    Path("artifacts/data_gate_88502/data_manifest.csv"),
    Path("artifacts/data_gate_88502/summary.json"),
    Path("artifacts/real_transition_88502_event_audit.csv"),
    Path("figures/figure_manifest.csv"),
)

OPTIONAL_SAFE_FILES = (
    Path("results/reproducibility_comparison.json"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_current_passing_release_gate(commit: str) -> None:
    """Refuse to package evidence from a failed or stale release assessment."""

    gate_path = ROOT / "results/release_gate.json"
    if not gate_path.is_file():
        raise FileNotFoundError("Cannot export without results/release_gate.json.")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if not gate.get("all_checks_passed"):
        raise RuntimeError("Cannot export because the release gate has not passed.")
    if gate.get("git_commit") != commit:
        raise RuntimeError(
            "Cannot export because the release gate was generated for a different "
            "source commit."
        )
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, encoding="utf-8"
    )
    if status.strip():
        raise RuntimeError(
            "Cannot export from a dirty source worktree; commit or discard source "
            "changes and rerun the release gate."
        )


def main() -> None:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    require_current_passing_release_gate(commit)
    missing = [
        str(path) for path in REQUIRED_SAFE_FILES if not (ROOT / path).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Cannot export an incomplete evidence package; missing: " + ", ".join(missing)
        )
    figure_manifest_path = ROOT / "figures/figure_manifest.csv"
    if not figure_manifest_path.is_file():
        raise FileNotFoundError("No primary figure manifest found.")
    figure_manifest = pd.read_csv(figure_manifest_path)
    figure_paths = [ROOT / "figures" / name for name in figure_manifest["figure"]]
    if not figure_paths or not all(path.is_file() for path in figure_paths):
        raise FileNotFoundError("One or more primary figures listed in the manifest is missing.")
    case_study_manifest = ROOT / "figures/case_studies/case_study_manifest.json"
    if not case_study_manifest.is_file():
        raise FileNotFoundError("No case-study manifest found.")
    case_study_paths = [
        ROOT / item["file"]
        for item in json.loads(case_study_manifest.read_text(encoding="utf-8"))
    ]
    if not all(path.is_file() for path in case_study_paths):
        raise FileNotFoundError("One or more case-study figures listed in the manifest is missing.")
    optional_files = []
    comparison_path = ROOT / "results/reproducibility_comparison.json"
    if comparison_path.is_file():
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        if (
            comparison.get("all_core_artifacts_match")
            and comparison.get("source_commits_match")
            and comparison.get("first_git_commit") == commit
            and comparison.get("second_git_commit") == commit
        ):
            optional_files.append(comparison_path)
    files = (
        [ROOT / path for path in REQUIRED_SAFE_FILES]
        + optional_files
        + figure_paths
        + case_study_paths
        + [case_study_manifest]
    )
    forbidden_parts = {"data", "raw", "aqs_qa"}
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in forbidden_parts for part in relative.parts):
            raise ValueError(f"Unsafe raw/API path selected for evidence bundle: {relative}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    archive_path = OUTPUT_DIR / f"MetaShift-Bench-evidence-{commit[:12]}.zip"
    manifest_path = OUTPUT_DIR / f"MetaShift-Bench-evidence-{commit[:12]}-manifest.json"
    manifest = {
        "git_commit": commit,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "safety_statement": (
            "This bundle intentionally excludes EPA raw archives, AQS API responses, "
            "credentials, and local environment variables."
        ),
        "reproducibility_comparison_included": bool(optional_files),
        "files": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
        archive.write(manifest_path, manifest_path.name)
    print(archive_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
