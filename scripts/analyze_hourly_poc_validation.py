"""Analyze same-site target/reference POC differences using matched hourly data."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
CONTROLS_PATH = Path("artifacts/data_gate/colocated_controls.csv")
DAILY_PATH = Path("artifacts/colocated_validation.csv")
DOWNLOAD_MANIFEST_PATH = Path("artifacts/hourly_poc_download_manifest.json")
RAW_DIR = Path("data/raw/aqs_hourly_poc")
OUTPUT_PATH = Path("artifacts/hourly_poc_validation_summary.csv")
DETAIL_PATH = Path("artifacts/hourly_poc_validation_details.csv")


def canonical_hourly_records(payload: dict[str, object]) -> pd.DataFrame:
    """Return deduplicated 1-hour records, rejecting conflicting monitor-hours."""

    data = pd.DataFrame(payload.get("Data", []))
    required = {
        "poc",
        "date_local",
        "time_local",
        "sample_measurement",
        "sample_duration",
        "method_code",
        "qualifier",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Hourly API response lacks fields: {sorted(missing)}")
    data = data.loc[
        (data["sample_duration"] == "1 HOUR")
        & pd.to_numeric(data["sample_measurement"], errors="coerce").notna()
    ].copy()
    data["poc"] = data["poc"].astype("string")
    data["measurement"] = pd.to_numeric(data["sample_measurement"])
    data["timestamp"] = pd.to_datetime(
        data["date_local"].astype(str) + " " + data["time_local"].astype(str),
        errors="raise",
    )
    key_columns = ["poc", "timestamp"]
    conflicts = (
        data.groupby(key_columns)
        .agg(measurements=("measurement", "nunique"), methods=("method_code", "nunique"))
    )
    if ((conflicts["measurements"] > 1) | (conflicts["methods"] > 1)).any():
        raise ValueError("Conflicting duplicate hourly POC records.")
    return data.drop_duplicates(key_columns).sort_values(key_columns)


def qualifier_fraction(records: pd.DataFrame, poc: str, start: pd.Timestamp, end: pd.Timestamp) -> float:
    subset = records.loc[
        (records["poc"] == poc)
        & (records["timestamp"] >= start)
        & (records["timestamp"] <= end)
    ]
    if subset.empty:
        return np.nan
    qualifier = subset["qualifier"].astype("string").fillna("").str.strip()
    return float((qualifier != "").mean())


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_response_reason(manifest_entry: dict[str, object], raw_path: Path) -> str | None:
    """Reject API data unless this refresh recorded a successful matching response."""

    if not manifest_entry.get("request_succeeded", False):
        return str(
            manifest_entry.get(
                "api_error", "No successful hourly API request in manifest."
            )
        )
    expected_sha256 = manifest_entry.get("raw_sha256")
    if not raw_path.is_file() or not expected_sha256:
        return "Missing current successful hourly API response or hash."
    if file_sha256(raw_path) != expected_sha256:
        return "Hourly API response hash does not match current manifest."
    return None


def main() -> None:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    controls = pd.read_csv(CONTROLS_PATH, dtype="string")
    daily = pd.read_csv(DAILY_PATH, dtype="string")
    daily["target_minus_reference_effect_ug_m3"] = pd.to_numeric(
        daily["target_minus_reference_effect_ug_m3"]
    )
    manifest = json.loads(DOWNLOAD_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_by_id = {str(item["anchor_id"]): item for item in manifest}
    rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []

    for _, control in controls.iterrows():
        anchor_id = str(control["anchor_id"])
        anchor = anchors.loc[anchors["anchor_id"] == anchor_id].iloc[0]
        date = pd.Timestamp(anchor["start_date"])
        target_poc = str(anchor["POC"])
        reference_poc = str(control["control_poc"])
        manifest_entry = manifest_by_id.get(anchor_id, {})
        raw_path = RAW_DIR / f"{anchor_id}.json"
        base = {
            "anchor_id": anchor_id,
            "anchor_date": date.date().isoformat(),
            "target_poc": target_poc,
            "reference_poc": reference_poc,
            "api_status": manifest_entry.get("api_status"),
        }
        freshness_reason = current_response_reason(manifest_entry, raw_path)
        if freshness_reason is not None:
            rows.append(
                {
                    **base,
                    "status": "hourly_api_unavailable",
                    "reason": freshness_reason,
                }
            )
            continue
        try:
            records = canonical_hourly_records(
                json.loads(raw_path.read_text(encoding="utf-8"))
            )
            target = records.loc[records["poc"] == target_poc, ["timestamp", "measurement"]].rename(
                columns={"measurement": "target_measurement"}
            )
            reference = records.loc[
                records["poc"] == reference_poc, ["timestamp", "measurement"]
            ].rename(columns={"measurement": "reference_measurement"})
            paired = target.merge(reference, on="timestamp", how="inner")
            paired["difference_ug_m3"] = (
                paired["target_measurement"] - paired["reference_measurement"]
            )
            pre = paired.loc[
                (paired["timestamp"] >= date - pd.Timedelta(days=60))
                & (paired["timestamp"] < date)
            ]
            post = paired.loc[
                (paired["timestamp"] >= date)
                & (paired["timestamp"] <= date + pd.Timedelta(days=59))
            ]
            if len(pre) < 30 or len(post) < 30:
                raise ValueError(
                    "Fewer than 30 matched 1-hour POC observations in pre or post window."
                )
            effect = float(
                np.median(post["difference_ug_m3"])
                - np.median(pre["difference_ug_m3"])
            )
            daily_match = daily.loc[daily["anchor_id"] == anchor_id]
            daily_effect = (
                float(daily_match["target_minus_reference_effect_ug_m3"].iloc[0])
                if len(daily_match)
                else np.nan
            )
            rows.append(
                {
                    **base,
                    "status": "paired_hourly_pre_post_available",
                    "reason": None,
                    "paired_pre_hours": len(pre),
                    "paired_post_hours": len(post),
                    "pre_median_difference_ug_m3": float(
                        np.median(pre["difference_ug_m3"])
                    ),
                    "post_median_difference_ug_m3": float(
                        np.median(post["difference_ug_m3"])
                    ),
                    "hourly_difference_change_ug_m3": effect,
                    "daily_difference_change_ug_m3": daily_effect,
                    "hourly_daily_direction_agreement": bool(
                        np.sign(effect) == np.sign(daily_effect)
                    )
                    if np.isfinite(daily_effect) and daily_effect != 0
                    else np.nan,
                    "target_pre_qualifier_fraction": qualifier_fraction(
                        records, target_poc, date - pd.Timedelta(days=60), date - pd.Timedelta(days=1)
                    ),
                    "target_post_qualifier_fraction": qualifier_fraction(
                        records, target_poc, date, date + pd.Timedelta(days=59)
                    ),
                    "reference_pre_qualifier_fraction": qualifier_fraction(
                        records, reference_poc, date - pd.Timedelta(days=60), date - pd.Timedelta(days=1)
                    ),
                    "reference_post_qualifier_fraction": qualifier_fraction(
                        records, reference_poc, date, date + pd.Timedelta(days=59)
                    ),
                    "interpretation_boundary": (
                        "Same-site POC comparison reduces spatial variation but does "
                        "not establish physical instrument identity or causal bias."
                    ),
                }
            )
            detail_rows.extend(
                [
                    {
                        **base,
                        "period": "pre" if timestamp < date else "post",
                        "timestamp_local": timestamp.isoformat(),
                        "difference_ug_m3": difference,
                    }
                    for timestamp, difference in zip(
                        paired["timestamp"], paired["difference_ug_m3"], strict=True
                    )
                ]
            )
        except (KeyError, ValueError, pd.errors.ParserError) as error:
            rows.append(
                {
                    **base,
                    "status": "insufficient_matched_hourly_poc_evidence",
                    "reason": str(error),
                }
            )

    summary = pd.DataFrame(rows)
    summary.to_csv(OUTPUT_PATH, index=False)
    pd.DataFrame(detail_rows).to_csv(DETAIL_PATH, index=False)
    print(summary["status"].value_counts(dropna=False).to_string())
    print(f"Wrote {OUTPUT_PATH} and {DETAIL_PATH}")


if __name__ == "__main__":
    main()
