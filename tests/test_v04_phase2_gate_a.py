import unittest

from scripts import verify_v04_phase2_gate_a as verifier


class PhaseTwoGateATests(unittest.TestCase):
    def test_tracked_gate_a_contract_is_complete_and_bounded(self) -> None:
        report = verifier.build_report()

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(8, len(report["checks"]))


if __name__ == "__main__":
    unittest.main()
