import unittest
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

from scripts.verify_taxonomy_human_review_packet import (
    PACKET_PATH,
    SOURCE_PATH,
    build_report,
    packet_rows,
)


def source_row() -> dict[str, str]:
    return {
        "old_method_code": "101",
        "old_method_name": "Old A",
        "new_method_code": "102",
        "new_method_name": "New A",
        "old_analyzer_family": "A",
        "new_analyzer_family": "B",
        "transition_class": "cross_analyzer_family",
        "nda_related": "false",
        "same_hardware_family": "false",
        "classification_basis": "Metadata-only",
        "official_source": "https://example.invalid/source",
        "review_status": "pending_student_teacher_review",
    }


class TaxonomyHumanReviewPacketTests(unittest.TestCase):
    def test_git_lf_checkout_preserves_frozen_source_identity(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = root / SOURCE_PATH.relative_to(SOURCE_PATH.parents[1])
            packet_path = root / PACKET_PATH.relative_to(PACKET_PATH.parents[2])
            source_path.parent.mkdir(parents=True)
            packet_path.parent.mkdir(parents=True)
            source_path.write_bytes(SOURCE_PATH.read_bytes().replace(b"\r\n", b"\n"))
            copy2(PACKET_PATH, packet_path)

            report = build_report(root)

        self.assertTrue(report["all_checks_passed"])

    def test_completed_decision_in_template_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = root / SOURCE_PATH.relative_to(SOURCE_PATH.parents[1])
            packet_path = root / PACKET_PATH.relative_to(PACKET_PATH.parents[2])
            source_path.parent.mkdir(parents=True)
            packet_path.parent.mkdir(parents=True)
            copy2(SOURCE_PATH, source_path)
            packet_path.write_text(
                PACKET_PATH.read_text(encoding="utf-8").replace(
                    "pending_human_review", "confirmed_as_recorded", 1
                ),
                encoding="utf-8",
            )

            report = build_report(root)

        self.assertFalse(report["all_checks_passed"])
        self.assertFalse(
            next(
                item["passed"]
                for item in report["checks"]
                if item["name"] == "packet_remains_unreviewed"
            )
        )

    def test_tracked_packet_remains_an_unreviewed_exact_copy(self) -> None:
        self.assertTrue(build_report()["all_checks_passed"])

    def test_packet_rows_preserve_metadata_and_leave_human_fields_empty(self) -> None:
        rows = packet_rows([source_row()], "a" * 64)

        self.assertEqual(1, len(rows))
        self.assertEqual("TAX-001", rows[0]["review_row_id"])
        self.assertEqual(
            "cross_analyzer_family", rows[0]["frozen_proposed_transition_class"]
        )
        self.assertEqual("pending_human_review", rows[0]["human_review_decision"])
        self.assertEqual("", rows[0]["student_reviewer_initials"])
        self.assertEqual("a" * 64, rows[0]["frozen_taxonomy_sha256"])


if __name__ == "__main__":
    unittest.main()
