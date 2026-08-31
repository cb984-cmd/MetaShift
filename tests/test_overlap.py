import unittest

import numpy as np

from metashift.overlap import direction_agreement, paired_spearman


class OverlapTests(unittest.TestCase):
    def test_direction_agreement_requires_finite_nonzero_effects(self) -> None:
        self.assertTrue(direction_agreement(1.0, 2.0))
        self.assertFalse(direction_agreement(-1.0, 2.0))
        self.assertIsNone(direction_agreement(0.0, 2.0))
        self.assertIsNone(direction_agreement(np.nan, 2.0))

    def test_paired_spearman_filters_missing_values(self) -> None:
        count, correlation = paired_spearman(
            np.array([1.0, 2.0, np.nan, 4.0]),
            np.array([2.0, 4.0, 7.0, 8.0]),
        )
        self.assertEqual(3, count)
        self.assertAlmostEqual(1.0, correlation)
