import unittest

import numpy as np
import pandas as pd

from metashift.synthetic import PerturbationKind, inject_perturbation


class SyntheticInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2024-01-01", periods=100, freq="D")
        self.target = pd.Series(np.full(100, 10.0), index=self.index)
        self.donors = pd.DataFrame(
            {"a": np.full(100, 10.0), "b": np.full(100, 8.0)}, index=self.index
        )
        self.anchor = self.index[60]

    def test_target_only_step_preserves_pre_anchor_values(self) -> None:
        injected, donors, truth = inject_perturbation(
            self.target,
            self.donors,
            self.anchor,
            PerturbationKind.ADDITIVE_STEP,
            3.0,
        )

        self.assertTrue((injected.loc[: self.index[59]] == 10.0).all())
        self.assertTrue((injected.loc[self.anchor :] == 13.0).all())
        self.assertTrue(donors.equals(self.donors))
        self.assertEqual(truth.affected_columns, ("target",))

    def test_regional_effect_changes_target_and_all_donors(self) -> None:
        injected, donors, truth = inject_perturbation(
            self.target,
            self.donors,
            self.anchor,
            PerturbationKind.REGIONAL_PROPORTIONAL_STEP,
            0.2,
        )

        self.assertTrue((injected.loc[self.anchor :] == 12.0).all())
        self.assertTrue((donors.loc[self.anchor :, "a"] == 12.0).all())
        self.assertTrue((donors.loc[self.anchor :, "b"] == 9.6).all())
        self.assertEqual(truth.affected_columns, ("target", "a", "b"))

    def test_regional_additive_step_is_shared(self) -> None:
        injected, donors, truth = inject_perturbation(
            self.target,
            self.donors,
            self.anchor,
            PerturbationKind.REGIONAL_ADDITIVE_STEP,
            3.0,
        )

        self.assertTrue((injected.loc[self.anchor :] == 13.0).all())
        self.assertTrue((donors.loc[self.anchor :, "a"] == 13.0).all())
        self.assertTrue((donors.loc[self.anchor :, "b"] == 11.0).all())
        self.assertEqual(truth.affected_columns, ("target", "a", "b"))
