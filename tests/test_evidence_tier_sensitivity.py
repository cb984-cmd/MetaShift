import unittest

import pandas as pd

from scripts.run_evidence_tier_sensitivity import (
    complete_tier_summary,
    condition_flags,
    funnel_summary,
)


class EvidenceTierSensitivityTests(unittest.TestCase):
    def test_q_threshold_varies_with_setting(self) -> None:
        event = pd.Series(
            {
                "audit_status": "complete",
                "quality_gate_passed": True,
                "selection_ci95_lower": -0.1,
                "selection_ci95_upper": 0.2,
                "selection_ci_excludes_zero": True,
                "placebo_status": "complete_100",
                "placebo_count": 100,
                "placebo_p_value": 0.08,
                "placebo_q_value": 0.08,
                "leave_one_donor_out_direction_fraction": 0.9,
            }
        )
        strict = condition_flags(
            event,
            {
                "raw_placebo_p_cutoff": 0.05,
                "bh_q_cutoff": 0.05,
                "donor_direction_fraction_cutoff": 0.95,
            },
            50,
        )
        primary = condition_flags(
            event,
            {
                "raw_placebo_p_cutoff": 0.1,
                "bh_q_cutoff": 0.1,
                "donor_direction_fraction_cutoff": 0.9,
            },
            50,
        )
        self.assertFalse(strict["bh_q_passes"])
        self.assertTrue(primary["bh_q_passes"])

    def test_funnel_reports_sequential_exclusions(self) -> None:
        details = pd.DataFrame(
            {
                "setting": ["primary", "primary"],
                "audit_complete": [True, True],
                "quality_gate_passed": [True, False],
            }
        )
        funnel = funnel_summary(
            details, ["audit_complete", "quality_gate_passed"]
        )
        self.assertEqual([2, 2, 1], funnel["anchor_count"].tolist())
        self.assertEqual([0, 0, 1], funnel["excluded_at_stage"].tolist())

    def test_summary_keeps_zero_count_tiers(self) -> None:
        details = pd.DataFrame(
            {
                "setting": ["strict"],
                "evidence_tier": ["not_supported_by_available_evidence"],
            }
        )
        summary = complete_tier_summary(details, ["strict"])
        self.assertEqual(3, len(summary))
        self.assertEqual(0, int(summary["anchor_count"].min()))
