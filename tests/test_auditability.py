import unittest

import numpy as np
import pandas as pd

from metashift.auditability import (
    epa_region,
    fit_ridge_logistic,
    standardized_mean_difference,
)


class AuditabilityTests(unittest.TestCase):
    def test_maps_epa_regions(self) -> None:
        self.assertEqual("EPA Region 5", epa_region("17"))
        self.assertEqual("EPA Region 9", epa_region("6"))
        self.assertEqual("Outside EPA mapped regions", epa_region("80"))
        with self.assertRaisesRegex(ValueError, "No EPA-region"):
            epa_region("99")

    def test_standardized_difference_has_expected_direction(self) -> None:
        value = standardized_mean_difference([4.0, 5.0, 6.0], [1.0, 2.0, 3.0])
        self.assertGreater(value, 0)

    def test_descriptive_ridge_logistic_is_finite(self) -> None:
        features = pd.DataFrame(
            {
                "pre_fit": [0.1, 0.2, 0.8, 0.9],
                "distance": [1.0, 2.0, 8.0, 9.0],
            }
        )
        fit = fit_ridge_logistic(features, np.array([1, 1, 0, 0]), 1.0)
        self.assertEqual(4, fit.observations)
        self.assertEqual(2, fit.positive_outcomes)
        self.assertTrue(np.isfinite(fit.coefficients).all())
