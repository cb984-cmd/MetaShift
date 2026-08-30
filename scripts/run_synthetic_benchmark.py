"""Run an initial, paired synthetic local-vs-regional benchmark for MetaShift."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.baselines import cusum_change_point, pelt_change_points, rolling_median_change_point
from metashift.counterfactual import (
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)
from metashift.synthetic import PerturbationKind, inject_perturbation
from run_feasibility_prototype import event_donors, load_series, synthetic_control_weights


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
CONTROLS_PATH = Path("artifacts/data_gate/geographic_controls.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
EVENT_COUNT = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run paired synthetic local-versus-regional MetaShift evaluation."
    )
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--event-count", type=int, default=EVENT_COUNT)
    parser.add_argument("--ridge-penalty", type=float, default=0.1)
    parser.add_argument("--prior-penalty", type=float, default=0.1)
    parser.add_argument(
        "--label",
        default="development",
        help="Label included in every output row to preserve evaluation provenance.",
    )
    return parser.parse_args()


def average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    """Compute average precision without adding a scikit-learn dependency."""

    order = np.argsort(-scores, kind="stable")
    ranked_labels = labels[order]
    positives = int(ranked_labels.sum())
    if positives == 0:
        raise ValueError("Average precision requires at least one positive event.")
    precision = np.cumsum(ranked_labels) / np.arange(1, len(ranked_labels) + 1)
    return float((precision * ranked_labels).sum() / positives)


def prepare_events() -> tuple[pd.DataFrame, pd.DataFrame]:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    anchors["pre_span_days"] = pd.to_numeric(anchors["pre_span_days"])
    anchors["geographic_control_count"] = pd.to_numeric(
        anchors["geographic_control_count"]
    )
    controls = pd.read_csv(CONTROLS_PATH, dtype="string")
    for column in [
        "distance_km",
        "pre_transition_paired_days",
        "pre_transition_log_correlation",
        "rank",
    ]:
        controls[column] = pd.to_numeric(controls[column])

    # The long pre-run ensures the 180-to-15-day calibration period lies wholly
    # in one reported method regime. Events are selected before any result is run.
    candidates = anchors.loc[
        (anchors["pre_span_days"] >= 270)
        & (anchors["geographic_control_count"] >= 3)
    ].sort_values(["anchor_id"], kind="stable")
    if len(candidates) < EVENT_COUNT:
        raise ValueError(
            f"Only {len(candidates)} initial candidate events; expected {EVENT_COUNT}."
        )
    return candidates, controls


def pre_scale(target: pd.Series, date: pd.Timestamp) -> float:
    values = target.loc[date - pd.Timedelta(days=180) : date - pd.Timedelta(days=15)]
    values = values.dropna().to_numpy()
    if len(values) < 60:
        raise ValueError("Synthetic event has insufficient target calibration data.")
    return max(1.4826 * float(np.median(np.abs(values - np.median(values)))), 0.5)


def fit_weights(
    target: pd.Series,
    donors: pd.DataFrame,
    metadata: pd.DataFrame,
    date: pd.Timestamp,
    ridge_penalty: float,
    prior_penalty: float,
) -> dict[str, pd.Series]:
    metadata = metadata.copy()
    metadata.index = donors.columns
    reliability = donor_weights(metadata)
    calibration = slice(date - pd.Timedelta(days=180), date - pd.Timedelta(days=15))
    nearest = pd.Series(0.0, index=donors.columns)
    nearest.iloc[0] = 1.0
    return {
        "nearest_neighbor_did": nearest,
        "standard_synthetic_control": synthetic_control_weights(target, donors, date),
        "metashift": reliability_constrained_weights(
            target.loc[calibration],
            donors.loc[calibration],
            reliability,
            ridge_penalty=ridge_penalty,
            prior_penalty=prior_penalty,
        ),
    }


def single_station_scores(target: pd.Series, date: pd.Timestamp) -> dict[str, float]:
    window = target.loc[date - pd.Timedelta(days=60) : date + pd.Timedelta(days=59)].dropna()
    values = np.log1p(window.clip(lower=0).to_numpy())
    if len(values) < 80:
        raise ValueError("Single-station baseline lacks 80 observations.")
    cusum = cusum_change_point(values)
    rolling = rolling_median_change_point(values, window=20)
    pelt = pelt_change_points(values, min_size=15)
    # PELT has no natural calibrated continuous score; the maximum score is one
    # when it selects a split within seven observed samples of the metadata date.
    anchor_index = int(np.searchsorted(window.index.to_numpy(), date.to_datetime64()))
    pelt_score = float(
        any(abs(change_index - anchor_index) <= 7 for change_index in pelt.change_indices)
    )
    return {
        "cusum": float(cusum.strongest_score or 0.0),
        "rolling_mad": float(rolling.strongest_score or 0.0),
        "pelt": pelt_score,
    }


def evaluate_variant(
    target: pd.Series,
    donors: pd.DataFrame,
    weights: dict[str, pd.Series],
    date: pd.Timestamp,
    kind: PerturbationKind,
    magnitude: float,
    seed: int,
) -> list[dict[str, object]]:
    altered_target, altered_donors, truth = inject_perturbation(
        target, donors, date, kind, magnitude, random_seed=seed
    )
    baseline_estimates = {
        name: estimate_metadata_anchor(target, donors, value, date)
        for name, value in weights.items()
    }
    altered_estimates = {
        name: estimate_metadata_anchor(altered_target, altered_donors, value, date)
        for name, value in weights.items()
    }
    rows = []
    is_local = kind is PerturbationKind.ADDITIVE_STEP
    expected_increment = float(
        np.median(
            np.log1p(altered_target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0))
            - np.log1p(target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0))
        )
    )
    for method, baseline in baseline_estimates.items():
        altered = altered_estimates[method]
        increment = altered.log_effect - baseline.log_effect
        rows.append(
            {
                "method": method,
                "perturbation": kind.value,
                "is_local": int(is_local),
                "expected_log_increment": np.nan if not is_local else expected_increment,
                "estimated_log_increment": increment,
                "absolute_error": abs(increment - (expected_increment if is_local else 0.0)),
                "ranking_score": abs(increment),
                "truth_anchor_date": truth.anchor_date.date().isoformat(),
            }
        )

    # These three methods observe only the identical target series; paired local
    # and regional variants make their expected discriminative performance clear.
    for name, score in single_station_scores(altered_target, date).items():
        rows.append(
            {
                "method": name,
                "perturbation": kind.value,
                "is_local": int(is_local),
                "expected_log_increment": np.nan,
                "estimated_log_increment": np.nan,
                "absolute_error": np.nan,
                "ranking_score": score,
                "truth_anchor_date": truth.anchor_date.date().isoformat(),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    if args.event_count <= 0:
        raise ValueError("--event-count must be positive.")
    label = re.sub(r"[^a-zA-Z0-9_-]+", "_", args.label).strip("_")
    if not label:
        raise ValueError("--label must contain at least one letter or number.")
    output_path = Path("artifacts") / f"synthetic_{label}_event_results.csv"
    summary_path = Path("artifacts") / f"synthetic_{label}_summary.csv"
    exclusions_path = Path("artifacts") / f"synthetic_{label}_event_exclusions.csv"
    events, controls = prepare_events()
    if args.start_year is not None:
        events = events.loc[events["start_date"].dt.year >= args.start_year]
    if args.end_year is not None:
        events = events.loc[events["start_date"].dt.year <= args.end_year]
    if len(events) < args.event_count:
        raise ValueError(
            f"Only {len(events)} eligible events within the requested date split; "
            f"expected {args.event_count}."
        )
    series = load_series()
    results: list[dict[str, object]] = []

    exclusions: list[dict[str, str]] = []
    completed_events = 0
    for _, event in events.iterrows():
        if completed_events == args.event_count:
            break
        event_id = str(event["anchor_id"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = series[target_key]
        date = pd.Timestamp(event["start_date"])
        try:
            donors, _ = event_donors(event_id, controls, series)
            metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
                "rank"
            ).head(5)
            magnitude = pre_scale(target, date) * 2
            weights = fit_weights(
                target,
                donors,
                metadata,
                date,
                args.ridge_penalty,
                args.prior_penalty,
            )
            # Confirm the single-station window before committing this event.
            single_station_scores(target, date)
        except ValueError as error:
            exclusions.append({"anchor_id": event_id, "reason": str(error)})
            print(f"Excluded {event_id}: {error}")
            continue
        for kind in (
            PerturbationKind.ADDITIVE_STEP,
            PerturbationKind.REGIONAL_ADDITIVE_STEP,
        ):
            variant_rows = evaluate_variant(
                target,
                donors,
                weights,
                date,
                kind,
                magnitude,
                completed_events + 1,
            )
            for row in variant_rows:
                row["anchor_id"] = event_id
                row["magnitude"] = magnitude
                row["evaluation_label"] = args.label
                results.append(row)
        completed_events += 1
        print(
            f"Completed paired synthetic benchmark {completed_events}/{args.event_count}: "
            f"{event_id}"
        )

    pd.DataFrame(exclusions).to_csv(exclusions_path, index=False)
    if completed_events < args.event_count:
        raise RuntimeError(
            f"Only {completed_events} complete benchmark events were available; "
            f"expected {args.event_count}. See {exclusions_path}."
        )

    output = pd.DataFrame(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    summary_rows = []
    for method, group in output.groupby("method", sort=True):
        labels = group["is_local"].to_numpy(dtype=int)
        scores = group["ranking_score"].to_numpy(dtype=float)
        effect_errors = group.loc[group["is_local"] == 1, "absolute_error"].dropna()
        summary_rows.append(
            {
                "method": method,
                "instances": len(group),
                "local_average_precision": average_precision(labels, scores),
                "local_effect_mae_log": float(effect_errors.mean()) if len(effect_errors) else np.nan,
                "regional_false_attribution_mean_score": float(
                    group.loc[group["is_local"] == 0, "ranking_score"].mean()
                ),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values("local_average_precision", ascending=False)
    summary.to_csv(summary_path, index=False)
    print("\nSynthetic benchmark summary:")
    print(summary.to_string(index=False))
    print(f"\nWrote {output_path} and {summary_path}")


if __name__ == "__main__":
    main()
