"""Generate reproducible diagnostic figures for preselected real-anchor cases."""

from __future__ import annotations

import json
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

from metashift.counterfactual import weighted_donor_series  # noqa: E402
from run_feasibility_prototype import event_donors, load_series  # noqa: E402
from run_real_transition_audit import fixed_weights, load_inputs  # noqa: E402


ARTIFACTS = Path("artifacts")
GATE_DIR = ARTIFACTS / "data_gate"
SELECTION_PATH = ARTIFACTS / "real_transition_88101_case_study_selection.csv"
TIME_PLACEBO_PATH = ARTIFACTS / "time_placebo_scores.csv"
LOO_PATH = ARTIFACTS / "leave_one_donor_out_details.csv"
OUTPUT_DIR = Path("figures") / "case_studies"
MANIFEST_PATH = OUTPUT_DIR / "case_study_manifest.json"
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(":", "_")


def plot_complete_case(
    figure: plt.Figure,
    axes: np.ndarray,
    event: pd.Series,
    target: pd.Series,
    donors: pd.DataFrame,
    weights: pd.Series,
    date: pd.Timestamp,
) -> None:
    """Plot raw counterfactual, calibrated residual, time placebos, and LOO."""

    visible_start = date - pd.Timedelta(days=120)
    visible_end = date + pd.Timedelta(days=120)
    raw_donor, _ = weighted_donor_series(donors, weights, logarithmic=False)
    calibration = pd.concat(
        [target.rename("target"), raw_donor.rename("donor")], axis="columns", sort=False
    ).loc[date - pd.Timedelta(days=180) : date - pd.Timedelta(days=15)].dropna()
    offset = float(np.median(calibration["target"] - calibration["donor"]))
    counterfactual = raw_donor + offset

    axes[0, 0].plot(target.loc[visible_start:visible_end], label="Target", color="#111827")
    axes[0, 0].plot(
        counterfactual.loc[visible_start:visible_end],
        label="Counterfactual",
        color="#2563eb",
    )
    axes[0, 0].axvline(date, color="#dc2626", linestyle="--", label="Method Code anchor")
    axes[0, 0].set_title("Target and cross-site counterfactual")
    axes[0, 0].set_ylabel("PM2.5 (ug/m3)")
    axes[0, 0].legend(fontsize=8)

    target_log = np.log1p(target.clip(lower=0.0))
    donor_log, _ = weighted_donor_series(donors, weights, logarithmic=True)
    log_calibration = pd.concat(
        [target_log.rename("target"), donor_log.rename("donor")],
        axis="columns",
        sort=False,
    ).loc[date - pd.Timedelta(days=180) : date - pd.Timedelta(days=15)].dropna()
    residual = target_log - donor_log - np.median(
        log_calibration["target"] - log_calibration["donor"]
    )
    axes[0, 1].plot(residual.loc[visible_start:visible_end], color="#7c3aed")
    axes[0, 1].axhline(0, color="#111827", linewidth=0.8)
    axes[0, 1].axvline(date, color="#dc2626", linestyle="--")
    axes[0, 1].set_title("Calibrated log residual")
    axes[0, 1].set_ylabel("log residual")

    placebo = pd.read_csv(TIME_PLACEBO_PATH)
    anchor_id = str(event["anchor_id"])
    actual = placebo.loc[
        (placebo["anchor_id"] == anchor_id)
        & (placebo["date_type"] == "actual_method_code_anchor"),
        "standardized_score",
    ]
    placebo_values = placebo.loc[
        (placebo["anchor_id"] == anchor_id)
        & (placebo["date_type"] == "post_transition_time_placebo"),
        "standardized_score",
    ]
    axes[1, 0].hist(placebo_values, bins=20, color="#94a3b8", alpha=0.85)
    if len(actual):
        axes[1, 0].axvline(
            actual.iloc[0],
            color="#dc2626",
            linestyle="--",
            label="Actual anchor score",
        )
    if placebo_values.empty:
        axes[1, 0].text(
            0.5,
            0.5,
            "No >=50-date\nstable placebo set",
            ha="center",
            va="center",
            transform=axes[1, 0].transAxes,
        )
    axes[1, 0].set_title("Stable post-transition time placebos")
    axes[1, 0].set_xlabel("Absolute standardized score")
    if len(actual):
        axes[1, 0].legend(fontsize=8)

    loo = pd.read_csv(LOO_PATH)
    loo = loo.loc[
        (loo["anchor_id"] == anchor_id) & (loo["run_status"] == "complete")
    ].sort_values("leave_one_out_log_effect")
    axes[1, 1].scatter(
        loo["leave_one_out_log_effect"],
        np.arange(len(loo)),
        color="#2563eb",
        label="Leave-one-donor-out",
    )
    if len(loo):
        axes[1, 1].axvline(
            loo["full_log_effect"].iloc[0],
            color="#dc2626",
            linestyle="--",
            label="Full donor set",
        )
    axes[1, 1].axvline(0, color="#111827", linewidth=0.8)
    axes[1, 1].set_title("Donor-removal sensitivity")
    axes[1, 1].set_xlabel("Estimated log effect")
    axes[1, 1].set_yticks([])
    axes[1, 1].legend(fontsize=8)


def plot_inconclusive_case(
    figure: plt.Figure, axes: np.ndarray, event: pd.Series, target: pd.Series, date: pd.Timestamp
) -> None:
    """Show why an event without a comparable counterfactual remains inconclusive."""

    visible_start = date - pd.Timedelta(days=120)
    visible_end = date + pd.Timedelta(days=120)
    axes[0, 0].plot(target.loc[visible_start:visible_end], color="#111827")
    axes[0, 0].axvline(date, color="#dc2626", linestyle="--")
    axes[0, 0].set_title("Target series only")
    axes[0, 0].set_ylabel("PM2.5 (ug/m3)")
    reason = str(event.get("evidence_reasons", "No common comparative estimate"))
    for axis in (axes[0, 1], axes[1, 0], axes[1, 1]):
        axis.axis("off")
        axis.text(
            0.05,
            0.55,
            "Inconclusive case\n\n"
            f"Evidence reason:\n{reason}\n\n"
            "No cross-site causal or measurement-bias conclusion is made.",
            va="center",
            ha="left",
            wrap=True,
            fontsize=10,
        )


def main() -> None:
    selection = pd.read_csv(SELECTION_PATH, dtype="string")
    anchors, controls = load_inputs(GATE_DIR)
    anchor_by_id = anchors.set_index("anchor_id")
    series = load_series("88101")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for _, selected in selection.iterrows():
        anchor_id = str(selected["anchor_id"])
        event = anchor_by_id.loc[anchor_id]
        date = pd.Timestamp(event["start_date"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = series[target_key]
        figure, axes = plt.subplots(2, 2, figsize=(12, 7))
        if event["geographic_control_count"] >= 3:
            try:
                donors, _ = event_donors(anchor_id, controls, series)
                metadata = controls.loc[controls["anchor_id"] == anchor_id].sort_values(
                    "rank"
                ).head(5)
                _, _, weights = fixed_weights(target, donors, metadata, date)
                plot_complete_case(figure, axes, selected, target, donors, weights, date)
            except (KeyError, RuntimeError, ValueError):
                plot_inconclusive_case(figure, axes, selected, target, date)
        else:
            plot_inconclusive_case(figure, axes, selected, target, date)
        figure.suptitle(
            f"{selected['case_group']} case {selected['selection_rank']}: {anchor_id}\n"
            f"Reported Method Code {event['previous_method_code']} -> {event['method_code']} "
            f"on {date.date()}",
            fontsize=11,
        )
        filename = (
            f"{selected['case_group']}_{int(selected['selection_rank'])}_"
            f"{safe_name(anchor_id)}.png"
        )
        output_path = OUTPUT_DIR / filename
        figure.tight_layout(rect=(0, 0, 1, 0.92))
        figure.savefig(output_path, dpi=200, bbox_inches="tight")
        plt.close(figure)
        manifest.append(
            {
                "anchor_id": anchor_id,
                "case_group": selected["case_group"],
                "selection_rank": int(selected["selection_rank"]),
                "file": str(output_path).replace("\\", "/"),
                "selection_rule": selected["selection_rule"],
            }
        )
        print(f"Generated {output_path}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
