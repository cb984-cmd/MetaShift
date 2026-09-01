"""Package existing v0.5 frozen evidence without rerunning or replacing it."""

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
AUDIT_PATH = ROOT / "paper" / "upgrade" / "V05_EXECUTION_AUDIT.md"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_complete_public_archive import credential_pattern_name, verify_source_snapshot
from scripts.verify_v05_frozen_result_provenance import MANIFEST_PATH, build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive existing v0.5 frozen evidence without recomputation."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("evidence_bundle"))
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
        raise RuntimeError("Frozen evidence export requires a clean source worktree.")


def bundle_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve()
    expected_root = (ROOT / "evidence_bundle").resolve()
    if candidate.parent != expected_root:
        raise ValueError("Archive paths must be files directly under evidence_bundle/.")
    return candidate


def publish_without_overwrite(temporary_path: Path, final_path: Path) -> None:
    os.link(temporary_path, final_path)
    temporary_path.unlink()


def main() -> None:
    args = parse_args()
    require_clean_worktree()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_report(manifest)
    if not report["all_checks_passed"]:
        raise RuntimeError("Frozen-result provenance failed; refusing export.")
    archival = manifest["archival_plan"]
    authority = manifest["execution_authority"]
    if not AUDIT_PATH.is_file():
        raise FileNotFoundError("Tracked v0.5 post-execution audit is absent.")
    output_dir = (ROOT / args.output_dir).resolve()
    if output_dir != (ROOT / "evidence_bundle").resolve():
        raise ValueError("The v0.5 archive must use the declared evidence_bundle directory.")
    source_tag = str(archival["source_snapshot_tag"])
    if (
        source_tag != authority["execution_freeze_tag"]
        or git_bytes(["rev-parse", f"{source_tag}^{{commit}}"]).decode().strip()
        != authority["execution_commit"]
    ):
        raise ValueError("Archive source tag is not the executed freeze snapshot.")
    archive_path = bundle_path(str(archival["archive_path"]))
    sidecar_path = bundle_path(str(archival["sidecar_manifest_path"]))
    if archive_path.exists() or sidecar_path.exists():
        raise FileExistsError("Frozen archive or sidecar already exists; refusing overwrite.")
    source_archive = git_bytes(["archive", "--format=zip", source_tag])
    verify_source_snapshot(source_archive)
    output_dir.mkdir(parents=True, exist_ok=True)
    locks = [archive_path.with_suffix(".zip.lock"), sidecar_path.with_suffix(".json.lock")]
    temporary_paths: list[Path] = []
    acquired: list[Path] = []
    source_entry = f"source/MetaShift-{source_tag}.zip"
    archive_manifest = {
        "archive_kind": "v05_frozen_one_time_answerability_evidence",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "execution_freeze_tag": authority["execution_freeze_tag"],
        "execution_claim_tag": authority["execution_claim_tag"],
        "execution_commit": authority["execution_commit"],
        "source_snapshot_entry": source_entry,
        "source_snapshot_sha256": hashlib.sha256(source_archive).hexdigest(),
        "tracked_provenance_manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
        "tracked_provenance_manifest_sha256": sha256(MANIFEST_PATH),
        "tracked_execution_audit": AUDIT_PATH.relative_to(ROOT).as_posix(),
        "tracked_execution_audit_sha256": sha256(AUDIT_PATH),
        "files": [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"],
             "evidence_role": item["evidence_role"]}
            for item in manifest["artifacts"]
        ],
        "interpretation_boundary": manifest["evidence_role"],
        "no_rerun_rule": archival["no_rerun_rule"],
    }
    try:
        for lock in locks:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            acquired.append(lock)
        if archive_path.exists() or sidecar_path.exists():
            raise FileExistsError("Frozen archive or sidecar already exists; refusing overwrite.")
        with tempfile.NamedTemporaryFile(
            dir=output_dir, prefix=f"{archive_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        temporary_paths.append(temporary_path)
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "README.md",
                "# MetaShift v0.5 frozen answerability evidence\n\n"
                "This archive preserves existing byte-identical outputs from the sole "
                "authorized execution. It does not rerun the executor or establish "
                "real-world mechanisms, external validity, or deployment readiness.\n",
            )
            archive.writestr(source_entry, source_archive)
            archive.writestr("provenance/v05_frozen_result_manifest.json", MANIFEST_PATH.read_bytes())
            archive.writestr("provenance/V05_EXECUTION_AUDIT.md", AUDIT_PATH.read_bytes())
            archive.writestr("archive_manifest.json", json.dumps(archive_manifest, indent=2))
            for item in manifest["artifacts"]:
                payload = (ROOT / item["path"]).read_bytes()
                if credential_pattern_name(payload) is not None:
                    raise ValueError(f"Credential-like content found in {item['path']}.")
                archive.writestr(f"outputs/{item['path']}", payload)
        publish_without_overwrite(temporary_path, archive_path)
        temporary_paths.remove(temporary_path)
        sidecar = {**archive_manifest, "archive_path": archive_path.name, "archive_sha256": sha256(archive_path)}
        with tempfile.NamedTemporaryFile(
            dir=output_dir, prefix=f"{sidecar_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(sidecar, indent=2).encode("utf-8"))
        temporary_paths.append(temporary_path)
        publish_without_overwrite(temporary_path, sidecar_path)
        temporary_paths.remove(temporary_path)
    finally:
        for path in temporary_paths + acquired:
            if path.exists():
                path.unlink()
    print(archive_path)
    print(sidecar_path)


if __name__ == "__main__":
    main()
