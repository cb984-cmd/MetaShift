from pathlib import Path
import tempfile
import unittest

from scripts import verify_v04_protocol_freeze as verifier


class ProtocolFreezeTests(unittest.TestCase):
    def test_pre_outcome_protocol_contract_remains_complete_after_output(self) -> None:
        report = verifier.build_report(require_no_outputs=False)

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(11, len(report["checks"]))
        self.assertEqual(64, len(report["protocol_sha256"]))

    def test_declared_output_predicate_isolated_from_historical_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "outputs"

            self.assertFalse(
                verifier.no_declared_output_exists(output, ["results.json"])
            )
            output.mkdir()
            (output / "results.json").write_text("{}", encoding="utf-8")
            self.assertTrue(
                verifier.no_declared_output_exists(output, ["results.json"])
            )


if __name__ == "__main__":
    unittest.main()
