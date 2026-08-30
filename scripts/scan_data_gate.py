"""Build the reproducible EPA AQS Method Code data-gate inventory for MetaShift."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import pandas as pd


EPA_AIRDATA_URL = "https://aqs.epa.gov/aqsweb/airdata/daily_{parameter_code}_{year}.zip"
DEFAULT_PARAMETER_CODE = "88101"
SERIES_KEYS = ["State Code", "County Code", "Site Num", "POC"]
SITE_KEYS = SERIES_KEYS[:3]
SIGNAL_DURATION = "24-HR BLK AVG"

USE_COLUMNS = [
    "State Code",
    "County Code",
    "Site Num",
    "POC",
    "Parameter Code",
    "Sample Duration",
    "Date Local",
    "Arithmetic Mean",
    "Observation Percent",
    "Method Code",
    "Method Name",
    "Latitude",
    "Longitude",
    "Event Type",
]

DTYPES = {
    # AQS codes are identifiers, not numbers. Keeping their leading zeroes is
    # necessary for joins against the monitor and API data.
    "State Code": "string",
    "County Code": "string",
    "Site Num": "string",
    "POC": "string",
    "Parameter Code": "string",
    "Sample Duration": "category",
    "Arithmetic Mean": "float32",
    "Observation Percent": "float32",
    "Method Code": "string",
    "Method Name": "string",
    "Latitude": "float32",
    "Longitude": "float32",
    "Event Type": "category",
}


@dataclass(frozen=True)
class GateConfig:
    years: tuple[int, ...]
    min_window_days: int
    min_window_observations: int
    max_transition_gap_days: int
    calibration_days: int
    calibration_buffer_days: int
    min_paired_days: int
    min_correlation: float
    max_distance_km: float


DEFAULT_CONFIG = GateConfig(
    years=tuple(range(2019, 2026)),
    min_window_days=60,
    min_window_observations=45,
    max_transition_gap_days=7,
    calibration_days=180,
    calibration_buffer_days=15,
    min_paired_days=60,
    min_correlation=0.60,
    max_distance_km=100.0,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan persistent AQS PM2.5 Method Code transitions and controls."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data") / "raw",
        help="Directory containing daily_88101_<year>.zip archives.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts") / "data_gate",
        help="Directory for CSV inventories and the provenance manifest.",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(DEFAULT_CONFIG.years),
        help="AQS archive years to scan.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download missing archives from EPA AirData.",
    )
    parser.add_argument(
        "--parameter-code",
        default=DEFAULT_PARAMETER_CODE,
        help="AQS parameter code, kept separate for each analysis pipeline.",
    )
    return parser.parse_args()


def archive_path(raw_dir: Path, year: int, parameter_code: str = DEFAULT_PARAMETER_CODE) -> Path:
    return raw_dir / f"daily_{parameter_code}_{year}.zip"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_archives(
    raw_dir: Path,
    years: tuple[int, ...],
    download: bool,
    parameter_code: str = DEFAULT_PARAMETER_CODE,
) -> list[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for year in years:
        path = archive_path(raw_dir, year, parameter_code)
        if not path.exists():
            if not download:
                raise FileNotFoundError(
                    f"Missing {path}. Re-run with --download or place the EPA archive there."
                )
            url = EPA_AIRDATA_URL.format(year=year, parameter_code=parameter_code)
            print(f"Downloading {url}", flush=True)
            urlretrieve(url, path)
        paths.append(path)
    return paths


def write_source_manifest(
    paths: list[Path], output_dir: Path, parameter_code: str = DEFAULT_PARAMETER_CODE
) -> None:
    manifest = []
    for path in paths:
        year = int(path.stem.rsplit("_", 1)[1])
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            if len(members) != 1 or not members[0].endswith(".csv"):
                raise ValueError(f"Expected exactly one CSV member in {path}.")
            member = members[0]
            with archive.open(member) as csv_file:
                row_count = sum(1 for _ in csv_file) - 1
        manifest.append(
            {
                "year": year,
                "parameter_code": parameter_code,
                "url": EPA_AIRDATA_URL.format(year=year, parameter_code=parameter_code),
                "path": str(path),
                "bytes": path.stat().st_size,
                "file_modified_utc": datetime.fromtimestamp(
                    path.stat().st_mtime, UTC
                ).isoformat(),
                "sha256": file_sha256(path),
                "csv_member": member,
                "csv_data_rows": row_count,
            }
        )
    (output_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    pd.DataFrame(manifest).to_csv(output_dir / "data_manifest.csv", index=False)


def load_canonical_signal(
    paths: list[Path], parameter_code: str = DEFAULT_PARAMETER_CODE
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(
            path,
            usecols=USE_COLUMNS,
            dtype=DTYPES,
            parse_dates=["Date Local"],
            compression="zip",
            low_memory=False,
        )
        frame["Method Code"] = frame["Method Code"].str.strip()
        event_type = frame["Event Type"].astype("string").fillna("")
        valid = (
            (frame["Sample Duration"] == SIGNAL_DURATION)
            & (frame["Parameter Code"] == parameter_code)
            & (event_type != "Excluded")
            & frame["Arithmetic Mean"].notna()
            & np.isfinite(frame["Arithmetic Mean"])
            & (frame["Observation Percent"] >= 75)
            & frame["Method Code"].notna()
            & (frame["Method Code"] != "")
        )
        frame = frame.loc[valid].copy()
        frames.append(frame)
        print(f"Loaded {path.name}: {len(frame):,} canonical records", flush=True)

    data = pd.concat(frames, ignore_index=True)
    duplicate_rows = data.duplicated(SERIES_KEYS + ["Date Local"], keep=False)
    if duplicate_rows.any():
        duplicate_count = int(duplicate_rows.sum())
        raise ValueError(
            f"Found {duplicate_count:,} duplicate monitor-days after canonical filtering; "
            "refusing to choose a record silently."
        )

    return data.sort_values(SERIES_KEYS + ["Date Local"], kind="stable").reset_index(
        drop=True
    )


def build_runs(data: pd.DataFrame) -> pd.DataFrame:
    grouped = data.groupby(SERIES_KEYS, observed=True, sort=False)
    first_in_series = grouped.cumcount().eq(0)
    method_changed = data["Method Code"].ne(grouped["Method Code"].shift())
    data = data.copy()
    data["_run_id"] = (first_in_series | method_changed).cumsum()

    runs = (
        data.groupby(SERIES_KEYS + ["_run_id"], observed=True, sort=False)
        .agg(
            method_code=("Method Code", "first"),
            method_name=("Method Name", "first"),
            start_date=("Date Local", "min"),
            end_date=("Date Local", "max"),
            observations=("Date Local", "size"),
        )
        .reset_index()
        .sort_values(SERIES_KEYS + ["start_date"], kind="stable")
        .reset_index(drop=True)
    )

    grouped_runs = runs.groupby(SERIES_KEYS, observed=True, sort=False)
    runs["previous_method_code"] = grouped_runs["method_code"].shift()
    runs["previous_method_name"] = grouped_runs["method_name"].shift()
    runs["previous_start_date"] = grouped_runs["start_date"].shift()
    runs["previous_end_date"] = grouped_runs["end_date"].shift()
    runs["previous_observations"] = grouped_runs["observations"].shift()
    runs["transition_gap_days"] = (
        runs["start_date"] - runs["previous_end_date"]
    ).dt.days
    runs["pre_span_days"] = (
        runs["previous_end_date"] - runs["previous_start_date"]
    ).dt.days
    runs["post_span_days"] = (runs["end_date"] - runs["start_date"]).dt.days
    return runs


def select_anchors(runs: pd.DataFrame, config: GateConfig) -> pd.DataFrame:
    anchors = runs.loc[runs["previous_method_code"].notna()].copy()
    return anchors.loc[
        (anchors["previous_observations"] >= config.min_window_observations)
        & (anchors["observations"] >= config.min_window_observations)
        & (anchors["pre_span_days"] >= config.min_window_days - 1)
        & (anchors["post_span_days"] >= config.min_window_days - 1)
        & (anchors["transition_gap_days"] <= config.max_transition_gap_days)
    ].copy()


def series_key(row: pd.Series) -> tuple[str, str, str, str]:
    return tuple(str(row[column]) for column in SERIES_KEYS)  # type: ignore[return-value]


def anchor_id(row: pd.Series) -> str:
    state, county, site, poc = series_key(row)
    return f"{state}-{county}-{site}-poc{poc}-{pd.Timestamp(row['start_date']).date().isoformat()}"


def haversine_km(
    origin_latitude: float,
    origin_longitude: float,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> np.ndarray:
    origin_latitude, origin_longitude = np.radians(
        [origin_latitude, origin_longitude]
    )
    target_latitudes = np.radians(latitudes)
    target_longitudes = np.radians(longitudes)
    latitude_delta = target_latitudes - origin_latitude
    longitude_delta = target_longitudes - origin_longitude
    a = (
        np.sin(latitude_delta / 2) ** 2
        + np.cos(origin_latitude)
        * np.cos(target_latitudes)
        * np.sin(longitude_delta / 2) ** 2
    )
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def window_is_stable(
    table: pd.DataFrame, anchor_date: pd.Timestamp, config: GateConfig
) -> bool:
    start = anchor_date - pd.Timedelta(days=config.min_window_days)
    end = anchor_date + pd.Timedelta(days=config.min_window_days)
    window = table.loc[start:end]
    return (
        len(window) >= 2 * config.min_window_observations
        and window["Method Code"].nunique() == 1
    )


def historical_pairing(
    target: pd.DataFrame,
    control: pd.DataFrame,
    anchor_date: pd.Timestamp,
    config: GateConfig,
) -> tuple[int, float] | None:
    start = anchor_date - pd.Timedelta(days=config.calibration_days)
    end = anchor_date - pd.Timedelta(days=config.calibration_buffer_days)
    target_pre = target.loc[start:end, ["Arithmetic Mean"]].rename(
        columns={"Arithmetic Mean": "target"}
    )
    control_pre = control.loc[start:end, ["Arithmetic Mean"]].rename(
        columns={"Arithmetic Mean": "control"}
    )
    paired = target_pre.join(control_pre, how="inner")
    if len(paired) < config.min_paired_days:
        return None

    # Rare slightly negative concentrations are retained in the data but clipped
    # only for the logarithmic correlation transform.
    target_values = np.log1p(np.maximum(paired["target"].to_numpy(), 0.0))
    control_values = np.log1p(np.maximum(paired["control"].to_numpy(), 0.0))
    if np.std(target_values) == 0 or np.std(control_values) == 0:
        return None
    correlation = float(np.corrcoef(target_values, control_values)[0, 1])
    if not np.isfinite(correlation):
        return None
    return len(paired), correlation


def prepare_series_lookup(
    data: pd.DataFrame,
) -> tuple[
    dict[tuple[str, str, str, str], pd.DataFrame],
    pd.DataFrame,
    dict[tuple[str, str, str], list[tuple[str, str, str, str]]],
]:
    lookup: dict[tuple[str, str, str, str], pd.DataFrame] = {}
    site_to_series: dict[tuple[str, str, str], list[tuple[str, str, str, str]]] = {}
    for raw_key, group in data.groupby(SERIES_KEYS, observed=True, sort=False):
        key = tuple(str(value) for value in raw_key)
        lookup[key] = group.set_index("Date Local")[
            ["Arithmetic Mean", "Method Code"]
        ].sort_index()
        site_to_series.setdefault(key[:3], []).append(key)

    coordinates = (
        data.groupby(SERIES_KEYS, observed=True)[["Latitude", "Longitude"]]
        .median()
        .reset_index()
    )
    if coordinates[["Latitude", "Longitude"]].isna().any().any():
        raise ValueError("At least one canonical monitor series has no coordinates.")
    return lookup, coordinates, site_to_series


def match_controls(
    anchors: pd.DataFrame, data: pd.DataFrame, config: GateConfig
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lookup, coordinates, site_to_series = prepare_series_lookup(data)
    coordinate_keys = [
        tuple(str(value) for value in row)
        for row in coordinates[SERIES_KEYS].itertuples(index=False, name=None)
    ]
    coordinate_index = {key: index for index, key in enumerate(coordinate_keys)}
    latitudes = coordinates["Latitude"].to_numpy()
    longitudes = coordinates["Longitude"].to_numpy()

    geographic_rows: list[dict[str, object]] = []
    colocated_rows: list[dict[str, object]] = []
    anchor_rows: list[dict[str, object]] = []

    for position, (_, row) in enumerate(anchors.iterrows(), start=1):
        target_key = series_key(row)
        target = lookup[target_key]
        date = pd.Timestamp(row["start_date"])
        current_index = coordinate_index[target_key]
        distances = haversine_km(
            float(latitudes[current_index]),
            float(longitudes[current_index]),
            latitudes,
            longitudes,
        )
        candidate_indexes = np.flatnonzero(distances <= config.max_distance_km)
        event_id = anchor_id(row)
        eligible_controls: list[dict[str, object]] = []

        for index in candidate_indexes:
            control_key = coordinate_keys[index]
            if control_key[:3] == target_key[:3]:
                continue
            control = lookup[control_key]
            if not window_is_stable(control, date, config):
                continue
            pairing = historical_pairing(target, control, date, config)
            if pairing is None:
                continue
            paired_days, correlation = pairing
            if correlation < config.min_correlation:
                continue
            eligible_controls.append(
                {
                    "anchor_id": event_id,
                    "control_state_code": control_key[0],
                    "control_county_code": control_key[1],
                    "control_site_num": control_key[2],
                    "control_poc": control_key[3],
                    "distance_km": float(distances[index]),
                    "pre_transition_paired_days": paired_days,
                    "pre_transition_log_correlation": correlation,
                }
            )

        eligible_controls.sort(
            key=lambda value: (
                -float(value["pre_transition_log_correlation"]),
                float(value["distance_km"]),
            )
        )
        for rank, control in enumerate(eligible_controls, start=1):
            control["rank"] = rank
            geographic_rows.append(control)

        colocated_count = 0
        for control_key in site_to_series[target_key[:3]]:
            if control_key == target_key:
                continue
            control = lookup[control_key]
            if not window_is_stable(control, date, config):
                continue
            pairing = historical_pairing(target, control, date, config)
            if pairing is None or pairing[1] < config.min_correlation:
                continue
            paired_days, correlation = pairing
            colocated_rows.append(
                {
                    "anchor_id": event_id,
                    "control_state_code": control_key[0],
                    "control_county_code": control_key[1],
                    "control_site_num": control_key[2],
                    "control_poc": control_key[3],
                    "pre_transition_paired_days": paired_days,
                    "pre_transition_log_correlation": correlation,
                }
            )
            colocated_count += 1

        anchor_row = row.to_dict()
        anchor_row["anchor_id"] = event_id
        anchor_row["geographic_control_count"] = len(eligible_controls)
        anchor_row["colocated_control_count"] = colocated_count
        anchor_rows.append(anchor_row)

        if position % 100 == 0 or position == len(anchors):
            print(f"Matched controls for {position:,}/{len(anchors):,} anchors", flush=True)

    return (
        pd.DataFrame(anchor_rows),
        pd.DataFrame(geographic_rows),
        pd.DataFrame(colocated_rows),
    )


def write_outputs(
    data: pd.DataFrame,
    runs: pd.DataFrame,
    anchor_inventory: pd.DataFrame,
    controls: pd.DataFrame,
    colocated_controls: pd.DataFrame,
    output_dir: Path,
    config: GateConfig,
    parameter_code: str = DEFAULT_PARAMETER_CODE,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs.to_csv(output_dir / "method_runs.csv", index=False)
    anchor_inventory.to_csv(output_dir / "anchor_inventory.csv", index=False)
    controls.to_csv(output_dir / "geographic_controls.csv", index=False)
    colocated_controls.to_csv(output_dir / "colocated_controls.csv", index=False)

    transition_summary = (
        anchor_inventory.groupby(
            ["previous_method_code", "method_code"], dropna=False
        )
        .size()
        .rename("anchor_count")
        .reset_index()
        .sort_values("anchor_count", ascending=False)
    )
    transition_summary.to_csv(output_dir / "transition_summary.csv", index=False)

    state_summary = (
        anchor_inventory.groupby("State Code")
        .size()
        .rename("anchor_count")
        .reset_index()
        .sort_values("anchor_count", ascending=False)
    )
    state_summary.to_csv(output_dir / "state_summary.csv", index=False)

    summary = {
        "canonical_records": int(len(data)),
        "monitor_series": int(data.groupby(SERIES_KEYS, observed=True).ngroups),
        "method_runs": int(len(runs)),
        "eligible_anchors": int(len(anchor_inventory)),
        "anchors_with_one_geographic_control": int(
            (anchor_inventory["geographic_control_count"] >= 1).sum()
        ),
        "anchors_with_three_geographic_controls": int(
            (anchor_inventory["geographic_control_count"] >= 3).sum()
        ),
        "anchors_with_colocated_control": int(
            (anchor_inventory["colocated_control_count"] >= 1).sum()
        ),
        "config": {
            "years": list(config.years),
            "parameter_code": parameter_code,
            "signal_duration": SIGNAL_DURATION,
            "minimum_window_days": config.min_window_days,
            "minimum_window_observations": config.min_window_observations,
            "maximum_transition_gap_days": config.max_transition_gap_days,
            "calibration_days": config.calibration_days,
            "calibration_buffer_days": config.calibration_buffer_days,
            "minimum_paired_days": config.min_paired_days,
            "minimum_correlation": config.min_correlation,
            "maximum_control_distance_km": config.max_distance_km,
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main() -> int:
    args = parse_args()
    years = tuple(sorted(set(args.years)))
    config = GateConfig(
        years=years,
        min_window_days=DEFAULT_CONFIG.min_window_days,
        min_window_observations=DEFAULT_CONFIG.min_window_observations,
        max_transition_gap_days=DEFAULT_CONFIG.max_transition_gap_days,
        calibration_days=DEFAULT_CONFIG.calibration_days,
        calibration_buffer_days=DEFAULT_CONFIG.calibration_buffer_days,
        min_paired_days=DEFAULT_CONFIG.min_paired_days,
        min_correlation=DEFAULT_CONFIG.min_correlation,
        max_distance_km=DEFAULT_CONFIG.max_distance_km,
    )
    parameter_code = str(args.parameter_code)
    paths = ensure_archives(args.raw_dir, years, args.download, parameter_code)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_source_manifest(paths, args.output_dir, parameter_code)
    data = load_canonical_signal(paths, parameter_code)
    runs = build_runs(data)
    anchors = select_anchors(runs, config)
    anchor_inventory, controls, colocated_controls = match_controls(
        anchors, data, config
    )
    write_outputs(
        data,
        runs,
        anchor_inventory,
        controls,
        colocated_controls,
        args.output_dir,
        config,
        parameter_code,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
        print(f"Data-gate failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
