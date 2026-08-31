"""Draw same-site overlap consistency plots from saved artifacts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DETAIL_PATH = Path("artifacts/same_site_overlap_consistency_v1_details.csv")
SUMMARY_PATH = Path("artifacts/same_site_overlap_consistency_v1_summary.csv")
OUTPUT_PATH = Path("figures/figure_15_same_site_overlap_consistency.png")


def scatter_with_identity(
    axis: plt.Axes, data: pd.DataFrame, x_column: str, y_column: str, title: str
) -> None:
    """Plot finite paired effects with a zero-centered identity reference."""

    paired = data.loc[
        data[x_column].notna() & data[y_column].notna(), [x_column, y_column]
    ]
    axis.scatter(paired[x_column], paired[y_column], color="#2563eb", alpha=0.8)
    if len(paired):
        bound = float(np.abs(paired.to_numpy(dtype=float)).max()) * 1.1
        axis.plot([-bound, bound], [-bound, bound], color="#64748b", linestyle="--")
        axis.set_xlim(-bound, bound)
        axis.set_ylim(-bound, bound)
    axis.axhline(0, color="#111827", linewidth=0.7)
    axis.axvline(0, color="#111827", linewidth=0.7)
    axis.set_title(title)
    axis.set_xlabel("Daily same-site difference change (ug/m3)")
    axis.set_ylabel("Comparison effect (ug/m3)")
    axis.grid(alpha=0.25)


def main() -> None:
    details = pd.read_csv(DETAIL_PATH)
    summary = pd.read_csv(SUMMARY_PATH)
    figure, axes = plt.subplots(1, 3, figsize=(13, 4))
    daily_hourly = details.drop_duplicates("anchor_id")
    scatter_with_identity(
        axes[0],
        daily_hourly,
        "target_minus_reference_effect_ug_m3",
        "hourly_difference_change_ug_m3",
        "Same-site daily vs hourly",
    )
    standard = details.loc[details["method"] == "standard_synthetic_control"]
    scatter_with_identity(
        axes[1],
        standard,
        "target_minus_reference_effect_ug_m3",
        "cross_site_raw_effect_ug_m3",
        "Same-site daily vs Standard SC",
    )
    cross_summary = summary.loc[
        summary["comparison"] == "same_site_daily_vs_cross_site_raw_residual"
    ]
    bars = axes[2].bar(
        cross_summary["method"],
        cross_summary["direction_agreement_fraction"],
        color="#7c3aed",
    )
    axes[2].bar_label(
        bars,
        labels=[
            f"{int(row.direction_agreement_count)}/{int(row.nonzero_direction_pairs)}"
            for row in cross_summary.itertuples()
        ],
        padding=2,
        fontsize=8,
    )
    axes[2].set_ylim(0, 1)
    axes[2].set_title("Same-site vs cross-site direction agreement")
    axes[2].set_ylabel("Agreement fraction")
    axes[2].tick_params(axis="x", rotation=25, labelsize=8)
    axes[2].grid(axis="y", alpha=0.25)
    figure.suptitle(
        "Alternate-POC overlap: consistency context, not physical ground truth",
        fontsize=12,
    )
    figure.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight")
    plt.close(figure)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
