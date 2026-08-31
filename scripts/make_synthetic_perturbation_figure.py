"""Illustrate the predeclared synthetic perturbation families on one fixed case."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.synthetic import PerturbationKind, inject_perturbation  # noqa: E402
from run_stable_synthetic_benchmark import (  # noqa: E402
    donor_inputs,
    load_cases,
    load_series,
    robust_pre_scale,
)


OUTPUT_PATH = Path("figures/figure_3_synthetic_perturbations.png")
SELECTION_PATH = Path("artifacts/synthetic_perturbation_illustration_case.json")


def main() -> None:
    cases, donor_records = load_cases("calibration", 1)
    case = cases.iloc[0]
    series = load_series("88101")
    target_key = tuple(
        str(case[column]) for column in ["State Code", "County Code", "Site Num", "POC"]
    )
    target = series[target_key]
    donors, _ = donor_inputs(str(case["case_id"]), donor_records, series)
    date = pd.Timestamp(case["pseudo_anchor_date"])
    scale = robust_pre_scale(target, date)
    variants = [
        (PerturbationKind.ADDITIVE_STEP, scale * 2, "Local additive step"),
        (PerturbationKind.PROPORTIONAL_STEP, 0.15, "Local proportional step"),
        (PerturbationKind.GRADUAL_DRIFT, scale * 2, "Local gradual drift"),
        (PerturbationKind.TEMPORARY_STEP, scale * 2, "Local temporary step"),
        (PerturbationKind.VARIANCE_INCREASE, 0.5, "Local variance increase"),
        (
            PerturbationKind.REGIONAL_ADDITIVE_STEP,
            scale * 2,
            "Matched regional additive step",
        ),
    ]
    visible = slice(date - pd.Timedelta(days=30), date + pd.Timedelta(days=89))
    donor_baseline = donors.mean(axis=1)
    figure, axes = plt.subplots(2, 3, figsize=(12, 6), sharex=True, sharey=True)
    for index, (kind, magnitude, title) in enumerate(variants):
        changed_target, changed_donors, _ = inject_perturbation(
            target, donors, date, kind, magnitude, random_seed=20_260_830 + index
        )
        axis = axes.flat[index]
        axis.plot(target.loc[visible], color="#111827", linewidth=1, label="Original target")
        axis.plot(
            changed_target.loc[visible],
            color="#dc2626",
            linewidth=1,
            label="Perturbed target",
        )
        if kind.value.startswith("regional_"):
            axis.plot(
                changed_donors.mean(axis=1).loc[visible],
                color="#2563eb",
                linewidth=1,
                label="Perturbed donor mean",
            )
        else:
            axis.plot(
                donor_baseline.loc[visible],
                color="#2563eb",
                linewidth=1,
                label="Donor mean",
            )
        axis.axvline(date, color="#6b7280", linestyle="--", linewidth=1)
        axis.set_title(title, fontsize=10)
        axis.grid(alpha=0.2)
    axes[0, 0].set_ylabel("PM2.5 (ug/m3)")
    axes[1, 0].set_ylabel("PM2.5 (ug/m3)")
    for axis in axes[1, :]:
        axis.set_xlabel("Date")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, fontsize=8)
    figure.suptitle(
        f"Stable-window synthetic perturbations: {case['case_id']}",
        y=0.995,
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.92))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight")
    plt.close(figure)
    SELECTION_PATH.write_text(
        (
            "{\n"
            f'  "case_id": "{case["case_id"]}",\n'
            f'  "pseudo_anchor_date": "{date.date()}",\n'
            '  "selection_rule": "First deterministic calibration case; illustrative only, not selected by performance."\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH} and {SELECTION_PATH}")


if __name__ == "__main__":
    main()
