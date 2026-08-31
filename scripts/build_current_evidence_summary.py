"""Build or verify the tracked v2 frozen-evidence summary from local artifacts.

The tracked summary is the CI-safe public data contract. This script is its
local Layer-2 verifier: it recomputes every headline count and listed source
hash from generated evidence artifacts, which are intentionally not tracked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
FROZEN_TAG = "v0.3.2-evidence-final"
RELEASE_URL = (
    "https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final"
)

SOURCE_PATHS = (
    "artifacts/data_gate/summary.json",
    "artifacts/stable_synthetic_case_manifest.json",
    "artifacts/stable_synthetic_case_split_audit.json",
    "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
    "artifacts/stable_synthetic_stable_full_v2_bootstrap.csv",
    "artifacts/benchmark_ablation_alignment_stable_full_v2.json",
    "artifacts/real_transition_88101_event_audit.csv",
    "artifacts/real_transition_88101_event_intervals.csv",
    "artifacts/real_transition_88101_nested_selection_intervals.csv",
    "artifacts/leave_one_donor_out_summary.csv",
    "artifacts/time_placebo_summary.csv",
    "artifacts/time_placebo_date_permutations.csv",
    "artifacts/donor_as_treated_placebos.csv",
    "artifacts/real_transition_88101_evidence_tier_summary.json",
    "artifacts/synthetic_interval_coverage_v2_summary.csv",
    "artifacts/hourly_poc_validation_summary.csv",
    "artifacts/external_document_review_summary.json",
    "artifacts/data_gate_88502/summary.json",
    "artifacts/real_transition_88502_event_audit.csv",
    "results/release_gate.json",
    "results/document_consistency.json",
    "results/manuscript_number_verification.json",
    "results/reproducibility_comparison.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or verify configs/current_evidence_summary_v2.json."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--write",
        action="store_true",
        help="Write the tracked summary using the frozen local artifacts.",
    )
    action.add_argument(
        "--check",
        action="store_true",
        help="Fail unless the tracked summary equals the frozen local artifacts.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_tag_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-list", "-n", "1", FROZEN_TAG],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def require_matching_frozen_provenance(
    frozen_commit: str, release_gate: dict[str, Any], document_report: dict[str, Any],
    manuscript_report: dict[str, Any], reproducibility: dict[str, Any],
) -> None:
    report_commits = {
        "results/release_gate.json": release_gate["git_commit"],
        "results/document_consistency.json": document_report["git_commit"],
        "results/manuscript_number_verification.json": manuscript_report["git_commit"],
        "results/reproducibility_comparison.json:first_git_commit": reproducibility[
            "first_git_commit"
        ],
        "results/reproducibility_comparison.json:second_git_commit": reproducibility[
            "second_git_commit"
        ],
    }
    mismatches = {
        path: commit for path, commit in report_commits.items() if commit != frozen_commit
    }
    if mismatches:
        rendered = ", ".join(f"{path}={commit}" for path, commit in mismatches.items())
        raise RuntimeError(
            f"Frozen tag {FROZEN_TAG} resolves to {frozen_commit}, but provenance "
            f"artifacts disagree: {rendered}"
        )


def source_records() -> list[dict[str, object]]:
    records = []
    for relative_path in SOURCE_PATHS:
        path = ROOT / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Required frozen evidence source is missing: {path}")
        records.append(
            {
                "path": relative_path,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return records


def integer(value: object) -> int:
    return int(value)


def build_summary() -> dict[str, object]:
    data_gate = load_json("artifacts/data_gate/summary.json")
    case_manifest = load_json("artifacts/stable_synthetic_case_manifest.json")
    split_audit = load_json("artifacts/stable_synthetic_case_split_audit.json")
    alignment = load_json("artifacts/benchmark_ablation_alignment_stable_full_v2.json")
    tiers = load_json("artifacts/real_transition_88101_evidence_tier_summary.json")
    external_review = load_json("artifacts/external_document_review_summary.json")
    secondary_gate = load_json("artifacts/data_gate_88502/summary.json")
    release_gate = load_json("results/release_gate.json")
    document_report = load_json("results/document_consistency.json")
    manuscript_report = load_json("results/manuscript_number_verification.json")
    reproducibility = load_json("results/reproducibility_comparison.json")
    audit = pd.read_csv(ROOT / "artifacts/real_transition_88101_event_audit.csv")
    intervals = pd.read_csv(ROOT / "artifacts/real_transition_88101_event_intervals.csv")
    nested = pd.read_csv(
        ROOT / "artifacts/real_transition_88101_nested_selection_intervals.csv"
    )
    leave_one_out = pd.read_csv(ROOT / "artifacts/leave_one_donor_out_summary.csv")
    time_placebo = pd.read_csv(ROOT / "artifacts/time_placebo_summary.csv")
    date_permutations = pd.read_csv(
        ROOT / "artifacts/time_placebo_date_permutations.csv"
    )
    donor_placebos = pd.read_csv(ROOT / "artifacts/donor_as_treated_placebos.csv")
    coverage = pd.read_csv(ROOT / "artifacts/synthetic_interval_coverage_v2_summary.csv")
    hourly_poc = pd.read_csv(ROOT / "artifacts/hourly_poc_validation_summary.csv")
    secondary_audit = pd.read_csv(
        ROOT / "artifacts/real_transition_88502_event_audit.csv"
    )
    metrics = pd.read_csv(
        ROOT / "artifacts/stable_synthetic_stable_full_v2_metrics.csv"
    )
    bootstrap = pd.read_csv(
        ROOT / "artifacts/stable_synthetic_stable_full_v2_bootstrap.csv"
    )

    frozen_commit = frozen_tag_commit()
    require_matching_frozen_provenance(
        frozen_commit,
        release_gate,
        document_report,
        manuscript_report,
        reproducibility,
    )
    if not (
        release_gate["all_checks_passed"]
        and document_report["all_checks_passed"]
        and manuscript_report["all_numbers_match"]
        and reproducibility["all_core_artifacts_match"]
        and reproducibility["source_commits_match"]
    ):
        raise RuntimeError("Frozen verification reports must all pass before summarizing.")

    complete = audit.loc[audit["audit_status"] == "complete"]
    audit_counts = audit["audit_status"].value_counts()
    conditional = coverage.loc[
        (coverage["interval_type"] == "conditional_block_bootstrap")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].sort_values("method")
    conformal = coverage.loc[
        (coverage["interval_type"] == "split_conformal")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].sort_values("method")
    if len(conditional) != 4 or len(conformal) != 4:
        raise RuntimeError("Expected exactly four aggregate methods for each interval type.")
    aggregate_metrics = metrics.loc[
        metrics["perturbation_family"].isna()
    ].set_index("method")
    paired_bootstrap = bootstrap.set_index("comparison")
    paired_hourly = hourly_poc.loc[
        hourly_poc["status"] == "paired_hourly_pre_post_available"
    ]

    return {
        "schema_version": 2,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "evidence_version": "v0.3.2",
        "release_gate_target_checks": integer(len(release_gate["checks"])),
        "document_consistency_target_checks": integer(len(document_report["checks"])),
        "manuscript_number_target_checks": integer(len(manuscript_report["checks"])),
        "frozen_evidence": {
            "tag": FROZEN_TAG,
            "commit": frozen_commit,
            "release_url": RELEASE_URL,
            "supersedes": ["v0.3.0-distinct-donors", "v0.3.1-evidence-final"],
        },
        "result_label": "stable_full_v2",
        "case_manifest_sha256": case_manifest["case_and_donor_sha256"],
        "geographic_donor_rule": "one_best_poc_per_physical_site",
        "data_gate": {
            "canonical_records": integer(data_gate["canonical_records"]),
            "monitor_series": integer(data_gate["monitor_series"]),
            "eligible_anchors": integer(data_gate["eligible_anchors"]),
            "anchors_with_one_distinct_physical_donor": integer(
                data_gate["anchors_with_one_geographic_control"]
            ),
            "anchors_with_three_distinct_physical_donors": integer(
                data_gate["anchors_with_three_geographic_controls"]
            ),
            "same_site_poc_candidates": integer(data_gate["anchors_with_colocated_control"]),
        },
        "real_event_audit": {
            "total_anchors": integer(len(audit)),
            "complete_comparisons": integer(audit_counts["complete"]),
            "insufficient_geographic_donors": integer(
                audit_counts["insufficient_geographic_donors"]
            ),
            "estimator_input_failure": integer(audit_counts["estimator_input_failure"]),
        },
        "synthetic_benchmark": {
            "case_count": integer(case_manifest["case_count"]),
            "calibration_case_count": integer(case_manifest["calibration_case_count"]),
            "evaluation_case_count": integer(case_manifest["evaluation_case_count"]),
            "all_input_physical_sites_disjoint": bool(
                split_audit["all_input_physical_sites_disjoint"]
            ),
            "standard_synthetic_control": {
                "local_effect_mae_log": float(
                    aggregate_metrics.loc[
                        "standard_synthetic_control", "local_effect_mae_log"
                    ]
                ),
                "average_precision": float(
                    aggregate_metrics.loc[
                        "standard_synthetic_control", "average_precision"
                    ]
                ),
                "macro_f1": float(
                    aggregate_metrics.loc["standard_synthetic_control", "macro_f1"]
                ),
                "regional_false_positive_rate": float(
                    aggregate_metrics.loc[
                        "standard_synthetic_control", "false_positive_rate"
                    ]
                ),
            },
            "cross_validated_metashift": {
                "local_effect_mae_log": float(
                    aggregate_metrics.loc["metashift_v2_cv", "local_effect_mae_log"]
                ),
                "average_precision": float(
                    aggregate_metrics.loc["metashift_v2_cv", "average_precision"]
                ),
                "macro_f1": float(
                    aggregate_metrics.loc["metashift_v2_cv", "macro_f1"]
                ),
                "regional_false_positive_rate": float(
                    aggregate_metrics.loc["metashift_v2_cv", "false_positive_rate"]
                ),
                "paired_mae_difference_vs_standard": float(
                    paired_bootstrap.loc[
                        "metashift_v2_cv minus standard_synthetic_control",
                        "mae_difference_log",
                    ]
                ),
                "paired_mae_difference_95ci": [
                    float(
                        paired_bootstrap.loc[
                            "metashift_v2_cv minus standard_synthetic_control",
                            "bootstrap_95ci_lower",
                        ]
                    ),
                    float(
                        paired_bootstrap.loc[
                            "metashift_v2_cv minus standard_synthetic_control",
                            "bootstrap_95ci_upper",
                        ]
                    ),
                ],
            },
            "fixed_prior_metashift": {
                "local_effect_mae_log": float(
                    aggregate_metrics.loc["metashift_v1_fixed", "local_effect_mae_log"]
                ),
                "average_precision": float(
                    aggregate_metrics.loc["metashift_v1_fixed", "average_precision"]
                ),
                "macro_f1": float(
                    aggregate_metrics.loc["metashift_v1_fixed", "macro_f1"]
                ),
                "regional_false_positive_rate": float(
                    aggregate_metrics.loc[
                        "metashift_v1_fixed", "false_positive_rate"
                    ]
                ),
                "paired_mae_difference_vs_standard": float(
                    paired_bootstrap.loc[
                        "metashift_v1_fixed minus standard_synthetic_control",
                        "mae_difference_log",
                    ]
                ),
                "paired_mae_difference_95ci": [
                    float(
                        paired_bootstrap.loc[
                            "metashift_v1_fixed minus standard_synthetic_control",
                            "bootstrap_95ci_lower",
                        ]
                    ),
                    float(
                        paired_bootstrap.loc[
                            "metashift_v1_fixed minus standard_synthetic_control",
                            "bootstrap_95ci_upper",
                        ]
                    ),
                ],
            },
        },
        "synthetic_alignment": {
            "shared_standard_synthetic_control_rows": integer(
                alignment["comparison_rows"]
            ),
            "tolerance": float(alignment["tolerance"]),
            "all_rows_aligned": bool(alignment["all_rows_aligned"]),
        },
        "evidence_tiers": {
            "supported_candidate_discontinuity": integer(
                tiers["counts"]["supported_candidate_discontinuity"]
            ),
            "not_supported_by_available_evidence": integer(
                tiers["counts"]["not_supported_by_available_evidence"]
            ),
            "inconclusive_insufficient_evidence": integer(
                tiers["counts"]["inconclusive_insufficient_evidence"]
            ),
        },
        "placebos": {
            "time_placebo_rows": integer(len(time_placebo)),
            "complete_with_at_least_50": integer(
                (time_placebo["placebo_count"] >= 50).sum()
            ),
            "complete_with_100": integer((time_placebo["placebo_count"] >= 100).sum()),
            "donor_as_treated_rows": integer(len(donor_placebos)),
            "donor_as_treated_median_standardized_score": float(
                donor_placebos["standardized_score"].median()
            ),
            "date_resamples": integer(len(date_permutations)),
            "date_resampling_upper_tail_probability": float(
                (
                    1
                    + (date_permutations["mean_score_difference"] <= 0).sum()
                )
                / (len(date_permutations) + 1)
            ),
        },
        "real_event_intervals": {
            "fixed_weight_events_by_method": {
                str(method): {
                    "events": integer(len(group)),
                    "excludes_zero": integer(group["ci_excludes_zero"].sum()),
                }
                for method, group in intervals.groupby("method")
            },
            "selection_aware_events": integer(len(nested)),
            "selection_aware_excludes_zero": integer(
                nested["selection_ci_excludes_zero"].sum()
            ),
            "selection_aware_mean_width_log": float(
                (nested["selection_ci95_upper"] - nested["selection_ci95_lower"]).mean()
            ),
            "leave_one_donor_out_complete_events": integer(
                (leave_one_out["summary_status"] == "complete").sum()
            ),
            "leave_one_donor_out_direction_stable_events": integer(
                leave_one_out.loc[
                    leave_one_out["summary_status"] == "complete",
                    "direction_stable_all_donors",
                ].sum()
            ),
        },
        "interval_coverage": {
            "fixed_weight_status": "complete",
            "conditional_bootstrap_nominal_coverage": float(
                conditional["nominal_coverage"].iloc[0]
            ),
            "conditional_bootstrap_95_eval_coverage_range": [
                float(conditional["empirical_coverage"].min()),
                float(conditional["empirical_coverage"].max()),
            ],
            "split_conformal_nominal_coverage": float(
                conformal["nominal_coverage"].iloc[0]
            ),
            "split_conformal_90_eval_coverage_range": [
                float(conformal["empirical_coverage"].min()),
                float(conformal["empirical_coverage"].max()),
            ],
            "evaluation_instances_per_method": integer(
                conditional["event_instances"].iloc[0]
            ),
            "selection_aware_status": "infeasible_within_deadline",
            "selection_aware_protocol": "configs/selection_aware_coverage_protocol_v2.json",
        },
        "external_document_review": {
            "reviewed_events": integer(external_review["reviewed_events"]),
            "site_specific_dated_confirmations": integer(
                external_review["site_specific_dated_confirmations"]
            ),
        },
        "hourly_same_site_poc": {
            "candidate_events": integer(len(hourly_poc)),
            "usable_paired_events": integer(len(paired_hourly)),
            "daily_hourly_direction_agreement": integer(
                paired_hourly["hourly_daily_direction_agreement"].sum()
            ),
        },
        "secondary_88502": {
            "eligible_anchors": integer(secondary_gate["eligible_anchors"]),
            "complete_comparisons": integer(
                (secondary_audit["audit_status"] == "complete").sum()
            ),
        },
        "verification": {
            "release_gate_checks": integer(len(release_gate["checks"])),
            "document_consistency_checks": integer(len(document_report["checks"])),
            "manuscript_number_checks": integer(len(manuscript_report["checks"])),
            "two_environment_core_artifact_hashes": integer(
                len(reproducibility["comparisons"])
            ),
            "all_release_checks_passed": bool(release_gate["all_checks_passed"]),
            "all_core_artifact_hashes_match": bool(
                reproducibility["all_core_artifacts_match"]
            ),
        },
        "algorithm_superiority_claim": False,
        "interpretation_boundary": (
            "A Method Code transition is a metadata anchor, not a confirmed "
            "instrument fault, physical replacement, or causal measurement bias."
        ),
        "artifact_sources": source_records(),
    }


def normalized_for_comparison(summary: dict[str, object]) -> dict[str, object]:
    normalized = dict(summary)
    normalized.pop("generated_at_utc", None)
    return normalized


def main() -> None:
    args = parse_args()
    summary = build_summary()
    if args.write:
        SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(SUMMARY_PATH.relative_to(ROOT))
        return
    tracked = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if normalized_for_comparison(tracked) != normalized_for_comparison(summary):
        raise SystemExit(
            "configs/current_evidence_summary_v2.json does not match frozen local "
            "artifacts. Run scripts/build_current_evidence_summary.py --write."
        )
    print("Tracked frozen evidence summary matches local artifacts.")


if __name__ == "__main__":
    main()
