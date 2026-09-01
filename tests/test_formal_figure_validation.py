import copy
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from matplotlib.transforms import Bbox


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

FACTORY_PATH = (
    Path(__file__).resolve().parents[1]
    / "paper"
    / "latex"
    / "scripts"
    / "figure_factory.py"
)
FACTORY_SPEC = importlib.util.spec_from_file_location("formal_figure_factory", FACTORY_PATH)
assert FACTORY_SPEC is not None and FACTORY_SPEC.loader is not None
figure_factory = importlib.util.module_from_spec(FACTORY_SPEC)
FACTORY_SPEC.loader.exec_module(figure_factory)

BUILD_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "paper"
    / "latex"
    / "scripts"
    / "build_paper.py"
)
BUILD_SPEC = importlib.util.spec_from_file_location("formal_paper_builder", BUILD_SCRIPT_PATH)
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
paper_builder = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(paper_builder)


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

    def test_text_inside_padded_node_requires_each_axis_margin(self) -> None:
        node = Bbox.from_extents(0, 0, 100, 50)
        self.assertTrue(
            figure_factory.text_inside_padded_box(
                Bbox.from_extents(8, 6, 92, 44),
                node,
                horizontal_padding_px=6,
                vertical_padding_px=4,
            )
        )
        self.assertFalse(
            figure_factory.text_inside_padded_box(
                Bbox.from_extents(5, 6, 92, 44),
                node,
                horizontal_padding_px=6,
                vertical_padding_px=4,
            )
        )

    def test_text_gap_detects_overlap_and_less_than_three_point_spacing(self) -> None:
        first = Bbox.from_extents(0, 0, 20, 10)
        self.assertTrue(
            figure_factory.boxes_violate_minimum_gap(
                first,
                Bbox.from_extents(22, 0, 40, 10),
                minimum_gap_px=3,
            )
        )
        self.assertFalse(
            figure_factory.boxes_violate_minimum_gap(
                first,
                Bbox.from_extents(24, 0, 40, 10),
                minimum_gap_px=3,
            )
        )

    def test_caption_lookup_accepts_hyphenated_and_split_marker_words(self) -> None:
        words = (
            "Figure",
            "10:",
            "Complete",
            "v0.5",
            "failure-mode",
            "map.",
            "The",
            "negative",
            "control.",
        )
        xml_words = "".join(
            f'<word xMin="0" yMin="{index}" xMax="10" yMax="{index + 1}">{word}</word>'
            for index, word in enumerate(words)
        )
        bbox_xml = f'<doc><page width="595" height="842">{xml_words}</page></doc>'
        markers = {
            "fig_v05_failure_mode_map.png": (
                "complete",
                "v05",
                "failuremode",
                "map",
                "negative",
                "control",
            )
        }

        with (
            patch.object(paper_builder, "FIGURE_CAPTION_MARKERS", markers),
            patch.object(paper_builder.subprocess, "check_output", return_value=bbox_xml),
        ):
            locations = paper_builder.extract_caption_locations("pdftotext", Path("paper.pdf"))

        self.assertEqual(1, locations["fig_v05_failure_mode_map.png"]["page"])

    def test_final_build_cannot_skip_compliance(self) -> None:
        final_args = paper_builder.argparse.Namespace(
            skip_final_compliance=True, staged_only=False
        )
        with self.assertRaisesRegex(ValueError, "final build must pass"):
            paper_builder.validate_build_options(final_args)

        staged_args = paper_builder.argparse.Namespace(
            skip_final_compliance=True, staged_only=True
        )
        paper_builder.validate_build_options(staged_args)

    def test_final_build_requires_clean_worktree_before_building(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "clean Git worktree"):
            paper_builder.require_clean_final_worktree(
                [" M paper/latex/main.tex"], staged_only=False
            )

        paper_builder.require_clean_final_worktree(
            [" M paper/latex/main.tex"], staged_only=True
        )

    def test_failed_post_publish_check_restores_canonical_pdf(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            build_directory = temporary / "build"
            build_directory.mkdir()
            candidate = temporary / "candidate.pdf"
            canonical = temporary / "canonical.pdf"
            candidate.write_bytes(b"verified-candidate")
            canonical.write_bytes(b"previous-canonical")

            with (
                patch.object(paper_builder, "BUILD_DIR", build_directory),
                patch.object(paper_builder, "FINAL_PDF", canonical),
                patch.object(
                    paper_builder,
                    "run",
                    side_effect=RuntimeError("post-publication verification failed"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "post-publication"):
                    paper_builder.publish_verified_pdf(candidate)

            self.assertEqual(b"previous-canonical", canonical.read_bytes())
            self.assertEqual([], list(build_directory.glob(".previous_canonical_*.pdf")))
