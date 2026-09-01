import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from scripts import run_v05_answerability_frontier as runner


ROOT = Path(__file__).resolve().parents[1]


def miniature_protocol() -> dict:
    protocol = json.loads(
        (ROOT / "configs" / "v05_answerability_protocol.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = copy.deepcopy(protocol)
    protocol["synthetic_panel"]["component_counts"] = {
        "calibration": 2,
        "evaluation": 3,
    }
    cells = protocol["full_cartesian_grid"]["cells_per_component"]
    protocol["expected_accounting"]["pair_rows"] = {
        "calibration": 2 * cells,
        "evaluation": 3 * cells,
        "total": 5 * cells,
    }
    protocol["expected_accounting"]["scope_arm_events"] = {
        "calibration": 4 * cells,
        "evaluation": 6 * cells,
        "total": 10 * cells,
    }
    q0_cells = cells // 5
    protocol["expected_accounting"]["q0_pair_rows"] = {
        "calibration": 2 * q0_cells,
        "evaluation": 3 * q0_cells,
        "total": 5 * q0_cells,
    }
    protocol["reporting"]["cluster_bootstrap"]["repetitions"] = 5
    return protocol


class V05ExecutionContractTests(unittest.TestCase):
    def test_component_generation_is_deterministic_and_bounded(self) -> None:
        protocol = miniature_protocol()
        first = runner.generate_component(protocol, "calibration", 0)
        second = runner.generate_component(protocol, "calibration", 0)

        np.testing.assert_array_equal(first.common, second.common)
        np.testing.assert_array_equal(first.target_unit_noise, second.target_unit_noise)
        np.testing.assert_array_equal(first.donor_unit_noise, second.donor_unit_noise)
        self.assertEqual(300, len(first.index))
        self.assertEqual((300, 4), first.donor_unit_noise.shape)

    def test_complete_miniature_grid_preserves_target_and_q0_identity(self) -> None:
        protocol = miniature_protocol()
        component = runner.generate_component(protocol, "calibration", 0)
        rows = runner.rows_for_component(protocol, component, "test-tag")

        self.assertEqual(640, len(rows))
        q0 = [row for row in rows if row["nominal_q"] == 0.0]
        self.assertEqual(128, len(q0))
        self.assertTrue(all(row["target_identity"] for row in rows))
        self.assertTrue(all(row["comparative_observation_identity"] for row in q0))
        self.assertTrue(
            all(
                row["local_envelope_satisfied"]
                and row["shared_envelope_satisfied"]
                for row in rows
            )
        )
        self.assertTrue(
            all(
                (
                    not row["certificate_answered"]
                    or (
                        row["certificate_local_prediction"] == "local"
                        and row["certificate_shared_prediction"] == "shared"
                    )
                )
                for row in rows
            )
        )
        self.assertTrue(
            all(
                row["certificate_abstention_reason"] == "q0_observational_identity"
                for row in q0
            )
        )
        grouped = {}
        for row in rows:
            grouped.setdefault(row["target_group_id"], set()).add(
                row["local_target_sha256"]
            )
        self.assertTrue(all(len(digests) == 1 for digests in grouped.values()))

    def test_calibration_does_not_accept_evaluation_rows(self) -> None:
        protocol = miniature_protocol()
        evaluation = runner.generate_pair_results(protocol, "evaluation", "test-tag")

        with self.assertRaisesRegex(ValueError, "only calibration rows"):
            runner.calibration_policies(evaluation, protocol)

    def test_calibration_policies_apply_without_fitting_on_evaluation(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.generate_pair_results(protocol, "evaluation", "test-tag")
        applied = runner.apply_policies(evaluation, policies, protocol)

        self.assertEqual("calibration", policies["selection_split"])
        self.assertEqual(len(evaluation), len(applied))
        self.assertIn("confidence_alpha_0_05_local_answered", applied.columns)
        self.assertFalse(
            applied["confidence_alpha_0_05_local_answered"].isna().any()
        )

    def test_metrics_frontier_and_certificate_tables_are_complete(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.apply_policies(
            runner.generate_pair_results(protocol, "evaluation", "test-tag"),
            policies,
            protocol,
        )
        metrics = runner.policy_metrics(evaluation, protocol)
        frontier = runner.answerability_frontier(metrics, protocol)
        certificate = runner.certificate_validity(evaluation)
        failures = runner.failure_mode_map(evaluation)

        self.assertEqual(20 * 7, len(metrics))
        self.assertEqual(20 * 4 * 3, len(frontier))
        self.assertEqual(20, len(certificate))
        self.assertEqual(640, len(failures))
        q0 = frontier.loc[
            (frontier["group_type"] == "nominal_q")
            & (frontier["group_value"] == "q0.00")
            & (frontier["channel"] == "target_only")
        ]
        self.assertTrue((q0["frontier_coverage"] == 0.0).all())
        comparative = frontier.loc[frontier["channel"] == "comparative"]
        self.assertTrue((comparative["candidate_policy_count"] == 5).all())

    def test_frontier_considers_confidence_policies_calibrated_at_other_tolerances(
        self,
    ) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.apply_policies(
            runner.generate_pair_results(protocol, "evaluation", "test-tag"),
            policies,
            protocol,
        )
        metrics = runner.policy_metrics(evaluation, protocol)
        overall = (metrics["group_type"] == "overall") & (
            metrics["group_value"] == "all"
        )
        for calibration_alpha, coverage, error in (
            (0.01, 0.10, 0.00),
            (0.05, 0.90, 0.05),
            (0.10, 0.20, 0.00),
            (0.20, 0.30, 0.20),
        ):
            selected = (
                overall
                & (metrics["policy"] == "confidence_selective")
                & np.isclose(metrics["alpha"].astype(float), calibration_alpha)
            )
            metrics.loc[selected, "coverage"] = coverage
            metrics.loc[selected, "conditional_error"] = error
        forced = overall & (metrics["policy"] == "comparative_forced")
        metrics.loc[forced, "coverage"] = 0.10
        metrics.loc[forced, "conditional_error"] = 0.50

        frontier = runner.answerability_frontier(metrics, protocol)
        frontier_overall = (frontier["group_type"] == "overall") & (
            frontier["group_value"] == "all"
        )
        observed = frontier.loc[
            frontier_overall
            & np.isclose(frontier["alpha"].astype(float), 0.10)
            & (frontier["channel"] == "comparative")
        ].iloc[0]

        self.assertAlmostEqual(0.90, float(observed["frontier_coverage"]))
        self.assertIn(
            "confidence_selective@calibration_alpha=0.05",
            str(observed["qualifying_policies"]),
        )

    def test_vectorized_component_bootstrap_matches_reference_point_estimates(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.apply_policies(
            runner.generate_pair_results(protocol, "evaluation", "test-tag"),
            policies,
            protocol,
        )
        component_metrics = runner.component_policy_metrics(evaluation, protocol)
        vectorized = runner.component_bootstrap(component_metrics, protocol)
        reference = runner._component_bootstrap_dataframe_reference(
            component_metrics, protocol
        )

        merged = vectorized.merge(
            reference,
            on=["metric", "alpha"],
            suffixes=("_vectorized", "_reference"),
        )
        np.testing.assert_allclose(
            merged["point_estimate_vectorized"].to_numpy(dtype=float),
            merged["point_estimate_reference"].to_numpy(dtype=float),
            equal_nan=True,
        )

    def test_accounting_rejects_stale_or_incomplete_grid(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.apply_policies(
            runner.generate_pair_results(protocol, "evaluation", "test-tag"),
            policies,
            protocol,
        )
        combined = runner._expected_schema_frame(
            runner.pd.concat([runner.apply_policies(calibration, policies, protocol), evaluation]),
            protocol,
        )
        report = runner._accounting_report(combined, protocol)
        runner._assert_accounting(report)

        broken = combined.iloc[1:].copy()
        with self.assertRaisesRegex(ValueError, "Pair-row accounting"):
            runner._assert_accounting(runner._accounting_report(broken, protocol))

    def test_accounting_rejects_target_identity_violation(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.apply_policies(
            runner.generate_pair_results(protocol, "evaluation", "test-tag"),
            policies,
            protocol,
        )
        combined = runner._expected_schema_frame(
            runner.pd.concat([runner.apply_policies(calibration, policies, protocol), evaluation]),
            protocol,
        )
        broken = combined.copy()
        broken.loc[broken.index[0], "shared_target_sha256"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "target-identity"):
            runner._assert_accounting(runner._accounting_report(broken, protocol))

    def test_declared_pair_schema_rejects_an_omitted_policy_column(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        applied = runner.apply_policies(calibration, policies, protocol)

        with self.assertRaisesRegex(ValueError, "miss declared schema columns"):
            runner._expected_schema_frame(
                applied.drop(columns="confidence_alpha_0_20_shared_prediction"),
                protocol,
            )

    def test_policy_application_cannot_fit_on_evaluation(self) -> None:
        protocol = miniature_protocol()
        calibration = runner.generate_pair_results(protocol, "calibration", "test-tag")
        policies = runner.calibration_policies(calibration, protocol)
        evaluation = runner.generate_pair_results(protocol, "evaluation", "test-tag")

        with patch.object(runner, "select_macro_f1_threshold") as selected:
            runner.apply_policies(evaluation, policies, protocol)
        selected.assert_not_called()

    def test_remote_tag_parser_rejects_missing_or_mismatched_refs(self) -> None:
        tag = "v0.5.0-answerability-freeze"
        head = "a" * 40
        listing = (
            f"{'b' * 40}\trefs/tags/{tag}\n"
            f"{head}\trefs/tags/{tag}^{{}}\n"
        )

        self.assertEqual(
            head,
            runner.validate_annotated_execution_tag(tag, head, "tag", head, listing),
        )
        self.assertEqual("b" * 40, runner.remote_tag_object_id(listing, tag))
        with self.assertRaises(RuntimeError):
            runner.validate_annotated_execution_tag(tag, head, "commit", head, listing)
        with self.assertRaises(RuntimeError):
            runner.remote_peeled_tag_commit("", tag)
        with self.assertRaises(RuntimeError):
            runner.remote_tag_object_id("", tag)

    def test_remote_execution_claim_is_pushed_before_a_local_attempt(self) -> None:
        claim_tag = "v0.5.0-answerability-execution-claim"
        commit = "a" * 40
        protocol = {"output_contract": {"execution_claim_tag": claim_tag}}
        preconditions = {
            "execution_git_commit": commit,
            "execution_tag": "v0.5.0-answerability-freeze",
            "protocol_sha256": "b" * 64,
            "execution_manifest_sha256": "c" * 64,
            "allowed_input_hashes": {"metashift/answerability.py": "d" * 64},
            "runtime_environment": {"python_version": "3.13.0"},
        }
        claimed = False

        def fake_git_text(arguments: list[str]) -> str:
            nonlocal claimed
            if arguments[0] == "ls-remote":
                if not claimed:
                    return ""
                return (
                    f"{'c' * 40}\trefs/tags/{claim_tag}\n"
                    f"{commit}\trefs/tags/{claim_tag}^{{}}\n"
                )
            if arguments == ["cat-file", "-t", f"refs/tags/{claim_tag}"]:
                return "tag"
            if arguments == ["rev-parse", f"{claim_tag}^{{commit}}"]:
                return commit
            if arguments == ["rev-parse", claim_tag]:
                return "c" * 40
            self.fail(f"Unexpected Git query: {arguments}")

        def fake_check_call(arguments: list[str], **_: object) -> None:
            nonlocal claimed
            if arguments[:3] == ["git", "tag", "-a"]:
                self.assertEqual(claim_tag, arguments[3])
                self.assertIn("allowlisted_input_hashes_sha256=", arguments[-1])
                self.assertIn("runtime_environment_sha256=", arguments[-1])
                return
            if arguments[:4] == ["git", "push", "--atomic", "origin"]:
                self.assertEqual(
                    f"refs/tags/{claim_tag}:refs/tags/{claim_tag}", arguments[4]
                )
                claimed = True
                return
            self.fail(f"Unexpected Git command: {arguments}")

        with (
            patch.object(runner.subprocess, "run", return_value=Mock(returncode=1)),
            patch.object(runner.subprocess, "check_call", side_effect=fake_check_call),
            patch.object(runner, "git_text", side_effect=fake_git_text),
        ):
            result = runner.acquire_remote_execution_claim(protocol, preconditions)

        self.assertTrue(claimed)
        self.assertEqual(claim_tag, result["execution_claim_tag"])
        self.assertEqual(commit, result["remote_execution_claim_commit"])
        self.assertEqual("c" * 40, result["execution_claim_tag_object"])
        self.assertEqual(
            runner.canonical_json_sha256(preconditions["allowed_input_hashes"]),
            result["execution_claim_input_bundle_sha256"],
        )

    def test_run_once_validates_before_acquiring_an_attempt(self) -> None:
        protocol = miniature_protocol()

        with (
            patch.object(
                runner,
                "ensure_execution_preconditions",
                side_effect=RuntimeError("freeze unavailable"),
            ),
            patch.object(runner, "acquire_attempt") as acquire_attempt,
        ):
            with self.assertRaisesRegex(RuntimeError, "freeze unavailable"):
                runner.run_once(protocol)
        acquire_attempt.assert_not_called()

    def test_attempt_setup_failure_preserves_claimed_attempt_record(self) -> None:
        protocol = {
            "output_contract": {
                "directory": "ignored-output",
                "attempt_record": "ignored-attempt",
                "files": [],
            }
        }
        preconditions = {
            "execution_git_commit": "a" * 40,
            "execution_claim_tag": "test-claim",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            directory = temporary / "output"
            attempt = temporary / "attempt.json"

            def fake_project_path(relative_path: str) -> Path:
                if relative_path == "ignored-output":
                    return directory
                if relative_path == "ignored-attempt":
                    return attempt
                self.fail(f"Unexpected protocol path: {relative_path}")

            def simulate_output_race(path: Path) -> None:
                path.mkdir()
                raise FileExistsError("simulated output-directory race")

            with (
                patch.object(runner, "project_path", side_effect=fake_project_path),
                patch.object(runner, "_output_paths", return_value={}),
                patch.object(
                    runner, "_create_output_directory", side_effect=simulate_output_race
                ),
            ):
                with self.assertRaisesRegex(FileExistsError, "simulated output"):
                    runner.acquire_attempt(protocol, preconditions)

            record = json.loads(attempt.read_text(encoding="utf-8"))
            self.assertEqual("claim_acquired_setup_failed", record["state"])
            self.assertEqual("FileExistsError", record["error_type"])
            self.assertEqual("test-claim", record["execution_claim_tag"])

    def test_execution_preconditions_reject_stale_source_hash(self) -> None:
        tag = "v0.5.0-answerability-freeze"
        head = "a" * 40
        protocol_hash = "b" * 64
        manifest_hash = "c" * 64
        source_hash = "d" * 64
        protocol = {
            "output_contract": {
                "execution_freeze_tag": tag,
                "execution_claim_tag": "v0.5.0-answerability-execution-claim",
            },
            "data_access": {
                "execution_input_allowlist": [
                    runner.EXECUTION_MANIFEST_RELATIVE_PATH,
                    "metashift/answerability.py",
                ]
            },
        }
        manifest = {
            "protocol_sha256": protocol_hash,
            "execution_freeze_tag": tag,
            "bound_input_sha256": {"metashift/answerability.py": "e" * 64},
        }
        remote_listing = (
            f"{'f' * 40}\trefs/tags/{tag}\n"
            f"{head}\trefs/tags/{tag}^{{}}\n"
        )

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
                if any(
                    "v0.5.0-answerability-execution-claim" in argument
                    for argument in arguments
                ):
                    return ""
                return remote_listing
            self.fail(f"Unexpected Git query: {arguments}")

        with (
            patch.object(runner, "_run_pre_outcome_verifier"),
            patch.object(runner, "validate_runtime_environment", return_value={}),
            patch.object(runner, "ensure_execution_claim_absent"),
            patch.object(runner, "git_text", side_effect=fake_git_text),
            patch.object(
                runner,
                "ensure_allowlisted_inputs",
                return_value={
                    runner.EXECUTION_MANIFEST_RELATIVE_PATH: manifest_hash,
                    "metashift/answerability.py": source_hash,
                },
            ),
            patch.object(runner, "read_execution_manifest", return_value=manifest),
            patch.object(runner, "source_sha256", return_value=protocol_hash),
        ):
            with self.assertRaisesRegex(RuntimeError, "differs from its manifest"):
                runner.ensure_execution_preconditions(protocol)

    def test_run_once_writes_complete_miniature_bundle_to_temporary_paths(self) -> None:
        protocol = miniature_protocol()
        preconditions = {
            "execution_git_commit": "a" * 40,
            "execution_tag": "test-tag",
            "remote_execution_tag_commit": "a" * 40,
            "protocol_sha256": "b" * 64,
            "execution_manifest_sha256": "c" * 64,
            "allowed_input_hashes": {},
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            paths = {
                name: temporary / name
                for name in protocol["output_contract"]["files"]
            }
            attempt = temporary / "attempt.json"
            attempt.write_text(json.dumps({"state": "started"}), encoding="utf-8")

            with (
                patch.object(
                    runner, "ensure_execution_preconditions", return_value=preconditions
                ),
                patch.object(
                    runner,
                    "acquire_remote_execution_claim",
                    return_value={
                        "execution_claim_tag": "test-claim",
                        "remote_execution_claim_commit": "a" * 40,
                    },
                ),
                patch.object(
                    runner, "acquire_attempt", return_value=(temporary, attempt)
                ),
                patch.object(
                    runner,
                    "_output_paths",
                    return_value=paths,
                ),
                patch.object(
                    runner,
                    "semantic_crosscheck",
                    return_value={
                        "checked_grid_cells": 640,
                        "maximum_absolute_difference": 0.0,
                        "tolerance": 1e-12,
                        "passed": True,
                    },
                ),
            ):
                result = runner.run_once(protocol)

            self.assertEqual("completed", result["state"])
            self.assertTrue(all(path.is_file() for path in paths.values()))
            receipt = json.loads(
                paths["v05_execution_receipt.json"].read_text(encoding="utf-8")
            )
            self.assertEqual(7, len(receipt["output_hashes"]))
            stored_attempt = json.loads(attempt.read_text(encoding="utf-8"))
            self.assertEqual("completed", stored_attempt["state"])


if __name__ == "__main__":
    unittest.main()
