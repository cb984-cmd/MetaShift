import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_hourly_poc_validation import current_response_reason


class HourlyPocFreshnessTests(unittest.TestCase):
    def test_accepts_current_hashed_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "response.json"
            raw_path.write_text('{"Data": []}', encoding="utf-8")
            manifest_entry = {
                "request_succeeded": True,
                "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            }
            self.assertIsNone(current_response_reason(manifest_entry, raw_path))

    def test_rejects_stale_or_failed_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "response.json"
            raw_path.write_text('{"Data": []}', encoding="utf-8")
            self.assertIsNotNone(
                current_response_reason({"request_succeeded": False}, raw_path)
            )
            self.assertIsNotNone(
                current_response_reason(
                    {"request_succeeded": True, "raw_sha256": "not-a-real-hash"},
                    raw_path,
                )
            )
