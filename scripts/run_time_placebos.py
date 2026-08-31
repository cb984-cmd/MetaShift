"""Run post-transition time placebos for complete MetaShift-Bench events.

Each pseudo-date is in a stable post-transition target regime and has stable
donors. The counterfactual weights remain those learned before the real Method
Code transition; no pseudo-date's future observations are used to fit weights.
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

from metashift.counterfactual import estimate_metadata_anchor  # noqa: E402
from metashift.v2 import placebo_p_value  # noqa: E402
from run_feasibility_prototype import event_donors, load_series  # noqa: E402
from run_real_transition_audit import fixed_weights, load_inputs  # noqa: E402


GATE_DIR = Path("artifacts/data_gate")
EVENT_AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
METHOD_RUNS_PATH = GATE_DIR / "method_runs.csv"
SCORES_PATH = Path("artifacts/time_placebo_scores.csv")
SUMMARY_PATH = Path("artifacts/time_placebo_summary.csv")
EXCLUSIONS_PATH = Path("artifacts/time_placebo_exclusions.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
DEFAULT_MIN_PLACEBO_COUNT = 50
DEFAULT_MAX_PLACEBO_COUNT = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate real metadata anchors with unique stable time placebos."
    )
    parser.add_argument(
        "--min-placebos",
        type=int,
        default=DEFAULT_MIN_PLACEBO_COUNT,
        help="Minimum number of unique valid placebo dates required for screening.",
    )
    parser.add_argument(
        "--max-placebos",
        type=int,
        default=DEFAULT_MAX_PLACEBO_COUNT,
        help="Maximum number of evenly spaced unique valid placebo dates per event.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Limit events for a smoke test.",
    )
    return parser.parse_args()


def stable_run_lookup() -> dict[tuple[str, str, str, str], pd.DataFrame]:
    runs = pd.read_csv(METHOD_RUNS_PATH, dtype="string")
    runs["start_date"] = pd.to_datetime(runs["start_date"])
    runs["end_date"] = pd.to_datetime(runs["end_date"])
    result = {}
    for raw_key, group in runs.groupby(SERIES_KEYS, sort=False):
        key = tuple(str(value) for value in raw_key)
        result[key] = group.sort_values("start_date")
    return result


def is_method_stable(
    runs: dict[tuple[str, str, str, str], pd.DataFrame],
    key: tuple[str, str, str, str],
    date: pd.Timestamp,
    window_days: int = 60,
) -> bool:
    monitor_runs = runs.get(key)
    if monitor_runs is None:
        return False
    start = date - pd.Timedelta(days=window_days)
    end = date + pd.Timedelta(days=window_days)
    return bool(
        (
            (monitor_runs["start_date"] <= start)
            & (monitor_runs["end_date"] >= end)
        ).any()
    )


def evenly_spaced_dates(
    dates: pd.DatetimeIndex, count: int
) -> list[pd.Timestamp]:
    if len(dates) < count:
        return []
    positions = np.linspace(0, len(dates) - 1, count, dtype=int)
    selected = [pd.Timestamp(dates[position]) for position in positions]
    if len(set(selected)) != len(selected):
        raise ValueError("Time-placebo selection produced duplicate dates.")
    return selected


def main() -> None:
    args = parse_args()
    if args.min_placebos <= 0 or args.max_placebos < args.min_placebos:
        raise ValueError(
            "--min-placebos must be positive and no greater than --max-placebos."
        )
    anchors, controls = load_inputs(GATE_DIR)
    audit = pd.read_csv(EVENT_AUDIT_PATH, dtype="string")
    complete_ids = set(audit.loc[audit["audit_status"] == "complete", "anchor_id"])
    events = anchors.loc[anchors["anchor_id"].isin(complete_ids)].copy()
    if args.max_events is not None:
        if args.max_events <= 0:
            raise ValueError("--max-events must be positive.")
        events = events.head(args.max_events)
    events["end_date"] = pd.to_datetime(events["end_date"])
    series = load_series("88101")
    runs = stable_run_lookup()
    score_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        event_id = str(event["anchor_id"])
        date = pd.Timestamp(event["start_date"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        try:
            target = series[target_key]
            donors, _ = event_donors(event_id, controls, series)
            metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
                "rank"
            ).head(5)
            _, _, weights = fixed_weights(target, donors, metadata, date)
            actual = estimate_metadata_anchor(target, donors, weights, date)
            candidate_dates = target.loc[
                date + pd.Timedelta(days=75) : pd.Timestamp(event["end_date"])
                - pd.Timedelta(days=60)
            ].dropna().index
            stable_candidates = [
                candidate
                for candidate in candidate_dates
                if is_method_stable(runs, target_key, candidate)
                and all(
                    is_method_stable(
                        runs,
                        (
                            str(row.control_state_code),
                            str(row.control_county_code),
                            str(row.control_site_num),
                            str(row.control_poc),
                        ),
                        candidate,
                    )
                    for row in metadata.itertuples(index=False)
                )
            ]
            if len(stable_candidates) < args.min_placebos:
                raise ValueError(
                    f"Only {len(stable_candidates)} unique stable candidate dates; "
                    f"minimum is {args.min_placebos}."
                )
            maximum = min(args.max_placebos, len(stable_candidates))
            dates = evenly_spaced_dates(
                pd.DatetimeIndex(stable_candidates), maximum
            )

            placebo_scores = []
            event_score_rows: list[dict[str, object]] = []
            for placebo_date in dates:
                try:
                    estimate = estimate_metadata_anchor(
                        target, donors, weights, placebo_date
                    )
                except ValueError:
                    # A date can be method-stable but still lack enough retained
                    # target/donor observations for the identical estimate.
                    continue
                score = abs(estimate.standardized_score)
                placebo_scores.append(score)
                event_score_rows.append(
                    {
                        "anchor_id": event_id,
                        "date_type": "post_transition_time_placebo",
                        "date": placebo_date.date().isoformat(),
                        "standardized_score": score,
                    }
                )
            if len(placebo_scores) < args.min_placebos:
                raise ValueError(
                    f"Only {len(placebo_scores)} unique valid stable post-transition "
                    f"placebos; minimum is {args.min_placebos}."
                )
            actual_score = abs(actual.standardized_score)
            score_rows.extend(event_score_rows)
            score_rows.append(
                {
                    "anchor_id": event_id,
                    "date_type": "actual_method_code_anchor",
                    "date": date.date().isoformat(),
                    "standardized_score": actual_score,
                }
            )
            summary_rows.append(
                {
                    "anchor_id": event_id,
                    "actual_standardized_score": actual_score,
                    "placebo_count": len(placebo_scores),
                    "stable_candidate_date_count": len(stable_candidates),
                    "placebo_median_score": float(np.median(placebo_scores)),
                    "placebo_p_value": placebo_p_value(actual_score, placebo_scores),
                    "status": "complete_100"
                    if len(placebo_scores) >= args.max_placebos
                    else "complete_50_to_99",
                }
            )
        except (KeyError, RuntimeError, ValueError) as error:
            exclusions.append({"anchor_id": event_id, "reason": str(error)})
            summary_rows.append(
                {
                    "anchor_id": event_id,
                    "actual_standardized_score": np.nan,
                    "placebo_count": 0,
                    "stable_candidate_date_count": 0,
                    "placebo_median_score": np.nan,
                    "placebo_p_value": np.nan,
                    "status": "insufficient_unique_stable_placebos",
                    "failure_reason": str(error),
                }
            )
        if position % 50 == 0 or position == len(events):
            print(f"Processed time placebos for {position}/{len(events)} complete events")

    pd.DataFrame(score_rows).to_csv(SCORES_PATH, index=False)
    pd.DataFrame(summary_rows).to_csv(SUMMARY_PATH, index=False)
    pd.DataFrame(exclusions).to_csv(EXCLUSIONS_PATH, index=False)
    print("\nTime-placebo status:")
    print(pd.DataFrame(summary_rows)["status"].value_counts().to_string())
    print(f"\nWrote {SCORES_PATH}, {SUMMARY_PATH}, and {EXCLUSIONS_PATH}")


if __name__ == "__main__":
    main()
