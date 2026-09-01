import unittest

import numpy as np
import pandas as pd

from metashift.synthetic import benchmark_seed, inject_perturbation
from scripts.run_stable_synthetic_benchmark import variant_specs


class FrozenV03TheoryScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2024-01-01", periods=160, freq="D")
        values = np.arange(len(self.index), dtype=float)
        self.target = pd.Series(10.0 + np.sin(values / 7.0), index=self.index)
        self.donors = pd.DataFrame(
            {
                "a": 8.0 + np.sin(values / 7.0),
                "b": 12.0 + np.sin(values / 7.0),
            },
            index=self.index,
        )
        self.anchor = self.index[80]

    def test_only_deterministic_v03_pairs_have_exact_target_identity(self) -> None:
        specs = variant_specs(2.0, 1.0)
        for variant_index in range(0, 8, 2):
            local_kind, magnitude, _ = specs[variant_index]
            regional_kind, regional_magnitude, _ = specs[variant_index + 1]
            local, _, _ = inject_perturbation(
                self.target,
                self.donors,
                self.anchor,
                local_kind,
                magnitude,
                random_seed=benchmark_seed(1, 1, variant_index),
            )
            regional, _, _ = inject_perturbation(
                self.target,
                self.donors,
                self.anchor,
                regional_kind,
                regional_magnitude,
                random_seed=benchmark_seed(1, 1, variant_index + 1),
            )
            np.testing.assert_array_equal(local.to_numpy(), regional.to_numpy())

        local_kind, magnitude, _ = specs[8]
        regional_kind, regional_magnitude, _ = specs[9]
        local, _, _ = inject_perturbation(
            self.target,
            self.donors,
            self.anchor,
            local_kind,
            magnitude,
            random_seed=benchmark_seed(1, 1, 8),
        )
        regional, _, _ = inject_perturbation(
            self.target,
            self.donors,
            self.anchor,
            regional_kind,
            regional_magnitude,
            random_seed=benchmark_seed(1, 1, 9),
        )
        self.assertFalse(np.array_equal(local.to_numpy(), regional.to_numpy()))

    def test_raw_shared_additive_shift_is_not_exactly_shared_on_log_scale(self) -> None:
        target_delta = np.log1p(self.target + 2.0) - np.log1p(self.target)
        donor_delta = np.log1p(self.donors["a"] + 2.0) - np.log1p(
            self.donors["a"]
        )

        self.assertFalse(
            np.array_equal(target_delta.to_numpy(), donor_delta.to_numpy())
        )


if __name__ == "__main__":
    unittest.main()
