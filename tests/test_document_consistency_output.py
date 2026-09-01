import unittest

from scripts import verify_public_document_consistency as verifier


class DocumentConsistencyOutputTests(unittest.TestCase):
    def test_historical_draft_is_excluded_from_active_release_checks(self) -> None:
        historical_draft = verifier.ROOT / "paper" / "MANUSCRIPT_DRAFT.md"

        self.assertIn(historical_draft, verifier.HISTORICAL_DOCUMENTS)
        self.assertNotIn(historical_draft, verifier.ACTIVE_PUBLIC_DOCUMENTS)
        self.assertNotIn(historical_draft, verifier.CURRENT_RELEASE_DOCUMENTS)
        self.assertNotIn(historical_draft, verifier.EXTERNAL_REVIEW_DOCUMENTS)
        self.assertNotIn(historical_draft, verifier.V2_PATH_FILES)
        self.assertNotIn(historical_draft, verifier.STALE_COUNT_FILES)

    def test_default_output_does_not_overwrite_frozen_release_evidence(self) -> None:
        self.assertEqual(
            verifier.DEFAULT_OUTPUT_PATH,
            verifier.ROOT / "artifacts" / "document_consistency_ci.json",
        )
        self.assertNotEqual(verifier.DEFAULT_OUTPUT_PATH, verifier.FROZEN_RESULTS_PATH)
