import unittest

import numpy as np
import pandas as pd

from metashift.v2 import (
    AttributionShape,
    attribute_residual_shape,
    evaluate_quality_gate,
    placebo_p_value,
)


class MetaShiftV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2024-01-01", periods=360, freq="D")
        base = 10 + np.sin(np.arange(360) / 12)
        self.target = pd.Series(base, index=self.index)
        self.donors = pd.DataFrame(
            {"a": base + 0.02, "b": base - 0.03, "c": base + 0.01},
            index=self.index,
        )
        self.weights = pd.Series({"a": 0.4, "b": 0.35, "c": 0.25})
        self.anchor = self.index[250]

    def test_quality_gate_accepts_stable_well_matched_event(self) -> None:
        gate = evaluate_quality_gate(
            self.target, self.donors, self.weights, self.anchor
        )
        self.assertTrue(gate.passed)
        self.assertIsNone(gate.reason)
        self.assertGreater(gate.effective_donor_count, 2)

    def test_level_shift_has_level_attribution(self) -> None:
        residuals = pd.Series(np.zeros(len(self.index)), index=self.index)
        residuals.loc[self.anchor :] = 0.5
        attribution = attribute_residual_shape(residuals, self.anchor)
        self.assertEqual(attribution.shape, AttributionShape.LEVEL)
        self.assertGreater(attribution.persistence, 0.9)

    def test_placebo_probability_uses_finite_sample_correction(self) -> None:
        self.assertAlmostEqual(placebo_p_value(3.0, [1.0, 3.0, 4.0]), 0.75)
