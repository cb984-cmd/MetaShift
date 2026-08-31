import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts import build_stable_synthetic_cases, verify_stable_case_split


class StableCaseSplitTests(unittest.TestCase):
    def test_disjoint_physical_sites_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cases.csv"
            output = root / "audit.json"
            pd.DataFrame(
                {
                    "case_id": ["0", "1"],
                    "State Code": ["01", "02"],
                    "County Code": ["001", "002"],
                    "Site Num": ["0001", "0002"],
                    "POC": ["1", "1"],
                    "split": ["calibration", "evaluation"],
                }
            ).to_csv(source, index=False)
            donors = pd.DataFrame(
                {
                    "case_id": ["0", "1"],
                    "control_state_code": ["01", "02"],
                    "control_county_code": ["003", "004"],
                    "control_site_num": ["0003", "0004"],
                }
            )
            cases = pd.read_csv(source, dtype="string")
            audit = verify_stable_case_split.audit_split(cases, donors)
            self.assertTrue(audit["all_input_physical_sites_disjoint"])

    def test_cross_split_donor_overlap_fails(self) -> None:
        cases = pd.DataFrame(
            {
                "case_id": ["a", "b"],
                "State Code": ["01", "02"],
                "County Code": ["001", "002"],
                "Site Num": ["0001", "0002"],
                "POC": ["1", "1"],
                "split": ["calibration", "evaluation"],
            }
        )
        donors = pd.DataFrame(
            {
                "case_id": ["a", "b"],
                "control_state_code": ["01", "01"],
                "control_county_code": ["003", "003"],
                "control_site_num": ["0003", "0003"],
            }
        )
        audit = verify_stable_case_split.audit_split(cases, donors)
        self.assertFalse(audit["all_input_physical_sites_disjoint"])

    def test_duplicate_donor_physical_site_within_case_fails(self) -> None:
        cases = pd.DataFrame(
            {
                "case_id": ["a", "b"],
                "State Code": ["01", "02"],
                "County Code": ["001", "002"],
                "Site Num": ["0001", "0002"],
                "POC": ["1", "1"],
                "split": ["calibration", "evaluation"],
            }
        )
        donors = pd.DataFrame(
            {
                "case_id": ["a", "a", "b"],
                "control_state_code": ["01", "01", "02"],
                "control_county_code": ["003", "003", "004"],
                "control_site_num": ["0003", "0003", "0004"],
            }
        )
        audit = verify_stable_case_split.audit_split(cases, donors)
        self.assertEqual(2, audit["duplicate_physical_donors_within_case"])
        self.assertFalse(audit["all_input_physical_sites_disjoint"])

    def test_component_allocator_preserves_full_input_isolation(self) -> None:
        cases = pd.DataFrame(
            {
                "case_id": ["a", "b", "c", "d"],
                "State Code": ["01", "02", "03", "04"],
                "County Code": ["001", "002", "003", "004"],
                "Site Num": ["0001", "0002", "0003", "0004"],
                "POC": ["1", "1", "1", "1"],
            }
        )
        donors = pd.DataFrame(
            {
                "case_id": ["a", "b", "c", "d"],
                "control_state_code": ["10", "10", "11", "11"],
                "control_county_code": ["010", "010", "011", "011"],
                "control_site_num": ["0010", "0010", "0011", "0011"],
            }
        )
        assigned = build_stable_synthetic_cases.assign_input_disjoint_splits(
            cases, donors, calibration_case_count=2
        )
        audit = verify_stable_case_split.audit_split(assigned, donors)
        self.assertEqual(2, int((assigned["split"] == "calibration").sum()))
        self.assertTrue(audit["all_input_physical_sites_disjoint"])
