"""Run the reproducible MetaShift-Bench synthetic evaluation on stable regimes.

Synthetic effects are injected only at pseudo-anchors constructed in stable
target and donor method regimes. The configured calibration partition selects
thresholds; the disjoint evaluation partition supplies reported metrics.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.baselines import (  # noqa: E402
    bayesian_mean_shift,
    before_after_median,
    cusum_change_point,
    pelt_change_points,
    rolling_median_change_point,
)
from metashift.counterfactual import (  # noqa: E402
    cross_validated_reliability_weights,
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)
from metashift.metrics import (  # noqa: E402
    classification_metrics,
    cluster_bootstrap_difference,
    metrics_as_dict,
    select_macro_f1_threshold,
)
from metashift.synthetic import (  # noqa: E402
    PerturbationKind,
    benchmark_seed,
    inject_perturbation,
)
from run_feasibility_prototype import load_series, synthetic_control_weights  # noqa: E402


CASES_PATH = Path("artifacts/stable_synthetic_cases.csv")
DONORS_PATH = Path("artifacts/stable_synthetic_case_donors.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
DEFAULT_MULTIPLIERS = (0.5, 1.0, 1.5, 2.0, 3.0)
EFFECT_METHODS = (
    "before_after_median",
    "nearest_neighbor_did",
    "standard_synthetic_control",
    "metashift_v1_fixed",
    "metashift_v2_cv",
)
META_METHODS = ("metashift_v1_fixed", "metashift_v2_cv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate baselines and MetaShift on stable synthetic pseudo-anchors."
    )
    parser.add_argument(
        "--case-split",
        choices=("all", "calibration", "evaluation"),
        default="all",
        help="Run both split partitions by default so thresholds are calibrated separately.",
    )
    parser.add_argument("--case-count", type=int, default=None)
    parser.add_argument(
        "--magnitude-multipliers",
        nargs="+",
        type=float,
        default=list(DEFAULT_MULTIPLIERS),
    )
    parser.add_argument("--label", default="stable_v1")
    return parser.parse_args()


def load_cases(split: str, case_count: int | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cases = pd.read_csv(CASES_PATH, dtype="string")
    cases["pseudo_anchor_date"] = pd.to_datetime(cases["pseudo_anchor_date"])
    donors = pd.read_csv(DONORS_PATH, dtype="string")
    for column in (
        "rank",
        "distance_km",
        "pre_transition_paired_days",
        "pre_transition_log_correlation",
    ):
        donors[column] = pd.to_numeric(donors[column])
    if split != "all":
        cases = cases.loc[cases["split"] == split].copy()
    if case_count is not None:
        cases = cases.groupby("split", group_keys=False).head(case_count).copy()
    if cases.empty:
        raise ValueError("No stable cases match the requested split.")
    return cases, donors


def donor_inputs(
    case_id: str,
    donor_records: pd.DataFrame,
    series: dict[tuple[str, str, str, str], pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = donor_records.loc[donor_records["case_id"] == case_id].sort_values(
        "rank"
    )
    if len(selected) < 3:
        raise ValueError("Stable case lacks three recorded donors.")
    columns: dict[str, pd.Series] = {}
    for _, row in selected.iterrows():
        key = (
            str(row["control_state_code"]),
            str(row["control_county_code"]),
            str(row["control_site_num"]),
            str(row["control_poc"]),
        )
        if key not in series:
            raise KeyError(f"Donor series absent from canonical data: {key}")
        columns["-".join(key)] = series[key]
    metadata = selected.copy()
    metadata.index = list(columns)
    return pd.DataFrame(columns).sort_index(), metadata


def robust_pre_scale(target: pd.Series, date: pd.Timestamp) -> float:
    values = target.loc[
        date - pd.Timedelta(days=180) : date - pd.Timedelta(days=15)
    ].dropna()
    if len(values) < 60:
        raise ValueError("Stable case lacks 60 target calibration observations.")
    median = float(np.median(values))
    return max(1.4826 * float(np.median(np.abs(values - median))), 0.5)


def fit_comparative_weights(
    target: pd.Series,
    donors: pd.DataFrame,
    metadata: pd.DataFrame,
    date: pd.Timestamp,
) -> dict[str, pd.Series]:
    prior = donor_weights(metadata)
    calibration = slice(date - pd.Timedelta(days=180), date - pd.Timedelta(days=15))
    nearest = pd.Series(0.0, index=donors.columns)
    nearest.iloc[0] = 1.0
    return {
        "nearest_neighbor_did": nearest,
        "standard_synthetic_control": synthetic_control_weights(target, donors, date),
        "metashift_v1_fixed": reliability_constrained_weights(
            target.loc[calibration],
            donors.loc[calibration],
            prior,
            ridge_penalty=0.1,
            prior_penalty=0.1,
        ),
        "metashift_v2_cv": cross_validated_reliability_weights(
            target.loc[calibration], donors.loc[calibration], prior
        ).weights,
    }


def observed_window(
    target: pd.Series, date: pd.Timestamp
) -> tuple[pd.Series, int]:
    window = target.loc[
        date - pd.Timedelta(days=60) : date + pd.Timedelta(days=59)
    ].dropna()
    split_index = int((window.index < date).sum())
    if len(window) < 80 or split_index < 30 or len(window) - split_index < 30:
        raise ValueError("Single-station method lacks a complete comparison window.")
    return np.log1p(window.clip(lower=0.0)), split_index


def nearest_change_days(
    dates: pd.DatetimeIndex, indices: tuple[int, ...], date: pd.Timestamp
) -> float:
    if not indices:
        return np.nan
    candidate_dates = [
        pd.Timestamp(dates[min(index, len(dates) - 1)]) for index in indices
    ]
    return float(min(abs((candidate - date).days) for candidate in candidate_dates))


def single_station_results(
    target: pd.Series,
    date: pd.Timestamp,
) -> list[dict[str, float | str | None]]:
    values, split_index = observed_window(target, date)
    before_after = before_after_median(values.to_numpy(), split_index, min_size=30)
    bayes = bayesian_mean_shift(values.to_numpy(), split_index, min_size=30)
    cusum = cusum_change_point(values.to_numpy(), min_size=30)
    rolling = rolling_median_change_point(values.to_numpy(), window=30, min_size=30)
    pelt = pelt_change_points(values.to_numpy(), min_size=30)
    pelt_distance = nearest_change_days(values.index, pelt.change_indices, date)
    return [
        {
            "method": "before_after_median",
            "estimated_log_effect": before_after.effect,
            "ranking_score": before_after.score,
            "detected_change_distance_days": 0.0,
        },
        {
            "method": "bayesian_mean_shift",
            "estimated_log_effect": bayes.effect,
            "ranking_score": bayes.score,
            "detected_change_distance_days": 0.0,
        },
        {
            "method": "cusum",
            "estimated_log_effect": np.nan,
            "ranking_score": float(cusum.strongest_score or 0.0),
            "detected_change_distance_days": nearest_change_days(
                values.index, cusum.change_indices, date
            ),
        },
        {
            "method": "rolling_mad",
            "estimated_log_effect": np.nan,
            "ranking_score": float(rolling.strongest_score or 0.0),
            "detected_change_distance_days": nearest_change_days(
                values.index, rolling.change_indices, date
            ),
        },
        {
            "method": "pelt",
            "estimated_log_effect": np.nan,
            "ranking_score": 0.0
            if np.isnan(pelt_distance)
            else 1.0 / (1.0 + pelt_distance),
            "detected_change_distance_days": pelt_distance,
        },
    ]


def variant_specs(scale: float, multiplier: float) -> tuple[tuple[PerturbationKind, float, str], ...]:
    """Produce five local shapes and matched shared-environmental controls."""

    additive = scale * 2 * multiplier
    proportional = 0.15 * multiplier
    variance = 0.5 * multiplier
    return (
        (PerturbationKind.ADDITIVE_STEP, additive, "additive_step"),
        (PerturbationKind.REGIONAL_ADDITIVE_STEP, additive, "additive_step"),
        (PerturbationKind.PROPORTIONAL_STEP, proportional, "proportional_step"),
        (
            PerturbationKind.REGIONAL_PROPORTIONAL_STEP,
            proportional,
            "proportional_step",
        ),
        (PerturbationKind.GRADUAL_DRIFT, additive, "gradual_drift"),
        (
            PerturbationKind.REGIONAL_GRADUAL_DRIFT,
            additive,
            "gradual_drift",
        ),
        (PerturbationKind.TEMPORARY_STEP, additive, "temporary_step"),
        (
            PerturbationKind.REGIONAL_TEMPORARY_STEP,
            additive,
            "temporary_step",
        ),
        (PerturbationKind.VARIANCE_INCREASE, variance, "variance_increase"),
        (
            PerturbationKind.REGIONAL_VARIANCE_INCREASE,
            variance,
            "variance_increase",
        ),
    )


def is_local(kind: PerturbationKind) -> bool:
    return not kind.value.startswith("regional_")


def expected_local_effect(
    original_target: pd.Series,
    changed_target: pd.Series,
    date: pd.Timestamp,
    kind: PerturbationKind,
) -> float:
    """Return the known 60-day median local level effect, or NaN for variance."""

    if "variance" in kind.value:
        return np.nan
    if not is_local(kind):
        return 0.0
    original = np.log1p(
        original_target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0.0)
    )
    changed = np.log1p(
        changed_target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0.0)
    )
    paired = pd.concat(
        [original.rename("original"), changed.rename("changed")],
        axis="columns",
        sort=False,
    ).dropna()
    return float(np.median(paired["changed"] - paired["original"]))


def evaluate_variant(
    case: pd.Series,
    target: pd.Series,
    donors: pd.DataFrame,
    weights: dict[str, pd.Series],
    kind: PerturbationKind,
    magnitude: float,
    family: str,
    seed: int,
) -> list[dict[str, object]]:
    date = pd.Timestamp(case["pseudo_anchor_date"])
    changed_target, changed_donors, _ = inject_perturbation(
        target, donors, date, kind, magnitude, random_seed=seed
    )
    local = is_local(kind)
    true_effect = expected_local_effect(target, changed_target, date, kind)
    rows: list[dict[str, object]] = []

    for method, method_weights in weights.items():
        estimate = estimate_metadata_anchor(
            changed_target, changed_donors, method_weights, date
        )
        rows.append(
            {
                "method": method,
                "estimated_log_effect": estimate.log_effect,
                "ranking_score": abs(estimate.standardized_score),
                "detected_change_distance_days": 0.0,
                "pre_fit_rmse": estimate.calibration_residual_rmse,
            }
        )
    rows.extend(single_station_results(changed_target, date))

    common = {
        "case_id": case["case_id"],
        "case_source": case.get("case_source", "unspecified"),
        "split": case["split"],
        "target_state": case["State Code"],
        "pseudo_anchor_date": date.date().isoformat(),
        "perturbation": kind.value,
        "perturbation_family": family,
        "is_local": int(local),
        "magnitude": magnitude,
        "true_local_log_effect": true_effect,
        "random_seed": seed,
    }
    for row in rows:
        estimate = row["estimated_log_effect"]
        if np.isfinite(true_effect) and np.isfinite(estimate):
            row["absolute_effect_error"] = abs(float(estimate) - true_effect)
        else:
            row["absolute_effect_error"] = np.nan
        row.update(common)
    return rows


def summarize(
    result: pd.DataFrame, label: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calibrate each method threshold, then evaluate only held-out cases."""

    threshold_rows = []
    metrics_rows = []
    bootstrap_rows = []
    for method, all_method in result.groupby("method", sort=True):
        calibration = all_method.loc[all_method["split"] == "calibration"]
        evaluation = all_method.loc[all_method["split"] == "evaluation"]
        threshold = select_macro_f1_threshold(
            calibration["is_local"].to_numpy(),
            calibration["ranking_score"].to_numpy(),
        )
        threshold_rows.append(
            {
                "method": method,
                "calibration_instances": len(calibration),
                "threshold": threshold,
            }
        )
        summary = metrics_as_dict(
            classification_metrics(
                evaluation["is_local"].to_numpy(),
                evaluation["ranking_score"].to_numpy(),
                threshold,
            )
        )
        effects = evaluation.loc[
            (evaluation["is_local"] == 1)
            & evaluation["true_local_log_effect"].notna(),
            "absolute_effect_error",
        ].dropna()
        metrics_rows.append(
            {
                "method": method,
                "evaluation_instances": len(evaluation),
                "evaluation_effect_instances": len(effects),
                "local_effect_mae_log": float(effects.mean()) if len(effects) else np.nan,
                **summary,
            }
        )

        for family, group in evaluation.groupby("perturbation_family", sort=True):
            if group["is_local"].nunique() != 2:
                continue
            family_metrics = metrics_as_dict(
                classification_metrics(
                    group["is_local"].to_numpy(),
                    group["ranking_score"].to_numpy(),
                    threshold,
                )
            )
            family_effects = group.loc[
                (group["is_local"] == 1)
                & group["true_local_log_effect"].notna(),
                "absolute_effect_error",
            ].dropna()
            metrics_rows.append(
                {
                    "method": method,
                    "evaluation_instances": len(group),
                    "evaluation_effect_instances": len(family_effects),
                    "local_effect_mae_log": float(family_effects.mean())
                    if len(family_effects)
                    else np.nan,
                    "perturbation_family": family,
                    **family_metrics,
                }
            )

    thresholds = pd.DataFrame(threshold_rows)
    metrics = pd.DataFrame(metrics_rows)
    calibration_effects = result.loc[
        (result["split"] == "calibration")
        & result["method"].isin(EFFECT_METHODS)
        & (result["is_local"] == 1)
        & result["true_local_log_effect"].notna()
    ]
    baseline_maes = (
        calibration_effects.groupby("method")["absolute_effect_error"].mean().sort_values()
    )
    baseline_maes = baseline_maes.drop(labels=list(META_METHODS), errors="ignore")
    best_baseline = str(baseline_maes.index[0])
    evaluation_effects = result.loc[
        (result["split"] == "evaluation")
        & result["method"].isin((*META_METHODS, best_baseline))
        & (result["is_local"] == 1)
        & result["true_local_log_effect"].notna()
    ]
    for meta_method in META_METHODS:
        paired = evaluation_effects.pivot_table(
            index=["case_id", "perturbation", "magnitude", "random_seed"],
            columns="method",
            values="absolute_effect_error",
            aggfunc="first",
        ).dropna(subset=[meta_method, best_baseline])
        point, lower, upper = cluster_bootstrap_difference(
            paired.index.get_level_values("case_id").to_numpy(),
            paired[meta_method].to_numpy(),
            paired[best_baseline].to_numpy(),
        )
        bootstrap_rows.append(
            {
                "comparison": f"{meta_method} minus {best_baseline}",
                "evaluation_effect_instances": len(paired),
                "clusters": paired.index.get_level_values("case_id").nunique(),
                "mae_difference_log": point,
                "bootstrap_95ci_lower": lower,
                "bootstrap_95ci_upper": upper,
                "best_baseline_selected_on_calibration": best_baseline,
            }
        )
    return thresholds, metrics, pd.DataFrame(bootstrap_rows)


def main() -> None:
    args = parse_args()
    if args.case_count is not None and args.case_count <= 0:
        raise ValueError("--case-count must be positive.")
    if any(value <= 0 for value in args.magnitude_multipliers):
        raise ValueError("--magnitude-multipliers values must be positive.")
    label = re.sub(r"[^a-zA-Z0-9_-]+", "_", args.label).strip("_")
    if not label:
        raise ValueError("--label must contain a letter or number.")

    cases, donor_records = load_cases(args.case_split, args.case_count)
    if args.case_split != "all":
        raise ValueError(
            "Primary benchmark requires --case-split all to keep calibration and "
            "evaluation metrics separate."
        )
    if set(cases["split"]) != {"calibration", "evaluation"}:
        raise ValueError("Stable cases must contain calibration and evaluation splits.")
    series = load_series()
    results: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []

    for case_index, (_, case) in enumerate(cases.iterrows(), start=1):
        try:
            target_key = tuple(str(case[column]) for column in SERIES_KEYS)
            target = series[target_key]
            donors, metadata = donor_inputs(str(case["case_id"]), donor_records, series)
            date = pd.Timestamp(case["pseudo_anchor_date"])
            weights = fit_comparative_weights(target, donors, metadata, date)
            scale = robust_pre_scale(target, date)
            observed_window(target, date)
            for multiplier_index, multiplier in enumerate(args.magnitude_multipliers):
                for variant_index, (kind, magnitude, family) in enumerate(
                    variant_specs(scale, multiplier)
                ):
                    seed = benchmark_seed(
                        case_index, multiplier_index, variant_index
                    )
                    results.extend(
                        evaluate_variant(
                            case,
                            target,
                            donors,
                            weights,
                            kind,
                            magnitude,
                            family,
                            seed,
                        )
                    )
            print(f"Completed stable synthetic case {case_index}/{len(cases)}: {case['case_id']}")
        except (KeyError, RuntimeError, ValueError) as error:
            exclusions.append({"case_id": str(case["case_id"]), "reason": str(error)})
            print(f"Excluded stable synthetic case {case['case_id']}: {error}")

    if exclusions:
        raise RuntimeError(
            f"{len(exclusions)} prebuilt stable cases failed at execution; refusing "
            "to produce incomplete benchmark metrics."
        )
    result = pd.DataFrame(results)
    thresholds, metrics, bootstrap = summarize(result, label)
    artifacts = Path("artifacts")
    result.to_csv(artifacts / f"stable_synthetic_{label}_event_results.csv", index=False)
    thresholds.to_csv(artifacts / f"stable_synthetic_{label}_thresholds.csv", index=False)
    metrics.to_csv(artifacts / f"stable_synthetic_{label}_metrics.csv", index=False)
    bootstrap.to_csv(artifacts / f"stable_synthetic_{label}_bootstrap.csv", index=False)
    print("\nEvaluation aggregate metrics:")
    print(
        metrics.loc[metrics["perturbation_family"].isna()]
        .sort_values("macro_f1", ascending=False)
        .to_string(index=False)
    )
    print("\nPaired bootstrap MAE differences:")
    print(bootstrap.to_string(index=False))


if __name__ == "__main__":
    main()
