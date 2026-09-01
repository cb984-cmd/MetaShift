"""Create manuscript assets from receipt-verified frozen v0.5 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import verify_v05_answerability_results as result_verifier


OUTPUT_DIRECTORY = LATEX_ROOT / "generated"
TABLE_DIRECTORY = OUTPUT_DIRECTORY / "tables"
FIGURE_DIRECTORY = OUTPUT_DIRECTORY / "figures"
ASSET_MANIFEST = OUTPUT_DIRECTORY / "v05_answerability_asset_manifest.json"
LAYOUT_QA = OUTPUT_DIRECTORY / "v05_figure_layout_qa.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FINAL_PRINT_WIDTH_PT = 453.54

PRESENTATION_SOURCE_TYPE = "deterministic_receipt_bound_csv_presentation"
PRESENTATION_RENDERER = {
    "kind": "deterministic_csv_presentation_renderer",
    "source": "paper/latex/scripts/generate_v05_answerability_assets.py",
    "scope": (
        "Presentation-only visual derivatives from receipt-verified frozen result "
        "CSVs; no experiment execution, retuning, or outcome-dependent selection."
    ),
}
FIGURE_INPUT_FILES = {
    "fig_v05_answerability_frontier.png": ("v05_answerability_frontier.csv",),
    "fig_v05_structural_margin.png": ("v05_scope_pair_results.csv",),
    "fig_v05_risk_coverage.png": ("v05_policy_metrics.csv",),
    "fig_v05_certificate_validity.png": ("v05_certificate_validity.csv",),
    "fig_v05_failure_mode_map.png": ("v05_failure_mode_map.csv",),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate formal-report assets from frozen v0.5 artifacts."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write receipt-verified tables, macros, figures, and an asset manifest.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError(f"Not a valid PNG with an IHDR header: {path}")
    return struct.unpack(">II", header[16:24])


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        temporary.write(text)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def _result_input_records(
    input_names: tuple[str, ...], paths: dict[str, Path]
) -> list[dict[str, object]]:
    records = []
    for name in input_names:
        path = paths[name]
        records.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return records


def save_presentation_figure(figure: plt.Figure, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".png",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        figure.savefig(
            temporary_path,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="white",
            metadata={
                "Software": "MetaShift-Bench receipt-bound presentation renderer"
            },
        )
        width_px, height_px = png_dimensions(temporary_path)
        if width_px < 1200 or height_px < 500:
            raise ValueError(
                f"Presentation figure has insufficient dimensions: {destination.name}"
            )
        os.replace(temporary_path, destination)
    finally:
        plt.close(figure)
        if temporary_path.exists():
            temporary_path.unlink()


def figure_layout_record(
    output_name: str, input_names: tuple[str, ...], paths: dict[str, Path]
) -> dict[str, Any]:
    destination = FIGURE_DIRECTORY / output_name
    width_px, height_px = png_dimensions(destination)
    print_width_inches = FINAL_PRINT_WIDTH_PT / 72.0
    effective_ppi = width_px / print_width_inches
    input_records = _result_input_records(input_names, paths)
    checks = {
        "valid_png": destination.is_file(),
        "receipt_verified_csv_inputs": bool(input_records),
        "minimum_effective_print_resolution": effective_ppi >= 200.0,
        "nontrivial_dimensions": width_px >= 1200 and height_px >= 500,
    }
    return {
        "figure": output_name,
        "source_type": PRESENTATION_SOURCE_TYPE,
        "input_artifacts": input_records,
        "output_width_px": width_px,
        "output_height_px": height_px,
        "effective_print_ppi": round(effective_ppi, 2),
        "minimum_effective_print_ppi": 200.0,
        "final_print_width_pt": FINAL_PRINT_WIDTH_PT,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def _format_probability(value: object, digits: int = 6) -> str:
    if pd.isna(value):
        return "--"
    return f"{float(value):.{digits}f}"


def _format_percent(value: object) -> str:
    """Render a report-facing probability without implying excess precision."""

    if pd.isna(value):
        return "--"
    rendered = f"{100.0 * float(value):.1f}".rstrip("0").rstrip(".")
    return rendered + r"\%"


def _format_observed_error(value: object) -> str:
    """Distinguish zero observed errors from a population-risk assertion."""

    if pd.isna(value):
        return "--"
    if abs(float(value)) < 1e-12:
        return "0 observed errors"
    return _format_percent(value)


def _format_count(value: object) -> str:
    return f"{int(value):,}"


def _plain_percent(value: object, places: int = 1) -> str:
    """Use report-facing percentages in figures without decimal-log styling."""

    if pd.isna(value):
        return "--"
    rendered = f"{100.0 * float(value):.{places}f}".rstrip("0").rstrip(".")
    return rendered + "%"


def _compact_decimal(value: object, places: int = 2) -> str:
    if pd.isna(value):
        return "--"
    return f"{float(value):.{places}f}".rstrip("0").rstrip(".")


def _plain_observed_error(value: object) -> str:
    if pd.isna(value):
        return "--"
    if abs(float(value)) < 1e-12:
        return "0 observed errors"
    return _plain_percent(value)


def _overall(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[
        (frame["split"] == "evaluation")
        & (frame["group_type"] == "overall")
        & (frame["group_value"] == "all")
    ].copy()


def render_answerability_frontier_figure(frontier: pd.DataFrame) -> plt.Figure:
    selected = _overall(frontier)
    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    styles = {
        "target_only": ("#6B7280", "Target-only"),
        "comparative": ("#1976D2", "Comparative"),
        "comparative_plus_synthetic_design_information": (
            "#8E24AA",
            "Certificate-assisted",
        ),
    }
    for channel, (color, label) in styles.items():
        curve = selected.loc[selected["channel"] == channel].sort_values("alpha")
        axis.plot(
            curve["alpha"],
            curve["frontier_coverage"],
            marker="o",
            linewidth=2.2,
            markersize=5.5,
            color=color,
            label=label,
        )
    axis.set(
        xlabel="Allowed held-out scope-error tolerance ($\\alpha$)",
        ylabel="Answerable coverage",
        ylim=(-0.03, 1.03),
        xlim=(0.0, 0.21),
    )
    axis.set_xticks([0.01, 0.05, 0.10, 0.20])
    axis.set_yticks(np.arange(0.0, 1.01, 0.2))
    axis.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.grid(alpha=0.22)
    axis.legend(frameon=False)
    figure.tight_layout()
    return figure


def _heatmap_axes(
    axis: plt.Axes, q_order: list[str], h_order: list[str], title: str
) -> None:
    axis.set(
        title=title,
        xticks=np.arange(len(q_order)),
        xticklabels=["0%", "25%", "50%", "75%", "100%"],
        yticks=np.arange(len(h_order)),
        yticklabels=["0.04", "0.08", "0.12", "0.20"],
        xlabel="Nominal donor participation",
        ylabel="Signal strength $H$",
    )


def render_structural_margin_figure(pairs: pd.DataFrame) -> plt.Figure:
    selected = pairs.loc[pairs["split"] == "evaluation"].copy()
    selected["normalized_margin"] = (
        selected["q_effective_min"] * selected["h_min"]
    ) / (selected["local_error_bound"] + selected["shared_error_bound"])
    q_order = ["q0.00", "q0.25", "q0.50", "q0.75", "q1.00"]
    h_order = ["h0.04", "h0.08", "h0.12", "h0.20"]
    margin = selected.pivot_table(
        index="signal_h_name",
        columns="nominal_q_name",
        values="normalized_margin",
        aggfunc="median",
    ).reindex(index=h_order, columns=q_order)
    coverage = selected.pivot_table(
        index="signal_h_name",
        columns="nominal_q_name",
        values="certificate_answered",
        aggfunc="mean",
    ).reindex(index=h_order, columns=q_order)
    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.1), constrained_layout=True)
    margin_image = axes[0].imshow(
        margin.to_numpy(dtype=float), cmap="coolwarm", aspect="auto"
    )
    _heatmap_axes(axes[0], q_order, h_order, "Median structural-margin ratio")
    for row, h_name in enumerate(h_order):
        for column, q_name in enumerate(q_order):
            axes[0].text(
                column,
                row,
                _compact_decimal(margin.loc[h_name, q_name]),
                ha="center",
                va="center",
                fontsize=8,
            )
    figure.colorbar(
        margin_image,
        ax=axes[0],
        label=r"$q_{\min}H_{\min}/(B_L+B_S)$",
    )
    coverage_image = axes[1].imshow(
        coverage.to_numpy(dtype=float),
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        aspect="auto",
    )
    _heatmap_axes(axes[1], q_order, h_order, "Certificate-answered coverage")
    for row, h_name in enumerate(h_order):
        for column, q_name in enumerate(q_order):
            value = coverage.loc[h_name, q_name]
            axes[1].text(
                column,
                row,
                _plain_percent(value),
                ha="center",
                va="center",
                fontsize=8,
                color="white" if value < 0.55 else "black",
            )
    colorbar = figure.colorbar(
        coverage_image,
        ax=axes[1],
        label="Answered-pair coverage",
    )
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    colorbar.update_ticks()
    return figure


def render_risk_coverage_figure(metrics: pd.DataFrame) -> plt.Figure:
    selected = _overall(metrics)
    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    styles = {
        "target_only_forced": ("#6B7280", "o", "Target-only forced"),
        "comparative_forced": ("#1976D2", "s", "Comparative forced"),
        "confidence_selective": ("#E66A00", "^", "Confidence-selective"),
        "certificate_selective": ("#8E24AA", "D", "Certificate-selective"),
    }
    for policy, (color, marker, label) in styles.items():
        curve = selected.loc[selected["policy"] == policy].dropna(
            subset=["conditional_error"]
        )
        axis.scatter(
            curve["conditional_error"],
            curve["coverage"],
            label=label,
            color=color,
            marker=marker,
            s=52,
        )
    axis.set(
        xlabel="Held-out conditional scope error",
        ylabel="Coverage",
        xlim=(-0.01, 0.52),
        ylim=(-0.03, 1.03),
    )
    axis.set_xticks(np.arange(0.0, 0.51, 0.1))
    axis.set_yticks(np.arange(0.0, 1.01, 0.2))
    axis.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.grid(alpha=0.22)
    axis.legend(frameon=False, fontsize=8)
    figure.tight_layout()
    return figure


def render_certificate_validity_figure(certificate: pd.DataFrame) -> plt.Figure:
    selected = certificate.loc[
        (certificate["split"] == "evaluation")
        & (
            (certificate["group_type"] == "overall")
            | (certificate["group_type"] == "nominal_q")
        )
    ].copy()
    group_order = ["all", "q0.00", "q0.25", "q0.50", "q0.75", "q1.00"]
    selected = selected.set_index("group_value").reindex(group_order)
    rows = []
    for group, row in selected.iterrows():
        label = "Overall" if group == "all" else f"$q={int(round(float(group[1:]) * 100))}\\%$"
        rows.append(
            [
                label,
                _plain_percent(row["certificate_pair_coverage"]),
                _plain_observed_error(row["certificate_conditional_error"]),
                _plain_observed_error(row["envelope_violation_rate"]),
                _plain_percent(row["certificate_efficiency"]),
            ]
        )
    figure, axis = plt.subplots(figsize=(8.5, 2.6))
    axis.axis("off")
    rendered = axis.table(
        cellText=rows,
        colLabels=[
            "Group",
            "Pair coverage",
            "Observed scope error",
            "Envelope violations",
            "Oracle recovery",
        ],
        colWidths=[0.14, 0.17, 0.25, 0.25, 0.19],
        cellLoc="center",
        loc="center",
    )
    rendered.auto_set_font_size(False)
    rendered.set_fontsize(8)
    rendered.scale(1.0, 1.35)
    axis.set_title("Certificate behavior on held-out pairs", pad=10)
    figure.tight_layout()
    return figure


def render_failure_mode_figure(failure: pd.DataFrame) -> plt.Figure:
    selected = failure.loc[failure["split"] == "evaluation"].copy()
    grouped = selected.groupby(["signal_h_name", "nominal_q_name"], sort=False).agg(
        certificate_coverage=(
            "certificate_answered_pair_rows",
            lambda values: values.sum()
            / selected.loc[values.index, "total_pair_rows"].sum(),
        ),
        comparative_error_rate=(
            "comparative_forced_error_events",
            lambda values: values.sum()
            / (2 * selected.loc[values.index, "total_pair_rows"].sum()),
        ),
    )
    q_order = ["q0.00", "q0.25", "q0.50", "q0.75", "q1.00"]
    h_order = ["h0.04", "h0.08", "h0.12", "h0.20"]
    coverage = grouped["certificate_coverage"].unstack().reindex(
        index=h_order, columns=q_order
    )
    error = grouped["comparative_error_rate"].unstack().reindex(
        index=h_order, columns=q_order
    )
    figure, axes = plt.subplots(1, 2, figsize=(10.0, 4.1), constrained_layout=True)
    for axis, values, title, colorbar_label, cmap in (
        (
            axes[0],
            coverage,
            "Certificate-answered coverage",
            "Pair coverage",
            "viridis",
        ),
        (
            axes[1],
            error,
            "Comparative-forced error",
            "Scope-arm error rate",
            "magma_r",
        ),
    ):
        image = axis.imshow(
            values.to_numpy(dtype=float),
            cmap=cmap,
            vmin=0.0,
            vmax=1.0,
            aspect="auto",
        )
        _heatmap_axes(axis, q_order, h_order, title)
        for row, h_name in enumerate(h_order):
            for column, q_name in enumerate(q_order):
                value = values.loc[h_name, q_name]
                axis.text(
                    column,
                    row,
                    _plain_percent(value),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if value < 0.45 else "black",
                )
        colorbar = figure.colorbar(image, ax=axis, label=colorbar_label)
        colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        colorbar.update_ticks()
    return figure


def render_macros(
    frontier: pd.DataFrame,
    certificate: pd.DataFrame,
    failure: pd.DataFrame,
    policy: pd.DataFrame,
    bootstrap: pd.DataFrame,
    receipt: dict[str, Any],
) -> str:
    overall_frontier = _overall(frontier).set_index(["alpha", "channel"])
    overall_certificate = _overall(certificate).iloc[0]
    evaluation_failure = failure.loc[failure["split"] == "evaluation"]
    target_forced = _single_row(
        policy,
        "target-only forced policy",
        split="evaluation",
        group_type="overall",
        group_value="all",
        policy="target_only_forced",
    )
    comparative_forced = _single_row(
        policy,
        "comparative forced policy",
        split="evaluation",
        group_type="overall",
        group_value="all",
        policy="comparative_forced",
    )
    strict_confidence = policy.loc[
        (policy["split"] == "evaluation")
        & (policy["group_type"] == "overall")
        & (policy["group_value"] == "all")
        & (policy["policy"] == "confidence_selective")
        & (policy["alpha"].isin((0.01, 0.05, 0.10)))
    ]
    if len(strict_confidence) != 3 or strict_confidence["answered_events"].any():
        raise ValueError("Strict confidence-policy abstention differs from frozen v0.5 data.")
    q_zero_certificate = _single_row(
        certificate,
        "q=0 certificate diagnostic",
        split="evaluation",
        group_type="nominal_q",
        group_value="q0.00",
    )
    comparative_twenty = overall_frontier.loc[
        (0.20, "comparative")
    ]
    target_twenty = overall_frontier.loc[(0.20, "target_only")]
    gain_bootstrap = _single_row(
        bootstrap,
        "scope-answerability-gain bootstrap",
        metric="scope_answerability_gain",
        alpha=0.20,
    )
    grid_cells_per_component = int(
        receipt["observed_accounting"]["expected_grid_cells_per_component"]
    )
    return "\n".join(
        [
            "% Generated by scripts/generate_v05_answerability_assets.py. Do not edit manually.",
            r"\newcommand{\VFiveProtocolID}{" + str(receipt["protocol_id"]) + "}",
            r"\newcommand{\VFiveFreezeTag}{" + str(receipt["execution_tag"]) + "}",
            r"\newcommand{\VFiveExecutionCommit}{"
            + str(receipt["execution_git_commit"])
            + "}",
            r"\newcommand{\VFiveEvaluationComponents}{"
            + _format_count(
                int(receipt["observed_accounting"]["expected_pair_rows"]["evaluation"])
                // grid_cells_per_component
            )
            + "}",
            r"\newcommand{\VFiveCalibrationComponents}{"
            + _format_count(
                int(receipt["observed_accounting"]["expected_pair_rows"]["calibration"])
                // grid_cells_per_component
            )
            + "}",
            r"\newcommand{\VFiveCalibrationPairs}{"
            + _format_count(receipt["observed_accounting"]["expected_pair_rows"]["calibration"])
            + "}",
            r"\newcommand{\VFiveEvaluationPairs}{"
            + _format_count(receipt["observed_accounting"]["expected_pair_rows"]["evaluation"])
            + "}",
            r"\newcommand{\VFiveTotalPairs}{"
            + _format_count(receipt["observed_accounting"]["expected_pair_rows"]["total"])
            + "}",
            r"\newcommand{\VFiveEvaluationArms}{"
            + _format_count(
                receipt["observed_accounting"]["expected_scope_arm_events"]["evaluation"]
            )
            + "}",
            r"\newcommand{\VFiveTotalArms}{"
            + _format_count(
                receipt["observed_accounting"]["expected_scope_arm_events"]["total"]
            )
            + "}",
            r"\newcommand{\VFiveTargetFrontier}{"
            + _format_probability(target_twenty["frontier_coverage"])
            + "}",
            r"\newcommand{\VFiveTargetForcedCoverage}{"
            + _format_probability(target_forced["coverage"])
            + "}",
            r"\newcommand{\VFiveTargetForcedCoveragePercent}{"
            + _format_percent(target_forced["coverage"])
            + "}",
            r"\newcommand{\VFiveTargetForcedRisk}{"
            + _format_probability(target_forced["conditional_error"])
            + "}",
            r"\newcommand{\VFiveTargetForcedRiskPercent}{"
            + _format_percent(target_forced["conditional_error"])
            + "}",
            r"\newcommand{\VFiveComparativeForcedCoverage}{"
            + _format_probability(comparative_forced["coverage"])
            + "}",
            r"\newcommand{\VFiveComparativeForcedCoveragePercent}{"
            + _format_percent(comparative_forced["coverage"])
            + "}",
            r"\newcommand{\VFiveComparativeForcedRisk}{"
            + _format_probability(comparative_forced["conditional_error"])
            + "}",
            r"\newcommand{\VFiveComparativeForcedRiskPercent}{"
            + _format_percent(comparative_forced["conditional_error"])
            + "}",
            r"\newcommand{\VFiveComparativeForcedErrors}{"
            + _format_count(comparative_forced["error_events"])
            + "}",
            r"\newcommand{\VFiveStrictConfidenceAnsweredArms}{"
            + _format_count(strict_confidence["answered_events"].sum())
            + "}",
            (
                r"\newcommand{\VFiveComparativeFrontierTwenty}{"
                + _format_probability(comparative_twenty["frontier_coverage"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveComparativeFrontierTwentyPercent}{"
                + _format_percent(comparative_twenty["frontier_coverage"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveComparativeRiskTwenty}{"
                + _format_probability(comparative_twenty["frontier_conditional_error"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveComparativeRiskTwentyPercent}{"
                + _format_percent(comparative_twenty["frontier_conditional_error"])
                + "}"
            ),
            r"\newcommand{\VFiveComparativeGainLower}{"
            + _format_probability(gain_bootstrap["lower_95"])
            + "}",
            r"\newcommand{\VFiveComparativeGainLowerPercent}{"
            + _format_percent(gain_bootstrap["lower_95"])
            + "}",
            r"\newcommand{\VFiveComparativeGainUpper}{"
            + _format_probability(gain_bootstrap["upper_95"])
            + "}",
            r"\newcommand{\VFiveComparativeGainUpperPercent}{"
            + _format_percent(gain_bootstrap["upper_95"])
            + "}",
            (
                r"\newcommand{\VFiveCertificateCoverage}{"
                + _format_probability(overall_certificate["certificate_pair_coverage"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveCertificateCoveragePercent}{"
                + _format_percent(overall_certificate["certificate_pair_coverage"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveCertificateEfficiency}{"
                + _format_probability(overall_certificate["certificate_efficiency"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveCertificateEfficiencyPercent}{"
                + _format_percent(overall_certificate["certificate_efficiency"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveCertificateAnsweredPairs}{"
                + _format_count(overall_certificate["certificate_answered_pair_rows"])
                + "}"
            ),
            (
                r"\newcommand{\VFiveCertificateAnsweredArms}{"
                + _format_count(overall_certificate["certificate_answered_events"])
                + "}"
            ),
            r"\newcommand{\VFiveCertificateObservedError}{"
            + _format_probability(overall_certificate["certificate_conditional_error"])
            + "}",
            r"\newcommand{\VFiveCertificateObservedErrorDisplay}{"
            + _format_observed_error(overall_certificate["certificate_conditional_error"])
            + "}",
            (
                r"\newcommand{\VFiveNonpositiveMarginPairs}{"
                + _format_count(
                    evaluation_failure["nonpositive_structural_margin_pair_rows"].sum()
                )
                + "}"
            ),
            (
                r"\newcommand{\VFiveCertificateAbstentionPercent}{"
                + _format_percent(
                    evaluation_failure["nonpositive_structural_margin_pair_rows"].sum()
                    / receipt["observed_accounting"]["expected_pair_rows"]["evaluation"]
                )
                + "}"
            ),
            r"\newcommand{\VFiveEnvelopeViolations}{"
            + _format_count(
                evaluation_failure["envelope_violation_pair_rows"].sum()
            )
            + "}",
            (
                r"\newcommand{\VFiveQZeroPairs}{"
                + _format_count(
                    evaluation_failure["q0_observational_identity_pair_rows"].sum()
                )
                + "}"
            ),
            r"\newcommand{\VFiveQZeroCertificateAnsweredPairs}{"
            + _format_count(
                q_zero_certificate["certificate_answered_pair_rows"]
            )
            + "}",
            (
                r"\newcommand{\VFiveReceiptSHA}{"
                + str(receipt["receipt_sha256_short"])
                + "}"
            ),
            "",
        ]
    )


def render_frontier_table(frontier: pd.DataFrame, certificate: pd.DataFrame) -> str:
    selected = _overall(frontier)
    overall_certificate = _overall(certificate).iloc[0]
    certificate_answered_arms = _format_count(
        overall_certificate["certificate_answered_events"]
    )
    channels = {
        "target_only": "Target-only",
        "comparative": "Comparative",
        "comparative_plus_synthetic_design_information": "Certificate-assisted",
    }
    rows = []
    for alpha in (0.01, 0.05, 0.10, 0.20):
        values = selected.loc[
            (selected["alpha"] == alpha)
        ].set_index("channel")
        target = values.loc["target_only"]
        comparative = values.loc["comparative"]
        certificate = values.loc[
            "comparative_plus_synthetic_design_information"
        ]
        rows.append(
            "{} & {} & {} ({}) & {} ({}) \\\\".format(
                f"{100.0 * alpha:.0f}\\%",
                _format_percent(target["frontier_coverage"]),
                _format_percent(comparative["frontier_coverage"]),
                _format_observed_error(comparative["frontier_conditional_error"]),
                _format_percent(certificate["frontier_coverage"]),
                _format_observed_error(certificate["frontier_conditional_error"]),
            )
        )
    del channels
    return "\n".join(
        [
            r"\begin{table}[!ht]",
            r"\centering",
            r"\caption{Frozen finite-policy scope-answerability envelope on the",
            r"held-out target-fixed evaluation components. Parentheses give observed",
            r"conditional scope error for the policy attaining the displayed coverage;",
            r"\texttt{--} means no positive-coverage candidate qualified. The",
            r"certificate-assisted channel uses synthetic design information and is not",
            rf"an operational deployment channel. Its 0 observed errors are counted",
            rf"among {certificate_answered_arms} answered scope arms, not estimated",
            r"population risk.}",
            r"\label{tab:v05-frontier}",
            r"\small",
            r"\begin{tabular}{lrrr}",
            r"\toprule",
            r"Tolerance $\alpha$ & Target-only & Comparative & Certificate-assisted \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )


def render_certificate_table(certificate: pd.DataFrame) -> str:
    selected = certificate.loc[
        (certificate["split"] == "evaluation")
        & (certificate["group_type"] == "nominal_q")
    ].copy()
    order = ["q0.00", "q0.25", "q0.50", "q0.75", "q1.00"]
    selected = selected.set_index("group_value").reindex(order)
    rows = [
        "{} & {} & {} & {} \\\\".format(
            f"$q={int(round(float(value[1:]) * 100))}\\%$",
            _format_percent(row["certificate_pair_coverage"]),
            _format_observed_error(row["certificate_conditional_error"]),
            _format_percent(row["certificate_efficiency"]),
        )
        for value, row in selected.iterrows()
    ]
    return "\n".join(
        [
            r"\begin{table}[!ht]",
            r"\centering",
            r"\caption{Certificate behavior by nominal donor participation on held-out",
            r"target-fixed pairs. Oracle-region recovery is the share of predeclared",
            r"simulation-information-oracle answerable pairs recovered by the",
            r"certificate; it is undefined at $q=0$ because that negative-control",
            r"stratum has no oracle-answerable pairs. Across these strata, 0 observed",
            r"errors means 0 of 179,994 answered scope arms, not population risk.}",
            r"\label{tab:v05-certificate}",
            r"\small",
            r"\begin{tabular}{lrrr}",
            r"\toprule",
            r"Participation & Pair coverage & Observed error & Oracle-region recovery \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )


def render_failure_table(failure: pd.DataFrame, receipt: dict[str, Any]) -> str:
    selected = failure.loc[failure["split"] == "evaluation"]
    total_pairs = int(selected["total_pair_rows"].sum())
    certificate_answered_pairs = int(selected["certificate_answered_pair_rows"].sum())
    certificate_answered_arms = 2 * certificate_answered_pairs
    rows = [
        (
            "Target and donor observations identical at $q=0$",
            int(selected["q0_observational_identity_pair_rows"].sum()),
            "negative-control abstention stratum",
        ),
        (
            "Nonpositive structural margin",
            int(selected["nonpositive_structural_margin_pair_rows"].sum()),
            "certificate must abstain",
        ),
        (
            "Certificate-answered pairs",
            certificate_answered_pairs,
            f"0 errors among {certificate_answered_arms:,} answered arms",
        ),
        (
            "Envelope violations",
            int(selected["envelope_violation_pair_rows"].sum()),
            "none observed",
        ),
        (
            "Comparative-forced errors",
            int(selected["comparative_forced_error_events"].sum()),
            "among "
            + _format_count(
                receipt["observed_accounting"]["expected_scope_arm_events"]["evaluation"]
            )
            + " forced scope arms",
        ),
        (
            "Confidence policy at calibration $\\alpha=0.05$",
            int(selected["confidence_alpha_0_05_answered_events"].sum()),
            "no answered arms",
        ),
    ]
    rendered_rows = [
        f"{label} & {_format_count(count)} & {note} \\\\" for label, count, note in rows
    ]
    return "\n".join(
        [
            r"\begin{table}[!ht]",
            r"\centering",
            r"\caption{Predeclared failure and abstention accounting on",
            rf"{total_pairs:,} held-out target-fixed matched pairs. These rows are",
            r"retained rather than converted into a favorable single score. The rows",
            r"overlap and must not be summed: the $q=0$ row is a subset of the",
            r"nonpositive-margin row, while arm-level error rows use a different",
            r"denominator from pair-level rows.}",
            r"\label{tab:v05-failure-accounting}",
            r"\small",
            r"\begin{tabularx}{\linewidth}{@{}p{0.42\linewidth}rX@{}}",
            r"\toprule",
            r"Outcome & Count & Interpretation \\",
            r"\midrule",
            *rendered_rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
            "",
        ]
    )


def _single_row(
    frame: pd.DataFrame, description: str, **conditions: object
) -> pd.Series:
    selected = frame.copy()
    for column, value in conditions.items():
        selected = selected.loc[selected[column] == value]
    if len(selected) != 1:
        raise ValueError(
            f"Expected exactly one {description} row for {conditions}, found {len(selected)}."
        )
    return selected.iloc[0]


def build_claim_value_manifest(
    frontier: pd.DataFrame,
    certificate: pd.DataFrame,
    failure: pd.DataFrame,
    policy: pd.DataFrame,
    bootstrap: pd.DataFrame,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Derive display fragments for every v0.5 formal-paper numerical claim."""

    target_forced = _single_row(
        policy,
        "target-only forced policy",
        split="evaluation",
        group_type="overall",
        group_value="all",
        policy="target_only_forced",
    )
    comparative_forced = _single_row(
        policy,
        "comparative forced policy",
        split="evaluation",
        group_type="overall",
        group_value="all",
        policy="comparative_forced",
    )
    confidence_twenty = _single_row(
        policy,
        "confidence-selective alpha=.20 policy",
        split="evaluation",
        group_type="overall",
        group_value="all",
        policy="confidence_selective",
        alpha=0.20,
    )
    comparative_frontier_twenty = _single_row(
        frontier,
        "comparative alpha=.20 frontier",
        split="evaluation",
        group_type="overall",
        group_value="all",
        alpha=0.20,
        channel="comparative",
    )
    gain_bootstrap_twenty = _single_row(
        bootstrap,
        "scope-answerability-gain bootstrap",
        metric="scope_answerability_gain",
        alpha=0.20,
    )
    overall_certificate = _single_row(
        certificate,
        "overall certificate diagnostic",
        split="evaluation",
        group_type="overall",
        group_value="all",
    )
    certificate_by_q = certificate.loc[
        (certificate["split"] == "evaluation")
        & (certificate["group_type"] == "nominal_q")
    ].set_index("group_value")
    expected_q_groups = ("q0.00", "q0.25", "q0.50", "q0.75", "q1.00")
    if set(certificate_by_q.index) != set(expected_q_groups):
        raise ValueError("Certificate-by-participation rows differ from the preregistered grid.")
    evaluation_failure = failure.loc[failure["split"] == "evaluation"]
    if evaluation_failure.empty:
        raise ValueError("Frozen failure map has no evaluation rows.")

    grid_cells_per_component = int(
        receipt["observed_accounting"]["expected_grid_cells_per_component"]
    )
    total_pairs = int(evaluation_failure["total_pair_rows"].sum())
    q_zero_pairs = int(
        evaluation_failure["q0_observational_identity_pair_rows"].sum()
    )
    nonpositive_margin_pairs = int(
        evaluation_failure["nonpositive_structural_margin_pair_rows"].sum()
    )
    envelope_violations = int(evaluation_failure["envelope_violation_pair_rows"].sum())
    claims = {
        "V05-01": [
            _format_count(
                receipt["observed_accounting"]["expected_pair_rows"]["evaluation"]
            ),
            _format_count(
                receipt["observed_accounting"]["expected_scope_arm_events"]["evaluation"]
            ),
            str(
                int(receipt["observed_accounting"]["expected_pair_rows"]["evaluation"])
                // grid_cells_per_component
            ),
            str(
                int(receipt["observed_accounting"]["expected_pair_rows"]["calibration"])
                // grid_cells_per_component
            ),
            _format_count(
                receipt["observed_accounting"]["expected_pair_rows"]["calibration"]
            ),
            _format_count(
                receipt["observed_accounting"]["expected_scope_arm_events"]["total"]
            ),
        ],
        "V05-02": [
            _format_probability(target_forced["coverage"]),
            _format_probability(target_forced["conditional_error"]),
        ],
        "V05-03": [
            _format_probability(comparative_forced["coverage"]),
            _format_probability(comparative_forced["conditional_error"]),
            _format_count(comparative_forced["error_events"]),
        ],
        "V05-04": ["0.01", "0.05", "0.10", "0"],
        "V05-05": [
            _format_probability(comparative_frontier_twenty["frontier_coverage"]),
            _format_probability(comparative_frontier_twenty["frontier_conditional_error"]),
            _format_probability(gain_bootstrap_twenty["lower_95"]),
            _format_probability(gain_bootstrap_twenty["upper_95"]),
        ],
        "V05-06": [
            _format_probability(confidence_twenty["coverage"]),
            _format_probability(confidence_twenty["conditional_error"]),
        ],
        "V05-07": [
            _format_count(overall_certificate["certificate_answered_pair_rows"]),
            _format_count(overall_certificate["certificate_answered_events"]),
            _format_probability(overall_certificate["certificate_pair_coverage"]),
            _format_probability(overall_certificate["certificate_conditional_error"]),
        ],
        "V05-08": [
            _format_probability(overall_certificate["certificate_efficiency"]),
        ],
        "V05-09": [_format_count(q_zero_pairs), "0"],
        "V05-10": [
            _format_count(nonpositive_margin_pairs),
            _format_count(envelope_violations),
        ],
        "V05-11": [
            _format_probability(
                certificate_by_q.loc[group, "certificate_pair_coverage"]
            )
            for group in expected_q_groups
        ]
        + [
            _format_probability(
                certificate_by_q.loc[group, "certificate_efficiency"]
            )
            for group in expected_q_groups[1:]
        ],
        "V05-12": [
            str(receipt["execution_tag"]),
            str(receipt["execution_claim_tag"]),
            str(receipt["execution_git_commit"]),
            sha256(
                ROOT
                / "artifacts"
                / "v05_answerability_frontier"
                / "v05_execution_receipt.json"
            ),
        ],
    }
    if total_pairs != int(
        receipt["observed_accounting"]["expected_pair_rows"]["evaluation"]
    ):
        raise ValueError("Failure-map pair accounting differs from the execution receipt.")
    return {
        "schema_version": 1,
        "protocol_id": str(receipt["protocol_id"]),
        "execution_freeze_tag": str(receipt["execution_tag"]),
        "execution_claim_tag": str(receipt["execution_claim_tag"]),
        "source_receipt_sha256": sha256(
            ROOT
            / "artifacts"
            / "v05_answerability_frontier"
            / "v05_execution_receipt.json"
        ),
        "claims": {
            claim_id: {"expected_ledger_fragments": fragments}
            for claim_id, fragments in claims.items()
        },
    }


def result_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    output_directory = ROOT / str(protocol["output_contract"]["directory"])
    return {
        name: output_directory / name
        for name in protocol["output_contract"]["files"]
    }


def verify_receipt_binding(
    protocol: dict[str, Any], paths: dict[str, Path], receipt: dict[str, Any]
) -> None:
    if receipt.get("protocol_id") != protocol.get("protocol_id"):
        raise ValueError("Receipt protocol identifier differs from the frozen protocol.")
    required_output_names = set(protocol["output_contract"]["files"])
    output_hashes = receipt.get("output_hashes")
    if not isinstance(output_hashes, dict) or set(output_hashes) != required_output_names - {
        "v05_execution_receipt.json"
    }:
        raise ValueError("Receipt output inventory differs from the frozen output contract.")
    for name, expected in output_hashes.items():
        path = paths[name]
        if not path.is_file():
            raise FileNotFoundError(f"Frozen v0.5 result is missing: {path}")
        if expected.get("bytes") != path.stat().st_size or expected.get("sha256") != sha256(path):
            raise ValueError(f"Frozen v0.5 result differs from receipt: {path}")
    for relative_path, expected_hash in receipt.get("allowed_input_hashes", {}).items():
        path = ROOT / relative_path
        if not path.is_file() or result_verifier.runner.source_sha256(path) != expected_hash:
            raise ValueError(f"Frozen v0.5 source input differs from receipt: {relative_path}")


def load_verified_inputs() -> tuple[dict[str, Any], dict[str, Path], dict[str, pd.DataFrame]]:
    protocol = result_verifier.runner.read_protocol()
    paths = result_paths(protocol)
    receipt = json.loads(paths["v05_execution_receipt.json"].read_text(encoding="utf-8"))
    verify_receipt_binding(protocol, paths, receipt)
    receipt["receipt_sha256_short"] = sha256(
        paths["v05_execution_receipt.json"]
    )[:16] + r"\ldots"
    results = {
        "pairs": pd.read_csv(
            paths["v05_scope_pair_results.csv"],
            usecols=[
                "split",
                "nominal_q_name",
                "signal_h_name",
                "q_effective_min",
                "h_min",
                "local_error_bound",
                "shared_error_bound",
                "certificate_answered",
            ],
        ),
        "frontier": pd.read_csv(paths["v05_answerability_frontier.csv"]),
        "certificate": pd.read_csv(paths["v05_certificate_validity.csv"]),
        "failure": pd.read_csv(paths["v05_failure_mode_map.csv"]),
        "policy": pd.read_csv(paths["v05_policy_metrics.csv"]),
        "bootstrap": pd.read_csv(paths["v05_component_bootstrap.csv"]),
        "receipt": receipt,
    }
    return protocol, paths, results


def build_assets() -> dict[str, Any]:
    protocol, paths, results = load_verified_inputs()
    outputs: dict[Path, str] = {
        OUTPUT_DIRECTORY / "v05_answerability_macros.tex": render_macros(
            results["frontier"],
            results["certificate"],
            results["failure"],
            results["policy"],
            results["bootstrap"],
            results["receipt"],
        ),
        TABLE_DIRECTORY / "table_v05_frontier.tex": render_frontier_table(
            results["frontier"], results["certificate"]
        ),
        TABLE_DIRECTORY / "table_v05_certificate.tex": render_certificate_table(
            results["certificate"]
        ),
        TABLE_DIRECTORY / "table_v05_failure_accounting.tex": render_failure_table(
            results["failure"], results["receipt"]
        ),
        OUTPUT_DIRECTORY / "v05_claim_value_manifest.json": json.dumps(
            build_claim_value_manifest(
                results["frontier"],
                results["certificate"],
                results["failure"],
                results["policy"],
                results["bootstrap"],
                results["receipt"],
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }
    for path, content in outputs.items():
        write_text_atomic(path, content)
    figure_builders = {
        "fig_v05_answerability_frontier.png": lambda: render_answerability_frontier_figure(
            results["frontier"]
        ),
        "fig_v05_structural_margin.png": lambda: render_structural_margin_figure(
            results["pairs"]
        ),
        "fig_v05_risk_coverage.png": lambda: render_risk_coverage_figure(
            results["policy"]
        ),
        "fig_v05_certificate_validity.png": lambda: render_certificate_validity_figure(
            results["certificate"]
        ),
        "fig_v05_failure_mode_map.png": lambda: render_failure_mode_figure(
            results["failure"]
        ),
    }
    if set(figure_builders) != set(FIGURE_INPUT_FILES):
        raise RuntimeError("Figure rendering inventory differs from its input contract.")
    figure_outputs: list[Path] = []
    for output_name, builder in figure_builders.items():
        destination = FIGURE_DIRECTORY / output_name
        save_presentation_figure(builder(), destination)
        figure_outputs.append(destination)
    layout = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "source_receipt_sha256": sha256(paths["v05_execution_receipt.json"]),
        "presentation_renderer": PRESENTATION_RENDERER,
        "required_figure_count": len(FIGURE_INPUT_FILES),
        "figures": [
            figure_layout_record(output_name, input_names, paths)
            for output_name, input_names in FIGURE_INPUT_FILES.items()
        ],
    }
    layout["all_checks_passed"] = all(
        bool(record["all_checks_passed"]) for record in layout["figures"]
    )
    if not layout["all_checks_passed"]:
        raise ValueError("A v0.5 manuscript figure failed its layout contract.")
    write_text_atomic(LAYOUT_QA, json.dumps(layout, indent=2, sort_keys=True) + "\n")
    all_outputs = [*outputs, *figure_outputs, LAYOUT_QA]
    manifest = {
        "schema_version": 1,
        "generator": "paper/latex/scripts/generate_v05_answerability_assets.py",
        "protocol_id": protocol["protocol_id"],
        "execution_freeze_tag": results["receipt"]["execution_tag"],
        "execution_git_commit": results["receipt"]["execution_git_commit"],
        "execution_claim_tag": results["receipt"]["execution_claim_tag"],
        "source_receipt": {
            "path": str(paths["v05_execution_receipt.json"].relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "sha256": sha256(paths["v05_execution_receipt.json"]),
        },
        "presentation_renderer": PRESENTATION_RENDERER,
        "presentation_figure_inputs": {
            output_name: _result_input_records(input_names, paths)
            for output_name, input_names in FIGURE_INPUT_FILES.items()
        },
        "outputs": [
            {
                "path": str(path.relative_to(LATEX_ROOT)).replace("\\", "/"),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(all_outputs)
        ],
    }
    write_text_atomic(ASSET_MANIFEST, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    args = parse_args()
    if not args.write:
        raise SystemExit("Refusing to write manuscript assets without --write.")
    print(json.dumps(build_assets(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
