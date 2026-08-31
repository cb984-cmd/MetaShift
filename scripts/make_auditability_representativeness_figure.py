"""Draw the auditability representativeness figure from saved result artifacts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EVENTS_PATH = Path("artifacts/auditability_representativeness_v2_events.csv")
COVERAGE_PATH = Path("artifacts/auditability_representativeness_v2_coverage.csv")
SMD_PATH = Path("artifacts/auditability_representativeness_v2_standardized_differences.csv")
MODEL_PATH = Path("artifacts/auditability_representativeness_v2_model.csv")
OUTPUT_PATH = Path("figures/figure_14_auditability_representativeness_v2.png")


def main() -> None:
    events = pd.read_csv(EVENTS_PATH)
    coverage = pd.read_csv(COVERAGE_PATH)
    differences = pd.read_csv(SMD_PATH)
    model = pd.read_csv(MODEL_PATH)
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))

    for auditable, label, color in (
        (False, "Unavailable comparison", "#94a3b8"),
        (True, "Complete comparison", "#2563eb"),
    ):
        subset = events.loc[events["auditable"] == auditable]
        axes[0, 0].scatter(
            subset["Longitude"],
            subset["Latitude"],
            s=10,
            alpha=0.7,
            color=color,
            label=label,
        )
    axes[0, 0].set_title("Auditability of metadata anchors")
    axes[0, 0].set_xlabel("Longitude")
    axes[0, 0].set_ylabel("Latitude")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(alpha=0.2)

    regional = coverage.loc[coverage["dimension"] == "epa_region"].sort_values(
        "group"
    )
    bars = axes[0, 1].bar(
        regional["group"].str.replace("EPA Region ", "R"),
        regional["auditable_fraction"],
        color="#2563eb",
    )
    axes[0, 1].bar_label(
        bars,
        labels=[
            f"{int(row.auditable_count)}/{int(row.anchor_count)}"
            for row in regional.itertuples()
        ],
        padding=2,
        fontsize=8,
    )
    axes[0, 1].set_ylim(0, 1)
    axes[0, 1].set_title("Complete-comparison coverage by EPA region")
    axes[0, 1].set_xlabel("EPA region")
    axes[0, 1].set_ylabel("Auditable fraction")
    axes[0, 1].grid(axis="y", alpha=0.25)

    differences = differences.sort_values(
        "standardized_mean_difference_complete_minus_unavailable"
    )
    axes[1, 0].barh(
        differences["feature"],
        differences["standardized_mean_difference_complete_minus_unavailable"],
        color="#7c3aed",
    )
    axes[1, 0].axvline(0, color="#111827", linewidth=0.8)
    axes[1, 0].set_title("Complete minus unavailable anchors")
    axes[1, 0].set_xlabel("Pooled standardized mean difference")
    axes[1, 0].tick_params(axis="y", labelsize=7)
    axes[1, 0].grid(axis="x", alpha=0.25)

    model = model.sort_values("standardized_log_odds_coefficient")
    coefficients = model["standardized_log_odds_coefficient"].to_numpy()
    axes[1, 1].barh(model["feature"], coefficients, color="#f59e0b")
    axes[1, 1].axvline(0, color="#111827", linewidth=0.8)
    axes[1, 1].set_title("Descriptive auditability associations")
    axes[1, 1].set_xlabel("Standardized ridge-logistic coefficient")
    axes[1, 1].tick_params(axis="y", labelsize=7)
    axes[1, 1].grid(axis="x", alpha=0.25)

    figure.suptitle(
        "Where a common cross-site counterfactual comparison is available",
        fontsize=13,
    )
    figure.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight")
    plt.close(figure)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
