"""Verify the immutable v0.4 result bundle after its one permitted execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metashift.identifiability import paired_schedule_seed
from metashift.identifiability import schedule_sha256
from metashift.metrics import classification_metrics, metrics_as_dict, select_macro_f1_threshold
from scripts import run_v04_identifiability_benchmark as runner


PROTOCOL_PATH = ROOT / "configs" / "v04_identifiability_protocol.json"
MANIFEST_PATH = ROOT / "configs" / "v04_identifiability_execution_manifest.json"
PROTOCOL_RELATIVE_PATH = "configs/v04_identifiability_protocol.json"
MANIFEST_RELATIVE_PATH = "configs/v04_identifiability_execution_manifest.json"
EXPECTED_EXECUTION_TAG = "v0.4.1-execution-freeze"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a completed v0.4 identifiability result bundle."
    )
    parser.add_argument(
        "--require-results",
        action="store_true",
        help="Fail unless the one-time result bundle exists and passes every check.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def source_sha256(path: Path) -> str:
    """Hash tracked UTF-8 source as LF-normalized Git-blob content."""

    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def git_text(arguments: list[str]) -> str:
    return git_bytes(arguments).decode("utf-8").strip()


def git_bytes(arguments: list[str]) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def remote_peeled_tag_commit(remote_listing: str, tag: str) -> str:
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


def tagged_execution_authority(
    execution_tag: str = EXPECTED_EXECUTION_TAG,
    *,
    verify_current_checkout: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read and validate the immutable authority directly from the remote-bound tag."""

    if git_text(["cat-file", "-t", f"refs/tags/{execution_tag}"]) != "tag":
        raise RuntimeError("Execution evidence must be verified from a local annotated tag.")
    execution_commit = git_text(["rev-parse", f"{execution_tag}^{{commit}}"])
    remote_commit = remote_peeled_tag_commit(
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
    if remote_commit != execution_commit:
        raise RuntimeError(
            "The remote execution-freeze tag must resolve to the local tagged commit."
        )
    protocol_bytes = git_bytes(["show", f"{execution_tag}:{PROTOCOL_RELATIVE_PATH}"])
    manifest_bytes = git_bytes(["show", f"{execution_tag}:{MANIFEST_RELATIVE_PATH}"])
    protocol = json.loads(protocol_bytes)
    manifest = json.loads(manifest_bytes)
    if protocol["output_contract"]["execution_freeze_tag"] != execution_tag:
        raise RuntimeError("Tagged protocol is bound to a different execution-freeze tag.")
    allowlist = protocol["data_access"]["execution_input_allowlist"]
    tagged_hashes = {
        relative_path: sha256_bytes(
            git_bytes(["show", f"{execution_tag}:{relative_path}"])
        )
        for relative_path in allowlist
    }
    if manifest.get("protocol_sha256") != tagged_hashes[PROTOCOL_RELATIVE_PATH]:
        raise RuntimeError("Tagged execution manifest does not bind the tagged protocol.")
    expected_bound_paths = set(allowlist).difference({MANIFEST_RELATIVE_PATH})
    if manifest.get("bound_input_sha256") != {
        path: tagged_hashes[path] for path in expected_bound_paths
    }:
        raise RuntimeError(
            "Tagged execution manifest does not bind every tagged non-self input."
        )
    if verify_current_checkout:
        if git_text(["status", "--porcelain"]):
            raise RuntimeError(
                "Result verification requires a clean checkout of the execution tag."
            )
        if git_text(["rev-parse", "HEAD"]) != execution_commit:
            raise RuntimeError(
                "Result verification must run at the execution-freeze commit."
            )
        current_hashes = {
            relative_path: source_sha256(ROOT / relative_path)
            for relative_path in allowlist
        }
        if current_hashes != tagged_hashes:
            raise RuntimeError(
                "Current allowlisted source does not match the tagged execution source."
            )
    return (
        protocol,
        manifest,
        {
            "execution_git_commit": execution_commit,
            "protocol_sha256": tagged_hashes[PROTOCOL_RELATIVE_PATH],
            "execution_manifest_sha256": tagged_hashes[MANIFEST_RELATIVE_PATH],
            "allowed_input_hashes": tagged_hashes,
        },
    )


def replay_frozen_outputs(
    protocol: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    """Reconstruct all frozen synthetic outcomes in memory without output writes."""

    core = runner.generate_core_rows(
        protocol, str(protocol["output_contract"]["execution_freeze_tag"])
    )
    thresholds = runner.calibration_thresholds(core, protocol)
    return runner.apply_predictions(core, thresholds), thresholds, runner.generate_stress_rows(
        protocol
    )


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def json_matches(expected: Any, actual: Any, tolerance: float = 1e-12) -> bool:
    """Compare JSON-like values with a numerical tolerance for recomputation."""

    if expected is None or actual is None:
        return expected is actual
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(expected) == set(actual) and all(
            json_matches(expected[key], actual[key], tolerance) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            json_matches(left, right, tolerance) for left, right in zip(expected, actual)
        )
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return bool(
            np.isfinite(float(expected))
            and np.isfinite(float(actual))
            and np.isclose(float(expected), float(actual), rtol=0.0, atol=tolerance)
        )
    return expected == actual


def parse_boolean_series(series: pd.Series) -> np.ndarray:
    values: list[bool] = []
    for value in series:
        if isinstance(value, (bool, np.bool_)):
            values.append(bool(value))
        elif isinstance(value, str) and value.lower() in {"true", "false"}:
            values.append(value.lower() == "true")
        else:
            raise ValueError(f"Expected a Boolean CSV value, found {value!r}.")
    return np.asarray(values, dtype=bool)


def text_series(series: pd.Series) -> np.ndarray:
    return np.asarray(
        ["" if pd.isna(value) else str(value) for value in series], dtype=object
    )


def expected_thresholds(core: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]:
    calibration = core.loc[core["split"] == "calibration"].copy()
    scope = calibration.loc[calibration["state"].isin(["local", "regional"])].copy()
    detection_threshold = select_macro_f1_threshold(
        (calibration["state"] != "no_change").astype(int).to_numpy(),
        calibration["target_only_score"].to_numpy(dtype=float),
    )
    scope_threshold = select_macro_f1_threshold(
        (scope["state"] == "local").astype(int).to_numpy(),
        scope["comparative_scope_score"].to_numpy(dtype=float),
    )
    confidence = np.abs(
        scope["comparative_scope_score"].to_numpy(dtype=float) - scope_threshold
    )
    quantiles = protocol["evaluation"]["selective_policy"]["operating_quantiles"]
    return {
        "detection_threshold": float(detection_threshold),
        "scope_threshold": float(scope_threshold),
        "selective_confidence_cutoffs": {
            f"{float(quantile):.2f}": float(
                np.quantile(confidence, float(quantile), method="linear")
            )
            for quantile in quantiles
        },
        "calibration_case_counts": {
            "all_n_l_r": int(len(calibration)),
            "scope_l_r": int(len(scope)),
            "no_change": int((calibration["state"] == "no_change").sum()),
            "local": int((calibration["state"] == "local").sum()),
            "regional": int((calibration["state"] == "regional").sum()),
        },
    }


def scalar_metrics(
    frame: pd.DataFrame, thresholds: dict[str, Any]
) -> dict[str, float | None]:
    detection_labels = (frame["state"] != "no_change").astype(int).to_numpy()
    detection = classification_metrics(
        detection_labels,
        frame["target_only_score"].to_numpy(dtype=float),
        float(thresholds["detection_threshold"]),
    )
    scope = frame.loc[frame["state"].isin(["local", "regional"])].copy()
    scope_labels = (scope["state"] == "local").astype(int).to_numpy()
    forced_prediction = (
        scope["comparative_scope_score"].to_numpy(dtype=float)
        >= float(thresholds["scope_threshold"])
    ).astype(int)
    identity = parse_boolean_series(scope["local_regional_target_identity"])
    values: dict[str, float | None] = {
        "detection_macro_f1": float(detection.macro_f1),
        "forced_scope_error": float(np.mean(forced_prediction != scope_labels)),
        "target_only_scope_error": float(np.mean(1 != scope_labels)),
        "target_identity_rate": float(identity.mean()),
    }
    for quantile, cutoff in thresholds["selective_confidence_cutoffs"].items():
        answered = np.abs(
            scope["comparative_scope_score"].to_numpy(dtype=float)
            - float(thresholds["scope_threshold"])
        ) >= float(cutoff)
        if answered.any():
            values[f"selective_scope_error_q{quantile}"] = float(
                np.mean(forced_prediction[answered] != scope_labels[answered])
            )
        else:
            values[f"selective_scope_error_q{quantile}"] = None
        values[f"selective_scope_coverage_q{quantile}"] = float(answered.mean())
    return values


def expected_metrics(
    core: pd.DataFrame, thresholds: dict[str, Any]
) -> dict[str, Any]:
    evaluation = core.loc[core["split"] == "evaluation"].copy()
    scope = evaluation.loc[evaluation["state"].isin(["local", "regional"])].copy()
    values = scalar_metrics(evaluation, thresholds)
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
        confidence = np.abs(
            scope["comparative_scope_score"].to_numpy(dtype=float)
            - float(thresholds["scope_threshold"])
        )
        answered = confidence >= float(cutoff)
        reasons = np.where(answered, "answered", "below_scope_confidence_cutoff")
        entry: dict[str, Any] = {
            "confidence_cutoff": float(cutoff),
            "answered_count": int(answered.sum()),
            "scope_case_count": int(len(scope)),
            "coverage": float(answered.mean()),
            "abstention_reason_counts": {
                str(reason): int(count)
                for reason, count in pd.Series(reasons).value_counts().to_dict().items()
            },
        }
        if answered.any():
            entry["answered_case_error"] = values[
                f"selective_scope_error_q{quantile}"
            ]
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
        "target_identity_rate": values["target_identity_rate"],
        "detection": metrics_as_dict(detection),
        "forced_scope": {
            **metrics_as_dict(forced_scope),
            "error": values["forced_scope_error"],
        },
        "target_only_scope": {
            "policy": "always_local",
            "error": values["target_only_scope_error"],
            "scope_case_count": int(len(scope)),
        },
        "selective_scope": selective,
    }


def expected_bootstrap(
    core: pd.DataFrame, thresholds: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, Any]:
    evaluation = core.loc[core["split"] == "evaluation"].copy()
    component_ids = np.sort(evaluation["component_id"].unique())
    groups = {
        component_id: evaluation.loc[
            evaluation["component_id"] == component_id
        ].copy()
        for component_id in component_ids
    }
    point = scalar_metrics(evaluation, thresholds)
    specification = protocol["evaluation"]["bootstrap"]
    repetitions = int(specification["repetitions"])
    rng = np.random.default_rng(int(specification["seed"]))
    samples: dict[str, list[float]] = {name: [] for name in point}
    for _ in range(repetitions):
        sampled_ids = rng.choice(component_ids, size=len(component_ids), replace=True)
        sampled = pd.concat(
            [groups[component_id] for component_id in sampled_ids], ignore_index=True
        )
        values = scalar_metrics(sampled, thresholds)
        for name, value in values.items():
            if value is not None:
                samples[name].append(float(value))
    minimum_valid = int(
        specification["minimum_valid_repetitions_per_answered_risk"]
    )
    metrics: dict[str, Any] = {}
    for name, values in samples.items():
        if point[name] is None or len(values) < minimum_valid:
            metrics[name] = {
                "point": point[name],
                "valid_repetitions": len(values),
                "status": "insufficient_valid_repetitions",
            }
        else:
            metrics[name] = {
                "point": float(point[name]),
                "valid_repetitions": len(values),
                "status": "estimated",
                "lower_95": float(np.quantile(values, 0.025, method="linear")),
                "upper_95": float(np.quantile(values, 0.975, method="linear")),
            }
    return {
        "cluster": specification["cluster"],
        "repetitions": repetitions,
        "seed": int(specification["seed"]),
        "metrics": metrics,
    }


def expected_core_identity(
    protocol: dict[str, Any],
) -> dict[str, tuple[str, str, str, int, str]]:
    """Derive each permitted case from the protocol, without reading result values."""

    panel = protocol["synthetic_panel"]
    dates = pd.date_range(
        str(panel["start_date"]), periods=int(panel["days"]), freq="D"
    )
    anchor = dates[int(panel["anchor_day_index"])]
    pair_template = protocol["matched_pairs"]["pair_id_template"]
    base_seed = int(panel["base_seed"])
    expected: dict[str, tuple[str, str, int, str]] = {}
    for split, component_count in panel["component_counts"].items():
        for component_index in range(int(component_count)):
            component_id = str(panel["component_id_template"]).format(
                split=split, index=component_index
            )
            for specification in protocol["schedule_families"]:
                family = str(specification["name"])
                pair_id = str(pair_template).format(
                    split=split,
                    component_id=component_id,
                    schedule_family=family,
                )
                seed = paired_schedule_seed(pair_id, base_seed=base_seed)
                schedule = pd.Series(0.0, index=dates)
                post_mask = dates >= anchor
                if family == "constant_step":
                    schedule.loc[post_mask] = float(
                        specification["parameters"]["post_increment"]
                    )
                elif family == "bounded_stochastic_step":
                    rng = np.random.default_rng(seed)
                    schedule.loc[post_mask] = float(
                        specification["parameters"]["post_center"]
                    ) + rng.uniform(
                        -float(specification["parameters"]["uniform_half_width"]),
                        float(specification["parameters"]["uniform_half_width"]),
                        int(post_mask.sum()),
                    )
                else:
                    raise ValueError(f"Unknown frozen schedule family: {family}")
                for state in ("no_change", "local", "regional"):
                    expected[f"{pair_id}:{state}"] = (
                        str(split),
                        component_id,
                        family,
                        seed,
                        schedule_sha256(schedule),
                    )
    return expected


def core_is_complete(core: pd.DataFrame, protocol: dict[str, Any]) -> bool:
    contract = protocol["output_contract"]
    expected_columns = contract["schemas"]["v04_core_event_results.csv"]
    if list(core.columns) != expected_columns:
        return False
    expected = protocol["expected_accounting"]["core_events"]
    panel = protocol["synthetic_panel"]["component_counts"]
    families = {item["name"] for item in protocol["schedule_families"]}
    expected_identity = expected_core_identity(protocol)
    if (
        len(core) != int(expected["total"])
        or not core["case_id"].is_unique
        or set(core["case_id"]) != set(expected_identity)
    ):
        return False
    if not set(core["state"]) == {"no_change", "local", "regional"}:
        return False
    if not set(core["schedule_family"]) == families:
        return False
    if not (
        np.isfinite(
            core[
                [
                    "target_only_score",
                    "comparative_scope_score",
                    "comparative_log_effect",
                ]
            ].to_numpy(dtype=float)
        ).all()
    ):
        return False
    if not core["schedule_sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        return False
    if not (
        core["protocol_id"].eq(protocol["protocol_id"]).all()
        and core["execution_tag"].eq(contract["execution_freeze_tag"]).all()
    ):
        return False
    split_components: dict[str, set[str]] = {}
    for split, component_count in panel.items():
        rows = core.loc[core["split"] == split]
        if len(rows) != int(expected[split]):
            return False
        expected_per_state = int(expected[split]) // 3
        if any(int((rows["state"] == state).sum()) != expected_per_state for state in ("no_change", "local", "regional")):
            return False
        components = set(rows["component_id"])
        if len(components) != int(component_count):
            return False
        split_components[str(split)] = components
        for _, component_rows in rows.groupby("component_id", sort=False):
            if len(component_rows) != 3 * len(families):
                return False
            if set(component_rows["schedule_family"]) != families:
                return False
            for _, pair_rows in component_rows.groupby("pair_id", sort=False):
                if (
                    len(pair_rows) != 3
                    or set(pair_rows["state"]) != {"no_change", "local", "regional"}
                    or pair_rows["schedule_family"].nunique() != 1
                    or pair_rows["schedule_seed"].nunique() != 1
                    or pair_rows["schedule_sha256"].nunique() != 1
                ):
                    return False
                scope_rows = pair_rows.loc[
                    pair_rows["state"].isin(["local", "regional"])
                ]
                if not parse_boolean_series(
                    scope_rows["local_regional_target_identity"]
                ).all():
                    return False
                local_row = scope_rows.loc[scope_rows["state"] == "local"].iloc[0]
                regional_row = scope_rows.loc[
                    scope_rows["state"] == "regional"
                ].iloc[0]
                no_change_row = pair_rows.loc[
                    pair_rows["state"] == "no_change"
                ].iloc[0]
                if not (
                    np.isclose(
                        float(local_row["target_only_score"]),
                        float(regional_row["target_only_score"]),
                        rtol=0.0,
                        atol=0.0,
                    )
                    and np.isclose(
                        float(regional_row["comparative_log_effect"]),
                        float(no_change_row["comparative_log_effect"]),
                        rtol=0.0,
                        atol=float(protocol["estimator"]["numerical_invariance_tolerance"]),
                    )
                ):
                    return False
                if not pair_rows.loc[
                    pair_rows["state"] == "no_change",
                    "local_regional_target_identity",
                ].isna().all():
                    return False
    for _, row in core.iterrows():
        split, component_id, family, seed, schedule_hash = expected_identity[
            row["case_id"]
        ]
        if not (
            row["split"] == split
            and row["component_id"] == component_id
            and row["schedule_family"] == family
            and int(row["schedule_seed"]) == seed
            and row["schedule_sha256"] == schedule_hash
            and row["pair_id"] == str(row["case_id"]).rsplit(":", maxsplit=1)[0]
        ):
            return False
    return split_components["calibration"].isdisjoint(split_components["evaluation"])


def frames_match(
    actual: pd.DataFrame, expected: pd.DataFrame, index_columns: list[str]
) -> bool:
    """Compare a replayed frame to its stored counterpart, including all fields."""

    if list(actual.columns) != list(expected.columns) or len(actual) != len(expected):
        return False
    if actual.duplicated(index_columns).any() or expected.duplicated(index_columns).any():
        return False
    actual_indexed = actual.set_index(index_columns).sort_index()
    expected_indexed = expected.set_index(index_columns).sort_index()
    if not actual_indexed.index.equals(expected_indexed.index):
        return False
    for column in expected_indexed.columns:
        expected_column = expected_indexed[column]
        actual_column = actual_indexed[column]
        if pd.api.types.is_numeric_dtype(expected_column):
            try:
                actual_values = actual_column.to_numpy(dtype=float)
                expected_values = expected_column.to_numpy(dtype=float)
            except (TypeError, ValueError):
                return False
            if not np.allclose(
                actual_values,
                expected_values,
                rtol=0.0,
                atol=1e-12,
                equal_nan=True,
            ):
                return False
        elif not np.array_equal(
            text_series(actual_column),
            text_series(expected_column),
        ):
            return False
    return True


def predictions_match(actual: pd.DataFrame, replayed: pd.DataFrame) -> bool:
    """Compare categorical decisions to the replay before CSV decimal rounding."""

    columns = [
        "case_id",
        "detection_prediction",
        "forced_scope_prediction",
        "target_only_scope_prediction",
        "scope_confidence",
    ]
    for quantile in ("0.00", "0.25", "0.50", "0.75"):
        columns.extend(
            [f"answered_q{quantile}", f"abstention_reason_q{quantile}"]
        )
    return frames_match(
        actual.loc[:, columns], replayed.loc[:, columns], ["case_id"]
    )


def stress_is_complete(
    stress: pd.DataFrame, core: pd.DataFrame, protocol: dict[str, Any]
) -> bool:
    expected_columns = protocol["output_contract"]["schemas"]["v04_stress_results.csv"]
    if list(stress.columns) != expected_columns:
        return False
    expected_count = int(protocol["expected_accounting"]["stress_events"])
    families = {item["name"] for item in protocol["raw_scale_stress_suite"]["families"]}
    if len(stress) != expected_count or not set(stress["stress_family"]) == families:
        return False
    if not (
        stress["protocol_id"].eq(protocol["protocol_id"]).all()
        and np.isfinite(
            stress[
                [
                    "maximum_residual_leakage_bound",
                    "absolute_median_effect_leakage",
                ]
            ].to_numpy(dtype=float)
        ).all()
        and (stress["maximum_residual_leakage_bound"] >= 0.0).all()
        and (stress["absolute_median_effect_leakage"] >= 0.0).all()
        and parse_boolean_series(stress["bound_satisfied"]).all()
    ):
        return False
    tolerance = float(protocol["estimator"]["numerical_invariance_tolerance"])
    if (
        stress["absolute_median_effect_leakage"].to_numpy(dtype=float)
        > stress["maximum_residual_leakage_bound"].to_numpy(dtype=float) + tolerance
    ).any():
        return False
    base_seed = int(protocol["synthetic_panel"]["base_seed"])
    expected_components = {
        split: set(core.loc[core["split"] == split, "component_id"])
        for split in protocol["synthetic_panel"]["component_counts"]
    }
    if stress.duplicated(["component_id", "stress_family"]).any():
        return False
    for split, component_ids in expected_components.items():
        split_rows = stress.loc[stress["split"] == split]
        if set(split_rows["component_id"]) != component_ids:
            return False
        for _, row in split_rows.iterrows():
            expected_seed = paired_schedule_seed(
                (
                    f"{protocol['protocol_id']}:{row['split']}:{row['component_id']}:"
                    f"{row['stress_family']}:stress"
                ),
                base_seed=base_seed,
            )
            if int(row["stress_seed"]) != expected_seed:
                return False
    return True


def output_paths(protocol: dict[str, Any], directory: Path) -> dict[str, Path]:
    return {
        filename: directory / filename
        for filename in protocol["output_contract"]["files"]
    }


def build_pre_execution_report(
    protocol: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if protocol is None:
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if manifest is None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract = protocol["output_contract"]
    verifier_path = contract.get("post_execution_verifier")
    core_schema = contract["schemas"]["v04_core_event_results.csv"]
    required_core_columns = {
        "comparative_log_effect",
        "target_only_scope_prediction",
        "scope_confidence",
        "answered_q0.75",
        "abstention_reason_q0.75",
    }
    checks = [
        check(
            "result_verifier_is_predeclared_and_hashed",
            verifier_path == "scripts/verify_v04_identifiability_results.py"
            and verifier_path in protocol["data_access"]["execution_input_allowlist"]
            and verifier_path in manifest.get("bound_input_sha256", {})
            and (ROOT / str(verifier_path)).is_file(),
            "The independent post-execution verifier is declared, tracked, and input-hashed.",
        ),
        check(
            "result_bundle_schema_is_complete",
            required_core_columns.issubset(core_schema)
            and len(core_schema) == 26
            and len(contract["schemas"]["v04_stress_results.csv"]) == 8
            and "replay the deterministic core and stress suite in memory"
            in contract.get("post_execution_verifier_behavior", ""),
            "The frozen output schema retains all prediction and abstention provenance.",
        ),
        check(
            "predecessor_execution_tag_is_preserved_without_output",
            protocol.get("execution_freeze_predecessor", {}).get("tag")
            == "v0.4.0-execution-freeze"
            and protocol.get("execution_freeze_predecessor", {}).get("commit")
            == "9f4660a88beef829e6c3cac72e0d59134b929add"
            and "no independently committed post-execution result verifier"
            in protocol.get("execution_freeze_predecessor", {}).get("disposition", "")
            and manifest.get("execution_freeze_predecessor", {}).get("tag")
            == "v0.4.0-execution-freeze",
            "The inadequate prior execution tag remains historical and was never run.",
        ),
        check(
            "replacement_execution_tag_is_new_and_unallocated_in_source",
            contract.get("execution_freeze_tag") == "v0.4.1-execution-freeze"
            and manifest.get("execution_freeze_tag") == "v0.4.1-execution-freeze",
            "A new execution tag is required after the verifier-inclusive freeze.",
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Tracked pre-execution result-verifier contract.",
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def build_bundle_checks(
    protocol: dict[str, Any],
    manifest: dict[str, Any],
    directory: Path,
    attempt_record: Path,
    expected_provenance: dict[str, Any],
    replayed_core: pd.DataFrame | None = None,
    replayed_thresholds: dict[str, Any] | None = None,
    replayed_stress: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    paths = output_paths(protocol, directory)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing or not attempt_record.is_file():
        return [
            check(
                "completed_result_bundle_exists",
                False,
                "Missing result files or durable attempt record: "
                + ", ".join(
                    [
                        *missing,
                        *([] if attempt_record.is_file() else [attempt_record.name]),
                    ]
                ),
            )
        ]
    if (
        replayed_core is None
        or replayed_thresholds is None
        or replayed_stress is None
    ):
        raise ValueError("Completed result validation requires an in-memory replay.")

    contract = protocol["output_contract"]
    receipt = json.loads(paths["v04_execution_receipt.json"].read_text(encoding="utf-8"))
    attempt = json.loads(attempt_record.read_text(encoding="utf-8"))
    core = pd.read_csv(paths["v04_core_event_results.csv"])
    stress = pd.read_csv(paths["v04_stress_results.csv"])
    thresholds = json.loads(paths["v04_core_thresholds.json"].read_text(encoding="utf-8"))
    metrics = json.loads(paths["v04_core_metrics.json"].read_text(encoding="utf-8"))
    bootstrap = json.loads(paths["v04_core_bootstrap.json"].read_text(encoding="utf-8"))
    payload_names = [
        name for name in contract["files"] if name != "v04_execution_receipt.json"
    ]
    expected_hashes = {name: sha256(paths[name]) for name in payload_names}
    expected_threshold = expected_thresholds(replayed_core, protocol)
    expected_summary = expected_metrics(replayed_core, expected_threshold)
    expected_bootstrap_result = expected_bootstrap(
        replayed_core, expected_threshold, protocol
    )
    expected_allowed_hashes = expected_provenance["allowed_input_hashes"]
    receipt_is_bound = (
        receipt.get("state") == "completed"
        and receipt.get("protocol_id") == protocol["protocol_id"]
        and receipt.get("protocol_freeze_tag") == contract["protocol_freeze_tag"]
        and receipt.get("execution_tag") == contract["execution_freeze_tag"]
        and receipt.get("execution_git_commit")
        == expected_provenance["execution_git_commit"]
        and receipt.get("remote_execution_tag_commit")
        == expected_provenance["execution_git_commit"]
        and receipt.get("protocol_sha256") == expected_provenance["protocol_sha256"]
        and receipt.get("execution_manifest_sha256")
        == expected_provenance["execution_manifest_sha256"]
        and receipt.get("allowed_input_hashes") == expected_allowed_hashes
        and receipt.get("output_hashes") == expected_hashes
        and receipt.get("failure_count") == 0
        and receipt.get("input_count_accounting", {}).get("failure_count") == 0
    )
    attempt_is_bound = (
        attempt.get("state") == "completed"
        and attempt.get("execution_receipt_sha256")
        == sha256(paths["v04_execution_receipt.json"])
        and attempt.get("execution_tag") == receipt.get("execution_tag")
        and attempt.get("execution_git_commit") == receipt.get("execution_git_commit")
        and attempt.get("protocol_sha256") == receipt.get("protocol_sha256")
        and attempt.get("execution_manifest_sha256")
        == receipt.get("execution_manifest_sha256")
    )
    expected_core_events = int(protocol["expected_accounting"]["core_events"]["total"])
    expected_stress_events = int(protocol["expected_accounting"]["stress_events"])
    return [
        check(
            "completed_result_bundle_exists",
            True,
            "Every declared payload, receipt, and durable attempt record exists.",
        ),
        check(
            "receipt_hashes_and_frozen_provenance",
            receipt_is_bound and attempt_is_bound,
            "Payload hashes, tagged commit, source hashes, and durable receipt linkage agree.",
        ),
        check(
            "complete_core_accounting_and_pair_contract",
            core_is_complete(core, protocol)
            and receipt.get("input_count_accounting", {}).get("core_event_count")
            == expected_core_events,
            "N/L/R counts, split isolation, pair structure, exact target identity, and schema hold.",
        ),
        check(
            "deterministic_core_and_stress_replay",
            frames_match(core, replayed_core, ["case_id"])
            and json_matches(thresholds, replayed_thresholds)
            and frames_match(
                stress, replayed_stress, ["component_id", "stress_family"]
            ),
            "Every stored core score, prediction, threshold, and stress diagnostic matches an in-memory replay.",
        ),
        check(
            "calibration_only_thresholds_and_predictions",
            json_matches(expected_threshold, thresholds)
            and predictions_match(core, replayed_core),
            "Thresholds are reproduced from calibration only and predict every stored row.",
        ),
        check(
            "evaluation_scope_risk_coverage_and_metrics",
            json_matches(expected_summary, metrics),
            "Forced and selective scope risk, coverage, abstentions, and event metrics recompute.",
        ),
        check(
            "component_bootstrap_intervals_and_validity",
            json_matches(expected_bootstrap_result, bootstrap),
            "Cluster bootstrap point values, intervals, statuses, and valid-repetition counts recompute.",
        ),
        check(
            "raw_scale_stress_bounds_and_accounting",
            stress_is_complete(stress, core, protocol)
            and receipt.get("input_count_accounting", {}).get("stress_event_count")
            == expected_stress_events,
            "Every stress family and component is present with a satisfied declared bound.",
        ),
        check(
            "forbidden_input_boundary",
            set(receipt.get("allowed_input_hashes", {}))
            == set(protocol["data_access"]["execution_input_allowlist"])
            and set(manifest.get("bound_input_sha256", {}))
            == set(expected_allowed_hashes).difference(
                {"configs/v04_identifiability_execution_manifest.json"}
            ),
            "The receipt lists exactly the frozen code/configuration allowlist and no external data.",
        ),
    ]


def build_result_report(
    protocol: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    directory: Path | None = None,
    attempt_record: Path | None = None,
    expected_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if protocol is None:
        protocol, manifest, expected_provenance = tagged_execution_authority()
    elif manifest is None:
        raise ValueError("A supplied protocol requires its corresponding manifest.")
    contract = protocol["output_contract"]
    if directory is None:
        directory = ROOT / str(contract["directory"])
    if attempt_record is None:
        attempt_record = ROOT / str(contract["attempt_record"])
    preflight = build_pre_execution_report(protocol, manifest)
    provenance_check = check(
        "annotated_remote_tag_and_source_blob_provenance",
        expected_provenance is not None,
        "Authority was loaded from the local annotated tag, matching peeled origin tag, and tagged blobs.",
    )
    paths = output_paths(protocol, directory)
    bundle_exists = all(path.is_file() for path in paths.values()) and attempt_record.is_file()
    if not bundle_exists:
        checks = [
            *preflight["checks"],
            *build_bundle_checks(
                protocol,
                manifest,
                directory,
                attempt_record,
                expected_provenance or {},
            ),
        ]
        return {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "state": "not_executed",
            "scope": "Post-execution v0.4 result validation.",
            "verification_output_path": contract[
                "post_execution_verification_path"
            ],
            "all_checks_passed": False,
            "checks": [provenance_check, *checks],
        }
    if expected_provenance is None:
        raise ValueError("A supplied protocol and manifest require tagged provenance.")
    replayed_core, replayed_thresholds, replayed_stress = replay_frozen_outputs(protocol)
    checks = [
        provenance_check,
        *preflight["checks"],
        *build_bundle_checks(
            protocol,
            manifest,
            directory,
            attempt_record,
            expected_provenance,
            replayed_core,
            replayed_thresholds,
            replayed_stress,
        ),
    ]
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "state": "completed",
        "scope": "Post-execution v0.4 result validation.",
        "verification_output_path": contract["post_execution_verification_path"],
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def main() -> None:
    args = parse_args()
    report = (
        build_result_report()
        if args.require_results
        else build_pre_execution_report()
    )
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
    elif args.require_results:
        output = ROOT / str(report["verification_output_path"])
    else:
        output = ROOT / "artifacts" / "v04_result_verifier_preflight.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
