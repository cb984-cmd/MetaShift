import unittest

from scripts.verify_v04_stress_suite_audit import STRESS_BOUNDARIES, matrix_rows


def record(
    family: str, split: str, bound: float, leakage: float, satisfied: bool
) -> dict[str, str]:
    return {
        "stress_family": family,
        "split": split,
        "maximum_residual_leakage_bound": str(bound),
        "absolute_median_effect_leakage": str(leakage),
        "bound_satisfied": str(satisfied),
    }


class StressSuiteAuditTests(unittest.TestCase):
    def test_matrix_rows_retain_all_families_splits_and_failures(self) -> None:
        records = [
            record(family, split, 0.5, 0.1, family != "raw_variance_increase")
            for family in STRESS_BOUNDARIES
            for split in ("calibration", "evaluation")
        ]

        rows = matrix_rows(records, "artifacts/stress.csv", "b" * 64)

        self.assertEqual(10, len(rows))
        variance_evaluation = next(
            row
            for row in rows
            if row["stress_family"] == "raw_variance_increase"
            and row["split"] == "evaluation"
        )
        self.assertEqual("1", variance_evaluation["bound_failure_count"])
        self.assertEqual(
            "outside_exact_core_no_frozen_L_R_target_equivalence",
            variance_evaluation["exact_cancellation_status"],
        )
        self.assertEqual(
            "unavailable_in_frozen_output",
            variance_evaluation["classification_risk_coverage_status"],
        )


if __name__ == "__main__":
    unittest.main()
