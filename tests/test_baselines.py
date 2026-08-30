import unittest

import numpy as np

from metashift.baselines import bayesian_mean_shift, before_after_median


class AnchoredBaselineTests(unittest.TestCase):
    def test_before_after_median_recovers_level_shift(self) -> None:
        result = before_after_median([1.0] * 20 + [3.0] * 20, split_index=20)
        self.assertAlmostEqual(result.effect, 2.0)
        self.assertGreater(result.score, 1)

    def test_bayesian_mean_shift_scores_known_change(self) -> None:
        values = np.r_[np.zeros(30), np.ones(30)]
        shifted = bayesian_mean_shift(values, split_index=30)
        unshifted = bayesian_mean_shift(np.zeros(60), split_index=30)
        self.assertGreater(shifted.score, unshifted.score)
        self.assertGreater(shifted.effect, 0)
