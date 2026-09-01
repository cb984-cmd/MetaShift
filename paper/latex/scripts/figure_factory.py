"""Create the revised, evidence-bound vector figures for the formal report."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd


METHOD_ORDER = (
    "standard_synthetic_control",
    "metashift_v1_fixed",
    "metashift_v2_cv",
    "nearest_neighbor_did",
)
ALL_METHOD_ORDER = (
    "standard_synthetic_control",
    "metashift_v1_fixed",
    "metashift_v2_cv",
    "nearest_neighbor_did",
    "bayesian_mean_shift",
    "before_after_median",
    "cusum",
    "rolling_mad",
    "pelt",
)
METHOD_LABELS = {
    "standard_synthetic_control": "Standard SC",
    "metashift_v1_fixed": "MetaShift fixed",
    "metashift_v2_cv": "MetaShift CV",
    "nearest_neighbor_did": "Nearest-neighbor DiD",
    "bayesian_mean_shift": "Bayesian mean shift",
    "before_after_median": "Before-after median",
    "cusum": "CUSUM",
    "pelt": "PELT",
    "rolling_mad": "Rolling MAD",
}
METHOD_COLORS = {
    "standard_synthetic_control": "#4C566A",
    "metashift_v1_fixed": "#3B82F6",
    "metashift_v2_cv": "#7C3AED",
    "nearest_neighbor_did": "#0F766E",
    "bayesian_mean_shift": "#64748B",
    "before_after_median": "#64748B",
    "cusum": "#64748B",
    "pelt": "#64748B",
    "rolling_mad": "#64748B",
}
METHOD_MARKERS = {
    "standard_synthetic_control": "o",
    "metashift_v1_fixed": "^",
    "metashift_v2_cv": "D",
    "nearest_neighbor_did": "s",
    "bayesian_mean_shift": "P",
    "before_after_median": "X",
    "cusum": "v",
    "pelt": "<",
    "rolling_mad": ">",
}
FAMILY_ORDER = (
    "additive_step",
    "proportional_step",
    "gradual_drift",
    "temporary_step",
    "variance_increase",
)
FAMILY_LABELS = {
    "additive_step": "Additive step",
    "proportional_step": "Proportional step",
    "gradual_drift": "Gradual drift",
    "temporary_step": "Temporary step",
    "variance_increase": "Variance increase",
}
TIER_COLORS = {
    "supported_candidate_discontinuity": "#2563EB",
    "not_supported_by_available_evidence": "#B45309",
    "inconclusive_insufficient_evidence": "#64748B",
}


SaveFigure = Callable[[plt.Figure, Path, str, list[str], list[dict[str, Any]]], None]
FormatDecimal = Callable[[float, int], str]


def configure_figure_style() -> None:
    """Keep labels readable after inclusion at one report-column width."""

    plt.rcParams.update(
        {
            "font.size": 9,
            "font.family": "DejaVu Serif",
            "mathtext.fontset": "dejavuserif",
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.dpi": 160,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _box(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str = "#334155",
    fontsize: float = 8.5,
    hatch: str | None = None,
    weight: str = "normal",
) -> None:
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        transform=axis.transAxes,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=0.9,
        hatch=hatch,
        clip_on=False,
    )
    axis.add_patch(patch)
    axis.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color="#FFFFFF"
        if facecolor in {"#2563EB", "#B45309", "#64748B"}
        else "#111827",
        transform=axis.transAxes,
        wrap=True,
    )


def _arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = "#475569",
    style: str = "-",
) -> None:
    axis.annotate(
        "",
        xy=end,
        xytext=start,
        xycoords="axes fraction",
        arrowprops={
            "arrowstyle": "->",
            "color": color,
            "lw": 1.1,
            "linestyle": style,
            "shrinkA": 0,
            "shrinkB": 0,
        },
    )


def _comparison_shading(axis: plt.Axes) -> None:
    axis.axvspan(-60, -1, color="#DBEAFE", alpha=0.45, linewidth=0, zorder=0)
    axis.axvspan(0, 59, color="#FDE68A", alpha=0.38, linewidth=0, zorder=0)
    axis.axvline(0, color="#B91C1C", linestyle="--", linewidth=1.0, zorder=1)


def _finalize_axes(axis: plt.Axes) -> None:
    axis.grid(axis="both", color="#CBD5E1", alpha=0.55, linewidth=0.55)
    axis.set_axisbelow(True)


def _synthetic_example_figure(
    example: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(6.6, 4.9), sharex="col")
    titles = {
        "local": "Known local injection: target only",
        "regional": "Known regional injection: target and donors",
    }
    for column, key in enumerate(("local", "regional")):
        frame = example["variants"][key]
        top, bottom = axes[:, column]
        days = frame["relative_day"]
        pre_center = float(
            np.nanmedian(
                np.log1p(
                    frame.loc[frame["relative_day"] < 0, "donor_composite"].clip(
                        lower=0.0
                    )
                )
            )
        )
        top.plot(
            days,
            np.log1p(frame["target"].clip(lower=0.0)) - pre_center,
            color="#111827",
            linewidth=1.35,
            label="Injected target",
        )
        top.plot(
            days,
            np.log1p(frame["donor_composite"].clip(lower=0.0)) - pre_center,
            color="#4C566A",
            linewidth=1.2,
            linestyle="--",
            label="Fixed donor composite",
        )
        _comparison_shading(top)
        top.set_title(titles[key], fontweight="bold")
        top.set_ylabel(r"Centered $\log(1+\mathrm{PM}_{2.5})$")
        _finalize_axes(top)

        bottom.plot(days, frame["residual"], color="#7C3AED", linewidth=1.25)
        _comparison_shading(bottom)
        bottom.axhline(0, color="#111827", linewidth=0.8)
        bottom.set_xlabel("Days relative to pseudo-anchor")
        bottom.set_ylabel("Centered log residual")
        bottom.set_xlim(-60, 60)
        _finalize_axes(bottom)
    axes[0, 0].legend(loc="upper left", frameon=False)
    figure.suptitle(
        "Data-derived stable-window illustration (lexicographically first held-out case)",
        fontsize=10.5,
        y=0.995,
    )
    figure.text(
        0.5,
        0.01,
        "Blue: 60-day pre window. Amber: 60-day post window. "
        f"Frozen additive magnitude = {example['magnitude']:.2f} ug/m3.",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.045, 1, 0.955))
    save_figure(
        figure,
        figures / "fig_stable_synthetic_example.pdf",
        "Data-derived stable-window local and regional synthetic example",
        [
            "paper/latex/configs/synthetic_motivating_example_v1.json",
            "artifacts/stable_synthetic_cases.csv",
            "artifacts/stable_synthetic_case_donors.csv",
            "paper/latex/configs/case_study_rendering_v2.json",
        ],
        outputs,
    )


def _donor_construction_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    audit = data["audit"]
    donor_counts = pd.to_numeric(audit["geographic_control_candidates"], errors="raise")
    categories = pd.cut(
        donor_counts,
        bins=[-1, 0, 1, 2, np.inf],
        labels=["0", "1", "2", "3+"],
    ).value_counts().reindex(["0", "1", "2", "3+"], fill_value=0)
    figure, axes = plt.subplots(1, 2, figsize=(6.6, 3.15), gridspec_kw={"width_ratios": [1.12, 0.88]})
    schematic, distribution = axes
    schematic.axis("off")
    _box(
        schematic,
        0.17,
        0.64,
        0.25,
        0.22,
        "Target series\n(physical site, POC)",
        facecolor="#E0F2FE",
    )
    _box(
        schematic,
        0.17,
        0.25,
        0.25,
        0.18,
        "Same-site alternate POC\nexcluded as a donor",
        facecolor="#FEE2E2",
        edgecolor="#B91C1C",
        hatch="//",
    )
    _arrow(schematic, (0.17, 0.52), (0.17, 0.36), color="#B91C1C", style="--")
    for x, label in (
        (0.48, "Donor site A\none ranked POC"),
        (0.70, "Donor site B\none ranked POC"),
        (0.91, "Donor site C+\none ranked POC"),
    ):
        _box(schematic, x, 0.64, 0.18, 0.22, label, facecolor="#DCFCE7", fontsize=8)
        _arrow(schematic, (0.30, 0.64), (x - 0.10, 0.64))
    schematic.text(
        0.53,
        0.16,
        "Physical identity = State + County + Site.\nAt most one POC is retained per donor site.",
        ha="center",
        va="center",
        fontsize=8,
        transform=schematic.transAxes,
    )
    schematic.set_title("Distinct physical-donor construction", fontweight="bold")

    bars = distribution.bar(
        categories.index.astype(str),
        categories.to_numpy(),
        color=["#94A3B8", "#CBD5E1", "#F59E0B", "#0F766E"],
        edgecolor="#334155",
        linewidth=0.5,
    )
    for bar, value in zip(bars, categories.to_numpy(), strict=True):
        distribution.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            str(int(value)),
            ha="center",
            va="bottom",
            fontsize=8,
        )
    distribution.set_ylim(bottom=0)
    distribution.set_xlabel("Prequalified distinct donors")
    distribution.set_ylabel("Metadata anchors")
    distribution.set_title("Availability before input-window checks", fontweight="bold")
    _finalize_axes(distribution)
    figure.tight_layout()
    save_figure(
        figure,
        figures / "fig_donor_construction.pdf",
        "Physical donor construction and frozen availability",
        [
            "configs/benchmark_release_v2.json",
            "artifacts/real_transition_88101_event_audit.csv",
        ],
        outputs,
    )


def _window_protocol_figure(
    window_config: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    windows = window_config["windows"]
    figure, axis = plt.subplots(figsize=(6.6, 2.8))
    rows = (
        ("Calibration / fitting / residual centering", "calibration", "#C7D2FE"),
        ("Effect pre window", "pre", "#DBEAFE"),
        ("Effect post window", "post", "#FDE68A"),
    )
    for y, (label, key, color) in enumerate(rows[::-1]):
        record = windows[key]
        start = int(record["start_offset_days"])
        end = int(record["end_offset_days"])
        axis.broken_barh([(start, end - start + 1)], (y - 0.32, 0.64), facecolors=color, edgecolors="#334155")
        axis.text(
            start + (end - start + 1) / 2,
            y,
            f"{start} to {end} ({record['inclusive_calendar_dates']} dates)",
            ha="center",
            va="center",
            fontsize=8,
        )
    axis.axvspan(-60, -15, color="#F59E0B", alpha=0.18, zorder=0)
    axis.axvline(0, color="#B91C1C", linestyle="--", linewidth=1.1)
    axis.text(2, 2.36, r"$t_0$ anchor", color="#B91C1C", fontsize=8)
    axis.text(
        -37.5,
        -0.67,
        f"{windows['calibration_pre_overlap_calendar_dates']}-date calibration/pre overlap",
        ha="center",
        va="top",
        fontsize=8,
        color="#92400E",
    )
    axis.set_yticks(range(3), [label for label, _, _ in rows[::-1]])
    axis.set_xlim(-250, 80)
    axis.set_xticks([-240, -180, -120, -60, 0, 60])
    axis.set_xlabel(r"Calendar-day offset from $t_0$")
    axis.set_ylim(-0.95, 2.65)
    axis.set_title("Inclusive date-window implementation for the frozen audit", fontweight="bold")
    _finalize_axes(axis)
    figure.tight_layout()
    save_figure(
        figure,
        figures / "fig_window_protocol.pdf",
        "Frozen inclusive date-window protocol",
        [
            "paper/latex/configs/window_protocol_audit_v1.json",
            "metashift/counterfactual.py",
            "scripts/run_real_transition_audit.py",
            "scripts/run_feasibility_prototype.py",
        ],
        outputs,
    )


def _workflow_figure(
    summary: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    real = summary["real_event_audit"]
    tiers = summary["evidence_tiers"]
    figure, axis = plt.subplots(figsize=(6.6, 5.8))
    axis.axis("off")
    _box(axis, 0.5, 0.93, 0.31, 0.10, "Public EPA bulk archives", facecolor="#E0F2FE", weight="bold")
    _box(axis, 0.5, 0.78, 0.42, 0.12, "Canonical daily series + persistent metadata anchors", facecolor="#DBEAFE")
    _arrow(axis, (0.5, 0.88), (0.5, 0.84))
    _box(axis, 0.25, 0.60, 0.33, 0.14, "Stable regimes\nknown local and regional perturbations", facecolor="#FEF3C7")
    _box(axis, 0.75, 0.60, 0.33, 0.14, f"All {real['total_anchors']} real anchors\ndistinct physical-donor screening", facecolor="#EDE9FE")
    _arrow(axis, (0.5, 0.72), (0.25, 0.67))
    _arrow(axis, (0.5, 0.72), (0.75, 0.67))
    _box(axis, 0.25, 0.38, 0.33, 0.14, "66 calibration targets\nfreeze thresholds", facecolor="#FEF3C7")
    _box(axis, 0.25, 0.18, 0.33, 0.15, "80 held-out targets\nmetrics + paired uncertainty", facecolor="#FEF3C7")
    _arrow(axis, (0.25, 0.53), (0.25, 0.45))
    _arrow(axis, (0.25, 0.31), (0.25, 0.26))
    _box(
        axis,
        0.75,
        0.38,
        0.33,
        0.14,
        f"{real['complete_comparisons']} common comparisons\nor explicit failure reason",
        facecolor="#EDE9FE",
    )
    _arrow(axis, (0.75, 0.53), (0.75, 0.45))
    _box(
        axis,
        0.56,
        0.18,
        0.24,
        0.15,
        f"Diagnostics\nintervals, placebos, LOO",
        facecolor="#F1F5F9",
    )
    _box(
        axis,
        0.87,
        0.18,
        0.22,
        0.15,
        f"Three-way audit tiers\n{tiers['supported_candidate_discontinuity']} / "
        f"{tiers['not_supported_by_available_evidence']} / "
        f"{tiers['inconclusive_insufficient_evidence']}",
        facecolor="#F1F5F9",
        fontsize=8,
    )
    _arrow(axis, (0.75, 0.31), (0.56, 0.26))
    _arrow(axis, (0.75, 0.31), (0.87, 0.26))
    axis.text(
        0.5,
        0.025,
        "Parallel branches share frozen inputs but serve different questions: known-truth evaluation versus complete observational audit.",
        ha="center",
        va="bottom",
        fontsize=8,
        transform=axis.transAxes,
    )
    save_figure(
        figure,
        figures / "fig_audit_pipeline.pdf",
        "Top-down MetaShift-Bench workflow",
        [
            "configs/benchmark_release_v2.json",
            "configs/evidence_tier_primary_v1.json",
            "artifacts/real_transition_88101_event_audit.csv",
            "artifacts/real_transition_88101_evidence_tier_summary.json",
        ],
        outputs,
    )


def _split_integrity_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    figure, axis = plt.subplots(figsize=(6.6, 3.65))
    axis.axis("off")
    split_audit = data["split_audit"]
    axis.text(
        0.5,
        0.94,
        "Whole target-plus-donor connected components are assigned before any held-out metric",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        transform=axis.transAxes,
    )
    layouts = (
        (
            0.25,
            "Calibration partition",
            int(split_audit["calibration_physical_sites"]),
            int(split_audit["calibration_input_physical_sites"]),
            "#DBEAFE",
        ),
        (
            0.75,
            "Held-out evaluation partition",
            int(split_audit["evaluation_physical_sites"]),
            int(split_audit["evaluation_input_physical_sites"]),
            "#EDE9FE",
        ),
    )
    for x, title, targets, inputs, color in layouts:
        patch = FancyBboxPatch(
            (x - 0.20, 0.17),
            0.40,
            0.63,
            boxstyle="round,pad=0.014,rounding_size=0.02",
            transform=axis.transAxes,
            facecolor=color,
            edgecolor="#334155",
            linewidth=0.9,
        )
        axis.add_patch(patch)
        axis.text(
            x,
            0.73,
            f"{title}\n{targets} target sites | {inputs} physical inputs",
            ha="center",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            transform=axis.transAxes,
        )
        for offset_x, offset_y in ((-0.10, 0.49), (0.09, 0.49), (0.0, 0.30)):
            target_x, target_y = x + offset_x, offset_y
            axis.plot(
                target_x,
                target_y,
                marker="o",
                markersize=7,
                color="#1D4ED8",
                transform=axis.transAxes,
            )
            for donor_delta in ((-0.045, -0.075), (0.055, -0.06)):
                donor_x = target_x + donor_delta[0]
                donor_y = target_y + donor_delta[1]
                axis.plot(
                    [target_x, donor_x],
                    [target_y, donor_y],
                    color="#475569",
                    linewidth=0.8,
                    transform=axis.transAxes,
                )
                axis.plot(
                    donor_x,
                    donor_y,
                    marker="s",
                    markersize=4.6,
                    color="#64748B",
                    transform=axis.transAxes,
                )
        axis.text(
            x,
            0.20,
            "Illustrative component insets:\nblue target, gray donor physical site",
            ha="center",
            va="center",
            fontsize=8,
            transform=axis.transAxes,
        )
    axis.plot(
        [0.5, 0.5],
        [0.13, 0.84],
        color="#B91C1C",
        linestyle="--",
        linewidth=1.2,
        transform=axis.transAxes,
    )
    axis.text(
        0.5,
        0.49,
        f"0 shared\nphysical inputs",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="#991B1B",
        transform=axis.transAxes,
    )
    axis.text(
        0.5,
        0.045,
        "Component-level allocation prevents a target or any of its donor physical sites from crossing the calibration/evaluation boundary.",
        ha="center",
        va="center",
        fontsize=8,
        transform=axis.transAxes,
    )
    save_figure(
        figure,
        figures / "fig_split_integrity.pdf",
        "Complete target-plus-donor footprint split integrity",
        [
            "artifacts/stable_synthetic_case_manifest.json",
            "artifacts/stable_synthetic_case_split_audit.json",
        ],
        outputs,
    )


def _synthetic_metrics_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    format_decimal: FormatDecimal,
    outputs: list[dict[str, Any]],
) -> None:
    aggregate = (
        data["metrics"]
        .loc[data["metrics"]["perturbation_family"].isna()]
        .set_index("method")
        .loc[list(METHOD_ORDER)]
    )
    specs = (
        ("local_effect_mae_log", "Local-effect MAE", "Lower is better", (0.0, 0.13), 3),
        ("macro_f1", "Macro-F1", "Higher is better", (0.0, 1.0), 3),
        ("false_positive_rate", "Regional FPR", "Lower is better", (0.0, 1.0), 3),
    )
    figure, axes = plt.subplots(1, 3, figsize=(6.6, 3.3), sharey=True)
    positions = np.arange(len(METHOD_ORDER))
    for axis, (column, title, direction, limits, places) in zip(
        axes, specs, strict=True
    ):
        values = aggregate[column].to_numpy(dtype=float)
        for position, method, value in zip(
            positions, METHOD_ORDER, values, strict=True
        ):
            axis.scatter(
                value,
                position,
                color=METHOD_COLORS[method],
                marker=METHOD_MARKERS[method],
                s=43,
                edgecolor="#111827",
                linewidth=0.45,
                zorder=3,
            )
            axis.text(
                min(value + (limits[1] - limits[0]) * 0.025, limits[1] * 0.94),
                position,
                format_decimal(value, places),
                va="center",
                fontsize=8,
            )
        axis.set_xlim(*limits)
        axis.set_title(f"{title}\n{direction}", fontweight="bold")
        axis.set_xlabel("Held-out aggregate value")
        _finalize_axes(axis)
    axes[0].set_yticks(positions, [METHOD_LABELS[method] for method in METHOD_ORDER])
    axes[0].invert_yaxis()
    figure.suptitle(
        "Frozen held-out stable-synthetic comparison: 80 physical targets",
        fontsize=10.5,
        y=0.99,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.92))
    save_figure(
        figure,
        figures / "fig_synthetic_metrics.pdf",
        "Held-out cross-site synthetic metric dot plots",
        ["artifacts/stable_synthetic_stable_full_v2_metrics.csv"],
        outputs,
    )


def _perturbation_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    format_decimal: FormatDecimal,
    outputs: list[dict[str, Any]],
) -> None:
    metrics = data["metrics"]
    aggregate = (
        metrics.loc[metrics["perturbation_family"].isna()]
        .set_index("method")
        .loc[list(ALL_METHOD_ORDER)]
    )
    families = FAMILY_ORDER[:-1]
    family_metrics = metrics.loc[
        metrics["perturbation_family"].isin(families)
        & metrics["method"].isin(METHOD_ORDER)
    ].set_index(["method", "perturbation_family"])
    figure, axes = plt.subplots(1, 2, figsize=(6.6, 4.2), gridspec_kw={"width_ratios": [1.04, 0.96]})
    estimate_axis, class_axis = axes
    comparators = (
        "metashift_v1_fixed",
        "metashift_v2_cv",
        "nearest_neighbor_did",
    )
    offsets = (-0.20, 0.0, 0.20)
    values: list[float] = []
    for family_index, family in enumerate(families):
        reference = float(
            family_metrics.loc[
                ("standard_synthetic_control", family), "local_effect_mae_log"
            ]
        )
        for offset, method in zip(offsets, comparators, strict=True):
            difference = float(
                family_metrics.loc[(method, family), "local_effect_mae_log"]
            ) - reference
            values.append(difference)
            estimate_axis.scatter(
                difference,
                family_index + offset,
                color=METHOD_COLORS[method],
                marker=METHOD_MARKERS[method],
                s=40,
                edgecolor="#111827",
                linewidth=0.4,
                zorder=3,
            )
    extent = max(0.015, max(abs(value) for value in values) * 1.20)
    estimate_axis.axvline(0, color="#111827", linestyle="--", linewidth=0.9)
    estimate_axis.set_xlim(-extent, extent)
    estimate_axis.set_yticks(range(len(families)), [FAMILY_LABELS[item] for item in families])
    estimate_axis.invert_yaxis()
    estimate_axis.set_xlabel("Comparator MAE - Standard SC MAE")
    estimate_axis.set_title(
        "Effect estimation\nnegative favors comparator",
        fontweight="bold",
    )
    _finalize_axes(estimate_axis)
    estimate_axis.legend(
        [
            Line2D(
                [0],
                [0],
                color="none",
                marker=METHOD_MARKERS[method],
                markerfacecolor=METHOD_COLORS[method],
                markeredgecolor="#111827",
                label=METHOD_LABELS[method],
            )
            for method in comparators
        ],
        [METHOD_LABELS[method] for method in comparators],
        loc="lower left",
        frameon=False,
        handletextpad=0.35,
    )

    positions = np.arange(len(ALL_METHOD_ORDER))
    for position, method in zip(positions, ALL_METHOD_ORDER, strict=True):
        value = float(aggregate.loc[method, "macro_f1"])
        class_axis.scatter(
            value,
            position,
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            s=39,
            edgecolor="#111827",
            linewidth=0.4,
            zorder=3,
        )
        class_axis.text(min(value + 0.026, 0.94), position, format_decimal(value, 3), va="center", fontsize=8)
    class_axis.axhline(3.5, color="#94A3B8", linewidth=0.8)
    class_axis.text(0.02, 3.1, "Cross-site", fontsize=8, color="#334155")
    class_axis.text(0.02, 4.1, "Single-series", fontsize=8, color="#334155")
    class_axis.set_xlim(0.0, 1.0)
    class_axis.set_yticks(positions, [METHOD_LABELS[method] for method in ALL_METHOD_ORDER])
    class_axis.invert_yaxis()
    class_axis.set_xlabel("Aggregate Macro-F1")
    class_axis.set_title("Attribution classification\nhigher is better", fontweight="bold")
    _finalize_axes(class_axis)
    figure.suptitle(
        "Main-text perturbation comparison; the complete all-method matrix is in the appendix",
        fontsize=10.2,
        y=0.995,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    save_figure(
        figure,
        figures / "fig_perturbation_metrics.pdf",
        "Main perturbation comparison for estimation and classification",
        ["artifacts/stable_synthetic_stable_full_v2_metrics.csv"],
        outputs,
    )


def _paired_bootstrap_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    format_decimal: FormatDecimal,
    outputs: list[dict[str, Any]],
) -> None:
    bootstrap = data["bootstrap"].set_index("comparison")
    pairs = (
        ("metashift_v1_fixed minus standard_synthetic_control", "MetaShift fixed", "metashift_v1_fixed"),
        ("metashift_v2_cv minus standard_synthetic_control", "MetaShift CV", "metashift_v2_cv"),
    )
    centers = np.array([float(bootstrap.loc[item[0], "mae_difference_log"]) for item in pairs])
    lowers = np.array([float(bootstrap.loc[item[0], "bootstrap_95ci_lower"]) for item in pairs])
    uppers = np.array([float(bootstrap.loc[item[0], "bootstrap_95ci_upper"]) for item in pairs])
    extent = max(abs(lowers).max(), abs(uppers).max()) * 1.25
    figure, axis = plt.subplots(figsize=(6.15, 2.8))
    positions = np.array([1, 0])
    axis.axvline(0, color="#111827", linestyle="--", linewidth=1)
    for position, (_, label, method), center, lower, upper in zip(
        positions, pairs, centers, lowers, uppers, strict=True
    ):
        axis.errorbar(
            center,
            position,
            xerr=np.array([[center - lower], [upper - center]]),
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            markersize=6,
            capsize=4,
            linewidth=1.3,
            markeredgecolor="#111827",
            markeredgewidth=0.45,
            zorder=3,
        )
        axis.text(
            -extent * 0.97,
            position - 0.19,
            f"Delta={format_decimal(center, 5)}  [{format_decimal(lower, 5)}, {format_decimal(upper, 5)}]",
            fontsize=8,
            ha="left",
        )
    axis.set_xlim(-extent, extent)
    axis.set_ylim(-0.5, 1.45)
    axis.set_yticks(positions, [pair[1] for pair in pairs])
    axis.set_xlabel("Paired MAE difference: MetaShift - Standard SC")
    axis.set_title("Held-out paired bootstrap intervals (95%)", fontweight="bold")
    axis.text(-extent * 0.94, -0.37, "Negative: favors MetaShift", fontsize=8, ha="left")
    axis.text(extent * 0.94, -0.37, "Positive: favors Standard SC", fontsize=8, ha="right")
    _finalize_axes(axis)
    figure.tight_layout()
    save_figure(
        figure,
        figures / "fig_paired_bootstrap.pdf",
        "Paired held-out MAE bootstrap intervals",
        ["artifacts/stable_synthetic_stable_full_v2_bootstrap.csv"],
        outputs,
    )


def _event_accounting_figure(
    summary: dict[str, Any],
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    audit = data["audit"]
    tiers = data["tiers"]
    audit_counts = audit["audit_status"].value_counts()
    tier_counts = pd.crosstab(tiers["audit_status"], tiers["evidence_tier"])
    total = int(len(audit))
    donor_insufficient = int(audit_counts["insufficient_geographic_donors"])
    input_failure = int(audit_counts["estimator_input_failure"])
    complete = int(audit_counts["complete"])
    supported = int(
        tier_counts.loc["complete", "supported_candidate_discontinuity"]
    )
    not_supported = int(
        tier_counts.loc["complete", "not_supported_by_available_evidence"]
    )
    complete_inconclusive = int(
        tier_counts.loc["complete", "inconclusive_insufficient_evidence"]
    )
    figure, axis = plt.subplots(figsize=(6.6, 5.25))
    axis.axis("off")
    _box(
        axis,
        0.50,
        0.88,
        0.28,
        0.11,
        f"{total}\nprimary metadata anchors",
        facecolor="#E0F2FE",
        weight="bold",
    )
    _box(
        axis,
        0.23,
        0.63,
        0.27,
        0.14,
        f"{donor_insufficient}\nfewer than 3 donors\ninconclusive",
        facecolor="#E2E8F0",
        hatch="//",
    )
    _box(
        axis,
        0.68,
        0.63,
        0.27,
        0.14,
        f"{complete + input_failure}\nmeet >=3 distinct donor eligibility",
        facecolor="#DBEAFE",
    )
    _arrow(axis, (0.43, 0.825), (0.31, 0.70))
    _arrow(axis, (0.57, 0.825), (0.61, 0.70))
    _box(
        axis,
        0.48,
        0.38,
        0.24,
        0.14,
        f"{input_failure}\ninput-window failure\ninconclusive",
        facecolor="#E2E8F0",
        hatch="//",
    )
    _box(
        axis,
        0.80,
        0.38,
        0.25,
        0.14,
        f"{complete}\ncomplete common comparison",
        facecolor="#EDE9FE",
    )
    _arrow(axis, (0.64, 0.56), (0.53, 0.45), color="#B91C1C", style="--")
    _arrow(axis, (0.73, 0.56), (0.76, 0.45))
    leaves = (
        (
            0.28,
            0.14,
            f"{supported}\nsupported candidate",
            TIER_COLORS["supported_candidate_discontinuity"],
            None,
        ),
        (
            0.60,
            0.14,
            f"{not_supported}\nnot supported",
            TIER_COLORS["not_supported_by_available_evidence"],
            "//",
        ),
        (
            0.88,
            0.14,
            f"{complete_inconclusive}\ncomplete but\ninconclusive",
            TIER_COLORS["inconclusive_insufficient_evidence"],
            None,
        ),
    )
    for x, y, label, color, hatch in leaves:
        _box(axis, x, y, 0.23, 0.14, label, facecolor=color, hatch=hatch, fontsize=8)
        _arrow(axis, (0.80, 0.31), (x, 0.22))
    axis.text(
        0.50,
        0.015,
        f"Reconciliation: {donor_insufficient} + {input_failure} + {complete} = {total}; "
        f"{supported} + {not_supported} + {complete_inconclusive} = {complete}.",
        ha="center",
        va="center",
        fontsize=8,
        transform=axis.transAxes,
    )
    save_figure(
        figure,
        figures / "fig_event_accounting.pdf",
        "Hierarchical accounting of all primary metadata anchors",
        [
            "artifacts/real_transition_88101_event_audit.csv",
            "artifacts/real_transition_88101_evidence_tiers.csv",
            "artifacts/real_transition_88101_evidence_tier_summary.json",
        ],
        outputs,
    )


def _placebo_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    time_placebo = data["time_placebo"]
    complete = time_placebo.loc[
        time_placebo["status"].astype(str).str.startswith("complete_")
    ]
    complete_count = int(len(complete))
    at_100 = int((complete["placebo_count"] >= 100).sum())
    at_50_to_99 = complete_count - at_100
    unavailable = 228 - complete_count
    figure, axes = plt.subplots(1, 2, figsize=(6.6, 3.15), gridspec_kw={"width_ratios": [0.94, 1.06]})
    flow, histogram = axes
    flow.axis("off")
    _box(flow, 0.15, 0.55, 0.24, 0.16, "228\ncomplete comparisons", facecolor="#EDE9FE")
    _box(flow, 0.49, 0.68, 0.26, 0.16, f"{complete_count}\n>=50 stable dates", facecolor="#DBEAFE")
    _box(flow, 0.49, 0.29, 0.25, 0.16, f"{unavailable}\n<50 dates: unavailable", facecolor="#E2E8F0", hatch="//")
    _arrow(flow, (0.27, 0.59), (0.36, 0.68))
    _arrow(flow, (0.27, 0.51), (0.36, 0.29), color="#B91C1C", style="--")
    _box(flow, 0.84, 0.79, 0.23, 0.16, f"{at_100}\n100 dates", facecolor="#C7D2FE")
    _box(flow, 0.84, 0.51, 0.23, 0.16, f"{at_50_to_99}\n50--99 dates", facecolor="#DBEAFE")
    _arrow(flow, (0.62, 0.70), (0.72, 0.79))
    _arrow(flow, (0.62, 0.66), (0.72, 0.51))
    flow.text(
        0.5,
        0.06,
        "The 100-date cohort is nested within the >=50-date cohort.",
        ha="center",
        fontsize=8,
        transform=flow.transAxes,
    )
    flow.set_title("Nested time-placebo availability", fontweight="bold")

    histogram.hist(
        complete["placebo_p_value"].dropna(),
        bins=np.linspace(0, 1, 11),
        color="#0F766E",
        edgecolor="#FFFFFF",
    )
    histogram.axvline(0.10, color="#B91C1C", linestyle="--", linewidth=1)
    histogram.text(0.12, histogram.get_ylim()[1] * 0.93, "Frozen 0.10 screen", color="#991B1B", fontsize=8)
    histogram.set_xlim(0, 1)
    histogram.set_xlabel("Saved raw within-event placebo probability")
    histogram.set_ylabel("Complete events")
    histogram.set_title("Diagnostic probability distribution", fontweight="bold")
    _finalize_axes(histogram)
    figure.tight_layout()
    save_figure(
        figure,
        figures / "fig_placebos.pdf",
        "Nested time-placebo availability and probability distribution",
        ["artifacts/time_placebo_summary.csv"],
        outputs,
    )


def _interval_coverage_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    coverage = data["coverage"]
    conditional = coverage.loc[
        (coverage["interval_type"] == "conditional_block_bootstrap")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].set_index("method").loc[list(METHOD_ORDER)]
    conformal = coverage.loc[
        (coverage["interval_type"] == "split_conformal")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].set_index("method").loc[list(METHOD_ORDER)]
    figure, axes = plt.subplots(1, 2, figsize=(6.6, 3.5), sharey=True)
    coverage_axis, width_axis = axes
    positions = np.arange(len(METHOD_ORDER))
    for position, method in zip(positions, METHOD_ORDER, strict=True):
        color = METHOD_COLORS[method]
        for offset, subset, marker, label in (
            (-0.14, conditional, "o", "Conditional bootstrap, nominal 95%"),
            (0.14, conformal, "D", "Split conformal, nominal 90%"),
        ):
            value = float(subset.loc[method, "empirical_coverage"])
            coverage_axis.scatter(
                value,
                position + offset,
                color=color,
                marker=marker,
                edgecolor="#111827",
                linewidth=0.4,
                s=38,
                zorder=3,
            )
            coverage_axis.text(min(value + 0.025, 0.98), position + offset, f"{value * 100:.1f}%", va="center", fontsize=8)
            width = float(subset.loc[method, "mean_interval_width_log"])
            width_axis.scatter(
                width,
                position + offset,
                color=color,
                marker=marker,
                edgecolor="#111827",
                linewidth=0.4,
                s=38,
                zorder=3,
            )
            width_axis.text(width + 0.012, position + offset, f"{width:.3f}", va="center", fontsize=8)
    coverage_axis.axvline(0.95, color="#334155", linestyle="--", linewidth=0.9)
    coverage_axis.axvline(0.90, color="#334155", linestyle=":", linewidth=1.1)
    coverage_axis.text(0.95, -0.52, "95%", ha="center", fontsize=8)
    coverage_axis.text(0.90, -0.82, "90%", ha="center", fontsize=8)
    coverage_axis.set_xlim(0, 1.04)
    coverage_axis.set_xlabel("Empirical coverage (full 0--100% scale)")
    coverage_axis.set_title("Held-out coverage", fontweight="bold")
    coverage_axis.set_yticks(positions, [METHOD_LABELS[method] for method in METHOD_ORDER])
    coverage_axis.invert_yaxis()
    width_axis.set_xlim(0, 0.66)
    width_axis.set_xlabel("Mean interval width (log units)")
    width_axis.set_title("Width alongside coverage", fontweight="bold")
    for axis in axes:
        _finalize_axes(axis)
    figure.legend(
        [
            Line2D([0], [0], color="#111827", marker="o", linestyle="none"),
            Line2D([0], [0], color="#111827", marker="D", linestyle="none"),
        ],
        ["Conditional bootstrap (95% nominal)", "Split conformal (90% nominal)"],
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )
    figure.tight_layout(rect=(0, 0.08, 1, 1))
    save_figure(
        figure,
        figures / "fig_interval_coverage.pdf",
        "Full-scale held-out coverage and interval width",
        ["artifacts/synthetic_interval_coverage_v2_summary.csv"],
        outputs,
    )


def _screening_sensitivity_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    sensitivity = data["tier_sensitivity"].pivot(
        index="setting", columns="evidence_tier", values="anchor_count"
    ).loc[["strict", "primary", "lenient"]]
    screening = data["screening"].loc[
        data["screening"]["minimum_donors_required"] == 3
    ].set_index("setting")
    figure, axes = plt.subplots(1, 2, figsize=(6.6, 3.3), gridspec_kw={"width_ratios": [1.04, 0.96]})
    tiers_axis, radius_axis = axes
    bottom = np.zeros(len(sensitivity), dtype=float)
    tier_specs = (
        ("supported_candidate_discontinuity", "Supported", "#2563EB", None),
        ("not_supported_by_available_evidence", "Not supported", "#B45309", "//"),
        ("inconclusive_insufficient_evidence", "Inconclusive", "#64748B", None),
    )
    for column, label, color, hatch in tier_specs:
        values = sensitivity[column].to_numpy(dtype=float)
        proportions = values / values.sum(axis=0)
        bars = tiers_axis.bar(
            sensitivity.index,
            proportions * 100,
            bottom=bottom * 100,
            label=label,
            color=color,
            hatch=hatch,
            edgecolor="#FFFFFF",
            linewidth=0.55,
        )
        for bar, value, proportion in zip(bars, values, proportions, strict=True):
            if proportion > 0.08:
                tiers_axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    (bar.get_y() + bar.get_height() / 2),
                    str(int(value)),
                    ha="center",
                    va="center",
                    color="#FFFFFF",
                    fontsize=8,
                )
        bottom += proportions
    tiers_axis.set_ylim(0, 100)
    tiers_axis.set_ylabel("All anchors (%)")
    tiers_axis.set_title("Tier composition under frozen rule settings", fontweight="bold")
    tiers_axis.legend(loc="upper left", frameon=False)
    _finalize_axes(tiers_axis)

    radii = np.array([50, 100, 200])
    values = np.array(
        [
            int(screening.loc["distance_50", "eligible_anchors_after_donor_threshold"]),
            int(screening.loc["primary", "eligible_anchors_after_donor_threshold"]),
            int(screening.loc["distance_200", "eligible_anchors_after_donor_threshold"]),
        ]
    )
    radius_axis.plot(
        radii,
        values,
        color="#0F766E",
        marker="o",
        markeredgecolor="#111827",
        markeredgewidth=0.45,
        linewidth=1.3,
    )
    for radius, value in zip(radii, values, strict=True):
        radius_axis.text(radius, value + 10, str(int(value)), ha="center", fontsize=8)
    radius_axis.set_xlim(40, 210)
    radius_axis.set_ylim(0, max(values) * 1.16)
    radius_axis.set_xticks(radii)
    radius_axis.set_xlabel("Maximum donor radius (km)")
    radius_axis.set_ylabel("Anchors with >=3 donors")
    radius_axis.set_title("Predeclared donor-radius sensitivity", fontweight="bold")
    _finalize_axes(radius_axis)
    figure.text(
        0.5,
        0.005,
        "Strict: p,q<=0.05 and LOO>=0.95; primary: <=0.10 and >=0.90; lenient: <=0.20 and >=0.80.",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.06, 1, 1))
    save_figure(
        figure,
        figures / "fig_screening_sensitivity.pdf",
        "Normalized tier sensitivity and donor radius availability",
        [
            "configs/evidence_tier_sensitivity_v2.json",
            "artifacts/screening_sensitivity_summary.csv",
            "artifacts/evidence_tier_sensitivity_v2_summary.csv",
        ],
        outputs,
    )


def _draw_ladder(axis: plt.Axes, title: str, steps: list[tuple[str, int]], color: str) -> None:
    axis.axis("off")
    axis.set_title(title, fontsize=9.2, fontweight="bold", pad=5)
    positions = np.linspace(0.80, 0.18, len(steps))
    for index, ((label, value), y) in enumerate(zip(steps, positions, strict=True)):
        face = color if index == len(steps) - 1 else "#E2E8F0"
        hatch = "//" if value == 0 else None
        _box(
            axis,
            0.5,
            float(y),
            0.68,
            0.14,
            f"{value}: {label}",
            facecolor=face,
            hatch=hatch,
            fontsize=8,
        )
        if index < len(steps) - 1:
            _arrow(axis, (0.5, float(y - 0.08)), (0.5, float(positions[index + 1] + 0.08)))


def _external_evidence_figure(
    summary: dict[str, Any],
    data: dict[str, Any],
    external_config: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    qa = external_config["qa_collocation_evidence"]["expected_counts"]
    secondary_audit = data["secondary_audit"]
    secondary_complete = int((secondary_audit["audit_status"] == "complete").sum())
    secondary_donor_eligible = int(
        (secondary_audit["audit_status"] != "insufficient_geographic_donors").sum()
    )
    figure, axes = plt.subplots(2, 2, figsize=(6.6, 5.1))
    poc = summary["hourly_same_site_poc"]
    _draw_ladder(
        axes[0, 0],
        "Same-site POC context",
        [
            ("candidate anchors", int(poc["candidate_events"])),
            ("paired hourly windows", int(poc["usable_paired_events"])),
            ("daily/hourly direction agreement", int(poc["daily_hourly_direction_agreement"])),
        ],
        "#DBEAFE",
    )
    _draw_ladder(
        axes[0, 1],
        "QA collocation context",
        [
            ("QA candidates", int(qa["candidates"])),
            ("target POC matched", int(qa["target_poc_matched"])),
            (
                "adequate matched\npre/post windows",
                int(qa["adequate_matched_pre_post"]),
            ),
        ],
        "#FEE2E2",
    )
    documents = summary["external_document_review"]
    _draw_ladder(
        axes[1, 0],
        "Official-document context",
        [
            ("reviewed records", int(documents["reviewed_events"])),
            ("dated site-specific confirmations", int(documents["site_specific_dated_confirmations"])),
        ],
        "#FEE2E2",
    )
    secondary = summary["secondary_88502"]
    _draw_ladder(
        axes[1, 1],
        "Separate 88502 pipeline",
        [
            ("metadata anchors", int(secondary["eligible_anchors"])),
            (">=3 distinct donor-eligible", secondary_donor_eligible),
            ("complete common comparisons", secondary_complete),
        ],
        "#EDE9FE",
    )
    figure.text(
        0.5,
        0.01,
        "All pathways are contextual evidence or feasibility checks; none establishes a physical cause of a metadata transition.",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.055, 1, 1))
    save_figure(
        figure,
        figures / "fig_external_evidence.pdf",
        "Nested external-evidence and secondary-pipeline ladders",
        [
            "paper/latex/configs/external_evidence_rendering_v1.json",
            "artifacts/external_validation_evidence.csv",
            "artifacts/hourly_poc_validation_summary.csv",
            "artifacts/external_document_review_summary.json",
            "artifacts/data_gate_88502/summary.json",
            "artifacts/real_transition_88502_event_audit.csv",
        ],
        outputs,
    )


def _case_study_figure(
    cases: list[dict[str, Any]],
    figures: Path,
    save_figure: SaveFigure,
    format_decimal: FormatDecimal,
    outputs: list[dict[str, Any]],
) -> None:
    figure, axes = plt.subplots(
        4,
        len(cases),
        figsize=(6.6, 8.3),
        squeeze=False,
        gridspec_kw={"height_ratios": [1.1, 1.0, 0.82, 0.90]},
    )
    complete_effect_bounds = [
        value
        for case in cases
        if case["audit_status"] == "complete"
        for value in (*case["fixed_interval"], *case["nested_interval"], case["log_effect"])
        if value is not None
    ]
    effect_extent = max(abs(float(value)) for value in complete_effect_bounds) * 1.25
    for column, case in enumerate(cases):
        top, residual_axis, placebo_axis, interval_axis = axes[:, column]
        anchor_date = case["anchor_date"]
        target = case["target"].loc[case["visible_start"] : case["visible_end"]]
        group = case["case_group"].replace(": no qualified counterfactual", "")
        top.set_title(
            f"{group}\nanchor {anchor_date.date().isoformat()}",
            fontsize=8.5,
            fontweight="bold",
        )
        if case["audit_status"] == "complete":
            counterfactual = case["counterfactual"].loc[
                case["visible_start"] : case["visible_end"]
            ]
            residual = case["residual"].loc[
                case["visible_start"] : case["visible_end"]
            ]
            display = pd.concat(
                [
                    target.rename("target"),
                    counterfactual.rename("counterfactual"),
                    residual.rename("residual"),
                ],
                axis="columns",
            ).dropna()
            days = (display.index - anchor_date).days
            top.plot(
                days,
                display["target"],
                color="#111827",
                linewidth=1.1,
                label="Target",
            )
            top.plot(
                days,
                display["counterfactual"],
                color="#4C566A",
                linewidth=1.0,
                linestyle="--",
                label="Reliability-prior composite",
            )
            residual_axis.plot(
                days, display["residual"], color="#7C3AED", linewidth=1.1
            )
            _comparison_shading(residual_axis)
            residual_axis.axhline(0, color="#111827", linewidth=0.7)
            residual_axis.set_xlim(-60, 60)

            actual = case["placebo_actual_score"]
            median = case["placebo_median_score"]
            if actual is not None and median is not None:
                placebo_axis.plot(
                    [median, actual],
                    [0, 1],
                    color="#475569",
                    linewidth=0.9,
                    zorder=2,
                )
                placebo_axis.scatter(
                    [median, actual],
                    [0, 1],
                    color=["#64748B", "#7C3AED"],
                    marker="o",
                    s=30,
                    edgecolor="#111827",
                    linewidth=0.35,
                    zorder=3,
                )
                placebo_axis.set_yticks(
                    [0, 1],
                    ["Median", "Anchor"] if column == 0 else [],
                )
                placebo_axis.set_xlabel("Score")
                placebo_axis.set_title(
                    f"Saved summary: n={int(case['placebo_count'])}; "
                    f"p={case['placebo_p_value']:.3f}",
                    fontsize=8,
                    pad=2,
                )
                _finalize_axes(placebo_axis)
            else:
                placebo_axis.axis("off")
            fixed_lower, fixed_upper = case["fixed_interval"]
            nested_lower, nested_upper = case["nested_interval"]
            effect = float(case["log_effect"])
            interval_axis.axvline(0, color="#111827", linewidth=0.8)
            interval_axis.plot(
                [fixed_lower, fixed_upper],
                [1, 1],
                color="#3B82F6",
                linewidth=2.0,
                solid_capstyle="butt",
            )
            interval_axis.plot(effect, 1, marker="^", color="#3B82F6", markersize=4.8)
            interval_axis.plot(
                [nested_lower, nested_upper],
                [0, 0],
                color="#7C3AED",
                linewidth=1.6,
                linestyle="--",
                solid_capstyle="butt",
            )
            interval_axis.plot(effect, 0, marker="D", color="#7C3AED", markersize=4.3)
            interval_axis.set_xlim(-effect_extent, effect_extent)
            interval_axis.set_yticks(
                [0, 1],
                ["Nested", "Fixed"] if column == 0 else [],
            )
            interval_axis.set_xlabel("Log effect")
            interval_axis.text(
                0.5,
                0.04,
                f"{group}\nLOO={case['leave_one_donor_out_fraction']:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
                transform=interval_axis.transAxes,
            )
            _finalize_axes(interval_axis)
        else:
            residual_axis.axis("off")
            residual_axis.text(
                0.5,
                0.58,
                "No qualified geographic\ncounterfactual is constructed.",
                ha="center",
                va="center",
                fontsize=8.5,
                fontweight="bold",
                transform=residual_axis.transAxes,
            )
            residual_axis.text(
                0.5,
                0.25,
                "Reason: fewer than three\nprequalified distinct physical donors.",
                ha="center",
                va="center",
                fontsize=8,
                transform=residual_axis.transAxes,
            )
            placebo_axis.axis("off")
            placebo_axis.text(
                0.5,
                0.55,
                "No complete comparison\nso no time-placebo diagnostic.",
                ha="center",
                va="center",
                fontsize=8.5,
                transform=placebo_axis.transAxes,
            )
            interval_axis.axis("off")
            interval_axis.text(
                0.5,
                0.55,
                "Audit abstention\nNo effect estimate or interval is imputed.",
                ha="center",
                va="center",
                fontsize=8.5,
                transform=interval_axis.transAxes,
            )
            days = (target.index - anchor_date).days
            top.plot(days, target, color="#111827", linewidth=1.1, label="Target")
        _comparison_shading(top)
        top.set_xlim(-60, 60)
        for axis in (top, residual_axis):
            if axis.axison:
                _finalize_axes(axis)
                axis.set_xticks([-60, 0, 60])
        if column == 0:
            top.set_ylabel(r"PM$_{2.5}$ (ug/m$^3$)")
            residual_axis.set_ylabel("Centered log residual")
        else:
            top.set_ylabel("")
            if residual_axis.axison:
                residual_axis.set_ylabel("")
        if column == 0:
            top.legend(loc="upper left", frameon=False, fontsize=8)
    figure.text(0.01, 0.90, "Series", rotation=90, va="center", fontsize=8.5)
    figure.text(0.01, 0.66, "Residual", rotation=90, va="center", fontsize=8.5)
    figure.text(0.01, 0.42, "Placebo", rotation=90, va="center", fontsize=8.5)
    figure.text(0.01, 0.18, "Intervals + tier", rotation=90, va="center", fontsize=8.5)
    figure.suptitle(
        "Deterministically selected audit cases: source series, residual, placebo summary, and diagnostic intervals",
        fontsize=9.5,
        y=0.996,
    )
    figure.subplots_adjust(
        left=0.15,
        right=0.985,
        top=0.94,
        bottom=0.08,
        wspace=0.42,
        hspace=0.72,
    )
    save_figure(
        figure,
        figures / "fig_case_studies.pdf",
        "Standardized deterministic representative audit cases",
        [
            "artifacts/real_transition_88101_evidence_tiers.csv",
            "artifacts/real_transition_88101_method_results.csv",
            "artifacts/real_transition_88101_event_intervals.csv",
            "artifacts/time_placebo_summary.csv",
            "paper/latex/configs/case_study_rendering_v2.json",
            "artifacts/data_gate/source_manifest.json",
            "artifacts/data_gate/geographic_controls.csv",
        ],
        outputs,
    )


def _applicability_map_figure(
    summary: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    audit = summary["real_event_audit"]
    tiers = summary["evidence_tiers"]
    figure, axis = plt.subplots(figsize=(6.6, 3.65))
    axis.axis("off")
    headers = (
        (0.17, "Observed condition"),
        (0.50, "Protocol output"),
        (0.83, "Not established"),
    )
    for x, label in headers:
        axis.text(
            x,
            0.93,
            label,
            ha="center",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            transform=axis.transAxes,
        )
    rows = (
        (
            "Fewer than three\nphysical donors\n"
            f"({audit['insufficient_geographic_donors']})",
            "Inconclusive:\nno cross-site comparison",
            "No conclusion about\nan underlying site change",
            "#E2E8F0",
        ),
        (
            "Input-window failure\n"
            f"({audit['estimator_input_failure']})",
            "Inconclusive:\ninput unavailable",
            "No imputed effect\nor interval",
            "#E2E8F0",
        ),
        (
            "Complete comparison\n"
            f"({audit['complete_comparisons']})",
            "Diagnostic tier:\n"
            f"{tiers['supported_candidate_discontinuity']} / "
            f"{tiers['not_supported_by_available_evidence']} / "
            f"{audit['complete_comparisons'] - tiers['supported_candidate_discontinuity'] - tiers['not_supported_by_available_evidence']}",
            "No verified fault,\nreplacement, or bias",
            "#EDE9FE",
        ),
    )
    for y, (left, middle, right, color) in zip((0.72, 0.47, 0.22), rows, strict=True):
        _box(axis, 0.17, y, 0.28, 0.17, left, facecolor=color, fontsize=8)
        _box(axis, 0.50, y, 0.28, 0.17, middle, facecolor="#DBEAFE", fontsize=8)
        _box(axis, 0.83, y, 0.28, 0.17, right, facecolor="#FEF3C7", fontsize=8)
        _arrow(axis, (0.32, y), (0.35, y))
        _arrow(axis, (0.65, y), (0.68, y))
    axis.text(
        0.5,
        0.04,
        "Applicability map, not a classifier: further station records and human technical review are required for any equipment-level hypothesis.",
        ha="center",
        va="center",
        fontsize=8,
        transform=axis.transAxes,
    )
    save_figure(
        figure,
        figures / "fig_applicability_map.pdf",
        "Applicability and failure-mode map",
        [
            "artifacts/real_transition_88101_event_audit.csv",
            "artifacts/real_transition_88101_evidence_tier_summary.json",
        ],
        outputs,
    )


def _anchor_concentration_figure(
    data: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    audit = data["audit"].copy()
    dates = pd.to_datetime(audit["anchor_date"], errors="raise")
    year_counts = dates.dt.year.value_counts().reindex(range(2019, 2026), fill_value=0)
    anchors_2023 = audit.loc[dates.dt.year == 2023].copy()
    pair_counts = (
        anchors_2023.assign(
            old_method_code=anchors_2023["old_method_code"].astype(str),
            new_method_code=anchors_2023["new_method_code"].astype(str),
        )
        .groupby(["old_method_code", "new_method_code"])
        .size()
        .sort_values(ascending=False)
    )
    pair_one = int(pair_counts.loc[("236", "636")])
    pair_two = int(pair_counts.loc[("238", "638")])
    other = int(len(anchors_2023) - pair_one - pair_two)
    figure, axes = plt.subplots(1, 2, figsize=(6.6, 3.15), gridspec_kw={"width_ratios": [0.9, 1.1]})
    years_axis, pair_axis = axes
    colors = ["#94A3B8"] * len(year_counts)
    colors[list(year_counts.index).index(2023)] = "#B45309"
    bars = years_axis.bar(year_counts.index.astype(str), year_counts.to_numpy(), color=colors, edgecolor="#334155", linewidth=0.4)
    for bar, value in zip(bars, year_counts.to_numpy(), strict=True):
        years_axis.text(bar.get_x() + bar.get_width() / 2, value + 7, str(int(value)), ha="center", fontsize=8)
    years_axis.set_ylim(0, max(year_counts) * 1.17)
    years_axis.set_ylabel("Reported metadata anchors")
    years_axis.set_title("Anchor dates in the frozen snapshot", fontweight="bold")
    _finalize_axes(years_axis)

    labels = ["236 -> 636", "238 -> 638", "Other 2023 pairs"]
    values = [pair_one, pair_two, other]
    bars = pair_axis.barh(labels, values, color=["#B45309", "#D97706", "#94A3B8"], edgecolor="#334155", linewidth=0.4)
    for bar, value in zip(bars, values, strict=True):
        pair_axis.text(value + 4, bar.get_y() + bar.get_height() / 2, str(value), va="center", fontsize=8)
    pair_axis.set_xlim(0, max(values) * 1.18)
    pair_axis.set_xlabel("2023 metadata anchors")
    pair_axis.set_title("Named code-pair concentration", fontweight="bold")
    _finalize_axes(pair_axis)
    figure.text(
        0.5,
        0.005,
        "The two new-code labels include “Network Data Alignment enabled”; this association does not establish why records changed.",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.055, 1, 1))
    save_figure(
        figure,
        figures / "fig_anchor_concentration.pdf",
        "Appendix temporal concentration of metadata anchors",
        ["artifacts/real_transition_88101_event_audit.csv"],
        outputs,
    )


def create_revised_figures(
    summary: dict[str, Any],
    data: dict[str, Any],
    cases: list[dict[str, Any]],
    synthetic_example: dict[str, Any],
    window_config: dict[str, Any],
    external_config: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    format_decimal: FormatDecimal,
    outputs: list[dict[str, Any]],
) -> None:
    """Generate the complete redesigned figure set from frozen/pinned inputs."""

    configure_figure_style()
    _synthetic_example_figure(synthetic_example, figures, save_figure, outputs)
    _donor_construction_figure(data, figures, save_figure, outputs)
    _window_protocol_figure(window_config, figures, save_figure, outputs)
    _workflow_figure(summary, figures, save_figure, outputs)
    _split_integrity_figure(data, figures, save_figure, outputs)
    _synthetic_metrics_figure(data, figures, save_figure, format_decimal, outputs)
    _perturbation_figure(data, figures, save_figure, format_decimal, outputs)
    _paired_bootstrap_figure(data, figures, save_figure, format_decimal, outputs)
    _event_accounting_figure(summary, data, figures, save_figure, outputs)
    _placebo_figure(data, figures, save_figure, outputs)
    _interval_coverage_figure(data, figures, save_figure, outputs)
    _screening_sensitivity_figure(data, figures, save_figure, outputs)
    _external_evidence_figure(summary, data, external_config, figures, save_figure, outputs)
    _case_study_figure(cases, figures, save_figure, format_decimal, outputs)
    _applicability_map_figure(summary, figures, save_figure, outputs)
    _anchor_concentration_figure(data, figures, save_figure, outputs)
