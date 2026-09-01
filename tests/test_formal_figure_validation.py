import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "paper"
    / "latex"
    / "scripts"
    / "verify_figures.py"
)
SPEC = importlib.util.spec_from_file_location("formal_figure_verifier", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
figure_verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(figure_verifier)


class FormalFigureValidationTests(unittest.TestCase):
    def test_window_contract_requires_inclusive_bounds_and_overlap(self) -> None:
        config = {
            "windows": {
                "calibration": {
                    "start_offset_days": -180,
                    "end_offset_days": -15,
                    "inclusive_calendar_dates": 166,
                },
                "pre": {
                    "start_offset_days": -60,
                    "end_offset_days": -1,
                    "inclusive_calendar_dates": 60,
                },
                "post": {
                    "start_offset_days": 0,
                    "end_offset_days": 59,
                    "inclusive_calendar_dates": 60,
                },
                "calibration_pre_overlap_calendar_dates": 46,
            }
        }
        self.assertEqual([], figure_verifier.window_contract_violations(config))

        invalid = copy.deepcopy(config)
        invalid["windows"]["calibration_pre_overlap_calendar_dates"] = 45
        self.assertEqual(
            "incorrect_calibration_pre_overlap",
            figure_verifier.window_contract_violations(invalid)[0]["issue"],
        )
