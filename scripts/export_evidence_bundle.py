"""Export a public, auditable evidence bundle without raw data or credentials."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "evidence_bundle"
SAFE_FILES = (
    Path("MetaShift_项目结果汇总.txt"),
    Path("MODEL_DECISION.md"),
    Path("PROJECT_PLAN.md"),
    Path("REPRODUCIBILITY.md"),
    Path("configs/benchmark_release_v1.json"),
    Path("results/release_gate.json"),
    Path("results/reproducibility_comparison.json"),
    Path("artifacts/data_gate/data_manifest.csv"),
    Path("artifacts/data_gate/summary.json"),
    Path("artifacts/data_gate/state_summary.csv"),
    Path("artifacts/data_gate/transition_summary.csv"),
    Path("artifacts/stable_synthetic_case_manifest.json"),
    Path("artifacts/stable_synthetic_stable_full_v1_metrics.csv"),
    Path("artifacts/stable_synthetic_stable_full_v1_thresholds.csv"),
    Path("artifacts/stable_synthetic_stable_full_v1_bootstrap.csv"),
    Path("artifacts/reliability_ablation_stable_full_v1_metrics.csv"),
    Path("artifacts/reliability_ablation_stable_full_v1_bootstrap.csv"),
    Path("artifacts/benchmark_ablation_alignment.json"),
    Path("artifacts/real_transition_88101_event_audit.csv"),
    Path("artifacts/real_transition_88101_method_results.csv"),
    Path("artifacts/real_transition_88101_event_intervals.csv"),
    Path("artifacts/leave_one_donor_out_summary.csv"),
    Path("artifacts/time_placebo_summary.csv"),
    Path("artifacts/time_placebo_date_permutation_summary.json"),
    Path("artifacts/external_validation_evidence.csv"),
    Path("artifacts/data_gate_88502/data_manifest.csv"),
    Path("artifacts/data_gate_88502/summary.json"),
    Path("artifacts/real_transition_88502_event_audit.csv"),
    Path("figures/figure_manifest.csv"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    missing = [str(path) for path in SAFE_FILES if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(
            "Cannot export an incomplete evidence package; missing: " + ", ".join(missing)
        )
    figure_paths = sorted((ROOT / "figures").glob("*.png"))
    if not figure_paths:
        raise FileNotFoundError("No generated figures found.")
    files = [ROOT / path for path in SAFE_FILES] + figure_paths
    forbidden_parts = {"data", "raw", "aqs_qa"}
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in forbidden_parts for part in relative.parts):
            raise ValueError(f"Unsafe raw/API path selected for evidence bundle: {relative}")

    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
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
