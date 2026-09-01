"""Verify the preserved bytes and provenance of the one-time v0.4.1 outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "configs" / "v04_frozen_result_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify frozen v0.4.1 artifact bytes without rerunning the benchmark."
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def csv_shape(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.reader(source)
        header = next(reader)
        return header, sum(1 for _ in reader)


def root_relative_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if candidate == root.resolve() or root.resolve() not in candidate.parents:
        raise ValueError(f"Artifact path escapes the repository root: {relative_path}")
    return candidate


def git_text(arguments: list[str]) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode("utf-8").strip()


def tagged_blob_sha256(tag: str, path: str) -> str:
    blob = subprocess.check_output(["git", "show", f"{tag}:{path}"], cwd=ROOT)
    return hashlib.sha256(blob).hexdigest()


def remote_peeled_tag_commit(remote_listing: str, tag: str) -> str | None:
    reference = f"refs/tags/{tag}^{{}}"
    matches = [
        line.split("\t", maxsplit=1)[0]
        for line in remote_listing.splitlines()
        if "\t" in line and line.split("\t", maxsplit=1)[1] == reference
    ]
    return matches[0] if len(matches) == 1 else None


def artifact_check(entry: dict[str, Any], root: Path) -> tuple[bool, str]:
    relative_path = str(entry["path"])
    try:
        path = root_relative_path(root, relative_path)
    except ValueError as error:
        return False, str(error)
    if not path.is_file():
        return False, f"missing {relative_path}"
    if path.stat().st_size != int(entry["bytes"]):
        return False, f"byte count differs for {relative_path}"
    if sha256(path) != entry["sha256"]:
        return False, f"SHA-256 differs for {relative_path}"
    if entry["kind"] == "csv":
        header, rows = csv_shape(path)
        if header != entry["schema"] or rows != int(entry["data_rows"]):
            return False, f"schema or row count differs for {relative_path}"
    elif entry["kind"] == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not set(entry["required_keys"]).issubset(payload):
            return False, f"required JSON keys differ for {relative_path}"
    else:
        return False, f"unknown artifact kind for {relative_path}"
    return True, f"{relative_path} matches its frozen bytes and declared shape."


def build_metadata_report(manifest: dict[str, Any]) -> dict[str, Any]:
    authority = manifest["execution_authority"]
    artifact_paths = [entry["path"] for entry in manifest["artifacts"]]
    expected_paths = {
        "artifacts/v04_identifiability_core/v04_core_event_results.csv",
        "artifacts/v04_identifiability_core/v04_core_thresholds.json",
        "artifacts/v04_identifiability_core/v04_core_metrics.json",
        "artifacts/v04_identifiability_core/v04_core_bootstrap.json",
        "artifacts/v04_identifiability_core/v04_stress_results.csv",
        "artifacts/v04_identifiability_core/v04_execution_receipt.json",
        "artifacts/v04_identifiability_core/v04_result_verification.json",
        "artifacts/.v04_identifiability_core_attempt.json",
    }
    checks = [
        check(
            "manifest_identity",
            manifest.get("manifest_id") == "v0.4.1-frozen-result-provenance"
            and manifest.get("evidence_status") == "frozen_one_time_execution_verified",
            "The manifest identifies the completed v0.4.1 one-time evidence.",
        ),
        check(
            "complete_frozen_artifact_inventory",
            len(artifact_paths) == 8
            and len(set(artifact_paths)) == 8
            and set(artifact_paths) == expected_paths,
            "The manifest names exactly the receipt, attempt record, payloads, and result verification.",
        ),
        check(
            "execution_authority_is_pinned",
            authority.get("execution_tag") == "v0.4.1-execution-freeze"
            and authority.get("execution_commit")
            == "b286221f13b5da8c18dc30226114400d071421d1"
            and authority.get("prior_unrun_tag") == "v0.4.0-execution-freeze",
            "The executed and preserved-but-unrun tags are explicitly distinct.",
        ),
        check(
            "archive_plan_uses_existing_ignored_asset_root",
            manifest.get("archival_plan", {}).get("archive_path", "").startswith(
                "evidence_bundle/"
            )
            and manifest.get("archival_plan", {}).get("sidecar_manifest_path", "").startswith(
                "evidence_bundle/"
            ),
            "The existing ignored release-asset directory is the archival target.",
        ),
        check(
            "archive_source_is_execution_authority",
            manifest.get("archival_plan", {}).get("source_snapshot_tag")
            == authority.get("execution_tag"),
            "The archived source snapshot must be the exact execution-freeze tag.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Tracked frozen-result provenance manifest validation.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def build_report(
    manifest: dict[str, Any], root: Path = ROOT, *, verify_remote: bool = True
) -> dict[str, Any]:
    metadata = build_metadata_report(manifest)
    authority = manifest["execution_authority"]
    entry_results = [artifact_check(entry, root) for entry in manifest["artifacts"]]
    receipt_path = root / "artifacts/v04_identifiability_core/v04_execution_receipt.json"
    attempt_path = root / "artifacts/.v04_identifiability_core_attempt.json"
    verification_path = (
        root
        / "artifacts/v04_identifiability_core/v04_result_verification.json"
    )
    receipt: dict[str, Any] = {}
    attempt: dict[str, Any] = {}
    verification: dict[str, Any] = {}
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if attempt_path.is_file():
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    if verification_path.is_file():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    execution_tag = str(authority["execution_tag"])
    local_tag_matches = False
    remote_tag_matches = not verify_remote
    tagged_config_hashes_match = False
    try:
        local_tag_matches = (
            git_text(["cat-file", "-t", f"refs/tags/{execution_tag}"]) == "tag"
            and git_text(["rev-parse", f"{execution_tag}^{{commit}}"])
            == authority["execution_commit"]
        )
        tagged_config_hashes_match = (
            tagged_blob_sha256(
                execution_tag, "configs/v04_identifiability_protocol.json"
            )
            == authority["protocol_sha256"]
            and tagged_blob_sha256(
                execution_tag, "configs/v04_identifiability_execution_manifest.json"
            )
            == authority["execution_manifest_sha256"]
        )
        if verify_remote:
            remote_tag_matches = (
                remote_peeled_tag_commit(
                    git_text(
                        [
                            "ls-remote",
                            "origin",
                            f"refs/tags/{execution_tag}",
                            f"refs/tags/{execution_tag}^{{}}",
                        ]
                    ),
                    execution_tag,
                )
                == authority["execution_commit"]
            )
    except subprocess.CalledProcessError:
        local_tag_matches = False
        remote_tag_matches = False
        tagged_config_hashes_match = False
    output_hashes = receipt.get("output_hashes", {})
    manifest_payloads = {
        Path(entry["path"]).name: entry["sha256"]
        for entry in manifest["artifacts"]
        if entry["evidence_role"]
        not in {
            "preregistered_durable_execution_receipt",
            "post_execution_deterministic_replay_verification",
            "preregistered_durable_attempt_chain",
        }
    }
    receipt_hash_matches_attempt = (
        receipt_path.is_file()
        and attempt.get("execution_receipt_sha256") == sha256(receipt_path)
    )
    checks = [
        *metadata["checks"],
        check(
            "all_frozen_bytes_and_shapes_match",
            all(passed for passed, _ in entry_results),
            " ".join(detail for _, detail in entry_results),
        ),
        check(
            "receipt_and_attempt_chain",
            receipt.get("state") == "completed"
            and receipt.get("execution_tag") == execution_tag
            and receipt.get("execution_git_commit") == authority["execution_commit"]
            and receipt.get("remote_execution_tag_commit")
            == authority["execution_commit"]
            and receipt.get("protocol_sha256") == authority["protocol_sha256"]
            and receipt.get("execution_manifest_sha256")
            == authority["execution_manifest_sha256"]
            and receipt.get("protocol_freeze_tag")
            == authority["protocol_freeze_tag"]
            and receipt.get("output_hashes") == manifest_payloads
            and attempt.get("state") == "completed"
            and attempt.get("execution_tag") == execution_tag
            and attempt.get("execution_git_commit") == authority["execution_commit"]
            and attempt.get("protocol_sha256") == authority["protocol_sha256"]
            and attempt.get("execution_manifest_sha256")
            == authority["execution_manifest_sha256"]
            and attempt.get("remote_execution_tag_commit")
            == authority["execution_commit"]
            and receipt_hash_matches_attempt,
            "The receipt payload hashes and exclusive attempt chain match the manifest.",
        ),
        check(
            "post_execution_result_verification",
            verification.get("state") == "completed"
            and verification.get("all_checks_passed") is True
            and verification.get("scope") == "Post-execution v0.4 result validation."
            and verification.get("verification_output_path")
            == manifest["post_execution_verification"]["artifact_path"]
            and len(verification.get("checks", []))
            == int(manifest["post_execution_verification"]["check_count"])
            and sum(
                bool(item.get("passed"))
                for item in verification.get("checks", [])
                if isinstance(item, dict)
            )
            == int(manifest["post_execution_verification"]["passed_check_count"]),
            "The frozen deterministic replay verifier completed every declared check.",
        ),
        check(
            "local_and_remote_execution_tag",
            local_tag_matches and remote_tag_matches,
            "The annotated local and peeled origin execution tags resolve to the frozen commit.",
        ),
        check(
            "tagged_protocol_and_execution_manifest_hashes",
            tagged_config_hashes_match,
            "The execution tag's Git blobs match the frozen protocol and input-manifest hashes.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Byte-level frozen v0.4.1 result provenance validation; no benchmark execution.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_report(manifest)
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
