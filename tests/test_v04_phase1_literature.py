import unittest

from scripts import verify_v04_phase1_literature as verifier


class PhaseOneLiteratureTests(unittest.TestCase):
    def test_phase_one_audit_is_complete_and_bounded(self) -> None:
        report = verifier.build_report()

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(6, len(report["checks"]))


if __name__ == "__main__":
    unittest.main()
