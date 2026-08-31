"""Build full geographically eligible donor pools for selection-aware bootstrap.

Unlike the main donor graph, this pool retains candidates below the initial
correlation threshold. Nested bootstrap repetitions can therefore re-evaluate
the correlation eligibility rule rather than conditioning on the original
top-ranked qualified donors alone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scan_data_gate import (  # noqa: E402
    DEFAULT_CONFIG,
    SERIES_KEYS,
    ensure_archives,
    haversine_km,
    historical_pairing,
    load_canonical_signal,
    prepare_series_lookup,
    window_is_stable,
)
from run_real_transition_audit import load_inputs  # noqa: E402


GATE_DIR = Path("artifacts/data_gate")
EVENT_AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
POOL_PATH = Path("artifacts/nested_bootstrap_candidate_pool.csv")
SUMMARY_PATH = Path("artifacts/nested_bootstrap_candidate_pool_summary.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build all stable geographic candidate donors for real anchors."
    )
    parser.add_argument("--max-events", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    anchors, _ = load_inputs(GATE_DIR)
    audit = pd.read_csv(EVENT_AUDIT_PATH, dtype="string")
    complete_ids = set(audit.loc[audit["audit_status"] == "complete", "anchor_id"])
    events = anchors.loc[anchors["anchor_id"].isin(complete_ids)].copy()
    if args.max_events is not None:
        if args.max_events <= 0:
            raise ValueError("--max-events must be positive.")
        events = events.head(args.max_events)

    data = load_canonical_signal(
        ensure_archives(Path("data/raw"), DEFAULT_CONFIG.years, download=False),
        "88101",
    )
    lookup, coordinates, _ = prepare_series_lookup(data)
    coordinate_keys = [
        tuple(str(value) for value in values)
        for values in coordinates[SERIES_KEYS].itertuples(index=False, name=None)
    ]
    coordinate_index = {key: index for index, key in enumerate(coordinate_keys)}
    latitudes = coordinates["Latitude"].to_numpy()
    longitudes = coordinates["Longitude"].to_numpy()
    rows: list[dict[str, object]] = []

    for position, (_, event) in enumerate(events.iterrows(), start=1):
        target_key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = lookup[target_key]
        date = pd.Timestamp(event["start_date"])
        target_index = coordinate_index[target_key]
        distances = haversine_km(
            float(latitudes[target_index]),
            float(longitudes[target_index]),
            latitudes,
            longitudes,
        )
        for candidate_index in np.flatnonzero(
            (distances > 0) & (distances <= DEFAULT_CONFIG.max_distance_km)
        ):
            candidate_key = coordinate_keys[candidate_index]
            if candidate_key[:3] == target_key[:3]:
                continue
            candidate = lookup[candidate_key]
            if not window_is_stable(candidate, date, DEFAULT_CONFIG):
                continue
            pairing = historical_pairing(target, candidate, date, DEFAULT_CONFIG)
            if pairing is None:
                continue
            paired_days, correlation = pairing
            rows.append(
                {
                    "anchor_id": event["anchor_id"],
                    "control_state_code": candidate_key[0],
                    "control_county_code": candidate_key[1],
                    "control_site_num": candidate_key[2],
                    "control_poc": candidate_key[3],
                    "distance_km": float(distances[candidate_index]),
                    "pre_transition_paired_days": paired_days,
                    "pre_transition_log_correlation": correlation,
                    "initially_passed_correlation_threshold": correlation
                    >= DEFAULT_CONFIG.min_correlation,
                }
            )
        if position % 50 == 0 or position == len(events):
            print(f"Built candidate pool for {position}/{len(events)} events")

    pool = pd.DataFrame(rows)
    summary = (
        pool.groupby("anchor_id")
        .agg(
            candidates=("control_poc", "size"),
            initially_eligible=(
                "initially_passed_correlation_threshold",
                "sum",
            ),
            minimum_correlation=("pre_transition_log_correlation", "min"),
            maximum_correlation=("pre_transition_log_correlation", "max"),
        )
        .reset_index()
    )
    pool.to_csv(POOL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    print(f"Wrote {POOL_PATH} and {SUMMARY_PATH}")
    print(summary[["candidates", "initially_eligible"]].describe().to_string())


if __name__ == "__main__":
    main()
