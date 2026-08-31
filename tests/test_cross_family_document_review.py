import unittest

import pandas as pd

from scripts.select_cross_family_document_review import select_round_robin


class CrossFamilyDocumentReviewTests(unittest.TestCase):
    def test_selects_round_robin_across_pairs(self) -> None:
        candidates = pd.DataFrame(
            {
                "anchor_id": ["a1", "a2", "a3", "b1", "b2"],
                "previous_method_code": ["1", "1", "1", "2", "2"],
                "method_code": ["3", "3", "3", "4", "4"],
            }
        )
        selected = select_round_robin(candidates, 3)
        self.assertEqual(3, len(selected))
        self.assertEqual(2, selected["transition_pair"].nunique())
        self.assertEqual([1, 2, 3], selected["selection_rank"].tolist())

    def test_rejects_oversized_sample(self) -> None:
        candidates = pd.DataFrame(
            {
                "anchor_id": ["a1"],
                "previous_method_code": ["1"],
                "method_code": ["2"],
            }
        )
        with self.assertRaisesRegex(ValueError, "Only 1 eligible"):
            select_round_robin(candidates, 2)
