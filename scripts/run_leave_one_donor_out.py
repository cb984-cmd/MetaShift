"""Measure real-anchor sensitivity to each individual geographic donor."""

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
from run_feasibility_prototype import event_donors, load_series  # noqa: E402
from run_real_transition_audit import fixed_weights, load_inputs  # noqa: E402


GATE_DIR = Path("artifacts/data_gate")
EVENT_AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
DETAIL_PATH = Path("artifacts/leave_one_donor_out_details.csv")
SUMMARY_PATH = Path("artifacts/leave_one_donor_out_summary.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refit MetaShift after removing each donor from real anchors."
    )
    parser.add_argument("--max-events", type=int, default=None)
    return parser.parse_args()


def stable_direction(value: float, tolerance: float = 1e-8) -> int:
    if abs(value) <= tolerance:
        return 0
    return int(np.sign(value))


def main() -> None:
    args = parse_args()
    anchors, controls = load_inputs(GATE_DIR)
    audit = pd.read_csv(EVENT_AUDIT_PATH, dtype="string")
    complete_ids = set(audit.loc[audit["audit_status"] == "complete", "anchor_id"])
    events = anchors.loc[anchors["anchor_id"].isin(complete_ids)].copy()
    if args.max_events is not None:
        if args.max_events <= 0:
            raise ValueError("--max-events must be positive.")
        events = events.head(args.max_events)
    series = load_series("88101")
    details: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        event_id = str(event["anchor_id"])
        date = pd.Timestamp(event["start_date"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = series[target_key]
        donors, _ = event_donors(event_id, controls, series)
        metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
            "rank"
        ).head(5)
        metadata = metadata.copy()
        metadata.index = donors.columns
        _, _, full_weights = fixed_weights(target, donors, metadata, date)
        full_estimate = estimate_metadata_anchor(target, donors, full_weights, date)
        leave_effects = []
        failed_runs = 0

        for removed_donor in donors.columns:
            remaining_donors = donors.drop(columns=removed_donor)
            remaining_metadata = metadata.drop(index=removed_donor)
            try:
                prior = donor_weights(remaining_metadata)
                calibration = slice(
                    date - pd.Timedelta(days=180), date - pd.Timedelta(days=15)
                )
                weights = reliability_constrained_weights(
                    target.loc[calibration],
                    remaining_donors.loc[calibration],
                    prior,
                    ridge_penalty=0.1,
                    prior_penalty=0.1,
                )
                estimate = estimate_metadata_anchor(
                    target, remaining_donors, weights, date
                )
            except (RuntimeError, ValueError) as error:
                failed_runs += 1
                details.append(
                    {
                        "anchor_id": event_id,
                        "anchor_date": date.date().isoformat(),
                        "removed_donor": removed_donor,
                        "remaining_donors": len(remaining_donors.columns),
                        "full_log_effect": full_estimate.log_effect,
                        "leave_one_out_log_effect": np.nan,
                        "difference_from_full": np.nan,
                        "same_direction_as_full": np.nan,
                        "pre_residual_rmse": np.nan,
                        "run_status": "unavailable_after_donor_removal",
                        "run_reason": str(error),
                    }
                )
                continue
            leave_effects.append(estimate.log_effect)
            details.append(
                {
                    "anchor_id": event_id,
                    "anchor_date": date.date().isoformat(),
                    "removed_donor": removed_donor,
                    "remaining_donors": len(remaining_donors.columns),
                    "full_log_effect": full_estimate.log_effect,
                    "leave_one_out_log_effect": estimate.log_effect,
                    "difference_from_full": estimate.log_effect
                    - full_estimate.log_effect,
                    "same_direction_as_full": stable_direction(estimate.log_effect)
                    == stable_direction(full_estimate.log_effect),
                    "pre_residual_rmse": estimate.calibration_residual_rmse,
                    "run_status": "complete",
                    "run_reason": None,
                }
            )

        effect_array = np.asarray(leave_effects, dtype=float)
        full_direction = stable_direction(full_estimate.log_effect)
        directions = np.asarray([stable_direction(value) for value in effect_array])
        summaries.append(
            {
                "anchor_id": event_id,
                "anchor_date": date.date().isoformat(),
                "full_log_effect": full_estimate.log_effect,
                "donor_count": len(donors.columns),
                "leave_one_out_runs": len(effect_array),
                "leave_one_out_failed_runs": failed_runs,
                "leave_one_out_min_effect": float(effect_array.min())
                if len(effect_array)
                else np.nan,
                "leave_one_out_max_effect": float(effect_array.max())
                if len(effect_array)
                else np.nan,
                "leave_one_out_max_abs_deviation": float(
                    np.max(np.abs(effect_array - full_estimate.log_effect))
                )
                if len(effect_array)
                else np.nan,
                "full_direction": full_direction,
                "direction_stable_all_donors": bool(
                    np.all(directions == full_direction)
                )
                if len(directions)
                else False,
                "direction_flip_count": int(np.count_nonzero(directions != full_direction)),
                "summary_status": "complete"
                if failed_runs == 0
                else "partial_after_donor_removal"
                if len(effect_array)
                else "unavailable_after_all_donor_removals",
            }
        )
        if position % 50 == 0 or position == len(events):
            print(f"Completed leave-one-donor-out {position}/{len(events)} events")

    detail_frame = pd.DataFrame(details)
    summary_frame = pd.DataFrame(summaries)
    DETAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    detail_frame.to_csv(DETAIL_PATH, index=False)
    summary_frame.to_csv(SUMMARY_PATH, index=False)
    print("\nLeave-one-donor-out summary:")
    print(
        summary_frame.groupby("summary_status")["direction_stable_all_donors"]
        .agg(["size", "sum", "mean"])
        .to_string()
    )
    print(f"\nWrote {DETAIL_PATH} and {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
