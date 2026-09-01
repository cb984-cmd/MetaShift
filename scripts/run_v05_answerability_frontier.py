"""Run the one-time v0.5 synthetic scope-answerability experiment.

The entrypoint is deliberately data-free: it constructs bounded synthetic
panels in memory and can execute only from the separately tagged source state.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import importlib.metadata
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import traceback
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metashift.answerability import (
    policy_summary,
    select_confidence_cutoff,
    structural_certificate,
    structural_error_bound,
)
from metashift.metrics import select_macro_f1_threshold


PROTOCOL_RELATIVE_PATH = "configs/v05_answerability_protocol.json"
EXECUTION_MANIFEST_RELATIVE_PATH = "configs/v05_answerability_execution_manifest.json"
PROTOCOL_PATH = ROOT / PROTOCOL_RELATIVE_PATH
EXECUTION_MANIFEST_PATH = ROOT / EXECUTION_MANIFEST_RELATIVE_PATH
PRE_OUTCOME_VERIFIER_RELATIVE_PATH = "scripts/verify_v05_protocol_freeze.py"

ALPHAS = (0.01, 0.05, 0.10, 0.20)


@dataclass(frozen=True)
class SyntheticComponent:
    """One source-independent bounded base component."""

    split: str
    component_id: str
    component_index: int
    index: pd.DatetimeIndex
    common: np.ndarray
    target_unit_noise: np.ndarray
    donor_unit_noise: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the one-time v0.5 scope-answerability experiment."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute only from the matching annotated execution-freeze tag.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_sha256(path: Path) -> str:
    """Hash source as LF-normalized text, matching its Git blob bytes."""

    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def validate_runtime_environment(protocol: dict[str, Any]) -> dict[str, Any]:
    """Require the lockfile and active runtime recorded by the frozen protocol."""

    contract = protocol.get("runtime_environment", {})
    if platform.python_implementation() != contract.get("python_implementation"):
        raise RuntimeError("Python implementation differs from the frozen runtime.")
    if (
        sys.version_info.major != contract.get("python_major")
        or sys.version_info.minor != contract.get("python_minor")
    ):
        raise RuntimeError("Python major/minor version differs from the frozen runtime.")
    lock_relative = contract.get("requirements_lock")
    if not isinstance(lock_relative, str):
        raise ValueError("Runtime contract lacks a requirements lock path.")
    lock_path = project_path(lock_relative)
    if not lock_path.is_file():
        raise FileNotFoundError("Runtime requirements lock is absent.")
    expected_versions = contract.get("required_distribution_versions")
    if not isinstance(expected_versions, dict) or not expected_versions:
        raise ValueError("Runtime contract lacks required distribution versions.")
    lock_versions: dict[str, str] = {}
    for raw_line in lock_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.count("==") != 1:
            raise ValueError("requirements-lock.txt must contain exact package pins.")
        name, version = line.split("==", maxsplit=1)
        lock_versions[name] = version
    if lock_versions != expected_versions:
        raise RuntimeError("Runtime distribution contract differs from requirements-lock.txt.")
    actual_versions: dict[str, str] = {}
    for distribution, expected_version in expected_versions.items():
        try:
            actual_version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as error:
            raise RuntimeError(
                f"Frozen runtime distribution is not installed: {distribution}"
            ) from error
        if actual_version != expected_version:
            raise RuntimeError(
                f"Frozen runtime distribution version differs: {distribution}"
            )
        actual_versions[distribution] = actual_version
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_major": sys.version_info.major,
        "python_minor": sys.version_info.minor,
        "requirements_lock_sha256": source_sha256(lock_path),
        "distribution_versions": actual_versions,
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Write JSON atomically without accepting NaN as a serialized value."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode(
        "utf-8"
    )
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(encoded)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def write_csv_atomic(path: Path, frame: pd.DataFrame) -> None:
    """Write a complete CSV atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        frame.to_csv(temporary, index=False)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def project_path(relative_path: str) -> Path:
    """Resolve a protocol path only when it remains inside this repository."""

    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Protocol path must remain inside the repository: {relative_path}")
    resolved = (ROOT / path).resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise ValueError(f"Protocol path escapes the repository: {relative_path}")
    return resolved


def read_protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def read_execution_manifest() -> dict[str, Any]:
    return json.loads(EXECUTION_MANIFEST_PATH.read_text(encoding="utf-8"))


def _factor_name(specification: dict[str, Any]) -> str:
    name = specification.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Every grid specification must have a nonempty name.")
    return name


def grid_specifications(protocol: dict[str, Any]) -> list[dict[str, dict[str, Any]]]:
    """Materialize the declared Cartesian grid in its frozen factor order."""

    grid = protocol["full_cartesian_grid"]
    factor_order = grid["factor_order"]
    if not isinstance(factor_order, list) or not factor_order:
        raise ValueError("The grid must declare a nonempty factor order.")
    factor_values: list[list[dict[str, Any]]] = []
    for factor in factor_order:
        values = grid.get(factor)
        if not isinstance(values, list) or not values:
            raise ValueError(f"Grid factor {factor} is missing or empty.")
        if len({_factor_name(value) for value in values}) != len(values):
            raise ValueError(f"Grid factor {factor} has duplicate names.")
        factor_values.append(values)
    cells = [
        dict(zip(factor_order, combination, strict=True))
        for combination in itertools.product(*factor_values)
    ]
    if len(cells) != grid["cells_per_component"]:
        raise ValueError("Declared grid cell count does not match the Cartesian product.")
    return cells


def component_seed(protocol: dict[str, Any], split: str, index: int) -> int:
    panel = protocol["synthetic_panel"]
    if split not in panel["split_seed_offsets"]:
        raise ValueError(f"Unknown split: {split}")
    if index < 0:
        raise ValueError("component index cannot be negative.")
    return int(panel["base_seed"] + panel["split_seed_offsets"][split] + index)


def generate_component(
    protocol: dict[str, Any], split: str, component_index: int
) -> SyntheticComponent:
    """Construct one bounded base process without scope or grid outcomes."""

    panel = protocol["synthetic_panel"]
    generator = panel["analysis_scale_generator"]
    days = int(panel["days"])
    donor_count = int(panel["donor_count"])
    start = pd.Timestamp(panel["start_date"])
    index = pd.date_range(start, periods=days, freq="D")
    rng = np.random.default_rng(component_seed(protocol, split, component_index))
    innovation_half_width = float(generator["common_innovation_half_width"])
    rho = float(generator["common_ar1_coefficient"])
    if not 0.0 <= rho < 1.0 or innovation_half_width <= 0.0:
        raise ValueError("The bounded common-process parameters are invalid.")
    common = np.empty(days, dtype=float)
    common[0] = rng.uniform(
        -innovation_half_width / (1.0 - rho),
        innovation_half_width / (1.0 - rho),
    )
    for date_index in range(1, days):
        common[date_index] = (
            rho * common[date_index - 1]
            + rng.uniform(-innovation_half_width, innovation_half_width)
        )
    target_unit_noise = rng.uniform(-1.0, 1.0, days)
    donor_unit_noise = rng.uniform(-1.0, 1.0, (days, donor_count))
    component_id = str(panel["component_id_template"]).format(
        split=split, index=component_index
    )
    return SyntheticComponent(
        split=split,
        component_id=component_id,
        component_index=component_index,
        index=index,
        common=common,
        target_unit_noise=target_unit_noise,
        donor_unit_noise=donor_unit_noise,
    )


def _post_mask(protocol: dict[str, Any]) -> np.ndarray:
    panel = protocol["synthetic_panel"]
    days = int(panel["days"])
    anchor = int(panel["anchor_day_index"])
    if not 0 < anchor < days:
        raise ValueError("anchor_day_index must lie inside the synthetic panel.")
    return np.arange(days) >= anchor


def _score_indices(protocol: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    panel = protocol["synthetic_panel"]
    estimator = protocol["estimator"]
    anchor = int(panel["anchor_day_index"])
    comparison_days = int(estimator["comparison_days"])
    pre = np.arange(anchor - comparison_days, anchor)
    post = np.arange(anchor, anchor + comparison_days)
    days = int(panel["days"])
    if pre.min(initial=0) < 0 or post.max(initial=-1) >= days:
        raise ValueError("The declared score windows leave the synthetic panel.")
    return pre, post


def availability_mask(
    protocol: dict[str, Any],
    component: SyntheticComponent,
    availability: dict[str, Any],
) -> np.ndarray:
    """Return the arm-invariant donor availability matrix for one component."""

    days = int(protocol["synthetic_panel"]["days"])
    donors = int(protocol["synthetic_panel"]["donor_count"])
    name = _factor_name(availability)
    mask = np.ones((days, donors), dtype=bool)
    if name == "complete":
        return mask
    if name != "rotating_one_missing":
        raise ValueError(f"Unsupported availability condition: {name}")
    missing = (component.component_index + np.arange(days)) % donors
    mask[np.arange(days), missing] = False
    return mask


def _noise_amplitudes(
    protocol: dict[str, Any], noise: dict[str, Any]
) -> np.ndarray:
    pre_width = float(noise["pre_half_width"])
    post_width = float(noise["post_half_width"])
    if min(pre_width, post_width) < 0.0:
        raise ValueError("bounded noise widths must be nonnegative.")
    result = np.full(int(protocol["synthetic_panel"]["days"]), pre_width)
    result[_post_mask(protocol)] = post_width
    return result


def base_analysis_scale_paths(
    protocol: dict[str, Any],
    component: SyntheticComponent,
    mismatch: dict[str, Any],
    noise: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Build bounded target and donor paths before scope injection."""

    generator = protocol["synthetic_panel"]["analysis_scale_generator"]
    mean = float(generator["mean"])
    minimum = float(generator["minimum_analysis_scale"])
    amplitudes = _noise_amplitudes(protocol, noise)
    maximum_offset = float(mismatch["maximum_absolute_offset"])
    multipliers = np.asarray(mismatch["offset_multipliers"], dtype=float)
    donors = int(protocol["synthetic_panel"]["donor_count"])
    if multipliers.shape != (donors,):
        raise ValueError("Donor mismatch offsets must match the donor count.")
    if not np.isfinite(multipliers).all() or np.abs(multipliers).max() > 1.0:
        raise ValueError("Donor mismatch multipliers must be finite values in [-1, 1].")
    target = mean + component.common + component.target_unit_noise * amplitudes
    donor_paths = (
        mean
        + component.common[:, np.newaxis]
        + component.donor_unit_noise * amplitudes[:, np.newaxis]
        + maximum_offset * multipliers[np.newaxis, :]
    )
    if target.min() < minimum or donor_paths.min() < minimum:
        raise ValueError("The bounded source process violates its positive-scale contract.")
    return target, donor_paths


def _contamination_vector(
    component: SyntheticComponent,
    contamination: dict[str, Any],
    protocol: dict[str, Any],
) -> np.ndarray:
    magnitude = float(contamination["maximum_log_scale_shift"])
    donors = int(protocol["synthetic_panel"]["donor_count"])
    values = np.zeros((int(protocol["synthetic_panel"]["days"]), donors), dtype=float)
    if magnitude == 0.0:
        return values
    name = _factor_name(contamination)
    if name != "one_donor_bounded":
        raise ValueError(f"Unsupported contamination condition: {name}")
    digest = hashlib.sha256(component.component_id.encode("utf-8")).digest()
    sign = 1.0 if digest[0] & 1 else -1.0
    donor_index = (component.component_index + 1) % donors
    values[_post_mask(protocol), donor_index] = sign * magnitude
    return values


def _normalize_weights(mask: np.ndarray, weights: np.ndarray) -> np.ndarray:
    if mask.ndim != 2 or weights.ndim != 1 or mask.shape[1] != weights.size:
        raise ValueError("Availability and donor weights are incompatible.")
    raw = mask.astype(float) * weights[np.newaxis, :]
    totals = raw.sum(axis=1)
    if (totals <= 0.0).any():
        raise ValueError("At least one donor must be available on every date.")
    return raw / totals[:, np.newaxis]


def _target_digest(index: pd.DatetimeIndex, values: np.ndarray) -> str:
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Target digest requires one finite raw target path.")
    payload = (
        index.asi8.astype("<i8", copy=False).tobytes()
        + values.astype("<f8", copy=False).tobytes()
    )
    return sha256_bytes(payload)


def _apply_raw_field(
    raw_target: np.ndarray,
    raw_donors: np.ndarray,
    protocol: dict[str, Any],
    raw_field: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    magnitude = float(raw_field["post_anchor_raw_additive_magnitude"])
    if not np.isfinite(magnitude) or magnitude < 0.0:
        raise ValueError("Raw field magnitude must be finite and nonnegative.")
    target = raw_target.copy()
    donors = raw_donors.copy()
    if magnitude:
        post = _post_mask(protocol)
        target[post] += magnitude
        donors[post] += magnitude
    return target, donors


def _raw_additive_bound(
    target_before_field: np.ndarray,
    donors_before_field: np.ndarray,
    normalized_weights: np.ndarray,
    post_indices: np.ndarray,
    magnitude: float,
) -> float:
    """Vectorized counterpart of the declared raw-additive leakage envelope."""

    if magnitude == 0.0:
        return 0.0
    target = target_before_field[post_indices]
    donors = donors_before_field[post_indices]
    weights = normalized_weights[post_indices]
    available = weights > 0.0
    lower = np.minimum(
        target,
        np.where(available, donors, np.inf).min(axis=1),
    )
    if not np.isfinite(lower).all() or (lower < 0.0).any():
        raise ValueError("Raw leakage bound requires finite nonnegative values.")
    constants = magnitude / ((1.0 + lower + magnitude) * (1.0 + lower))
    mismatch = np.abs(target[:, np.newaxis] - donors)
    result = float(
        np.mean(constants * np.sum(np.where(available, weights * mismatch, 0.0), axis=1))
    )
    if not np.isfinite(result) or result < 0.0:
        raise ValueError("Raw leakage bound must be finite and nonnegative.")
    return result


def _score_from_arrays(
    target_log: np.ndarray,
    donor_log: np.ndarray,
    normalized_weights: np.ndarray,
    pre_indices: np.ndarray,
    post_indices: np.ndarray,
) -> float:
    donor_composite = np.sum(
        np.where(normalized_weights > 0.0, normalized_weights * donor_log, 0.0),
        axis=1,
    )
    residual = target_log - donor_composite
    score = float(residual[post_indices].mean() - residual[pre_indices].mean())
    if not np.isfinite(score):
        raise ValueError("Scope score must be finite.")
    return score


def _prediction_name(prediction_is_local: bool | None) -> str:
    if prediction_is_local is None:
        return "abstain"
    return "local" if prediction_is_local else "shared"


def _truth_column_values() -> tuple[np.ndarray, np.ndarray]:
    return np.array([True, False]), np.array(["local", "shared"], dtype=object)


def _score_threshold_prediction(score: float, threshold: float) -> str:
    if not np.isfinite(score) or not np.isfinite(threshold):
        raise ValueError("Score and threshold must be finite.")
    return "local" if score >= threshold else "shared"


def _grid_id(protocol: dict[str, Any], cell: dict[str, dict[str, Any]]) -> str:
    return "|".join(
        f"{factor}={_factor_name(cell[factor])}"
        for factor in protocol["full_cartesian_grid"]["factor_order"]
    )


def _target_group_id(
    component: SyntheticComponent,
    signal: dict[str, Any],
    raw_field: dict[str, Any],
    noise: dict[str, Any],
) -> str:
    return (
        f"{component.split}:{component.component_id}:"
        f"{_factor_name(signal)}:{_factor_name(raw_field)}:{_factor_name(noise)}"
    )


def rows_for_component(
    protocol: dict[str, Any],
    component: SyntheticComponent,
    execution_tag: str,
) -> list[dict[str, Any]]:
    """Generate all 640 target-fixed scope pairs for one component in memory."""

    estimator = protocol["estimator"]
    grid = grid_specifications(protocol)
    pre_indices, post_indices = _score_indices(protocol)
    post_mask = _post_mask(protocol)
    weights = np.asarray(estimator["donor_weights"], dtype=float)
    if not np.isclose(weights.sum(), 1.0, rtol=0.0, atol=1e-12):
        raise ValueError("Fixed donor weights must sum to one.")
    if (weights < 0.0).any():
        raise ValueError("Fixed donor weights must be nonnegative.")
    expected_rows = int(protocol["full_cartesian_grid"]["cells_per_component"])
    rows: list[dict[str, Any]] = []
    target_cache: dict[tuple[str, str, str], tuple[np.ndarray, str]] = {}
    normalized_cache: dict[str, np.ndarray] = {}
    availability_cache: dict[str, np.ndarray] = {}

    for cell in grid:
        q_spec = cell["nominal_donor_participation"]
        signal = cell["signal_h"]
        mismatch = cell["donor_mismatch"]
        availability = cell["availability"]
        contamination = cell["donor_contamination"]
        raw_field = cell["raw_scale_field"]
        noise = cell["bounded_noise"]
        q_name = _factor_name(q_spec)
        signal_name = _factor_name(signal)
        mismatch_name = _factor_name(mismatch)
        availability_name = _factor_name(availability)
        contamination_name = _factor_name(contamination)
        raw_name = _factor_name(raw_field)
        noise_name = _factor_name(noise)
        h = float(signal["value"])
        if not np.isfinite(h) or h <= 0.0:
            raise ValueError("Signal H must be finite and positive.")
        lambdas = np.asarray(q_spec["donor_participation"], dtype=float)
        if lambdas.shape != weights.shape or (lambdas < 0.0).any() or (lambdas > 1.0).any():
            raise ValueError("Donor participation must match donors and lie in [0, 1].")
        nominal_q = float(q_spec["value"])
        if not np.isclose(float(lambdas.mean()), nominal_q, rtol=0.0, atol=1e-12):
            raise ValueError("Nominal q must equal the mean declared donor participation.")

        if availability_name not in availability_cache:
            availability_cache[availability_name] = availability_mask(
                protocol, component, availability
            )
            minimum_available = availability_cache[availability_name].sum(axis=1).min()
            if minimum_available < int(estimator["minimum_available_donors"]):
                raise ValueError("Availability condition violates the donor minimum.")
        mask = availability_cache[availability_name]
        if availability_name not in normalized_cache:
            normalized_cache[availability_name] = _normalize_weights(mask, weights)
        normalized = normalized_cache[availability_name]

        target_base, donor_base = base_analysis_scale_paths(
            protocol, component, mismatch, noise
        )
        target_key = (signal_name, raw_name, noise_name)
        if target_key in target_cache:
            target_raw, target_hash = target_cache[target_key]
        else:
            target_before_raw = np.expm1(target_base + post_mask.astype(float) * h)
            target_raw, _ = _apply_raw_field(
                target_before_raw,
                np.zeros((len(component.index), len(weights)), dtype=float),
                protocol,
                raw_field,
            )
            target_hash = _target_digest(component.index, target_raw)
            target_cache[target_key] = (target_raw, target_hash)

        local_before_raw = np.where(mask, np.expm1(donor_base), np.nan)
        shared_before_raw = np.where(
            mask,
            np.expm1(
                donor_base + post_mask[:, np.newaxis] * h * lambdas[np.newaxis, :]
            ),
            np.nan,
        )
        if (lambdas == 0.0).all():
            shared_before_raw = local_before_raw.copy()
        _, local_after_field = _apply_raw_field(
            np.zeros(len(component.index), dtype=float),
            local_before_raw,
            protocol,
            raw_field,
        )
        _, shared_after_field = _apply_raw_field(
            np.zeros(len(component.index), dtype=float),
            shared_before_raw,
            protocol,
            raw_field,
        )
        contamination_values = _contamination_vector(component, contamination, protocol)
        local_log = np.log1p(local_after_field) + contamination_values
        shared_log = np.log1p(shared_after_field) + contamination_values
        if (lambdas == 0.0).all():
            shared_log = local_log.copy()
        target_log = np.log1p(target_raw)
        local_score = _score_from_arrays(
            target_log, local_log, normalized, pre_indices, post_indices
        )
        shared_score = _score_from_arrays(
            target_log, shared_log, normalized, pre_indices, post_indices
        )
        effective_q = np.sum(normalized * lambdas[np.newaxis, :], axis=1)
        q_post = effective_q[post_indices]
        h_min = float(np.min(np.full(post_indices.size, h)))
        q_min = float(q_post.min())
        realized_gap = float(np.mean(q_post * h))
        local_without_contamination = _score_from_arrays(
            target_log,
            local_log - contamination_values,
            normalized,
            pre_indices,
            post_indices,
        )
        shared_without_contamination = _score_from_arrays(
            target_log,
            shared_log - contamination_values,
            normalized,
            pre_indices,
            post_indices,
        )
        if not np.isclose(
            local_score - shared_score,
            local_without_contamination - shared_without_contamination,
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError("Shared donor contamination must not alter paired separation.")

        raw_magnitude = float(raw_field["post_anchor_raw_additive_magnitude"])
        local_raw_bound = _raw_additive_bound(
            target_raw - post_mask.astype(float) * raw_magnitude,
            local_before_raw,
            normalized,
            post_indices,
            raw_magnitude,
        )
        shared_raw_bound = _raw_additive_bound(
            target_raw - post_mask.astype(float) * raw_magnitude,
            shared_before_raw,
            normalized,
            post_indices,
            raw_magnitude,
        )
        base_bound = 2.0 * float(mismatch["maximum_absolute_offset"]) + 2.0 * (
            float(noise["pre_half_width"]) + float(noise["post_half_width"])
        )
        contamination_bound = float(contamination["maximum_log_scale_shift"])
        local_error_bound = structural_error_bound(
            maximum_absolute_donor_offset=float(
                mismatch["maximum_absolute_offset"]
            ),
            pre_noise_half_width=float(noise["pre_half_width"]),
            post_noise_half_width=float(noise["post_half_width"]),
            raw_error_bound=local_raw_bound,
            contamination_error_bound=contamination_bound,
        )
        shared_error_bound = structural_error_bound(
            maximum_absolute_donor_offset=float(
                mismatch["maximum_absolute_offset"]
            ),
            pre_noise_half_width=float(noise["pre_half_width"]),
            post_noise_half_width=float(noise["post_half_width"]),
            raw_error_bound=shared_raw_bound,
            contamination_error_bound=contamination_bound,
        )
        lower_gap = q_min * h_min
        local_envelope_satisfied = bool(
            abs(local_score - h) <= local_error_bound + 1e-12
        )
        shared_envelope_satisfied = bool(
            abs(shared_score - (h - realized_gap)) <= shared_error_bound + 1e-12
        )
        envelope_contract_valid = (
            local_envelope_satisfied and shared_envelope_satisfied
        )
        local_certificate = structural_certificate(
            score=local_score,
            signal_h=h,
            gap_lower_bound=lower_gap,
            local_error_bound=local_error_bound,
            shared_error_bound=shared_error_bound,
        )
        shared_certificate = structural_certificate(
            score=shared_score,
            signal_h=h,
            gap_lower_bound=lower_gap,
            local_error_bound=local_error_bound,
            shared_error_bound=shared_error_bound,
        )
        if local_certificate.answered != shared_certificate.answered:
            raise ValueError("A pair must have one shared certificate answer state.")
        local_oracle = structural_certificate(
            score=local_score,
            signal_h=h,
            gap_lower_bound=realized_gap,
            local_error_bound=local_error_bound,
            shared_error_bound=shared_error_bound,
        )
        shared_oracle = structural_certificate(
            score=shared_score,
            signal_h=h,
            gap_lower_bound=realized_gap,
            local_error_bound=local_error_bound,
            shared_error_bound=shared_error_bound,
        )
        if local_oracle.answered != shared_oracle.answered:
            raise ValueError("A pair must have one shared oracle answer state.")
        q_zero_identity = bool(
            (lambdas == 0.0).all()
            and np.array_equal(local_log, shared_log, equal_nan=True)
            and local_score == shared_score
        )
        if nominal_q == 0.0 and not q_zero_identity:
            raise ValueError("The q=0 comparative negative control lost observation identity.")
        pair_id = (
            f"{protocol['protocol_id']}:{component.split}:{component.component_id}:"
            f"{_grid_id(protocol, cell)}"
        )
        rows.append(
            {
                "protocol_id": protocol["protocol_id"],
                "execution_tag": execution_tag,
                "split": component.split,
                "component_id": component.component_id,
                "component_index": component.component_index,
                "grid_id": _grid_id(protocol, cell),
                "pair_id": pair_id,
                "target_group_id": _target_group_id(
                    component, signal, raw_field, noise
                ),
                "nominal_q_name": q_name,
                "nominal_q": nominal_q,
                "signal_h_name": signal_name,
                "signal_h": h,
                "donor_mismatch_name": mismatch_name,
                "donor_mismatch_bound": float(
                    mismatch["maximum_absolute_offset"]
                ),
                "availability_name": availability_name,
                "contamination_name": contamination_name,
                "contamination_bound": contamination_bound,
                "raw_field_name": raw_name,
                "raw_field_magnitude": raw_magnitude,
                "noise_name": noise_name,
                "pre_noise_bound": float(noise["pre_half_width"]),
                "post_noise_bound": float(noise["post_half_width"]),
                "local_target_sha256": target_hash,
                "shared_target_sha256": target_hash,
                "target_identity": True,
                "comparative_observation_identity": q_zero_identity,
                "local_score": local_score,
                "shared_score": shared_score,
                "q_effective_mean": float(q_post.mean()),
                "q_effective_min": q_min,
                "h_min": h_min,
                "realized_gap": realized_gap,
                "base_error_bound": base_bound,
                "local_raw_error_bound": local_raw_bound,
                "shared_raw_error_bound": shared_raw_bound,
                "local_error_bound": local_error_bound,
                "shared_error_bound": shared_error_bound,
                "structural_margin": local_certificate.structural_margin,
                "certificate_threshold": local_certificate.threshold,
                "oracle_structural_margin": local_oracle.structural_margin,
                "oracle_threshold": local_oracle.threshold,
                "certificate_answered": (
                    local_certificate.answered and envelope_contract_valid
                ),
                "certificate_abstention_reason": (
                    "answered"
                    if local_certificate.answered and envelope_contract_valid
                    else (
                        "envelope_violation"
                        if not envelope_contract_valid
                        else (
                            "q0_observational_identity"
                            if nominal_q == 0.0
                            else "nonpositive_structural_margin"
                        )
                    )
                ),
                "certificate_local_prediction": _prediction_name(
                    (
                        local_certificate.predicts_local
                        if envelope_contract_valid
                        else None
                    )
                ),
                "certificate_shared_prediction": _prediction_name(
                    (
                        shared_certificate.predicts_local
                        if envelope_contract_valid
                        else None
                    )
                ),
                "oracle_answerable": local_oracle.answered and envelope_contract_valid,
                "local_envelope_satisfied": local_envelope_satisfied,
                "shared_envelope_satisfied": shared_envelope_satisfied,
            }
        )
    if len(rows) != expected_rows:
        raise ValueError("Component row count does not match the frozen grid.")
    return rows


def generate_pair_results(
    protocol: dict[str, Any], split: str, execution_tag: str
) -> pd.DataFrame:
    """Generate one split's complete in-memory pair table."""

    if split not in protocol["synthetic_panel"]["component_counts"]:
        raise ValueError(f"Unknown split: {split}")
    rows: list[dict[str, Any]] = []
    for component_index in range(
        int(protocol["synthetic_panel"]["component_counts"][split])
    ):
        component = generate_component(protocol, split, component_index)
        rows.extend(rows_for_component(protocol, component, execution_tag))
    frame = pd.DataFrame(rows)
    expected = int(protocol["expected_accounting"]["pair_rows"][split])
    if len(frame) != expected:
        raise ValueError("Observed pair-row accounting does not match the protocol.")
    if frame["pair_id"].duplicated().any():
        raise ValueError("Every generated matched pair must have a unique pair identifier.")
    return frame


def _require_split(frame: pd.DataFrame, split: str) -> None:
    observed = set(frame["split"].astype(str))
    if observed != {split}:
        raise ValueError(f"This operation requires only {split} rows, got {observed}.")


def _event_vectors(
    frame: pd.DataFrame, prediction_prefix: str, answered_prefix: str | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Expand a pair table to ordered local/shared event vectors."""

    local_predictions = frame[f"{prediction_prefix}_local_prediction"].to_numpy(
        dtype=object
    )
    shared_predictions = frame[f"{prediction_prefix}_shared_prediction"].to_numpy(
        dtype=object
    )
    predictions = np.concatenate(
        [local_predictions == "local", shared_predictions == "local"]
    )
    labels = np.concatenate(
        [
            np.ones(len(frame), dtype=bool),
            np.zeros(len(frame), dtype=bool),
        ]
    )
    if answered_prefix is None:
        answered = np.ones(labels.shape, dtype=bool)
    elif answered_prefix == "certificate":
        pair_answered = frame["certificate_answered"].to_numpy(dtype=bool)
        answered = np.concatenate([pair_answered, pair_answered])
    else:
        answered = np.concatenate(
            [
                frame[f"{answered_prefix}_local_answered"].to_numpy(dtype=bool),
                frame[f"{answered_prefix}_shared_answered"].to_numpy(dtype=bool),
            ]
        )
    components = np.concatenate(
        [frame["component_id"].to_numpy(dtype=object)] * 2
    )
    return labels, predictions, answered, components


def calibration_policies(
    calibration: pd.DataFrame, protocol: dict[str, Any]
) -> dict[str, Any]:
    """Fit every predeclared threshold using calibration rows only."""

    _require_split(calibration, "calibration")
    scores = np.concatenate(
        [
            calibration["local_score"].to_numpy(dtype=float),
            calibration["shared_score"].to_numpy(dtype=float),
        ]
    )
    labels = np.concatenate(
        [
            np.ones(len(calibration), dtype=bool),
            np.zeros(len(calibration), dtype=bool),
        ]
    )
    if not np.isfinite(scores).all():
        raise ValueError("Calibration scope scores must be finite.")
    threshold = select_macro_f1_threshold(labels.astype(int), scores)
    quantile_count = int(protocol["calibration_and_evaluation"]["cutoff_quantiles"]["count"])
    selected: dict[str, dict[str, Any]] = {}
    for alpha in ALPHAS:
        cutoff = select_confidence_cutoff(
            labels, scores, threshold, alpha, quantile_count=quantile_count
        )
        selected[_alpha_token(alpha)] = {
            "alpha": cutoff.alpha,
            "cutoff": cutoff.cutoff if np.isfinite(cutoff.cutoff) else None,
            "calibration_coverage": cutoff.calibration_coverage,
            "calibration_conditional_error": cutoff.calibration_conditional_error,
            "status": cutoff.status,
        }
    return {
        "protocol_id": protocol["protocol_id"],
        "selection_split": "calibration",
        "comparative_scope_threshold": float(threshold),
        "confidence_cutoffs": selected,
    }


def _alpha_token(alpha: float) -> str:
    return f"{alpha:.2f}".replace(".", "_")


def apply_policies(
    frame: pd.DataFrame, policies: dict[str, Any], protocol: dict[str, Any]
) -> pd.DataFrame:
    """Apply precomputed threshold policies without fitting on this frame."""

    threshold = float(policies["comparative_scope_threshold"])
    if not np.isfinite(threshold):
        raise ValueError("A finite calibration threshold is required.")
    result = frame.copy()
    result["target_only_local_prediction"] = "local"
    result["target_only_shared_prediction"] = "local"
    result["comparative_local_prediction"] = np.where(
        result["local_score"].to_numpy(dtype=float) >= threshold, "local", "shared"
    )
    result["comparative_shared_prediction"] = np.where(
        result["shared_score"].to_numpy(dtype=float) >= threshold, "local", "shared"
    )
    for alpha in ALPHAS:
        token = _alpha_token(alpha)
        selected_cutoff = policies["confidence_cutoffs"][token]["cutoff"]
        cutoff = float("inf") if selected_cutoff is None else float(selected_cutoff)
        local_confidence = np.abs(result["local_score"].to_numpy(dtype=float) - threshold)
        shared_confidence = np.abs(
            result["shared_score"].to_numpy(dtype=float) - threshold
        )
        result[f"confidence_alpha_{token}_local_answered"] = local_confidence >= cutoff
        result[f"confidence_alpha_{token}_shared_answered"] = (
            shared_confidence >= cutoff
        )
        result[f"confidence_alpha_{token}_local_prediction"] = result[
            "comparative_local_prediction"
        ]
        result[f"confidence_alpha_{token}_shared_prediction"] = result[
            "comparative_shared_prediction"
        ]
    _validate_pair_result_schema(result, protocol, before_policies=False)
    return result


def _pair_events(
    frame: pd.DataFrame, prediction_prefix: str, answered_prefix: str | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels, predictions, answered, _ = _event_vectors(
        frame, prediction_prefix, answered_prefix
    )
    return labels, predictions, answered


def policy_metrics(
    frame: pd.DataFrame,
    protocol: dict[str, Any],
    *,
    groups: list[tuple[str, str, Callable[[pd.DataFrame], pd.Series]]] | None = None,
) -> pd.DataFrame:
    """Report every fixed policy for all prespecified aggregation groups."""

    if groups is None:
        groups = reporting_groups(frame)
    rows: list[dict[str, Any]] = []
    policy_specs: list[tuple[str, str, str | None, float | None]] = [
        ("target_only_forced", "target_only", None, None),
        ("comparative_forced", "comparative", None, None),
        ("certificate_selective", "certificate", "certificate", None),
    ]
    for alpha in ALPHAS:
        policy_specs.append(
            (
                "confidence_selective",
                f"confidence_alpha_{_alpha_token(alpha)}",
                f"confidence_alpha_{_alpha_token(alpha)}",
                alpha,
            )
        )
    for group_type, group_value, predicate in groups:
        selected = frame.loc[predicate(frame)]
        if selected.empty:
            raise ValueError(f"Declared group {group_type}={group_value} is empty.")
        for policy, prefix, answered_prefix, alpha in policy_specs:
            labels, predictions, answered = _pair_events(
                selected, prefix, answered_prefix
            )
            summary = policy_summary(labels, predictions, answered)
            rows.append(
                {
                    "split": str(selected["split"].iloc[0]),
                    "group_type": group_type,
                    "group_value": group_value,
                    "policy": policy,
                    "alpha": alpha,
                    **summary,
                }
            )
    return pd.DataFrame(rows)


def reporting_groups(
    frame: pd.DataFrame,
) -> list[tuple[str, str, Callable[[pd.DataFrame], pd.Series]]]:
    """Return the complete predeclared overall and one-factor report groups."""

    groups: list[tuple[str, str, Callable[[pd.DataFrame], pd.Series]]] = [
        ("overall", "all", lambda data: pd.Series(True, index=data.index))
    ]
    columns = [
        ("nominal_q", "nominal_q_name"),
        ("signal_h", "signal_h_name"),
        ("donor_mismatch", "donor_mismatch_name"),
        ("availability", "availability_name"),
        ("contamination", "contamination_name"),
        ("raw_field", "raw_field_name"),
        ("bounded_noise", "noise_name"),
    ]
    for group_type, column in columns:
        for value in sorted(frame[column].astype(str).unique()):
            groups.append(
                (
                    group_type,
                    value,
                    lambda data, column=column, value=value: data[column].astype(str)
                    == value,
                )
            )
    return groups


def _summary_lookup(
    metrics: pd.DataFrame,
    group_type: str,
    group_value: str,
    policy: str,
    alpha: float | None,
) -> dict[str, Any]:
    candidate = metrics.loc[
        (metrics["group_type"] == group_type)
        & (metrics["group_value"] == group_value)
        & (metrics["policy"] == policy)
        & (
            metrics["alpha"].isna()
            if alpha is None
            else np.isclose(metrics["alpha"].astype(float), alpha)
        )
    ]
    if len(candidate) != 1:
        raise ValueError("Every policy/group summary must occur exactly once.")
    return candidate.iloc[0].to_dict()


def answerability_frontier(
    evaluation_metrics: pd.DataFrame,
    protocol: dict[str, Any],
) -> pd.DataFrame:
    """Compute the held-out finite-policy frontier without changing any policy."""

    rows: list[dict[str, Any]] = []
    group_pairs = evaluation_metrics.loc[:, ["group_type", "group_value"]].drop_duplicates()
    for group_type, group_value in group_pairs.itertuples(index=False):
        target = _summary_lookup(
            evaluation_metrics, group_type, group_value, "target_only_forced", None
        )
        forced = _summary_lookup(
            evaluation_metrics, group_type, group_value, "comparative_forced", None
        )
        certificate = _summary_lookup(
            evaluation_metrics,
            group_type,
            group_value,
            "certificate_selective",
            None,
        )
        for alpha in ALPHAS:
            confidence_candidates = [
                (
                    (
                        "confidence_selective"
                        f"@calibration_alpha={calibration_alpha:.2f}"
                    ),
                    _summary_lookup(
                        evaluation_metrics,
                        group_type,
                        group_value,
                        "confidence_selective",
                        calibration_alpha,
                    ),
                )
                for calibration_alpha in ALPHAS
            ]
            channel_candidates = {
                "target_only": [("target_only_forced", target)],
                "comparative": [
                    ("comparative_forced", forced),
                    *confidence_candidates,
                ],
                "comparative_plus_synthetic_design_information": [
                    ("certificate_selective", certificate)
                ],
            }
            for channel, candidates in channel_candidates.items():
                qualifying: list[tuple[str, dict[str, Any]]] = []
                for policy_name, summary in candidates:
                    risk = summary["conditional_error"]
                    if risk is not None and float(risk) <= alpha:
                        qualifying.append((policy_name, summary))
                if not qualifying:
                    rows.append(
                        {
                            "split": "evaluation",
                            "group_type": group_type,
                            "group_value": group_value,
                            "alpha": alpha,
                            "channel": channel,
                            "frontier_coverage": 0.0,
                            "frontier_conditional_error": None,
                            "qualifying_policies": "",
                            "candidate_policy_count": len(candidates),
                            "status": "no_positive_coverage_qualifying_policy",
                        }
                    )
                    continue
                maximum_coverage = max(
                    float(summary["coverage"]) for _, summary in qualifying
                )
                frontier_policies = [
                    (name, summary)
                    for name, summary in qualifying
                    if np.isclose(float(summary["coverage"]), maximum_coverage)
                ]
                rows.append(
                    {
                        "split": "evaluation",
                        "group_type": group_type,
                        "group_value": group_value,
                        "alpha": alpha,
                        "channel": channel,
                        "frontier_coverage": maximum_coverage,
                        "frontier_conditional_error": min(
                            float(summary["conditional_error"])
                            for _, summary in frontier_policies
                        ),
                        "qualifying_policies": "|".join(
                            name for name, _ in frontier_policies
                        ),
                        "candidate_policy_count": len(candidates),
                        "status": "complete",
                    }
                )
    return pd.DataFrame(rows)


def certificate_validity(
    frame: pd.DataFrame,
    *,
    groups: list[tuple[str, str, Callable[[pd.DataFrame], pd.Series]]] | None = None,
) -> pd.DataFrame:
    """Summarize answer, violation, and oracle-efficiency outcomes for certificates."""

    if groups is None:
        groups = reporting_groups(frame)
    rows: list[dict[str, Any]] = []
    for group_type, group_value, predicate in groups:
        selected = frame.loc[predicate(frame)]
        certificate_events = _pair_events(
            selected, "certificate", "certificate"
        )
        labels, predictions, answered = certificate_events
        answered_events = int(answered.sum())
        error_events = int((predictions[answered] != labels[answered]).sum())
        violations = int(
            (~selected["local_envelope_satisfied"].to_numpy(dtype=bool)).sum()
            + (~selected["shared_envelope_satisfied"].to_numpy(dtype=bool)).sum()
        )
        certificate_pairs = int(selected["certificate_answered"].sum())
        oracle_pairs = int(selected["oracle_answerable"].sum())
        q0_pairs = int(
            selected.loc[
                selected["nominal_q"] == 0.0, "certificate_answered"
            ].sum()
        )
        if oracle_pairs:
            efficiency: float | None = certificate_pairs / oracle_pairs
        else:
            efficiency = None
        rows.append(
            {
                "split": str(selected["split"].iloc[0]),
                "group_type": group_type,
                "group_value": group_value,
                "total_pair_rows": int(len(selected)),
                "certificate_answered_pair_rows": certificate_pairs,
                "certificate_pair_coverage": certificate_pairs / len(selected),
                "certificate_error_events": error_events,
                "certificate_answered_events": answered_events,
                "certificate_conditional_error": (
                    error_events / answered_events if answered_events else None
                ),
                "envelope_violating_events": violations,
                "envelope_violation_rate": violations / (2 * len(selected)),
                "oracle_answerable_pair_rows": oracle_pairs,
                "certificate_efficiency": efficiency,
                "q0_certificate_answered_pair_rows": q0_pairs,
                "status": (
                    "certificate_contract_violation"
                    if violations
                    else (
                        "no_oracle_answerable_pairs"
                        if oracle_pairs == 0
                        else "complete"
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def failure_mode_map(frame: pd.DataFrame) -> pd.DataFrame:
    """Report every frozen grid cell, including unfavorable modes."""

    rows: list[dict[str, Any]] = []
    group_columns = [
        "split",
        "grid_id",
        "nominal_q_name",
        "signal_h_name",
        "donor_mismatch_name",
        "availability_name",
        "contamination_name",
        "raw_field_name",
        "noise_name",
    ]
    for values, selected in frame.groupby(group_columns, sort=True, dropna=False):
        (
            split,
            grid_id,
            q_name,
            signal_name,
            mismatch_name,
            availability_name,
            contamination_name,
            raw_name,
            noise_name,
        ) = values
        labels, predictions, answered = _pair_events(
            selected, "certificate", "certificate"
        )
        comparative_labels, comparative_predictions, _ = _pair_events(
            selected, "comparative"
        )
        confidence_labels, confidence_predictions, confidence_answered = _pair_events(
            selected,
            "confidence_alpha_0_05",
            "confidence_alpha_0_05",
        )
        rows.append(
            {
                "split": split,
                "grid_id": grid_id,
                "nominal_q_name": q_name,
                "signal_h_name": signal_name,
                "donor_mismatch_name": mismatch_name,
                "availability_name": availability_name,
                "contamination_name": contamination_name,
                "raw_field_name": raw_name,
                "noise_name": noise_name,
                "total_pair_rows": int(len(selected)),
                "q0_observational_identity_pair_rows": int(
                    selected["comparative_observation_identity"].sum()
                ),
                "nonpositive_structural_margin_pair_rows": int(
                    (selected["structural_margin"] <= 0.0).sum()
                ),
                "certificate_answered_pair_rows": int(
                    selected["certificate_answered"].sum()
                ),
                "envelope_violation_pair_rows": int(
                    (
                        ~selected["local_envelope_satisfied"].to_numpy(dtype=bool)
                        | ~selected["shared_envelope_satisfied"].to_numpy(dtype=bool)
                    ).sum()
                ),
                "certificate_error_events": int(
                    (predictions[answered] != labels[answered]).sum()
                ),
                "comparative_forced_error_events": int(
                    (comparative_predictions != comparative_labels).sum()
                ),
                "confidence_alpha_0_05_answered_events": int(confidence_answered.sum()),
                "confidence_alpha_0_05_error_events": int(
                    (
                        confidence_predictions[confidence_answered]
                        != confidence_labels[confidence_answered]
                    ).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _metric_value(
    component_table: pd.DataFrame,
    policy: str,
    alpha: float | None,
    quantity: str,
) -> float:
    selected = component_table.loc[
        (component_table["policy"] == policy)
        & (
            component_table["alpha"].isna()
            if alpha is None
            else np.isclose(component_table["alpha"].astype(float), alpha)
        )
    ]
    if len(selected) != 1:
        raise ValueError("Bootstrap component metrics are incomplete.")
    answered = float(selected.iloc[0]["answered_events"])
    total = float(selected.iloc[0]["total_events"])
    errors = float(selected.iloc[0]["error_events"])
    if quantity == "coverage":
        return answered / total
    if quantity == "conditional_error":
        return errors / answered if answered else float("nan")
    raise ValueError(f"Unsupported bootstrap quantity: {quantity}")


def _frontier_from_component_metric_tables(
    component_tables: list[pd.DataFrame], alpha: float
) -> tuple[float, float, float]:
    """Calculate target/comparative frontiers from a resampled component list."""

    merged = pd.concat(component_tables, ignore_index=True)

    def summary(policy: str, policy_alpha: float | None) -> tuple[float, float]:
        selected = merged.loc[
            (merged["policy"] == policy)
            & (
                merged["alpha"].isna()
                if policy_alpha is None
                else np.isclose(merged["alpha"].astype(float), policy_alpha)
            )
        ]
        answered = float(selected["answered_events"].sum())
        total = float(selected["total_events"].sum())
        errors = float(selected["error_events"].sum())
        risk = errors / answered if answered else float("nan")
        return answered / total, risk

    target_coverage, target_risk = summary("target_only_forced", None)
    forced_coverage, forced_risk = summary("comparative_forced", None)
    confidence_candidates = [
        summary("confidence_selective", calibration_alpha)
        for calibration_alpha in ALPHAS
    ]
    target = target_coverage if np.isfinite(target_risk) and target_risk <= alpha else 0.0
    comparative = max(
        (
            coverage
            if np.isfinite(risk) and risk <= alpha
            else 0.0
            for coverage, risk in (
                (forced_coverage, forced_risk),
                *confidence_candidates,
            )
        ),
        default=0.0,
    )
    return target, comparative, comparative - target


def _component_bootstrap_dataframe_reference(
    evaluation_metrics: pd.DataFrame, protocol: dict[str, Any]
) -> pd.DataFrame:
    """Reference implementation for tiny test fixtures only."""

    overall = evaluation_metrics.loc[
        (evaluation_metrics["group_type"] == "overall")
        & (evaluation_metrics["group_value"] == "all")
    ].copy()
    # Metrics are first recomputed per component from pair rows by the caller.
    # This function intentionally receives component-level rows despite its
    # historic argument name to make accidental row-level resampling impossible.
    if "component_id" not in overall.columns:
        raise ValueError("Component bootstrap requires a component_id column.")
    components = sorted(overall["component_id"].astype(str).unique())
    if len(components) < 2:
        raise ValueError("At least two components are required for bootstrap.")
    repetitions = int(protocol["reporting"]["cluster_bootstrap"]["repetitions"])
    seed = int(protocol["reporting"]["cluster_bootstrap"]["seed"])
    rng = np.random.default_rng(seed)
    by_component = {
        component: overall.loc[overall["component_id"].astype(str) == component].copy()
        for component in components
    }

    metric_specs: list[tuple[str, float | None, Callable[[list[pd.DataFrame]], float]]] = []
    for policy, alpha in [
        ("target_only_forced", None),
        ("comparative_forced", None),
        ("certificate_selective", None),
    ]:
        for quantity in ("coverage", "conditional_error"):
            metric_specs.append(
                (
                    f"{policy}_{quantity}",
                    alpha,
                    lambda tables, policy=policy, alpha=alpha, quantity=quantity: (
                        _aggregate_policy_quantity(tables, policy, alpha, quantity)
                    ),
                )
            )
    for alpha in ALPHAS:
        for quantity in ("coverage", "conditional_error"):
            metric_specs.append(
                (
                    (
                        "confidence_selective_calibration_alpha_"
                        f"{_alpha_token(alpha)}_{quantity}"
                    ),
                    alpha,
                    lambda tables, alpha=alpha, quantity=quantity: (
                        _aggregate_policy_quantity(
                            tables, "confidence_selective", alpha, quantity
                        )
                    ),
                )
            )
        metric_specs.extend(
            [
                (
                    "target_only_frontier_coverage",
                    alpha,
                    lambda tables, alpha=alpha: _frontier_from_component_metric_tables(
                        tables, alpha
                    )[0],
                ),
                (
                    "comparative_frontier_coverage",
                    alpha,
                    lambda tables, alpha=alpha: _frontier_from_component_metric_tables(
                        tables, alpha
                    )[1],
                ),
                (
                    "scope_answerability_gain",
                    alpha,
                    lambda tables, alpha=alpha: _frontier_from_component_metric_tables(
                        tables, alpha
                    )[2],
                ),
            ]
        )

    rows: list[dict[str, Any]] = []
    for metric_name, alpha, statistic in metric_specs:
        point = statistic(list(by_component.values()))
        samples: list[float] = []
        for _ in range(repetitions):
            sampled = rng.choice(components, size=len(components), replace=True)
            value = statistic([by_component[str(component)] for component in sampled])
            if np.isfinite(value):
                samples.append(float(value))
        if samples:
            lower, upper = np.quantile(samples, [0.025, 0.975], method="linear")
            status = "complete"
        else:
            lower = upper = None
            status = "no_valid_repetitions"
        rows.append(
            {
                "metric": metric_name,
                "alpha": alpha,
                "point_estimate": float(point) if np.isfinite(point) else None,
                "lower_95": float(lower) if lower is not None else None,
                "upper_95": float(upper) if upper is not None else None,
                "valid_repetitions": len(samples),
                "repetitions": repetitions,
                "cluster_unit": "evaluation component_id",
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def _aggregate_policy_quantity(
    tables: list[pd.DataFrame], policy: str, alpha: float | None, quantity: str
) -> float:
    merged = pd.concat(tables, ignore_index=True)
    selected = merged.loc[
        (merged["policy"] == policy)
        & (
            merged["alpha"].isna()
            if alpha is None
            else np.isclose(merged["alpha"].astype(float), alpha)
        )
    ]
    if selected.empty:
        raise ValueError("Bootstrap statistic has no selected rows.")
    answered = float(selected["answered_events"].sum())
    total = float(selected["total_events"].sum())
    errors = float(selected["error_events"].sum())
    if quantity == "coverage":
        return answered / total
    if quantity == "conditional_error":
        return errors / answered if answered else float("nan")
    raise ValueError(f"Unsupported bootstrap quantity: {quantity}")


def component_bootstrap(
    evaluation_metrics: pd.DataFrame, protocol: dict[str, Any]
) -> pd.DataFrame:
    """Bootstrap compact component count arrays instead of individual event rows."""

    overall = evaluation_metrics.loc[
        (evaluation_metrics["group_type"] == "overall")
        & (evaluation_metrics["group_value"] == "all")
    ].copy()
    if "component_id" not in overall.columns:
        raise ValueError("Component bootstrap requires a component_id column.")
    components = sorted(overall["component_id"].astype(str).unique())
    if len(components) < 2:
        raise ValueError("At least two components are required for bootstrap.")
    repetitions = int(protocol["reporting"]["cluster_bootstrap"]["repetitions"])
    rng = np.random.default_rng(int(protocol["reporting"]["cluster_bootstrap"]["seed"]))
    samples = rng.integers(
        0, len(components), size=(repetitions, len(components))
    )

    def counts_for(
        policy: str, alpha: float | None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        selected = overall.loc[
            (overall["policy"] == policy)
            & (
                overall["alpha"].isna()
                if alpha is None
                else np.isclose(overall["alpha"].astype(float), alpha)
            )
        ].set_index("component_id")
        selected = selected.reindex(components)
        required_counts = selected[["answered_events", "error_events", "total_events"]]
        if len(selected) != len(components) or required_counts.isna().any().any():
            raise ValueError("Bootstrap component metrics are incomplete.")
        answered = selected["answered_events"].to_numpy(dtype=float)
        errors = selected["error_events"].to_numpy(dtype=float)
        totals = selected["total_events"].to_numpy(dtype=float)
        if (totals <= 0.0).any():
            raise ValueError("Bootstrap components must have positive event totals.")
        return answered, errors, totals

    all_counts: dict[
        tuple[str, float | None], tuple[np.ndarray, np.ndarray, np.ndarray]
    ] = {}
    for policy, alpha in (
        ("target_only_forced", None),
        ("comparative_forced", None),
        ("certificate_selective", None),
    ):
        all_counts[(policy, alpha)] = counts_for(policy, alpha)
    for alpha in ALPHAS:
        all_counts[("confidence_selective", alpha)] = counts_for(
            "confidence_selective", alpha
        )

    def summarize(
        counts: tuple[np.ndarray, np.ndarray, np.ndarray]
    ) -> tuple[float, float, np.ndarray, np.ndarray]:
        answered, errors, totals = counts
        point_answered = float(answered.sum())
        point_errors = float(errors.sum())
        point_total = float(totals.sum())
        point_coverage = point_answered / point_total
        point_error = (
            point_errors / point_answered if point_answered else float("nan")
        )
        sampled_answered = answered[samples].sum(axis=1)
        sampled_errors = errors[samples].sum(axis=1)
        sampled_totals = totals[samples].sum(axis=1)
        sampled_coverage = sampled_answered / sampled_totals
        sampled_error = np.divide(
            sampled_errors,
            sampled_answered,
            out=np.full(repetitions, np.nan),
            where=sampled_answered > 0.0,
        )
        return point_coverage, point_error, sampled_coverage, sampled_error

    summaries = {key: summarize(value) for key, value in all_counts.items()}
    rows: list[dict[str, Any]] = []

    def append_metric(
        metric: str, alpha: float | None, point: float, sampled: np.ndarray
    ) -> None:
        valid = sampled[np.isfinite(sampled)]
        if valid.size:
            lower, upper = np.quantile(valid, [0.025, 0.975], method="linear")
            status = "complete"
        else:
            lower = upper = None
            status = "no_valid_repetitions"
        rows.append(
            {
                "metric": metric,
                "alpha": alpha,
                "point_estimate": float(point) if np.isfinite(point) else None,
                "lower_95": float(lower) if lower is not None else None,
                "upper_95": float(upper) if upper is not None else None,
                "valid_repetitions": int(valid.size),
                "repetitions": repetitions,
                "cluster_unit": "evaluation component_id",
                "status": status,
            }
        )

    for policy, alpha in (
        ("target_only_forced", None),
        ("comparative_forced", None),
        ("certificate_selective", None),
    ):
        coverage, error, sampled_coverage, sampled_error = summaries[(policy, alpha)]
        append_metric(f"{policy}_coverage", alpha, coverage, sampled_coverage)
        append_metric(
            f"{policy}_conditional_error", alpha, error, sampled_error
        )

    target = summaries[("target_only_forced", None)]
    forced = summaries[("comparative_forced", None)]
    for alpha in ALPHAS:
        confidence = summaries[("confidence_selective", alpha)]
        (
            confidence_coverage,
            confidence_error,
            confidence_sampled_coverage,
            confidence_sampled_error,
        ) = confidence
        append_metric(
            f"confidence_selective_calibration_alpha_{_alpha_token(alpha)}_coverage",
            alpha,
            confidence_coverage,
            confidence_sampled_coverage,
        )
        append_metric(
            (
                "confidence_selective_calibration_alpha_"
                f"{_alpha_token(alpha)}_conditional_error"
            ),
            alpha,
            confidence_error,
            confidence_sampled_error,
        )
        target_coverage, target_error, target_sampled_coverage, target_sampled_error = target
        forced_coverage, forced_error, forced_sampled_coverage, forced_sampled_error = forced
        target_frontier_point = (
            target_coverage
            if np.isfinite(target_error) and target_error <= alpha
            else 0.0
        )
        target_frontier_sampled = np.where(
            np.isfinite(target_sampled_error) & (target_sampled_error <= alpha),
            target_sampled_coverage,
            0.0,
        )
        forced_frontier_sampled = np.where(
            np.isfinite(forced_sampled_error) & (forced_sampled_error <= alpha),
            forced_sampled_coverage,
            0.0,
        )
        confidence_frontier_point = max(
            (
                summaries[("confidence_selective", calibration_alpha)][0]
                if np.isfinite(
                    summaries[("confidence_selective", calibration_alpha)][1]
                )
                and summaries[("confidence_selective", calibration_alpha)][1] <= alpha
                else 0.0
            )
            for calibration_alpha in ALPHAS
        )
        confidence_frontier_sampled = np.maximum.reduce(
            [
                np.where(
                    np.isfinite(
                        summaries[("confidence_selective", calibration_alpha)][3]
                    )
                    & (
                        summaries[("confidence_selective", calibration_alpha)][3]
                        <= alpha
                    ),
                    summaries[("confidence_selective", calibration_alpha)][2],
                    0.0,
                )
                for calibration_alpha in ALPHAS
            ]
        )
        comparative_frontier_point = max(
            forced_coverage
            if np.isfinite(forced_error) and forced_error <= alpha
            else 0.0,
            confidence_frontier_point,
        )
        comparative_frontier_sampled = np.maximum(
            forced_frontier_sampled, confidence_frontier_sampled
        )
        append_metric(
            "target_only_frontier_coverage",
            alpha,
            target_frontier_point,
            target_frontier_sampled,
        )
        append_metric(
            "comparative_frontier_coverage",
            alpha,
            comparative_frontier_point,
            comparative_frontier_sampled,
        )
        append_metric(
            "scope_answerability_gain",
            alpha,
            comparative_frontier_point - target_frontier_point,
            comparative_frontier_sampled - target_frontier_sampled,
        )
    return pd.DataFrame(rows)


def component_policy_metrics(frame: pd.DataFrame, protocol: dict[str, Any]) -> pd.DataFrame:
    """Calculate overall-policy metrics separately for each evaluation component."""

    _require_split(frame, "evaluation")
    rows: list[pd.DataFrame] = []
    for component_id, component_frame in frame.groupby("component_id", sort=True):
        metrics = policy_metrics(
            component_frame,
            protocol,
            groups=[
                (
                    "overall",
                    "all",
                    lambda data: pd.Series(True, index=data.index),
                )
            ],
        )
        metrics["component_id"] = component_id
        rows.append(metrics)
    return pd.concat(rows, ignore_index=True)


def _validate_pair_result_schema(
    frame: pd.DataFrame, protocol: dict[str, Any], *, before_policies: bool
) -> None:
    required = protocol["output_contract"]["schemas"]["v05_scope_pair_results.csv"]
    policy_columns = {
        "target_only_local_prediction",
        "target_only_shared_prediction",
        "comparative_local_prediction",
        "comparative_shared_prediction",
    }
    required_before = [
        name
        for name in required
        if name not in policy_columns and not name.startswith("confidence_")
    ]
    expected = required_before if before_policies else required
    missing = [name for name in expected if name not in frame.columns]
    if missing:
        raise ValueError(f"Pair results miss declared schema columns: {missing}")
    if not frame.loc[:, expected].notna().all().all():
        nullable = {
            "certificate_local_prediction",
            "certificate_shared_prediction",
        }
        problematic = [
            column
            for column in expected
            if column not in nullable and frame[column].isna().any()
        ]
        if problematic:
            raise ValueError(f"Pair results contain null declared fields: {problematic}")


def _expected_schema_frame(frame: pd.DataFrame, protocol: dict[str, Any]) -> pd.DataFrame:
    columns = protocol["output_contract"]["schemas"]["v05_scope_pair_results.csv"]
    _validate_pair_result_schema(frame, protocol, before_policies=False)
    extras = sorted(set(frame.columns).difference(columns))
    if extras:
        raise ValueError(f"Pair result table has undeclared columns: {extras}")
    return frame.loc[:, columns]


def _accounting_report(frame: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]:
    expected = protocol["expected_accounting"]
    observed_pairs = {
        split: int((frame["split"] == split).sum())
        for split in ("calibration", "evaluation")
    }
    observed_events = {split: 2 * count for split, count in observed_pairs.items()}
    target_groups = frame.groupby("target_group_id")[
        ["local_target_sha256", "shared_target_sha256"]
    ].nunique()
    target_group_identity = bool((target_groups == 1).all().all())
    q0 = frame.loc[frame["nominal_q"] == 0.0]
    return {
        "observed_pair_rows": {
            **observed_pairs,
            "total": int(len(frame)),
        },
        "expected_pair_rows": expected["pair_rows"],
        "observed_scope_arm_events": {
            **observed_events,
            "total": int(2 * len(frame)),
        },
        "expected_scope_arm_events": expected["scope_arm_events"],
        "grid_cells_per_component": int(
            frame.groupby(["split", "component_id"]).size().min()
        ),
        "expected_grid_cells_per_component": expected["grid_cells_per_component"],
        "all_pair_ids_unique": not frame["pair_id"].duplicated().any(),
        "all_targets_identical_inside_pairs": bool(frame["target_identity"].all()),
        "all_target_groups_identical": target_group_identity,
        "q0_pair_rows": {
            "observed": int(len(q0)),
            "expected": int(expected["q0_pair_rows"]["total"]),
        },
        "all_q0_comparative_observations_identical": bool(
            q0["comparative_observation_identity"].all()
        ),
    }


def _assert_accounting(report: dict[str, Any]) -> None:
    if report["observed_pair_rows"] != report["expected_pair_rows"]:
        raise ValueError("Pair-row accounting does not match the frozen protocol.")
    if report["observed_scope_arm_events"] != report["expected_scope_arm_events"]:
        raise ValueError("Scope-arm accounting does not match the frozen protocol.")
    if (
        report["grid_cells_per_component"]
        != report["expected_grid_cells_per_component"]
    ):
        raise ValueError("At least one component has an incomplete Cartesian grid.")
    required_true = [
        "all_pair_ids_unique",
        "all_targets_identical_inside_pairs",
        "all_target_groups_identical",
        "all_q0_comparative_observations_identical",
    ]
    if not all(bool(report[name]) for name in required_true):
        raise ValueError("A target-identity or q=0 negative-control check failed.")
    if report["q0_pair_rows"]["observed"] != report["q0_pair_rows"]["expected"]:
        raise ValueError("q=0 negative-control accounting does not match protocol.")


def git_bytes(arguments: list[str]) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def git_text(arguments: list[str]) -> str:
    return git_bytes(arguments).decode("utf-8").strip()


def remote_peeled_tag_commit(remote_listing: str, tag: str) -> str:
    """Extract one annotated tag's peeled remote commit, failing closed."""

    reference = f"refs/tags/{tag}^{{}}"
    matches = [
        line.split("\t", maxsplit=1)[0]
        for line in remote_listing.splitlines()
        if "\t" in line and line.split("\t", maxsplit=1)[1] == reference
    ]
    if len(matches) != 1 or len(matches[0]) != 40:
        raise RuntimeError("origin must expose one peeled annotated execution-freeze tag.")
    return matches[0]


def remote_tag_object_id(remote_listing: str, tag: str) -> str:
    """Return the annotated tag object advertised by origin."""

    matches = [
        line.split("\t", maxsplit=1)[0]
        for line in remote_listing.splitlines()
        if "\t" in line and line.split("\t", maxsplit=1)[1] == f"refs/tags/{tag}"
    ]
    if len(matches) != 1 or len(matches[0]) != 40:
        raise RuntimeError("Remote tag object is absent or malformed.")
    return matches[0]


def validate_annotated_execution_tag(
    tag: str,
    head_commit: str,
    local_tag_object_type: str,
    local_tag_commit: str,
    remote_listing: str,
) -> str:
    if local_tag_object_type != "tag":
        raise RuntimeError("execution-freeze tag must be a local annotated Git tag.")
    if local_tag_commit != head_commit:
        raise RuntimeError("HEAD must resolve to the configured execution-freeze tag.")
    remote_commit = remote_peeled_tag_commit(remote_listing, tag)
    if remote_commit != head_commit:
        raise RuntimeError("origin execution-freeze tag must resolve to HEAD.")
    return remote_commit


def ensure_execution_claim_absent(protocol: dict[str, Any]) -> None:
    """Reject a second conforming run before it can acquire a local attempt."""

    claim_tag = str(protocol["output_contract"]["execution_claim_tag"])
    local = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{claim_tag}"],
        cwd=ROOT,
        check=False,
    )
    if local.returncode == 0:
        raise RuntimeError("The local remote-execution claim tag already exists.")
    if local.returncode != 1:
        raise RuntimeError("Unable to determine whether the local execution claim exists.")
    remote = git_text(
        [
            "ls-remote",
            "origin",
            f"refs/tags/{claim_tag}",
            f"refs/tags/{claim_tag}^{{}}",
        ]
    )
    if remote:
        raise RuntimeError("The remote execution claim tag already exists.")


def acquire_remote_execution_claim(
    protocol: dict[str, Any], preconditions: dict[str, Any]
) -> dict[str, str]:
    """Atomically push the append-only remote claim before local execution."""

    claim_tag = str(protocol["output_contract"]["execution_claim_tag"])
    execution_commit = str(preconditions["execution_git_commit"])
    input_bundle_sha256 = canonical_json_sha256(preconditions["allowed_input_hashes"])
    runtime_sha256 = canonical_json_sha256(preconditions["runtime_environment"])
    ensure_execution_claim_absent(protocol)
    message = "\n".join(
        [
            "MetaShift v0.5 one-time execution claim",
            f"execution_commit={execution_commit}",
            f"execution_freeze_tag={preconditions['execution_tag']}",
            f"protocol_sha256={preconditions['protocol_sha256']}",
            f"execution_manifest_sha256={preconditions['execution_manifest_sha256']}",
            f"allowlisted_input_hashes_sha256={input_bundle_sha256}",
            f"runtime_environment_sha256={runtime_sha256}",
        ]
    )
    try:
        subprocess.check_call(
            ["git", "tag", "-a", claim_tag, execution_commit, "-m", message],
            cwd=ROOT,
        )
        if git_text(["cat-file", "-t", f"refs/tags/{claim_tag}"]) != "tag":
            raise RuntimeError("Local execution claim must be an annotated Git tag.")
        if git_text(["rev-parse", f"{claim_tag}^{{commit}}"]) != execution_commit:
            raise RuntimeError("Local execution claim resolves to the wrong commit.")
        claim_object = git_text(["rev-parse", claim_tag])
        subprocess.check_call(
            [
                "git",
                "push",
                "--atomic",
                "origin",
                f"refs/tags/{claim_tag}:refs/tags/{claim_tag}",
            ],
            cwd=ROOT,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Unable to atomically acquire and push the remote execution claim tag."
        ) from error
    return {
        "execution_claim_tag": claim_tag,
        "remote_execution_claim_commit": execution_commit,
        "execution_claim_tag_object": claim_object,
        "execution_claim_input_bundle_sha256": input_bundle_sha256,
        "execution_claim_runtime_sha256": runtime_sha256,
    }


def ensure_allowlisted_inputs(protocol: dict[str, Any]) -> dict[str, str]:
    """Hash exactly the tracked source inputs listed in the protocol."""

    allowlist = protocol["data_access"]["execution_input_allowlist"]
    if not isinstance(allowlist, list) or not allowlist:
        raise ValueError("The execution input allowlist is absent.")
    hashes: dict[str, str] = {}
    for relative_path in allowlist:
        if not isinstance(relative_path, str):
            raise ValueError("The execution input allowlist contains a non-string path.")
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


def _run_pre_outcome_verifier() -> dict[str, Any]:
    from scripts import verify_v05_protocol_freeze as verifier

    report = verifier.build_report(require_no_outputs=True)
    if not report["all_checks_passed"]:
        raise RuntimeError("The tracked v0.5 pre-outcome verifier did not pass.")
    return report


def ensure_execution_preconditions(protocol: dict[str, Any]) -> dict[str, Any]:
    """Reject execution unless source, tag, and pre-outcome contract all match."""

    _run_pre_outcome_verifier()
    runtime = validate_runtime_environment(protocol)
    ensure_execution_claim_absent(protocol)
    output = protocol["output_contract"]
    tag = str(output["execution_freeze_tag"])
    if git_text(["status", "--porcelain"]):
        raise RuntimeError("Refusing execution from a dirty Git worktree.")
    head_commit = git_text(["rev-parse", "HEAD"])
    try:
        tag_type = git_text(["cat-file", "-t", f"refs/tags/{tag}"])
    except subprocess.CalledProcessError as error:
        raise RuntimeError("The execution-freeze tag must exist locally.") from error
    tag_commit = git_text(["rev-parse", f"{tag}^{{commit}}"])
    remote_listing = git_text(
        ["ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"]
    )
    remote_commit = validate_annotated_execution_tag(
        tag, head_commit, tag_type, tag_commit, remote_listing
    )
    allowlisted_hashes = ensure_allowlisted_inputs(protocol)
    manifest = read_execution_manifest()
    protocol_hash = source_sha256(PROTOCOL_PATH)
    if manifest.get("protocol_sha256") != protocol_hash:
        raise RuntimeError("Execution manifest does not bind the current protocol SHA-256.")
    if manifest.get("execution_freeze_tag") != tag:
        raise RuntimeError("Execution manifest binds a different execution tag.")
    bound_hashes = manifest.get("bound_input_sha256")
    if not isinstance(bound_hashes, dict):
        raise ValueError("Execution manifest lacks input hashes.")
    expected_bound_paths = set(allowlisted_hashes).difference(
        {EXECUTION_MANIFEST_RELATIVE_PATH}
    )
    if set(bound_hashes) != expected_bound_paths:
        raise RuntimeError("Execution manifest must bind every non-self source input.")
    for relative_path, actual_hash in allowlisted_hashes.items():
        if relative_path == EXECUTION_MANIFEST_RELATIVE_PATH:
            continue
        if bound_hashes[relative_path] != actual_hash:
            raise RuntimeError(f"Execution input differs from its manifest: {relative_path}")
    for relative_path, actual_hash in allowlisted_hashes.items():
        tagged_hash = sha256_bytes(
            git_bytes(["show", f"{tag}:{relative_path}"])
        )
        if tagged_hash != actual_hash:
            raise RuntimeError(
                f"Current allowlisted input differs from execution tag: {relative_path}"
            )
    if sha256_bytes(
        git_bytes(["show", f"{tag}:{PROTOCOL_RELATIVE_PATH}"])
    ) != protocol_hash:
        raise RuntimeError("Protocol at HEAD differs from the execution-freeze tag.")
    return {
        "execution_git_commit": head_commit,
        "execution_tag": tag,
        "remote_execution_tag_commit": remote_commit,
        "protocol_sha256": protocol_hash,
        "execution_manifest_sha256": source_sha256(EXECUTION_MANIFEST_PATH),
        "allowed_input_hashes": allowlisted_hashes,
        "runtime_environment": runtime,
    }


def _output_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    output = protocol["output_contract"]
    directory = project_path(str(output["directory"]))
    return {
        filename: directory / filename
        for filename in output["files"]
    }


def _create_output_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)


def acquire_attempt(
    protocol: dict[str, Any], preconditions: dict[str, Any]
) -> tuple[Path, Path]:
    """Persist a claimed attempt before allocating its result directory."""

    output = protocol["output_contract"]
    directory = project_path(str(output["directory"]))
    attempt = project_path(str(output["attempt_record"]))
    paths = _output_paths(protocol)
    if directory.exists() or attempt.exists() or any(path.exists() for path in paths.values()):
        raise FileExistsError("A v0.5 output directory, output file, or attempt record exists.")
    attempt.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "state": "claimed",
        "started_at_utc": utc_now(),
        **preconditions,
    }
    with attempt.open("x", encoding="utf-8") as destination:
        json.dump(record, destination, indent=2, sort_keys=True, allow_nan=False)
        destination.flush()
        os.fsync(destination.fileno())
    try:
        _create_output_directory(directory)
    except Exception as error:
        _complete_attempt(
            attempt,
            preconditions,
            "claim_acquired_setup_failed",
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
        )
        raise
    return directory, attempt


def _complete_attempt(
    attempt: Path, preconditions: dict[str, Any], state: str, **details: Any
) -> None:
    write_json_atomic(
        attempt,
        {
            "state": state,
            "finished_at_utc": utc_now(),
            **preconditions,
            **details,
        },
    )


def _receipt(
    protocol: dict[str, Any],
    preconditions: dict[str, Any],
    paths: dict[str, Path],
    accounting: dict[str, Any],
    semantics_check: dict[str, Any],
    failure_count: int,
) -> dict[str, Any]:
    hashes = {
        filename: {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for filename, path in paths.items()
        if filename != "v05_execution_receipt.json"
    }
    return {
        "protocol_id": protocol["protocol_id"],
        "created_at_utc": utc_now(),
        **preconditions,
        "observed_accounting": accounting,
        "implementation_semantics_check": semantics_check,
        "failure_count": failure_count,
        "output_hashes": hashes,
    }


def semantic_crosscheck(
    protocol: dict[str, Any], execution_tag: str
) -> dict[str, Any]:
    """Cross-check vector scores against the existing residual-window implementation.

    This only uses the first calibration component and declared grid cells. It
    exercises every factor before the one-time output is interpreted, while the
    main runner remains vectorized for the complete grid.
    """

    from metashift.answerability import (
        build_partial_scope_pair,
        effective_donor_participation,
        raw_additive_mean_leakage_bound,
        signed_mean_residual_effect,
    )

    component = generate_component(protocol, "calibration", 0)
    rows = rows_for_component(protocol, component, execution_tag)
    estimator = protocol["estimator"]
    weights = pd.Series(
        np.asarray(estimator["donor_weights"], dtype=float),
        index=[f"donor_{index}" for index in range(len(estimator["donor_weights"]))],
    )
    maximum_difference = 0.0
    checked = 0
    for row in rows:
        # Reconstruct the declared condition without using output values as inputs.
        cell = next(
            candidate
            for candidate in grid_specifications(protocol)
            if _grid_id(protocol, candidate) == row["grid_id"]
        )
        target_base, donor_base = base_analysis_scale_paths(
            protocol,
            component,
            cell["donor_mismatch"],
            cell["bounded_noise"],
        )
        target = pd.Series(np.expm1(target_base), index=component.index)
        donors = pd.DataFrame(
            np.expm1(donor_base),
            index=component.index,
            columns=weights.index,
        )
        mask = availability_mask(protocol, component, cell["availability"])
        donors = donors.where(mask)
        signal = pd.Series(0.0, index=component.index)
        signal.iloc[int(protocol["synthetic_panel"]["anchor_day_index"]) :] = float(
            cell["signal_h"]["value"]
        )
        field = pd.Series(0.0, index=component.index)
        field.iloc[int(protocol["synthetic_panel"]["anchor_day_index"]) :] = float(
            cell["raw_scale_field"]["post_anchor_raw_additive_magnitude"]
        )
        participation = pd.DataFrame(
            np.broadcast_to(
                np.asarray(cell["nominal_donor_participation"]["donor_participation"]),
                donors.shape,
            ),
            index=component.index,
            columns=weights.index,
        )
        contamination = pd.DataFrame(
            _contamination_vector(component, cell["donor_contamination"], protocol),
            index=component.index,
            columns=weights.index,
        )
        pair = build_partial_scope_pair(
            target,
            donors,
            component.index[int(protocol["synthetic_panel"]["anchor_day_index"])],
            signal,
            participation,
            field,
            contamination,
        )
        local_score, _, post = signed_mean_residual_effect(
            pair.target,
            pair.local_donors,
            weights,
            component.index[int(protocol["synthetic_panel"]["anchor_day_index"])],
            calibration_days=int(estimator["calibration_days"]),
            calibration_buffer_days=int(estimator["calibration_buffer_days"]),
            comparison_days=int(estimator["comparison_days"]),
            min_window_observations=int(estimator["minimum_window_observations"]),
            min_available_donors=int(estimator["minimum_available_donors"]),
        )
        shared_score, _, shared_post = signed_mean_residual_effect(
            pair.target,
            pair.shared_donors,
            weights,
            component.index[int(protocol["synthetic_panel"]["anchor_day_index"])],
            calibration_days=int(estimator["calibration_days"]),
            calibration_buffer_days=int(estimator["calibration_buffer_days"]),
            comparison_days=int(estimator["comparison_days"]),
            min_window_observations=int(estimator["minimum_window_observations"]),
            min_available_donors=int(estimator["minimum_available_donors"]),
        )
        if not post.equals(shared_post):
            raise ValueError("Vectorized arms have mismatched retained score dates.")
        q = effective_donor_participation(pair.local_donors, weights, participation)
        raw_bound = raw_additive_mean_leakage_bound(
            pair.target - field,
            pair.local_donors_before_raw_field,
            weights,
            post,
            float(cell["raw_scale_field"]["post_anchor_raw_additive_magnitude"]),
        )
        maximum_difference = max(
            maximum_difference,
            abs(local_score - float(row["local_score"])),
            abs(shared_score - float(row["shared_score"])),
            abs(float(q.loc[post].min()) - float(row["q_effective_min"])),
            abs(raw_bound - float(row["local_raw_error_bound"])),
        )
        checked += 1
    tolerance = float(protocol["estimator"]["numerical_identity_tolerance"])
    return {
        "checked_grid_cells": checked,
        "maximum_absolute_difference": maximum_difference,
        "tolerance": tolerance,
        "passed": maximum_difference <= tolerance,
    }


def run_once(protocol: dict[str, Any]) -> dict[str, Any]:
    """Perform the sole authorized execution after all source gates succeed."""

    preconditions = ensure_execution_preconditions(protocol)
    preconditions = {
        **preconditions,
        **acquire_remote_execution_claim(protocol, preconditions),
    }
    _, attempt = acquire_attempt(protocol, preconditions)
    paths = _output_paths(protocol)
    try:
        semantics = semantic_crosscheck(protocol, str(preconditions["execution_tag"]))
        if not semantics["passed"]:
            raise RuntimeError("Vectorized score semantics do not match residual windows.")
        calibration = generate_pair_results(
            protocol, "calibration", str(preconditions["execution_tag"])
        )
        _validate_pair_result_schema(calibration, protocol, before_policies=True)
        policies = calibration_policies(calibration, protocol)
        calibration = apply_policies(calibration, policies, protocol)
        evaluation = generate_pair_results(
            protocol, "evaluation", str(preconditions["execution_tag"])
        )
        _validate_pair_result_schema(evaluation, protocol, before_policies=True)
        evaluation = apply_policies(evaluation, policies, protocol)
        pairs = _expected_schema_frame(
            pd.concat([calibration, evaluation], ignore_index=True), protocol
        )
        accounting = _accounting_report(pairs, protocol)
        _assert_accounting(accounting)
        groups_calibration = reporting_groups(calibration)
        groups_evaluation = reporting_groups(evaluation)
        metrics = pd.concat(
            [
                policy_metrics(calibration, protocol, groups=groups_calibration),
                policy_metrics(evaluation, protocol, groups=groups_evaluation),
            ],
            ignore_index=True,
        )
        evaluation_metrics = metrics.loc[metrics["split"] == "evaluation"].copy()
        frontier = answerability_frontier(evaluation_metrics, protocol)
        certificate = pd.concat(
            [
                certificate_validity(calibration, groups=groups_calibration),
                certificate_validity(evaluation, groups=groups_evaluation),
            ],
            ignore_index=True,
        )
        failure_map = failure_mode_map(pairs)
        bootstrap = component_bootstrap(component_policy_metrics(evaluation, protocol), protocol)
        write_csv_atomic(paths["v05_scope_pair_results.csv"], pairs)
        write_json_atomic(paths["v05_calibration_policy.json"], policies)
        write_csv_atomic(paths["v05_policy_metrics.csv"], metrics)
        write_csv_atomic(paths["v05_answerability_frontier.csv"], frontier)
        write_csv_atomic(paths["v05_certificate_validity.csv"], certificate)
        write_csv_atomic(paths["v05_failure_mode_map.csv"], failure_map)
        write_csv_atomic(paths["v05_component_bootstrap.csv"], bootstrap)
        envelope_failures = int(
            (~pairs["local_envelope_satisfied"].to_numpy(dtype=bool)).sum()
            + (~pairs["shared_envelope_satisfied"].to_numpy(dtype=bool)).sum()
        )
        receipt = _receipt(
            protocol,
            preconditions,
            paths,
            accounting,
            semantics,
            envelope_failures,
        )
        write_json_atomic(paths["v05_execution_receipt.json"], receipt)
        state = "completed" if envelope_failures == 0 else "completed_certificate_contract_violation"
        _complete_attempt(
            attempt,
            preconditions,
            state,
            receipt_sha256=sha256(paths["v05_execution_receipt.json"]),
            failure_count=envelope_failures,
        )
        return {
            "state": state,
            "receipt": receipt,
        }
    except Exception as error:
        _complete_attempt(
            attempt,
            preconditions,
            "failed",
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
        )
        raise


def main() -> None:
    args = parse_args()
    if not args.execute:
        raise SystemExit(
            "Refusing to generate v0.5 results without --execute and the execution-freeze tag."
        )
    result = run_once(read_protocol())
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
