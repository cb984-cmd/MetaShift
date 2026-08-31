"""Export every safe project output and source snapshot for a GitHub Release."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOTS = ("artifacts", "results", "figures")
FORBIDDEN_PATH_PARTS = frozenset(
    {
        "raw",
        "aqs_qa",
        "aqs_hourly_poc",
        "__pycache__",
        ".pytest_cache",
        ".repro-venv",
        "metashift-repro-venv",
    }
)
SECRET_PATTERNS = {
    "github_token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "aqs_credential_assignment": re.compile(
        rb"""(?i)(?:AQS_API_KEY|AQS_API_EMAIL)\s*[:=]\s*["'][^"']{4,}"""
    ),
    "bearer_token": re.compile(rb"(?i)authorization\s*[:=]\s*bearer\s+\S+"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a complete public-safe MetaShift project archive."
    )
    parser.add_argument(
        "--evidence-commit",
        default=None,
        help="Verified evidence commit; defaults to results/release_gate.json.",
    )
    parser.add_argument(
        "--source-commit",
        default="HEAD",
        help="Git revision to snapshot as source (default: HEAD).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence_bundle"),
        help="Ignored directory for generated release assets.",
    )
    return parser.parse_args()


def git_output(arguments: list[str]) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def resolve_commit(revision: str) -> str:
    return git_output(["rev-parse", f"{revision}^{{commit}}"])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def credential_pattern_name(data: bytes) -> str | None:
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(data):
            return name
    return None


def is_safe_relative_output_path(relative: Path) -> bool:
    return (
        bool(relative.parts)
        and relative.parts[0] in OUTPUT_ROOTS
        and not any(part.lower() in FORBIDDEN_PATH_PARTS for part in relative.parts)
    )


def require_clean_worktree() -> None:
    if git_output(["status", "--porcelain"]):
        raise RuntimeError(
            "Complete public archive requires a clean source worktree so its "
            "source snapshot is unambiguous."
        )


def load_verified_evidence_commit() -> str:
    gate_path = ROOT / "results" / "release_gate.json"
    comparison_path = ROOT / "results" / "reproducibility_comparison.json"
    if not gate_path.is_file() or not comparison_path.is_file():
        raise FileNotFoundError(
            "Complete archive requires release_gate.json and "
            "reproducibility_comparison.json."
        )
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    evidence_commit = str(gate.get("git_commit", ""))
    if not gate.get("all_checks_passed") or not evidence_commit:
        raise RuntimeError("Complete archive requires a passing release gate.")
    if not (
        comparison.get("all_core_artifacts_match")
        and comparison.get("source_commits_match")
        and comparison.get("first_git_commit") == evidence_commit
        and comparison.get("second_git_commit") == evidence_commit
    ):
        raise RuntimeError(
            "Complete archive requires a two-environment comparison matching "
            "the release-gate evidence commit."
        )
    return resolve_commit(evidence_commit)


def collect_safe_output_paths() -> tuple[list[Path], list[str]]:
    included: list[Path] = []
    excluded: list[str] = []
    for root_name in OUTPUT_ROOTS:
        root = ROOT / root_name
        if not root.is_dir():
            raise FileNotFoundError(f"Missing generated output directory: {root}")
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if not is_safe_relative_output_path(relative):
                excluded.append(relative.as_posix())
                continue
            credential_pattern = credential_pattern_name(path.read_bytes())
            if credential_pattern is not None:
                raise ValueError(
                    f"Credential-like content ({credential_pattern}) found in "
                    f"candidate public output: {relative}"
                )
            included.append(path)
    return sorted(included), sorted(excluded)


def verify_source_snapshot(source_archive: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(source_archive)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            credential_pattern = credential_pattern_name(archive.read(entry))
            if credential_pattern is not None:
                raise ValueError(
                    "Credential-like content "
                    f"({credential_pattern}) found in source snapshot entry {entry.filename}"
                )


def archive_readme(
    evidence_commit: str, source_commit: str, output_count: int, excluded: list[str]
) -> str:
    return f"""# MetaShift-Bench complete public-safe archive

This archive is a complete safe snapshot for public review.

* Verified evidence commit: `{evidence_commit}`
* Source snapshot commit: `{source_commit}`
* Safe generated output files included: {output_count}
* Outputs excluded by path policy: {len(excluded)}

`source/` contains an exact Git archive of the source snapshot. `process/`
contains Git history through that snapshot. `outputs/` contains every safe file
present under `artifacts/`, `results/`, and `figures/` when this archive was
created.

The archive intentionally excludes EPA raw archives, raw AQS API responses,
credentials, local environment files, and virtual environments. Legacy smoke,
development, and superseded diagnostic outputs are included for process
transparency, but they do not support the final scientific claims. Those claims
are limited to the passing release-gate evidence for the verified evidence
commit above.
"""


def main() -> None:
    args = parse_args()
    require_clean_worktree()
    evidence_commit = (
        resolve_commit(args.evidence_commit)
        if args.evidence_commit is not None
        else load_verified_evidence_commit()
    )
    verified_commit = load_verified_evidence_commit()
    if evidence_commit != verified_commit:
        raise RuntimeError(
            "--evidence-commit must match the passing release-gate evidence commit."
        )
    source_commit = resolve_commit(args.source_commit)
    source_archive = subprocess.check_output(
        ["git", "archive", "--format=zip", source_commit], cwd=ROOT
    )
    verify_source_snapshot(source_archive)
    git_history = git_output(
        [
            "--no-pager",
            "log",
            "--all",
            "--decorate",
            "--date=iso-strict",
            "--format=fuller",
        ]
    )
    output_paths, excluded = collect_safe_output_paths()

    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_short = evidence_commit[:12]
    source_short = source_commit[:12]
    archive_path = output_dir / (
        "MetaShift-Bench-complete-safe-archive-"
        f"evidence-{evidence_short}-source-{source_short}.zip"
    )
    manifest_path = output_dir / (
        "MetaShift-Bench-complete-safe-archive-"
        f"evidence-{evidence_short}-source-{source_short}-manifest.json"
    )
    source_entry = f"source/MetaShift-Bench-source-{source_short}.zip"
    manifest = {
        "archive_kind": "complete_public_safe_project_archive",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "verified_evidence_commit": evidence_commit,
        "source_snapshot_commit": source_commit,
        "source_snapshot_entry": source_entry,
        "source_snapshot_sha256": sha256_bytes(source_archive),
        "git_history_entry": "process/git-history.txt",
        "safe_output_roots": list(OUTPUT_ROOTS),
        "excluded_path_policy": sorted(FORBIDDEN_PATH_PARTS),
        "excluded_paths": excluded,
        "scientific_interpretation_boundary": (
            "Only artifacts covered by the passing release gate for the verified "
            "evidence commit support the final benchmark claims. Legacy diagnostics "
            "are retained for transparent process history."
        ),
        "files": [
            {
                "path": f"outputs/{path.relative_to(ROOT).as_posix()}",
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in output_paths
        ],
    }
    temporary_archive = archive_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(
        temporary_archive, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr(
            "README.md",
            archive_readme(evidence_commit, source_commit, len(output_paths), excluded),
        )
        archive.writestr("process/git-history.txt", git_history + "\n")
        archive.writestr(source_entry, source_archive)
        archive.writestr("archive_manifest.json", json.dumps(manifest, indent=2))
        for path in output_paths:
            archive.write(path, f"outputs/{path.relative_to(ROOT).as_posix()}")
    temporary_archive.replace(archive_path)
    sidecar_manifest = {
        **manifest,
        "archive_path": archive_path.name,
        "archive_sha256": sha256_file(archive_path),
    }
    manifest_path.write_text(json.dumps(sidecar_manifest, indent=2), encoding="utf-8")
    print(archive_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
