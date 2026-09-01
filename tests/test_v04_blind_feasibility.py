import unittest

import pandas as pd

from scripts.audit_v04_blind_feasibility import cluster_power_design


class BlindFeasibilityTests(unittest.TestCase):
    def test_six_component_design_reports_limited_precision(self) -> None:
        report = cluster_power_design(6)

        self.assertEqual(6, report["nonoverlapping_metadata_component_count"])
        self.assertEqual(
            "not_established_by_physical-footprint separation",
            report["independence_status"],
        )
        self.assertAlmostEqual(
            1.434544782040,
            float(report["paired_t_standardized_mde_at_80_percent_power"]),
            places=10,
        )
        self.assertAlmostEqual(
            0.03125,
            float(report["two_sided_sign_test_minimum_p_at_all_same_direction"]),
        )
        self.assertAlmostEqual(
            0.262208,
            float(report["two_sided_sign_test_power_by_direction_probability"]["0.80"]),
        )

    def test_one_component_design_refuses_precision_claim(self) -> None:
        report = cluster_power_design(1)

        self.assertEqual(1, report["nonoverlapping_metadata_component_count"])
        self.assertEqual(
            "insufficient_for_paired_cluster_precision", report["status"]
        )


if __name__ == "__main__":
    unittest.main()
