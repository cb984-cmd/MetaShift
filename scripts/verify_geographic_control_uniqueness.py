"""Verify that geographic donor inventories are unique by physical site."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit physical-site uniqueness of geographic controls."
    )
    parser.add_argument("--gate-dir", type=Path, default=Path("artifacts/data_gate"))
    return parser.parse_args()


def audit_controls(anchors: pd.DataFrame, controls: pd.DataFrame) -> dict[str, object]:
    """Check counts, donor-site uniqueness, and target/donor physical separation."""

    required_anchor = {
        "anchor_id",
        "State Code",
        "County Code",
        "Site Num",
        "geographic_control_count",
    }
    required_control = {
        "anchor_id",
        "control_state_code",
        "control_county_code",
        "control_site_num",
        "control_poc",
    }
    missing = required_anchor.difference(anchors.columns).union(
        required_control.difference(controls.columns)
    )
    if missing:
        raise ValueError(f"Control inventory lacks columns: {sorted(missing)}")
    duplicate_physical = controls.duplicated(
        [
            "anchor_id",
            "control_state_code",
            "control_county_code",
            "control_site_num",
        ]
    )
    counts = controls.groupby("anchor_id").size().rename("actual_control_count")
    comparison = anchors.loc[:, ["anchor_id", "geographic_control_count"]].merge(
        counts, on="anchor_id", how="left", validate="one_to_one"
    )
    comparison["actual_control_count"] = comparison["actual_control_count"].fillna(0)
    comparison["geographic_control_count"] = pd.to_numeric(
        comparison["geographic_control_count"], errors="raise"
    )
    count_mismatches = comparison[
        "geographic_control_count"
    ].ne(comparison["actual_control_count"])
    targets = anchors.loc[
        :, ["anchor_id", "State Code", "County Code", "Site Num"]
    ].rename(
        columns={
            "State Code": "target_state_code",
            "County Code": "target_county_code",
            "Site Num": "target_site_num",
        }
    )
    donor_targets = controls.merge(targets, on="anchor_id", how="left", validate="many_to_one")
    donor_matches_target = (
        donor_targets["control_state_code"].eq(donor_targets["target_state_code"])
        & donor_targets["control_county_code"].eq(
            donor_targets["target_county_code"]
        )
        & donor_targets["control_site_num"].eq(donor_targets["target_site_num"])
    )
    return {
        "anchor_count": len(anchors),
        "geographic_control_rows": len(controls),
        "anchors_with_controls": int((comparison["actual_control_count"] > 0).sum()),
        "duplicate_physical_donor_rows": int(duplicate_physical.sum()),
        "anchor_count_mismatches": int(count_mismatches.sum()),
        "donors_matching_target_physical_site": int(donor_matches_target.sum()),
        "all_geographic_controls_are_distinct_physical_sites": (
            not duplicate_physical.any()
            and not count_mismatches.any()
            and not donor_matches_target.any()
        ),
    }


def main() -> None:
    args = parse_args()
    anchors = pd.read_csv(args.gate_dir / "anchor_inventory.csv", dtype="string")
    controls = pd.read_csv(args.gate_dir / "geographic_controls.csv", dtype="string")
    audit = audit_controls(anchors, controls)
    output_path = args.gate_dir / "geographic_control_physical_site_audit.json"
    output_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    if not audit["all_geographic_controls_are_distinct_physical_sites"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
