import unittest

from scripts import verify_v04_execution_freeze as verifier


class ExecutionFreezeTests(unittest.TestCase):
    def test_execution_freeze_candidate_is_fully_bound_and_output_free(self) -> None:
        report = verifier.build_report()

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(9, len(report["checks"]))
        self.assertTrue(
            next(
                item["passed"]
                for item in report["checks"]
                if item["name"] == "execution_path_cannot_bypass_preconditions"
            )
        )
        self.assertEqual(64, len(report["protocol_sha256"]))
        self.assertEqual(64, len(report["execution_manifest_sha256"]))


if __name__ == "__main__":
    unittest.main()
