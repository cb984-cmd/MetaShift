import unittest

import numpy as np

from metashift.inference import (
    block_bootstrap_median_difference,
    seed_from_identifier,
)


class InferenceTests(unittest.TestCase):
    def test_seed_is_stable_and_identifier_specific(self) -> None:
        self.assertEqual(seed_from_identifier("event-a"), seed_from_identifier("event-a"))
        self.assertNotEqual(seed_from_identifier("event-a"), seed_from_identifier("event-b"))

    def test_block_bootstrap_is_deterministic(self) -> None:
        pre = np.arange(20, dtype=float)
        post = pre + 2
        first = block_bootstrap_median_difference(
            pre, post, repetitions=100, random_seed=4
        )
        second = block_bootstrap_median_difference(
            pre, post, repetitions=100, random_seed=4
        )
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.point_estimate, 2.0)
        self.assertLess(first.lower_95, first.upper_95)
