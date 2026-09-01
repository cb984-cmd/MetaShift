import unittest

from scripts import verify_public_document_consistency as verifier


class DocumentConsistencyOutputTests(unittest.TestCase):
    def test_default_output_does_not_overwrite_frozen_release_evidence(self) -> None:
        self.assertEqual(
            verifier.DEFAULT_OUTPUT_PATH,
            verifier.ROOT / "artifacts" / "document_consistency_ci.json",
        )
        self.assertNotEqual(verifier.DEFAULT_OUTPUT_PATH, verifier.FROZEN_RESULTS_PATH)
