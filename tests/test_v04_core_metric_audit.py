import unittest

from scripts.verify_v04_core_metric_audit import matrix_rows


def event(
    split: str,
    state: str,
    detection: str,
    forced_scope: str = "",
    target_scope: str = "",
    *,
    answered_q000: bool = False,
) -> dict[str, str]:
    value = str(answered_q000)
    return {
        "split": split,
        "state": state,
        "detection_prediction": detection,
        "forced_scope_prediction": forced_scope,
        "target_only_scope_prediction": target_scope,
        "answered_q0.00": value,
        "answered_q0.25": value,
        "answered_q0.50": value,
        "answered_q0.75": value,
    }


class CoreMetricAuditTests(unittest.TestCase):
    def test_matrix_rows_include_zero_cells_and_abstentions(self) -> None:
        events = [
            event("calibration", "no_change", "no_change"),
            event(
                "calibration",
                "local",
                "change",
                "local",
                "local",
                answered_q000=True,
            ),
            event(
                "calibration",
                "regional",
                "change",
                "regional",
                "local",
                answered_q000=False,
            ),
            event("evaluation", "no_change", "change"),
            event(
                "evaluation",
                "local",
                "change",
                "local",
                "local",
                answered_q000=True,
            ),
            event(
                "evaluation",
                "regional",
                "no_change",
                "regional",
                "local",
                answered_q000=False,
            ),
        ]

        rows = matrix_rows(
            events,
            ["0.00", "0.25", "0.50", "0.75"],
            "artifacts/core.csv",
            "a" * 64,
        )

        self.assertEqual(72, len(rows))
        self.assertIn(
            {
                "task": "forced_scope",
                "split": "evaluation",
                "quantile": "",
                "truth_label": "local",
                "decision": "answered",
                "prediction_label": "regional",
                "count": "0",
                "task_denominator": "2",
                "source_artifact_path": "artifacts/core.csv",
                "source_artifact_sha256": "a" * 64,
            },
            rows,
        )
        self.assertIn(
            {
                "task": "selective_scope",
                "split": "evaluation",
                "quantile": "0.00",
                "truth_label": "regional",
                "decision": "abstained",
                "prediction_label": "not_answered",
                "count": "1",
                "task_denominator": "2",
                "source_artifact_path": "artifacts/core.csv",
                "source_artifact_sha256": "a" * 64,
            },
            rows,
        )


if __name__ == "__main__":
    unittest.main()
