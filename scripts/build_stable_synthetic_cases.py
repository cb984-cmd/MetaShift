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
from collections import defaultdict
from pathlib import Path

import numpy as np
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
    haversine_km,
    historical_pairing,
    load_canonical_signal,
    prepare_series_lookup,
    rank_distinct_physical_controls,
    window_is_stable,
)


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
CONTROLS_PATH = Path("artifacts/data_gate/geographic_controls.csv")
CASES_PATH = Path("artifacts/stable_synthetic_cases.csv")
DONORS_PATH = Path("artifacts/stable_synthetic_case_donors.csv")
EXCLUSIONS_PATH = Path("artifacts/stable_synthetic_case_exclusions.csv")
MANIFEST_PATH = Path("artifacts/stable_synthetic_case_manifest.json")
CASE_COUNT = 146
CALIBRATION_CASE_COUNT = 66
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


def stable_regime_pseudo_dates(table: pd.DataFrame) -> list[pd.Timestamp]:
    """Choose deterministic pseudo-anchors from any sufficiently long method run."""

    methods = table["Method Code"].astype("string")
    run_ids = methods.ne(methods.shift()).cumsum()
    candidates: set[pd.Timestamp] = set()
    for _, run in table.groupby(run_ids, sort=False):
        earliest = run.index.min() + pd.Timedelta(days=180)
        latest = run.index.max() - pd.Timedelta(days=60)
        if earliest > latest:
            continue
        span_days = (latest - earliest).days
        for fraction in (0.50, 0.25, 0.75, 0.10, 0.90):
            candidates.add(
                earliest + pd.Timedelta(days=round(span_days * fraction))
            )
    return sorted(candidates)


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
    excluded_sites: set[tuple[str, str, str]] | None = None,
) -> pd.DataFrame:
    """Revalidate each donor at the pseudo-anchor using pre-date data only."""

    candidates = controls.loc[controls["anchor_id"] == source_anchor_id]
    excluded_sites = excluded_sites or set()
    eligible: list[dict[str, object]] = []
    for _, candidate in candidates.iterrows():
        key = key_from_control(candidate)
        if key[:3] in excluded_sites:
            continue
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


def nearby_stable_donors(
    target_key: tuple[str, str, str, str],
    target: pd.DataFrame,
    pseudo_date: pd.Timestamp,
    lookup: dict[tuple[str, str, str, str], pd.DataFrame],
    coordinate_keys: list[tuple[str, str, str, str]],
    coordinate_index: dict[tuple[str, str, str, str], int],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> pd.DataFrame:
    """Find distinct physical donor sites for a non-transition stable monitor."""

    target_index = coordinate_index[target_key]
    distances = haversine_km(
        float(latitudes[target_index]),
        float(longitudes[target_index]),
        latitudes,
        longitudes,
    )
    eligible: list[dict[str, object]] = []
    for candidate_index in np.flatnonzero(
        (distances > 0) & (distances <= DEFAULT_CONFIG.max_distance_km)
    ):
        control_key = coordinate_keys[candidate_index]
        if control_key[:3] == target_key[:3]:
            continue
        control = lookup[control_key]
        if not window_is_stable(control, pseudo_date, DEFAULT_CONFIG):
            continue
        pairing = historical_pairing(target, control, pseudo_date, DEFAULT_CONFIG)
        if pairing is None:
            continue
        paired_days, correlation = pairing
        if correlation < DEFAULT_CONFIG.min_correlation:
            continue
        eligible.append(
            {
                "control_state_code": control_key[0],
                "control_county_code": control_key[1],
                "control_site_num": control_key[2],
                "control_poc": control_key[3],
                "distance_km": float(distances[candidate_index]),
                "pre_transition_paired_days": paired_days,
                "pre_transition_log_correlation": correlation,
            }
        )
    return pd.DataFrame(rank_distinct_physical_controls(eligible)).head(DONOR_COUNT)


def donor_series(
    metadata: pd.DataFrame,
    lookup: dict[tuple[str, str, str, str], pd.DataFrame],
) -> pd.DataFrame:
    """Materialize recorded donor metadata as a deterministically ordered matrix."""

    values = {
        "-".join(key_from_control(donor)): lookup[key_from_control(donor)][
            "Arithmetic Mean"
        ]
        for _, donor in metadata.iterrows()
    }
    return pd.DataFrame(values).sort_index()


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


def assign_input_disjoint_splits(
    cases: pd.DataFrame, donors: pd.DataFrame, calibration_case_count: int
) -> pd.DataFrame:
    """Assign whole shared-input components to calibration or evaluation."""

    case_ids = [str(case_id) for case_id in cases["case_id"]]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Stable synthetic case IDs must be unique.")
    if not 0 < calibration_case_count < len(case_ids):
        raise ValueError("Calibration case count must be within the case set.")
    parent = {case_id: case_id for case_id in case_ids}

    def find(case_id: str) -> str:
        while parent[case_id] != case_id:
            parent[case_id] = parent[parent[case_id]]
            case_id = parent[case_id]
        return case_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    sites_to_cases: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for _, row in cases.iterrows():
        sites_to_cases[
            (str(row["State Code"]), str(row["County Code"]), str(row["Site Num"]))
        ].append(str(row["case_id"]))
    for _, row in donors.iterrows():
        case_id = str(row["case_id"])
        if case_id not in parent:
            raise ValueError(f"Donor row references unknown case ID: {case_id}")
        sites_to_cases[
            (
                str(row["control_state_code"]),
                str(row["control_county_code"]),
                str(row["control_site_num"]),
            )
        ].append(case_id)
    for linked_cases in sites_to_cases.values():
        for case_id in linked_cases[1:]:
            union(linked_cases[0], case_id)

    components: dict[str, list[str]] = defaultdict(list)
    for case_id in case_ids:
        components[find(case_id)].append(case_id)
    ordered_components = sorted(
        (sorted(component) for component in components.values()),
        key=lambda component: (len(component), component),
    )
    reachable: dict[int, tuple[int, ...]] = {0: ()}
    for component_index, component in enumerate(ordered_components):
        component_size = len(component)
        for total in sorted(list(reachable), reverse=True):
            candidate_total = total + component_size
            if (
                candidate_total <= calibration_case_count
                and candidate_total not in reachable
            ):
                reachable[candidate_total] = reachable[total] + (component_index,)
    if calibration_case_count not in reachable:
        component_sizes = [len(component) for component in ordered_components]
        raise RuntimeError(
            "Unable to form an input-disjoint calibration split with "
            f"{calibration_case_count} cases from component sizes {component_sizes}."
        )

    calibration_components = set(reachable[calibration_case_count])
    split_by_case = {
        case_id: (
            "calibration"
            if component_index in calibration_components
            else "evaluation"
        )
        for component_index, component in enumerate(ordered_components)
        for case_id in component
    }
    result = cases.copy()
    result["split"] = result["case_id"].map(split_by_case)
    return result


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
    calibration_quota = args.calibration_case_count
    evaluation_quota = args.case_count - calibration_quota
    raw_paths = ensure_archives(
        Path("data/raw"), DEFAULT_CONFIG.years, download=False
    )
    data = load_canonical_signal(raw_paths)
    lookup, coordinates, _ = prepare_series_lookup(data)
    coordinate_keys = [
        tuple(str(value) for value in row)
        for row in coordinates[SERIES_KEYS].itertuples(index=False, name=None)
    ]
    coordinate_index = {
        key: index for index, key in enumerate(coordinate_keys)
    }
    latitudes = coordinates["Latitude"].to_numpy()
    longitudes = coordinates["Longitude"].to_numpy()

    exclusions: list[dict[str, str]] = []
    candidates: list[dict[str, object]] = []
    # A physical station may have several POCs. Keeping the target site identifier
    # unique prevents POC variants from leaking between calibration and evaluation.
    used_target_sites: set[tuple[str, str, str]] = set()
    for _, source in source_events.iterrows():
        if len(candidates) == args.case_count:
            break
        target_key = tuple(str(source[column]) for column in SERIES_KEYS)
        site_key = target_key[:3]
        if site_key in used_target_sites:
            continue
        target = lookup[target_key]
        for candidate_date in pseudo_dates(source):
            pseudo_date = nearest_observed_date(target, candidate_date)
            if pseudo_date is None:
                continue
            if not window_is_stable(target, pseudo_date, DEFAULT_CONFIG):
                continue
            metadata = selected_donors(
                str(source["anchor_id"]),
                target,
                pseudo_date,
                controls,
                lookup,
            )
            if len(metadata) < 3:
                continue
            donors = donor_series(metadata, lookup)
            try:
                is_complete_case(target, donors, metadata, pseudo_date)
            except (RuntimeError, ValueError) as error:
                exclusions.append(
                    {
                        "source_anchor_id": str(source["anchor_id"]),
                        "candidate_date": pseudo_date.date().isoformat(),
                        "reason": f"candidate validation: {error}",
                    }
                )
                continue
            candidates.append(
                {
                    "source_anchor_id": str(source["anchor_id"]),
                    "target_key": target_key,
                    "pseudo_date": pseudo_date,
                    "donor_metadata": metadata,
                    "case_source": "method_transition_stable_regime",
                }
            )
            used_target_sites.add(site_key)
            break

    for target_key in sorted(lookup):
        if len(candidates) == args.case_count:
            break
        site_key = target_key[:3]
        if target_key[0] in V2_FINAL_TEST_STATES or site_key in used_target_sites:
            continue
        target = lookup[target_key]
        for candidate_date in stable_regime_pseudo_dates(target):
            pseudo_date = nearest_observed_date(target, candidate_date)
            if pseudo_date is None:
                continue
            if not window_is_stable(target, pseudo_date, DEFAULT_CONFIG):
                continue
            metadata = nearby_stable_donors(
                target_key,
                target,
                pseudo_date,
                lookup,
                coordinate_keys,
                coordinate_index,
                latitudes,
                longitudes,
            )
            if len(metadata) < 3:
                continue
            donors = donor_series(metadata, lookup)
            try:
                is_complete_case(target, donors, metadata, pseudo_date)
            except (RuntimeError, ValueError) as error:
                exclusions.append(
                    {
                        "source_anchor_id": "",
                        "candidate_date": pseudo_date.date().isoformat(),
                        "reason": f"generic stable-monitor validation: {error}",
                    }
                )
                continue
            candidates.append(
                {
                    "source_anchor_id": None,
                    "target_key": target_key,
                    "pseudo_date": pseudo_date,
                    "donor_metadata": metadata,
                    "case_source": "all_monitor_stable_regime",
                }
            )
            used_target_sites.add(site_key)
            break

    if len(candidates) < args.case_count:
        pd.DataFrame(exclusions).to_csv(EXCLUSIONS_PATH, index=False)
        raise RuntimeError(
            f"Only identified {len(candidates)} stable complete target cases; expected "
            f"{args.case_count}. See {EXCLUSIONS_PATH}."
        )

    cases: list[dict[str, object]] = []
    donor_rows: list[dict[str, object]] = []
    for candidate in candidates:
        target_key = candidate["target_key"]
        if not isinstance(target_key, tuple):
            raise TypeError("Stable-case target key must be a tuple.")
        pseudo_date = candidate["pseudo_date"]
        if not isinstance(pseudo_date, pd.Timestamp):
            raise TypeError("Stable-case pseudo-anchor must be a pandas timestamp.")
        target = lookup[target_key]
        metadata = candidate["donor_metadata"]
        if not isinstance(metadata, pd.DataFrame):
            raise TypeError("Stable-case donor metadata must be a pandas DataFrame.")
        if len(metadata) < 3:
            raise RuntimeError("A previously validated stable case lost its donors.")
        donors = donor_series(metadata, lookup)
        try:
            is_complete_case(target, donors, metadata, pseudo_date)
        except (RuntimeError, ValueError) as error:
            raise RuntimeError(
                "A previously validated stable case no longer has complete inputs."
            ) from error
        case_id = stable_case_id(target_key, pseudo_date)
        cases.append(
            {
                "case_id": case_id,
                "source_anchor_id": candidate["source_anchor_id"],
                "case_source": candidate["case_source"],
                "State Code": target_key[0],
                "County Code": target_key[1],
                "Site Num": target_key[2],
                "POC": target_key[3],
                "pseudo_anchor_date": pseudo_date.date().isoformat(),
                "target_method_code": target.loc[pseudo_date, "Method Code"],
                "donor_count": len(metadata),
            }
        )
        donor_rows.extend(
            {
                "case_id": case_id,
                "rank": rank,
                **donor.to_dict(),
            }
            for rank, (_, donor) in enumerate(metadata.iterrows(), start=1)
        )

    case_frame = pd.DataFrame(cases)
    donor_frame = pd.DataFrame(donor_rows)
    case_frame = assign_input_disjoint_splits(
        case_frame, donor_frame, calibration_quota
    )
    pd.DataFrame(exclusions).to_csv(EXCLUSIONS_PATH, index=False)
    if len(case_frame) != args.case_count:
        raise RuntimeError(
            f"Built {len(case_frame)} cases; expected {args.case_count}."
        )
    if int((case_frame["split"] == "evaluation").sum()) != evaluation_quota:
        raise RuntimeError("Input-disjoint split did not preserve the evaluation quota.")
    case_frame.to_csv(CASES_PATH, index=False)
    donor_frame.to_csv(DONORS_PATH, index=False)
    manifest = {
        "purpose": "Stable method-regime synthetic benchmark cases",
        "case_count": len(case_frame),
        "calibration_case_count": args.calibration_case_count,
        "evaluation_case_count": evaluation_quota,
        "unique_target_monitors": case_frame[
            ["State Code", "County Code", "Site Num", "POC"]
        ].drop_duplicates().shape[0],
        "unique_target_physical_sites": case_frame[
            ["State Code", "County Code", "Site Num"]
        ].drop_duplicates().shape[0],
        "case_source_counts": case_frame["case_source"].value_counts().to_dict(),
        "excluded_target_states": sorted(V2_FINAL_TEST_STATES),
        "input_partition_rule": (
            "The full target-plus-donor overlap graph is decomposed into connected "
            "components. Whole components are deterministically assigned to the "
            "calibration subset through an exact subset-sum allocation; remaining "
            "components form evaluation, so no physical input site crosses splits."
        ),
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
