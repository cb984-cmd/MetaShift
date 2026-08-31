import unittest

import numpy as np

from metashift.inference import (
    block_bootstrap_median_difference,
    nested_selection_block_bootstrap,
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

    def test_nested_bootstrap_reselects_correlated_donors(self) -> None:
        dates = np.arange(100, dtype=float)
        target = 10 + np.sin(dates / 9)
        donors = np.column_stack(
            [
                target + 0.05,
                target - 0.04,
                target + 0.03,
                target - 0.02,
            ]
        )
        calibration = np.column_stack([target, donors])
        pre = np.column_stack([target[:60], donors[:60]])
        post = np.column_stack([target[:60] + 2, donors[:60]])
        result = nested_selection_block_bootstrap(
            calibration,
            pre,
            post,
            np.array([5.0, 10.0, 15.0, 20.0]),
            repetitions=50,
            block_length=7,
            minimum_pair_days=30,
            minimum_effect_observations=20,
            random_seed=5,
        )
        self.assertGreater(result.point_estimate, 0.1)
        self.assertGreaterEqual(result.valid_repetitions, 25)
        self.assertGreater(result.lower_95, 0)
