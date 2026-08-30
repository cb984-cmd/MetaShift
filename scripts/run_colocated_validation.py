"""Audit same-site alternate-POC evidence for metadata-anchor events.

This script treats a stable alternate POC as a spatially controlled reference,
not as a physical-instrument ground truth. EPA explicitly documents that POC is
not a universal instrument identifier.
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd


SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
USE_COLUMNS = SERIES_KEYS + [
    "Sample Duration",
    "Date Local",
    "Arithmetic Mean",
    "Observation Percent",
    "Method Code",
    "Method Name",
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
    "Method Code": "string",
    "Method Name": "string",
    "Event Type": "category",
}
OUTPUT_PATH = Path("artifacts/colocated_validation.csv")


def load_canonical_data() -> pd.DataFrame:
    frames = []
    for path in sorted(glob.glob("data/raw/daily_88101_*.zip")):
        frame = pd.read_csv(
            path,
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
        frames.append(frame.loc[valid].copy())
    data = pd.concat(frames, ignore_index=True)
    if data.duplicated(SERIES_KEYS + ["Date Local"]).any():
        raise ValueError("Canonical input contains duplicate monitor-days.")
    return data


def robust_effect(differences: pd.Series, date: pd.Timestamp) -> tuple[float, float, int, int]:
    pre = differences.loc[date - pd.Timedelta(days=60) : date - pd.Timedelta(days=1)]
    post = differences.loc[date : date + pd.Timedelta(days=59)]
    pre = pre.dropna()
    post = post.dropna()
    if len(pre) < 30 or len(post) < 30:
        raise ValueError("Fewer than 30 paired days in a 60-day comparison window.")
    effect = float(np.median(post) - np.median(pre))
    scale = max(1.4826 * float(np.median(np.abs(pre - np.median(pre)))), 1e-8)
    return effect, effect / scale, len(pre), len(post)


def method_at(
    data: pd.DataFrame, key: tuple[str, str, str, str], date: pd.Timestamp
) -> tuple[str, str]:
    state, county, site, poc = key
    records = data.loc[
        (data["State Code"] == state)
        & (data["County Code"] == county)
        & (data["Site Num"] == site)
        & (data["POC"] == poc)
        & (data["Date Local"] >= date - pd.Timedelta(days=60))
        & (data["Date Local"] <= date + pd.Timedelta(days=60))
    ]
    if records.empty:
        return "", ""
    return str(records["Method Code"].iloc[0]), str(records["Method Name"].iloc[0])


def main() -> None:
    anchors = pd.read_csv("artifacts/data_gate/anchor_inventory.csv", dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    controls = pd.read_csv("artifacts/data_gate/colocated_controls.csv", dtype="string")
    data = load_canonical_data()

    rows: list[dict[str, object]] = []
    for control in controls.itertuples(index=False):
        event = anchors.loc[anchors["anchor_id"] == control.anchor_id].iloc[0]
        date = pd.Timestamp(event["start_date"])
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        control_key = (
            str(control.control_state_code),
            str(control.control_county_code),
            str(control.control_site_num),
            str(control.control_poc),
        )
        target = data.loc[
            (data["State Code"] == target_key[0])
            & (data["County Code"] == target_key[1])
            & (data["Site Num"] == target_key[2])
            & (data["POC"] == target_key[3]),
            ["Date Local", "Arithmetic Mean"],
        ].set_index("Date Local")["Arithmetic Mean"]
        reference = data.loc[
            (data["State Code"] == control_key[0])
            & (data["County Code"] == control_key[1])
            & (data["Site Num"] == control_key[2])
            & (data["POC"] == control_key[3]),
            ["Date Local", "Arithmetic Mean"],
        ].set_index("Date Local")["Arithmetic Mean"]
        effect, score, pre_days, post_days = robust_effect(target - reference, date)
        reference_code, reference_name = method_at(data, control_key, date)
        rows.append(
            {
                "anchor_id": control.anchor_id,
                "anchor_date": date.date().isoformat(),
                "target_poc": target_key[3],
                "reference_poc": control_key[3],
                "target_old_method_code": event["previous_method_code"],
                "target_new_method_code": event["method_code"],
                "reference_method_code": reference_code,
                "reference_method_name": reference_name,
                "paired_pre_days": pre_days,
                "paired_post_days": post_days,
                "target_minus_reference_effect_ug_m3": effect,
                "robust_standardized_effect": score,
                "pre_transition_log_correlation": float(
                    control.pre_transition_log_correlation
                ),
            }
        )

    result = pd.DataFrame(rows).sort_values("anchor_date")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False)
    print(result.to_string(index=False))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
