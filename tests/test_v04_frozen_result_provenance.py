import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts import verify_v04_frozen_result_provenance as verifier


ROOT = Path(__file__).resolve().parents[1]


class FrozenResultProvenanceTests(unittest.TestCase):
    def test_tracked_manifest_has_complete_static_contract(self) -> None:
        manifest = json.loads(
            (ROOT / "configs" / "v04_frozen_result_manifest.json").read_text(
                encoding="utf-8"
            )
        )

        report = verifier.build_metadata_report(manifest)

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(5, len(report["checks"]))

    def test_csv_artifact_check_rejects_byte_or_shape_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "artifacts" / "sample.csv"
            path.parent.mkdir()
            with path.open("w", encoding="utf-8", newline="") as destination:
                writer = csv.writer(destination)
                writer.writerow(["id", "score"])
                writer.writerow(["case-1", "0.5"])
            entry = {
                "path": "artifacts/sample.csv",
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "kind": "csv",
                "data_rows": 1,
                "schema": ["id", "score"],
            }

            self.assertTrue(verifier.artifact_check(entry, root)[0])
            with path.open("a", encoding="utf-8", newline="") as destination:
                destination.write("case-2,0.7\n")
            self.assertFalse(verifier.artifact_check(entry, root)[0])

    def test_remote_peeled_tag_parser_requires_one_reference(self) -> None:
        tag = "v0.4.1-execution-freeze"
        commit = "a" * 40

        self.assertEqual(
            commit,
            verifier.remote_peeled_tag_commit(
                f"{'b' * 40}\trefs/tags/{tag}\n"
                f"{commit}\trefs/tags/{tag}^{{}}\n",
                tag,
            ),
        )
        self.assertIsNone(
            verifier.remote_peeled_tag_commit(
                f"{'b' * 40}\trefs/tags/{tag}\n", tag
            )
        )

    def test_artifact_path_must_stay_under_its_validation_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            with self.assertRaises(ValueError):
                verifier.root_relative_path(root, "../outside.json")


if __name__ == "__main__":
    unittest.main()
