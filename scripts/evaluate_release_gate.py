"""Write the machine-readable MetaShift-Bench release checklist."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


ARTIFACTS = Path("artifacts")
RESULTS = Path("results")
CONFIG_PATH = Path("configs/benchmark_release_v1.json")


def exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
    ).strip()


def main() -> None:
    checks = []
    manifest_path = ARTIFACTS / "data_gate/data_manifest.csv"
    if exists(manifest_path):
        manifest = pd.read_csv(manifest_path)
        checks.append(
            check(
                "88101_data_manifest",
                len(manifest) == 7
                and manifest["sha256"].notna().all()
                and manifest["csv_data_rows"].gt(0).all(),
                f"{len(manifest)} source archives with hashes and CSV row counts",
            )
        )
    else:
        checks.append(check("88101_data_manifest", False, "Missing data manifest"))

    stable_manifest_path = ARTIFACTS / "stable_synthetic_case_manifest.json"
    if exists(stable_manifest_path) and exists(CONFIG_PATH):
        stable_manifest = json.loads(stable_manifest_path.read_text(encoding="utf-8"))
        frozen_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        checks.append(
            check(
                "frozen_stable_case_manifest",
                stable_manifest["case_and_donor_sha256"]
                == frozen_config["stable_synthetic_cases"]["case_and_donor_sha256"],
                "Generated stable-case manifest matches the frozen configuration hash.",
            )
        )
    else:
        checks.append(
            check(
                "frozen_stable_case_manifest",
                False,
                "Missing stable-case manifest or frozen benchmark configuration.",
            )
        )

    figure_manifest = Path("figures/figure_manifest.csv")
    checks.append(
        check(
            "saved_result_figures",
            exists(figure_manifest) and len(pd.read_csv(figure_manifest)) >= 6,
            "Figures are generated solely from saved result artifacts.",
        )
    )

    real_audit_path = ARTIFACTS / "real_transition_88101_event_audit.csv"
    method_path = ARTIFACTS / "real_transition_88101_method_results.csv"
    if exists(real_audit_path) and exists(method_path):
        audit = pd.read_csv(real_audit_path)
        methods = pd.read_csv(method_path)
        required_methods = {
            "before_after_median",
            "bayesian_mean_shift",
            "cusum",
            "rolling_mad",
            "pelt",
            "nearest_neighbor_did",
            "standard_synthetic_control",
            "metashift_v1_fixed",
        }
        checks.append(
            check(
                "full_88101_anchor_audit",
                len(audit) == 563
                and required_methods.issubset(set(methods["method"])),
                f"{len(audit)} anchors and {methods['method'].nunique()} comparison methods",
            )
        )
    else:
        checks.append(check("full_88101_anchor_audit", False, "Missing real audit files"))

    synthetic_path = ARTIFACTS / "stable_synthetic_stable_full_v1_event_results.csv"
    metric_path = ARTIFACTS / "stable_synthetic_stable_full_v1_metrics.csv"
    bootstrap_path = ARTIFACTS / "stable_synthetic_stable_full_v1_bootstrap.csv"
    if exists(synthetic_path) and exists(metric_path) and exists(bootstrap_path):
        synthetic = pd.read_csv(synthetic_path)
        evaluation = synthetic.loc[synthetic["split"] == "evaluation"]
        counts = evaluation.loc[
            evaluation["method"] == "standard_synthetic_control"
        ].groupby("perturbation").size()
        required_perturbations = {
            "additive_step",
            "proportional_step",
            "gradual_drift",
            "temporary_step",
            "variance_increase",
            "regional_additive_step",
            "regional_proportional_step",
            "regional_gradual_drift",
            "regional_temporary_step",
            "regional_variance_increase",
        }
        checks.append(
            check(
                "stable_six_family_synthetic_benchmark",
                required_perturbations.issubset(set(counts.index))
                and all(counts[name] >= 200 for name in required_perturbations),
                f"{len(evaluation)} held-out synthetic method rows; minimum per perturbation="
                f"{int(counts.min()) if len(counts) else 0}",
            )
        )
    else:
        checks.append(
            check(
                "stable_six_family_synthetic_benchmark",
                False,
                "Missing synthetic metrics or bootstrap artifacts",
            )
        )

    ablation_path = ARTIFACTS / "reliability_ablation_stable_full_v1_metrics.csv"
    checks.append(
        check(
            "key_reliability_ablations",
            exists(ablation_path)
            and len(pd.read_csv(ablation_path)["method"].unique()) >= 8,
            "Reliability prior, distance, correlation, coverage, and regularization ablations",
        )
    )

    time_path = ARTIFACTS / "time_placebo_summary.csv"
    donor_path = ARTIFACTS / "donor_as_treated_placebos.csv"
    permutation_path = ARTIFACTS / "time_placebo_date_permutations.csv"
    regional_available = exists(synthetic_path)
    if exists(time_path) and exists(donor_path) and exists(permutation_path):
        time_summary = pd.read_csv(time_path)
        donor = pd.read_csv(donor_path)
        permutations = pd.read_csv(permutation_path)
        checks.append(
            check(
                "placebo_suite",
                (time_summary["status"] == "complete").any()
                and len(donor) > 0
                and len(permutations) >= 200
                and regional_available,
                f"time={len(time_summary)}, donor={len(donor)}, date_permutations={len(permutations)}",
            )
        )
    else:
        checks.append(check("placebo_suite", False, "Missing one or more placebo artifacts"))

    external_path = ARTIFACTS / "external_validation_evidence.csv"
    if exists(external_path):
        external = pd.read_csv(external_path)
        has_poc = (
            external["evidence_source"].eq("same_site_alternate_poc").sum() >= 1
        )
        checks.append(
            check(
                "graded_external_validation",
                has_poc,
                "POC evidence is present; QA limitations must remain disclosed.",
            )
        )
    else:
        checks.append(
            check("graded_external_validation", False, "Missing POC/QA evidence summary")
        )

    sensitivity_manifest = ARTIFACTS / "data_gate_88502/data_manifest.csv"
    sensitivity_audit = ARTIFACTS / "real_transition_88502_event_audit.csv"
    if exists(sensitivity_manifest) and exists(sensitivity_audit):
        audit_88502 = pd.read_csv(sensitivity_audit)
        checks.append(
            check(
                "independent_88502_sensitivity",
                len(audit_88502) == 34,
                f"{len(audit_88502)} separately processed 88502 anchors",
            )
        )
    else:
        checks.append(
            check("independent_88502_sensitivity", False, "Missing 88502 artifacts")
        )

    reproducibility_files = [
        Path("REPRODUCIBILITY.md"),
        Path("MODEL_DECISION.md"),
        Path("configs/benchmark_release_v1.json"),
    ]
    checks.append(
        check(
            "reproducibility_documentation",
            all(exists(path) for path in reproducibility_files),
            "Required protocol, decision, and reconstruction documents",
        )
    )

    reproducibility_comparison = RESULTS / "reproducibility_comparison.json"
    if exists(reproducibility_comparison):
        comparison = json.loads(reproducibility_comparison.read_text(encoding="utf-8"))
        checks.append(
            check(
                "two_environment_reproduction",
                bool(comparison.get("all_core_artifacts_match")),
                "Two independently captured core-result hash sets must match.",
            )
        )
    else:
        checks.append(
            check(
                "two_environment_reproduction",
                False,
                "Awaiting two-environment core-result hash comparison.",
            )
        )

    output = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "route": "MetaShift-Bench",
        "algorithm_superiority_claim": False,
        "all_checks_passed": all(item["passed"] for item in checks),
        "checks": checks,
        "interpretation_boundary": (
            "A Method Code transition is a metadata anchor, not a confirmed "
            "instrument fault or causal measurement bias."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS / "release_gate.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
