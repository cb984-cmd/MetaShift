"""Create the revised, evidence-bound vector figures for the formal report."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
from matplotlib.text import Text
from matplotlib.transforms import Bbox
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
FINAL_PRINT_WIDTH_PT = 453.54
MIN_NORMAL_FONT_PT = 8.5
MIN_NODE_FONT_PT = 9.0
MIN_PANEL_TITLE_PT = 10.0
NODE_HORIZONTAL_PADDING_PT = 6.0
NODE_VERTICAL_PADDING_PT = 4.0
MIN_TEXT_GAP_PT = 3.0


class LayoutNode:
    """A measured text-and-patch pair in axes-fraction coordinates."""

    def __init__(
        self,
        identifier: str,
        axis: plt.Axes,
        patch: FancyBboxPatch,
        text: Text,
        center: tuple[float, float],
        width: float,
        height: float,
    ) -> None:
        self.identifier = identifier
        self.axis = axis
        self.patch = patch
        self.text = text
        self.center = center
        self.width = width
        self.height = height


class FigureLayoutState:
    def __init__(self) -> None:
        self.nodes: list[LayoutNode] = []
        self.connectors: list[LayoutConnector] = []


class LayoutConnector:
    def __init__(
        self,
        source: LayoutNode,
        destination: LayoutNode,
        color: str,
        style: str,
        artist: Any,
    ) -> None:
        self.source = source
        self.destination = destination
        self.color = color
        self.style = style
        self.artist = artist


def text_inside_padded_box(
    text_box: Bbox,
    node_box: Bbox,
    *,
    horizontal_padding_px: float,
    vertical_padding_px: float,
) -> bool:
    """Return whether text is fully inside its node after required padding."""

    return bool(
        text_box.x0 >= node_box.x0 + horizontal_padding_px
        and text_box.x1 <= node_box.x1 - horizontal_padding_px
        and text_box.y0 >= node_box.y0 + vertical_padding_px
        and text_box.y1 <= node_box.y1 - vertical_padding_px
    )


def boxes_violate_minimum_gap(
    first: Bbox, second: Bbox, *, minimum_gap_px: float
) -> bool:
    """Return whether two independent text boxes overlap or approach too closely."""

    return bool(
        not (
        first.x1 + minimum_gap_px <= second.x0
        or second.x1 + minimum_gap_px <= first.x0
        or first.y1 + minimum_gap_px <= second.y0
        or second.y1 + minimum_gap_px <= first.y0
        )
    )


def _layout_state(figure: plt.Figure) -> FigureLayoutState:
    state = getattr(figure, "_metashift_layout_state", None)
    if state is None:
        state = FigureLayoutState()
        setattr(figure, "_metashift_layout_state", state)
    return state


def _points_to_pixels(figure: plt.Figure, points: float) -> float:
    return points * figure.dpi / 72.0


def _identifier_fragment(text: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in text)
    return cleaned.strip("_")[:48] or "empty"


def _element_identifier(
    text: Text, category: str, seen_identifiers: dict[str, int]
) -> str:
    base = text.get_gid() or f"{category}:{_identifier_fragment(text.get_text())}"
    seen_identifiers[base] = seen_identifiers.get(base, 0) + 1
    return f"{base}:{seen_identifiers[base]}"


def configure_figure_style() -> None:
    """Keep labels readable after inclusion at one report-column width."""

    plt.rcParams.update(
        {
            "font.size": 9.5,
            "font.family": "DejaVu Serif",
            "mathtext.fontset": "dejavuserif",
            "axes.titlesize": 10.5,
            "axes.labelsize": 9,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 9,
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
    fontsize: float = 9.5,
    hatch: str | None = None,
    weight: str = "normal",
    identifier: str | None = None,
) -> LayoutNode:
    """Draw a node after sizing it against its rendered text bounds."""

    figure = axis.figure
    required_fontsize = max(fontsize, MIN_NODE_FONT_PT)
    text_artist = axis.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=required_fontsize,
        fontweight=weight,
        color="#FFFFFF"
        if facecolor in {"#2563EB", "#B45309", "#64748B"}
        else "#111827",
        transform=axis.transAxes,
        clip_on=False,
    )
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    text_box = text_artist.get_window_extent(renderer)
    axis_box = axis.get_window_extent(renderer)
    horizontal_padding = _points_to_pixels(figure, NODE_HORIZONTAL_PADDING_PT)
    vertical_padding = _points_to_pixels(figure, NODE_VERTICAL_PADDING_PT)
    measured_width = (text_box.width + 2 * horizontal_padding) / axis_box.width
    measured_height = (text_box.height + 2 * vertical_padding) / axis_box.height
    width = max(width, measured_width)
    height = max(height, measured_height)
    node_identifier = identifier or f"node:{_identifier_fragment(text)}"
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
    patch.set_gid(f"{node_identifier}:patch")
    axis.add_patch(patch)
    text_artist.set_gid(node_identifier)
    text_artist.set_zorder(patch.get_zorder() + 1)
    node = LayoutNode(
        node_identifier, axis, patch, text_artist, (x, y), width, height
    )
    _layout_state(figure).nodes.append(node)
    return node


def _arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = "#475569",
    style: str = "-",
) -> Any:
    arrow = axis.annotate(
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
    arrow.set_gid("connector")
    return arrow


def _node_edge_toward(node: LayoutNode, destination: tuple[float, float]) -> tuple[float, float]:
    delta_x = destination[0] - node.center[0]
    delta_y = destination[1] - node.center[1]
    if delta_x == 0 and delta_y == 0:
        return node.center
    scale = 1.0 / max(
        abs(delta_x) / (node.width / 2),
        abs(delta_y) / (node.height / 2),
    )
    return (node.center[0] + delta_x * scale, node.center[1] + delta_y * scale)


def _arrow_between(
    source: LayoutNode,
    destination: LayoutNode,
    *,
    color: str = "#475569",
    style: str = "-",
) -> None:
    """Connect measured nodes at their borders rather than through their labels."""

    if source.axis is not destination.axis:
        raise ValueError("Measured node connectors require a shared axes.")
    arrow = _arrow(
        source.axis,
        _node_edge_toward(source, destination.center),
        _node_edge_toward(destination, source.center),
        color=color,
        style=style,
    )
    _layout_state(source.axis.figure).connectors.append(
        LayoutConnector(source, destination, color, style, arrow)
    )


def _comparison_shading(axis: plt.Axes) -> None:
    axis.axvspan(-60, -1, color="#DBEAFE", alpha=0.45, linewidth=0, zorder=0)
    axis.axvspan(0, 59, color="#FDE68A", alpha=0.38, linewidth=0, zorder=0)
    axis.axvline(0, color="#B91C1C", linestyle="--", linewidth=1.0, zorder=1)


def _finalize_axes(axis: plt.Axes) -> None:
    axis.grid(axis="both", color="#CBD5E1", alpha=0.55, linewidth=0.55)
    axis.set_axisbelow(True)


def _visible_text(text: Text) -> bool:
    return bool(text.get_visible() and text.get_text().strip())


def _collect_important_text(
    figure: plt.Figure, state: FigureLayoutState
) -> list[dict[str, Any]]:
    node_identifiers = {id(node.text): node.identifier for node in state.nodes}
    elements: list[dict[str, Any]] = []
    seen_artists: set[int] = set()
    seen_identifiers: dict[str, int] = {}

    def add(text: Text, category: str) -> None:
        if id(text) in seen_artists or not _visible_text(text):
            return
        seen_artists.add(id(text))
        node_identifier = node_identifiers.get(id(text))
        elements.append(
            {
                "identifier": _element_identifier(
                    text, "node_label" if node_identifier else category, seen_identifiers
                ),
                "category": "node_label" if node_identifier else category,
                "artist": text,
            }
        )

    for axis in figure.axes:
        add(axis.title, "panel_title")
        add(getattr(axis, "_left_title", axis.title), "panel_title")
        add(getattr(axis, "_right_title", axis.title), "panel_title")
        add(axis.xaxis.label, "axis_label")
        add(axis.yaxis.label, "axis_label")
        for text in axis.texts:
            add(text, "annotation")
        legend = axis.get_legend()
        if legend is not None:
            for text in legend.get_texts():
                add(text, "legend")
    for legend in figure.legends:
        for text in legend.get_texts():
            add(text, "legend")
    suptitle = getattr(figure, "_suptitle", None)
    for text in figure.texts:
        add(text, "figure_title" if text is suptitle else "explanatory_text")
    return elements


def _record_box(box: Bbox) -> dict[str, float]:
    return {
        "x0_px": round(float(box.x0), 2),
        "y0_px": round(float(box.y0), 2),
        "x1_px": round(float(box.x1), 2),
        "y1_px": round(float(box.y1), 2),
    }


def _boxes_intersect(first: Bbox, second: Bbox) -> bool:
    return not (
        first.x1 <= second.x0
        or second.x1 <= first.x0
        or first.y1 <= second.y0
        or second.y1 <= first.y0
    )


def _resize_nodes_for_final_layout(
    figure: plt.Figure, state: FigureLayoutState
) -> None:
    """Re-measure nodes after tight_layout or subplots_adjust changes an axes."""

    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    horizontal_padding = _points_to_pixels(figure, NODE_HORIZONTAL_PADDING_PT)
    vertical_padding = _points_to_pixels(figure, NODE_VERTICAL_PADDING_PT)
    changed = False
    for node in state.nodes:
        text_box = node.text.get_window_extent(renderer)
        axis_box = node.axis.get_window_extent(renderer)
        required_width = (
            text_box.width + 2 * horizontal_padding + 2.0
        ) / axis_box.width
        required_height = (
            text_box.height + 2 * vertical_padding + 2.0
        ) / axis_box.height
        width = max(node.width, required_width)
        height = max(node.height, required_height)
        if width > node.width or height > node.height:
            node.width = width
            node.height = height
            node.patch.set_bounds(
                node.center[0] - width / 2,
                node.center[1] - height / 2,
                width,
                height,
            )
            changed = True
    if changed:
        for connector in state.connectors:
            connector.artist.remove()
            connector.artist = _arrow(
                connector.source.axis,
                _node_edge_toward(connector.source, connector.destination.center),
                _node_edge_toward(connector.destination, connector.source.center),
                color=connector.color,
                style=connector.style,
            )
        figure.canvas.draw()


def inspect_figure_layout(figure: plt.Figure, figure_name: str) -> dict[str, Any]:
    """Measure all report-facing text before a vector figure is written.

    This check uses the Agg renderer used for generation, so a source build fails
    before a crowded label or a too-small node can become part of the PDF.
    """

    state = _layout_state(figure)
    _resize_nodes_for_final_layout(figure, state)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    text_elements = _collect_important_text(figure, state)
    scale_to_final_width = (FINAL_PRINT_WIDTH_PT / 72.0) / figure.get_figwidth()
    horizontal_padding = _points_to_pixels(figure, NODE_HORIZONTAL_PADDING_PT)
    vertical_padding = _points_to_pixels(figure, NODE_VERTICAL_PADDING_PT)
    minimum_gap = _points_to_pixels(figure, MIN_TEXT_GAP_PT)
    canvas = figure.bbox
    violations: list[dict[str, Any]] = []

    node_records: list[dict[str, Any]] = []
    for node in state.nodes:
        text_box = node.text.get_window_extent(renderer)
        patch_box = node.patch.get_window_extent(renderer)
        fits = text_inside_padded_box(
            text_box,
            patch_box,
            horizontal_padding_px=horizontal_padding,
            vertical_padding_px=vertical_padding,
        )
        node_records.append(
            {
                "identifier": node.identifier,
                "text_inside_node": fits,
                "text_bounds": _record_box(text_box),
                "node_bounds": _record_box(patch_box),
            }
        )
        if not fits:
            violations.append(
                {
                    "issue": "text_outside_required_node_padding",
                    "element": node.identifier,
                }
            )

    element_records: list[dict[str, Any]] = []
    for element in text_elements:
        text = element["artist"]
        text_box = text.get_window_extent(renderer)
        category = str(element["category"])
        effective_font = float(text.get_fontsize()) * scale_to_final_width
        required_font = (
            MIN_NODE_FONT_PT
            if category == "node_label"
            else MIN_PANEL_TITLE_PT
            if category in {"panel_title", "figure_title"}
            else MIN_NORMAL_FONT_PT
        )
        inside_canvas = bool(
            text_box.x0 >= canvas.x0
            and text_box.x1 <= canvas.x1
            and text_box.y0 >= canvas.y0
            and text_box.y1 <= canvas.y1
        )
        if effective_font + 0.01 < required_font:
            violations.append(
                {
                    "issue": "font_below_minimum",
                    "element": element["identifier"],
                    "category": category,
                    "effective_font_pt": round(effective_font, 2),
                    "minimum_font_pt": required_font,
                }
            )
        if not inside_canvas:
            violations.append(
                {
                    "issue": "text_outside_figure_canvas",
                    "element": element["identifier"],
                }
            )
        element_records.append(
            {
                "identifier": element["identifier"],
                "category": category,
                "font_size_source_pt": round(float(text.get_fontsize()), 2),
                "font_size_print_pt": round(effective_font, 2),
                "inside_canvas": inside_canvas,
                "bounds": _record_box(text_box),
            }
        )

    overlap_pairs: list[dict[str, str]] = []
    for index, first in enumerate(text_elements):
        first_box = first["artist"].get_window_extent(renderer)
        for second in text_elements[index + 1 :]:
            second_box = second["artist"].get_window_extent(renderer)
            if boxes_violate_minimum_gap(
                first_box, second_box, minimum_gap_px=minimum_gap
            ):
                overlap_pairs.append(
                    {
                        "first": str(first["identifier"]),
                        "second": str(second["identifier"]),
                    }
                )
    for pair in overlap_pairs:
        violations.append({"issue": "text_overlap_or_insufficient_gap", **pair})

    legend_overlap_records: list[dict[str, str]] = []
    legends = [
        *(legend for axis in figure.axes if (legend := axis.get_legend()) is not None),
        *figure.legends,
    ]
    for legend in legends:
        legend_box = legend.get_window_extent(renderer)
        for axis_index, axis in enumerate(figure.axes):
            if axis.has_data() and _boxes_intersect(legend_box, axis.get_window_extent(renderer)):
                legend_overlap_records.append(
                    {
                        "legend": "axes_legend"
                        if legend is axis.get_legend()
                        else "shared_figure_legend",
                        "data_axis": str(axis_index),
                    }
                )
    for record in legend_overlap_records:
        violations.append({"issue": "legend_over_data_region", **record})

    rgba = np.asarray(figure.canvas.buffer_rgba())
    luminance = (
        0.2126 * rgba[..., 0].astype(float)
        + 0.7152 * rgba[..., 1].astype(float)
        + 0.0722 * rgba[..., 2].astype(float)
    )
    nonwhite = luminance[luminance < 248.0]
    grayscale_contrast = (
        float(np.percentile(nonwhite, 95) - np.percentile(nonwhite, 5))
        if nonwhite.size
        else 0.0
    )
    grayscale_passed = bool(nonwhite.size and grayscale_contrast >= 35.0)
    if not grayscale_passed:
        violations.append(
            {
                "issue": "insufficient_grayscale_luminance_contrast",
                "contrast": round(grayscale_contrast, 2),
            }
        )

    smallest_font = min(
        (record["font_size_print_pt"] for record in element_records), default=0.0
    )
    return {
        "figure": figure_name,
        "final_print_width_pt": round(FINAL_PRINT_WIDTH_PT, 2),
        "source_width_in": round(float(figure.get_figwidth()), 3),
        "source_height_in": round(float(figure.get_figheight()), 3),
        "print_scale": round(scale_to_final_width, 4),
        "smallest_font_size_print_pt": round(float(smallest_font), 2),
        "text_inside_nodes_passed": not any(
            item["issue"] == "text_outside_required_node_padding" for item in violations
        ),
        "annotation_overlap_passed": not overlap_pairs,
        "canvas_boundary_passed": not any(
            item["issue"] == "text_outside_figure_canvas" for item in violations
        ),
        "legend_data_overlap_passed": not legend_overlap_records,
        "typography_passed": not any(
            item["issue"] == "font_below_minimum" for item in violations
        ),
        "grayscale_passed": grayscale_passed,
        "grayscale_luminance_contrast": round(grayscale_contrast, 2),
        "visual_inspection": {
            "source_rendered_geometry": "passed" if not violations else "failed",
            "final_page_crop_review": "pending_final_build",
        },
        "node_records": node_records,
        "elements": element_records,
        "overlap_pairs": overlap_pairs,
        "violations": violations,
        "all_checks_passed": not violations,
    }


def _synthetic_example_figure(
    example: dict[str, Any],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(6.3, 4.9), sharex="col")
    titles = {
        "local": "Local injection\nTarget only",
        "regional": "Regional injection\nTarget + donors",
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
        if column == 0:
            top.set_ylabel(r"Centered $\log(1+\mathrm{PM}_{2.5})$")
        else:
            top.set_ylabel("")
        _finalize_axes(top)

        bottom.plot(days, frame["residual"], color="#7C3AED", linewidth=1.25)
        _comparison_shading(bottom)
        bottom.axhline(0, color="#111827", linewidth=0.8)
        bottom.set_xlabel("Days relative to pseudo-anchor")
        if column == 0:
            bottom.set_ylabel("Centered log residual")
        else:
            bottom.set_ylabel("")
        bottom.set_xlim(-60, 60)
        _finalize_axes(bottom)
    figure.legend(
        *axes[0, 0].get_legend_handles_labels(),
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.055),
    )
    figure.suptitle(
        "Data-derived stable-window illustration (lexicographically first held-out case)",
        fontsize=11,
        y=0.985,
    )
    figure.text(
        0.5,
        0.01,
        "Blue: 60-day pre window. Amber: 60-day post window. "
        f"Frozen additive magnitude = {example['magnitude']:.2f} ug/m3.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.105, 1, 0.95))
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
    figure, axes = plt.subplots(
        1, 2, figsize=(6.3, 3.35), gridspec_kw={"width_ratios": [1.18, 0.82]}
    )
    schematic, distribution = axes
    schematic.axis("off")
    target = _box(
        schematic,
        0.13,
        0.68,
        0.24,
        0.18,
        "Target site\n+ POC",
        facecolor="#E0F2FE",
        identifier="donor_target_site",
    )
    same_site = _box(
        schematic,
        0.13,
        0.28,
        0.24,
        0.16,
        "Same-site POC\nexcluded",
        facecolor="#FEE2E2",
        edgecolor="#B91C1C",
        hatch="//",
        identifier="donor_same_site_poc",
    )
    _arrow_between(target, same_site, color="#B91C1C", style="--")
    donor_nodes: list[LayoutNode] = []
    for x, label in (
        (0.43, "Donor A"),
        (0.66, "Donor B"),
        (0.89, "Donor C+"),
    ):
        donor_nodes.append(
            _box(
                schematic,
                x,
                0.68,
                0.14,
                0.14,
                label,
                facecolor="#DCFCE7",
                identifier=f"donor_{label.split()[1].lower().replace('+', 'plus')}",
            )
        )
    for donor in donor_nodes:
        _arrow_between(target, donor)
    schematic.text(
        0.54,
        0.075,
        "Physical identity: State + County + Site.\nEach donor box represents one retained POC.",
        ha="center",
        va="center",
        fontsize=9,
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
            fontsize=9,
        )
    distribution.set_ylim(0, float(categories.max()) * 1.20)
    distribution.set_xlabel("Prequalified distinct donors")
    distribution.set_ylabel("Metadata anchors")
    distribution.set_title("Donor availability", fontweight="bold")
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
    figure, axis = plt.subplots(figsize=(6.3, 2.8))
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
            fontsize=9,
        )
    axis.axvspan(-60, -15, color="#F59E0B", alpha=0.18, zorder=0)
    axis.axvline(0, color="#B91C1C", linestyle="--", linewidth=1.1)
    axis.text(2, 2.36, r"$t_0$ anchor", color="#B91C1C", fontsize=9)
    axis.text(
        -37.5,
        -0.67,
        f"{windows['calibration_pre_overlap_calendar_dates']}-date calibration/pre overlap",
        ha="center",
        va="top",
        fontsize=9,
        color="#92400E",
    )
    axis.set_yticks(range(3), [label for label, _, _ in rows[::-1]])
    axis.set_xlim(-250, 80)
    axis.set_xticks([-240, -180, -120, -60, 0, 60])
    axis.set_xlabel(r"Calendar-day offset from $t_0$")
    axis.set_ylim(-0.95, 2.65)
    axis.set_title("Frozen inclusive date windows", fontweight="bold")
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
    figure, axis = plt.subplots(figsize=(6.3, 5.85))
    axis.axis("off")
    archives = _box(
        axis,
        0.5,
        0.92,
        0.28,
        0.10,
        "Public EPA\nbulk archives",
        facecolor="#E0F2FE",
        weight="bold",
        identifier="workflow_archives",
    )
    anchors = _box(
        axis,
        0.5,
        0.77,
        0.38,
        0.11,
        "Canonical daily series\n+ metadata anchors",
        facecolor="#DBEAFE",
        identifier="workflow_anchors",
    )
    stable = _box(
        axis,
        0.25,
        0.58,
        0.33,
        0.13,
        "Stable regimes\nknown synthetic truth",
        facecolor="#FEF3C7",
        identifier="workflow_stable_regimes",
    )
    real_anchors = _box(
        axis,
        0.75,
        0.58,
        0.33,
        0.13,
        f"All {real['total_anchors']} anchors\ndistinct donor screen",
        facecolor="#EDE9FE",
        identifier="workflow_real_anchors",
    )
    calibration = _box(
        axis,
        0.25,
        0.37,
        0.31,
        0.12,
        "66 calibration targets\nfreeze thresholds",
        facecolor="#FEF3C7",
        identifier="workflow_calibration",
    )
    evaluation = _box(
        axis,
        0.25,
        0.16,
        0.31,
        0.12,
        "80 held-out targets\nfixed metrics",
        facecolor="#FEF3C7",
        identifier="workflow_evaluation",
    )
    comparisons = _box(
        axis,
        0.75,
        0.37,
        0.34,
        0.13,
        f"{real['complete_comparisons']} comparisons\nor recorded abstention",
        facecolor="#EDE9FE",
        identifier="workflow_comparisons",
    )
    diagnostics = _box(
        axis,
        0.60,
        0.16,
        0.25,
        0.12,
        f"Diagnostics\nintervals, placebos, LOO",
        facecolor="#F1F5F9",
        identifier="workflow_diagnostics",
    )
    tiers_node = _box(
        axis,
        0.88,
        0.16,
        0.20,
        0.12,
        f"Audit tiers\n{tiers['supported_candidate_discontinuity']} / "
        f"{tiers['not_supported_by_available_evidence']} / "
        f"{tiers['inconclusive_insufficient_evidence']}",
        facecolor="#F1F5F9",
        identifier="workflow_tiers",
    )
    _arrow_between(archives, anchors)
    _arrow_between(anchors, stable)
    _arrow_between(anchors, real_anchors)
    _arrow_between(stable, calibration)
    _arrow_between(calibration, evaluation)
    _arrow_between(real_anchors, comparisons)
    _arrow_between(comparisons, diagnostics)
    _arrow_between(comparisons, tiers_node)
    axis.text(
        0.5,
        0.025,
        "Separate branches: known-truth evaluation versus complete observational audit.",
        ha="center",
        va="bottom",
        fontsize=9,
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
    figure, axis = plt.subplots(figsize=(6.3, 3.85))
    axis.axis("off")
    split_audit = data["split_audit"]
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
            (x - 0.21, 0.15),
            0.42,
            0.66,
            boxstyle="round,pad=0.014,rounding_size=0.02",
            transform=axis.transAxes,
            facecolor=color,
            edgecolor="#334155",
            linewidth=0.9,
        )
        axis.add_patch(patch)
        _box(
            axis,
            x,
            0.74,
            0.37,
            0.12,
            f"{title}\n{targets} targets | {inputs} inputs",
            facecolor="#FFFFFF",
            weight="bold",
            identifier=f"split_{title.lower().replace(' ', '_')}",
        )
        for offset_x, offset_y in ((-0.10, 0.50), (0.09, 0.50), (0.0, 0.31)):
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
            "Illustrative component insets:\nblue target; gray donor site",
            ha="center",
            va="center",
            fontsize=9,
            transform=axis.transAxes,
        )
    axis.plot(
        [0.5, 0.5],
        [0.13, 0.83],
        color="#B91C1C",
        linestyle="--",
        linewidth=1.2,
        transform=axis.transAxes,
    )
    axis.text(
        0.5,
        0.88,
        "0 shared physical inputs",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color="#991B1B",
        transform=axis.transAxes,
        bbox={"boxstyle": "round,pad=0.22", "facecolor": "#FFFFFF", "edgecolor": "none"},
    )
    axis.text(
        0.5,
        0.04,
        "Whole components prevent any target or donor physical site from crossing the split.",
        ha="center",
        va="center",
        fontsize=9,
        transform=axis.transAxes,
    )
    figure.suptitle(
        "Whole target-plus-donor components are assigned before held-out metrics",
        fontsize=11,
        y=0.985,
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
        ("local_effect_mae_log", "Local-effect MAE", "Lower is better", (0.0, 0.145), 3),
        ("macro_f1", "Macro-F1", "Higher is better", (0.0, 1.18), 3),
        ("false_positive_rate", "Regional FPR", "Lower is better", (0.0, 1.18), 3),
    )
    figure, axes = plt.subplots(1, 3, figsize=(6.3, 3.45), sharey=True)
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
                min(
                    value + (limits[1] - limits[0]) * 0.045,
                    limits[1] - (limits[1] - limits[0]) * 0.16,
                ),
                position,
                format_decimal(value, places),
                va="center",
                fontsize=9,
            )
        axis.set_xlim(*limits)
        axis.set_title(f"{title}\n{direction}", fontweight="bold")
        axis.set_xlabel("Held-out value")
        _finalize_axes(axis)
    axes[0].set_yticks(positions, [METHOD_LABELS[method] for method in METHOD_ORDER])
    axes[0].invert_yaxis()
    figure.suptitle(
        "Frozen held-out stable-synthetic comparison: 80 physical targets",
        fontsize=11,
        y=0.985,
    )
    figure.subplots_adjust(left=0.25, right=0.97, top=0.79, bottom=0.18, wspace=0.62)
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
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(6.3, 4.35),
        gridspec_kw={"width_ratios": [1.04, 0.96]},
    )
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
        class_axis.text(
            min(value + 0.035, 0.91),
            position,
            format_decimal(value, 3),
            va="center",
            fontsize=9,
        )
    class_axis.axhline(3.5, color="#94A3B8", linewidth=0.8)
    class_axis.set_xlim(0.0, 1.10)
    class_axis.set_yticks(positions, [METHOD_LABELS[method] for method in ALL_METHOD_ORDER])
    class_axis.invert_yaxis()
    class_axis.set_xlabel("Aggregate Macro-F1")
    class_axis.set_title("Attribution\nhigher is better", fontweight="bold")
    _finalize_axes(class_axis)
    figure.suptitle(
        "Frozen perturbation comparison (full matrix in appendix)",
        fontsize=11,
        y=0.985,
    )
    figure.legend(
        [
            Line2D(
                [0],
                [0],
                color="none",
                marker=METHOD_MARKERS[method],
                markerfacecolor=METHOD_COLORS[method],
                markeredgecolor="#111827",
            )
            for method in comparators
        ],
        [METHOD_LABELS[method] for method in comparators],
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.025),
        handletextpad=0.35,
    )
    figure.subplots_adjust(left=0.22, right=0.985, top=0.82, bottom=0.20, wspace=0.72)
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
    figure, axis = plt.subplots(figsize=(6.3, 2.8))
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
            fontsize=9,
            ha="left",
        )
    axis.set_xlim(-extent, extent)
    axis.set_ylim(-0.5, 1.45)
    axis.set_yticks(positions, [pair[1] for pair in pairs])
    axis.set_xlabel("Paired MAE difference: MetaShift - Standard SC")
    axis.set_title("Held-out paired bootstrap intervals (95%)", fontweight="bold")
    axis.text(-extent * 0.94, -0.37, "Negative: favors MetaShift", fontsize=9, ha="left")
    axis.text(extent * 0.94, -0.37, "Positive: favors Standard SC", fontsize=9, ha="right")
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
    figure, axis = plt.subplots(figsize=(6.3, 5.45))
    axis.axis("off")
    all_anchors = _box(
        axis,
        0.50,
        0.88,
        0.28,
        0.11,
        f"{total}\nprimary metadata anchors",
        facecolor="#E0F2FE",
        weight="bold",
        identifier="accounting_all_anchors",
    )
    donor_insufficient_node = _box(
        axis,
        0.23,
        0.63,
        0.27,
        0.14,
        f"{donor_insufficient}\ndonor insufficient",
        facecolor="#E2E8F0",
        hatch="//",
        identifier="accounting_donor_insufficient",
    )
    donor_eligible_node = _box(
        axis,
        0.68,
        0.63,
        0.27,
        0.14,
        f"{complete + input_failure}\nat least 3 distinct donors",
        facecolor="#DBEAFE",
        identifier="accounting_donor_eligible",
    )
    input_failure_node = _box(
        axis,
        0.39,
        0.38,
        0.24,
        0.14,
        f"{input_failure}\ninput-window failure",
        facecolor="#E2E8F0",
        hatch="//",
        identifier="accounting_input_failure",
    )
    complete_node = _box(
        axis,
        0.80,
        0.38,
        0.29,
        0.15,
        f"{complete}\ncomplete common comparison",
        facecolor="#EDE9FE",
        identifier="accounting_complete",
    )
    _arrow_between(all_anchors, donor_insufficient_node)
    _arrow_between(all_anchors, donor_eligible_node)
    _arrow_between(
        donor_eligible_node, input_failure_node, color="#B91C1C", style="--"
    )
    _arrow_between(donor_eligible_node, complete_node)
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
    leaf_nodes: list[LayoutNode] = []
    for x, y, label, color, hatch in leaves:
        leaf_nodes.append(
            _box(
                axis,
                x,
                y,
                0.23,
                0.14,
                label,
                facecolor=color,
                hatch=hatch,
                identifier=f"accounting_leaf_{int(x * 100)}",
            )
        )
    for node in leaf_nodes:
        _arrow_between(complete_node, node)
    axis.text(
        0.50,
        0.025,
        f"Reconciliation: {donor_insufficient} + {input_failure} + {complete} = {total}; "
        f"{supported} + {not_supported} + {complete_inconclusive} = {complete}.",
        ha="center",
        va="center",
        fontsize=9,
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
    figure, axes = plt.subplots(
        1, 2, figsize=(6.3, 3.3), gridspec_kw={"width_ratios": [0.94, 1.06]}
    )
    flow, histogram = axes
    flow.axis("off")
    complete_node = _box(
        flow,
        0.15,
        0.55,
        0.24,
        0.16,
        "228\ncomplete",
        facecolor="#EDE9FE",
        identifier="placebo_complete",
    )
    available_node = _box(
        flow,
        0.49,
        0.68,
        0.26,
        0.16,
        f"{complete_count}\n50+ dates",
        facecolor="#DBEAFE",
        identifier="placebo_available",
    )
    unavailable_node = _box(
        flow,
        0.49,
        0.29,
        0.25,
        0.16,
        f"{unavailable}\nunder 50",
        facecolor="#E2E8F0",
        hatch="//",
        identifier="placebo_unavailable",
    )
    at_100_node = _box(
        flow,
        0.84,
        0.79,
        0.23,
        0.16,
        f"{at_100}\n100 dates",
        facecolor="#C7D2FE",
        identifier="placebo_100_dates",
    )
    at_50_to_99_node = _box(
        flow,
        0.84,
        0.51,
        0.23,
        0.16,
        f"{at_50_to_99}\n50--99 dates",
        facecolor="#DBEAFE",
        identifier="placebo_50_to_99_dates",
    )
    _arrow_between(complete_node, available_node)
    _arrow_between(complete_node, unavailable_node, color="#B91C1C", style="--")
    _arrow_between(available_node, at_100_node)
    _arrow_between(available_node, at_50_to_99_node)
    flow.text(
        0.5,
        0.06,
        "100-date cohort is nested in the 50+-date cohort.",
        ha="center",
        fontsize=9,
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
    histogram.text(
        0.12,
        histogram.get_ylim()[1] * 0.93,
        "Frozen 0.10 screen",
        color="#991B1B",
        fontsize=9,
    )
    histogram.set_xlim(0, 1)
    histogram.set_xlabel("Raw placebo probability")
    histogram.set_ylabel("Complete events")
    histogram.set_title("Placebo probability", fontweight="bold")
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
    figure, axes = plt.subplots(1, 2, figsize=(6.3, 3.65), sharey=True)
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
            coverage_axis.text(
                value - 0.020 if value >= 0.93 else value + 0.020,
                position + offset,
                f"{value * 100:.1f}%",
                ha="right" if value >= 0.93 else "left",
                va="center",
                fontsize=9,
            )
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
            width_axis.text(
                width + 0.016,
                position + offset,
                f"{width:.3f}",
                va="center",
                fontsize=9,
            )
    coverage_axis.axvline(0.95, color="#334155", linestyle="--", linewidth=0.9)
    coverage_axis.axvline(0.90, color="#334155", linestyle=":", linewidth=1.1)
    coverage_axis.set_xlim(0, 1.04)
    coverage_axis.set_xlabel("Empirical coverage (full 0--100% scale)")
    coverage_axis.set_title("Held-out coverage", fontweight="bold")
    coverage_axis.set_yticks(positions, [METHOD_LABELS[method] for method in METHOD_ORDER])
    coverage_axis.invert_yaxis()
    maximum_width = max(
        conditional["mean_interval_width_log"].max(),
        conformal["mean_interval_width_log"].max(),
    )
    width_axis.set_xlim(0, float(maximum_width) * 1.32 + 0.03)
    width_axis.set_xlabel("Mean interval width (log units)")
    width_axis.set_title("Width alongside coverage", fontweight="bold")
    for axis in axes:
        _finalize_axes(axis)
    figure.legend(
        [
            Line2D([0], [0], color="#111827", marker="o", linestyle="none"),
            Line2D([0], [0], color="#111827", marker="D", linestyle="none"),
            Line2D([0], [0], color="#334155", linestyle="--"),
            Line2D([0], [0], color="#334155", linestyle=":"),
        ],
        [
            "Conditional bootstrap (95% nominal)",
            "Split conformal (90% nominal)",
            "95% nominal guide",
            "90% nominal guide",
        ],
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.015),
    )
    figure.tight_layout(rect=(0, 0.17, 1, 1))
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
    figure, axes = plt.subplots(
        1, 2, figsize=(6.3, 3.55), gridspec_kw={"width_ratios": [1.04, 0.96]}
    )
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
                    fontsize=9,
                )
        bottom += proportions
    tiers_axis.set_ylim(0, 112)
    tiers_axis.set_ylabel("All anchors (%)")
    tiers_axis.set_title("Tier composition\nunder frozen rules", fontweight="bold")
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
        radius_axis.text(radius, value + 10, str(int(value)), ha="center", fontsize=9)
    radius_axis.set_xlim(40, 210)
    radius_axis.set_ylim(0, max(values) * 1.16)
    radius_axis.set_xticks(radii)
    radius_axis.set_xlabel("Maximum donor radius (km)")
    radius_axis.set_ylabel("Anchors with 3+ donors")
    radius_axis.set_title("Donor-radius\nsensitivity", fontweight="bold")
    _finalize_axes(radius_axis)
    figure.text(
        0.5,
        0.10,
        "Strict: p,q<=0.05 and LOO>=0.95; primary: <=0.10 and >=0.90; lenient: <=0.20 and >=0.80.",
        ha="center",
        fontsize=9,
    )
    figure.legend(
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.005),
    )
    figure.subplots_adjust(left=0.13, right=0.98, top=0.80, bottom=0.27, wspace=0.80)
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
    axis.set_title(title, fontsize=10.5, fontweight="bold", pad=5)
    positions = np.linspace(0.80, 0.18, len(steps))
    previous: LayoutNode | None = None
    for index, ((label, value), y) in enumerate(zip(steps, positions, strict=True)):
        face = color if index == len(steps) - 1 else "#E2E8F0"
        hatch = "//" if value == 0 else None
        node = _box(
            axis,
            0.5,
            float(y),
            0.72,
            0.14,
            f"{value}\n{label}",
            facecolor=face,
            hatch=hatch,
            identifier=f"ladder_{_identifier_fragment(title)}_{index + 1}",
        )
        if previous is not None:
            _arrow_between(previous, node)
        previous = node


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
    figure, axes = plt.subplots(2, 2, figsize=(6.3, 5.3))
    poc = summary["hourly_same_site_poc"]
    _draw_ladder(
        axes[0, 0],
        "Same-site POC context",
        [
            ("candidate anchors", int(poc["candidate_events"])),
            ("paired hourly windows", int(poc["usable_paired_events"])),
            ("daily/hourly agreement", int(poc["daily_hourly_direction_agreement"])),
        ],
        "#DBEAFE",
    )
    _draw_ladder(
        axes[0, 1],
        "QA collocation context",
        [
            ("QA candidates", int(qa["candidates"])),
            ("target POC match", int(qa["target_poc_matched"])),
            (
                "adequate paired windows",
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
            ("dated site confirmation", int(documents["site_specific_dated_confirmations"])),
        ],
        "#FEE2E2",
    )
    secondary = summary["secondary_88502"]
    _draw_ladder(
        axes[1, 1],
        "Separate 88502 pipeline",
        [
            ("metadata anchors", int(secondary["eligible_anchors"])),
            ("3+ donor eligible", secondary_donor_eligible),
            ("complete common comparisons", secondary_complete),
        ],
        "#EDE9FE",
    )
    figure.text(
        0.5,
        0.015,
        "All pathways are contextual evidence or feasibility checks.\n"
        "None establishes a physical cause of a metadata transition.",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.075, 1, 1))
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


def _case_study_figures(
    cases: list[dict[str, Any]],
    figures: Path,
    save_figure: SaveFigure,
    outputs: list[dict[str, Any]],
) -> None:
    """Separate complete-case evidence from the intentionally unavailable case."""

    complete_cases = [case for case in cases if case["audit_status"] == "complete"]
    abstention_cases = [case for case in cases if case["audit_status"] != "complete"]
    if len(complete_cases) != 2 or len(abstention_cases) != 1:
        raise RuntimeError("The deterministic case contract must contain two complete cases and one abstention.")

    figure, axes = plt.subplots(
        3,
        len(complete_cases),
        figsize=(6.3, 6.55),
        squeeze=False,
        gridspec_kw={"height_ratios": [1.14, 0.94, 0.90]},
    )
    complete_effect_bounds = [
        value
        for case in complete_cases
        for value in (*case["fixed_interval"], *case["nested_interval"], case["log_effect"])
        if value is not None
    ]
    effect_extent = max(abs(float(value)) for value in complete_effect_bounds) * 1.25
    for column, case in enumerate(complete_cases):
        top, residual_axis, interval_axis = axes[:, column]
        anchor_date = case["anchor_date"]
        group = case["case_group"]
        target = case["target"].loc[case["visible_start"] : case["visible_end"]]
        counterfactual = case["counterfactual"].loc[
            case["visible_start"] : case["visible_end"]
        ]
        residual = case["residual"].loc[case["visible_start"] : case["visible_end"]]
        display = pd.concat(
            [
                target.rename("target"),
                counterfactual.rename("counterfactual"),
                residual.rename("residual"),
            ],
            axis="columns",
        ).dropna()
        days = (display.index - anchor_date).days
        top.plot(days, display["target"], color="#111827", linewidth=1.1, label="Target")
        top.plot(
            days,
            display["counterfactual"],
            color="#4C566A",
            linewidth=1.0,
            linestyle="--",
            label="Reliability-prior composite",
        )
        _comparison_shading(top)
        top.set_xlim(-60, 60)
        top.set_title(
            f"{group}\nanchor {anchor_date.date().isoformat()}",
            fontsize=10.5,
            fontweight="bold",
        )
        _finalize_axes(top)

        residual_axis.plot(days, display["residual"], color="#7C3AED", linewidth=1.1)
        _comparison_shading(residual_axis)
        residual_axis.axhline(0, color="#111827", linewidth=0.7)
        residual_axis.set_xlim(-60, 60)
        residual_axis.set_xlabel("Days relative to anchor")
        _finalize_axes(residual_axis)

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
        interval_axis.plot(effect, 1, marker="^", color="#3B82F6", markersize=5.0)
        interval_axis.plot(
            [nested_lower, nested_upper],
            [0, 0],
            color="#7C3AED",
            linewidth=1.6,
            linestyle="--",
            solid_capstyle="butt",
        )
        interval_axis.plot(effect, 0, marker="D", color="#7C3AED", markersize=4.5)
        interval_axis.set_xlim(-effect_extent, effect_extent)
        interval_axis.set_yticks([0, 1], ["Nested", "Fixed"] if column == 0 else [])
        interval_axis.set_xlabel("Log effect")
        interval_axis.text(
            0.5,
            0.05,
            f"Saved placebo n={int(case['placebo_count'])}; p={case['placebo_p_value']:.3f}\n"
            f"LOO direction={case['leave_one_donor_out_fraction']:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
            transform=interval_axis.transAxes,
        )
        _finalize_axes(interval_axis)
        if column == 0:
            top.set_ylabel(r"PM$_{2.5}$ (ug/m$^3$)")
            residual_axis.set_ylabel("Centered log residual")

    figure.suptitle(
        "Deterministically selected complete comparisons",
        fontsize=11,
        y=0.985,
    )
    figure.legend(
        *axes[0, 0].get_legend_handles_labels(),
        loc="lower center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.015),
    )
    figure.subplots_adjust(
        left=0.15,
        right=0.985,
        top=0.87,
        bottom=0.13,
        wspace=0.36,
        hspace=0.58,
    )
    case_sources = [
        "artifacts/real_transition_88101_evidence_tiers.csv",
        "artifacts/real_transition_88101_method_results.csv",
        "artifacts/real_transition_88101_event_intervals.csv",
        "artifacts/time_placebo_summary.csv",
        "paper/latex/configs/case_study_rendering_v2.json",
        "artifacts/data_gate/source_manifest.json",
        "artifacts/data_gate/geographic_controls.csv",
    ]
    save_figure(
        figure,
        figures / "fig_case_studies_complete.pdf",
        "Deterministic complete representative audit cases",
        case_sources,
        outputs,
    )

    abstention = abstention_cases[0]
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(6.3, 3.2),
        gridspec_kw={"width_ratios": [1.30, 0.70]},
    )
    series_axis, decision_axis = axes
    anchor_date = abstention["anchor_date"]
    target = abstention["target"].loc[
        abstention["visible_start"] : abstention["visible_end"]
    ]
    days = (target.index - anchor_date).days
    series_axis.plot(days, target, color="#111827", linewidth=1.15)
    _comparison_shading(series_axis)
    series_axis.set_xlim(-60, 60)
    series_axis.set_xlabel("Days relative to anchor")
    series_axis.set_ylabel(r"PM$_{2.5}$ (ug/m$^3$)")
    series_axis.set_title(
        f"Inconclusive anchor\n{anchor_date.date().isoformat()}",
        fontsize=10.5,
        fontweight="bold",
    )
    _finalize_axes(series_axis)
    decision_axis.axis("off")
    no_counterfactual = _box(
        decision_axis,
        0.5,
        0.68,
        0.72,
        0.19,
        "No common cross-site\ncounterfactual",
        facecolor="#E2E8F0",
        hatch="//",
        weight="bold",
        identifier="abstention_no_counterfactual",
    )
    reason = _box(
        decision_axis,
        0.5,
        0.31,
        0.72,
        0.19,
        "Reason: fewer than 3\nqualified physical donors",
        facecolor="#FEE2E2",
        edgecolor="#B91C1C",
        identifier="abstention_reason",
    )
    _arrow_between(no_counterfactual, reason, color="#B91C1C", style="--")
    figure.suptitle(
        "Deterministic abstention example: no counterfactual is imputed",
        fontsize=11,
        y=0.985,
    )
    figure.subplots_adjust(left=0.12, right=0.98, top=0.74, bottom=0.17, wspace=0.34)
    save_figure(
        figure,
        figures / "fig_case_studies_abstention.pdf",
        "Deterministic representative audit abstention",
        case_sources,
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
    figure, axis = plt.subplots(figsize=(6.3, 4.15))
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
            fontsize=10.5,
            fontweight="bold",
            transform=axis.transAxes,
        )
    rows = (
        (
            f"Donor insufficient\n{audit['insufficient_geographic_donors']} anchors",
            "Inconclusive:\ncomparison unavailable",
            "No physical cause\nestablished",
            "#E2E8F0",
        ),
        (
            f"Input-window failure\n{audit['estimator_input_failure']} anchors",
            "Inconclusive:\ninput unavailable",
            "No imputed effect\nor interval",
            "#E2E8F0",
        ),
        (
            f"Complete comparison\n{audit['complete_comparisons']} anchors",
            "Audit tiers:\n"
            f"{tiers['supported_candidate_discontinuity']} / "
            f"{tiers['not_supported_by_available_evidence']} / "
            f"{audit['complete_comparisons'] - tiers['supported_candidate_discontinuity'] - tiers['not_supported_by_available_evidence']}",
            "No verified fault,\nreplacement, or bias",
            "#EDE9FE",
        ),
    )
    for index, (y, (left, middle, right, color)) in enumerate(
        zip((0.71, 0.45, 0.20), rows, strict=True)
    ):
        left_node = _box(
            axis,
            0.17,
            y,
            0.28,
            0.18,
            left,
            facecolor=color,
            identifier=f"applicability_observed_{index + 1}",
        )
        middle_node = _box(
            axis,
            0.50,
            y,
            0.28,
            0.18,
            middle,
            facecolor="#DBEAFE",
            identifier=f"applicability_output_{index + 1}",
        )
        right_node = _box(
            axis,
            0.83,
            y,
            0.28,
            0.18,
            right,
            facecolor="#FEF3C7",
            identifier=f"applicability_boundary_{index + 1}",
        )
        _arrow_between(left_node, middle_node)
        _arrow_between(middle_node, right_node)
    axis.text(
        0.5,
        0.025,
        "Applicability map, not a classifier: station records and human technical review remain required.",
        ha="center",
        va="center",
        fontsize=9,
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
    figure, axes = plt.subplots(
        1, 2, figsize=(6.3, 3.4), gridspec_kw={"width_ratios": [0.9, 1.1]}
    )
    years_axis, pair_axis = axes
    colors = ["#94A3B8"] * len(year_counts)
    colors[list(year_counts.index).index(2023)] = "#B45309"
    bars = years_axis.bar(year_counts.index.astype(str), year_counts.to_numpy(), color=colors, edgecolor="#334155", linewidth=0.4)
    for bar, value in zip(bars, year_counts.to_numpy(), strict=True):
        years_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 9,
            str(int(value)),
            ha="center",
            fontsize=9,
        )
    years_axis.set_ylim(0, max(year_counts) * 1.23)
    years_axis.tick_params(axis="x", labelrotation=30)
    years_axis.set_ylabel("Reported metadata anchors")
    years_axis.set_title("Anchor dates in the frozen snapshot", fontweight="bold")
    _finalize_axes(years_axis)

    labels = ["236 -> 636", "238 -> 638", "Other 2023 pairs"]
    values = [pair_one, pair_two, other]
    bars = pair_axis.barh(labels, values, color=["#B45309", "#D97706", "#94A3B8"], edgecolor="#334155", linewidth=0.4)
    for bar, value in zip(bars, values, strict=True):
        pair_axis.text(
            value + 6,
            bar.get_y() + bar.get_height() / 2,
            str(value),
            va="center",
            fontsize=9,
        )
    pair_axis.set_xlim(0, max(values) * 1.30 + 12)
    pair_axis.set_xlabel("2023 metadata anchors")
    pair_axis.set_title("Named code-pair concentration", fontweight="bold")
    _finalize_axes(pair_axis)
    figure.text(
        0.5,
        0.015,
        "Alignment-enabled new-code labels are descriptive metadata.\n"
        "They do not establish why records changed.",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.08, 1, 1))
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
    _case_study_figures(cases, figures, save_figure, outputs)
    _applicability_map_figure(summary, figures, save_figure, outputs)
    _anchor_concentration_figure(data, figures, save_figure, outputs)
