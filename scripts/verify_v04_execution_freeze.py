"""Verify source, provenance, and no-output conditions before v0.4 execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "v04_identifiability_protocol.json"
MANIFEST_PATH = ROOT / "configs" / "v04_identifiability_execution_manifest.json"
RUNNER_PATH = ROOT / "scripts" / "run_v04_identifiability_benchmark.py"
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "v04_execution_freeze_verification.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the tracked v0.4 execution-freeze candidate."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def source_sha256(path: Path) -> str:
    """Hash tracked source as LF-normalized UTF-8 text, matching its Git blob."""

    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def build_report() -> dict[str, object]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract = protocol["output_contract"]
    allowlist = protocol["data_access"]["execution_input_allowlist"]
    expected_bound_paths = set(allowlist).difference({str(contract["execution_manifest"])})
    bound_hashes = manifest.get("bound_input_sha256", {})
    current_bound_hashes = {
        relative_path: source_sha256(ROOT / relative_path)
        for relative_path in expected_bound_paths
    }
    output_directory = ROOT / str(contract["directory"])
    attempt_record = ROOT / str(contract["attempt_record"])
    runner_source = RUNNER_PATH.read_text(encoding="utf-8")
    run_once_body = runner_source.split("def run_once(", maxsplit=1)[-1].split(
        "def main(", maxsplit=1
    )[0]
    checks = [
        check(
            "execution_candidate_identity",
            protocol.get("protocol_state") == "execution_freeze_candidate"
            and manifest.get("protocol_id") == protocol.get("protocol_id")
            and manifest.get("execution_freeze_tag")
            == contract.get("execution_freeze_tag"),
            "Protocol and execution manifest bind the same future execution tag.",
        ),
        check(
            "superseded_protocol_only_history",
            manifest.get("protocol_only_predecessor", {}).get("tag")
            == "v0.4.0-protocol-freeze"
            and manifest.get("protocol_only_predecessor", {}).get("commit")
            == "37e5bde5949018789e439d27ee2ac444f7b2e45d"
            and "Superseded before any v0.4 output"
            in manifest.get("protocol_only_predecessor", {}).get("disposition", ""),
            "The retained protocol-only tag is explicitly historical and pre-outcome.",
        ),
        check(
            "protocol_hash_binding",
            manifest.get("protocol_sha256") == source_sha256(PROTOCOL_PATH),
            "Execution manifest binds the exact corrected protocol SHA-256.",
        ),
        check(
            "all_nonself_inputs_are_hashed",
            set(bound_hashes) == expected_bound_paths
            and bound_hashes == current_bound_hashes,
            "The manifest hashes every allowlisted input except its non-self manifest file.",
        ),
        check(
            "no_external_data_loader",
            all(
                prohibited not in runner_source
                for prohibited in (
                    "read_csv",
                    "load_series",
                    "data/raw",
                    "AQS",
                    "requests.",
                    "urllib.",
                    "--input",
                    "--data",
                )
            ),
            "The runner contains no external-data loader, AQS client, or generic input argument.",
        ),
        check(
            "runtime_input_and_tag_guards",
            "ensure_allowlisted_inputs" in runner_source
            and "ensure_execution_preconditions" in runner_source
            and 'git_text(["status", "--porcelain"])' in runner_source
            and "remote_peeled_tag_commit" in runner_source
            and "validate_annotated_execution_tag" in runner_source
            and '"cat-file"' in runner_source
            and '"ls-remote"' in runner_source
            and "execution-freeze tag" in runner_source
            and "git_bytes([\"show\"" in runner_source,
            "The runner checks clean HEAD, tag identity, tagged source hashes, and the allowlist.",
        ),
        check(
            "atomic_single_attempt_and_receipts",
            "os.O_EXCL" in runner_source
            and "state\": \"started" in runner_source
            and "state\": \"failed" in runner_source
            and "state\": \"completed" in runner_source
            and "partial_output_hashes" in runner_source,
            "The runner has exclusive start, durable failure, and completed receipt paths.",
        ),
        check(
            "execution_path_cannot_bypass_preconditions",
            "preconditions = ensure_execution_preconditions(protocol)" in run_once_body
            and run_once_body.find("ensure_execution_preconditions(protocol)")
            < run_once_body.find("acquire_attempt("),
            "The only full execution path validates freeze preconditions before an attempt record.",
        ),
        check(
            "no_outputs_before_execution",
            not output_directory.exists() and not attempt_record.exists(),
            "No v0.4 result directory or one-time attempt record exists.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Tracked source and no-output execution-freeze verification.",
        "protocol_sha256": source_sha256(PROTOCOL_PATH),
        "execution_manifest_sha256": source_sha256(MANIFEST_PATH),
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = build_report()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
