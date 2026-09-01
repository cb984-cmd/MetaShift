import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_v04_identifiability_benchmark as runner
from scripts import verify_v04_identifiability_results as verifier


ROOT = Path(__file__).resolve().parents[1]


def miniature_protocol() -> dict:
    protocol = copy.deepcopy(
        json.loads(
            (ROOT / "configs" / "v04_identifiability_protocol.json").read_text(
                encoding="utf-8"
            )
        )
    )
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
    protocol["output_contract"]["execution_freeze_tag"] = "test-tag"
    protocol["data_access"]["execution_input_allowlist"] = []
    return protocol


class V04ResultsVerifierTests(unittest.TestCase):
    def test_pre_execution_verifier_contract_is_complete(self) -> None:
        report = verifier.build_pre_execution_report()

        self.assertTrue(report["all_checks_passed"])
        self.assertEqual(4, len(report["checks"]))

    def test_tagged_authority_requires_remote_annotated_source_hashes(self) -> None:
        tag = "v0.4.1-execution-freeze"
        commit = "a" * 40
        protocol = {
            "output_contract": {"execution_freeze_tag": tag},
            "data_access": {
                "execution_input_allowlist": [
                    "configs/v04_identifiability_execution_manifest.json",
                    "configs/v04_identifiability_protocol.json",
                    "scripts/frozen_runner.py",
                ]
            },
        }
        protocol_bytes = json.dumps(protocol).encode("utf-8")
        runner_bytes = b"frozen runner source"
        manifest = {
            "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
            "bound_input_sha256": {
                "configs/v04_identifiability_protocol.json": hashlib.sha256(
                    protocol_bytes
                ).hexdigest(),
                "scripts/frozen_runner.py": hashlib.sha256(runner_bytes).hexdigest(),
            },
        }
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        remote_listing = (
            f"{'b' * 40}\trefs/tags/{tag}\n"
            f"{commit}\trefs/tags/{tag}^{{}}\n"
        )

        def fake_git_bytes(arguments: list[str]) -> bytes:
            if arguments == ["cat-file", "-t", f"refs/tags/{tag}"]:
                return b"tag\n"
            if arguments == ["rev-parse", f"{tag}^{{commit}}"]:
                return f"{commit}\n".encode("ascii")
            if arguments[0] == "ls-remote":
                return remote_listing.encode("ascii")
            if arguments == [
                "show",
                f"{tag}:configs/v04_identifiability_protocol.json",
            ]:
                return protocol_bytes
            if arguments == [
                "show",
                f"{tag}:configs/v04_identifiability_execution_manifest.json",
            ]:
                return manifest_bytes
            if arguments == ["show", f"{tag}:scripts/frozen_runner.py"]:
                return runner_bytes
            self.fail(f"Unexpected Git query: {arguments}")

        with patch.object(verifier, "git_bytes", side_effect=fake_git_bytes):
            tagged_protocol, tagged_manifest, provenance = verifier.tagged_execution_authority(
                tag, verify_current_checkout=False
            )

        self.assertEqual(protocol, tagged_protocol)
        self.assertEqual(manifest, tagged_manifest)
        self.assertEqual(commit, provenance["execution_git_commit"])
        self.assertEqual(
            hashlib.sha256(runner_bytes).hexdigest(),
            provenance["allowed_input_hashes"]["scripts/frozen_runner.py"],
        )

    def test_miniature_result_bundle_recomputes_all_post_execution_checks(self) -> None:
        protocol = miniature_protocol()
        manifest = {"bound_input_sha256": {}}
        provenance = {
            "execution_git_commit": "a" * 40,
            "protocol_sha256": "b" * 64,
            "execution_manifest_sha256": "c" * 64,
            "allowed_input_hashes": {},
        }
        core = runner.generate_core_rows(protocol, "test-tag")
        thresholds = runner.calibration_thresholds(core, protocol)
        core = runner.apply_predictions(core, thresholds)
        metrics = runner.summarize_evaluation(core, thresholds, protocol)
        bootstrap = runner.bootstrap_evaluation(core, thresholds, protocol)
        stress = runner.generate_stress_rows(protocol)
        replayed_core, replayed_thresholds, replayed_stress = (
            verifier.replay_frozen_outputs(protocol)
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory) / "bundle"
            directory.mkdir()
            paths = verifier.output_paths(protocol, directory)
            core.to_csv(paths["v04_core_event_results.csv"], index=False)
            stress.to_csv(paths["v04_stress_results.csv"], index=False)
            paths["v04_core_thresholds.json"].write_text(
                json.dumps(thresholds), encoding="utf-8"
            )
            paths["v04_core_metrics.json"].write_text(
                json.dumps(metrics), encoding="utf-8"
            )
            paths["v04_core_bootstrap.json"].write_text(
                json.dumps(bootstrap), encoding="utf-8"
            )
            payload_names = [
                name
                for name in protocol["output_contract"]["files"]
                if name != "v04_execution_receipt.json"
            ]
            receipt = {
                "state": "completed",
                "protocol_id": protocol["protocol_id"],
                "protocol_freeze_tag": protocol["output_contract"]["protocol_freeze_tag"],
                "execution_tag": "test-tag",
                "execution_git_commit": provenance["execution_git_commit"],
                "remote_execution_tag_commit": provenance["execution_git_commit"],
                "protocol_sha256": provenance["protocol_sha256"],
                "execution_manifest_sha256": provenance["execution_manifest_sha256"],
                "allowed_input_hashes": {},
                "output_hashes": {
                    name: verifier.sha256(paths[name]) for name in payload_names
                },
                "failure_count": 0,
                "input_count_accounting": {
                    "core_event_count": 30,
                    "stress_event_count": 25,
                    "failure_count": 0,
                },
            }
            paths["v04_execution_receipt.json"].write_text(
                json.dumps(receipt), encoding="utf-8"
            )
            attempt_record = directory.parent / "attempt.json"
            attempt_record.write_text(
                json.dumps(
                    {
                        "state": "completed",
                        "execution_receipt_sha256": verifier.sha256(
                            paths["v04_execution_receipt.json"]
                        ),
                        "execution_tag": "test-tag",
                        "execution_git_commit": provenance["execution_git_commit"],
                        "protocol_sha256": provenance["protocol_sha256"],
                        "execution_manifest_sha256": provenance[
                            "execution_manifest_sha256"
                        ],
                    }
                ),
                encoding="utf-8",
            )

            checks = verifier.build_bundle_checks(
                protocol,
                manifest,
                directory,
                attempt_record,
                provenance,
                replayed_core,
                replayed_thresholds,
                replayed_stress,
            )
            metrics["selective_scope"]["0.75"]["coverage"] = 0.0
            paths["v04_core_metrics.json"].write_text(
                json.dumps(metrics), encoding="utf-8"
            )
            receipt["output_hashes"]["v04_core_metrics.json"] = verifier.sha256(
                paths["v04_core_metrics.json"]
            )
            paths["v04_execution_receipt.json"].write_text(
                json.dumps(receipt), encoding="utf-8"
            )
            attempt_record.write_text(
                json.dumps(
                    {
                        "state": "completed",
                        "execution_receipt_sha256": verifier.sha256(
                            paths["v04_execution_receipt.json"]
                        ),
                        "execution_tag": "test-tag",
                        "execution_git_commit": provenance["execution_git_commit"],
                        "protocol_sha256": provenance["protocol_sha256"],
                        "execution_manifest_sha256": provenance[
                            "execution_manifest_sha256"
                        ],
                    }
                ),
                encoding="utf-8",
            )
            corrupted_checks = verifier.build_bundle_checks(
                protocol,
                manifest,
                directory,
                attempt_record,
                provenance,
                replayed_core,
                replayed_thresholds,
                replayed_stress,
            )

        self.assertTrue(
            all(check["passed"] for check in checks),
            [check["name"] for check in checks if not check["passed"]],
        )
        self.assertEqual(9, len(checks))
        self.assertFalse(
            next(
                check["passed"]
                for check in corrupted_checks
                if check["name"] == "evaluation_scope_risk_coverage_and_metrics"
            )
        )


if __name__ == "__main__":
    unittest.main()
