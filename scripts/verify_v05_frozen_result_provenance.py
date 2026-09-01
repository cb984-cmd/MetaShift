"""Verify preserved v0.5 output bytes and their one-time execution provenance."""

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
MANIFEST_PATH = ROOT / "configs" / "v05_frozen_result_manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify frozen v0.5 evidence without invoking its executor."
    )
    parser.add_argument(
        "--verify-results",
        action="store_true",
        help="Also run the existing read-only deterministic result verifier.",
    )
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
        return next(reader), sum(1 for _ in reader)


def root_relative_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise ValueError(f"Artifact path escapes the repository root: {relative_path}")
    return candidate


def git_text(arguments: list[str]) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def remote_tag_object_id(remote_listing: str, tag: str) -> str | None:
    reference = f"refs/tags/{tag}"
    matches = [
        line.split("\t", maxsplit=1)[0]
        for line in remote_listing.splitlines()
        if "\t" in line and line.split("\t", maxsplit=1)[1] == reference
    ]
    return matches[0] if len(matches) == 1 else None


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
    if path.stat().st_size != int(entry["bytes"]) or sha256(path) != entry["sha256"]:
        return False, f"bytes or SHA-256 differ for {relative_path}"
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
    return True, f"{relative_path} matches frozen bytes and declared shape."


def build_metadata_report(manifest: dict[str, Any]) -> dict[str, Any]:
    authority = manifest["execution_authority"]
    paths = [str(entry["path"]) for entry in manifest["artifacts"]]
    expected = {
        "artifacts/v05_answerability_frontier/v05_scope_pair_results.csv",
        "artifacts/v05_answerability_frontier/v05_calibration_policy.json",
        "artifacts/v05_answerability_frontier/v05_policy_metrics.csv",
        "artifacts/v05_answerability_frontier/v05_answerability_frontier.csv",
        "artifacts/v05_answerability_frontier/v05_certificate_validity.csv",
        "artifacts/v05_answerability_frontier/v05_failure_mode_map.csv",
        "artifacts/v05_answerability_frontier/v05_component_bootstrap.csv",
        "artifacts/v05_answerability_frontier/v05_execution_receipt.json",
        "artifacts/.v05_answerability_frontier_attempt.json",
    }
    checks = [
        check(
            "manifest_identity",
            manifest.get("manifest_id") == "v0.5.0-frozen-result-provenance"
            and manifest.get("evidence_status") == "frozen_one_time_execution_verified",
            "The manifest identifies completed one-time v0.5 evidence.",
        ),
        check(
            "complete_frozen_inventory",
            len(paths) == len(expected) and len(set(paths)) == len(expected) and set(paths) == expected,
            "The inventory names every declared output and the durable attempt record.",
        ),
        check(
            "freeze_and_claim_authority_pinned",
            authority.get("execution_freeze_tag") == "v0.5.0-answerability-freeze"
            and authority.get("execution_claim_tag") == "v0.5.0-answerability-execution-claim"
            and authority.get("execution_commit")
            == "14fd0fee4fb015e6c661299041e35ff704a27286",
            "The distinct annotated freeze and execution-claim authorities are pinned.",
        ),
        check(
            "archive_is_non_destructive_and_source_bound",
            manifest.get("archival_plan", {}).get("source_snapshot_tag")
            == authority.get("execution_freeze_tag")
            and manifest.get("archival_plan", {}).get("source_snapshot_commit")
            == authority.get("execution_commit")
            and manifest.get("archival_plan", {}).get("archive_path", "").startswith("evidence_bundle/")
            and "never invokes the executor" in manifest.get("archival_plan", {}).get("no_rerun_rule", ""),
            "The archive binds the executed source snapshot and forbids rerunning or replacing evidence.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Tracked v0.5 frozen-result provenance manifest validation.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def _tag_and_source_check(manifest: dict[str, Any], receipt: dict[str, Any]) -> None:
    authority = manifest["execution_authority"]
    freeze_tag = str(authority["execution_freeze_tag"])
    claim_tag = str(authority["execution_claim_tag"])
    commit = str(authority["execution_commit"])
    for tag, object_key in (
        (freeze_tag, "execution_freeze_tag_object"),
        (claim_tag, "execution_claim_tag_object"),
    ):
        if git_text(["cat-file", "-t", f"refs/tags/{tag}"]) != "tag":
            raise ValueError(f"{tag} is not an annotated local tag")
        if git_text(["rev-parse", f"{tag}^{{commit}}"]) != commit:
            raise ValueError(f"{tag} does not resolve to the executed commit")
        local_object = git_text(["rev-parse", tag])
        if local_object != authority[object_key]:
            raise ValueError(f"{tag} object differs from the pinned annotated tag object")
        remote = git_text(["ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"])
        if (
            remote_tag_object_id(remote, tag) != local_object
            or remote_peeled_tag_commit(remote, tag) != commit
        ):
            raise ValueError(f"origin {tag} differs from the pinned annotated tag")
    protocol_bytes = subprocess.check_output(
        ["git", "show", f"{freeze_tag}:configs/v05_answerability_protocol.json"], cwd=ROOT
    )
    execution_manifest_bytes = subprocess.check_output(
        ["git", "show", f"{freeze_tag}:configs/v05_answerability_execution_manifest.json"], cwd=ROOT
    )
    execution_manifest = json.loads(execution_manifest_bytes)
    allowed = receipt.get("allowed_input_hashes")
    if not isinstance(allowed, dict):
        raise ValueError("receipt lacks allowlisted input hashes")
    manifest_relative = "configs/v05_answerability_execution_manifest.json"
    bound_sources = {
        relative_path: source_hash
        for relative_path, source_hash in allowed.items()
        if relative_path != manifest_relative
    }
    if (
        hashlib.sha256(protocol_bytes).hexdigest() != authority["protocol_sha256"]
        or hashlib.sha256(execution_manifest_bytes).hexdigest()
        != authority["execution_manifest_sha256"]
        or execution_manifest.get("bound_input_sha256") != bound_sources
    ):
        raise ValueError("freeze-tag protocol, input manifest, and receipt source binding differ")
    for relative_path, expected_hash in allowed.items():
        source_bytes = subprocess.check_output(
            ["git", "show", f"{freeze_tag}:{relative_path}"], cwd=ROOT
        )
        if hashlib.sha256(source_bytes).hexdigest() != expected_hash:
            raise ValueError(f"freeze-tag source hash differs for {relative_path}")


def build_report(manifest: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    metadata = build_metadata_report(manifest)
    authority = manifest["execution_authority"]
    entries = manifest["artifacts"]
    entry_results = [artifact_check(entry, root) for entry in entries]
    receipt_path = root / "artifacts/v05_answerability_frontier/v05_execution_receipt.json"
    attempt_path = root / "artifacts/.v05_answerability_frontier_attempt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
    attempt = json.loads(attempt_path.read_text(encoding="utf-8")) if attempt_path.is_file() else {}
    payload_hashes = {
        Path(entry["path"]).name: {"bytes": entry["bytes"], "sha256": entry["sha256"]}
        for entry in entries
        if Path(entry["path"]).name != "v05_execution_receipt.json"
        and entry["path"] != "artifacts/.v05_answerability_frontier_attempt.json"
    }
    checks = [
        *metadata["checks"],
        check(
            "all_frozen_bytes_schemas_and_rows_match",
            all(passed for passed, _ in entry_results),
            " ".join(detail for _, detail in entry_results),
        ),
        check(
            "receipt_and_attempt_chain",
            receipt.get("protocol_id") == authority["protocol_id"]
            and receipt.get("execution_tag") == authority["execution_freeze_tag"]
            and receipt.get("execution_claim_tag") == authority["execution_claim_tag"]
            and receipt.get("execution_git_commit") == authority["execution_commit"]
            and receipt.get("execution_claim_tag_object") == authority["execution_claim_tag_object"]
            and receipt.get("protocol_sha256") == authority["protocol_sha256"]
            and receipt.get("execution_manifest_sha256") == authority["execution_manifest_sha256"]
            and receipt.get("execution_claim_input_bundle_sha256")
            == authority["allowlisted_input_bundle_sha256"]
            and receipt.get("execution_claim_runtime_sha256")
            == authority["runtime_environment_sha256"]
            and receipt.get("output_hashes") == payload_hashes
            and receipt.get("failure_count") == 0
            and attempt.get("state") == "completed"
            and attempt.get("receipt_sha256") == sha256(receipt_path)
            and attempt.get("execution_claim_tag_object") == authority["execution_claim_tag_object"],
            "The receipt binds all preceding payloads and the exclusive attempt binds its receipt.",
        ),
    ]
    try:
        _tag_and_source_check(manifest, receipt)
    except (KeyError, OSError, subprocess.CalledProcessError, ValueError) as error:
        checks.append(check("annotated_tags_and_frozen_source_binding", False, str(error)))
    else:
        checks.append(
            check(
                "annotated_tags_and_frozen_source_binding",
                True,
                "Local and origin annotated tags, exact tag objects, and every frozen allowlisted source match.",
            )
        )
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Byte-level v0.5 frozen output and one-time execution provenance validation; no execution.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_report(manifest)
    if args.verify_results and report["all_checks_passed"]:
        completed = subprocess.run(
            ["python", "scripts/verify_v05_answerability_results.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            result_report = json.loads(completed.stdout)
            result_passed = completed.returncode == 0 and result_report["all_checks_passed"]
        except (json.JSONDecodeError, KeyError):
            result_passed = False
        report["checks"].append(
            check(
                "existing_read_only_result_verifier",
                result_passed,
                "The existing full deterministic result verifier passed."
                if result_passed
                else f"Result verifier failed: {completed.stderr.strip() or completed.stdout[-500:]}",
            )
        )
        report["all_checks_passed"] = all(item["passed"] for item in report["checks"])
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
