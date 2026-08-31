"""Generate MetaShift-Bench figures only from saved result artifacts."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ARTIFACTS = Path("artifacts")
OUTPUT_DIR = Path("figures")


def save_figure(
    figure: plt.Figure,
    filename: str,
    title: str,
    source: str,
    manifest: list[dict[str, str]],
) -> None:
    path = OUTPUT_DIR / filename
    figure.tight_layout()
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    manifest.append({"figure": filename, "title": title, "source_artifact": source})


def anchor_flow(manifest: list[dict[str, str]]) -> None:
    audit = pd.read_csv(ARTIFACTS / "real_transition_88101_event_audit.csv")
    counts = audit["audit_status"].value_counts().sort_values(ascending=True)
    labels = {
        "complete": "Complete comparison",
        "insufficient_geographic_donors": "<3 geographic donors",
        "estimator_input_failure": "Input-window failure",
    }
    figure, axis = plt.subplots(figsize=(7, 3.5))
    bars = axis.barh(
        [labels.get(name, name) for name in counts.index],
        counts.to_numpy(),
        color=["#3b82f6", "#f59e0b", "#ef4444"],
    )
    axis.bar_label(bars, padding=3)
    axis.set_xlabel("Method Code anchors")
    axis.set_title("AQS 88101 metadata-anchor audit flow (2019-2025)")
    axis.set_xlim(0, max(counts) * 1.15)
    save_figure(
        figure,
        "figure_1_anchor_audit_flow.png",
        "Full metadata-anchor audit flow",
        "artifacts/real_transition_88101_event_audit.csv",
        manifest,
    )


def anchor_map(manifest: list[dict[str, str]]) -> None:
    anchors = pd.read_csv(ARTIFACTS / "real_transition_88101_anchor_coordinates.csv")
    colors = {
        "supported_candidate_discontinuity": "#2563eb",
        "not_supported_by_available_evidence": "#f59e0b",
        "inconclusive_insufficient_evidence": "#94a3b8",
    }
    labels = {
        "supported_candidate_discontinuity": "Supported candidate",
        "not_supported_by_available_evidence": "Not supported",
        "inconclusive_insufficient_evidence": "Inconclusive",
    }
    figure, axis = plt.subplots(figsize=(10, 5))
    for tier, group in anchors.groupby("evidence_tier", dropna=False):
        axis.scatter(
            group["Longitude"],
            group["Latitude"],
            s=10,
            alpha=0.7,
            color=colors.get(tier, "#111827"),
            label=labels.get(tier, "Missing tier"),
        )
    axis.set_xlabel("Longitude")
    axis.set_ylabel("Latitude")
    axis.set_title("Geographic distribution of 563 AQS 88101 metadata anchors")
    axis.legend(markerscale=1.8, fontsize=8)
    axis.grid(alpha=0.2)
    save_figure(
        figure,
        "figure_2_anchor_map.png",
        "Geographic distribution of audited metadata anchors",
        "artifacts/real_transition_88101_anchor_coordinates.csv",
        manifest,
    )


def synthetic_perturbation_illustration(manifest: list[dict[str, str]]) -> None:
    path = OUTPUT_DIR / "figure_3_synthetic_perturbations.png"
    if not path.is_file():
        raise FileNotFoundError(
            "Synthetic perturbation illustration must be generated before figure manifest."
        )
    manifest.append(
        {
            "figure": path.name,
            "title": "Stable-window synthetic perturbation illustrations",
            "source_artifact": "artifacts/synthetic_perturbation_illustration_case.json",
        }
    )


def synthetic_summary(manifest: list[dict[str, str]]) -> None:
    metrics = pd.read_csv(
        ARTIFACTS / "stable_synthetic_stable_full_v2_metrics.csv"
    )
    metrics = metrics.loc[
        metrics["perturbation_family"].isna()
        & metrics["method"].isin(
            [
                "nearest_neighbor_did",
                "standard_synthetic_control",
                "metashift_v1_fixed",
                "metashift_v2_cv",
            ]
        )
    ].copy()
    labels = {
        "nearest_neighbor_did": "Nearest-neighbor DiD",
        "standard_synthetic_control": "Standard SC",
        "metashift_v1_fixed": "MetaShift fixed",
        "metashift_v2_cv": "MetaShift CV",
    }
    metrics["label"] = metrics["method"].map(labels)
    metrics = metrics.sort_values("local_effect_mae_log")
    figure, axes = plt.subplots(1, 3, figsize=(11, 3.5))
    colors = ["#2563eb" if "MetaShift" in label else "#64748b" for label in metrics["label"]]
    axes[0].bar(metrics["label"], metrics["local_effect_mae_log"], color=colors)
    axes[0].set_title("Local-effect MAE")
    axes[0].set_ylabel("MAE on log(1 + PM2.5)")
    axes[1].bar(metrics["label"], metrics["macro_f1"], color=colors)
    axes[1].set_title("Local vs regional macro-F1")
    axes[1].set_ylim(0, 1)
    axes[2].bar(metrics["label"], metrics["false_positive_rate"], color=colors)
    axes[2].set_title("Regional false-attribution rate")
    axes[2].set_ylim(0, 1)
    for axis in axes:
        axis.tick_params(axis="x", rotation=30)
        axis.grid(axis="y", alpha=0.25)
    save_figure(
        figure,
        "figure_4_stable_synthetic_summary.png",
        "Threshold-isolated stable synthetic benchmark",
        "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
        manifest,
    )


def synthetic_by_family(manifest: list[dict[str, str]]) -> None:
    metrics = pd.read_csv(
        ARTIFACTS / "stable_synthetic_stable_full_v2_metrics.csv"
    )
    metrics = metrics.loc[
        metrics["perturbation_family"].notna()
        & metrics["method"].isin(
            ["standard_synthetic_control", "metashift_v1_fixed", "metashift_v2_cv"]
        )
    ]
    families = [
        "additive_step",
        "proportional_step",
        "gradual_drift",
        "temporary_step",
        "variance_increase",
    ]
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    for method, label, color in (
        ("standard_synthetic_control", "Standard SC", "#64748b"),
        ("metashift_v1_fixed", "MetaShift fixed", "#2563eb"),
        ("metashift_v2_cv", "MetaShift CV", "#7c3aed"),
    ):
        subset = metrics.loc[metrics["method"] == method].set_index(
            "perturbation_family"
        )
        axes[0].plot(
            families,
            [subset.loc[family, "local_effect_mae_log"] for family in families],
            marker="o",
            label=label,
            color=color,
        )
        axes[1].plot(
            families,
            [subset.loc[family, "macro_f1"] for family in families],
            marker="o",
            label=label,
            color=color,
        )
    axes[0].set_title("Effect error by perturbation family")
    axes[0].set_ylabel("Local-effect MAE")
    axes[1].set_title("Attribution macro-F1 by family")
    axes[1].set_ylim(0, 1)
    for axis in axes:
        axis.tick_params(axis="x", rotation=25)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    save_figure(
        figure,
        "figure_5_synthetic_by_family.png",
        "Stable synthetic benchmark by perturbation family",
        "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
        manifest,
    )


def reliability_ablation(manifest: list[dict[str, str]]) -> None:
    metrics = pd.read_csv(
        ARTIFACTS / "reliability_ablation_stable_full_v2_metrics.csv"
    ).sort_values("local_effect_mae_log")
    figure, axis = plt.subplots(figsize=(9, 4))
    colors = [
        "#2563eb" if value == "metashift_full_correlation_distance" else "#94a3b8"
        for value in metrics["method"]
    ]
    bars = axis.barh(metrics["method"], metrics["local_effect_mae_log"], color=colors)
    axis.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    axis.set_xlabel("Local-effect MAE on log(1 + PM2.5)")
    axis.set_title("Reliability-prior and regularization ablations")
    axis.grid(axis="x", alpha=0.25)
    save_figure(
        figure,
        "figure_6_reliability_ablations.png",
        "Reliability ablation effect error",
        "artifacts/reliability_ablation_stable_full_v2_metrics.csv",
        manifest,
    )


def placebo_distribution(manifest: list[dict[str, str]]) -> None:
    scores = pd.read_csv(ARTIFACTS / "time_placebo_scores.csv")
    actual = scores.loc[
        scores["date_type"] == "actual_method_code_anchor", "standardized_score"
    ]
    placebo = scores.loc[
        scores["date_type"] == "post_transition_time_placebo", "standardized_score"
    ]
    figure, axis = plt.subplots(figsize=(7, 3.5))
    upper = max(actual.quantile(0.98), placebo.quantile(0.98))
    bins = np.linspace(0, upper, 35)
    axis.hist(placebo, bins=bins, alpha=0.65, label="Stable post-transition placebo")
    axis.hist(actual, bins=bins, alpha=0.65, label="Method Code anchor")
    axis.set_xlabel("Absolute standardized residual score")
    axis.set_ylabel("Event-date observations")
    axis.set_title("Time-placebo calibration of real metadata anchors")
    axis.legend()
    save_figure(
        figure,
        "figure_7_time_placebo_distribution.png",
        "Real anchor and time-placebo score distribution",
        "artifacts/time_placebo_scores.csv",
        manifest,
    )


def real_effect_distribution(manifest: list[dict[str, str]]) -> None:
    results = pd.read_csv(ARTIFACTS / "real_transition_88101_method_results.csv")
    subset = results.loc[results["method"] == "metashift_v1_fixed"]
    figure, axis = plt.subplots(figsize=(7, 3.5))
    axis.hist(subset["log_effect"].dropna(), bins=35, color="#2563eb", alpha=0.8)
    axis.axvline(0, color="black", linewidth=1)
    axis.set_xlabel("Estimated 60-day log residual effect")
    axis.set_ylabel("Metadata anchors")
    axis.set_title("Observational MetaShift estimates across complete anchors")
    save_figure(
        figure,
        "figure_8_real_effect_distribution.png",
        "Real metadata-anchor effect distribution",
        "artifacts/real_transition_88101_method_results.csv",
        manifest,
    )


def interval_and_donor_sensitivity(manifest: list[dict[str, str]]) -> None:
    intervals = pd.read_csv(ARTIFACTS / "real_transition_88101_event_intervals.csv")
    nested = pd.read_csv(
        ARTIFACTS / "real_transition_88101_nested_selection_intervals.csv"
    )
    leave_one_out = pd.read_csv(ARTIFACTS / "leave_one_donor_out_summary.csv")
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.5))

    interval_summary = intervals.groupby("method")["ci_excludes_zero"].mean()
    labels = interval_summary.index.str.replace("_", " ")
    positions = np.arange(len(labels))
    axes[0].barh(
        positions,
        interval_summary.to_numpy(),
        color="#94a3b8",
        label="Fixed-weight conditional CI",
    )
    meta_position = list(interval_summary.index).index("metashift_v1_fixed")
    axes[0].barh(
        meta_position,
        nested["selection_ci_excludes_zero"].mean(),
        color="#2563eb",
        label="MetaShift selection-aware CI",
    )
    axes[0].set_yticks(positions, labels)
    axes[0].set_xlim(0, 1)
    axes[0].set_xlabel("Fraction of 95% CIs excluding zero")
    axes[0].set_title("Fixed-weight and selection-aware event intervals")
    axes[0].legend(fontsize=7)

    complete = leave_one_out.loc[
        leave_one_out["summary_status"].isin(
            ["complete", "partial_after_donor_removal"]
        )
    ]
    axes[1].hist(
        complete["leave_one_out_max_abs_deviation"].dropna(),
        bins=30,
        color="#7c3aed",
        alpha=0.8,
    )
    axes[1].set_xlabel("Maximum leave-one-donor-out effect deviation")
    axes[1].set_ylabel("Real metadata anchors")
    axes[1].set_title("Sensitivity to removing one donor")
    save_figure(
        figure,
        "figure_9_interval_and_donor_sensitivity.png",
        "Event uncertainty and leave-one-donor-out sensitivity",
        "artifacts/real_transition_88101_event_intervals.csv; "
        "artifacts/real_transition_88101_nested_selection_intervals.csv; "
        "artifacts/leave_one_donor_out_summary.csv",
        manifest,
    )


def evidence_tier_distribution(manifest: list[dict[str, str]]) -> None:
    tiers = pd.read_csv(ARTIFACTS / "real_transition_88101_evidence_tiers.csv")
    counts = tiers["evidence_tier"].value_counts()
    labels = {
        "supported_candidate_discontinuity": "Supported candidate",
        "not_supported_by_available_evidence": "Not supported",
        "inconclusive_insufficient_evidence": "Inconclusive",
    }
    figure, axis = plt.subplots(figsize=(7, 3.5))
    bars = axis.bar(
        [labels.get(name, name) for name in counts.index],
        counts.to_numpy(),
        color=["#2563eb", "#f59e0b", "#94a3b8"],
    )
    axis.bar_label(bars, padding=3)
    axis.set_ylabel("Metadata anchors")
    axis.set_title("Observational evidence tiers for real Method Code anchors")
    axis.tick_params(axis="x", rotation=15)
    save_figure(
        figure,
        "figure_10_real_event_evidence_tiers.png",
        "Observational real-event evidence tiers",
        "artifacts/real_transition_88101_evidence_tiers.csv",
        manifest,
    )


def evidence_tier_sensitivity(manifest: list[dict[str, str]]) -> None:
    summary = pd.read_csv(ARTIFACTS / "evidence_tier_sensitivity_summary.csv")
    labels = {
        "supported_candidate_discontinuity": "Supported",
        "not_supported_by_available_evidence": "Not supported",
        "inconclusive_insufficient_evidence": "Inconclusive",
    }
    pivot = (
        summary.assign(label=summary["evidence_tier"].map(labels))
        .pivot(index="setting", columns="label", values="anchor_count")
        .reindex(index=["strict", "primary", "lenient"])
        .fillna(0)
    )
    figure, axis = plt.subplots(figsize=(7, 3.5))
    bottom = np.zeros(len(pivot))
    colors = {
        "Supported": "#2563eb",
        "Not supported": "#f59e0b",
        "Inconclusive": "#94a3b8",
    }
    for label in ("Supported", "Not supported", "Inconclusive"):
        values = pivot[label].to_numpy() if label in pivot else np.zeros(len(pivot))
        axis.bar(pivot.index, values, bottom=bottom, label=label, color=colors[label])
        bottom += values
    axis.set_ylabel("Metadata anchors")
    axis.set_title("Evidence-tier threshold sensitivity")
    axis.legend(fontsize=8)
    save_figure(
        figure,
        "figure_11_evidence_tier_sensitivity.png",
        "Strict, primary, and lenient evidence-tier sensitivity",
        "artifacts/evidence_tier_sensitivity_summary.csv",
        manifest,
    )


def risk_coverage_curve(manifest: list[dict[str, str]]) -> None:
    curve = pd.read_csv(ARTIFACTS / "synthetic_risk_coverage_stable_full_v2.csv")
    labels = {
        "nearest_neighbor_did": "Nearest-neighbor DiD",
        "standard_synthetic_control": "Standard SC",
        "metashift_v1_fixed": "MetaShift fixed",
        "metashift_v2_cv": "MetaShift CV",
    }
    colors = {
        "nearest_neighbor_did": "#94a3b8",
        "standard_synthetic_control": "#475569",
        "metashift_v1_fixed": "#2563eb",
        "metashift_v2_cv": "#7c3aed",
    }
    figure, axis = plt.subplots(figsize=(7, 3.5))
    for method, group in curve.groupby("method", sort=True):
        group = group.sort_values("evaluation_case_coverage")
        axis.plot(
            group["evaluation_case_coverage"],
            group["local_effect_mae_log"],
            marker="o",
            label=labels[method],
            color=colors[method],
        )
    axis.set_xlabel("Evaluation-case coverage after pre-fit quality gate")
    axis.set_ylabel("Local-effect MAE on log(1 + PM2.5)")
    axis.set_title("Synthetic risk-coverage curves")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    save_figure(
        figure,
        "figure_12_synthetic_risk_coverage.png",
        "Pre-fit quality risk-coverage on independent synthetic cases",
        "artifacts/synthetic_risk_coverage_stable_full_v2.csv",
        manifest,
    )


def effect_window_sensitivity(manifest: list[dict[str, str]]) -> None:
    summary = pd.read_csv(ARTIFACTS / "effect_window_sensitivity_summary.csv")
    complete = summary.loc[summary["status"] == "complete"]
    labels = {
        "nearest_neighbor_did": "Nearest-neighbor DiD",
        "standard_synthetic_control": "Standard SC",
        "metashift_v1_fixed": "MetaShift fixed",
    }
    colors = {
        "nearest_neighbor_did": "#94a3b8",
        "standard_synthetic_control": "#475569",
        "metashift_v1_fixed": "#2563eb",
    }
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    for method, group in complete.groupby("method", sort=True):
        group = group.sort_values("comparison_window_days")
        axes[0].plot(
            group["comparison_window_days"],
            group["median_log_effect"],
            marker="o",
            label=labels[method],
            color=colors[method],
        )
        axes[1].plot(
            group["comparison_window_days"],
            group["sign_agreement_with_60_day"],
            marker="o",
            label=labels[method],
            color=colors[method],
        )
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Median real-anchor effect by window")
    axes[0].set_xlabel("Pre/post window days")
    axes[0].set_ylabel("Median log residual effect")
    axes[1].set_title("Direction agreement with 60-day effect")
    axes[1].set_xlabel("Pre/post window days")
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("Fraction of complete events")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    save_figure(
        figure,
        "figure_13_effect_window_sensitivity.png",
        "Observational effect-window sensitivity",
        "artifacts/effect_window_sensitivity_summary.csv",
        manifest,
    )


def screening_sensitivity(manifest: list[dict[str, str]]) -> None:
    summary = pd.read_csv(ARTIFACTS / "screening_sensitivity_summary.csv")
    complete = summary.loc[summary["minimum_donors_required"] == 3].copy()
    figure, axis = plt.subplots(figsize=(10, 3.5))
    axis.bar(
        complete["setting"],
        complete["eligible_anchors_after_donor_threshold"],
        color="#2563eb",
    )
    axis.axhline(
        complete.loc[complete["setting"] == "primary", "eligible_anchors_after_donor_threshold"].iloc[0],
        color="#111827",
        linestyle="--",
        linewidth=1,
        label="Primary setting",
    )
    axis.set_ylabel("Anchors with at least 3 geographic donors")
    axis.set_title("One-factor data-screening sensitivity")
    axis.tick_params(axis="x", rotation=35)
    axis.legend(fontsize=8)
    save_figure(
        figure,
        "figure_14_screening_sensitivity.png",
        "One-factor screening sensitivity with three required donors",
        "artifacts/screening_sensitivity_summary.csv",
        manifest,
    )


def reporting_scale_sensitivity(manifest: list[dict[str, str]]) -> None:
    summary = pd.read_csv(ARTIFACTS / "reporting_scale_sensitivity_summary.csv")
    labels = summary["method"].str.replace("_", " ")
    figure, axis = plt.subplots(figsize=(7, 3.5))
    bars = axis.bar(
        labels,
        summary["log_raw_direction_agreement"],
        color=["#2563eb", "#475569", "#94a3b8"],
    )
    axis.bar_label(bars, fmt="%.3f", padding=3)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Direction agreement")
    axis.set_title("Log-effect versus raw-effect direction agreement")
    axis.tick_params(axis="x", rotation=25)
    axis.grid(axis="y", alpha=0.25)
    save_figure(
        figure,
        "figure_15_reporting_scale_sensitivity.png",
        "Reporting-scale direction concordance",
        "artifacts/reporting_scale_sensitivity_summary.csv",
        manifest,
    )


def hourly_poc_validation(manifest: list[dict[str, str]]) -> None:
    summary = pd.read_csv(ARTIFACTS / "hourly_poc_validation_summary.csv")
    paired = summary.loc[
        summary["status"] == "paired_hourly_pre_post_available"
    ].copy()
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].scatter(
        paired["daily_difference_change_ug_m3"],
        paired["hourly_difference_change_ug_m3"],
        color="#2563eb",
    )
    limits = [
        min(
            paired["daily_difference_change_ug_m3"].min(),
            paired["hourly_difference_change_ug_m3"].min(),
        ),
        max(
            paired["daily_difference_change_ug_m3"].max(),
            paired["hourly_difference_change_ug_m3"].max(),
        ),
    ]
    axes[0].plot(limits, limits, color="#6b7280", linestyle="--")
    axes[0].set_xlabel("Daily POC difference change (ug/m3)")
    axes[0].set_ylabel("Hourly POC difference change (ug/m3)")
    axes[0].set_title("Same-site POC daily/hourly direction context")
    axes[0].grid(alpha=0.25)

    qualifier_columns = [
        "target_pre_qualifier_fraction",
        "target_post_qualifier_fraction",
        "reference_pre_qualifier_fraction",
        "reference_post_qualifier_fraction",
    ]
    axes[1].boxplot(
        [paired[column].dropna() for column in qualifier_columns],
        tick_labels=["T pre", "T post", "R pre", "R post"],
    )
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("Rows with nonempty Qualifier")
    axes[1].set_title("Hourly QA qualifier availability")
    axes[1].grid(axis="y", alpha=0.25)
    save_figure(
        figure,
        "figure_16_hourly_poc_validation.png",
        "Same-site hourly POC external consistency and qualifier context",
        "artifacts/hourly_poc_validation_summary.csv",
        manifest,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    anchor_flow(manifest)
    anchor_map(manifest)
    synthetic_perturbation_illustration(manifest)
    synthetic_summary(manifest)
    synthetic_by_family(manifest)
    reliability_ablation(manifest)
    placebo_distribution(manifest)
    real_effect_distribution(manifest)
    interval_and_donor_sensitivity(manifest)
    evidence_tier_distribution(manifest)
    evidence_tier_sensitivity(manifest)
    risk_coverage_curve(manifest)
    effect_window_sensitivity(manifest)
    screening_sensitivity(manifest)
    reporting_scale_sensitivity(manifest)
    hourly_poc_validation(manifest)
    with (OUTPUT_DIR / "figure_manifest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["figure", "title", "source_artifact"])
        writer.writeheader()
        writer.writerows(manifest)
    print(f"Generated {len(manifest)} figures in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
