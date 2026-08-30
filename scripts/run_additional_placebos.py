"""Run donor-as-treated and within-event date-resampling placebo analyses."""

from __future__ import annotations

import json
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
from run_feasibility_prototype import (  # noqa: E402
    event_donors,
    load_series,
    synthetic_control_weights,
)
from run_real_transition_audit import load_inputs  # noqa: E402


GATE_DIR = Path("artifacts/data_gate")
EVENT_AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
METHOD_RESULTS_PATH = Path("artifacts/real_transition_88101_method_results.csv")
TIME_PLACEBO_SCORES_PATH = Path("artifacts/time_placebo_scores.csv")
DONOR_PLACEBO_PATH = Path("artifacts/donor_as_treated_placebos.csv")
DONOR_EXCLUSIONS_PATH = Path("artifacts/donor_as_treated_exclusions.csv")
DATE_PERMUTATION_PATH = Path("artifacts/time_placebo_date_permutations.csv")
DATE_PERMUTATION_SUMMARY_PATH = Path("artifacts/time_placebo_date_permutation_summary.json")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
PERMUTATIONS = 200
RANDOM_SEED = 20260830


def donor_as_treated_placebos(
    anchors: pd.DataFrame, controls: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use each stable geographic donor as a pseudo-treated site at its target's date."""

    audit = pd.read_csv(EVENT_AUDIT_PATH, dtype="string")
    complete_ids = set(audit.loc[audit["audit_status"] == "complete", "anchor_id"])
    events = anchors.loc[anchors["anchor_id"].isin(complete_ids)]
    series = load_series("88101")
    rows: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        event_id = str(event["anchor_id"])
        date = pd.Timestamp(event["start_date"])
        try:
            donors, _ = event_donors(event_id, controls, series)
            if len(donors.columns) < 4:
                raise ValueError(
                    "Fewer than four selected donors; cannot leave three controls "
                    "after designating a donor as pseudo-treated."
                )
            for pseudo_target_name in donors.columns:
                pseudo_target = donors[pseudo_target_name]
                pseudo_controls = donors.drop(columns=pseudo_target_name)
                weights = synthetic_control_weights(pseudo_target, pseudo_controls, date)
                estimate = estimate_metadata_anchor(
                    pseudo_target, pseudo_controls, weights, date
                )
                rows.append(
                    {
                        "anchor_id": event_id,
                        "anchor_date": date.date().isoformat(),
                        "pseudo_treated_donor": pseudo_target_name,
                        "remaining_controls": len(pseudo_controls.columns),
                        "log_effect": estimate.log_effect,
                        "raw_effect_ug_m3": estimate.raw_effect,
                        "standardized_score": abs(estimate.standardized_score),
                        "pre_residual_rmse": estimate.calibration_residual_rmse,
                    }
                )
        except (KeyError, RuntimeError, ValueError) as error:
            exclusions.append({"anchor_id": event_id, "reason": str(error)})
        if position % 50 == 0 or position == len(events):
            print(f"Processed donor-as-treated placebos for {position}/{len(events)} events")
    return pd.DataFrame(rows), pd.DataFrame(exclusions)


def date_resampling_permutations() -> tuple[pd.DataFrame, dict[str, object]]:
    """Resample one post-transition placebo date per event for a global null test."""

    scores = pd.read_csv(TIME_PLACEBO_SCORES_PATH)
    actual = scores.loc[
        scores["date_type"] == "actual_method_code_anchor",
        ["anchor_id", "standardized_score"],
    ].set_index("anchor_id")["standardized_score"]
    placebo = scores.loc[
        scores["date_type"] == "post_transition_time_placebo",
        ["anchor_id", "standardized_score"],
    ].groupby("anchor_id")["standardized_score"].apply(list)
    shared_ids = actual.index.intersection(placebo.index)
    actual = actual.loc[shared_ids]
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []
    actual_mean = float(actual.mean())
    for permutation in range(PERMUTATIONS):
        sampled = np.array([rng.choice(placebo[event_id]) for event_id in shared_ids])
        differences = actual.to_numpy() - sampled
        rows.append(
            {
                "permutation": permutation,
                "events": len(shared_ids),
                "actual_mean_score": actual_mean,
                "sampled_placebo_mean_score": float(np.mean(sampled)),
                "mean_score_difference": float(np.mean(differences)),
                "median_score_difference": float(np.median(differences)),
                "fraction_actual_score_higher": float(np.mean(differences > 0)),
            }
        )
    result = pd.DataFrame(rows)
    p_value = float(
        (1 + (result["sampled_placebo_mean_score"] >= actual_mean).sum())
        / (1 + len(result))
    )
    summary = {
        "method": "within_event_post_transition_placebo_date_resampling",
        "random_seed": RANDOM_SEED,
        "permutations": PERMUTATIONS,
        "events_with_complete_time_placebos": len(shared_ids),
        "actual_mean_score": actual_mean,
        "permutation_mean_score": float(result["sampled_placebo_mean_score"].mean()),
        "global_upper_tail_p_value": p_value,
        "interpretation_boundary": (
            "This compares a Method Code anchor with stable dates after that "
            "transition using the original pre-transition donor weights. It does "
            "not identify the physical cause of any observed discontinuity."
        ),
    }
    return result, summary


def main() -> None:
    anchors, controls = load_inputs(GATE_DIR)
    donor_rows, donor_exclusions = donor_as_treated_placebos(anchors, controls)
    donor_rows.to_csv(DONOR_PLACEBO_PATH, index=False)
    donor_exclusions.to_csv(DONOR_EXCLUSIONS_PATH, index=False)
    permutations, summary = date_resampling_permutations()
    permutations.to_csv(DATE_PERMUTATION_PATH, index=False)
    DATE_PERMUTATION_SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("\nDonor-as-treated placebo status:")
    print(
        f"records={len(donor_rows)}, excluded_events={len(donor_exclusions)}, "
        f"median_score={donor_rows['standardized_score'].median():.4f}"
    )
    print("\nDate-resampling summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
