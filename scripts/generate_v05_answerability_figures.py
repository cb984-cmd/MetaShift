"""Render v0.5 figures from frozen result files without rerunning the experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_v05_answerability_frontier as runner
from scripts import verify_v05_answerability_results as result_verifier


FIGURE_DIRECTORY = ROOT / "figures" / "v05_answerability_frontier"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _paths(protocol: dict) -> dict[str, Path]:
    directory = ROOT / protocol["output_contract"]["directory"]
    return {name: directory / name for name in protocol["output_contract"]["files"]}


def _validate_frozen_inputs(protocol: dict) -> dict[str, Path]:
    verification = result_verifier.build_report(replay=True)
    if not verification["all_checks_passed"]:
        raise RuntimeError(
            "Refusing figure generation because frozen-result verification failed."
        )
    paths = _paths(protocol)
    receipt = json.loads(paths["v05_execution_receipt.json"].read_text(encoding="utf-8"))
    hashes = receipt.get("output_hashes", {})
    expected = set(paths).difference({"v05_execution_receipt.json"})
    if set(hashes) != expected:
        raise ValueError("Frozen receipt does not bind exactly the figure input files.")
    for name in expected:
        if hashes[name]["sha256"] != sha256(paths[name]):
            raise ValueError(f"Frozen input hash differs from receipt: {name}")
    return paths


def _read_results(paths: dict[str, Path]) -> dict[str, pd.DataFrame]:
    return {
        "pairs": pd.read_csv(paths["v05_scope_pair_results.csv"]),
        "metrics": pd.read_csv(paths["v05_policy_metrics.csv"]),
        "frontier": pd.read_csv(paths["v05_answerability_frontier.csv"]),
        "certificate": pd.read_csv(paths["v05_certificate_validity.csv"]),
        "failure": pd.read_csv(paths["v05_failure_mode_map.csv"]),
    }


def _save(figure: plt.Figure, name: str) -> Path:
    FIGURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIRECTORY / name
    figure.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(figure)
    return path


def answerability_frontier_figure(frontier: pd.DataFrame) -> Path:
    selected = frontier.loc[
        (frontier["group_type"] == "overall") & (frontier["group_value"] == "all")
    ].copy()
    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    styles = {
        "target_only": ("#9b9b9b", "Target-only"),
        "comparative": ("#1976d2", "Comparative"),
        "comparative_plus_synthetic_design_information": (
            "#8e24aa",
            "Certificate-assisted",
        ),
    }
    for channel, (color, label) in styles.items():
        curve = selected.loc[selected["channel"] == channel].sort_values("alpha")
        axis.plot(
            curve["alpha"],
            curve["frontier_coverage"],
            marker="o",
            linewidth=2,
            color=color,
            label=label,
        )
    axis.set(
        xlabel="Allowed held-out scope error ($\\alpha$)",
        ylabel="Finite-policy answerable coverage",
        ylim=(-0.03, 1.03),
        xlim=(0.0, 0.21),
    )
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    return _save(figure, "v05_answerability_frontier.png")


def structural_margin_figure(pairs: pd.DataFrame) -> Path:
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
    image = axes[0].imshow(margin.to_numpy(dtype=float), cmap="coolwarm", aspect="auto")
    axes[0].set(
        title="Median normalized lower margin",
        xticks=np.arange(len(q_order)),
        xticklabels=q_order,
        yticks=np.arange(len(h_order)),
        yticklabels=h_order,
        xlabel="Nominal donor participation",
        ylabel="Signal",
    )
    for row, h_name in enumerate(h_order):
        for column, q_name in enumerate(q_order):
            axes[0].text(
                column,
                row,
                f"{margin.loc[h_name, q_name]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
            )
    figure.colorbar(image, ax=axes[0], label="$q_{min}H_{min}/(B_L+B_S)$")
    image = axes[1].imshow(
        coverage.to_numpy(dtype=float), cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto"
    )
    axes[1].set(
        title="Certificate answered-pair coverage",
        xticks=np.arange(len(q_order)),
        xticklabels=q_order,
        yticks=np.arange(len(h_order)),
        yticklabels=h_order,
        xlabel="Nominal donor participation",
        ylabel="Signal",
    )
    for row, h_name in enumerate(h_order):
        for column, q_name in enumerate(q_order):
            axes[1].text(
                column,
                row,
                f"{coverage.loc[h_name, q_name]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if coverage.loc[h_name, q_name] < 0.55 else "black",
            )
    figure.colorbar(image, ax=axes[1], label="Answered-pair proportion")
    return _save(figure, "v05_structural_margin_phase_diagram.png")


def risk_coverage_figure(metrics: pd.DataFrame) -> Path:
    selected = metrics.loc[
        (metrics["split"] == "evaluation")
        & (metrics["group_type"] == "overall")
        & (metrics["group_value"] == "all")
    ].copy()
    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    styles = {
        "target_only_forced": ("#9b9b9b", "o", "Target-only forced"),
        "comparative_forced": ("#1976d2", "s", "Comparative forced"),
        "confidence_selective": ("#ef6c00", "^", "Confidence-selective"),
        "certificate_selective": ("#8e24aa", "D", "Certificate-selective"),
    }
    for policy, (color, marker, label) in styles.items():
        curve = selected.loc[
            selected["policy"] == policy
        ].dropna(subset=["conditional_error"])
        axis.scatter(
            curve["conditional_error"],
            curve["coverage"],
            label=label,
            color=color,
            marker=marker,
            s=42,
        )
    for alpha in (0.01, 0.05, 0.10, 0.20):
        axis.axvline(alpha, color="#d0d0d0", linewidth=0.8, zorder=0)
    axis.set(
        xlabel="Held-out conditional scope error",
        ylabel="Coverage",
        xlim=(-0.01, 0.52),
        ylim=(-0.03, 1.03),
    )
    axis.grid(alpha=0.25)
    axis.legend(frameon=False, fontsize=8)
    return _save(figure, "v05_risk_coverage.png")


def certificate_validity_table(certificate: pd.DataFrame) -> Path:
    selected = certificate.loc[
        (certificate["split"] == "evaluation")
        & (
            (certificate["group_type"] == "overall")
            | (certificate["group_type"] == "nominal_q")
        )
    ].copy()
    selected["group"] = np.where(
        selected["group_type"] == "overall",
        "overall",
        selected["group_value"],
    )
    table = selected.loc[
        :,
        [
            "group",
            "certificate_pair_coverage",
            "certificate_conditional_error",
            "envelope_violation_rate",
            "certificate_efficiency",
        ],
    ].copy()
    table = table.fillna("-")
    for column in table.columns[1:]:
        table[column] = table[column].map(
            lambda value: value if isinstance(value, str) else f"{value:.3f}"
        )
    figure, axis = plt.subplots(figsize=(8.5, 2.5))
    axis.axis("off")
    rendered = axis.table(
        cellText=table.values,
        colLabels=[
            "Group",
            "Certificate coverage",
            "Conditional error",
            "Envelope violations",
            "Efficiency vs oracle",
        ],
        cellLoc="center",
        loc="center",
    )
    rendered.auto_set_font_size(False)
    rendered.set_fontsize(8)
    rendered.scale(1.0, 1.35)
    axis.set_title("Certificate validity from frozen evaluation", pad=10)
    return _save(figure, "v05_certificate_validity_table.png")


def failure_mode_figure(failure: pd.DataFrame) -> Path:
    selected = failure.loc[failure["split"] == "evaluation"].copy()
    grouped = selected.groupby(["signal_h_name", "nominal_q_name"], sort=False).agg(
        certificate_coverage=(
            "certificate_answered_pair_rows",
            lambda values: values.sum() / selected.loc[
                values.index, "total_pair_rows"
            ].sum(),
        ),
        comparative_error_rate=(
            "comparative_forced_error_events",
            lambda values: values.sum()
            / (
                2
                * selected.loc[values.index, "total_pair_rows"].sum()
            ),
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
            "Certificate answered coverage",
            "Pair coverage",
            "viridis",
        ),
        (
            axes[1],
            error,
            "Comparative-forced error",
            "Event error rate",
            "magma_r",
        ),
    ):
        image = axis.imshow(
            values.to_numpy(dtype=float), cmap=cmap, vmin=0.0, vmax=1.0, aspect="auto"
        )
        axis.set(
            title=title,
            xticks=np.arange(len(q_order)),
            xticklabels=q_order,
            yticks=np.arange(len(h_order)),
            yticklabels=h_order,
            xlabel="Nominal donor participation",
            ylabel="Signal",
        )
        for row, h_name in enumerate(h_order):
            for column, q_name in enumerate(q_order):
                value = values.loc[h_name, q_name]
                axis.text(
                    column,
                    row,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if value < 0.45 else "black",
                )
        figure.colorbar(image, ax=axis, label=colorbar_label)
    return _save(figure, "v05_failure_mode_map.png")


def main() -> None:
    protocol = runner.read_protocol()
    paths = _validate_frozen_inputs(protocol)
    results = _read_results(paths)
    outputs = [
        answerability_frontier_figure(results["frontier"]),
        structural_margin_figure(results["pairs"]),
        risk_coverage_figure(results["metrics"]),
        certificate_validity_table(results["certificate"]),
        failure_mode_figure(results["failure"]),
    ]
    manifest = {
        "protocol_id": protocol["protocol_id"],
        "source_receipt_sha256": sha256(paths["v05_execution_receipt.json"]),
        "figures": {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in outputs
        },
    }
    (FIGURE_DIRECTORY / "v05_figure_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
