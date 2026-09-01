from pathlib import Path
import tempfile
import unittest

from scripts import verify_v04_execution_freeze as verifier


class ExecutionFreezeTests(unittest.TestCase):
    def test_execution_freeze_verifier_rejects_post_execution_source_evolution(self) -> None:
        report = verifier.build_report(require_no_outputs=False)

        self.assertFalse(report["all_checks_passed"])
        self.assertEqual(11, len(report["checks"]))
        self.assertFalse(
            next(
                item["passed"]
                for item in report["checks"]
                if item["name"] == "all_nonself_inputs_are_hashed"
            )
        )
        self.assertTrue(
            next(
                item["passed"]
                for item in report["checks"]
                if item["name"] == "execution_path_cannot_bypass_preconditions"
            )
        )
        self.assertEqual(64, len(report["protocol_sha256"]))
        self.assertEqual(64, len(report["execution_manifest_sha256"]))

    def test_no_output_predicate_isolated_from_historical_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "outputs"
            attempt = root / "attempt.json"

            self.assertTrue(verifier.no_outputs_before_execution(output, attempt))
            output.mkdir()
            self.assertFalse(verifier.no_outputs_before_execution(output, attempt))


if __name__ == "__main__":
    unittest.main()
