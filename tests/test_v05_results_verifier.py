import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from scripts import verify_v05_answerability_results as verifier


class V05ResultVerifierTests(unittest.TestCase):
    def test_strict_schema_rejects_missing_column(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "result.csv"
            pd.DataFrame({"first": [1]}).to_csv(path, index=False)

            with self.assertRaisesRegex(ValueError, "schema differs"):
                verifier._read_csv_strict(path, ["first", "second"])

    def test_deterministic_comparison_rejects_tampered_numeric_payload(self) -> None:
        expected = pd.DataFrame({"value": [0.1, 0.2], "name": ["a", "b"]})
        actual = expected.copy()
        actual.loc[1, "value"] = 0.3

        with self.assertRaisesRegex(ValueError, "numeric column differs"):
            verifier._assert_frame_equivalent(actual, expected, "test")

    def test_receipt_hash_validation_rejects_tampered_payload(self) -> None:
        protocol = {
            "output_contract": {
                "files": ["payload.csv", "v05_execution_receipt.json"]
            }
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            payload = directory / "payload.csv"
            receipt_path = directory / "v05_execution_receipt.json"
            payload.write_text("value\n1\n", encoding="utf-8")
            receipt_path.write_text("{}", encoding="utf-8")
            paths = {
                "payload.csv": payload,
                "v05_execution_receipt.json": receipt_path,
            }
            receipt = {
                "output_hashes": {
                    "payload.csv": {
                        "sha256": "0" * 64,
                        "bytes": payload.stat().st_size,
                    }
                }
            }

            with patch.object(verifier, "_paths", return_value=paths):
                with self.assertRaisesRegex(ValueError, "hash differs"):
                    verifier._validate_receipt_hashes(protocol, receipt)

    def test_policy_json_replay_rejects_evaluation_selection_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "protocol_id": "v0.5-answerability-frontier",
                        "selection_split": "evaluation",
                        "comparative_scope_threshold": 0.0,
                        "confidence_cutoffs": {},
                    }
                ),
                encoding="utf-8",
            )
            calibration = pd.DataFrame(
                {
                    "split": ["calibration"],
                    "local_score": [0.1],
                    "shared_score": [0.0],
                }
            )
            protocol = {
                "protocol_id": "v0.5-answerability-frontier",
                "calibration_and_evaluation": {"cutoff_quantiles": {"count": 2}},
            }

            with self.assertRaisesRegex(ValueError, "calibration-only"):
                verifier._validate_policy_json(path, calibration, protocol)


if __name__ == "__main__":
    unittest.main()
