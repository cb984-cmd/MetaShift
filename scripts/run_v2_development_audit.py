"""Run MetaShift v2 quality and placebo diagnostics on development target states."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.counterfactual import donor_weights, reliability_constrained_weights
from metashift.v2 import (
    AttributionShape,
    attribute_residual_shape,
    evaluate_quality_gate,
    placebo_p_value,
    residual_series,
)
from run_feasibility_prototype import event_donors, load_series
from run_synthetic_benchmark import CONTROLS_PATH, prepare_events


TEST_STATES = {"17", "25"}
MAX_EVENTS = 40
PLACEBO_COUNT = 10
RIDGE_PENALTY = 0.1
PRIOR_PENALTY = 0.1
RESULT_PATH = Path("artifacts/v2_development_audit.csv")
EXCLUSION_PATH = Path("artifacts/v2_development_exclusions.csv")


def dynamic_reliability_prior(
    target: pd.Series,
    donors: pd.DataFrame,
    metadata: pd.DataFrame,
    anchor_date: pd.Timestamp,
) -> pd.Series:
    """Recalculate correlations using only the candidate date's pre-period."""

    start = anchor_date - pd.Timedelta(days=180)
    end = anchor_date - pd.Timedelta(days=15)
    correlations = []
    for column in donors.columns:
        paired = pd.concat(
            [target.rename("target"), donors[column].rename("donor")],
            axis="columns",
            sort=False,
        ).sort_index().loc[start:end].dropna()
        if len(paired) < 60:
            correlations.append(np.nan)
            continue
        target_values = np.log1p(paired["target"].clip(lower=0))
        donor_values = np.log1p(paired["donor"].clip(lower=0))
        correlations.append(float(target_values.corr(donor_values)))
    current = metadata.copy()
    current.index = donors.columns
    current["pre_transition_log_correlation"] = correlations
    if current["pre_transition_log_correlation"].isna().any():
        raise ValueError("A donor lacks 60 paired observations for the candidate date.")
    return donor_weights(current)


def fitted_event(
    target: pd.Series,
    donors: pd.DataFrame,
    metadata: pd.DataFrame,
    date: pd.Timestamp,
) -> tuple[object, object]:
    prior = dynamic_reliability_prior(target, donors, metadata, date)
    calibration = slice(date - pd.Timedelta(days=180), date - pd.Timedelta(days=15))
    weights = reliability_constrained_weights(
        target.loc[calibration],
        donors.loc[calibration],
        prior,
        ridge_penalty=RIDGE_PENALTY,
        prior_penalty=PRIOR_PENALTY,
    )
    gate = evaluate_quality_gate(target, donors, weights, date)
    residuals, _ = residual_series(target, donors, weights)
    attribution = attribute_residual_shape(residuals, date)
    return gate, attribution


def placebo_dates(event: pd.Series, target: pd.Series) -> list[pd.Timestamp]:
    """Choose evenly spaced pre-transition dates safe from the known anchor."""

    start = pd.Timestamp(event["previous_start_date"]) + pd.Timedelta(days=195)
    end = pd.Timestamp(event["start_date"]) - pd.Timedelta(days=75)
    candidates = target.loc[start:end].dropna().index.unique()
    if len(candidates) < PLACEBO_COUNT:
        raise ValueError("Fewer than ten eligible pre-transition placebo dates.")
    indexes = np.linspace(0, len(candidates) - 1, PLACEBO_COUNT, dtype=int)
    return [pd.Timestamp(candidates[index]) for index in indexes]


def main() -> None:
    events, controls = prepare_events()
    events = events.loc[~events["State Code"].isin(TEST_STATES)]
    if len(events) < MAX_EVENTS:
        raise ValueError("Insufficient development-state candidate events.")
    series = load_series()
    results: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []

    for _, event in events.iterrows():
        if len(results) == MAX_EVENTS:
            break
        event_id = str(event["anchor_id"])
        target_key = (
            str(event["State Code"]),
            str(event["County Code"]),
            str(event["Site Num"]),
            str(event["POC"]),
        )
        try:
            target = series[target_key]
            donors, _ = event_donors(event_id, controls, series)
            metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
                "rank"
            ).head(5)
            date = pd.Timestamp(event["start_date"])
            gate, attribution = fitted_event(target, donors, metadata, date)

            scores = []
            for date_placebo in placebo_dates(event, target):
                placebo_gate, placebo_attribution = fitted_event(
                    target, donors, metadata, date_placebo
                )
                if placebo_gate.passed:
                    scores.append(placebo_attribution.score)
            if len(scores) < 5:
                raise ValueError("Fewer than five quality-gated placebo scores.")

            results.append(
                {
                    "anchor_id": event_id,
                    "target_state": target_key[0],
                    "anchor_date": date.date().isoformat(),
                    "quality_gate_passed": gate.passed,
                    "quality_gate_reason": gate.reason,
                    "paired_pre_observations": gate.paired_pre_observations,
                    "effective_donor_count": gate.effective_donor_count,
                    "maximum_donor_weight": gate.maximum_donor_weight,
                    "pre_residual_rmse": gate.pre_residual_rmse,
                    "predicted_shape": attribution.shape.value,
                    "observed_score": attribution.score,
                    "level_effect_log": attribution.level_effect,
                    "drift_per_day_log": attribution.drift_per_day,
                    "log_variance_ratio": attribution.log_variance_ratio,
                    "persistence": attribution.persistence,
                    "placebo_count": len(scores),
                    "placebo_p_value": placebo_p_value(attribution.score, scores),
                }
            )
            print(f"Completed V2 development audit: {event_id}")
        except ValueError as error:
            exclusions.append({"anchor_id": event_id, "reason": str(error)})
            print(f"Excluded V2 development event {event_id}: {error}")

    result = pd.DataFrame(results)
    result.to_csv(RESULT_PATH, index=False)
    pd.DataFrame(exclusions).to_csv(EXCLUSION_PATH, index=False)
    print(f"\nWrote {RESULT_PATH} and {EXCLUSION_PATH}")
    print(
        result.groupby(["quality_gate_passed", "predicted_shape"], dropna=False)
        .size()
        .rename("events")
        .reset_index()
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
