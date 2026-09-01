"""Execute the one-time, theorem-aligned v0.4 synthetic benchmark.

The entrypoint intentionally has no input-path arguments.  It generates all
panels in memory from the tracked protocol and refuses any attempt that is not
at the separately tagged execution-freeze commit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metashift.counterfactual import anchor_residual_windows, estimate_metadata_anchor
from metashift.identifiability import (
    additive_increment_lipschitz_constant,
    build_analysis_scale_scope_pair,
    clipped_log,
    paired_schedule_seed,
    proportional_increment_lipschitz_constant,
)
from metashift.metrics import classification_metrics, metrics_as_dict, select_macro_f1_threshold
from metashift.synthetic import PerturbationKind, inject_perturbation


PROTOCOL_RELATIVE_PATH = "configs/v04_identifiability_protocol.json"
EXECUTION_MANIFEST_RELATIVE_PATH = "configs/v04_identifiability_execution_manifest.json"
PROTOCOL_PATH = ROOT / PROTOCOL_RELATIVE_PATH
EXECUTION_MANIFEST_PATH = ROOT / EXECUTION_MANIFEST_RELATIVE_PATH


@dataclass(frozen=True)
class SyntheticComponent:
    """One fully synthetic base panel with a fixed target and four donors."""

    component_id: str
    split: str
    target: pd.Series
    donors: pd.DataFrame
    anchor_date: pd.Timestamp
    weights: pd.Series


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the one-time v0.4 identifiability benchmark."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute only after v0.4.0-execution-freeze is created and pushed.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_sha256(path: Path) -> str:
    """Hash tracked source as LF-normalized UTF-8 text, matching its Git blob."""

    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Write durable JSON without exposing a partially written final path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode("utf-8")
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(encoded)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def write_csv_atomic(path: Path, frame: pd.DataFrame) -> None:
    """Write a CSV atomically after all values have been constructed in memory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent,
        prefix=f".{path.name}.", delete=False
    ) as temporary:
        frame.to_csv(temporary, index=False)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def project_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Protocol path must remain within the repository: {relative_path}")
    resolved = (ROOT / path).resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise ValueError(f"Protocol path escapes the repository: {relative_path}")
    return resolved


def read_protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def read_execution_manifest() -> dict[str, Any]:
    return json.loads(EXECUTION_MANIFEST_PATH.read_text(encoding="utf-8"))


def git_bytes(arguments: list[str]) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def git_text(arguments: list[str]) -> str:
    return git_bytes(arguments).decode("utf-8").strip()


def remote_peeled_tag_commit(remote_listing: str, tag: str) -> str:
    """Extract the peeled commit of one annotated remote tag or fail closed."""

    expected_reference = f"refs/tags/{tag}^{{}}"
    matches = [
        line.split("\t", maxsplit=1)[0]
        for line in remote_listing.splitlines()
        if "\t" in line and line.split("\t", maxsplit=1)[1] == expected_reference
    ]
    if len(matches) != 1 or len(matches[0]) != 40:
        raise RuntimeError(
            "origin must expose one peeled annotated execution-freeze tag reference."
        )
    return matches[0]


def validate_annotated_execution_tag(
    tag: str,
    head_commit: str,
    local_tag_object_type: str,
    local_tag_commit: str,
    remote_listing: str,
) -> str:
    """Validate local and remote annotated-tag bindings without side effects."""

    if local_tag_object_type != "tag":
        raise RuntimeError("execution-freeze tag must be a local annotated Git tag.")
    if local_tag_commit != head_commit:
        raise RuntimeError(
            "HEAD must equal the resolved execution-freeze tag before one-time execution."
        )
    remote_commit = remote_peeled_tag_commit(remote_listing, tag)
    if remote_commit != head_commit:
        raise RuntimeError(
            "origin execution-freeze tag must resolve to the same commit as HEAD."
        )
    return remote_commit


def ensure_allowlisted_inputs(protocol: dict[str, Any]) -> dict[str, str]:
    """Return hashes of exactly the tracked files declared as execution inputs."""

    data_access = protocol.get("data_access", {})
    allowlist = data_access.get("execution_input_allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        raise ValueError("Protocol has no execution input allowlist.")
    hashes: dict[str, str] = {}
    for relative_path in allowlist:
        if not isinstance(relative_path, str):
            raise ValueError("Execution input allowlist contains a non-string path.")
        path = project_path(relative_path)
        if not path.is_file():
            raise FileNotFoundError(f"Allowlisted execution input is absent: {relative_path}")
        subprocess.check_call(
            ["git", "ls-files", "--error-unmatch", "--", relative_path],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        hashes[relative_path] = source_sha256(path)
    return hashes


def ensure_execution_preconditions(protocol: dict[str, Any]) -> dict[str, Any]:
    """Reject execution unless current source exactly matches its execution tag."""

    output_contract = protocol.get("output_contract", {})
    execution_tag = output_contract.get("execution_freeze_tag")
    if not isinstance(execution_tag, str) or not execution_tag:
        raise ValueError("Protocol lacks an execution-freeze tag.")
    if git_text(["status", "--porcelain"]):
        raise RuntimeError("Refusing execution from a dirty Git worktree.")
    head_commit = git_text(["rev-parse", "HEAD"])
    try:
        local_tag_object_type = git_text(
            ["cat-file", "-t", f"refs/tags/{execution_tag}"]
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "execution-freeze tag must exist locally as an annotated Git tag."
        ) from error
    tag_commit = git_text(["rev-parse", f"{execution_tag}^{{commit}}"])
    remote_listing = git_text(
        [
            "ls-remote",
            "origin",
            f"refs/tags/{execution_tag}",
            f"refs/tags/{execution_tag}^{{}}",
        ]
    )
    remote_commit = validate_annotated_execution_tag(
        execution_tag,
        head_commit,
        local_tag_object_type,
        tag_commit,
        remote_listing,
    )

    allowlisted_hashes = ensure_allowlisted_inputs(protocol)
    manifest_relative_path = output_contract.get("execution_manifest")
    if manifest_relative_path != EXECUTION_MANIFEST_RELATIVE_PATH:
        raise ValueError("Protocol execution manifest path does not match the runner contract.")
    manifest = read_execution_manifest()
    protocol_hash = source_sha256(PROTOCOL_PATH)
    if manifest.get("protocol_sha256") != protocol_hash:
        raise RuntimeError("Execution manifest does not bind the current protocol SHA-256.")
    if manifest.get("execution_freeze_tag") != execution_tag:
        raise RuntimeError("Execution manifest is bound to a different execution tag.")

    bound_hashes = manifest.get("bound_input_sha256")
    if not isinstance(bound_hashes, dict):
        raise ValueError("Execution manifest lacks its bound input hash map.")
    for relative_path, expected_hash in bound_hashes.items():
        actual_hash = allowlisted_hashes.get(relative_path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Execution input does not match the manifest: {relative_path}"
            )
    expected_bound_paths = set(allowlisted_hashes).difference(
        {EXECUTION_MANIFEST_RELATIVE_PATH}
    )
    if set(bound_hashes) != expected_bound_paths:
        raise RuntimeError("Execution manifest must bind every non-self allowlisted input.")

    for relative_path, actual_hash in allowlisted_hashes.items():
        tagged_hash = sha256_bytes(
            git_bytes(["show", f"{execution_tag}:{relative_path}"])
        )
        if tagged_hash != actual_hash:
            raise RuntimeError(
                f"Current allowlisted input differs from execution tag: {relative_path}"
            )
    if sha256_bytes(git_bytes(["show", f"{execution_tag}:{PROTOCOL_RELATIVE_PATH}"])) != protocol_hash:
        raise RuntimeError("Protocol at HEAD differs from the execution-freeze tag.")

    return {
        "execution_git_commit": head_commit,
        "execution_tag": execution_tag,
        "remote_execution_tag_commit": remote_commit,
        "protocol_sha256": protocol_hash,
        "execution_manifest_sha256": source_sha256(EXECUTION_MANIFEST_PATH),
        "allowed_input_hashes": allowlisted_hashes,
    }


def component_seed(protocol: dict[str, Any], split: str, index: int) -> int:
    """Derive the declared deterministic component seed."""

    panel = protocol["synthetic_panel"]
    if split not in panel["split_seed_offsets"]:
        raise ValueError(f"Unknown synthetic split: {split}")
    if index < 0:
        raise ValueError("Component index cannot be negative.")
    return int(panel["base_seed"]) + int(panel["split_seed_offsets"][split]) + index


def availability_seed(protocol: dict[str, Any], split: str, index: int) -> int:
    """Derive the separate declared donor-availability seed."""

    panel = protocol["synthetic_panel"]
    if split not in panel["split_seed_offsets"]:
        raise ValueError(f"Unknown synthetic split: {split}")
    if index < 0:
        raise ValueError("Component index cannot be negative.")
    return (
        int(panel["base_seed"])
        + 2_000_000
        + int(panel["split_seed_offsets"][split])
        + index
    )


def generate_component(
    protocol: dict[str, Any], split: str, index: int
) -> SyntheticComponent:
    """Generate one panel exactly according to the frozen protocol equations."""

    panel = protocol["synthetic_panel"]
    generator = panel["analysis_scale_generator"]
    days = int(panel["days"])
    donor_count = int(panel["donor_count"])
    anchor_index = int(panel["anchor_day_index"])
    if not 0 < anchor_index < days:
        raise ValueError("Anchor day must lie strictly inside the synthetic panel.")
    offsets = np.asarray(generator["donor_offsets"], dtype=float)
    if len(offsets) != donor_count:
        raise ValueError("The donor offset count must equal the donor count.")

    rng = np.random.default_rng(component_seed(protocol, split, index))
    rho = float(generator["ar1_coefficient"])
    common_sd = float(generator["common_innovation_sd"])
    common = np.empty(days, dtype=float)
    common[0] = rng.normal(0.0, common_sd / np.sqrt(1.0 - rho**2))
    common_innovations = rng.normal(0.0, common_sd, days - 1)
    for day_index, innovation in enumerate(common_innovations, start=1):
        common[day_index] = rho * common[day_index - 1] + innovation
    target_innovations = rng.normal(
        0.0, float(generator["target_innovation_sd"]), days
    )
    donor_innovations = rng.normal(
        0.0, float(generator["donor_innovation_sd"]), (days, donor_count)
    )
    minimum = float(generator["minimum_analysis_scale"])
    mean = float(generator["mean"])
    target_scale = np.maximum(minimum, mean + common + target_innovations)
    donor_scale = np.maximum(
        minimum, mean + common[:, np.newaxis] + offsets + donor_innovations
    )

    date_index = pd.date_range(
        str(panel["start_date"]), periods=days, freq="D"
    )
    target = pd.Series(np.expm1(target_scale), index=date_index, name="target")
    donors = pd.DataFrame(
        np.expm1(donor_scale),
        index=date_index,
        columns=[f"donor_{donor_index + 1}" for donor_index in range(donor_count)],
    )
    availability = panel["donor_availability"]
    availability_rng = np.random.default_rng(availability_seed(protocol, split, index))
    probability = float(availability["single_missing_probability"])
    for day_index in range(days):
        if availability_rng.random() < probability:
            missing_donor = int(availability_rng.integers(0, donor_count))
            donors.iloc[day_index, missing_donor] = np.nan

    component_id = str(panel["component_id_template"]).format(
        split=split, index=index
    )
    return SyntheticComponent(
        component_id=component_id,
        split=split,
        target=target,
        donors=donors,
        anchor_date=date_index[anchor_index],
        weights=pd.Series(1.0 / donor_count, index=donors.columns),
    )


def schedule_for_pair(
    protocol: dict[str, Any],
    pair_id: str,
    schedule_specification: dict[str, Any],
    date_index: pd.DatetimeIndex,
    anchor_date: pd.Timestamp,
) -> tuple[pd.Series, int]:
    """Create a declared analysis-scale schedule from its arm-invariant pair ID."""

    seed = paired_schedule_seed(
        pair_id, base_seed=int(protocol["synthetic_panel"]["base_seed"])
    )
    schedule = pd.Series(0.0, index=date_index, name="analysis_scale_increment")
    post_mask = date_index >= anchor_date
    parameters = schedule_specification.get("parameters", {})
    name = schedule_specification.get("name")
    if name == "constant_step":
        schedule.loc[post_mask] = float(parameters["post_increment"])
    elif name == "bounded_stochastic_step":
        rng = np.random.default_rng(seed)
        schedule.loc[post_mask] = float(parameters["post_center"]) + rng.uniform(
            -float(parameters["uniform_half_width"]),
            float(parameters["uniform_half_width"]),
            int(post_mask.sum()),
        )
    else:
        raise ValueError(f"Unknown exact-core schedule family: {name}")
    return schedule, seed


def target_only_score(
    target: pd.Series, anchor_date: pd.Timestamp, comparison_days: int
) -> float:
    """Return the predeclared absolute median change on the analysis scale."""

    scale = clipped_log(target)
    assert isinstance(scale, pd.Series)
    anchor_position = target.index.get_loc(anchor_date)
    if not isinstance(anchor_position, int):
        raise ValueError("Synthetic target anchor must have one unique position.")
    pre = scale.iloc[anchor_position - comparison_days : anchor_position]
    post = scale.iloc[anchor_position : anchor_position + comparison_days]
    if len(pre) != comparison_days or len(post) != comparison_days:
        raise ValueError("Synthetic target lacks a complete score window.")
    if not np.isfinite(pre.to_numpy()).all() or not np.isfinite(post.to_numpy()).all():
        raise ValueError("Target-only score has a nonfinite observation.")
    return float(abs(np.median(post) - np.median(pre)))


def comparative_estimate(
    component: SyntheticComponent,
    target: pd.Series,
    donors: pd.DataFrame,
    protocol: dict[str, Any],
):
    """Apply the frozen comparative estimator without fitting any weights."""

    estimator = protocol["estimator"]
    estimate = estimate_metadata_anchor(
        target,
        donors,
        component.weights,
        component.anchor_date,
        calibration_days=int(estimator["calibration_days"]),
        calibration_buffer_days=int(estimator["calibration_buffer_days"]),
        comparison_days=int(estimator["comparison_days"]),
        min_window_observations=int(estimator["minimum_window_observations"]),
        min_available_donors=int(estimator["minimum_available_donors"]),
    )
    if not np.isfinite(estimate.log_effect):
        raise ValueError("Comparative scope score is nonfinite.")
    return estimate


def core_rows_for_component(
    protocol: dict[str, Any], component: SyntheticComponent, execution_tag: str
) -> list[dict[str, Any]]:
    """Generate N/L/R records for both frozen schedule families in one component."""

    estimator = protocol["estimator"]
    comparison_days = int(estimator["comparison_days"])
    tolerance = float(estimator["numerical_invariance_tolerance"])
    rows: list[dict[str, Any]] = []
    pair_template = protocol["matched_pairs"]["pair_id_template"]

    for schedule_specification in protocol["schedule_families"]:
        schedule_family = str(schedule_specification["name"])
        pair_id = str(pair_template).format(
            split=component.split,
            component_id=component.component_id,
            schedule_family=schedule_family,
        )
        schedule, schedule_seed = schedule_for_pair(
            protocol,
            pair_id,
            schedule_specification,
            component.target.index,
            component.anchor_date,
        )
        pair = build_analysis_scale_scope_pair(
            component.target,
            component.donors,
            component.anchor_date,
            schedule,
            pair_id,
            random_seed=schedule_seed,
        )
        if not np.array_equal(
            pair.local_target.to_numpy(), pair.regional_target.to_numpy()
        ):
            raise RuntimeError("Matched local/regional targets are not exactly identical.")

        base_estimate = comparative_estimate(
            component, component.target, component.donors, protocol
        )
        local_estimate = comparative_estimate(
            component, pair.local_target, pair.local_donors, protocol
        )
        regional_estimate = comparative_estimate(
            component, pair.regional_target, pair.regional_donors, protocol
        )
        if abs(regional_estimate.log_effect - base_estimate.log_effect) > tolerance:
            raise RuntimeError(
                "Analysis-scale regional residual exceeds the frozen numerical tolerance."
            )

        variants = (
            ("no_change", component.target, component.donors, base_estimate, None),
            ("local", pair.local_target, pair.local_donors, local_estimate, True),
            (
                "regional",
                pair.regional_target,
                pair.regional_donors,
                regional_estimate,
                True,
            ),
        )
        for state, target, donors, estimate, identity in variants:
            score = target_only_score(target, component.anchor_date, comparison_days)
            comparative_score = float(abs(estimate.log_effect))
            if not np.isfinite(score) or not np.isfinite(comparative_score):
                raise ValueError("Core event contains a nonfinite score.")
            rows.append(
                {
                    "protocol_id": protocol["protocol_id"],
                    "execution_tag": execution_tag,
                    "component_id": component.component_id,
                    "split": component.split,
                    "case_id": f"{pair_id}:{state}",
                    "pair_id": pair_id,
                    "state": state,
                    "schedule_family": schedule_family,
                    "schedule_seed": schedule_seed,
                    "schedule_sha256": pair.schedule_sha256,
                    "target_only_score": score,
                    "comparative_scope_score": comparative_score,
                    "comparative_log_effect": float(estimate.log_effect),
                    "local_regional_target_identity": identity,
                }
            )
    return rows


def generate_core_rows(
    protocol: dict[str, Any], execution_tag: str
) -> pd.DataFrame:
    """Generate all predeclared primary-core events without writing results."""

    rows: list[dict[str, Any]] = []
    for split, count in protocol["synthetic_panel"]["component_counts"].items():
        for index in range(int(count)):
            component = generate_component(protocol, str(split), index)
            rows.extend(core_rows_for_component(protocol, component, execution_tag))
    frame = pd.DataFrame(rows)
    expected = protocol["expected_accounting"]["core_events"]
    for split, count in expected.items():
        if split == "total":
            continue
        if int((frame["split"] == split).sum()) != int(count):
            raise RuntimeError(f"Core {split} event count does not match the protocol.")
    if len(frame) != int(expected["total"]):
        raise RuntimeError("Core total event count does not match the protocol.")
    if not set(frame["state"]) == {"no_change", "local", "regional"}:
        raise RuntimeError("Core event accounting lacks an N/L/R state.")
    return frame


def calibration_thresholds(
    core: pd.DataFrame, protocol: dict[str, Any]
) -> dict[str, Any]:
    """Select all thresholds and confidence cutoffs only from calibration rows."""

    calibration = core.loc[core["split"] == "calibration"].copy()
    scope = calibration.loc[calibration["state"].isin(["local", "regional"])].copy()
    if len(calibration) != int(protocol["expected_accounting"]["core_events"]["calibration"]):
        raise RuntimeError("Calibration core event count does not match the protocol.")
    if len(scope) != int(protocol["expected_accounting"]["core_scope_events"]["calibration"]):
        raise RuntimeError("Calibration scope event count does not match the protocol.")
    score_columns = ("target_only_score", "comparative_scope_score")
    if not np.isfinite(calibration.loc[:, score_columns].to_numpy(dtype=float)).all():
        raise ValueError("Calibration contains a nonfinite score.")
    detection_labels = (calibration["state"] != "no_change").astype(int).to_numpy()
    detection_threshold = select_macro_f1_threshold(
        detection_labels, calibration["target_only_score"].to_numpy(dtype=float)
    )
    scope_labels = (scope["state"] == "local").astype(int).to_numpy()
    scope_threshold = select_macro_f1_threshold(
        scope_labels, scope["comparative_scope_score"].to_numpy(dtype=float)
    )
    confidence = np.abs(
        scope["comparative_scope_score"].to_numpy(dtype=float) - scope_threshold
    )
    if not np.isfinite(confidence).all():
        raise ValueError("Calibration scope confidence is nonfinite.")
    quantiles = protocol["evaluation"]["selective_policy"]["operating_quantiles"]
    cutoffs = {
        f"{float(quantile):.2f}": float(
            np.quantile(confidence, float(quantile), method="linear")
        )
        for quantile in quantiles
    }
    if not np.isfinite([detection_threshold, scope_threshold, *cutoffs.values()]).all():
        raise ValueError("Threshold selection produced a nonfinite value.")
    return {
        "detection_threshold": float(detection_threshold),
        "scope_threshold": float(scope_threshold),
        "selective_confidence_cutoffs": cutoffs,
        "calibration_case_counts": {
            "all_n_l_r": int(len(calibration)),
            "scope_l_r": int(len(scope)),
            "no_change": int((calibration["state"] == "no_change").sum()),
            "local": int((calibration["state"] == "local").sum()),
            "regional": int((calibration["state"] == "regional").sum()),
        },
    }


def apply_predictions(
    core: pd.DataFrame, thresholds: dict[str, Any]
) -> pd.DataFrame:
    """Attach frozen-threshold predictions and selective abstention decisions."""

    frame = core.copy()
    detection_threshold = float(thresholds["detection_threshold"])
    scope_threshold = float(thresholds["scope_threshold"])
    frame["detection_prediction"] = np.where(
        frame["target_only_score"] >= detection_threshold, "change", "no_change"
    )
    scope_mask = frame["state"].isin(["local", "regional"])
    frame["forced_scope_prediction"] = ""
    frame.loc[scope_mask, "forced_scope_prediction"] = np.where(
        frame.loc[scope_mask, "comparative_scope_score"] >= scope_threshold,
        "local",
        "regional",
    )
    frame["target_only_scope_prediction"] = ""
    frame.loc[scope_mask, "target_only_scope_prediction"] = "local"
    frame["scope_confidence"] = np.nan
    frame.loc[scope_mask, "scope_confidence"] = np.abs(
        frame.loc[scope_mask, "comparative_scope_score"] - scope_threshold
    )

    for quantile, cutoff in thresholds["selective_confidence_cutoffs"].items():
        reason_column = f"abstention_reason_q{quantile}"
        answered_column = f"answered_q{quantile}"
        frame[reason_column] = "not_applicable"
        frame[answered_column] = False
        confident = frame.loc[scope_mask, "scope_confidence"] >= float(cutoff)
        answered = confident
        frame.loc[scope_mask, answered_column] = answered.to_numpy()
        frame.loc[
            scope_mask
            & (frame["scope_confidence"] < float(cutoff)),
            reason_column,
        ] = "below_scope_confidence_cutoff"
        frame.loc[scope_mask & frame[answered_column], reason_column] = "answered"
    return frame


def scalar_evaluation_metrics(
    frame: pd.DataFrame, thresholds: dict[str, Any]
) -> dict[str, float | None]:
    """Return finite scalar metrics for one evaluation or bootstrap sample."""

    detection_labels = (frame["state"] != "no_change").astype(int).to_numpy()
    detection = classification_metrics(
        detection_labels,
        frame["target_only_score"].to_numpy(dtype=float),
        float(thresholds["detection_threshold"]),
    )
    scope = frame.loc[frame["state"].isin(["local", "regional"])].copy()
    labels = (scope["state"] == "local").astype(int).to_numpy()
    forced_predictions = (scope["forced_scope_prediction"] == "local").astype(int)
    target_only_predictions = (
        scope["target_only_scope_prediction"] == "local"
    ).astype(int)
    scalars = {
        "detection_macro_f1": float(detection.macro_f1),
        "forced_scope_error": float(np.mean(forced_predictions != labels)),
        "target_only_scope_error": float(np.mean(target_only_predictions != labels)),
        "target_identity_rate": float(
            scope["local_regional_target_identity"].astype(bool).mean()
        ),
    }
    for quantile in thresholds["selective_confidence_cutoffs"]:
        answered = scope[f"answered_q{quantile}"].to_numpy(dtype=bool)
        if answered.any():
            predictions = (
                scope.loc[answered, "forced_scope_prediction"] == "local"
            ).astype(int)
            scalars[f"selective_scope_error_q{quantile}"] = float(
                np.mean(predictions != labels[answered])
            )
        else:
            scalars[f"selective_scope_error_q{quantile}"] = None
        scalars[f"selective_scope_coverage_q{quantile}"] = float(answered.mean())
    finite_values = [value for value in scalars.values() if value is not None]
    if not np.isfinite(finite_values).all():
        raise ValueError("Evaluation contains a nonfinite scalar metric.")
    return scalars


def summarize_evaluation(
    core: pd.DataFrame, thresholds: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, Any]:
    """Build the predeclared complete N/L/R and selective evaluation summary."""

    evaluation = core.loc[core["split"] == "evaluation"].copy()
    expected = protocol["expected_accounting"]
    if len(evaluation) != int(expected["core_events"]["evaluation"]):
        raise RuntimeError("Evaluation core event count does not match the protocol.")
    scope = evaluation.loc[evaluation["state"].isin(["local", "regional"])].copy()
    if len(scope) != int(expected["core_scope_events"]["evaluation"]):
        raise RuntimeError("Evaluation scope event count does not match the protocol.")
    scalars = scalar_evaluation_metrics(evaluation, thresholds)
    detection = classification_metrics(
        (evaluation["state"] != "no_change").astype(int).to_numpy(),
        evaluation["target_only_score"].to_numpy(dtype=float),
        float(thresholds["detection_threshold"]),
    )
    forced_scope = classification_metrics(
        (scope["state"] == "local").astype(int).to_numpy(),
        scope["comparative_scope_score"].to_numpy(dtype=float),
        float(thresholds["scope_threshold"]),
    )
    selective: dict[str, Any] = {}
    for quantile, cutoff in thresholds["selective_confidence_cutoffs"].items():
        answered = scope[f"answered_q{quantile}"].to_numpy(dtype=bool)
        answered_scope = scope.loc[answered]
        reasons = scope[f"abstention_reason_q{quantile}"].value_counts().to_dict()
        entry: dict[str, Any] = {
            "confidence_cutoff": float(cutoff),
            "answered_count": int(answered.sum()),
            "scope_case_count": int(len(scope)),
            "coverage": float(answered.mean()),
            "abstention_reason_counts": {
                str(reason): int(count) for reason, count in reasons.items()
            },
        }
        if answered.any():
            entry["answered_case_error"] = float(
                np.mean(
                    (answered_scope["forced_scope_prediction"] == "local").astype(int)
                    != (answered_scope["state"] == "local").astype(int)
                )
            )
            entry["risk_status"] = "estimated"
        else:
            entry["answered_case_error"] = None
            entry["risk_status"] = "no_answered_cases"
        selective[quantile] = entry
    return {
        "complete_event_accounting": {
            state: int((evaluation["state"] == state).sum())
            for state in ("no_change", "local", "regional")
        },
        "target_identity_rate": scalars["target_identity_rate"],
        "detection": metrics_as_dict(detection),
        "forced_scope": {
            **metrics_as_dict(forced_scope),
            "error": scalars["forced_scope_error"],
        },
        "target_only_scope": {
            "policy": "always_local",
            "error": scalars["target_only_scope_error"],
            "scope_case_count": int(len(scope)),
        },
        "selective_scope": selective,
    }


def bootstrap_evaluation(
    core: pd.DataFrame, thresholds: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, Any]:
    """Resample complete evaluation components for predeclared metric intervals."""

    evaluation = core.loc[core["split"] == "evaluation"].copy()
    component_ids = np.sort(evaluation["component_id"].unique())
    expected_components = int(
        protocol["synthetic_panel"]["component_counts"]["evaluation"]
    )
    if len(component_ids) != expected_components:
        raise RuntimeError("Evaluation component count does not match the protocol.")
    point = scalar_evaluation_metrics(evaluation, thresholds)
    bootstrap = protocol["evaluation"]["bootstrap"]
    repetitions = int(bootstrap["repetitions"])
    rng = np.random.default_rng(int(bootstrap["seed"]))
    groups = {
        component_id: evaluation.loc[
            evaluation["component_id"] == component_id
        ].copy()
        for component_id in component_ids
    }
    samples: dict[str, list[float]] = {name: [] for name in point}
    for _ in range(repetitions):
        sampled_ids = rng.choice(component_ids, size=len(component_ids), replace=True)
        sampled = pd.concat(
            [groups[component_id] for component_id in sampled_ids], ignore_index=True
        )
        values = scalar_evaluation_metrics(sampled, thresholds)
        for name, value in values.items():
            if value is not None:
                samples[name].append(value)
    minimum_valid = int(
        bootstrap["minimum_valid_repetitions_per_answered_risk"]
    )
    intervals: dict[str, dict[str, Any]] = {}
    for name, values in samples.items():
        if point[name] is None or len(values) < minimum_valid:
            intervals[name] = {
                "point": point[name],
                "valid_repetitions": len(values),
                "status": "insufficient_valid_repetitions",
            }
            continue
        intervals[name] = {
            "point": float(point[name]),
            "valid_repetitions": len(values),
            "status": "estimated",
            "lower_95": float(np.quantile(values, 0.025, method="linear")),
            "upper_95": float(np.quantile(values, 0.975, method="linear")),
        }
    return {
        "cluster": bootstrap["cluster"],
        "repetitions": repetitions,
        "seed": int(bootstrap["seed"]),
        "metrics": intervals,
    }


def availability_normalized_mismatch(
    target: pd.Series, donors: pd.DataFrame, weights: pd.Series, dates: pd.DatetimeIndex
) -> tuple[np.ndarray, np.ndarray]:
    """Return retained-date donor mismatch and normalized weight matrices."""

    donor_values = donors.loc[dates].astype(float)
    available = donor_values.notna()
    normalized = available.mul(weights, axis="columns")
    weight_sum = normalized.sum(axis="columns")
    if (weight_sum <= 0).any():
        raise RuntimeError("Stress bound encountered a date without available donors.")
    normalized = normalized.div(weight_sum, axis="index")
    target_values = target.loc[dates].to_numpy(dtype=float)[:, np.newaxis]
    mismatch = np.abs(target_values - donor_values.to_numpy(dtype=float))
    return mismatch, normalized.to_numpy(dtype=float)


def stress_variant(
    component: SyntheticComponent,
    stress_specification: dict[str, Any],
    protocol: dict[str, Any],
) -> tuple[pd.Series, pd.DataFrame, int]:
    """Apply one fully declared regional raw-scale stress perturbation."""

    name = str(stress_specification["name"])
    parameters = stress_specification["parameters"]
    stress_id = (
        f"{protocol['protocol_id']}:{component.split}:{component.component_id}:"
        f"{name}:stress"
    )
    seed = paired_schedule_seed(
        stress_id, base_seed=int(protocol["synthetic_panel"]["base_seed"])
    )
    if name == "raw_additive_step":
        kind, magnitude, kwargs = PerturbationKind.REGIONAL_ADDITIVE_STEP, float(
            parameters["magnitude"]
        ), {}
    elif name == "raw_proportional_step":
        kind, magnitude, kwargs = PerturbationKind.REGIONAL_PROPORTIONAL_STEP, float(
            parameters["proportion"]
        ), {}
    elif name == "raw_gradual_drift":
        kind, magnitude, kwargs = PerturbationKind.REGIONAL_GRADUAL_DRIFT, float(
            parameters["magnitude"]
        ), {"drift_days": int(parameters["drift_days"])}
    elif name == "raw_temporary_step":
        kind, magnitude, kwargs = PerturbationKind.REGIONAL_TEMPORARY_STEP, float(
            parameters["magnitude"]
        ), {"duration_days": int(parameters["duration_days"])}
    elif name == "raw_variance_increase":
        kind, magnitude, kwargs = PerturbationKind.REGIONAL_VARIANCE_INCREASE, float(
            parameters["magnitude_multiplier"]
        ), {}
    else:
        raise ValueError(f"Unknown raw-scale stress family: {name}")
    target, donors, _ = inject_perturbation(
        component.target,
        component.donors,
        component.anchor_date,
        kind,
        magnitude,
        random_seed=seed,
        **kwargs,
    )
    return target, donors, seed


def stress_bound(
    component: SyntheticComponent,
    changed_target: pd.Series,
    stress_specification: dict[str, Any],
    protocol: dict[str, Any],
) -> float:
    """Calculate the predeclared maximum median-leakage upper bound."""

    estimator = protocol["estimator"]
    baseline_windows = anchor_residual_windows(
        component.target,
        component.donors,
        component.weights,
        component.anchor_date,
        calibration_days=int(estimator["calibration_days"]),
        calibration_buffer_days=int(estimator["calibration_buffer_days"]),
        comparison_days=int(estimator["comparison_days"]),
        min_window_observations=int(estimator["minimum_window_observations"]),
        min_available_donors=int(estimator["minimum_available_donors"]),
    )
    dates = baseline_windows.post.index
    mismatch, normalized = availability_normalized_mismatch(
        component.target, component.donors, component.weights, dates
    )
    name = str(stress_specification["name"])
    parameters = stress_specification["parameters"]
    if name in {"raw_additive_step", "raw_gradual_drift", "raw_temporary_step"}:
        increments = (
            changed_target.loc[dates].to_numpy(dtype=float)
            - component.target.loc[dates].to_numpy(dtype=float)
        )
        lower_bounds = np.minimum(
            component.target.loc[dates].to_numpy(dtype=float),
            np.nanmin(component.donors.loc[dates].to_numpy(dtype=float), axis=1),
        )
        constants = np.asarray(
            [
                additive_increment_lipschitz_constant(
                    float(increment), nonnegative_lower_bound=float(lower_bound)
                )
                for increment, lower_bound in zip(increments, lower_bounds, strict=True)
            ]
        )
    elif name == "raw_proportional_step":
        constants = np.full(
            len(dates),
            proportional_increment_lipschitz_constant(
                float(parameters["proportion"])
            ),
        )
    elif name == "raw_variance_increase":
        constants = np.ones(len(dates))
    else:
        raise ValueError(f"Unknown raw-scale stress family: {name}")
    daily_bound = constants * np.nansum(normalized * mismatch, axis=1)
    if not np.isfinite(daily_bound).all():
        raise ValueError("Stress bound is nonfinite.")
    return float(np.max(daily_bound))


def generate_stress_rows(protocol: dict[str, Any]) -> pd.DataFrame:
    """Generate all regional raw-scale stress diagnostics without output writes."""

    estimator = protocol["estimator"]
    tolerance = float(estimator["numerical_invariance_tolerance"])
    rows: list[dict[str, Any]] = []
    for split, count in protocol["synthetic_panel"]["component_counts"].items():
        for index in range(int(count)):
            component = generate_component(protocol, str(split), index)
            baseline_windows = anchor_residual_windows(
                component.target,
                component.donors,
                component.weights,
                component.anchor_date,
                calibration_days=int(estimator["calibration_days"]),
                calibration_buffer_days=int(estimator["calibration_buffer_days"]),
                comparison_days=int(estimator["comparison_days"]),
                min_window_observations=int(estimator["minimum_window_observations"]),
                min_available_donors=int(estimator["minimum_available_donors"]),
            )
            baseline_effect = float(
                np.median(baseline_windows.post["log_residual"])
                - np.median(baseline_windows.pre["log_residual"])
            )
            for stress_specification in protocol["raw_scale_stress_suite"]["families"]:
                changed_target, changed_donors, seed = stress_variant(
                    component, stress_specification, protocol
                )
                changed_windows = anchor_residual_windows(
                    changed_target,
                    changed_donors,
                    component.weights,
                    component.anchor_date,
                    calibration_days=int(estimator["calibration_days"]),
                    calibration_buffer_days=int(estimator["calibration_buffer_days"]),
                    comparison_days=int(estimator["comparison_days"]),
                    min_window_observations=int(estimator["minimum_window_observations"]),
                    min_available_donors=int(estimator["minimum_available_donors"]),
                )
                changed_effect = float(
                    np.median(changed_windows.post["log_residual"])
                    - np.median(changed_windows.pre["log_residual"])
                )
                leakage = abs(changed_effect - baseline_effect)
                maximum_bound = stress_bound(
                    component, changed_target, stress_specification, protocol
                )
                if leakage > maximum_bound + tolerance:
                    raise RuntimeError(
                        f"Stress bound failed for {component.component_id} "
                        f"{stress_specification['name']}."
                    )
                rows.append(
                    {
                        "protocol_id": protocol["protocol_id"],
                        "component_id": component.component_id,
                        "split": component.split,
                        "stress_family": stress_specification["name"],
                        "stress_seed": seed,
                        "maximum_residual_leakage_bound": maximum_bound,
                        "absolute_median_effect_leakage": leakage,
                        "bound_satisfied": True,
                    }
                )
    frame = pd.DataFrame(rows)
    expected_count = int(protocol["expected_accounting"]["stress_events"])
    if len(frame) != expected_count:
        raise RuntimeError("Stress event count does not match the protocol.")
    if not frame["bound_satisfied"].all():
        raise RuntimeError("Stress suite contains a bound failure.")
    return frame


def assert_output_schema(
    frame: pd.DataFrame, required_columns: list[str], filename: str
) -> None:
    missing = set(required_columns).difference(frame.columns)
    if missing:
        raise RuntimeError(f"{filename} is missing required columns: {sorted(missing)}")


def acquire_attempt(
    output_directory: Path, attempt_record: Path, preconditions: dict[str, Any]
) -> None:
    """Atomically record a one-time start before any results can be written."""

    if output_directory.exists() or attempt_record.exists():
        raise FileExistsError(
            "A v0.4 result directory or durable attempt record already exists; "
            "refusing a rerun."
        )
    attempt_record.parent.mkdir(parents=True, exist_ok=True)
    started = {
        "state": "started",
        "started_at_utc": utc_now(),
        **preconditions,
    }
    encoded = json.dumps(started, indent=2, sort_keys=True, allow_nan=False).encode(
        "utf-8"
    )
    descriptor = os.open(
        attempt_record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(encoded)
        destination.flush()
        os.fsync(destination.fileno())
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
    except Exception as error:
        write_json_atomic(
            attempt_record,
            {
                "state": "failed",
                "failed_at_utc": utc_now(),
                "failure_type": type(error).__name__,
                "failure_message": str(error),
                **preconditions,
            },
        )
        raise


def run_once(protocol: dict[str, Any]) -> dict[str, Any]:
    """Generate, score, bootstrap, and archive one fully frozen result set."""

    preconditions = ensure_execution_preconditions(protocol)
    contract = protocol["output_contract"]
    output_directory = project_path(str(contract["directory"]))
    attempt_record = project_path(str(contract["attempt_record"]))
    acquire_attempt(output_directory, attempt_record, preconditions)
    receipt_path = output_directory / "v04_execution_receipt.json"
    paths = {
        "v04_core_event_results.csv": output_directory / "v04_core_event_results.csv",
        "v04_core_thresholds.json": output_directory / "v04_core_thresholds.json",
        "v04_core_metrics.json": output_directory / "v04_core_metrics.json",
        "v04_core_bootstrap.json": output_directory / "v04_core_bootstrap.json",
        "v04_stress_results.csv": output_directory / "v04_stress_results.csv",
    }
    core_event_count: int | None = None
    stress_event_count: int | None = None
    try:
        core = generate_core_rows(protocol, str(preconditions["execution_tag"]))
        core_event_count = int(len(core))
        thresholds = calibration_thresholds(core, protocol)
        core = apply_predictions(core, thresholds)
        metrics = summarize_evaluation(core, thresholds, protocol)
        bootstrap = bootstrap_evaluation(core, thresholds, protocol)
        stress = generate_stress_rows(protocol)
        stress_event_count = int(len(stress))

        schemas = contract["schemas"]
        assert_output_schema(
            core, list(schemas["v04_core_event_results.csv"]), "v04_core_event_results.csv"
        )
        assert_output_schema(
            stress, list(schemas["v04_stress_results.csv"]), "v04_stress_results.csv"
        )
        write_csv_atomic(paths["v04_core_event_results.csv"], core)
        write_json_atomic(paths["v04_core_thresholds.json"], thresholds)
        write_json_atomic(paths["v04_core_metrics.json"], metrics)
        write_json_atomic(paths["v04_core_bootstrap.json"], bootstrap)
        write_csv_atomic(paths["v04_stress_results.csv"], stress)
        output_hashes = {filename: sha256(path) for filename, path in paths.items()}
        receipt = {
            "state": "completed",
            "completed_at_utc": utc_now(),
            "protocol_id": protocol["protocol_id"],
            "protocol_freeze_tag": contract["protocol_freeze_tag"],
            **preconditions,
            "input_count_accounting": {
                "core_event_count": core_event_count,
                "stress_event_count": stress_event_count,
                "failure_count": 0,
            },
            "output_hashes": output_hashes,
            "failure_count": 0,
        }
        write_json_atomic(receipt_path, receipt)
        write_json_atomic(
            attempt_record,
            {
                "state": "completed",
                "completed_at_utc": utc_now(),
                "execution_receipt_sha256": sha256(receipt_path),
                **preconditions,
            },
        )
        return receipt
    except Exception as error:
        partial_output_hashes = {
            filename: sha256(path)
            for filename, path in paths.items()
            if path.is_file()
        }
        failure_receipt = {
            "state": "failed",
            "failed_at_utc": utc_now(),
            "protocol_id": protocol["protocol_id"],
            "protocol_freeze_tag": contract["protocol_freeze_tag"],
            **preconditions,
            "input_count_accounting": {
                "core_event_count": core_event_count,
                "stress_event_count": stress_event_count,
                "failure_count": 1,
            },
            "output_hashes": partial_output_hashes,
            "failure_type": type(error).__name__,
            "failure_message": str(error),
            "traceback": traceback.format_exc(),
            "failure_count": 1,
        }
        write_json_atomic(receipt_path, failure_receipt)
        write_json_atomic(
            attempt_record,
            {
                "state": "failed",
                "failed_at_utc": utc_now(),
                "execution_receipt_sha256": sha256(receipt_path),
                "failure_type": type(error).__name__,
                "failure_message": str(error),
                **preconditions,
            },
        )
        raise


def main() -> None:
    args = parse_args()
    protocol = read_protocol()
    if not args.execute:
        print(
            json.dumps(
                {
                    "state": "not_executed",
                    "protocol_id": protocol["protocol_id"],
                    "message": (
                        "Pass --execute only at the matching "
                        "v0.4.0-execution-freeze commit."
                    ),
                },
                indent=2,
            )
        )
        return
    receipt = run_once(protocol)
    print(
        json.dumps(
            {
                "state": receipt["state"],
                "execution_tag": receipt["execution_tag"],
                "core_event_count": receipt["input_count_accounting"]["core_event_count"],
                "stress_event_count": receipt["input_count_accounting"]["stress_event_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
