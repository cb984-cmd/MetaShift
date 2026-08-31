import unittest

import pandas as pd

from scripts.scan_data_gate import rank_distinct_physical_controls
from scripts.verify_geographic_control_uniqueness import audit_controls


class GeographicControlUniquenessTests(unittest.TestCase):
    def test_selects_one_best_poc_per_physical_site(self) -> None:
        controls = [
            {
                "control_state_code": "01",
                "control_county_code": "001",
                "control_site_num": "0001",
                "control_poc": "2",
                "distance_km": 5.0,
                "pre_transition_paired_days": 100,
                "pre_transition_log_correlation": 0.9,
            },
            {
                "control_state_code": "01",
                "control_county_code": "001",
                "control_site_num": "0001",
                "control_poc": "1",
                "distance_km": 5.0,
                "pre_transition_paired_days": 110,
                "pre_transition_log_correlation": 0.9,
            },
            {
                "control_state_code": "01",
                "control_county_code": "003",
                "control_site_num": "0001",
                "control_poc": "1",
                "distance_km": 10.0,
                "pre_transition_paired_days": 100,
                "pre_transition_log_correlation": 0.8,
            },
        ]
        selected = rank_distinct_physical_controls(controls)
        self.assertEqual(2, len(selected))
        self.assertEqual("1", selected[0]["control_poc"])

    def test_audit_rejects_duplicate_physical_donors(self) -> None:
        anchors = pd.DataFrame(
            {
                "anchor_id": ["a"],
                "State Code": ["01"],
                "County Code": ["001"],
                "Site Num": ["0001"],
                "geographic_control_count": [2],
            }
        )
        controls = pd.DataFrame(
            {
                "anchor_id": ["a", "a"],
                "control_state_code": ["01", "01"],
                "control_county_code": ["003", "003"],
                "control_site_num": ["0001", "0001"],
                "control_poc": ["1", "2"],
            }
        )
        audit = audit_controls(anchors, controls)
        self.assertFalse(audit["all_geographic_controls_are_distinct_physical_sites"])
        self.assertEqual(1, audit["duplicate_physical_donor_rows"])
