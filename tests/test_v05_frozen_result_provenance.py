import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import verify_v05_frozen_result_provenance as verifier


ROOT = Path(__file__).resolve().parents[1]


class FrozenV05ResultProvenanceTests(unittest.TestCase):
    def test_tracked_manifest_has_complete_static_contract(self) -> None:
        manifest = json.loads(
            (ROOT / "configs" / "v05_frozen_result_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        report = verifier.build_metadata_report(manifest)
        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(4, len(report["checks"]))

    def test_annotated_tag_parsers_require_one_exact_reference(self) -> None:
        tag = "v0.5.0-answerability-freeze"
        object_id = "a" * 40
        commit = "b" * 40
        listing = f"{object_id}\trefs/tags/{tag}\n{commit}\trefs/tags/{tag}^{{}}\n"
        self.assertEqual(object_id, verifier.remote_tag_object_id(listing, tag))
        self.assertEqual(commit, verifier.remote_peeled_tag_commit(listing, tag))
        self.assertIsNone(verifier.remote_peeled_tag_commit(f"{object_id}\trefs/tags/{tag}\n", tag))

    def test_artifact_path_cannot_escape_validation_root(self) -> None:
        with self.assertRaises(ValueError):
            verifier.root_relative_path(ROOT, "../outside.csv")

    def test_exporter_is_directly_invocable(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/export_v05_frozen_evidence.py", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("Archive existing v0.5 frozen evidence", completed.stdout)


if __name__ == "__main__":
    unittest.main()
