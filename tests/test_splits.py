import tempfile
import unittest
from pathlib import Path

import pandas as pd

from metashift.splits import append_access_log, final_test_events, split_sha256


class SplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = pd.DataFrame(
            {
                "State Code": ["06", "17", "25", "17"],
                "anchor_id": ["california", "illinois-a", "massachusetts", "illinois-b"],
            }
        )

    def test_final_test_targets_are_state_disjoint(self) -> None:
        selected = final_test_events(self.events)
        self.assertEqual(set(selected["State Code"]), {"17", "25"})
        self.assertEqual(len(selected), 3)

    def test_split_hash_is_order_invariant(self) -> None:
        self.assertEqual(
            split_sha256(self.events),
            split_sha256(self.events.sample(frac=1, random_state=4)),
        )

    def test_access_log_appends_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "access.jsonl"
            append_access_log(
                log,
                action="test",
                purpose="unit test",
                split_hash="abc",
                event_count=3,
            )
            self.assertIn('"action": "test"', log.read_text(encoding="utf-8"))
