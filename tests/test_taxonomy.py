import unittest

import pandas as pd

from metashift.taxonomy import (
    observed_transition_pairs,
    validate_transition_taxonomy,
)


def sample_anchors() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "previous_method_code": ["101", "101", "201"],
            "previous_method_name": ["Old A", "Old A", "Old B"],
            "method_code": ["102", "102", "202"],
            "method_name": ["New A", "New A", "New B"],
        }
    )


def sample_taxonomy() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "old_method_code": ["101", "201"],
            "old_method_name": ["Old A", "Old B"],
            "new_method_code": ["102", "202"],
            "new_method_name": ["New A", "New B"],
            "old_analyzer_family": ["A", "B"],
            "new_analyzer_family": ["A", "C"],
            "transition_class": [
                "same_analyzer_configuration",
                "cross_analyzer_family",
            ],
            "nda_related": ["false", "false"],
            "same_hardware_family": ["true", "false"],
            "classification_basis": ["Metadata-only", "Metadata-only"],
            "official_source": ["AQS Method Code", "AQS Method Code"],
            "review_status": ["pending_human_review", "pending_human_review"],
        }
    )


class TransitionTaxonomyTests(unittest.TestCase):
    def test_accepts_exact_metadata_pair_coverage(self) -> None:
        validated = validate_transition_taxonomy(
            sample_taxonomy(), observed_transition_pairs(sample_anchors())
        )
        self.assertEqual(2, len(validated))

    def test_rejects_missing_transition_pair(self) -> None:
        taxonomy = sample_taxonomy().iloc[:1]
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            validate_transition_taxonomy(
                taxonomy, observed_transition_pairs(sample_anchors())
            )

    def test_rejects_invalid_class(self) -> None:
        taxonomy = sample_taxonomy()
        taxonomy.loc[0, "transition_class"] = "confirmed_instrument_change"
        with self.assertRaisesRegex(ValueError, "invalid transition classes"):
            validate_transition_taxonomy(
                taxonomy, observed_transition_pairs(sample_anchors())
            )
