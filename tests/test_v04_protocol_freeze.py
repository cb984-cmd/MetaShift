import unittest

from scripts import verify_v04_protocol_freeze as verifier


class ProtocolFreezeTests(unittest.TestCase):
    def test_pre_outcome_protocol_is_complete_and_has_no_result_files(self) -> None:
        report = verifier.build_report()

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(11, len(report["checks"]))
        self.assertEqual(64, len(report["protocol_sha256"]))


if __name__ == "__main__":
    unittest.main()
