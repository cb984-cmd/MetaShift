import unittest

import numpy as np

from scripts.run_synthetic_interval_coverage import finite_sample_conformal_quantile


class SyntheticIntervalCoverageTests(unittest.TestCase):
    def test_uses_finite_sample_conformal_rank(self) -> None:
        scores = np.arange(1.0, 67.0)
        self.assertEqual(61.0, finite_sample_conformal_quantile(scores, 0.9))

    def test_rejects_missing_or_invalid_scores(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite scores"):
            finite_sample_conformal_quantile([np.nan], 0.9)
        with self.assertRaisesRegex(ValueError, "must be in"):
            finite_sample_conformal_quantile([0.1, 0.2], 1.0)
