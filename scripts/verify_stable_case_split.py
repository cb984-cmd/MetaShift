"""Verify physical-station disjointness in stable synthetic benchmark splits."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


INPUT_PATH = Path("artifacts/stable_synthetic_cases.csv")
DONORS_PATH = Path("artifacts/stable_synthetic_case_donors.csv")
OUTPUT_PATH = Path("artifacts/stable_synthetic_case_split_audit.json")
SITE_KEYS = ["State Code", "County Code", "Site Num"]


def audit_split(cases: pd.DataFrame, donors: pd.DataFrame) -> dict[str, object]:
    expected_splits = {"calibration", "evaluation"}
    if set(cases["split"]) != expected_splits:
        raise ValueError(f"Expected splits {expected_splits}; found {set(cases['split'])}.")
    duplicated_sites = cases.duplicated(SITE_KEYS, keep=False)
    calibration_sites = set(
        map(tuple, cases.loc[cases["split"] == "calibration", SITE_KEYS].to_numpy())
    )
    evaluation_sites = set(
        map(tuple, cases.loc[cases["split"] == "evaluation", SITE_KEYS].to_numpy())
    )
    shared_sites = calibration_sites.intersection(evaluation_sites)
    donor_required = {
        "case_id",
        "control_state_code",
        "control_county_code",
        "control_site_num",
    }
    missing = donor_required.difference(donors.columns)
    if missing:
        raise ValueError(f"Donor table lacks columns: {sorted(missing)}")
    donor_splits = donors.merge(cases[["case_id", "split"]], on="case_id", how="left")
    if donor_splits["split"].isna().any():
        raise ValueError("Donor table contains case IDs absent from case table.")
    donor_splits["site_key"] = list(
        zip(
            donor_splits["control_state_code"],
            donor_splits["control_county_code"],
            donor_splits["control_site_num"],
            strict=True,
        )
    )
    calibration_donors = set(
        donor_splits.loc[donor_splits["split"] == "calibration", "site_key"]
    )
    evaluation_donors = set(
        donor_splits.loc[donor_splits["split"] == "evaluation", "site_key"]
    )
    calibration_inputs = calibration_sites.union(calibration_donors)
    evaluation_inputs = evaluation_sites.union(evaluation_donors)
    shared_input_sites = calibration_inputs.intersection(evaluation_inputs)
    target_donor_cross_overlap = (
        calibration_sites.intersection(evaluation_donors).union(
            evaluation_sites.intersection(calibration_donors)
        )
    )
    return {
        "calibration_cases": int((cases["split"] == "calibration").sum()),
        "evaluation_cases": int((cases["split"] == "evaluation").sum()),
        "calibration_physical_sites": len(calibration_sites),
        "evaluation_physical_sites": len(evaluation_sites),
        "duplicate_physical_sites_anywhere": int(duplicated_sites.sum()),
        "physical_sites_shared_across_splits": len(shared_sites),
        "calibration_input_physical_sites": len(calibration_inputs),
        "evaluation_input_physical_sites": len(evaluation_inputs),
        "all_input_physical_sites_shared_across_splits": len(shared_input_sites),
        "target_donor_cross_split_overlaps": len(target_donor_cross_overlap),
        "all_input_physical_sites_disjoint": not duplicated_sites.any()
        and not shared_sites
        and not shared_input_sites,
    }


def main() -> None:
    cases = pd.read_csv(INPUT_PATH, dtype="string")
    donors = pd.read_csv(DONORS_PATH, dtype="string")
    payload = audit_split(cases, donors)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["all_input_physical_sites_disjoint"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
