"""Run the preregistered minimal MetaShift feasibility prototype on five events."""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.counterfactual import (
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)


RAW_GLOB = "data/raw/daily_88101_*.zip"
GATE_DIR = Path("artifacts/data_gate")
OUTPUT_PATH = Path("artifacts/feasibility_prototype.csv")
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
USE_COLUMNS = SERIES_KEYS + [
    "Sample Duration",
    "Date Local",
    "Arithmetic Mean",
    "Observation Percent",
    "Event Type",
]
DTYPES = {
    "State Code": "string",
    "County Code": "string",
    "Site Num": "string",
    "POC": "string",
    "Sample Duration": "category",
    "Arithmetic Mean": "float64",
    "Observation Percent": "float64",
    "Event Type": "category",
}


def load_series(
    parameter_code: str = "88101", raw_dir: Path = Path("data") / "raw"
) -> dict[tuple[str, str, str, str], pd.Series]:
    frames = []
    pattern = str(raw_dir / f"daily_{parameter_code}_*.zip")
    for raw_path in sorted(glob.glob(pattern)):
        frame = pd.read_csv(
            raw_path,
            usecols=USE_COLUMNS,
            dtype=DTYPES,
            parse_dates=["Date Local"],
            compression="zip",
            low_memory=False,
        )
        included = frame["Event Type"].astype("string").fillna("") != "Excluded"
        valid = (
            (frame["Sample Duration"] == "24-HR BLK AVG")
            & included
            & frame["Arithmetic Mean"].notna()
            & np.isfinite(frame["Arithmetic Mean"])
            & (frame["Observation Percent"] >= 75)
        )
        frames.append(frame.loc[valid, SERIES_KEYS + ["Date Local", "Arithmetic Mean"]])

    if not frames:
        raise FileNotFoundError(f"No AQS daily archives matched {pattern}.")
    data = pd.concat(frames, ignore_index=True)
    if data.duplicated(SERIES_KEYS + ["Date Local"]).any():
        raise ValueError("Canonical data has duplicate monitor-days.")
    return {
        tuple(str(value) for value in key): group.set_index("Date Local")[
            "Arithmetic Mean"
        ].sort_index()
        for key, group in data.groupby(SERIES_KEYS, observed=True, sort=False)
    }


def synthetic_control_weights(
    target: pd.Series, donors: pd.DataFrame, anchor_date: pd.Timestamp
) -> pd.Series:
    """Fit nonnegative sum-to-one weights exclusively before the anchor."""

    calibration = pd.concat(
        [target.rename("target"), donors], axis=1, sort=False
    ).sort_index()
    calibration = calibration.loc[
        anchor_date - pd.Timedelta(days=180) : anchor_date - pd.Timedelta(days=15)
    ].dropna()
    if len(calibration) < 60:
        raise ValueError("Standard synthetic control lacks 60 pre-anchor observations.")
    target_values = np.log1p(calibration.pop("target").clip(lower=0).to_numpy())
    donor_values = np.log1p(calibration.clip(lower=0).to_numpy())
    donor_count = donor_values.shape[1]

    def objective(weights: np.ndarray) -> float:
        return float(np.mean(np.square(target_values - donor_values @ weights)))

    result = minimize(
        objective,
        x0=np.full(donor_count, 1 / donor_count),
        method="SLSQP",
        bounds=[(0.0, 1.0)] * donor_count,
        constraints={"type": "eq", "fun": lambda weights: weights.sum() - 1},
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not result.success:
        raise RuntimeError(f"Synthetic-control optimization failed: {result.message}")
    return pd.Series(result.x, index=donors.columns)


def event_donors(
    event_id: str,
    controls: pd.DataFrame,
    series: dict[tuple[str, str, str, str], pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = controls.loc[controls["anchor_id"] == event_id].sort_values("rank").head(5)
    if len(selected) < 3:
        raise ValueError("Event has fewer than three prequalified geographic donors.")
    columns: dict[str, pd.Series] = {}
    for row in selected.itertuples(index=False):
        key = (
            str(row.control_state_code).zfill(2),
            str(row.control_county_code).zfill(3),
            str(row.control_site_num).zfill(4),
            str(row.control_poc),
        )
        if key not in series:
            raise KeyError(f"Control series absent from canonical data: {key}")
        columns["-".join(key)] = series[key]
    return pd.DataFrame(columns), selected.set_index(
        ["control_state_code", "control_county_code", "control_site_num", "control_poc"]
    )


def run_event(
    event: pd.Series,
    controls: pd.DataFrame,
    series: dict[tuple[str, str, str, str], pd.Series],
) -> dict[str, object]:
    event_id = str(event["anchor_id"])
    target_key = tuple(str(event[column]) for column in SERIES_KEYS)
    target = series[target_key]
    donors, _ = event_donors(event_id, controls, series)
    date = pd.Timestamp(event["start_date"])

    metadata = controls.loc[controls["anchor_id"] == event_id].sort_values("rank").head(5)
    metadata = metadata.copy()
    metadata.index = donors.columns
    reliability = donor_weights(metadata)
    calibration_start = date - pd.Timedelta(days=180)
    calibration_end = date - pd.Timedelta(days=15)
    metashift_weights = reliability_constrained_weights(
        target.loc[calibration_start:calibration_end],
        donors.loc[calibration_start:calibration_end],
        reliability,
    )
    standard = synthetic_control_weights(target, donors, date)
    nearest = pd.Series(0.0, index=donors.columns)
    nearest.iloc[0] = 1.0

    estimates = {
        "nearest_neighbor": estimate_metadata_anchor(target, donors, nearest, date),
        "standard_synthetic_control": estimate_metadata_anchor(target, donors, standard, date),
        "metashift": estimate_metadata_anchor(target, donors, metashift_weights, date),
    }
    injected_target = target.copy()
    injected_target.loc[date:] *= 1.25
    injected = estimate_metadata_anchor(injected_target, donors, metashift_weights, date)
    original = estimates["metashift"]
    expected_injected_log_increment = float(
        np.median(
            np.log1p(injected_target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0))
            - np.log1p(target.loc[date : date + pd.Timedelta(days=59)].clip(lower=0))
        )
    )
    recovered_log_increment = injected.log_effect - original.log_effect

    result: dict[str, object] = {
        "anchor_id": event_id,
        "anchor_date": date.date().isoformat(),
        "old_method": event["previous_method_code"],
        "new_method": event["method_code"],
        "geographic_donors": len(donors.columns),
        "is_tier_c_candidate": int(event["colocated_control_count"]) >= 1,
        "synthetic_expected_log_increment": expected_injected_log_increment,
        "synthetic_recovered_log_increment": recovered_log_increment,
        "synthetic_log_increment_absolute_error": abs(
            recovered_log_increment - expected_injected_log_increment
        ),
    }
    for method, estimate in estimates.items():
        result[f"{method}_relative_effect"] = estimate.relative_effect
        result[f"{method}_raw_effect_ug_m3"] = estimate.raw_effect
        result[f"{method}_score"] = estimate.standardized_score
        result[f"{method}_pre_rmse"] = estimate.calibration_residual_rmse
    return result


def main() -> None:
    anchors = pd.read_csv(GATE_DIR / "anchor_inventory.csv", dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    controls = pd.read_csv(GATE_DIR / "geographic_controls.csv", dtype="string")
    for column in ["distance_km", "pre_transition_paired_days", "pre_transition_log_correlation", "rank"]:
        controls[column] = pd.to_numeric(controls[column])

    eligible = anchors.loc[
        (pd.to_numeric(anchors["geographic_control_count"]) >= 3)
        & (pd.to_numeric(anchors["colocated_control_count"]) >= 1)
    ].copy()
    selected = eligible.sort_values(
        ["geographic_control_count", "start_date", "anchor_id"],
        ascending=[False, True, True],
    ).head(5)
    if len(selected) < 5:
        raise ValueError("Fewer than five Tier C candidates were available for the gate.")

    series = load_series()
    results = [run_event(event, controls, series) for _, event in selected.iterrows()]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(OUTPUT_PATH, index=False)
    print(pd.DataFrame(results).to_string(index=False))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
