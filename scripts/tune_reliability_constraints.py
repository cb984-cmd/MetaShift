"""Select MetaShift reliability penalties on development events only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.counterfactual import (
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)
from metashift.synthetic import PerturbationKind, inject_perturbation
from run_feasibility_prototype import event_donors, load_series
from run_synthetic_benchmark import CONTROLS_PATH, prepare_events, pre_scale


OUTPUT_PATH = Path("artifacts/reliability_constraint_tuning.csv")
EXCLUSIONS_PATH = Path("artifacts/reliability_tuning_exclusions.csv")
DEVELOPMENT_EVENT_COUNT = 30
RIDGE_PENALTIES = (0.0, 0.001, 0.01, 0.1)
PRIOR_PENALTIES = (0.001, 0.01, 0.1, 1.0)


def local_injection_error(
    target: pd.Series,
    donors: pd.DataFrame,
    weights: pd.Series,
    date: pd.Timestamp,
    magnitude: float,
) -> float:
    baseline = estimate_metadata_anchor(target, donors, weights, date)
    injected_target, injected_donors, _ = inject_perturbation(
        target, donors, date, PerturbationKind.ADDITIVE_STEP, magnitude
    )
    injected = estimate_metadata_anchor(injected_target, injected_donors, weights, date)
    expected_increment = float(
        np.median(
            np.log1p(injected_target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0))
            - np.log1p(target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0))
        )
    )
    return abs((injected.log_effect - baseline.log_effect) - expected_increment)


def main() -> None:
    candidates, controls = prepare_events()
    candidates = candidates.loc[candidates["start_date"].dt.year <= 2022]
    if len(candidates) < DEVELOPMENT_EVENT_COUNT:
        raise ValueError(
            f"Only {len(candidates)} pre-2023 development events are available; "
            f"expected {DEVELOPMENT_EVENT_COUNT}."
        )

    series = load_series()
    prepared = []
    exclusions = []
    for _, event in candidates.iterrows():
        if len(prepared) == DEVELOPMENT_EVENT_COUNT:
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
            date = pd.Timestamp(event["start_date"])
            metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
                "rank"
            ).head(5)
            metadata = metadata.copy()
            metadata.index = donors.columns
            prior = donor_weights(metadata)
            calibration = slice(
                date - pd.Timedelta(days=180), date - pd.Timedelta(days=15)
            )
            initial_weights = reliability_constrained_weights(
                target.loc[calibration], donors.loc[calibration], prior
            )
            # Complete-case eligibility is stricter than the initial gate.
            estimate_metadata_anchor(target, donors, initial_weights, date)
            prepared.append(
                (event_id, target, donors, prior, date, pre_scale(target, date) * 2)
            )
        except ValueError as error:
            exclusions.append({"anchor_id": event_id, "reason": str(error)})
            print(f"Excluded {event_id}: {error}")

    pd.DataFrame(exclusions).to_csv(EXCLUSIONS_PATH, index=False)
    if len(prepared) < DEVELOPMENT_EVENT_COUNT:
        raise RuntimeError(
            f"Only {len(prepared)} complete-case development events were available; "
            f"expected {DEVELOPMENT_EVENT_COUNT}. See {EXCLUSIONS_PATH}."
        )

    rows = []
    for ridge_penalty in RIDGE_PENALTIES:
        for prior_penalty in PRIOR_PENALTIES:
            errors = []
            for event_id, target, donors, prior, date, magnitude in prepared:
                calibration = slice(
                    date - pd.Timedelta(days=180), date - pd.Timedelta(days=15)
                )
                weights = reliability_constrained_weights(
                    target.loc[calibration],
                    donors.loc[calibration],
                    prior,
                    ridge_penalty=ridge_penalty,
                    prior_penalty=prior_penalty,
                )
                errors.append(local_injection_error(target, donors, weights, date, magnitude))
            rows.append(
                {
                    "ridge_penalty": ridge_penalty,
                    "prior_penalty": prior_penalty,
                    "development_events": len(errors),
                    "local_effect_mae_log": float(np.mean(errors)),
                    "local_effect_median_ae_log": float(np.median(errors)),
                }
            )
            print(
                f"ridge={ridge_penalty:g}, prior={prior_penalty:g}, "
                f"MAE={np.mean(errors):.6f}"
            )

    results = pd.DataFrame(rows).sort_values(
        ["local_effect_mae_log", "local_effect_median_ae_log"], kind="stable"
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT_PATH, index=False)
    print("\nSelected development configuration:")
    print(results.head(1).to_string(index=False))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
