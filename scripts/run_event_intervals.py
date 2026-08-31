"""Compute conditional event-level block-bootstrap intervals for real anchors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.counterfactual import anchor_residual_windows  # noqa: E402
from metashift.inference import (  # noqa: E402
    block_bootstrap_median_difference,
    seed_from_identifier,
)
from run_feasibility_prototype import event_donors, load_series  # noqa: E402
from run_real_transition_audit import fixed_weights, load_inputs  # noqa: E402


GATE_DIR = Path("artifacts/data_gate")
EVENT_AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
OUTPUT_PATH = Path("artifacts/real_transition_88101_event_intervals.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
METHODS = ("nearest_neighbor_did", "standard_synthetic_control", "metashift_v1_fixed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap event-level intervals for fixed pre-event weights."
    )
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--repetitions", type=int, default=1_000)
    parser.add_argument("--block-length", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repetitions <= 0 or args.block_length <= 0:
        raise ValueError("Bootstrap repetitions and block length must be positive.")
    anchors, controls = load_inputs(GATE_DIR)
    audit = pd.read_csv(EVENT_AUDIT_PATH, dtype="string")
    completed_ids = set(audit.loc[audit["audit_status"] == "complete", "anchor_id"])
    events = anchors.loc[anchors["anchor_id"].isin(completed_ids)].copy()
    if args.max_events is not None:
        if args.max_events <= 0:
            raise ValueError("--max-events must be positive.")
        events = events.head(args.max_events)
    series = load_series("88101")
    rows: list[dict[str, object]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        event_id = str(event["anchor_id"])
        date = pd.Timestamp(event["start_date"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = series[target_key]
        donors, _ = event_donors(event_id, controls, series)
        metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
            "rank"
        ).head(5)
        nearest, standard, metashift = fixed_weights(target, donors, metadata, date)
        weights_by_method = {
            "nearest_neighbor_did": nearest,
            "standard_synthetic_control": standard,
            "metashift_v1_fixed": metashift,
        }
        for method in METHODS:
            windows = anchor_residual_windows(
                target, donors, weights_by_method[method], date
            )
            interval = block_bootstrap_median_difference(
                windows.pre["log_residual"].to_numpy(),
                windows.post["log_residual"].to_numpy(),
                repetitions=args.repetitions,
                block_length=args.block_length,
                random_seed=seed_from_identifier(f"{event_id}:{method}"),
            )
            rows.append(
                {
                    "anchor_id": event_id,
                    "method": method,
                    "anchor_date": date.date().isoformat(),
                    "log_effect": interval.point_estimate,
                    "ci95_lower": interval.lower_95,
                    "ci95_upper": interval.upper_95,
                    "ci_excludes_zero": interval.lower_95 > 0
                    or interval.upper_95 < 0,
                    "bootstrap_repetitions": interval.repetitions,
                    "block_length_observations": interval.block_length,
                    "random_seed": interval.random_seed,
                    "inference_scope": (
                        "Conditional on fixed pre-event donor weights; does not "
                        "include donor-selection or model-specification uncertainty."
                    ),
                }
            )
        if position % 50 == 0 or position == len(events):
            print(f"Computed intervals for {position}/{len(events)} events")

    output = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_PATH, index=False)
    print("\nInterval counts by method:")
    print(
        output.groupby("method")["ci_excludes_zero"]
        .agg(["size", "sum", "mean"])
        .to_string()
    )
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
