"""Create one content-addressed archive from the already frozen v0.4.1 bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_complete_public_archive import (
    credential_pattern_name,
    verify_source_snapshot,
)
from scripts.verify_v04_frozen_result_provenance import (
    MANIFEST_PATH,
    build_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive existing v0.4.1 frozen evidence without recomputation."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence_bundle"),
        help="Ignored directory for a release-asset archive and sidecar manifest.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_bytes(arguments: list[str]) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def require_clean_worktree() -> None:
    if git_bytes(["status", "--porcelain"]).strip():
        raise RuntimeError(
            "Frozen evidence archive requires a clean source worktree before packaging."
        )


def require_execution_source_tag(manifest: dict[str, object]) -> tuple[str, str]:
    authority = manifest["execution_authority"]
    archival = manifest["archival_plan"]
    source_tag = str(archival["source_snapshot_tag"])
    execution_tag = str(authority["execution_tag"])
    execution_commit = str(authority["execution_commit"])
    if source_tag != execution_tag:
        raise ValueError("The archive source tag must equal the execution tag.")
    source_commit = git_bytes(["rev-parse", f"{source_tag}^{{commit}}"]).decode(
        "utf-8"
    ).strip()
    if source_commit != execution_commit:
        raise ValueError("The archive source tag does not resolve to the execution commit.")
    return source_tag, execution_commit


def evidence_bundle_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve()
    expected_root = (ROOT / "evidence_bundle").resolve()
    if candidate.parent != expected_root:
        raise ValueError("Archive path must be a file directly under evidence_bundle/.")
    return candidate


def reserve_lock(path: Path) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(descriptor)


def publish_without_overwrite(temporary_path: Path, final_path: Path) -> None:
    os.link(temporary_path, final_path)
    temporary_path.unlink()


def main() -> None:
    args = parse_args()
    require_clean_worktree()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_report(manifest)
    if not report["all_checks_passed"]:
        raise RuntimeError("Frozen result provenance validation failed; refusing archive.")
    archival = manifest["archival_plan"]
    source_tag, execution_commit = require_execution_source_tag(manifest)
    output_dir = (ROOT / args.output_dir).resolve()
    expected_dir = (ROOT / "evidence_bundle").resolve()
    if output_dir != expected_dir:
        raise ValueError("The v0.4 archive must use the declared evidence_bundle directory.")
    archive_path = evidence_bundle_path(str(archival["archive_path"]))
    sidecar_path = evidence_bundle_path(str(archival["sidecar_manifest_path"]))
    if archive_path.exists() or sidecar_path.exists():
        raise FileExistsError(
            "Frozen archive or sidecar already exists; refusing to overwrite it."
        )
    source_archive = git_bytes(["archive", "--format=zip", source_tag])
    verify_source_snapshot(source_archive)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_lock_path = archive_path.with_name(f"{archive_path.name}.lock")
    sidecar_lock_path = sidecar_path.with_name(f"{sidecar_path.name}.lock")
    acquired_locks: list[Path] = []
    temporary_paths: list[Path] = []
    source_entry = f"source/MetaShift-{source_tag}.zip"
    archive_manifest = {
        "archive_kind": "v04_frozen_one_time_evidence",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "execution_tag": manifest["execution_authority"]["execution_tag"],
        "execution_commit": execution_commit,
        "source_snapshot_commit": execution_commit,
        "source_snapshot_entry": source_entry,
        "source_snapshot_sha256": hashlib.sha256(source_archive).hexdigest(),
        "tracked_provenance_manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
        "tracked_provenance_manifest_sha256": sha256(MANIFEST_PATH),
        "files": [
            {
                "path": entry["path"],
                "bytes": entry["bytes"],
                "sha256": entry["sha256"],
                "evidence_role": entry["evidence_role"],
            }
            for entry in manifest["artifacts"]
        ],
        "interpretation_boundary": manifest["evidence_role"],
    }
    try:
        for lock_path in (archive_lock_path, sidecar_lock_path):
            reserve_lock(lock_path)
            acquired_locks.append(lock_path)
        if archive_path.exists() or sidecar_path.exists():
            raise FileExistsError(
                "Frozen archive or sidecar already exists; refusing to overwrite it."
            )
        with tempfile.NamedTemporaryFile(
            dir=output_dir, prefix=f"{archive_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        temporary_paths.append(temporary_path)
        with zipfile.ZipFile(
            temporary_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr(
                "README.md",
                (
                    "# MetaShift v0.4.1 frozen synthetic evidence\n\n"
                    "This archive preserves byte-identical outputs from the sole "
                    "authorized v0.4.1 execution. It does not establish real-world "
                    "scope attribution, mechanism attribution, AQS external validity, "
                    "or estimator superiority.\n"
                ),
            )
            archive.writestr(source_entry, source_archive)
            archive.writestr(
                "provenance/v04_frozen_result_manifest.json",
                MANIFEST_PATH.read_bytes(),
            )
            archive.writestr(
                "archive_manifest.json", json.dumps(archive_manifest, indent=2)
            )
            for entry in manifest["artifacts"]:
                source = ROOT / entry["path"]
                payload = source.read_bytes()
                if credential_pattern_name(payload) is not None:
                    raise ValueError(
                        f"Credential-like content found in {entry['path']}."
                    )
                archive.writestr(f"outputs/{entry['path']}", payload)
        publish_without_overwrite(temporary_path, archive_path)
        temporary_paths.remove(temporary_path)
        sidecar = {
            **archive_manifest,
            "archive_path": archive_path.name,
            "archive_sha256": sha256(archive_path),
        }
        with tempfile.NamedTemporaryFile(
            dir=output_dir, prefix=f"{sidecar_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(sidecar, indent=2).encode("utf-8"))
        temporary_paths.append(temporary_path)
        publish_without_overwrite(temporary_path, sidecar_path)
        temporary_paths.remove(temporary_path)
    finally:
        for temporary_path in temporary_paths:
            if temporary_path.exists():
                temporary_path.unlink()
        for lock_path in acquired_locks:
            if lock_path.exists():
                lock_path.unlink()
    print(archive_path)
    print(sidecar_path)


if __name__ == "__main__":
    main()
