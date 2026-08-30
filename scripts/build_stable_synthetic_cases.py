"""Create synthetic benchmark cases from stable AQS method regimes only.

Unlike the superseded smoke experiments, this builder never injects a synthetic
effect at a reported Method Code transition. Each pseudo-anchor lies at least
60 days from a target or selected donor's reported method transition.
"""

from __future__ import annotations

import hashlib
import json
import sys
import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.counterfactual import (  # noqa: E402
    cross_validated_reliability_weights,
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)
from metashift.splits import V2_FINAL_TEST_STATES  # noqa: E402
from run_feasibility_prototype import synthetic_control_weights  # noqa: E402
from scan_data_gate import (  # noqa: E402
    DEFAULT_CONFIG,
    SERIES_KEYS,
    ensure_archives,
    historical_pairing,
    load_canonical_signal,
    prepare_series_lookup,
    window_is_stable,
)


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
CONTROLS_PATH = Path("artifacts/data_gate/geographic_controls.csv")
CASES_PATH = Path("artifacts/stable_synthetic_cases.csv")
DONORS_PATH = Path("artifacts/stable_synthetic_case_donors.csv")
EXCLUSIONS_PATH = Path("artifacts/stable_synthetic_case_exclusions.csv")
MANIFEST_PATH = Path("artifacts/stable_synthetic_case_manifest.json")
CASE_COUNT = 80
CALIBRATION_CASE_COUNT = 40
DONOR_COUNT = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build stable pseudo-anchor cases for the synthetic benchmark."
    )
    parser.add_argument("--case-count", type=int, default=CASE_COUNT)
    parser.add_argument(
        "--calibration-case-count", type=int, default=CALIBRATION_CASE_COUNT
    )
    return parser.parse_args()


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    for column in ["previous_start_date", "previous_end_date", "start_date"]:
        anchors[column] = pd.to_datetime(anchors[column])
    anchors["geographic_control_count"] = pd.to_numeric(
        anchors["geographic_control_count"]
    )
    anchors["pre_span_days"] = pd.to_numeric(anchors["pre_span_days"])

    controls = pd.read_csv(CONTROLS_PATH, dtype="string")
    for column in [
        "distance_km",
        "pre_transition_paired_days",
        "pre_transition_log_correlation",
        "rank",
    ]:
        controls[column] = pd.to_numeric(controls[column])
    return anchors, controls


def pseudo_dates(row: pd.Series) -> list[pd.Timestamp]:
    """Return deterministic candidate dates within the old stable method regime."""

    earliest = pd.Timestamp(row["previous_start_date"]) + pd.Timedelta(days=180)
    latest = pd.Timestamp(row["previous_end_date"]) - pd.Timedelta(days=60)
    if earliest > latest:
        return []
    span_days = (latest - earliest).days
    fractions = (0.50, 0.25, 0.75, 0.10, 0.90)
    dates = {
        earliest + pd.Timedelta(days=round(span_days * fraction))
        for fraction in fractions
    }
    return sorted(dates)


def nearest_observed_date(
    table: pd.DataFrame, candidate: pd.Timestamp, maximum_offset_days: int = 7
) -> pd.Timestamp | None:
    """Select a deterministic observed date near a metadata-only pseudo date."""

    observed = table.loc[
        candidate - pd.Timedelta(days=maximum_offset_days) : candidate
        + pd.Timedelta(days=maximum_offset_days)
    ].index
    if len(observed) == 0:
        return None
    return min(
        (pd.Timestamp(date) for date in observed),
        key=lambda date: (abs((date - candidate).days), date),
    )


def key_from_control(row: pd.Series) -> tuple[str, str, str, str]:
    return (
        str(row["control_state_code"]),
        str(row["control_county_code"]),
        str(row["control_site_num"]),
        str(row["control_poc"]),
    )


def selected_donors(
    source_anchor_id: str,
    target: pd.DataFrame,
    pseudo_date: pd.Timestamp,
    controls: pd.DataFrame,
    lookup: dict[tuple[str, str, str, str], pd.DataFrame],
) -> pd.DataFrame:
    """Revalidate each donor at the pseudo-anchor using pre-date data only."""

    candidates = controls.loc[controls["anchor_id"] == source_anchor_id]
    eligible: list[dict[str, object]] = []
    for _, candidate in candidates.iterrows():
        key = key_from_control(candidate)
        control = lookup.get(key)
        if control is None or not window_is_stable(control, pseudo_date, DEFAULT_CONFIG):
            continue
        pairing = historical_pairing(target, control, pseudo_date, DEFAULT_CONFIG)
        if pairing is None:
            continue
        paired_days, correlation = pairing
        if correlation < DEFAULT_CONFIG.min_correlation:
            continue
        eligible.append(
            {
                "control_state_code": key[0],
                "control_county_code": key[1],
                "control_site_num": key[2],
                "control_poc": key[3],
                "distance_km": float(candidate["distance_km"]),
                "pre_transition_paired_days": paired_days,
                "pre_transition_log_correlation": correlation,
            }
        )
    result = pd.DataFrame(eligible)
    if result.empty:
        return result
    return result.sort_values(
        ["pre_transition_log_correlation", "distance_km"],
        ascending=[False, True],
        kind="stable",
    ).head(DONOR_COUNT)


def is_complete_case(
    target: pd.DataFrame, donors: pd.DataFrame, metadata: pd.DataFrame, date: pd.Timestamp
) -> bool:
    """Require all comparative estimators to have valid pre/post input windows."""

    target_values = target["Arithmetic Mean"]
    donor_values = donors.sort_index()
    metadata = metadata.copy()
    metadata.index = donor_values.columns
    prior = donor_weights(metadata)
    calibration = slice(date - pd.Timedelta(days=180), date - pd.Timedelta(days=15))
    standard_weights = synthetic_control_weights(target_values, donor_values, date)
    metashift_weights = reliability_constrained_weights(
        target_values.loc[calibration],
        donor_values.loc[calibration],
        prior,
        ridge_penalty=0.1,
        prior_penalty=0.1,
    )
    cross_validated_reliability_weights(
        target_values.loc[calibration],
        donor_values.loc[calibration],
        prior,
    )
    estimate_metadata_anchor(target_values, donor_values, standard_weights, date)
    estimate_metadata_anchor(target_values, donor_values, metashift_weights, date)
    return True


def stable_case_id(target_key: tuple[str, str, str, str], date: pd.Timestamp) -> str:
    return f"stable-{'-'.join(target_key)}-{date.date().isoformat()}"


def manifest_sha256(cases: pd.DataFrame, donors: pd.DataFrame) -> str:
    case_data = cases.sort_values("case_id").to_csv(index=False, lineterminator="\n")
    donor_data = donors.sort_values(["case_id", "rank"]).to_csv(
        index=False, lineterminator="\n"
    )
    return hashlib.sha256((case_data + donor_data).encode("utf-8")).hexdigest()


def main() -> None:
    args = parse_args()
    if args.case_count <= 0:
        raise ValueError("--case-count must be positive.")
    if not 0 < args.calibration_case_count < args.case_count:
        raise ValueError(
            "--calibration-case-count must be positive and smaller than --case-count."
        )
    anchors, controls = load_inputs()
    source_events = anchors.loc[
        (~anchors["State Code"].isin(V2_FINAL_TEST_STATES))
        & (anchors["pre_span_days"] >= 300)
        & (anchors["geographic_control_count"] >= 3)
    ].sort_values("anchor_id", kind="stable")
    raw_paths = ensure_archives(
        Path("data/raw"), DEFAULT_CONFIG.years, download=False
    )
    data = load_canonical_signal(raw_paths)
    lookup, _, _ = prepare_series_lookup(data)

    cases: list[dict[str, object]] = []
    donor_rows: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []
    used_targets: set[tuple[str, str, str, str]] = set()

    for _, source in source_events.iterrows():
        if len(cases) == args.case_count:
            break
        target_key = tuple(str(source[column]) for column in SERIES_KEYS)
        if target_key in used_targets:
            continue
        target = lookup[target_key]
        for candidate_date in pseudo_dates(source):
            pseudo_date = nearest_observed_date(target, candidate_date)
            if pseudo_date is None:
                continue
            if not window_is_stable(target, pseudo_date, DEFAULT_CONFIG):
                continue
            metadata = selected_donors(
                str(source["anchor_id"]), target, pseudo_date, controls, lookup
            )
            if len(metadata) < 3:
                continue
            donor_series: dict[str, pd.Series] = {}
            for _, donor in metadata.iterrows():
                control_key = key_from_control(donor)
                donor_id = "-".join(control_key)
                donor_series[donor_id] = lookup[control_key]["Arithmetic Mean"]
            donors = pd.DataFrame(donor_series).sort_index()
            try:
                is_complete_case(target, donors, metadata, pseudo_date)
            except (RuntimeError, ValueError) as error:
                exclusions.append(
                    {
                        "source_anchor_id": str(source["anchor_id"]),
                        "candidate_date": pseudo_date.date().isoformat(),
                        "reason": str(error),
                    }
                )
                continue

            case_id = stable_case_id(target_key, pseudo_date)
            cases.append(
                {
                    "case_id": case_id,
                    "source_anchor_id": source["anchor_id"],
                    "State Code": target_key[0],
                    "County Code": target_key[1],
                    "Site Num": target_key[2],
                    "POC": target_key[3],
                    "pseudo_anchor_date": pseudo_date.date().isoformat(),
                    "target_method_code": target.loc[pseudo_date, "Method Code"],
                    "donor_count": len(metadata),
                }
            )
            for rank, (_, donor) in enumerate(metadata.iterrows(), start=1):
                donor_rows.append(
                    {
                        "case_id": case_id,
                        "rank": rank,
                        **donor.to_dict(),
                    }
                )
            used_targets.add(target_key)
            print(f"Built stable case {len(cases)}/{args.case_count}: {case_id}")
            break

    case_frame = pd.DataFrame(cases)
    donor_frame = pd.DataFrame(donor_rows)
    pd.DataFrame(exclusions).to_csv(EXCLUSIONS_PATH, index=False)
    if len(case_frame) < args.case_count:
        raise RuntimeError(
            f"Only constructed {len(case_frame)} stable complete cases; expected "
            f"{args.case_count}. See {EXCLUSIONS_PATH}."
        )
    case_frame["split"] = [
        "calibration"
        if index < args.calibration_case_count
        else "evaluation"
        for index in range(len(case_frame))
    ]
    case_frame.to_csv(CASES_PATH, index=False)
    donor_frame.to_csv(DONORS_PATH, index=False)
    manifest = {
        "purpose": "Stable method-regime synthetic benchmark cases",
        "case_count": len(case_frame),
        "calibration_case_count": args.calibration_case_count,
        "evaluation_case_count": len(case_frame) - args.calibration_case_count,
        "unique_target_monitors": case_frame[
            ["State Code", "County Code", "Site Num", "POC"]
        ].drop_duplicates().shape[0],
        "excluded_target_states": sorted(V2_FINAL_TEST_STATES),
        "minimum_distance_from_target_or_donor_method_transition_days": 60,
        "calibration_window_days": 180,
        "calibration_buffer_days": 15,
        "case_and_donor_sha256": manifest_sha256(case_frame, donor_frame),
        "status": "Synthetic effects are injected only at these stable pseudo-anchors.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
