"""Audit every AQS Method Code anchor with identical comparative estimators.

This is an observational audit. A reported Method Code transition is never
treated as a confirmed physical device replacement or a labeled bias event.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.counterfactual import (  # noqa: E402
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)
from metashift.splits import append_access_log, split_sha256  # noqa: E402
from metashift.v2 import evaluate_quality_gate  # noqa: E402
from run_feasibility_prototype import (  # noqa: E402
    event_donors,
    load_series,
    synthetic_control_weights,
)
from run_stable_synthetic_benchmark import single_station_results  # noqa: E402


ACCESS_LOG_PATH = Path("artifacts/test_access_log.jsonl")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a comparative observational audit of metadata anchors."
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Limit events for an implementation smoke test.",
    )
    parser.add_argument("--parameter-code", default="88101")
    parser.add_argument(
        "--gate-dir",
        type=Path,
        default=None,
        help="Parameter-specific output directory from scan_data_gate.py.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Output suffix; defaults to the AQS parameter code.",
    )
    return parser.parse_args()


def load_inputs(gate_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    anchors = pd.read_csv(gate_dir / "anchor_inventory.csv", dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    for column in [
        "geographic_control_count",
        "colocated_control_count",
        "previous_observations",
        "observations",
    ]:
        anchors[column] = pd.to_numeric(anchors[column])
    controls = pd.read_csv(gate_dir / "geographic_controls.csv", dtype="string")
    for column in [
        "distance_km",
        "pre_transition_paired_days",
        "pre_transition_log_correlation",
        "rank",
    ]:
        controls[column] = pd.to_numeric(controls[column])
    return anchors, controls


def fixed_weights(
    target: pd.Series, donors: pd.DataFrame, metadata: pd.DataFrame, date: pd.Timestamp
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Fit the three cross-site estimators exclusively on pre-transition data."""

    metadata = metadata.copy()
    metadata.index = donors.columns
    prior = donor_weights(metadata)
    calibration = slice(date - pd.Timedelta(days=180), date - pd.Timedelta(days=15))
    nearest = pd.Series(0.0, index=donors.columns)
    nearest.iloc[0] = 1.0
    standard = synthetic_control_weights(target, donors, date)
    metashift = reliability_constrained_weights(
        target.loc[calibration],
        donors.loc[calibration],
        prior,
        ridge_penalty=0.1,
        prior_penalty=0.1,
    )
    return nearest, standard, metashift


def event_base_row(event: pd.Series) -> dict[str, object]:
    return {
        "anchor_id": event["anchor_id"],
        "target_state": event["State Code"],
        "target_county": event["County Code"],
        "target_site": event["Site Num"],
        "target_poc": event["POC"],
        "anchor_date": pd.Timestamp(event["start_date"]).date().isoformat(),
        "old_method_code": event["previous_method_code"],
        "new_method_code": event["method_code"],
        "old_method_name": event["previous_method_name"],
        "new_method_name": event["method_name"],
        "geographic_control_candidates": int(event["geographic_control_count"]),
        "colocated_control_candidates": int(event["colocated_control_count"]),
    }


def main() -> None:
    args = parse_args()
    parameter_code = str(args.parameter_code)
    gate_dir = args.gate_dir or Path(
        "artifacts/data_gate"
        if parameter_code == "88101"
        else f"artifacts/data_gate_{parameter_code}"
    )
    label = args.label or parameter_code
    anchors, controls = load_inputs(gate_dir)
    if args.max_events is not None:
        if args.max_events <= 0:
            raise ValueError("--max-events must be positive.")
        anchors = anchors.head(args.max_events).copy()
    append_access_log(
        ACCESS_LOG_PATH,
        action="benchmark_observational_audit",
        purpose=(
            "Audit all reported metadata anchors after closing algorithm optimization; "
            "not a V2 final-test performance evaluation."
        ),
        split_hash=split_sha256(anchors),
        event_count=len(anchors),
    )
    series = load_series(parameter_code)
    event_rows: list[dict[str, object]] = []
    method_rows: list[dict[str, object]] = []

    for position, (_, event) in enumerate(anchors.iterrows(), start=1):
        row = event_base_row(event)
        event_id = str(event["anchor_id"])
        if int(event["geographic_control_count"]) < 3:
            row.update(
                {
                    "audit_status": "insufficient_geographic_donors",
                    "audit_reason": "Fewer than three prequalified geographic donors.",
                }
            )
            event_rows.append(row)
            continue

        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        date = pd.Timestamp(event["start_date"])
        try:
            target = series[target_key]
            donors, _ = event_donors(event_id, controls, series)
            metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
                "rank"
            ).head(5)
            nearest, standard, metashift = fixed_weights(target, donors, metadata, date)
            gate = evaluate_quality_gate(target, donors, metashift, date)
            estimators = {
                "nearest_neighbor_did": nearest,
                "standard_synthetic_control": standard,
                "metashift_v1_fixed": metashift,
            }
            for method, weights in estimators.items():
                estimate = estimate_metadata_anchor(target, donors, weights, date)
                method_rows.append(
                    {
                        **row,
                        "method": method,
                        "log_effect": estimate.log_effect,
                        "relative_effect": estimate.relative_effect,
                        "raw_effect_ug_m3": estimate.raw_effect,
                        "standardized_score": estimate.standardized_score,
                        "pre_residual_rmse": estimate.calibration_residual_rmse,
                        "calibration_observations": estimate.calibration_observations,
                        "pre_observations": estimate.pre_observations,
                        "post_observations": estimate.post_observations,
                        "mean_available_donors": estimate.mean_available_donors,
                        "effective_donor_count": float(1 / np.square(weights).sum()),
                        "maximum_donor_weight": float(weights.max()),
                        "quality_gate_passed": gate.passed,
                        "quality_gate_reason": gate.reason,
                        "detected_change_distance_days": 0.0,
                    }
                )
            for baseline in single_station_results(target, date):
                method_rows.append(
                    {
                        **row,
                        "method": baseline["method"],
                        "log_effect": baseline["estimated_log_effect"],
                        "relative_effect": np.nan,
                        "raw_effect_ug_m3": np.nan,
                        "standardized_score": baseline["ranking_score"],
                        "pre_residual_rmse": np.nan,
                        "calibration_observations": np.nan,
                        "pre_observations": np.nan,
                        "post_observations": np.nan,
                        "mean_available_donors": np.nan,
                        "effective_donor_count": np.nan,
                        "maximum_donor_weight": np.nan,
                        "quality_gate_passed": np.nan,
                        "quality_gate_reason": None,
                        "detected_change_distance_days": baseline[
                            "detected_change_distance_days"
                        ],
                    }
                )
            row.update(
                {
                    "audit_status": "complete",
                    "audit_reason": None,
                    "selected_donor_count": len(donors.columns),
                    "metashift_quality_gate_passed": gate.passed,
                    "metashift_quality_gate_reason": gate.reason,
                }
            )
        except (KeyError, RuntimeError, ValueError) as error:
            row.update(
                {
                    "audit_status": "estimator_input_failure",
                    "audit_reason": str(error),
                }
            )
        event_rows.append(row)
        if position % 50 == 0 or position == len(anchors):
            print(f"Audited {position}/{len(anchors)} real metadata anchors")

    event_audit = pd.DataFrame(event_rows)
    method_results = pd.DataFrame(method_rows)
    event_audit_path = Path("artifacts") / f"real_transition_{label}_event_audit.csv"
    method_results_path = (
        Path("artifacts") / f"real_transition_{label}_method_results.csv"
    )
    event_audit_path.parent.mkdir(parents=True, exist_ok=True)
    event_audit.to_csv(event_audit_path, index=False)
    method_results.to_csv(method_results_path, index=False)
    print("\nEvent audit status:")
    print(event_audit["audit_status"].value_counts(dropna=False).to_string())
    print("\nMethod-result counts:")
    print(method_results["method"].value_counts(dropna=False).to_string())
    print(f"\nWrote {event_audit_path} and {method_results_path}")


if __name__ == "__main__":
    main()
