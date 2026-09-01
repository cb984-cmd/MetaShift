import unittest

import numpy as np
import pandas as pd

from metashift.counterfactual import anchor_residual_windows
from metashift.identifiability import (
    additive_increment_lipschitz_constant,
    build_analysis_scale_scope_pair,
    paired_schedule_seed,
    raw_additive_log_increment,
    raw_proportional_log_increment,
    schedule_sha256,
    shared_analysis_scale_noise,
)


class IdentifiabilityCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2023-01-01", periods=260, freq="D")
        values = np.arange(len(self.index), dtype=float)
        self.target = pd.Series(12.0 + 0.01 * values, index=self.index)
        self.donors = pd.DataFrame(
            {
                "a": 10.0 + 0.01 * values,
                "b": 12.0 + 0.015 * values,
                "c": 14.0 + 0.005 * values,
            },
            index=self.index,
        )
        self.donors.loc[self.index[160:180], "b"] = np.nan
        self.anchor = self.index[150]
        self.weights = pd.Series({"a": 0.5, "b": 0.3, "c": 0.2})

    def windows(self, target: pd.Series, donors: pd.DataFrame):
        return anchor_residual_windows(
            target,
            donors,
            self.weights,
            self.anchor,
            calibration_days=100,
            calibration_buffer_days=10,
            comparison_days=40,
            min_window_observations=30,
            min_available_donors=2,
        )

    def test_shared_schedule_is_pair_determined_not_arm_determined(self) -> None:
        first, first_seed = shared_analysis_scale_noise(
            self.index, self.anchor, "component-07:case-003", 0.02
        )
        second, second_seed = shared_analysis_scale_noise(
            self.index, self.anchor, "component-07:case-003", 0.02
        )

        self.assertEqual(first_seed, second_seed)
        self.assertEqual(
            first_seed, paired_schedule_seed("component-07:case-003")
        )
        np.testing.assert_array_equal(first.to_numpy(), second.to_numpy())
        self.assertTrue((first.loc[first.index < self.anchor] == 0.0).all())

    def test_pair_preserves_target_identity_and_numerical_residual_invariance(self) -> None:
        schedule, seed = shared_analysis_scale_noise(
            self.index, self.anchor, "component-07:case-003", 0.02
        )
        pair = build_analysis_scale_scope_pair(
            self.target,
            self.donors,
            self.anchor,
            schedule,
            "component-07:case-003",
            random_seed=seed,
        )
        baseline = self.windows(self.target, self.donors)
        local = self.windows(pair.local_target, pair.local_donors)
        regional = self.windows(pair.regional_target, pair.regional_donors)

        np.testing.assert_array_equal(
            pair.local_target.to_numpy(), pair.regional_target.to_numpy()
        )
        self.assertEqual(schedule_sha256(schedule), pair.schedule_sha256)
        np.testing.assert_allclose(
            baseline.post["log_residual"].to_numpy(),
            regional.post["log_residual"].to_numpy(),
            atol=1e-12,
            rtol=0.0,
        )
        self.assertGreater(
            abs(
                float(np.median(local.post["log_residual"]))
                - float(np.median(baseline.post["log_residual"]))
            ),
            1e-5,
        )

    def test_exact_pair_rejects_pre_anchor_or_invalid_inverse_schedule(self) -> None:
        pre_anchor_schedule = pd.Series(0.0, index=self.index)
        pre_anchor_schedule.iloc[0] = 0.01
        with self.assertRaisesRegex(ValueError, "zero before the anchor"):
            build_analysis_scale_scope_pair(
                self.target,
                self.donors,
                self.anchor,
                pre_anchor_schedule,
                "bad-pre-anchor",
            )

        invalid_schedule = pd.Series(0.0, index=self.index)
        invalid_schedule.loc[self.anchor :] = -5.0
        with self.assertRaisesRegex(ValueError, "inverse-transform domain"):
            build_analysis_scale_scope_pair(
                self.target,
                self.donors,
                self.anchor,
                invalid_schedule,
                "bad-domain",
            )

        schedule, seed = shared_analysis_scale_noise(
            self.index, self.anchor, "correct-seed", 0.02
        )
        with self.assertRaisesRegex(ValueError, "pair_id-derived seed"):
            build_analysis_scale_scope_pair(
                self.target,
                self.donors,
                self.anchor,
                schedule,
                "correct-seed",
                random_seed=seed + 1,
            )

    def test_clipping_aware_additive_bound_and_median_stability(self) -> None:
        raw = np.array([-3.0, -0.5, 0.0, 2.0, 8.0, 20.0])
        other = np.array([-2.0, -0.2, 0.5, 3.0, 12.0, 25.0])
        magnitude = 2.0
        increment_gap = np.abs(
            raw_additive_log_increment(raw, magnitude)
            - raw_additive_log_increment(other, magnitude)
        )
        self.assertTrue(
            np.all(increment_gap <= np.abs(raw - other) + 1e-12)
        )
        for signed_magnitude in (-5.0, -0.5, 0.0, 0.5, 5.0):
            signed_gap = np.abs(
                raw_additive_log_increment(raw, signed_magnitude)
                - raw_additive_log_increment(other, signed_magnitude)
            )
            self.assertTrue(
                np.all(signed_gap <= np.abs(raw - other) + 1e-12)
            )

        baseline = np.array([-1.0, -0.4, 0.1, 0.9, 1.8])
        perturbation = np.array([-0.2, 0.15, 0.05, -0.1, 0.2])
        self.assertLessEqual(
            abs(np.median(baseline + perturbation) - np.median(baseline)),
            np.max(np.abs(perturbation)) + 1e-12,
        )

    def test_nonnegative_raw_additive_residual_obeys_sharp_bound(self) -> None:
        magnitude = 1.5
        baseline = self.windows(self.target, self.donors)
        changed_target = self.target.copy()
        changed_donors = self.donors.copy()
        changed_target.loc[self.anchor :] += magnitude
        changed_donors.loc[self.anchor :, :] += magnitude
        changed = self.windows(changed_target, changed_donors)

        post_donors = self.donors.loc[baseline.post.index]
        available = post_donors.notna()
        normalized = available.mul(self.weights, axis="columns")
        normalized = normalized.div(normalized.sum(axis="columns"), axis="index")
        target_values = self.target.loc[baseline.post.index].to_numpy()[:, np.newaxis]
        mismatch = np.abs(target_values - post_donors.to_numpy())
        constant = additive_increment_lipschitz_constant(
            magnitude, nonnegative_lower_bound=0.0
        )
        daily_bound = constant * np.nansum(normalized.to_numpy() * mismatch, axis=1)
        effect_gap = abs(
            float(np.median(changed.post["log_residual"]))
            - float(np.median(baseline.post["log_residual"]))
        )

        self.assertLessEqual(effect_gap, float(np.max(daily_bound)) + 1e-12)

    def test_proportional_increment_obeys_global_bound(self) -> None:
        raw = np.array([-3.0, -0.5, 0.0, 2.0, 8.0, 20.0])
        other = np.array([-2.0, -0.2, 0.5, 3.0, 12.0, 25.0])
        proportion = 0.15
        increment_gap = np.abs(
            raw_proportional_log_increment(raw, proportion)
            - raw_proportional_log_increment(other, proportion)
        )
        self.assertTrue(
            np.all(increment_gap <= proportion * np.abs(raw - other) + 1e-12)
        )


if __name__ == "__main__":
    unittest.main()
