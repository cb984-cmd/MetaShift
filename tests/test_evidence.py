import unittest

from metashift.evidence import EvidenceTier, evidence_tier


class EvidenceTierTests(unittest.TestCase):
    def test_complete_evidence_supports_only_candidate_language(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=True,
            ci_excludes_zero=True,
            placebo_available=True,
            placebo_p_value=0.1,
            donor_sensitivity_available=True,
            donor_direction_stable=True,
        )
        self.assertEqual(tier, EvidenceTier.SUPPORTED_CANDIDATE)
        self.assertEqual(reasons, [])

    def test_missing_placebo_is_inconclusive(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=True,
            ci_excludes_zero=True,
            placebo_available=False,
            placebo_p_value=None,
            donor_sensitivity_available=True,
            donor_direction_stable=True,
        )
        self.assertEqual(tier, EvidenceTier.INCONCLUSIVE)
        self.assertIn("time_placebo_unavailable", reasons)

    def test_failed_quality_is_not_supported(self) -> None:
        tier, reasons = evidence_tier(
            audit_complete=True,
            quality_gate_passed=False,
            ci_excludes_zero=True,
            placebo_available=True,
            placebo_p_value=0.01,
            donor_sensitivity_available=True,
            donor_direction_stable=True,
        )
        self.assertEqual(tier, EvidenceTier.NOT_SUPPORTED)
        self.assertIn("pre_event_quality_gate_failed", reasons)
