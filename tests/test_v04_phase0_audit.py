import unittest

import pandas as pd

from scripts.audit_v04_candidate_components import audit_candidate_components
from scripts import verify_v04_phase0_audit as verifier


class CandidateComponentAuditTests(unittest.TestCase):
    def test_component_audit_separates_prior_input_footprints(self) -> None:
        anchors = pd.DataFrame(
            {
                "anchor_id": ["a", "b", "c"],
                "State Code": ["01", "01", "02"],
                "County Code": ["001", "001", "001"],
                "Site Num": ["0001", "0002", "0001"],
                "geographic_control_count": [3, 3, 3],
            }
        )
        controls = pd.DataFrame(
            {
                "anchor_id": [
                    "a",
                    "a",
                    "a",
                    "b",
                    "b",
                    "b",
                    "c",
                    "c",
                    "c",
                ],
                "control_state_code": [
                    "90",
                    "90",
                    "90",
                    "90",
                    "90",
                    "90",
                    "91",
                    "91",
                    "91",
                ],
                "control_county_code": [
                    "001",
                    "001",
                    "001",
                    "001",
                    "002",
                    "003",
                    "001",
                    "002",
                    "003",
                ],
                "control_site_num": [
                    "0001",
                    "0002",
                    "0003",
                    "0001",
                    "0002",
                    "0003",
                    "0001",
                    "0002",
                    "0003",
                ],
                "control_poc": ["1"] * 9,
            }
        )
        cases = pd.DataFrame(
            {
                "State Code": ["01"],
                "County Code": ["001"],
                "Site Num": ["0001"],
            }
        )
        donors = pd.DataFrame(
            {
                "control_state_code": ["80"],
                "control_county_code": ["001"],
                "control_site_num": ["0001"],
            }
        )

        report = audit_candidate_components(anchors, controls, cases, donors)

        self.assertEqual(3, report["eligible_anchor_count"])
        self.assertEqual(2, report["component_count"])
        self.assertEqual(1, report["components_disjoint_from_prior_stable_input"])
        self.assertEqual(1, report["anchors_in_disjoint_components"])
        self.assertTrue(report["all_eligible_anchors_accounted_for"])


class PhaseZeroTrackedChecksTests(unittest.TestCase):
    def test_tracked_phase_zero_checks_pass(self) -> None:
        report = verifier.build_report()

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(4, len(report["checks"]))


if __name__ == "__main__":
    unittest.main()
