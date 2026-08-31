import unittest

import pandas as pd

from scripts.run_effect_window_sensitivity import method_window_reason


class EffectWindowSensitivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor_date = pd.Timestamp("2024-01-06")
        index = pd.date_range("2024-01-01", periods=10, freq="D")
        self.target = pd.DataFrame(
            {
                "Arithmetic Mean": range(10),
                "Method Code": ["old"] * 5 + ["new"] * 5,
            },
            index=index,
        )
        self.donor = pd.DataFrame(
            {
                "Arithmetic Mean": range(10),
                "Method Code": ["control"] * 10,
            },
            index=index,
        )
        self.event = pd.Series(
            {
                "State Code": "01",
                "County Code": "001",
                "Site Num": "0001",
                "POC": "1",
                "previous_method_code": "old",
                "method_code": "new",
            }
        )
        self.metadata = pd.DataFrame(
            {
                "control_state_code": ["01"],
                "control_county_code": ["001"],
                "control_site_num": ["0002"],
                "control_poc": ["1"],
            }
        )
        self.records = {
            ("01", "001", "0001", "1"): self.target,
            ("01", "001", "0002", "1"): self.donor,
        }

    def test_accepts_stable_target_and_donor_windows(self) -> None:
        self.assertIsNone(
            method_window_reason(
                self.event,
                self.metadata,
                self.records,
                self.anchor_date,
                window=2,
                minimum_observations=2,
            )
        )

    def test_rejects_donor_method_change_within_window(self) -> None:
        self.donor.loc[pd.Timestamp("2024-01-07"), "Method Code"] = "changed"
        reason = method_window_reason(
            self.event,
            self.metadata,
            self.records,
            self.anchor_date,
            window=2,
            minimum_observations=2,
        )
