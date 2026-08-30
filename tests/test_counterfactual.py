import unittest

import numpy as np
import pandas as pd

from metashift.counterfactual import (
    cross_validated_reliability_weights,
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
)


class MetaShiftEstimateTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(7)
        self.dates = pd.date_range("2020-01-01", periods=420, freq="D")
        base = 12 + 3 * np.sin(np.arange(len(self.dates)) / 16)
        self.donors = pd.DataFrame(
            {
                "donor_a": base + rng.normal(0, 0.15, len(base)),
                "donor_b": base + rng.normal(0, 0.18, len(base)),
                "donor_c": base + rng.normal(0, 0.20, len(base)),
            },
            index=self.dates,
        )
        self.target = pd.Series(
            base * 1.08 + rng.normal(0, 0.15, len(base)),
            index=self.dates,
            name="target",
        )
        self.weights = pd.Series(
            {"donor_a": 0.4, "donor_b": 0.35, "donor_c": 0.25}
        )
        self.anchor = self.dates[260]

    def test_local_shift_produces_positive_residual_score(self) -> None:
        shifted_target = self.target.copy()
        shifted_target.loc[self.anchor :] *= 1.25

        estimate = estimate_metadata_anchor(
            shifted_target, self.donors, self.weights, self.anchor
        )

        self.assertGreater(estimate.relative_effect, 0.15)
        self.assertGreater(estimate.standardized_score, 3)

    def test_shared_environmental_shift_is_removed_by_donor_composite(self) -> None:
        shifted_target = self.target.copy()
        shifted_donors = self.donors.copy()
        shifted_target.loc[self.anchor :] *= 1.25
        shifted_donors.loc[self.anchor :] *= 1.25

        estimate = estimate_metadata_anchor(
            shifted_target, shifted_donors, self.weights, self.anchor
        )

        self.assertLess(abs(estimate.relative_effect), 0.05)
        self.assertLess(abs(estimate.standardized_score), 2)

    def test_reliability_constrained_weights_are_valid_and_use_only_supplied_pre_data(
        self,
    ) -> None:
        reliability = donor_weights(
            pd.DataFrame(
                {
                    "pre_transition_log_correlation": [0.95, 0.85, 0.75],
                    "distance_km": [5.0, 10.0, 20.0],
                },
                index=self.donors.columns,
            )
        )
        weights = reliability_constrained_weights(
            self.target.loc[: self.anchor - pd.Timedelta(days=1)],
            self.donors.loc[: self.anchor - pd.Timedelta(days=1)],
            reliability,
        )

        self.assertTrue((weights >= 0).all())
        self.assertAlmostEqual(float(weights.sum()), 1.0, places=8)

        changed_post_target = self.target.copy()
        changed_post_target.loc[self.anchor :] += 1_000
        unchanged_weights = reliability_constrained_weights(
            changed_post_target.loc[: self.anchor - pd.Timedelta(days=1)],
            self.donors.loc[: self.anchor - pd.Timedelta(days=1)],
            reliability,
        )
        np.testing.assert_allclose(weights.to_numpy(), unchanged_weights.to_numpy())

    def test_cross_validated_weights_use_only_supplied_pre_data(self) -> None:
        reliability = pd.Series(
            {"donor_a": 0.5, "donor_b": 0.3, "donor_c": 0.2}
        )
        pre_target = self.target.loc[: self.anchor - pd.Timedelta(days=1)]
        pre_donors = self.donors.loc[: self.anchor - pd.Timedelta(days=1)]
        selected = cross_validated_reliability_weights(
            pre_target, pre_donors, reliability, validation_days=45
        )
        self.assertTrue((selected.weights >= 0).all())
        self.assertAlmostEqual(float(selected.weights.sum()), 1.0, places=8)

        changed_post_target = self.target.copy()
        changed_post_target.loc[self.anchor :] += 1_000
        unchanged = cross_validated_reliability_weights(
            changed_post_target.loc[: self.anchor - pd.Timedelta(days=1)],
            pre_donors,
            reliability,
            validation_days=45,
        )
        np.testing.assert_allclose(
            selected.weights.to_numpy(), unchanged.weights.to_numpy()
        )
