import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts import run_v04_identifiability_benchmark as runner


ROOT = Path(__file__).resolve().parents[1]


def miniature_protocol() -> dict:
    protocol = json.loads(
        (ROOT / "configs" / "v04_identifiability_protocol.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = copy.deepcopy(protocol)
    protocol["synthetic_panel"]["component_counts"] = {
        "calibration": 2,
        "evaluation": 3,
    }
    protocol["evaluation"]["bootstrap"]["repetitions"] = 5
    protocol["evaluation"]["bootstrap"][
        "minimum_valid_repetitions_per_answered_risk"
    ] = 1
    protocol["expected_accounting"]["core_pairs"] = {
        "calibration": 4,
        "evaluation": 6,
        "total": 10,
    }
    protocol["expected_accounting"]["core_events"] = {
        "calibration": 12,
        "evaluation": 18,
        "total": 30,
    }
    protocol["expected_accounting"]["core_scope_events"] = {
        "calibration": 8,
        "evaluation": 12,
        "total": 20,
    }
    protocol["expected_accounting"]["stress_events"] = 25
    return protocol


class V04ExecutionContractTests(unittest.TestCase):
    def test_component_generation_is_deterministic_and_preserves_donor_minimum(self) -> None:
        protocol = miniature_protocol()
        first = runner.generate_component(protocol, "calibration", 0)
        second = runner.generate_component(protocol, "calibration", 0)

        np.testing.assert_array_equal(first.target.to_numpy(), second.target.to_numpy())
        np.testing.assert_allclose(
            first.donors.to_numpy(),
            second.donors.to_numpy(),
            atol=0.0,
            rtol=0.0,
            equal_nan=True,
        )
        self.assertEqual(300, len(first.target))
        self.assertEqual(first.target.index[180], first.anchor_date)
        self.assertTrue((first.donors.notna().sum(axis="columns") >= 3).all())
        self.assertTrue((first.target > 0.0).all())

    def test_matched_core_rows_preserve_target_identity_and_regional_score(self) -> None:
        protocol = miniature_protocol()
        component = runner.generate_component(protocol, "calibration", 0)
        rows = runner.core_rows_for_component(protocol, component, "test-tag")

        self.assertEqual(6, len(rows))
        for family in ("constant_step", "bounded_stochastic_step"):
            pair = [row for row in rows if row["schedule_family"] == family]
            by_state = {row["state"]: row for row in pair}
            self.assertTrue(by_state["local"]["local_regional_target_identity"])
            self.assertTrue(by_state["regional"]["local_regional_target_identity"])
            self.assertAlmostEqual(
                by_state["no_change"]["comparative_log_effect"],
                by_state["regional"]["comparative_log_effect"],
                places=12,
            )
            self.assertEqual(
                by_state["local"]["target_only_score"],
                by_state["regional"]["target_only_score"],
            )

    def test_miniature_calibration_metrics_bootstrap_and_stress_are_complete(self) -> None:
        protocol = miniature_protocol()
        core = runner.generate_core_rows(protocol, "test-tag")
        thresholds = runner.calibration_thresholds(core, protocol)
        predicted = runner.apply_predictions(core, thresholds)
        summary = runner.summarize_evaluation(predicted, thresholds, protocol)
        bootstrap = runner.bootstrap_evaluation(predicted, thresholds, protocol)
        stress = runner.generate_stress_rows(protocol)

        self.assertEqual(
            {"no_change": 6, "local": 6, "regional": 6},
            summary["complete_event_accounting"],
        )
        self.assertEqual(5, bootstrap["repetitions"])
        self.assertEqual(25, len(stress))
        self.assertTrue(stress["bound_satisfied"].all())
        self.assertTrue(
            all(
                "valid_repetitions" in interval
                for interval in bootstrap["metrics"].values()
            )
        )
        self.assertEqual(
            set(protocol["evaluation"]["selective_policy"]["operating_quantiles"]),
            {float(key) for key in summary["selective_scope"]},
        )

    def test_attempt_record_is_exclusive_and_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            output_directory = temporary / "results"
            attempt_record = temporary / "attempt.json"
            preconditions = {
                "execution_git_commit": "a" * 40,
                "execution_tag": "test-tag",
                "protocol_sha256": "b" * 64,
                "execution_manifest_sha256": "c" * 64,
                "allowed_input_hashes": {},
            }

            runner.acquire_attempt(output_directory, attempt_record, preconditions)

            self.assertTrue(output_directory.is_dir())
            stored = json.loads(attempt_record.read_text(encoding="utf-8"))
            self.assertEqual("started", stored["state"])
            with self.assertRaises(FileExistsError):
                runner.acquire_attempt(output_directory, attempt_record, preconditions)

    def test_protocol_allowlist_excludes_external_data_paths(self) -> None:
        protocol = miniature_protocol()
        allowlist = protocol["data_access"]["execution_input_allowlist"]

        self.assertIn("configs/v04_identifiability_protocol.json", allowlist)
        self.assertIn("scripts/run_v04_identifiability_benchmark.py", allowlist)
        self.assertFalse(
            any(
                path.startswith(("data/", "artifacts/", "results/"))
                for path in allowlist
            )
        )

    def test_receipt_contract_requires_protocol_tag_and_partial_hashes(self) -> None:
        protocol = miniature_protocol()
        contract = protocol["output_contract"]

        self.assertEqual("v0.4.0-protocol-freeze", contract["protocol_freeze_tag"])
        self.assertIn("protocol tag", " ".join(contract["receipt_requirements"]))
        self.assertIn("receipt_hash_rule", contract)

    def test_remote_tag_parser_requires_one_peeled_annotated_reference(self) -> None:
        listing = (
            "1111111111111111111111111111111111111111\t"
            "refs/tags/v0.4.0-execution-freeze\n"
            "2222222222222222222222222222222222222222\t"
            "refs/tags/v0.4.0-execution-freeze^{}\n"
        )

        self.assertEqual(
            "2222222222222222222222222222222222222222",
            runner.remote_peeled_tag_commit(listing, "v0.4.0-execution-freeze"),
        )
        with self.assertRaises(RuntimeError):
            runner.remote_peeled_tag_commit(
                "1111111111111111111111111111111111111111\t"
                "refs/tags/v0.4.0-execution-freeze\n",
                "v0.4.0-execution-freeze",
            )

    def test_annotated_tag_binding_rejects_missing_or_mismatched_tags(self) -> None:
        tag = "v0.4.0-execution-freeze"
        head = "a" * 40
        matching_listing = (
            f"{'b' * 40}\trefs/tags/{tag}\n"
            f"{head}\trefs/tags/{tag}^{{}}\n"
        )

        self.assertEqual(
            head,
            runner.validate_annotated_execution_tag(
                tag, head, "tag", head, matching_listing
            ),
        )
        with self.assertRaises(RuntimeError):
            runner.validate_annotated_execution_tag(
                tag, head, "commit", head, matching_listing
            )
        with self.assertRaises(RuntimeError):
            runner.validate_annotated_execution_tag(
                tag, head, "tag", "c" * 40, matching_listing
            )
        with self.assertRaises(RuntimeError):
            runner.validate_annotated_execution_tag(
                tag, head, "tag", head, f"{'b' * 40}\trefs/tags/{tag}\n"
            )
        with self.assertRaises(RuntimeError):
            runner.validate_annotated_execution_tag(
                tag,
                head,
                "tag",
                head,
                f"{'b' * 40}\trefs/tags/{tag}\n"
                f"{'c' * 40}\trefs/tags/{tag}^{{}}\n",
            )

    def test_execution_preconditions_query_remote_tag_without_real_tag(self) -> None:
        tag = "v0.4.0-execution-freeze"
        head = "a" * 40
        empty_hash = hashlib.sha256(b"").hexdigest()
        protocol = {
            "output_contract": {
                "execution_freeze_tag": tag,
                "execution_manifest": runner.EXECUTION_MANIFEST_RELATIVE_PATH,
            },
            "data_access": {
                "execution_input_allowlist": [runner.EXECUTION_MANIFEST_RELATIVE_PATH]
            },
        }
        manifest = {
            "protocol_sha256": empty_hash,
            "execution_freeze_tag": tag,
            "bound_input_sha256": {},
        }

        def preconditions_for_listing(remote_listing: str) -> dict:
            def fake_git_text(arguments: list[str]) -> str:
                if arguments == ["status", "--porcelain"]:
                    return ""
                if arguments == ["rev-parse", "HEAD"]:
                    return head
                if arguments == ["cat-file", "-t", f"refs/tags/{tag}"]:
                    return "tag"
                if arguments == ["rev-parse", f"{tag}^{{commit}}"]:
                    return head
                if arguments[0] == "ls-remote":
                    return remote_listing
                self.fail(f"Unexpected Git text query: {arguments}")

            with (
                patch.object(runner, "git_text", side_effect=fake_git_text),
                patch.object(
                    runner,
                    "ensure_allowlisted_inputs",
                    return_value={runner.EXECUTION_MANIFEST_RELATIVE_PATH: empty_hash},
                ),
                patch.object(runner, "read_execution_manifest", return_value=manifest),
                patch.object(runner, "source_sha256", return_value=empty_hash),
                patch.object(runner, "git_bytes", return_value=b""),
            ):
                return runner.ensure_execution_preconditions(protocol)

        with self.assertRaises(RuntimeError):
            preconditions_for_listing("")
        with self.assertRaises(RuntimeError):
            preconditions_for_listing(
                f"{'b' * 40}\trefs/tags/{tag}\n"
                f"{'c' * 40}\trefs/tags/{tag}^{{}}\n"
            )
        preconditions = preconditions_for_listing(
            f"{'b' * 40}\trefs/tags/{tag}\n"
            f"{head}\trefs/tags/{tag}^{{}}\n"
        )
        self.assertEqual(head, preconditions["remote_execution_tag_commit"])

    def test_run_once_validates_before_creating_an_attempt_record(self) -> None:
        protocol = miniature_protocol()

        with (
            patch.object(
                runner,
                "ensure_execution_preconditions",
                side_effect=RuntimeError("frozen execution is unavailable"),
            ),
            patch.object(runner, "acquire_attempt") as acquire_attempt,
        ):
            with self.assertRaisesRegex(RuntimeError, "frozen execution is unavailable"):
                runner.run_once(protocol)
        acquire_attempt.assert_not_called()

if __name__ == "__main__":
    unittest.main()
