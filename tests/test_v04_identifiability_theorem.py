import unittest

import numpy as np

from metashift.identifiability import (
    discrete_binary_bayes_error,
    discrete_total_variation_distance,
    label_blind_accepted_local_prior,
)


class IdentifiabilityTheoremTests(unittest.TestCase):
    def test_balanced_identical_target_laws_have_half_bayes_error(self) -> None:
        common = np.array([0.2, 0.5, 0.3])

        error = discrete_binary_bayes_error(common, common, 0.5)
        variation = discrete_total_variation_distance(common, common)

        self.assertAlmostEqual(0.5, error)
        self.assertAlmostEqual(0.0, variation)
        self.assertAlmostEqual(error, 0.5 * (1.0 - variation))

    def test_ordinary_tv_does_not_determine_unequal_prior_bayes_error(self) -> None:
        local_first = np.array([0.75, 0.25])
        regional_first = np.array([0.25, 0.75])
        local_second = np.array([0.9, 0.1])
        regional_second = np.array([0.4, 0.6])

        self.assertAlmostEqual(
            discrete_total_variation_distance(local_first, regional_first),
            discrete_total_variation_distance(local_second, regional_second),
        )
        self.assertAlmostEqual(
            0.2, discrete_binary_bayes_error(local_first, regional_first, 0.8)
        )
        self.assertAlmostEqual(
            0.16, discrete_binary_bayes_error(local_second, regional_second, 0.8)
        )

    def test_label_blind_positive_coverage_preserves_the_scope_prior(self) -> None:
        common = np.array([0.2, 0.5, 0.3])
        acceptance = np.array([0.0, 0.4, 1.0])

        accepted_prior = label_blind_accepted_local_prior(common, acceptance, 0.8)

        self.assertAlmostEqual(0.8, accepted_prior)
        self.assertAlmostEqual(0.2, min(accepted_prior, 1.0 - accepted_prior))

    def test_label_dependent_selection_is_not_the_theorem_case(self) -> None:
        local_prior = 0.8
        common = np.array([0.2, 0.5, 0.3])
        local_acceptance = np.ones_like(common)
        regional_acceptance = np.zeros_like(common)
        numerator = local_prior * float(np.dot(common, local_acceptance))
        denominator = numerator + (1.0 - local_prior) * float(
            np.dot(common, regional_acceptance)
        )

        self.assertAlmostEqual(1.0, numerator / denominator)

    def test_probability_contract_rejects_invalid_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum to one"):
            discrete_binary_bayes_error([0.6, 0.6], [0.5, 0.5], 0.5)
        with self.assertRaisesRegex(ValueError, "positive coverage"):
            label_blind_accepted_local_prior([0.5, 0.5], [0.0, 0.0], 0.5)


if __name__ == "__main__":
    unittest.main()
