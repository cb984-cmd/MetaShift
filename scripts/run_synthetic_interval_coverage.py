"""Evaluate fixed bootstrap and split-conformal interval coverage on synthetic truth."""

from __future__ import annotations

import argparse
import json
import math
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
    anchor_residual_windows,
    estimate_metadata_anchor,
)
from metashift.inference import (  # noqa: E402
    block_bootstrap_median_difference,
    seed_from_identifier,
)
from metashift.synthetic import benchmark_seed, inject_perturbation  # noqa: E402
from run_feasibility_prototype import load_series  # noqa: E402
from run_stable_synthetic_benchmark import (  # noqa: E402
    SERIES_KEYS,
    donor_inputs,
    expected_local_effect,
    fit_comparative_weights,
    load_cases,
    robust_pre_scale,
    variant_specs,
)


CONFIG_PATH = Path("configs/synthetic_interval_coverage_v1.json")
EVENT_OUTPUT_PATH = Path("artifacts/synthetic_interval_coverage_v1_events.csv")
SUMMARY_OUTPUT_PATH = Path("artifacts/synthetic_interval_coverage_v1_summary.csv")
CONFORMAL_OUTPUT_PATH = Path(
    "artifacts/synthetic_interval_coverage_v1_conformal_calibration.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen synthetic interval coverage diagnostics."
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=None,
        help="Override frozen bootstrap repetitions for a smoke test only.",
    )
    parser.add_argument(
        "--max-cases-per-split",
        type=int,
        default=None,
        help="Limit each split for a smoke test only.",
    )
    parser.add_argument(
        "--label",
        default="synthetic_interval_coverage_v1",
        help="Output label; smoke tests must use a nonfinal label.",
    )
    return parser.parse_args()


def output_paths(label: str) -> tuple[Path, Path, Path]:
    """Return isolated artifact paths for one frozen or smoke interval run."""

    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", label).strip("_")
    if not safe_label:
        raise ValueError("--label must contain a letter or number.")
    return (
        Path(f"artifacts/{safe_label}_events.csv"),
        Path(f"artifacts/{safe_label}_summary.csv"),
        Path(f"artifacts/{safe_label}_conformal_calibration.csv"),
    )


def finite_sample_conformal_quantile(
    scores: np.ndarray | list[float], nominal_coverage: float
) -> float:
    """Return the finite-sample split-conformal order statistic."""

    values = np.asarray(scores, dtype=float)
    values = np.sort(values[np.isfinite(values)])
    if len(values) == 0:
        raise ValueError("Split-conformal calibration requires finite scores.")
    if not 0 < nominal_coverage < 1:
        raise ValueError("Split-conformal nominal coverage must be in (0, 1).")
    rank = min(math.ceil((len(values) + 1) * nominal_coverage), len(values))
    return float(values[rank - 1])


def calibration_quartile_labels(
    records: pd.DataFrame, value_column: str, by_method: bool
) -> pd.Series:
    """Bin a pre-event covariate using calibration-target cutoffs only."""

    labels = pd.Series(index=records.index, dtype="string")
    grouping = ["method"] if by_method else []
    groups = records.groupby(grouping, sort=True) if grouping else [(None, records)]
    for group_key, group in groups:
        calibration = (
            group.loc[group["split"] == "calibration", ["case_id", value_column]]
            .drop_duplicates("case_id")
            .dropna()
        )
        if len(calibration) < 4:
            labels.loc[group.index] = "not_applicable_smoke"
            continue
        cutoffs = np.quantile(calibration[value_column], [0.25, 0.5, 0.75])
        selected = group.index
        labels.loc[selected] = [
            f"Q{np.searchsorted(cutoffs, value, side='right') + 1}"
            for value in group[value_column]
        ]
    return labels


def add_split_conformal_intervals(
    records: pd.DataFrame, nominal_coverage: float, expected_calibration_targets: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calibrate one target-cluster error radius per method and apply it unchanged."""

    result = records.copy()
    result["conformal_radius_log"] = np.nan
    result["conformal_lower_log"] = np.nan
    result["conformal_upper_log"] = np.nan
    result["conformal_covers_truth"] = pd.NA
    calibration_rows: list[dict[str, object]] = []
    for method, group in result.groupby("method", sort=True):
        calibration = group.loc[group["split"] == "calibration"].copy()
        scores = (
            calibration.groupby("case_id", sort=True)["absolute_effect_error"]
            .max()
            .dropna()
        )
        if len(scores) != expected_calibration_targets:
            raise ValueError(
                f"{method} has {len(scores)} conformal calibration targets; expected "
                f"{expected_calibration_targets}."
            )
        radius = finite_sample_conformal_quantile(
            scores.to_numpy(), nominal_coverage
        )
        method_rows = result["method"] == method
        result.loc[method_rows, "conformal_radius_log"] = radius
        result.loc[method_rows, "conformal_lower_log"] = (
            result.loc[method_rows, "estimated_log_effect"] - radius
        )
        result.loc[method_rows, "conformal_upper_log"] = (
            result.loc[method_rows, "estimated_log_effect"] + radius
        )
        truth_available = method_rows & result["true_local_log_effect"].notna()
        result.loc[truth_available, "conformal_covers_truth"] = (
            (result.loc[truth_available, "conformal_lower_log"] <= result.loc[
                truth_available, "true_local_log_effect"
            ])
            & (result.loc[truth_available, "true_local_log_effect"] <= result.loc[
                truth_available, "conformal_upper_log"
            ])
        ).to_numpy()
        calibration_rows.append(
            {
                "method": method,
                "nominal_coverage": nominal_coverage,
                "calibration_target_sites": len(scores),
                "score_definition": (
                    "maximum absolute effect error over all fixed identifiable "
                    "perturbation instances per target site"
                ),
                "conformal_radius_log": radius,
                "minimum_calibration_score": float(scores.min()),
                "median_calibration_score": float(scores.median()),
                "maximum_calibration_score": float(scores.max()),
            }
        )
    return result, pd.DataFrame(calibration_rows)


def summarize_coverage(
    records: pd.DataFrame,
    interval_type: str,
    covered_column: str,
    width_column: str,
    nominal_coverage: float,
) -> pd.DataFrame:
    """Report target-cluster-aware coverage across predeclared descriptive strata."""

    valid = records.loc[
        records["true_local_log_effect"].notna()
        & records[covered_column].notna()
        & records[width_column].notna()
    ].copy()
    stratum_columns = (
        "perturbation_family",
        "magnitude_multiplier",
        "donor_count",
        "pre_fit_rmse_calibration_quartile",
        "target_pre_concentration_calibration_quartile",
    )
    rows: list[dict[str, object]] = []

    def append_summary(
        group: pd.DataFrame, split: str, method: str, stratum_type: str, stratum: str
    ) -> None:
        rows.append(
            {
                "interval_type": interval_type,
                "nominal_coverage": nominal_coverage,
                "split": split,
                "method": method,
                "stratum_type": stratum_type,
                "stratum": str(stratum),
                "event_instances": len(group),
                "physical_target_sites": group["case_id"].nunique(),
                "empirical_coverage": float(group[covered_column].astype(bool).mean()),
                "mean_interval_width_log": float(group[width_column].mean()),
                "median_interval_width_log": float(group[width_column].median()),
            }
        )

    for (split, method), group in valid.groupby(["split", "method"], sort=True):
        append_summary(group, split, method, "all", "all")
        for column in stratum_columns:
            for value, subgroup in group.groupby(column, dropna=False, sort=True):
                append_summary(subgroup, split, method, column, str(value))
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    bootstrap_config = config["conditional_bootstrap"]
    repetitions = (
        int(args.repetitions)
        if args.repetitions is not None
        else int(bootstrap_config["repetitions"])
    )
    if repetitions <= 0:
        raise ValueError("--repetitions must be positive.")
    if args.max_cases_per_split is not None and args.max_cases_per_split <= 0:
        raise ValueError("--max-cases-per-split must be positive.")
    event_output_path, summary_output_path, conformal_output_path = output_paths(
        args.label
    )
    if (
        args.max_cases_per_split is not None
        and event_output_path == EVENT_OUTPUT_PATH
    ):
        raise ValueError("Smoke tests must use a nonfinal --label.")
    cases, donor_records = load_cases("all", None)
    if args.max_cases_per_split is not None:
        cases = cases.groupby("split", group_keys=False).head(
            args.max_cases_per_split
        )
    expected_splits = {"calibration", "evaluation"}
    if set(cases["split"]) != expected_splits:
        raise ValueError("Interval coverage requires both stable case partitions.")
    configured_calibration_targets = int(
        config["case_partitions"]["calibration_targets"]
    )
    configured_evaluation_targets = int(config["case_partitions"]["evaluation_targets"])
    if args.max_cases_per_split is None:
        if (
            int((cases["split"] == "calibration").sum())
            != configured_calibration_targets
            or int((cases["split"] == "evaluation").sum())
            != configured_evaluation_targets
        ):
            raise ValueError("Stable case split differs from frozen interval protocol.")
    expected_calibration_targets = int((cases["split"] == "calibration").sum())
    configured_methods = tuple(config["methods"])
    allowed_families = set(config["effect_identifiable_perturbation_families"])
    configured_multipliers = tuple(float(value) for value in config["magnitude_multipliers"])
    block_length = int(bootstrap_config["block_length_observations"])
    series = load_series("88101")
    rows: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []

    for case_index, (_, case) in enumerate(cases.iterrows(), start=1):
        case_id = str(case["case_id"])
        try:
            target_key = tuple(str(case[column]) for column in SERIES_KEYS)
            target = series[target_key]
            donors, metadata = donor_inputs(case_id, donor_records, series)
            date = pd.Timestamp(case["pseudo_anchor_date"])
            weights = fit_comparative_weights(target, donors, metadata, date)
            if set(weights) != set(configured_methods):
                raise ValueError("Configured interval methods do not match fitted weights.")
            scale = robust_pre_scale(target, date)
            target_pre_median = float(
                target.loc[
                    date - pd.Timedelta(days=180) : date - pd.Timedelta(days=15)
                ].median()
            )
            for multiplier_index, multiplier in enumerate(configured_multipliers):
                for variant_index, (kind, magnitude, family) in enumerate(
                    variant_specs(scale, multiplier)
                ):
                    if family not in allowed_families:
                        continue
                    injection_seed = benchmark_seed(
                        case_index, multiplier_index, variant_index
                    )
                    changed_target, changed_donors, _ = inject_perturbation(
                        target,
                        donors,
                        date,
                        kind,
                        magnitude,
                        random_seed=injection_seed,
                    )
                    true_effect = expected_local_effect(
                        target, changed_target, date, kind
                    )
                    if not np.isfinite(true_effect):
                        continue
                    for method, method_weights in weights.items():
                        estimate = estimate_metadata_anchor(
                            changed_target, changed_donors, method_weights, date
                        )
                        windows = anchor_residual_windows(
                            changed_target, changed_donors, method_weights, date
                        )
                        bootstrap_seed = seed_from_identifier(
                            f"interval:{case_id}:{kind.value}:{multiplier}:{method}"
                        )
                        interval = block_bootstrap_median_difference(
                            windows.pre["log_residual"].to_numpy(),
                            windows.post["log_residual"].to_numpy(),
                            repetitions=repetitions,
                            block_length=block_length,
                            random_seed=bootstrap_seed,
                        )
                        if not np.isclose(
                            estimate.log_effect,
                            interval.point_estimate,
                            rtol=0.0,
                            atol=1e-12,
                        ):
                            raise RuntimeError(
                                "Bootstrap point estimate does not match anchor estimate."
                            )
                        rows.append(
                            {
                                "case_id": case_id,
                                "split": case["split"],
                                "target_state": case["State Code"],
                                "pseudo_anchor_date": date.date().isoformat(),
                                "method": method,
                                "perturbation": kind.value,
                                "perturbation_family": family,
                                "magnitude_multiplier": multiplier,
                                "injection_magnitude": magnitude,
                                "is_local": int(not kind.value.startswith("regional_")),
                                "true_local_log_effect": true_effect,
                                "estimated_log_effect": estimate.log_effect,
                                "absolute_effect_error": abs(
                                    estimate.log_effect - true_effect
                                ),
                                "conditional_ci95_lower": interval.lower_95,
                                "conditional_ci95_upper": interval.upper_95,
                                "conditional_ci95_width": (
                                    interval.upper_95 - interval.lower_95
                                ),
                                "conditional_ci95_covers_truth": (
                                    interval.lower_95
                                    <= true_effect
                                    <= interval.upper_95
                                ),
                                "bootstrap_repetitions": interval.repetitions,
                                "bootstrap_block_length_observations": interval.block_length,
                                "bootstrap_random_seed": interval.random_seed,
                                "donor_count": len(metadata),
                                "pre_fit_rmse": estimate.calibration_residual_rmse,
                                "target_pre_median_ug_m3": target_pre_median,
                                "injection_random_seed": injection_seed,
                            }
                        )
            print(f"Computed interval coverage {case_index}/{len(cases)}: {case_id}")
        except (KeyError, RuntimeError, ValueError) as error:
            exclusions.append({"case_id": case_id, "reason": str(error)})
            print(f"Excluded interval-coverage case {case_id}: {error}")

    if exclusions:
        raise RuntimeError(
            f"{len(exclusions)} stable cases failed interval coverage: {exclusions}"
        )
    records = pd.DataFrame(rows)
    expected_instances = (
        len(cases)
        * len(configured_methods)
        * len(configured_multipliers)
        * 2
        * len(allowed_families)
    )
    if len(records) != expected_instances:
        raise RuntimeError(
            f"Expected {expected_instances} coverage instances; found {len(records)}."
        )
    records["pre_fit_rmse_calibration_quartile"] = calibration_quartile_labels(
        records, "pre_fit_rmse", by_method=True
    )
    records["target_pre_concentration_calibration_quartile"] = (
        calibration_quartile_labels(
            records, "target_pre_median_ug_m3", by_method=False
        )
    )
    conformal_config = config["split_conformal"]
    records, conformal = add_split_conformal_intervals(
        records,
        float(conformal_config["nominal_coverage"]),
        expected_calibration_targets,
    )
    conditional_summary = summarize_coverage(
        records,
        "conditional_block_bootstrap",
        "conditional_ci95_covers_truth",
        "conditional_ci95_width",
        float(bootstrap_config["nominal_coverage"]),
    )
    conformal_summary = summarize_coverage(
        records.loc[records["split"] == "evaluation"],
        "split_conformal",
        "conformal_covers_truth",
        "conformal_radius_log",
        float(conformal_config["nominal_coverage"]),
    )
    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    records.to_csv(event_output_path, index=False)
    pd.concat([conditional_summary, conformal_summary], ignore_index=True).to_csv(
        summary_output_path, index=False
    )
    conformal.to_csv(conformal_output_path, index=False)
    print(
        pd.concat([conditional_summary, conformal_summary], ignore_index=True)
        .loc[lambda table: table["stratum_type"] == "all"]
        .to_string(index=False)
    )
    print(f"Wrote {event_output_path}, {summary_output_path}, and {conformal_output_path}")


if __name__ == "__main__":
    main()
