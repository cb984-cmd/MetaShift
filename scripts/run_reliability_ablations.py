"""Evaluate preregistered donor-prior and regularization ablations.

This script uses the frozen stable pseudo-anchor cases. It does not select a
new algorithm; it quantifies which pre-event reliability components alter
counterfactual effect error and local-versus-regional false attribution.
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

from metashift.counterfactual import (  # noqa: E402
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
from metashift.synthetic import benchmark_seed, inject_perturbation  # noqa: E402
from run_feasibility_prototype import synthetic_control_weights  # noqa: E402
from run_stable_synthetic_benchmark import (  # noqa: E402
    DEFAULT_MULTIPLIERS,
    donor_inputs,
    expected_local_effect,
    is_local,
    load_cases,
    load_series,
    robust_pre_scale,
    variant_specs,
)


FULL_METHOD = "metashift_full_correlation_distance"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fixed MetaShift reliability-prior ablations."
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


def build_weights(
    target: pd.Series, donors: pd.DataFrame, metadata: pd.DataFrame, date: pd.Timestamp
) -> dict[str, pd.Series]:
    """Build all ablations from the identical pre-event calibration period."""

    calibration = slice(date - pd.Timedelta(days=180), date - pd.Timedelta(days=15))
    full_prior = donor_weights(metadata)
    correlation_only = donor_weights(
        metadata, use_correlation=True, use_distance=False
    )
    distance_only = donor_weights(
        metadata, use_correlation=False, use_distance=True
    )
    coverage_prior = donor_weights(
        metadata, use_correlation=True, use_distance=True, use_coverage=True
    )
    uniform_prior = pd.Series(1 / len(donors.columns), index=donors.columns)

    def constrained(
        prior: pd.Series, ridge_penalty: float = 0.1, prior_penalty: float = 0.1
    ) -> pd.Series:
        return reliability_constrained_weights(
            target.loc[calibration],
            donors.loc[calibration],
            prior,
            ridge_penalty=ridge_penalty,
            prior_penalty=prior_penalty,
        )

    return {
        "standard_synthetic_control": synthetic_control_weights(target, donors, date),
        FULL_METHOD: constrained(full_prior),
        "ablation_no_correlation": constrained(distance_only),
        "ablation_no_distance": constrained(correlation_only),
        "ablation_add_coverage": constrained(coverage_prior),
        "ablation_no_graph_prior": constrained(full_prior, prior_penalty=0.0),
        "ablation_no_ridge": constrained(full_prior, ridge_penalty=0.0),
        "ablation_ridge_0_01": constrained(full_prior, ridge_penalty=0.01),
        "ablation_ridge_1_0": constrained(full_prior, ridge_penalty=1.0),
        "ablation_uniform_prior": constrained(uniform_prior),
        "ablation_direct_reliability": full_prior,
    }


def evaluate(
    case: pd.Series,
    target: pd.Series,
    donors: pd.DataFrame,
    weights: dict[str, pd.Series],
    multipliers: list[float],
    case_index: int,
) -> list[dict[str, object]]:
    date = pd.Timestamp(case["pseudo_anchor_date"])
    scale = robust_pre_scale(target, date)
    rows = []
    for multiplier_index, multiplier in enumerate(multipliers):
        for variant_index, (kind, magnitude, family) in enumerate(
            variant_specs(scale, multiplier)
        ):
            seed = benchmark_seed(case_index, multiplier_index, variant_index)
            changed_target, changed_donors, _ = inject_perturbation(
                target, donors, date, kind, magnitude, random_seed=seed
            )
            truth = expected_local_effect(target, changed_target, date, kind)
            for method, method_weights in weights.items():
                estimate = estimate_metadata_anchor(
                    changed_target, changed_donors, method_weights, date
                )
                rows.append(
                    {
                        "case_id": case["case_id"],
                        "case_source": case.get("case_source", "unspecified"),
                        "split": case["split"],
                        "target_state": case["State Code"],
                        "method": method,
                        "perturbation": kind.value,
                        "perturbation_family": family,
                        "is_local": int(is_local(kind)),
                        "magnitude": magnitude,
                        "random_seed": seed,
                        "true_local_log_effect": truth,
                        "estimated_log_effect": estimate.log_effect,
                        "absolute_effect_error": abs(estimate.log_effect - truth)
                        if np.isfinite(truth)
                        else np.nan,
                        "ranking_score": abs(estimate.standardized_score),
                    }
                )
    return rows


def summarize(result: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for method, group in result.groupby("method", sort=True):
        calibration = group.loc[group["split"] == "calibration"]
        evaluation = group.loc[group["split"] == "evaluation"]
        threshold = select_macro_f1_threshold(
            calibration["is_local"].to_numpy(), calibration["ranking_score"].to_numpy()
        )
        metrics = metrics_as_dict(
            classification_metrics(
                evaluation["is_local"].to_numpy(),
                evaluation["ranking_score"].to_numpy(),
                threshold,
            )
        )
        local_effects = evaluation.loc[
            (evaluation["is_local"] == 1)
            & evaluation["true_local_log_effect"].notna(),
            "absolute_effect_error",
        ].dropna()
        rows.append(
            {
                "method": method,
                "evaluation_instances": len(evaluation),
                "local_effect_instances": len(local_effects),
                "local_effect_mae_log": float(local_effects.mean()),
                **metrics,
            }
        )

    metric_frame = pd.DataFrame(rows)
    bootstrap_rows = []
    evaluation = result.loc[
        (result["split"] == "evaluation")
        & (result["is_local"] == 1)
        & result["true_local_log_effect"].notna()
    ]
    for method in metric_frame["method"]:
        if method == FULL_METHOD:
            continue
        paired = evaluation.loc[evaluation["method"].isin([FULL_METHOD, method])].pivot_table(
            index=["case_id", "perturbation", "magnitude", "random_seed"],
            columns="method",
            values="absolute_effect_error",
            aggfunc="first",
        ).dropna(subset=[FULL_METHOD, method])
        point, lower, upper = cluster_bootstrap_difference(
            paired.index.get_level_values("case_id").to_numpy(),
            paired[FULL_METHOD].to_numpy(),
            paired[method].to_numpy(),
        )
        bootstrap_rows.append(
            {
                "comparison": f"{FULL_METHOD} minus {method}",
                "effect_instances": len(paired),
                "event_clusters": paired.index.get_level_values("case_id").nunique(),
                "mae_difference_log": point,
                "bootstrap_95ci_lower": lower,
                "bootstrap_95ci_upper": upper,
            }
        )
    return metric_frame, pd.DataFrame(bootstrap_rows)


def main() -> None:
    args = parse_args()
    if args.case_count is not None and args.case_count <= 0:
        raise ValueError("--case-count must be positive.")
    if any(value <= 0 for value in args.magnitude_multipliers):
        raise ValueError("All magnitude multipliers must be positive.")
    label = re.sub(r"[^a-zA-Z0-9_-]+", "_", args.label).strip("_")
    cases, donor_records = load_cases("all", args.case_count)
    if set(cases["split"]) != {"calibration", "evaluation"}:
        raise ValueError("Ablation run requires both fixed case splits.")
    series = load_series()
    results: list[dict[str, object]] = []
    for case_index, (_, case) in enumerate(cases.iterrows(), start=1):
        target_key = tuple(str(case[column]) for column in ["State Code", "County Code", "Site Num", "POC"])
        target = series[target_key]
        donors, metadata = donor_inputs(str(case["case_id"]), donor_records, series)
        weights = build_weights(target, donors, metadata, pd.Timestamp(case["pseudo_anchor_date"]))
        results.extend(
            evaluate(
                case,
                target,
                donors,
                weights,
                args.magnitude_multipliers,
                case_index,
            )
        )
        print(f"Completed reliability ablations {case_index}/{len(cases)}: {case['case_id']}")

    result = pd.DataFrame(results)
    metrics, bootstrap = summarize(result)
    artifacts = Path("artifacts")
    result.to_csv(artifacts / f"reliability_ablation_{label}_event_results.csv", index=False)
    metrics.to_csv(artifacts / f"reliability_ablation_{label}_metrics.csv", index=False)
    bootstrap.to_csv(artifacts / f"reliability_ablation_{label}_bootstrap.csv", index=False)
    print("\nAblation evaluation metrics:")
    print(metrics.sort_values("local_effect_mae_log").to_string(index=False))
    print("\nPaired bootstrap comparisons:")
    print(bootstrap.to_string(index=False))


if __name__ == "__main__":
    main()
