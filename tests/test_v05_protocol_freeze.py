import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify_v05_protocol_freeze as verifier


ROOT = Path(__file__).resolve().parents[1]


class V05ProtocolFreezeTests(unittest.TestCase):
    def test_pre_outcome_contract_is_complete_without_outputs(self) -> None:
        report = verifier.build_report(require_no_outputs=True)

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(16, len(report["checks"]))
        self.assertEqual(64, len(report["protocol_sha256"]))

    def test_declared_output_predicate_detects_directory_or_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"

            self.assertFalse(verifier.no_declared_output_exists(output, ["x.csv"]))
            output.mkdir()
            self.assertTrue(verifier.no_declared_output_exists(output, ["x.csv"]))
            output.rmdir()
            attempt = root / "attempt.json"
            attempt.write_text("{}", encoding="utf-8")
            self.assertTrue(
                verifier.no_declared_output_exists(output, ["x.csv"], attempt)
            )

    def test_grid_contract_rejects_omitted_factor_level(self) -> None:
        protocol = json.loads(
            (ROOT / "configs" / "v05_answerability_protocol.json").read_text(
                encoding="utf-8"
            )
        )
        damaged = copy.deepcopy(protocol)
        damaged["full_cartesian_grid"]["signal_h"].pop()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "damaged_protocol.json"
            path.write_text(json.dumps(damaged), encoding="utf-8")
            with patch.object(verifier, "PROTOCOL_PATH", path):
                report = verifier.build_report(require_no_outputs=True)

        grid_check = next(
            item for item in report["checks"] if item["name"] == "complete_cartesian_grid"
        )
        self.assertFalse(grid_check["passed"])
        self.assertFalse(report["all_checks_passed"])

    def test_source_allowlist_rejects_external_footprint_paths(self) -> None:
        protocol = json.loads(
            (ROOT / "configs" / "v05_answerability_protocol.json").read_text(
                encoding="utf-8"
            )
        )
        allowed = protocol["data_access"]["execution_input_allowlist"]

        self.assertFalse(
            any(
                str(path).startswith(("data/", "artifacts/", "results/"))
                for path in allowed
            )
        )


if __name__ == "__main__":
    unittest.main()
