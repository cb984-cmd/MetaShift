"""Run predeclared observational effect-window and scale sensitivity checks."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.counterfactual import estimate_metadata_anchor  # noqa: E402
from run_feasibility_prototype import event_donors  # noqa: E402
from run_real_transition_audit import fixed_weights, load_inputs  # noqa: E402
from scan_data_gate import (  # noqa: E402
    DEFAULT_CONFIG,
    ensure_archives,
    load_canonical_signal,
    prepare_series_lookup,
)


CONFIG_PATH = Path("configs/effect_window_sensitivity_v1.json")
GATE_DIR = Path("artifacts/data_gate")
AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
DETAIL_PATH = Path("artifacts/effect_window_sensitivity_details.csv")
SUMMARY_PATH = Path("artifacts/effect_window_sensitivity_summary.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]


def signed(value: float, tolerance: float = 1e-8) -> int:
    return 0 if abs(value) <= tolerance else int(np.sign(value))


def stable_segment_reason(
    records: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    minimum_observations: int,
    expected_method_code: str | None = None,
) -> str | None:
    """Check one declared method regime without treating missing days as stability."""

    segment = records.loc[start:end]
    if len(segment) < minimum_observations:
        return (
            f"only {len(segment)} observations from {start.date()} through "
            f"{end.date()}; requires {minimum_observations}"
        )
    methods = segment["Method Code"].astype("string")
    if methods.nunique() != 1:
        return f"Method Code changes within {start.date()} through {end.date()}"
    if expected_method_code is not None and str(methods.iloc[0]) != expected_method_code:
        return (
            f"Method Code {methods.iloc[0]!r} does not match expected "
            f"{expected_method_code!r}"
        )
    return None


def method_window_reason(
    event: pd.Series,
    metadata: pd.DataFrame,
    records_by_monitor: dict[tuple[str, str, str, str], pd.DataFrame],
    date: pd.Timestamp,
    window: int,
    minimum_observations: int,
) -> str | None:
    """Require intended target regimes and every fixed donor to be stable."""

    pre_start = date - pd.Timedelta(days=window)
    pre_end = date - pd.Timedelta(days=1)
    post_start = date
    post_end = date + pd.Timedelta(days=window - 1)
    target_key = tuple(str(event[column]) for column in SERIES_KEYS)
    target = records_by_monitor.get(target_key)
    if target is None:
        return "target Method Code records are unavailable"
    target_pre_reason = stable_segment_reason(
        target,
        pre_start,
        pre_end,
        minimum_observations,
        str(event["previous_method_code"]),
    )
    if target_pre_reason is not None:
        return f"target pre-transition regime invalid: {target_pre_reason}"
    target_post_reason = stable_segment_reason(
        target,
        post_start,
        post_end,
        minimum_observations,
        str(event["method_code"]),
    )
    if target_post_reason is not None:
        return f"target post-transition regime invalid: {target_post_reason}"

    for donor in metadata.itertuples(index=False):
        donor_key = (
            str(donor.control_state_code).zfill(2),
            str(donor.control_county_code).zfill(3),
            str(donor.control_site_num).zfill(4),
            str(donor.control_poc),
        )
        donor_records = records_by_monitor.get(donor_key)
        if donor_records is None:
            return f"donor {donor_key} Method Code records are unavailable"
        donor_pre_reason = stable_segment_reason(
            donor_records, pre_start, pre_end, minimum_observations
        )
        donor_post_reason = stable_segment_reason(
            donor_records, post_start, post_end, minimum_observations
        )
        if donor_pre_reason is not None or donor_post_reason is not None:
            reason = donor_pre_reason or donor_post_reason
            return f"donor {donor_key} regime invalid: {reason}"
        donor_window = donor_records.loc[pre_start:post_end, "Method Code"]
        if donor_window.astype("string").nunique() != 1:
            return f"donor {donor_key} has a Method Code transition in the full window"
    return None


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    windows = [int(value) for value in config["comparison_window_days"]]
    methods = [str(value) for value in config["methods"]]
    anchors, controls = load_inputs(GATE_DIR)
    audit = pd.read_csv(AUDIT_PATH, dtype="string")
    completed_ids = set(audit.loc[audit["audit_status"] == "complete", "anchor_id"])
    events = anchors.loc[anchors["anchor_id"].isin(completed_ids)]
    raw_paths = ensure_archives(
        Path("data/raw"), DEFAULT_CONFIG.years, download=False
    )
    canonical = load_canonical_signal(raw_paths)
    records_by_monitor, _, _ = prepare_series_lookup(canonical)
    series = {
        key: records["Arithmetic Mean"] for key, records in records_by_monitor.items()
    }
    rows: list[dict[str, object]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        event_id = str(event["anchor_id"])
        date = pd.Timestamp(event["start_date"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = series[target_key]
        donors, _ = event_donors(event_id, controls, series)
        metadata = controls.loc[controls["anchor_id"] == event_id].sort_values(
            "rank"
        ).head(5)
        nearest, standard, metashift = fixed_weights(target, donors, metadata, date)
        weights_by_method = {
            "nearest_neighbor_did": nearest,
            "standard_synthetic_control": standard,
            "metashift_v1_fixed": metashift,
        }
        for window in windows:
            minimum_observations = math.ceil(
                window * float(config["minimum_observation_fraction_per_window"])
            )
            stability_reason = method_window_reason(
                event,
                metadata,
                records_by_monitor,
                date,
                window,
                minimum_observations,
            )
            for method in methods:
                if stability_reason is not None:
                    rows.append(
                        {
                            "anchor_id": event_id,
                            "method": method,
                            "comparison_window_days": window,
                            "minimum_window_observations": minimum_observations,
                            "log_effect": np.nan,
                            "raw_effect_ug_m3": np.nan,
                            "standardized_score": np.nan,
                            "status": "unavailable_method_window_contaminated",
                            "reason": stability_reason,
                        }
                    )
                    continue
                try:
                    estimate = estimate_metadata_anchor(
                        target,
                        donors,
                        weights_by_method[method],
                        date,
                        comparison_days=window,
                        min_window_observations=minimum_observations,
                    )
                    rows.append(
                        {
                            "anchor_id": event_id,
                            "method": method,
                            "comparison_window_days": window,
                            "minimum_window_observations": minimum_observations,
                            "log_effect": estimate.log_effect,
                            "raw_effect_ug_m3": estimate.raw_effect,
                            "standardized_score": estimate.standardized_score,
                            "status": "complete",
                            "reason": None,
                        }
                    )
                except (RuntimeError, ValueError) as error:
                    rows.append(
                        {
                            "anchor_id": event_id,
                            "method": method,
                            "comparison_window_days": window,
                            "minimum_window_observations": minimum_observations,
                            "log_effect": np.nan,
                            "raw_effect_ug_m3": np.nan,
                            "standardized_score": np.nan,
                            "status": "unavailable",
                            "reason": str(error),
                        }
                    )
        if position % 50 == 0 or position == len(events):
            print(f"Computed effect-window sensitivity {position}/{len(events)} events")

    output = pd.DataFrame(rows)
    output.to_csv(DETAIL_PATH, index=False)
    baseline = output.loc[
        (output["comparison_window_days"] == 60) & (output["status"] == "complete"),
        ["anchor_id", "method", "log_effect"],
    ].rename(columns={"log_effect": "baseline_log_effect"})
    merged = output.merge(baseline, on=["anchor_id", "method"], how="left")
    merged["same_sign_as_60_day"] = [
        signed(candidate) == signed(reference)
        if np.isfinite(candidate) and np.isfinite(reference)
        else np.nan
        for candidate, reference in zip(
            merged["log_effect"], merged["baseline_log_effect"], strict=True
        )
    ]
    summary = (
        merged.groupby(["method", "comparison_window_days", "status"], dropna=False)
        .agg(
            event_count=("anchor_id", "size"),
            median_log_effect=("log_effect", "median"),
            median_raw_effect_ug_m3=("raw_effect_ug_m3", "median"),
            median_abs_standardized_score=("standardized_score", lambda values: values.abs().median()),
            sign_agreement_with_60_day=("same_sign_as_60_day", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(SUMMARY_PATH, index=False)
    print(summary.to_string(index=False))
    print(f"Wrote {DETAIL_PATH} and {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
