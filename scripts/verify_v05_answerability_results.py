"""Read-only verifier for a completed v0.5 answerability result bundle."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_v05_answerability_frontier as runner
from scripts import verify_v05_protocol_freeze as pre_outcome


PROTOCOL_PATH = ROOT / "configs" / "v05_answerability_protocol.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a v0.5 frozen answerability result bundle."
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="Skip deterministic in-memory replay; intended only for narrow tests.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_text(arguments: list[str]) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode("utf-8").strip()


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _paths(protocol: dict[str, Any]) -> dict[str, Path]:
    output = protocol["output_contract"]
    directory = ROOT / str(output["directory"])
    return {name: directory / name for name in output["files"]}


def _attempt_path(protocol: dict[str, Any]) -> Path:
    return ROOT / str(protocol["output_contract"]["attempt_record"])


def _read_csv_strict(path: Path, expected_columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Declared output is absent: {path}")
    frame = pd.read_csv(path, keep_default_na=False)
    if list(frame.columns) != expected_columns:
        raise ValueError(
            f"{path.name} schema differs from its declared output-contract schema."
        )
    return frame


def _coerce_pair_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    bool_columns = [
        "target_identity",
        "comparative_observation_identity",
        "certificate_answered",
        "oracle_answerable",
        "local_envelope_satisfied",
        "shared_envelope_satisfied",
    ]
    for column in bool_columns:
        values = result[column].astype(str)
        if not values.isin(["True", "False"]).all():
            raise ValueError(f"Pair result boolean column is malformed: {column}")
        result[column] = values == "True"
    numeric_columns = [
        "component_index",
        "nominal_q",
        "signal_h",
        "donor_mismatch_bound",
        "contamination_bound",
        "raw_field_magnitude",
        "pre_noise_bound",
        "post_noise_bound",
        "local_score",
        "shared_score",
        "q_effective_mean",
        "q_effective_min",
        "h_min",
        "realized_gap",
        "base_error_bound",
        "local_raw_error_bound",
        "shared_raw_error_bound",
        "local_error_bound",
        "shared_error_bound",
        "structural_margin",
        "certificate_threshold",
        "oracle_structural_margin",
        "oracle_threshold",
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="raise")
        if not np.isfinite(result[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Pair result numeric column is nonfinite: {column}")
    return result


def _coerce_metrics_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    integer_columns = ["total_events", "answered_events", "error_events"]
    numeric_columns = ["coverage", "conditional_error", "alpha"]
    for column in integer_columns:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(int)
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _coerce_frontier_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ["alpha", "frontier_coverage", "frontier_conditional_error"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["candidate_policy_count"] = pd.to_numeric(
        result["candidate_policy_count"], errors="raise"
    ).astype(int)
    return result


def _coerce_certificate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    integer_columns = [
        "total_pair_rows",
        "certificate_answered_pair_rows",
        "certificate_error_events",
        "certificate_answered_events",
        "envelope_violating_events",
        "oracle_answerable_pair_rows",
        "q0_certificate_answered_pair_rows",
    ]
    numeric_columns = [
        "certificate_pair_coverage",
        "certificate_conditional_error",
        "envelope_violation_rate",
        "certificate_efficiency",
    ]
    for column in integer_columns:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(int)
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _coerce_failure_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if column.endswith("_rows") or column.endswith("_events"):
            result[column] = pd.to_numeric(result[column], errors="raise").astype(int)
    return result


def _coerce_bootstrap_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ["alpha", "point_estimate", "lower_95", "upper_95"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in ["valid_repetitions", "repetitions"]:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(int)
    return result


def _assert_frame_equivalent(
    actual: pd.DataFrame, expected: pd.DataFrame, name: str
) -> None:
    if list(actual.columns) != list(expected.columns):
        raise ValueError(f"{name} columns differ from deterministic replay.")
    if actual.shape != expected.shape:
        raise ValueError(f"{name} shape differs from deterministic replay.")
    for column in actual.columns:
        actual_column = actual[column]
        expected_column = expected[column]
        if pd.api.types.is_numeric_dtype(expected_column):
            actual_values = pd.to_numeric(actual_column, errors="coerce").to_numpy(
                dtype=float
            )
            expected_values = expected_column.to_numpy(dtype=float)
            if not np.allclose(
                actual_values,
                expected_values,
                rtol=0.0,
                atol=1e-12,
                equal_nan=True,
            ):
                raise ValueError(f"{name} numeric column differs from replay: {column}")
        else:
            actual_values = actual_column.fillna("").astype(str).to_numpy()
            expected_values = expected_column.fillna("").astype(str).to_numpy()
            if not np.array_equal(actual_values, expected_values):
                raise ValueError(f"{name} text column differs from replay: {column}")


def _source_and_tag_checks(protocol: dict[str, Any], receipt: dict[str, Any]) -> None:
    output = protocol["output_contract"]
    tag = str(output["execution_freeze_tag"])
    expected_commit = receipt.get("execution_git_commit")
    if not isinstance(expected_commit, str) or len(expected_commit) != 40:
        raise ValueError("Receipt lacks a valid execution Git commit.")
    if receipt.get("execution_tag") != tag:
        raise ValueError("Receipt is bound to a different execution tag.")
    if git_text(["cat-file", "-t", f"refs/tags/{tag}"]) != "tag":
        raise ValueError("Execution tag is no longer an annotated local tag.")
    if git_text(["rev-parse", f"{tag}^{{commit}}"]) != expected_commit:
        raise ValueError("Execution tag no longer resolves to the receipt commit.")
    remote_listing = git_text(
        ["ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"]
    )
    if runner.remote_peeled_tag_commit(remote_listing, tag) != expected_commit:
        raise ValueError("Remote execution tag no longer resolves to the receipt commit.")
    allowed = receipt.get("allowed_input_hashes")
    if not isinstance(allowed, dict):
        raise ValueError("Receipt lacks allowlisted source hashes.")
    claim_tag = str(output["execution_claim_tag"])
    if receipt.get("execution_claim_tag") != claim_tag:
        raise ValueError("Receipt is bound to a different execution claim tag.")
    if receipt.get("remote_execution_claim_commit") != expected_commit:
        raise ValueError("Receipt execution claim does not resolve to its execution commit.")
    if git_text(["cat-file", "-t", f"refs/tags/{claim_tag}"]) != "tag":
        raise ValueError("Execution claim is no longer an annotated local tag.")
    if git_text(["rev-parse", f"{claim_tag}^{{commit}}"]) != expected_commit:
        raise ValueError("Execution claim no longer resolves to the receipt commit.")
    claim_object = git_text(["rev-parse", claim_tag])
    if receipt.get("execution_claim_tag_object") != claim_object:
        raise ValueError("Receipt execution claim object differs from the local tag.")
    claim_remote_listing = git_text(
        [
            "ls-remote",
            "origin",
            f"refs/tags/{claim_tag}",
            f"refs/tags/{claim_tag}^{{}}",
        ]
    )
    if runner.remote_peeled_tag_commit(claim_remote_listing, claim_tag) != expected_commit:
        raise ValueError("Remote execution claim no longer resolves to the receipt commit.")
    if runner.remote_tag_object_id(claim_remote_listing, claim_tag) != claim_object:
        raise ValueError("Remote execution claim object differs from the local tag.")
    if receipt.get("execution_claim_input_bundle_sha256") != runner.canonical_json_sha256(
        allowed
    ):
        raise ValueError("Receipt claim does not bind its allowlisted input hashes.")
    runtime = runner.validate_runtime_environment(protocol)
    if receipt.get("execution_claim_runtime_sha256") != runner.canonical_json_sha256(
        runtime
    ):
        raise ValueError("Receipt claim does not bind its runtime environment.")
    claim_message = git_text(
        ["for-each-ref", "--format=%(contents)", f"refs/tags/{claim_tag}"]
    )
    expected_claim_lines = {
        "MetaShift v0.5 one-time execution claim",
        f"execution_commit={expected_commit}",
        f"execution_freeze_tag={tag}",
        f"protocol_sha256={receipt.get('protocol_sha256')}",
        f"execution_manifest_sha256={receipt.get('execution_manifest_sha256')}",
        f"allowlisted_input_hashes_sha256={receipt.get('execution_claim_input_bundle_sha256')}",
        f"runtime_environment_sha256={receipt.get('execution_claim_runtime_sha256')}",
    }
    if not expected_claim_lines.issubset(set(claim_message.splitlines())):
        raise ValueError("Execution-claim annotation does not bind the receipt provenance.")
    if receipt.get("protocol_sha256") != runner.source_sha256(PROTOCOL_PATH):
        raise ValueError("Current protocol hash differs from the receipt.")
    if receipt.get("runtime_environment") != runtime:
        raise ValueError("Current runtime differs from the receipt runtime contract.")
    expected_allowlist = protocol["data_access"]["execution_input_allowlist"]
    if set(allowed) != set(expected_allowlist):
        raise ValueError("Receipt source set differs from the protocol allowlist.")
    for relative_path, expected_hash in allowed.items():
        path = ROOT / relative_path
        if not path.is_file() or runner.source_sha256(path) != expected_hash:
            raise ValueError(f"Working source differs from receipt: {relative_path}")
        tagged_hash = sha256_bytes(
            subprocess.check_output(
                ["git", "show", f"{tag}:{relative_path}"], cwd=ROOT
            )
        )
        if tagged_hash != expected_hash:
            raise ValueError(f"Tagged source differs from receipt: {relative_path}")


def _validate_policy_json(
    policy_path: Path, calibration: pd.DataFrame, protocol: dict[str, Any]
) -> dict[str, Any]:
    stored = json.loads(policy_path.read_text(encoding="utf-8"))
    expected = runner.calibration_policies(calibration, protocol)
    if stored.get("protocol_id") != expected["protocol_id"]:
        raise ValueError("Calibration policy has a different protocol identity.")
    if stored.get("selection_split") != "calibration":
        raise ValueError("Calibration policy does not declare calibration-only selection.")
    if not np.isclose(
        float(stored["comparative_scope_threshold"]),
        float(expected["comparative_scope_threshold"]),
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("Stored comparative threshold differs from calibration replay.")
    for token, expected_cutoff in expected["confidence_cutoffs"].items():
        observed = stored.get("confidence_cutoffs", {}).get(token)
        if not isinstance(observed, dict):
            raise ValueError(f"Stored confidence cutoff is absent: {token}")
        for key in ("alpha", "calibration_coverage"):
            if not np.isclose(
                float(observed[key]), float(expected_cutoff[key]), rtol=0.0, atol=1e-12
            ):
                raise ValueError(f"Stored confidence cutoff differs for {token}:{key}.")
        for key in ("cutoff", "calibration_conditional_error"):
            if observed[key] is None or expected_cutoff[key] is None:
                if observed[key] != expected_cutoff[key]:
                    raise ValueError(f"Stored confidence cutoff null differs for {token}:{key}.")
            elif not np.isclose(
                float(observed[key]), float(expected_cutoff[key]), rtol=0.0, atol=1e-12
            ):
                raise ValueError(f"Stored confidence cutoff differs for {token}:{key}.")
        if observed.get("status") != expected_cutoff["status"]:
            raise ValueError(f"Stored confidence cutoff status differs for {token}.")
    return stored


def _read_payloads(protocol: dict[str, Any]) -> dict[str, Any]:
    paths = _paths(protocol)
    schemas = protocol["output_contract"]["schemas"]
    pair = _coerce_pair_frame(
        _read_csv_strict(
            paths["v05_scope_pair_results.csv"], schemas["v05_scope_pair_results.csv"]
        )
    )
    metrics = _coerce_metrics_frame(
        _read_csv_strict(paths["v05_policy_metrics.csv"], schemas["v05_policy_metrics.csv"])
    )
    frontier = _coerce_frontier_frame(
        _read_csv_strict(
            paths["v05_answerability_frontier.csv"],
            schemas["v05_answerability_frontier.csv"],
        )
    )
    certificate = _coerce_certificate_frame(
        _read_csv_strict(
            paths["v05_certificate_validity.csv"],
            schemas["v05_certificate_validity.csv"],
        )
    )
    failure = _coerce_failure_frame(
        _read_csv_strict(
            paths["v05_failure_mode_map.csv"], schemas["v05_failure_mode_map.csv"]
        )
    )
    bootstrap = _coerce_bootstrap_frame(
        _read_csv_strict(
            paths["v05_component_bootstrap.csv"],
            schemas["v05_component_bootstrap.csv"],
        )
    )
    policy = json.loads(paths["v05_calibration_policy.json"].read_text(encoding="utf-8"))
    receipt = json.loads(paths["v05_execution_receipt.json"].read_text(encoding="utf-8"))
    return {
        "pairs": pair,
        "metrics": metrics,
        "frontier": frontier,
        "certificate": certificate,
        "failure": failure,
        "bootstrap": bootstrap,
        "policy": policy,
        "receipt": receipt,
    }


def _validate_receipt_hashes(protocol: dict[str, Any], receipt: dict[str, Any]) -> None:
    paths = _paths(protocol)
    output_hashes = receipt.get("output_hashes")
    expected_names = set(paths).difference({"v05_execution_receipt.json"})
    if not isinstance(output_hashes, dict) or set(output_hashes) != expected_names:
        raise ValueError("Receipt output hashes do not cover exactly the non-self payloads.")
    for name in expected_names:
        recorded = output_hashes[name]
        if not isinstance(recorded, dict):
            raise ValueError(f"Malformed receipt hash entry: {name}")
        if recorded.get("sha256") != sha256(paths[name]):
            raise ValueError(f"Payload hash differs from receipt: {name}")
        if recorded.get("bytes") != paths[name].stat().st_size:
            raise ValueError(f"Payload byte count differs from receipt: {name}")


def _validate_attempt(protocol: dict[str, Any], receipt_path: Path) -> None:
    attempt = json.loads(_attempt_path(protocol).read_text(encoding="utf-8"))
    if attempt.get("state") not in {"completed", "completed_certificate_contract_violation"}:
        raise ValueError("The durable v0.5 attempt did not reach a completed state.")
    if attempt.get("receipt_sha256") != sha256(receipt_path):
        raise ValueError("Attempt record does not bind the final receipt bytes.")


def _validate_pair_contract(frame: pd.DataFrame, protocol: dict[str, Any]) -> None:
    accounting = runner._accounting_report(frame, protocol)
    runner._assert_accounting(accounting)
    if frame["protocol_id"].nunique() != 1 or frame["protocol_id"].iloc[0] != protocol[
        "protocol_id"
    ]:
        raise ValueError("Pair table protocol identity is invalid.")
    if not np.allclose(
        frame["realized_gap"].to_numpy(dtype=float),
        frame["q_effective_mean"].to_numpy(dtype=float)
        * frame["signal_h"].to_numpy(dtype=float),
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError("Realized gap does not match q-effective mean times H.")
    q0 = frame.loc[frame["nominal_q"] == 0.0]
    violating = (
        ~frame["local_envelope_satisfied"].to_numpy(dtype=bool)
        | ~frame["shared_envelope_satisfied"].to_numpy(dtype=bool)
    )
    if not (
        q0["certificate_answered"].eq(False).all()
        and q0.loc[
            q0["local_envelope_satisfied"] & q0["shared_envelope_satisfied"],
            "certificate_abstention_reason",
        ]
        .eq("q0_observational_identity")
        .all()
    ):
        raise ValueError("q=0 certificate negative-control accounting is invalid.")
    if not (
        frame.loc[frame["certificate_answered"], "structural_margin"] > 0.0
    ).all() or bool(frame.loc[violating, "certificate_answered"].any()):
        raise ValueError("Certificate answered outside the positive-margin region.")
    valid_abstentions = frame.loc[
        ~frame["certificate_answered"], "structural_margin"
    ].to_numpy(dtype=float) <= 0.0
    valid_abstentions |= violating[~frame["certificate_answered"].to_numpy(dtype=bool)]
    if not valid_abstentions.all():
        raise ValueError("Certificate abstained despite a positive structural margin.")
    if violating.any():
        raise ValueError(
            "A certificate envelope violation was preserved but invalidates the result."
        )


def _replay_payloads(protocol: dict[str, Any], execution_tag: str) -> dict[str, Any]:
    calibration = runner.generate_pair_results(protocol, "calibration", execution_tag)
    policies = runner.calibration_policies(calibration, protocol)
    calibration = runner.apply_policies(calibration, policies, protocol)
    evaluation = runner.generate_pair_results(protocol, "evaluation", execution_tag)
    evaluation = runner.apply_policies(evaluation, policies, protocol)
    pairs = runner._expected_schema_frame(
        pd.concat([calibration, evaluation], ignore_index=True), protocol
    )
    metrics = pd.concat(
        [
            runner.policy_metrics(calibration, protocol),
            runner.policy_metrics(evaluation, protocol),
        ],
        ignore_index=True,
    )
    evaluation_metrics = metrics.loc[metrics["split"] == "evaluation"].copy()
    return {
        "pairs": pairs,
        "policy": policies,
        "metrics": metrics,
        "frontier": runner.answerability_frontier(evaluation_metrics, protocol),
        "certificate": pd.concat(
            [
                runner.certificate_validity(calibration),
                runner.certificate_validity(evaluation),
            ],
            ignore_index=True,
        ),
        "failure": runner.failure_mode_map(pairs),
        "bootstrap": runner.component_bootstrap(
            runner.component_policy_metrics(evaluation, protocol), protocol
        ),
    }


def build_report(*, replay: bool = True) -> dict[str, Any]:
    """Run all non-mutating result checks and preserve each failure reason."""

    protocol = runner.read_protocol()
    paths = _paths(protocol)
    checks: list[dict[str, object]] = []
    payloads: dict[str, Any] | None = None

    def run_check(name: str, detail: str, operation: Callable[[], None]) -> None:
        try:
            operation()
        except Exception as error:
            checks.append(check(name, False, f"{detail} Failure: {error}"))
        else:
            checks.append(check(name, True, detail))

    pre_report = pre_outcome.build_report(require_no_outputs=False)
    checks.append(
        check(
            "pre_outcome_contract",
            bool(pre_report["all_checks_passed"]),
            "The tracked v0.5 pre-outcome contract remains complete after execution.",
        )
    )

    def load_payloads() -> None:
        nonlocal payloads
        payloads = _read_payloads(protocol)

    run_check(
        "declared_payload_schemas",
        "Every declared v0.5 output exists and matches its frozen schema.",
        load_payloads,
    )
    if payloads is not None:
        run_check(
            "receipt_hashes_and_bytes",
            "Receipt hashes and byte counts bind every preceding output payload.",
            lambda: _validate_receipt_hashes(protocol, payloads["receipt"]),
        )
        run_check(
            "attempt_receipt_chain",
            "The durable one-time attempt binds the final receipt hash.",
            lambda: _validate_attempt(protocol, paths["v05_execution_receipt.json"]),
        )
        run_check(
            "tagged_source_provenance",
            "All execution inputs match both receipt hashes and the annotated remote tag.",
            lambda: _source_and_tag_checks(protocol, payloads["receipt"]),
        )
        run_check(
            "complete_grid_identity_and_certificate_contract",
            "Pair accounting, target identity, q=0 identity, and certificate margins are valid.",
            lambda: _validate_pair_contract(payloads["pairs"], protocol),
        )
        calibration = payloads["pairs"].loc[
            payloads["pairs"]["split"] == "calibration"
        ].copy()
        run_check(
            "calibration_only_policy_replay",
            "All stored thresholds and confidence cutoffs reproduce from calibration rows only.",
            lambda: _validate_policy_json(
                paths["v05_calibration_policy.json"], calibration, protocol
            ),
        )
        if replay:
            replayed: dict[str, Any] | None = None

            def replay_and_compare() -> None:
                nonlocal replayed
                replayed = _replay_payloads(
                    protocol, str(payloads["receipt"]["execution_tag"])
                )
                _assert_frame_equivalent(
                    payloads["pairs"], replayed["pairs"], "Pair results"
                )
                _assert_frame_equivalent(
                    payloads["metrics"], replayed["metrics"], "Policy metrics"
                )
                _assert_frame_equivalent(
                    payloads["frontier"], replayed["frontier"], "Answerability frontier"
                )
                _assert_frame_equivalent(
                    payloads["certificate"],
                    replayed["certificate"],
                    "Certificate validity",
                )
                _assert_frame_equivalent(
                    payloads["failure"], replayed["failure"], "Failure-mode map"
                )
                _assert_frame_equivalent(
                    payloads["bootstrap"], replayed["bootstrap"], "Component bootstrap"
                )

            run_check(
                "deterministic_tagged_source_replay",
                "The complete in-memory synthetic generation and every derived table reproduce exactly.",
                replay_and_compare,
            )
        else:
            checks.append(
                check(
                    "deterministic_tagged_source_replay",
                    False,
                    "Replay was explicitly skipped; this is not a full frozen verification.",
                )
            )
    return {
        "protocol_id": protocol["protocol_id"],
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Read-only v0.5 output, provenance, accounting, and deterministic-replay verification.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    report = build_report(replay=not args.skip_replay)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
