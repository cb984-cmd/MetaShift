import unittest
from pathlib import Path

from scripts.export_complete_public_archive import (
    credential_pattern_name,
    is_safe_relative_output_path,
)


class CompletePublicArchiveTests(unittest.TestCase):
    def test_accepts_safe_generated_outputs(self) -> None:
        self.assertTrue(
            is_safe_relative_output_path(
                Path("artifacts") / "real_transition_88101_event_audit.csv"
            )
        )
        self.assertTrue(
            is_safe_relative_output_path(Path("figures") / "figure_2_summary.png")
        )

    def test_rejects_raw_and_virtual_environment_paths(self) -> None:
        self.assertFalse(
            is_safe_relative_output_path(Path("data") / "raw" / "daily_88101_2025.zip")
        )
        self.assertFalse(
            is_safe_relative_output_path(
                Path("artifacts") / "aqs_qa" / "response.json"
            )
        )
        self.assertFalse(
            is_safe_relative_output_path(
                Path("artifacts") / "metashift-repro-venv" / "package.py"
            )
        )

    def test_detects_credential_like_content(self) -> None:
        self.assertEqual(
            "github_token", credential_pattern_name(b"token=ghp_12345678901234567890")
        )
        self.assertEqual(
            "aqs_credential_assignment",
            credential_pattern_name(b'AQS_API_KEY = "not-for-publication"'),
        )
        self.assertIsNone(credential_pattern_name(b"safe, public result table"))
