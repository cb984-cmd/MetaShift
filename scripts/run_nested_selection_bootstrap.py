"""Estimate selection-aware nested block-bootstrap intervals for real anchors."""

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

from metashift.inference import (  # noqa: E402
    nested_selection_block_bootstrap,
    seed_from_identifier,
)
from run_feasibility_prototype import load_series  # noqa: E402


POOL_PATH = Path("artifacts/nested_bootstrap_candidate_pool.csv")
AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
METHOD_RESULTS_PATH = Path("artifacts/real_transition_88101_method_results.csv")
OUTPUT_PATH = Path("artifacts/real_transition_88101_nested_selection_intervals.csv")
FAILURE_PATH = Path("artifacts/real_transition_88101_nested_selection_failures.csv")
SERIES_KEYS = ["target_state", "target_county", "target_site", "target_poc"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run selection-aware block bootstrap for real MetaShift anchors."
    )
    parser.add_argument("--repetitions", type=int, default=1_000)
    parser.add_argument("--block-length", type=int, default=7)
    parser.add_argument("--max-events", type=int, default=None)
    return parser.parse_args()


def donor_key(row: pd.Series) -> tuple[str, str, str, str]:
    return (
        str(row["control_state_code"]),
        str(row["control_county_code"]),
        str(row["control_site_num"]),
        str(row["control_poc"]),
    )


def matrix_for_window(
    target: pd.Series,
    donors: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> np.ndarray:
    """Align target and every full-pool donor to a daily calendar index."""

    dates = pd.date_range(start, end, freq="D")
    table = pd.concat([target.rename("target"), donors], axis="columns", sort=False)
    return table.reindex(dates).to_numpy(dtype=float)


def main() -> None:
    args = parse_args()
    if args.repetitions <= 0 or args.block_length <= 0:
        raise ValueError("Bootstrap repetitions and block length must be positive.")
    audit = pd.read_csv(AUDIT_PATH, dtype="string")
    events = audit.loc[audit["audit_status"] == "complete"].copy()
    events["anchor_date"] = pd.to_datetime(events["anchor_date"])
    if args.max_events is not None:
        if args.max_events <= 0:
            raise ValueError("--max-events must be positive.")
        events = events.head(args.max_events)
    pool = pd.read_csv(POOL_PATH, dtype="string")
    for column in ["distance_km", "pre_transition_log_correlation"]:
        pool[column] = pd.to_numeric(pool[column])
    main_results = pd.read_csv(METHOD_RESULTS_PATH)
    main_meta = main_results.loc[
        main_results["method"] == "metashift_v1_fixed",
        ["anchor_id", "log_effect"],
    ].set_index("anchor_id")["log_effect"]
    series = load_series("88101")
    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        event_id = str(event["anchor_id"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        date = pd.Timestamp(event["anchor_date"])
        try:
            candidates = pool.loc[pool["anchor_id"] == event_id].copy()
            if len(candidates) < 3:
                raise ValueError("Fewer than three candidate donors in selection pool.")
            candidates = candidates.sort_values(
                [
                    "pre_transition_log_correlation",
                    "distance_km",
                    "control_state_code",
                    "control_county_code",
                    "control_site_num",
                    "control_poc",
                ],
                ascending=[False, True, True, True, True, True],
                kind="stable",
            )
            donor_series = {}
            for _, candidate in candidates.iterrows():
                key = donor_key(candidate)
                if key not in series:
                    raise KeyError(f"Candidate donor absent from series data: {key}")
                donor_series["-".join(key)] = series[key]
            target = series[target_key]
            donors = pd.DataFrame(donor_series).sort_index()
            distances = candidates["distance_km"].to_numpy(dtype=float)
            calibration = matrix_for_window(
                target, donors, date - pd.Timedelta(days=180), date - pd.Timedelta(days=15)
            )
            pre = matrix_for_window(
                target, donors, date - pd.Timedelta(days=60), date - pd.Timedelta(days=1)
            )
            post = matrix_for_window(
                target, donors, date, date + pd.Timedelta(days=59)
            )
            interval = nested_selection_block_bootstrap(
                calibration,
                pre,
                post,
                distances,
                repetitions=args.repetitions,
                block_length=args.block_length,
                random_seed=seed_from_identifier(f"{event_id}:nested_selection"),
            )
            fixed_effect = float(main_meta.loc[event_id])
            point_difference = interval.point_estimate - fixed_effect
            results.append(
                {
                    "anchor_id": event_id,
                    "anchor_date": date.date().isoformat(),
                    "candidate_pool_size": len(candidates),
                    "fixed_main_log_effect": fixed_effect,
                    "nested_point_log_effect": interval.point_estimate,
                    "nested_point_minus_fixed_effect": point_difference,
                    "selection_ci95_lower": interval.lower_95,
                    "selection_ci95_upper": interval.upper_95,
                    "selection_ci_excludes_zero": interval.lower_95 > 0
                    or interval.upper_95 < 0,
                    "valid_repetitions": interval.valid_repetitions,
                    "invalid_reselection_or_refit_repetitions": (
                        interval.invalid_reselection_or_refit_repetitions
                    ),
                    "invalid_effect_repetitions": interval.invalid_effect_repetitions,
                    "median_selected_donor_count": interval.median_selected_donor_count,
                    "random_seed": interval.random_seed,
                    "block_length_days": interval.block_length,
                    "inference_scope": (
                        "Selection-aware within a fixed observed geographic, method-"
                        "stability, and availability candidate pool. Each repetition "
                        "jointly block-resamples pre-event time, recalculates donor "
                        "correlations, reselects 3-5 donors, refits weights, and "
                        "block-resamples comparison windows. It does not model "
                        "uncertainty in source metadata, geography, or candidate-pool "
                        "construction."
                    ),
                }
            )
        except (KeyError, RuntimeError, ValueError) as error:
            failures.append(
                {
                    "anchor_id": event_id,
                    "anchor_date": date.date().isoformat(),
                    "reason": str(error),
                }
            )
        if position % 25 == 0 or position == len(events):
            print(f"Computed nested bootstrap {position}/{len(events)} events")

    result = pd.DataFrame(results)
    result.to_csv(OUTPUT_PATH, index=False)
    pd.DataFrame(
        failures, columns=["anchor_id", "anchor_date", "reason"]
    ).to_csv(FAILURE_PATH, index=False)
    print("\nNested-bootstrap completion:")
    print(
        {
            "completed_events": len(result),
            "failed_events": len(failures),
            "selection_ci_excludes_zero": int(
                result["selection_ci_excludes_zero"].sum()
            )
            if len(result)
            else 0,
            "maximum_point_difference_from_main": float(
                result["nested_point_minus_fixed_effect"].abs().max()
            )
            if len(result)
            else np.nan,
        }
    )
    print(f"Wrote {OUTPUT_PATH} and {FAILURE_PATH}")


if __name__ == "__main__":
    main()
