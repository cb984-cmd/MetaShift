import unittest

import numpy as np
import pandas as pd

from metashift.answerability import (
    build_partial_scope_pair,
    comparative_observation_identity,
    effective_donor_participation,
    normalized_availability_weights,
    policy_summary,
    raw_additive_mean_leakage_bound,
    select_confidence_cutoff,
    series_sha256,
    signed_mean_residual_effect,
    structural_certificate,
    structural_error_bound,
)


class ScopeAnswerabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2031-01-01", periods=300, freq="D")
        self.anchor = self.index[180]
        target_z = np.full(300, 2.4)
        donor_z = np.column_stack(
            [
                np.full(300, 2.3),
                np.full(300, 2.35),
                np.full(300, 2.45),
                np.full(300, 2.5),
            ]
        )
        self.target = pd.Series(np.expm1(target_z), index=self.index)
        self.donors = pd.DataFrame(
            np.expm1(donor_z),
            index=self.index,
            columns=["d0", "d1", "d2", "d3"],
        )
        self.weights = pd.Series(0.25, index=self.donors.columns)
        self.signal = pd.Series(0.0, index=self.index)
        self.signal.loc[self.anchor :] = 0.12
        self.raw_field = pd.Series(0.0, index=self.index)
        self.contamination = pd.DataFrame(
            0.0, index=self.index, columns=self.donors.columns
        )

    def score(self, target: pd.Series, donors: pd.DataFrame) -> tuple[float, pd.DatetimeIndex]:
        value, _, post = signed_mean_residual_effect(
            target,
            donors,
            self.weights,
            self.anchor,
            calibration_days=120,
            calibration_buffer_days=15,
            comparison_days=60,
            min_window_observations=40,
            min_available_donors=3,
        )
        return value, post

    def test_exact_partial_scope_identity_and_scores(self) -> None:
        participation = pd.DataFrame(0.5, index=self.index, columns=self.donors.columns)
        pair = build_partial_scope_pair(
            self.target,
            self.donors,
            self.anchor,
            self.signal,
            participation,
            self.raw_field,
            self.contamination,
        )
        local_score, post = self.score(pair.target, pair.local_donors)
        shared_score, _ = self.score(pair.target, pair.shared_donors)
        q = effective_donor_participation(pair.local_donors, self.weights, participation)

        np.testing.assert_array_equal(pair.target.to_numpy(), pair.target.to_numpy())
        self.assertAlmostEqual(0.12, local_score, places=12)
        self.assertAlmostEqual(0.06, shared_score, places=12)
        self.assertAlmostEqual(0.06, local_score - shared_score, places=12)
        self.assertTrue(np.allclose(q.loc[post].to_numpy(), 0.5))

    def test_q_zero_preserves_full_comparative_observation_identity(self) -> None:
        participation = pd.DataFrame(0.0, index=self.index, columns=self.donors.columns)
        pair = build_partial_scope_pair(
            self.target,
            self.donors,
            self.anchor,
            self.signal,
            participation,
            self.raw_field,
            self.contamination,
        )

        self.assertTrue(
            comparative_observation_identity(
                pair.target, pair.local_donors, pair.target, pair.shared_donors
            )
        )
        self.assertEqual(series_sha256(pair.target), series_sha256(pair.target.copy()))

    def test_availability_normalization_changes_effective_participation(self) -> None:
        participation = pd.DataFrame(
            [0.13, 0.21, 0.29, 0.37],
            index=self.donors.columns,
        ).T
        participation = pd.concat([participation] * len(self.index), ignore_index=True)
        participation.index = self.index
        donors = self.donors.copy()
        donors.loc[self.index[180], "d3"] = np.nan

        normalized = normalized_availability_weights(donors, self.weights)
        q = effective_donor_participation(donors, self.weights, participation)

        self.assertAlmostEqual(1.0, float(normalized.loc[self.index[180]].sum()))
        self.assertAlmostEqual(
            (0.13 + 0.21 + 0.29) / 3.0,
            float(q.loc[self.index[180]]),
        )

    def test_raw_field_leakage_is_bounded(self) -> None:
        participation = pd.DataFrame(0.5, index=self.index, columns=self.donors.columns)
        baseline = build_partial_scope_pair(
            self.target,
            self.donors,
            self.anchor,
            self.signal,
            participation,
            self.raw_field,
            self.contamination,
        )
        field = self.raw_field.copy()
        field.loc[self.anchor :] = 2.0
        stressed = build_partial_scope_pair(
            self.target,
            self.donors,
            self.anchor,
            self.signal,
            participation,
            field,
            self.contamination,
        )
        local_baseline, post = self.score(baseline.target, baseline.local_donors)
        local_stressed, _ = self.score(stressed.target, stressed.local_donors)
        bound = raw_additive_mean_leakage_bound(
            np.expm1(np.log1p(self.target) + self.signal),
            baseline.local_donors_before_raw_field,
            self.weights,
            post,
            2.0,
        )

        self.assertLessEqual(abs(local_stressed - local_baseline), bound + 1e-12)

    def test_structural_certificate_uses_interval_safe_threshold(self) -> None:
        local = structural_certificate(
            score=0.19,
            signal_h=0.2,
            gap_lower_bound=0.1,
            local_error_bound=0.01,
            shared_error_bound=0.04,
        )
        shared = structural_certificate(
            score=0.14,
            signal_h=0.2,
            gap_lower_bound=0.1,
            local_error_bound=0.01,
            shared_error_bound=0.04,
        )

        self.assertTrue(local.answered)
        self.assertTrue(local.predicts_local)
        self.assertTrue(shared.answered)
        self.assertFalse(shared.predicts_local)
        self.assertAlmostEqual(0.165, local.threshold)
        self.assertNotAlmostEqual(0.15, local.threshold)

    def test_nonpositive_margin_requires_abstention(self) -> None:
        certificate = structural_certificate(
            score=0.1,
            signal_h=0.12,
            gap_lower_bound=0.02,
            local_error_bound=0.02,
            shared_error_bound=0.01,
        )

        self.assertFalse(certificate.answered)
        self.assertIsNone(certificate.predicts_local)

    def test_structural_error_bound_matches_declared_formula(self) -> None:
        bound = structural_error_bound(
            maximum_absolute_donor_offset=0.002,
            pre_noise_half_width=0.004,
            post_noise_half_width=0.008,
            raw_error_bound=0.003,
            contamination_error_bound=0.01,
        )
        self.assertAlmostEqual(0.041, bound)

    def test_confidence_cutoff_is_calibration_only_and_has_fixed_tie_rule(self) -> None:
        labels = np.array([True, False, True, False])
        scores = np.array([0.9, 0.1, 0.6, 0.4])
        selected = select_confidence_cutoff(
            labels, scores, threshold=0.5, alpha=0.01, quantile_count=5
        )

        self.assertEqual("complete", selected.status)
        self.assertAlmostEqual(1.0, selected.calibration_coverage)
        self.assertAlmostEqual(0.0, float(selected.calibration_conditional_error))

    def test_policy_summary_retains_zero_coverage(self) -> None:
        summary = policy_summary(
            np.array([True, False]),
            np.array([True, False]),
            np.array([False, False]),
        )

        self.assertEqual(0, summary["answered_events"])
        self.assertEqual(0.0, summary["coverage"])
        self.assertIsNone(summary["conditional_error"])
        self.assertEqual("no_answered_cases", summary["status"])

    def test_pair_builder_rejects_pre_anchor_contamination(self) -> None:
        participation = pd.DataFrame(0.5, index=self.index, columns=self.donors.columns)
        contamination = self.contamination.copy()
        contamination.iloc[0, 0] = 0.01

        with self.assertRaisesRegex(ValueError, "zero before the anchor"):
            build_partial_scope_pair(
                self.target,
                self.donors,
                self.anchor,
                self.signal,
                participation,
                self.raw_field,
                contamination,
            )


if __name__ == "__main__":
    unittest.main()
