import unittest

import numpy as np

from metashift.evidence import EvidenceTier, benjamini_hochberg, evidence_tier


class EvidenceTierTests(unittest.TestCase):
    def test_complete_evidence_supports_only_candidate_language(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=True,
            selection_interval_available=True,
            ci_excludes_zero=True,
            placebo_available=True,
            placebo_count=100,
            placebo_p_value=0.1,
            placebo_q_value=0.1,
            donor_sensitivity_available=True,
            donor_direction_fraction=1.0,
        )
        self.assertEqual(tier, EvidenceTier.SUPPORTED_CANDIDATE)
        self.assertEqual(reasons, [])

    def test_missing_placebo_is_inconclusive(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=True,
            selection_interval_available=True,
            ci_excludes_zero=True,
            placebo_available=False,
            placebo_count=0,
            placebo_p_value=None,
            placebo_q_value=None,
            donor_sensitivity_available=True,
            donor_direction_fraction=1.0,
        )
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)
        self.assertIn("time_placebo_insufficient", reasons)

    def test_failed_quality_is_not_supported(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=False,
            selection_interval_available=True,
            ci_excludes_zero=True,
            placebo_available=True,
            placebo_count=100,
            placebo_p_value=0.01,
            placebo_q_value=0.01,
            donor_sensitivity_available=True,
            donor_direction_fraction=1.0,
        )
        self.assertEqual(tier, EvidenceTier.NOT_SUPPORTED)
        self.assertIn("pre_event_quality_gate_failed", reasons)

    def test_benjamini_hochberg_is_monotone_and_preserves_missing_values(self) -> None:
        q_values = benjamini_hochberg([0.01, 0.04, 0.03, float("nan")])
        self.assertAlmostEqual(q_values[0], 0.03)
        self.assertAlmostEqual(q_values[1], 0.04)
        self.assertAlmostEqual(q_values[2], 0.04)
        self.assertTrue(np.isnan(q_values[3]))

    def test_tier_thresholds_change_support_deterministically(self) -> None:
        common = {
            "audit_complete": True,
            "quality_gate_passed": True,
            "selection_interval_available": True,
            "ci_excludes_zero": True,
            "placebo_available": True,
            "placebo_count": 100,
            "placebo_p_value": 0.08,
            "placebo_q_value": 0.08,
            "donor_sensitivity_available": True,
            "donor_direction_fraction": 0.85,
        }
        strict, _ = evidence_tier(
            **common, placebo_cutoff=0.05, donor_stability_cutoff=0.95
        )
        loose, _ = evidence_tier(
            **common, placebo_cutoff=0.20, donor_stability_cutoff=0.80
        )
        self.assertEqual(strict, EvidenceTier.NOT_SUPPORTED)
        self.assertEqual(loose, EvidenceTier.SUPPORTED_CANDIDATE)

    def test_missing_selection_aware_interval_is_inconclusive(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=True,
            selection_interval_available=False,
            ci_excludes_zero=False,
            placebo_available=True,
            placebo_count=100,
            placebo_p_value=0.01,
            placebo_q_value=0.01,
            donor_sensitivity_available=True,
            donor_direction_fraction=1.0,
        )
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)
        self.assertIn("selection_aware_interval_unavailable", reasons)
