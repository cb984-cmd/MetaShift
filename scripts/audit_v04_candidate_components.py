"""Audit metadata-only v0.4 candidate components without loading signal values.

This utility reads only anchor, donor, and already-used input-footprint
identifiers. It deliberately does not open daily observations, evaluate stable
windows, fit weights, or inspect candidate post-window outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

if __package__:
    from .verify_geographic_control_uniqueness import audit_controls
else:
    from verify_geographic_control_uniqueness import audit_controls

TARGET_SITE_COLUMNS = ("State Code", "County Code", "Site Num")
CONTROL_SITE_COLUMNS = (
    "control_state_code",
    "control_county_code",
    "control_site_num",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find metadata-only anchor/donor components disjoint from the "
            "prior stable-benchmark input footprint."
        )
    )
    parser.add_argument(
        "--gate-dir", type=Path, default=Path("artifacts/data_gate")
    )
    parser.add_argument(
        "--cases-path",
        type=Path,
        default=Path("artifacts/stable_synthetic_cases.csv"),
    )
    parser.add_argument(
        "--donors-path",
        type=Path,
        default=Path("artifacts/stable_synthetic_case_donors.csv"),
    )
    parser.add_argument(
        "--minimum-donors",
        type=int,
        default=3,
        help="Minimum distinct physical donors required for an anchor.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/v04_candidate_component_audit.json"),
    )
    return parser.parse_args()


def require_columns(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{name} lacks columns: {sorted(missing)}")


def physical_site_key(row: pd.Series, columns: tuple[str, ...]) -> tuple[str, str, str]:
    values = tuple(row[column] for column in columns)
    if any(pd.isna(value) or not str(value).strip() for value in values):
        raise ValueError(f"Physical-site key has missing values for columns {columns}.")
    return tuple(str(value) for value in values)


def digest_lines(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def audit_candidate_components(
    anchors: pd.DataFrame,
    controls: pd.DataFrame,
    cases: pd.DataFrame,
    donors: pd.DataFrame,
    minimum_donors: int = 3,
) -> dict[str, object]:
    """Return component counts and opaque identities from metadata relationships."""
    if minimum_donors < 1:
        raise ValueError("minimum_donors must be positive.")

    require_columns(
        anchors,
        ("anchor_id", *TARGET_SITE_COLUMNS, "geographic_control_count"),
        "anchor inventory",
    )
    require_columns(
        controls, ("anchor_id", *CONTROL_SITE_COLUMNS), "geographic controls"
    )
    require_columns(cases, TARGET_SITE_COLUMNS, "stable synthetic cases")
    require_columns(donors, CONTROL_SITE_COLUMNS, "stable synthetic donors")

    uniqueness = audit_controls(anchors, controls)
    if not uniqueness["all_geographic_controls_are_distinct_physical_sites"]:
        raise ValueError("Geographic controls fail the distinct-physical-site audit.")

    donor_counts = pd.to_numeric(
        anchors["geographic_control_count"], errors="raise"
    )
    eligible = anchors.loc[donor_counts >= minimum_donors].copy()
    eligible_ids = eligible["anchor_id"].astype(str).tolist()
    if len(eligible_ids) != len(set(eligible_ids)):
        raise ValueError("Anchor inventory contains duplicate anchor IDs.")
    if not eligible_ids:
        raise ValueError("No anchors meet the requested donor threshold.")

    parent = {anchor_id: anchor_id for anchor_id in eligible_ids}

    def find(anchor_id: str) -> str:
        while parent[anchor_id] != anchor_id:
            parent[anchor_id] = parent[parent[anchor_id]]
            anchor_id = parent[anchor_id]
        return anchor_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    site_to_anchors: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    anchor_to_sites: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    anchor_to_target_site: dict[str, tuple[str, str, str]] = {}
    for _, row in eligible.iterrows():
        anchor_id = str(row["anchor_id"])
        site = physical_site_key(row, TARGET_SITE_COLUMNS)
        site_to_anchors[site].append(anchor_id)
        anchor_to_sites[anchor_id].add(site)
        anchor_to_target_site[anchor_id] = site

    eligible_controls = controls.loc[
        controls["anchor_id"].astype(str).isin(eligible_ids)
    ].copy()
    actual_counts = eligible_controls.groupby("anchor_id").size()
    for _, row in eligible.iterrows():
        anchor_id = str(row["anchor_id"])
        expected_count = int(row["geographic_control_count"])
        if int(actual_counts.get(anchor_id, 0)) != expected_count:
            raise ValueError(
                f"Anchor {anchor_id} has inconsistent geographic-control metadata."
            )
    for _, row in eligible_controls.iterrows():
        anchor_id = str(row["anchor_id"])
        site = physical_site_key(row, CONTROL_SITE_COLUMNS)
        site_to_anchors[site].append(anchor_id)
        anchor_to_sites[anchor_id].add(site)

    for linked_anchors in site_to_anchors.values():
        for anchor_id in linked_anchors[1:]:
            union(linked_anchors[0], anchor_id)

    components: dict[str, list[str]] = defaultdict(list)
    for anchor_id in eligible_ids:
        components[find(anchor_id)].append(anchor_id)

    prior_input_sites = {
        physical_site_key(row, TARGET_SITE_COLUMNS) for _, row in cases.iterrows()
    }
    prior_input_sites.update(
        physical_site_key(row, CONTROL_SITE_COLUMNS) for _, row in donors.iterrows()
    )

    rows: list[dict[str, object]] = []
    available_anchor_count = 0
    available_site_count = 0
    available_target_sites: set[tuple[str, str, str]] = set()
    for index, anchor_ids in enumerate(
        sorted((sorted(ids) for ids in components.values()), key=lambda ids: tuple(ids)),
        start=1,
    ):
        component_sites = set().union(
            *(anchor_to_sites[anchor_id] for anchor_id in anchor_ids)
        )
        component_target_sites = {
            anchor_to_target_site[anchor_id] for anchor_id in anchor_ids
        }
        overlaps_prior_input = bool(component_sites.intersection(prior_input_sites))
        if not overlaps_prior_input:
            available_anchor_count += len(anchor_ids)
            available_site_count += len(component_sites)
            available_target_sites.update(component_target_sites)
        rows.append(
            {
                "component_id": f"metadata-component-{index:03d}",
                "anchor_count": len(anchor_ids),
                "physical_site_count": len(component_sites),
                "target_physical_site_count": len(component_target_sites),
                "anchor_id_sha256": digest_lines(anchor_ids),
                "physical_site_sha256": digest_lines(
                    ["-".join(site) for site in sorted(component_sites)]
                ),
                "overlaps_prior_stable_input_footprint": overlaps_prior_input,
            }
        )

    available_components = [
        row for row in rows if not row["overlaps_prior_stable_input_footprint"]
    ]
    if sum(int(row["anchor_count"]) for row in rows) != len(eligible_ids):
        raise RuntimeError("Component accounting did not preserve all eligible anchors.")

    return {
        "schema_version": 1,
        "scope": (
            "Metadata-only physical-site graph audit; no signal values, "
            "post-window outcomes, scores, or fitted models are read."
        ),
        "minimum_distinct_physical_donors": minimum_donors,
        "eligible_anchor_count": len(eligible_ids),
        "prior_stable_input_physical_site_count": len(prior_input_sites),
        "component_count": len(rows),
        "components_disjoint_from_prior_stable_input": len(available_components),
        "anchors_in_disjoint_components": available_anchor_count,
        "physical_sites_in_disjoint_components": available_site_count,
        "target_physical_sites_in_disjoint_components": len(available_target_sites),
        "all_eligible_anchors_accounted_for": True,
        "components": rows,
    }


def main() -> None:
    args = parse_args()
    anchors = pd.read_csv(args.gate_dir / "anchor_inventory.csv", dtype="string")
    controls = pd.read_csv(args.gate_dir / "geographic_controls.csv", dtype="string")
    cases = pd.read_csv(args.cases_path, dtype="string")
    donors = pd.read_csv(args.donors_path, dtype="string")
    report = audit_candidate_components(
        anchors, controls, cases, donors, args.minimum_donors
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
