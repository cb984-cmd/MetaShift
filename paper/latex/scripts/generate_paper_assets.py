"""Generate formal-paper tables, macros, and vector figures from frozen evidence.

This script is intentionally read-only with respect to analysis artifacts. It
accepts only the tracked v0.3.2 evidence summary plus locally available,
hash-verified saved artifacts and writes paper-local derivative assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
LATEX_ROOT = Path(__file__).resolve().parents[1]
GENERATED = LATEX_ROOT / "generated"
TABLES = GENERATED / "tables"
FIGURES = GENERATED / "figures"
MANIFEST_PATH = GENERATED / "asset_manifest.json"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"

REQUIRED_ARTIFACTS = (
    "artifacts/data_gate/summary.json",
    "artifacts/stable_synthetic_case_manifest.json",
    "artifacts/stable_synthetic_case_split_audit.json",
    "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
    "artifacts/stable_synthetic_stable_full_v2_bootstrap.csv",
    "artifacts/reliability_ablation_stable_full_v2_metrics.csv",
    "artifacts/reliability_ablation_stable_full_v2_bootstrap.csv",
    "artifacts/benchmark_ablation_alignment_stable_full_v2.json",
    "artifacts/real_transition_88101_event_audit.csv",
    "artifacts/real_transition_88101_method_results.csv",
    "artifacts/real_transition_88101_event_intervals.csv",
    "artifacts/real_transition_88101_nested_selection_intervals.csv",
    "artifacts/leave_one_donor_out_summary.csv",
    "artifacts/time_placebo_summary.csv",
    "artifacts/time_placebo_date_permutations.csv",
    "artifacts/donor_as_treated_placebos.csv",
    "artifacts/real_transition_88101_evidence_tier_summary.json",
    "artifacts/real_transition_88101_evidence_tiers.csv",
    "artifacts/evidence_tier_sensitivity_v2_summary.csv",
    "artifacts/synthetic_interval_coverage_v2_summary.csv",
    "artifacts/effect_window_sensitivity_summary.csv",
    "artifacts/reporting_scale_sensitivity_summary.csv",
    "artifacts/screening_sensitivity_summary.csv",
    "artifacts/synthetic_risk_coverage_stable_full_v2.csv",
    "artifacts/hourly_poc_validation_summary.csv",
    "artifacts/external_document_review_summary.json",
    "artifacts/data_gate_88502/summary.json",
    "artifacts/real_transition_88502_event_audit.csv",
    "results/release_gate.json",
    "results/document_consistency.json",
    "results/manuscript_number_verification.json",
    "results/reproducibility_comparison.json",
    "configs/selection_aware_coverage_protocol_v2.json",
    "paper/EXTERNAL_DOCUMENT_REVIEW.csv",
)

METHOD_LABELS = {
    "standard_synthetic_control": "Standard SC",
    "metashift_v1_fixed": "MetaShift fixed",
    "metashift_v2_cv": "MetaShift CV",
    "nearest_neighbor_did": "Nearest-neighbor DiD",
    "bayesian_mean_shift": "Bayesian mean shift",
    "before_after_median": "Before-after median",
    "cusum": "CUSUM",
    "pelt": "PELT",
    "rolling_mad": "Rolling MAD",
    "metashift_full_correlation_distance": "MetaShift full prior",
    "ablation_no_graph_prior": "No graph-prior",
    "ablation_no_distance": "No distance term",
    "ablation_no_ridge": "No ridge penalty",
    "ablation_ridge_0_01": "Ridge = 0.01",
    "ablation_ridge_1_0": "Ridge = 1.0",
    "ablation_direct_reliability": "Direct reliability",
    "ablation_add_coverage": "Add coverage",
    "ablation_no_correlation": "No correlation term",
    "ablation_uniform_prior": "Uniform prior",
}

METHOD_ORDER = (
    "standard_synthetic_control",
    "metashift_v1_fixed",
    "metashift_v2_cv",
    "nearest_neighbor_did",
)

COLORS = {
    "Standard SC": "#4C566A",
    "MetaShift fixed": "#3B82F6",
    "MetaShift CV": "#7C3AED",
    "Nearest-neighbor DiD": "#0F766E",
    "Supported candidate": "#2563EB",
    "Not supported": "#F59E0B",
    "Inconclusive": "#94A3B8",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or verify formal-paper assets from frozen evidence."
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write", action="store_true", help="Generate all assets.")
    actions.add_argument(
        "--check", action="store_true", help="Verify the saved asset manifest."
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(relative_path: str) -> dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def format_decimal(value: float, places: int) -> str:
    quantum = Decimal("1").scaleb(-places)
    return str(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def percent(value: float, places: int = 1) -> str:
    return f"{format_decimal(100 * value, places)}\\%"


def latex_escape(value: object) -> str:
    text = str(value)
    substitutions = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(substitutions.get(character, character) for character in text)


def latex_row(values: list[str]) -> str:
    return " & ".join(values) + r" \\"


def source_hashes(summary: dict[str, Any]) -> dict[str, str]:
    records = [
        *summary.get("artifact_sources", []),
        *summary.get("frozen_protocol_sources", []),
    ]
    return {
        str(record["path"]): str(record["sha256"])
        for record in records
        if isinstance(record, dict)
    }


def verify_frozen_inputs(summary: dict[str, Any]) -> None:
    if summary["evidence_version"] != "v0.3.2":
        raise RuntimeError("Paper assets require v0.3.2 frozen evidence.")
    if summary["result_label"] != "stable_full_v2":
        raise RuntimeError("Paper assets require the stable_full_v2 benchmark.")
    if summary["frozen_evidence"]["tag"] != "v0.3.2-evidence-final":
        raise RuntimeError("Paper assets require the v0.3.2 evidence tag.")
    hashes = source_hashes(summary)
    missing_hashes = [path for path in REQUIRED_ARTIFACTS if path not in hashes]
    if missing_hashes:
        raise RuntimeError(
            "Frozen evidence summary lacks required source hashes: "
            + ", ".join(missing_hashes)
        )
    mismatches = []
    for relative_path in REQUIRED_ARTIFACTS:
        path = ROOT / relative_path
        if not path.is_file():
            mismatches.append(f"{relative_path}:missing")
        elif sha256(path) != hashes[relative_path]:
            mismatches.append(f"{relative_path}:sha256_mismatch")
    if mismatches:
        raise RuntimeError(
            "Frozen source artifact validation failed: " + ", ".join(mismatches)
        )


def latex_table(
    label: str,
    caption: str,
    alignment: str,
    headers: list[str],
    rows: list[list[str]],
    note: str,
    size: str = r"\small",
    scale_to_width: bool = False,
) -> str:
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{tab:{label}}}",
        size,
    ]
    if scale_to_width:
        lines.append(r"\resizebox{\linewidth}{!}{%")
    lines.extend(
        [
            f"\\begin{{tabular}}{{{alignment}}}",
        r"\toprule",
        latex_row(headers),
        r"\midrule",
        ]
    )
    lines.extend(latex_row(row) for row in rows)
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            *(["}"] if scale_to_width else []),
            r"\par\smallskip",
            r"\begin{minipage}{0.94\linewidth}",
            r"\footnotesize\textit{Note.} " + note,
            r"\end{minipage}",
            r"\end{table}",
            "",
        ]
    )
    return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def build_macros(
    summary: dict[str, Any],
    metrics: pd.DataFrame,
    nested: pd.DataFrame,
) -> str:
    aggregate = metrics.loc[metrics["perturbation_family"].isna()].set_index("method")
    benchmark = summary["synthetic_benchmark"]
    fixed = benchmark["fixed_prior_metashift"]
    cv = benchmark["cross_validated_metashift"]
    standard = benchmark["standard_synthetic_control"]
    coverage = summary["interval_coverage"]
    tiers = summary["evidence_tiers"]
    real = summary["real_event_audit"]
    placebos = summary["placebos"]
    intervals = summary["real_event_intervals"]
    poc = summary["hourly_same_site_poc"]
    verification = summary["verification"]
    macros = {
        "EvidenceVersion": summary["evidence_version"],
        "EvidenceTag": summary["frozen_evidence"]["tag"],
        "EvidenceCommit": summary["frozen_evidence"]["commit"],
        "EvidenceReleaseURL": summary["frozen_evidence"]["release_url"],
        "CaseManifestSHA": summary["case_manifest_sha256"],
        "CanonicalRecords": f"{summary['data_gate']['canonical_records']:,}",
        "MonitorSeries": f"{summary['data_gate']['monitor_series']:,}",
        "TotalAnchors": str(real["total_anchors"]),
        "OneDonorAnchors": str(
            summary["data_gate"]["anchors_with_one_distinct_physical_donor"]
        ),
        "ThreeDonorAnchors": str(
            summary["data_gate"]["anchors_with_three_distinct_physical_donors"]
        ),
        "CompleteComparisons": str(real["complete_comparisons"]),
        "InsufficientDonorAnchors": str(real["insufficient_geographic_donors"]),
        "InputFailureAnchors": str(real["estimator_input_failure"]),
        "SyntheticCases": str(benchmark["case_count"]),
        "CalibrationCases": str(benchmark["calibration_case_count"]),
        "EvaluationCases": str(benchmark["evaluation_case_count"]),
        "SamplesPerVariant": str(
            int(
                aggregate.loc[
                    "standard_synthetic_control", "evaluation_instances"
                ]
                / 10
            )
        ),
        "StdSCMAE": format_decimal(standard["local_effect_mae_log"], 5),
        "StdSCAUPRC": format_decimal(standard["average_precision"], 5),
        "StdSCFOne": format_decimal(standard["macro_f1"], 5),
        "StdSCFPR": format_decimal(standard["regional_false_positive_rate"], 3),
        "FixedMAE": format_decimal(fixed["local_effect_mae_log"], 5),
        "FixedAUPRC": format_decimal(fixed["average_precision"], 5),
        "FixedFOne": format_decimal(fixed["macro_f1"], 5),
        "FixedFPR": format_decimal(fixed["regional_false_positive_rate"], 3),
        "CVMAE": format_decimal(cv["local_effect_mae_log"], 5),
        "CVAUPRC": format_decimal(cv["average_precision"], 5),
        "CVFOne": format_decimal(cv["macro_f1"], 5),
        "CVFPR": format_decimal(cv["regional_false_positive_rate"], 3),
        "CVPairedMAEDifference": format_decimal(
            cv["paired_mae_difference_vs_standard"], 5
        ),
        "CVPairedMALower": format_decimal(
            cv["paired_mae_difference_95ci"][0], 5
        ),
        "CVPairedMAEUpper": format_decimal(
            cv["paired_mae_difference_95ci"][1], 5
        ),
        "FixedPairedMAEDifference": format_decimal(
            fixed["paired_mae_difference_vs_standard"], 5
        ),
        "FixedPairedMAELower": format_decimal(
            fixed["paired_mae_difference_95ci"][0], 5
        ),
        "FixedPairedMAEUpper": format_decimal(
            fixed["paired_mae_difference_95ci"][1], 5
        ),
        "SharedStandardRows": str(
            summary["synthetic_alignment"]["shared_standard_synthetic_control_rows"]
        ),
        "SupportedCandidates": str(tiers["supported_candidate_discontinuity"]),
        "NotSupportedEvents": str(tiers["not_supported_by_available_evidence"]),
        "InconclusiveEvents": str(tiers["inconclusive_insufficient_evidence"]),
        "TimePlaceboEvents": str(placebos["complete_with_at_least_50"]),
        "FullTimePlaceboEvents": str(placebos["complete_with_100"]),
        "DonorPlaceboRecords": f"{placebos['donor_as_treated_rows']:,}",
        "DonorPlaceboMedian": format_decimal(
            placebos["donor_as_treated_median_standardized_score"], 5
        ),
        "DateResamples": str(placebos["date_resamples"]),
        "DateResamplingP": format_decimal(
            placebos["date_resampling_upper_tail_probability"], 5
        ),
        "NestedIntervalEvents": str(intervals["selection_aware_events"]),
        "NestedIntervalValidMinimum": str(int(nested["valid_repetitions"].min())),
        "NestedExcludesZero": str(intervals["selection_aware_excludes_zero"]),
        "NestedMeanWidth": format_decimal(
            intervals["selection_aware_mean_width_log"], 5
        ),
        "LOOCompleteEvents": str(intervals["leave_one_donor_out_complete_events"]),
        "LOODirectionStableEvents": str(
            intervals["leave_one_donor_out_direction_stable_events"]
        ),
        "ConditionalCoverageLow": percent(
            coverage["conditional_bootstrap_95_eval_coverage_range"][0], 3
        ),
        "ConditionalCoverageHigh": percent(
            coverage["conditional_bootstrap_95_eval_coverage_range"][1], 3
        ),
        "ConformalCoverageLow": percent(
            coverage["split_conformal_90_eval_coverage_range"][0], 4
        ),
        "ConformalCoverageHigh": percent(
            coverage["split_conformal_90_eval_coverage_range"][1], 4
        ),
        "CoverageInstancesPerMethod": f"{coverage['evaluation_instances_per_method']:,}",
        "ExternalReviewEvents": str(
            summary["external_document_review"]["reviewed_events"]
        ),
        "ExternalReviewConfirmations": str(
            summary["external_document_review"]["site_specific_dated_confirmations"]
        ),
        "POCCandidates": str(poc["candidate_events"]),
        "POCUsablePairs": str(poc["usable_paired_events"]),
        "POCDirectionAgreements": str(poc["daily_hourly_direction_agreement"]),
        "SecondaryAnchors": str(summary["secondary_88502"]["eligible_anchors"]),
        "SecondaryComplete": str(summary["secondary_88502"]["complete_comparisons"]),
        "ReleaseGateChecks": str(verification["release_gate_checks"]),
        "DocumentChecks": str(verification["document_consistency_checks"]),
        "ManuscriptChecks": str(verification["manuscript_number_checks"]),
        "ReproducibleArtifactHashes": str(
            verification["two_environment_core_artifact_hashes"]
        ),
    }
    return "\n".join(
        [
            "% Generated by scripts/generate_paper_assets.py. Do not edit manually.",
            *(f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in macros.items()),
            "",
        ]
    )


def build_claim_value_manifest(
    summary: dict[str, Any], data: dict[str, Any]
) -> dict[str, Any]:
    """Derive the exact display fragments for every formal-paper ledger claim."""

    metrics = data["metrics"]
    bootstrap = data["bootstrap"].set_index("comparison")
    audit = data["audit"]
    intervals = data["intervals"]
    nested = data["nested"]
    loo = data["loo"]
    time_placebo = data["time_placebo"]
    tier_rows = data["tiers"]
    windows = data["windows"]
    reporting = data["reporting"].set_index("method")
    screening = data["screening"]
    risk = data["risk"]
    method_results = data["method_results"]
    aggregate = metrics.loc[metrics["perturbation_family"].isna()].set_index("method")
    audit_counts = audit["audit_status"].value_counts()
    complete_audit_count = int(audit_counts["complete"])
    fixed = summary["synthetic_benchmark"]["fixed_prior_metashift"]
    standard = summary["synthetic_benchmark"]["standard_synthetic_control"]
    cv = summary["synthetic_benchmark"]["cross_validated_metashift"]
    tiers = summary["evidence_tiers"]
    coverage = summary["interval_coverage"]
    real = summary["real_event_intervals"]
    placebos = summary["placebos"]
    donor_three = screening.loc[
        screening["minimum_donors_required"] == 3
    ].set_index("setting")
    fixed_windows = windows.loc[
        (windows["method"] == "metashift_v1_fixed")
        & (windows["status"] == "complete")
    ].set_index("comparison_window_days")
    standard_risk = risk.loc[
        (risk["method"] == "standard_synthetic_control")
        & (risk["target_calibration_coverage"] == 0.9)
    ].iloc[0]
    standard_full_risk = risk.loc[
        (risk["method"] == "standard_synthetic_control")
        & (risk["target_calibration_coverage"] == 1.0)
    ].iloc[0]
    medians = method_results.groupby("method")["log_effect"].median()
    fixed_interval_counts = real["fixed_weight_events_by_method"]
    raw_placebo_count = int(
        (
            time_placebo.loc[
                time_placebo["status"].astype("string").str.startswith("complete_"),
                "placebo_p_value",
            ]
            <= 0.10
        ).sum()
    )
    bh_count = int((tier_rows["placebo_q_value"] <= 0.10).sum())
    claims = {
        "Q01": ["2,424,793", "1,689"],
        "Q02": [str(summary["real_event_audit"]["total_anchors"])],
        "Q03": [
            str(summary["data_gate"]["anchors_with_three_distinct_physical_donors"])
        ],
        "Q04": [
            str(audit_counts["complete"]),
            str(audit_counts["insufficient_geographic_donors"]),
            str(audit_counts["estimator_input_failure"]),
        ],
        "Q05": [
            str(summary["synthetic_benchmark"]["case_count"]),
            str(summary["synthetic_benchmark"]["calibration_case_count"]),
            str(summary["synthetic_benchmark"]["evaluation_case_count"]),
        ],
        "Q06": [
            str(
                int(
                    aggregate.loc[
                        "standard_synthetic_control", "evaluation_instances"
                    ]
                    / 10
                )
            )
        ],
        "Q07": [
            format_decimal(standard["local_effect_mae_log"], 5),
            format_decimal(standard["average_precision"], 5),
            format_decimal(standard["macro_f1"], 5),
            format_decimal(standard["regional_false_positive_rate"], 3),
        ],
        "Q08": ["fixed-prior", "cross-validated"],
        "Q09": [
            format_decimal(cv["paired_mae_difference_vs_standard"], 5),
            format_decimal(cv["paired_mae_difference_95ci"][0], 5),
            format_decimal(cv["paired_mae_difference_95ci"][1], 5),
        ],
        "Q10": [
            format_decimal(fixed["paired_mae_difference_vs_standard"], 5),
            format_decimal(fixed["paired_mae_difference_95ci"][0], 5),
            format_decimal(fixed["paired_mae_difference_95ci"][1], 5),
        ],
        "Q11": [
            f"{summary['synthetic_alignment']['shared_standard_synthetic_control_rows']:,}",
            "1e-10",
        ],
        "Q12": [
            str(tiers["supported_candidate_discontinuity"]),
            str(tiers["not_supported_by_available_evidence"]),
            str(tiers["inconclusive_insufficient_evidence"]),
        ],
        "Q13": [
            str(placebos["complete_with_at_least_50"]),
            str(placebos["complete_with_100"]),
        ],
        "Q14": [str(raw_placebo_count), str(bh_count), "0.10"],
        "Q15": [
            str(placebos["date_resamples"]),
            format_decimal(placebos["date_resampling_upper_tail_probability"], 5),
        ],
        "Q16": [
            f"{placebos['donor_as_treated_rows']:,}",
            format_decimal(placebos["donor_as_treated_median_standardized_score"], 5),
        ],
        "Q17": [
            f"{fixed_interval_counts['metashift_v1_fixed']['excludes_zero']}/"
            f"{fixed_interval_counts['metashift_v1_fixed']['events']}",
            f"{fixed_interval_counts['standard_synthetic_control']['excludes_zero']}/"
            f"{fixed_interval_counts['standard_synthetic_control']['events']}",
            f"{fixed_interval_counts['nearest_neighbor_did']['excludes_zero']}/"
            f"{fixed_interval_counts['nearest_neighbor_did']['events']}",
        ],
        "Q18": [
            str(real["selection_aware_events"]),
            str(real["selection_aware_excludes_zero"]),
            format_decimal(real["selection_aware_mean_width_log"], 5),
        ],
        "Q19": [
            str(real["leave_one_donor_out_complete_events"]),
            str(real["leave_one_donor_out_direction_stable_events"]),
        ],
        "Q20": [
            "95%",
            percent(coverage["conditional_bootstrap_95_eval_coverage_range"][0], 1)
            .replace(r"\%", "%"),
            percent(coverage["conditional_bootstrap_95_eval_coverage_range"][1], 1)
            .replace(r"\%", "%"),
        ],
        "Q21": [
            "90%",
            percent(coverage["split_conformal_90_eval_coverage_range"][0], 1).replace(
                r"\%", "%"
            ),
            percent(coverage["split_conformal_90_eval_coverage_range"][1], 1).replace(
                r"\%", "%"
            ),
        ],
        "Q22": ["infeasible within the deadline"],
        "Q23": [
            f"{summary['hourly_same_site_poc']['usable_paired_events']}/"
            f"{summary['hourly_same_site_poc']['candidate_events']}",
            f"{summary['hourly_same_site_poc']['daily_hourly_direction_agreement']}/"
            f"{summary['hourly_same_site_poc']['usable_paired_events']}",
        ],
        "Q24": [
            f"{summary['external_document_review']['site_specific_dated_confirmations']}/"
            f"{summary['external_document_review']['reviewed_events']}"
        ],
        "Q25": [
            str(summary["secondary_88502"]["eligible_anchors"]),
            str(summary["secondary_88502"]["complete_comparisons"]),
        ],
        "Q26": [
            str(summary["verification"]["release_gate_checks"]),
            str(summary["verification"]["document_consistency_checks"]),
            str(summary["verification"]["manuscript_number_checks"]),
            str(summary["verification"]["two_environment_core_artifact_hashes"]),
        ],
        "Q27": [
            format_decimal(medians["metashift_v1_fixed"], 5),
            format_decimal(medians["standard_synthetic_control"], 5),
            format_decimal(medians["nearest_neighbor_did"], 5),
        ],
        "Q28": [
            f"{int(fixed_windows.loc[45, 'event_count'])}/{complete_audit_count}",
            f"{int(fixed_windows.loc[60, 'event_count'])}/{complete_audit_count}",
            f"{int(fixed_windows.loc[90, 'event_count'])}/{complete_audit_count}",
            percent(fixed_windows.loc[45, "sign_agreement_with_60_day"], 1).replace(
                r"\%", "%"
            ),
            percent(fixed_windows.loc[90, "sign_agreement_with_60_day"], 1).replace(
                r"\%", "%"
            ),
        ],
        "Q29": [
            percent(
                reporting.loc["metashift_v1_fixed", "log_raw_direction_agreement"], 1
            ).replace(r"\%", "%"),
            percent(
                reporting.loc[
                    "standard_synthetic_control", "log_raw_direction_agreement"
                ],
                1,
            ).replace(r"\%", "%"),
            percent(
                reporting.loc["nearest_neighbor_did", "log_raw_direction_agreement"],
                1,
            ).replace(r"\%", "%"),
        ],
        "Q30": [
            str(int(donor_three.loc["primary", "eligible_anchors_after_donor_threshold"])),
            "100 km",
            str(int(donor_three.loc["distance_50", "eligible_anchors_after_donor_threshold"])),
            "50 km",
            str(int(donor_three.loc["distance_200", "eligible_anchors_after_donor_threshold"])),
            "200 km",
        ],
        "Q31": [
            f"{int(standard_risk['evaluation_cases'])}/"
            f"{int(standard_full_risk['evaluation_cases'])}",
            format_decimal(standard_risk["local_effect_mae_log"], 5),
            format_decimal(standard_full_risk["local_effect_mae_log"], 5),
        ],
        "Q32": ["same", "confidence-supported"],
    }
    return {
        "schema_version": 1,
        "evidence_version": summary["evidence_version"],
        "frozen_evidence": summary["frozen_evidence"],
        "claims": {
            claim_id: {"expected_ledger_fragments": fragments}
            for claim_id, fragments in claims.items()
        },
    }


def create_tables(summary: dict[str, Any], data: dict[str, Any]) -> dict[Path, str]:
    metrics = data["metrics"]
    bootstrap = data["bootstrap"].set_index("comparison")
    ablation = data["ablation"]
    audit = data["audit"]
    intervals = data["intervals"]
    nested = data["nested"]
    loo = data["loo"]
    time_placebo = data["time_placebo"]
    tier_sensitivity = data["tier_sensitivity"]
    coverage = data["coverage"]
    windows = data["windows"]
    reporting = data["reporting"]
    screening = data["screening"]
    risk = data["risk"]

    aggregate = metrics.loc[metrics["perturbation_family"].isna()].set_index("method")
    tables: dict[Path, str] = {}
    tables[TABLES / "table_data_summary.tex"] = latex_table(
        "data-summary",
        "Frozen v0.3.2 data and audit inventory.",
        "lr",
        ["Quantity", "Count"],
        [
            ["Canonical daily PM2.5 records", f"{summary['data_gate']['canonical_records']:,}"],
            ["Monitor time series", f"{summary['data_gate']['monitor_series']:,}"],
            ["Persistent Method Code anchors", str(summary["real_event_audit"]["total_anchors"])],
            ["Anchors with at least one distinct physical donor", str(summary["data_gate"]["anchors_with_one_distinct_physical_donor"])],
            ["Anchors with at least three distinct physical donors", str(summary["data_gate"]["anchors_with_three_distinct_physical_donors"])],
            ["Complete common-method comparisons", str(summary["real_event_audit"]["complete_comparisons"])],
            ["Donor-insufficient anchors", str(summary["real_event_audit"]["insufficient_geographic_donors"])],
            ["Estimator input-window failures", str(summary["real_event_audit"]["estimator_input_failure"])],
        ],
        "The physical donor identifier is State Code + County Code + Site Number; "
        "at most one POC is retained per donor site.",
    )
    metric_rows = []
    for method in METHOD_ORDER:
        row = aggregate.loc[method]
        metric_rows.append(
            [
                METHOD_LABELS[method],
                format_decimal(row["local_effect_mae_log"], 5),
                format_decimal(row["average_precision"], 5),
                format_decimal(row["macro_f1"], 5),
                format_decimal(row["false_positive_rate"], 3),
            ]
        )
    tables[TABLES / "table_synthetic_metrics.tex"] = latex_table(
        "synthetic-metrics",
        "Independent stable-regime synthetic evaluation.",
        "lrrrr",
        ["Method", "MAE", "AUPRC", "Macro-F1", "Regional FPR"],
        metric_rows,
        "Metrics are aggregates over the frozen \\texttt{stable\\_full\\_v2} evaluation set. "
        "Lower MAE and regional false-positive rate are preferable; higher AUPRC "
        "and macro-F1 are preferable.",
    )
    paired_rows = []
    for comparison, label in (
        (
            "metashift_v1_fixed minus standard_synthetic_control",
            "MetaShift fixed minus Standard SC",
        ),
        (
            "metashift_v2_cv minus standard_synthetic_control",
            "MetaShift CV minus Standard SC",
        ),
    ):
        row = bootstrap.loc[comparison]
        paired_rows.append(
            [
                label,
                format_decimal(row["mae_difference_log"], 5),
                "["
                + format_decimal(row["bootstrap_95ci_lower"], 5)
                + ", "
                + format_decimal(row["bootstrap_95ci_upper"], 5)
                + "]",
                str(int(row["clusters"])),
            ]
        )
    tables[TABLES / "table_paired_bootstrap.tex"] = latex_table(
        "paired-bootstrap",
        "Paired event-cluster bootstrap for local-effect MAE differences.",
        "lrrr",
        ["Comparison", "Difference", "95\\% CI", "Clusters"],
        paired_rows,
        "Difference is MetaShift minus standard synthetic control; negative values "
        "favor MetaShift on MAE. Both intervals include zero.",
    )
    ablation_rows = []
    for _, row in ablation.sort_values("local_effect_mae_log").iterrows():
        ablation_rows.append(
            [
                METHOD_LABELS.get(row["method"], latex_escape(row["method"])),
                format_decimal(row["local_effect_mae_log"], 5),
                format_decimal(row["macro_f1"], 5),
                format_decimal(row["false_positive_rate"], 3),
            ]
        )
    tables[TABLES / "table_ablation.tex"] = latex_table(
        "ablations",
        "Reliability-prior and regularization ablations on shared synthetic inputs.",
        "lrrr",
        ["Variant", "MAE", "Macro-F1", "Regional FPR"],
        ablation_rows,
        "The common standard-synthetic-control records align exactly across the "
        "main and ablation experiments to tolerance $10^{-10}$.",
        size=r"\scriptsize",
    )
    audit_counts = audit["audit_status"].value_counts()
    complete_method = data["method_results"].groupby("method")["log_effect"].median()
    fixed_width = (
        intervals.loc[intervals["method"] == "metashift_v1_fixed", "ci95_upper"]
        - intervals.loc[intervals["method"] == "metashift_v1_fixed", "ci95_lower"]
    ).mean()
    audit_rows = [
        ["Complete common-method comparison", str(int(audit_counts["complete"]))],
        [
            "Fewer than three distinct physical donors",
            str(int(audit_counts["insufficient_geographic_donors"])),
        ],
        ["Estimator input-window failure", str(int(audit_counts["estimator_input_failure"]))],
        ["Total", str(len(audit))],
    ]
    interval_rows = []
    for method in (
        "metashift_v1_fixed",
        "standard_synthetic_control",
        "nearest_neighbor_did",
    ):
        group = intervals.loc[intervals["method"] == method]
        interval_rows.append(
            [
                METHOD_LABELS[method],
                str(len(group)),
                str(int(group["ci_excludes_zero"].sum())),
                format_decimal(complete_method[method], 5),
            ]
        )
    real_audit_lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Complete 88101 event audit and real-event diagnostics.}",
        r"\label{tab:real-audit}",
        r"\small",
        r"\begin{tabular}{lr}",
        r"\toprule",
        latex_row(["Audit disposition", "Anchors"]),
        r"\midrule",
        *(latex_row(row) for row in audit_rows),
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\medskip",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        latex_row(["Method", "Events", "Fixed CI excludes 0", "Median log effect"]),
        r"\midrule",
        *(latex_row(row) for row in interval_rows),
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.94\linewidth}",
        r"\footnotesize\textit{Note.} Nested selection-aware intervals are available for "
        + f"{len(nested)}/{int(audit_counts['complete'])} complete events; "
        + f"{int(nested['selection_ci_excludes_zero'].sum())} exclude zero. Their mean "
        + f"width is {format_decimal((nested['selection_ci95_upper'] - nested['selection_ci95_lower']).mean(), 5)} "
        + f"log units versus {format_decimal(fixed_width, 5)} for fixed-weight MetaShift intervals. "
        + f"Leave-one-donor-out refits complete for {int((loo['summary_status'] == 'complete').sum())} "
        + f"events, with {int(loo.loc[loo['summary_status'] == 'complete', 'direction_stable_all_donors'].sum())} "
        + "retaining direction under every donor removal. All intervals are diagnostic, not "
        + "calibrated physical-bias confidence intervals.",
        r"\end{minipage}",
        r"\end{table}",
        "",
    ]
    tables[TABLES / "table_real_audit.tex"] = "\n".join(real_audit_lines)
    conditional = coverage.loc[
        (coverage["interval_type"] == "conditional_block_bootstrap")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].set_index("method")
    conformal = coverage.loc[
        (coverage["interval_type"] == "split_conformal")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].set_index("method")
    coverage_rows = []
    for method in METHOD_ORDER:
        conditional_row = conditional.loc[method]
        conformal_row = conformal.loc[method]
        coverage_rows.append(
            [
                METHOD_LABELS[method],
                percent(conditional_row["empirical_coverage"], 3),
                format_decimal(conditional_row["mean_interval_width_log"], 3),
                percent(conformal_row["empirical_coverage"], 4),
                format_decimal(conformal_row["mean_interval_width_log"], 3),
            ]
        )
    tables[TABLES / "table_interval_coverage.tex"] = latex_table(
        "interval-coverage",
        "Held-out synthetic interval coverage by method.",
        "lrrrr",
        [
            "Method",
            "Fixed 95\\% coverage",
            "Fixed mean width",
            "Conformal 90\\% coverage",
            "Conformal mean width",
        ],
        coverage_rows,
        f"Each method has {int(conditional['event_instances'].iloc[0]):,} evaluation "
        "effect instances. Fixed-weight intervals under-cover and split-conformal "
        "intervals over-cover under this frozen synthetic design.",
        size=r"\scriptsize",
        scale_to_width=True,
    )
    complete_windows = windows.loc[
        (windows["method"] == "metashift_v1_fixed") & (windows["status"] == "complete")
    ].set_index("comparison_window_days")
    reporting = reporting.set_index("method")
    window_rows = [
        [
            f"{days} days",
            str(int(complete_windows.loc[days, "event_count"])),
            format_decimal(complete_windows.loc[days, "median_log_effect"], 5),
            "reference"
            if days == 60
            else percent(
                complete_windows.loc[days, "sign_agreement_with_60_day"], 1
            ),
        ]
        for days in (45, 60, 90)
    ]
    scale_rows = [
        [
            METHOD_LABELS[method],
            percent(reporting.loc[method, "log_raw_direction_agreement"], 1),
            format_decimal(
                reporting.loc[method, "spearman_abs_log_vs_raw"], 3
            ),
        ]
        for method in (
            "metashift_v1_fixed",
            "standard_synthetic_control",
            "nearest_neighbor_did",
        )
    ]
    window_scale_lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Predeclared effect-window and reporting-scale sensitivity.}",
        r"\label{tab:window-scale-sensitivity}",
        r"\small",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        latex_row(["MetaShift window", "Complete events", "Median log effect", "Sign agreement with 60 days"]),
        r"\midrule",
        *(latex_row(row) for row in window_rows),
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\medskip",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        latex_row(["Method", "Log/raw sign agreement", "Spearman $\\rho$"]),
        r"\midrule",
        *(latex_row(row) for row in scale_rows),
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.94\linewidth}",
        r"\footnotesize\textit{Note.} Window sensitivity adds a full method-stability "
        r"check for every target and donor window. Reporting-scale agreement is a "
        r"concordance diagnostic and does not equate raw and log causal estimands.",
        r"\end{minipage}",
        r"\end{table}",
        "",
    ]
    tables[TABLES / "table_window_scale_sensitivity.tex"] = "\n".join(
        window_scale_lines
    )
    screen = screening.loc[screening["minimum_donors_required"] == 3].set_index(
        "setting"
    )
    screen_labels = (
        ("primary", "Primary (100 km)"),
        ("coverage_70", "Coverage 70\\%"),
        ("coverage_80", "Coverage 80\\%"),
        ("window_45", "Stable window 45 days"),
        ("window_90", "Stable window 90 days"),
        ("gap_3", "Transition gap 3 days"),
        ("gap_14", "Transition gap 14 days"),
        ("distance_50", "Donor radius 50 km"),
        ("distance_200", "Donor radius 200 km"),
        ("correlation_050", "Correlation $\\rho \\geq 0.50$"),
        ("correlation_070", "Correlation $\\rho \\geq 0.70$"),
    )
    screening_rows = [
        [
            label,
            str(int(screen.loc[key, "eligible_anchors_before_donor_threshold"])),
            str(int(screen.loc[key, "eligible_anchors_after_donor_threshold"])),
        ]
        for key, label in screen_labels
    ]
    tables[TABLES / "table_screening_sensitivity.tex"] = latex_table(
        "screening-sensitivity",
        "One-factor screening sensitivity with three required distinct donors.",
        "lrr",
        ["Setting", "Eligible before donor rule", "With at least 3 donors"],
        screening_rows,
        "One predeclared setting changes at a time. These counts describe audit "
        "availability, not detected-effect frequency.",
        size=r"\scriptsize",
    )
    risk_standard = risk.loc[
        (risk["method"] == "standard_synthetic_control")
        & (risk["target_calibration_coverage"].isin([0.9, 1.0]))
    ].set_index("target_calibration_coverage")
    placebo_complete = time_placebo.loc[
        time_placebo["status"].astype(str).str.startswith("complete_")
    ]
    tables[TABLES / "table_placebo_external.tex"] = latex_table(
        "placebo-external",
        "Placebo, external-document, and same-site POC evidence boundaries.",
        "lr",
        ["Diagnostic", "Value"],
        [
            ["Complete time-placebo events with at least 50 dates", str(len(placebo_complete))],
            ["Complete time-placebo events with 100 dates", str(int((placebo_complete["placebo_count"] >= 100).sum()))],
            ["Raw time-placebo probabilities at most 0.10", str(int((placebo_complete["placebo_p_value"] <= 0.10).sum()))],
            ["BH q values at most 0.10", str(int((data["tiers"]["placebo_q_value"] <= 0.10).sum()))],
            ["Donor-as-treated placebo records", f"{len(data['donor_placebos']):,}"],
            ["Date-resampling permutations", str(len(data["date_permutations"]))],
            ["Dated site-specific external confirmations", f"0/{summary['external_document_review']['reviewed_events']}"],
            ["Usable hourly same-site POC comparisons", f"{summary['hourly_same_site_poc']['usable_paired_events']}/{summary['hourly_same_site_poc']['candidate_events']}"],
            ["Daily/hourly POC direction agreements", f"{summary['hourly_same_site_poc']['daily_hourly_direction_agreement']}/{summary['hourly_same_site_poc']['usable_paired_events']}"],
            ["Standard SC 90th-percentile risk-gate retention", f"{int(risk_standard.loc[0.9, 'evaluation_cases'])}/{int(risk_standard.loc[1.0, 'evaluation_cases'])}"],
        ],
        "Time and donor placebos are diagnostic falsifications. Same-site POC and "
        "document review provide contextual evidence only, not instrument ground truth.",
        size=r"\scriptsize",
    )
    verification = summary["verification"]
    tables[TABLES / "table_reproducibility.tex"] = latex_table(
        "reproducibility",
        "Frozen evidence release verification record.",
        "lr",
        ["Record", "Value"],
        [
            ["Evidence tag", latex_escape(summary["frozen_evidence"]["tag"])],
            ["Frozen evidence commit", r"\texttt{" + summary["frozen_evidence"]["commit"][:12] + "}"],
            ["Synthetic result label", latex_escape(summary["result_label"])],
            ["Case manifest SHA-256", r"\texttt{" + summary["case_manifest_sha256"][:16] + r"\ldots}"],
            ["Release-gate checks passed", f"{verification['release_gate_checks']}/{verification['release_gate_checks']}"],
            ["Document-consistency checks passed", f"{verification['document_consistency_checks']}/{verification['document_consistency_checks']}"],
            ["Markdown number checks passed", f"{verification['manuscript_number_checks']}/{verification['manuscript_number_checks']}"],
            ["Two-environment core hashes matched", str(verification["two_environment_core_artifact_hashes"])],
        ],
        "The two-environment statement applies only to the listed designated core "
        "artifacts in the frozen reproducibility comparison, not to every local file.",
    )
    return tables


def save_figure(
    figure: plt.Figure, path: Path, title: str, sources: list[str], outputs: list[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        path,
        format="pdf",
        bbox_inches="tight",
        metadata={
            "Title": title,
            "Creator": "MetaShift-Bench formal-paper asset generator",
        },
    )
    plt.close(figure)
    outputs.append(
        {
            "path": str(path.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "vector_figure",
            "sources": sources,
        }
    )


def create_figures(summary: dict[str, Any], data: dict[str, Any], outputs: list[dict[str, Any]]) -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.dpi": 160,
        }
    )
    audit = data["audit"]
    counts = audit["audit_status"].value_counts()
    labels = [
        "Complete comparison",
        "<3 distinct donors",
        "Input-window failure",
    ]
    values = [
        int(counts["complete"]),
        int(counts["insufficient_geographic_donors"]),
        int(counts["estimator_input_failure"]),
    ]
    fig, axis = plt.subplots(figsize=(6.3, 2.9))
    bars = axis.barh(labels, values, color=["#2563EB", "#F59E0B", "#DC2626"])
    axis.bar_label(bars, padding=3)
    axis.set_xlabel("Method Code anchors")
    axis.set_title("Complete 88101 metadata-anchor audit")
    axis.set_xlim(0, max(values) * 1.18)
    axis.grid(axis="x", alpha=0.22)
    save_figure(
        fig,
        FIGURES / "fig_event_flow.pdf",
        "Complete metadata-anchor audit flow",
        ["artifacts/real_transition_88101_event_audit.csv"],
        outputs,
    )

    aggregate = data["metrics"].loc[
        data["metrics"]["perturbation_family"].isna()
    ].set_index("method").loc[list(METHOD_ORDER)]
    labels = [METHOD_LABELS[method] for method in METHOD_ORDER]
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.9))
    for axis, column, title, ylabel in (
        (axes[0], "local_effect_mae_log", "Local-effect error", "MAE"),
        (axes[1], "macro_f1", "Attribution", "Macro-F1"),
        (axes[2], "false_positive_rate", "Regional attribution", "False-positive rate"),
    ):
        values = aggregate[column].to_numpy()
        bars = axis.bar(
            range(len(labels)),
            values,
            color=[COLORS[label] for label in labels],
        )
        axis.set_xticks(range(len(labels)), labels, rotation=28, ha="right")
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.22)
        if column != "local_effect_mae_log":
            axis.set_ylim(0, 1)
        for bar, value in zip(bars, values, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value,
                format_decimal(float(value), 3),
                ha="center",
                va="bottom",
                fontsize=7,
            )
    fig.suptitle("Held-out stable-regime synthetic benchmark", y=1.03, fontsize=10)
    fig.tight_layout()
    save_figure(
        fig,
        FIGURES / "fig_synthetic_metrics.pdf",
        "Held-out stable-regime synthetic metrics",
        ["artifacts/stable_synthetic_stable_full_v2_metrics.csv"],
        outputs,
    )

    bootstrap = data["bootstrap"].set_index("comparison")
    pairs = [
        ("metashift_v1_fixed minus standard_synthetic_control", "MetaShift fixed"),
        ("metashift_v2_cv minus standard_synthetic_control", "MetaShift CV"),
    ]
    centers = np.array(
        [bootstrap.loc[key, "mae_difference_log"] for key, _ in pairs], dtype=float
    )
    lowers = np.array(
        [
            bootstrap.loc[key, "bootstrap_95ci_lower"]
            for key, _ in pairs
        ],
        dtype=float,
    )
    uppers = np.array(
        [
            bootstrap.loc[key, "bootstrap_95ci_upper"]
            for key, _ in pairs
        ],
        dtype=float,
    )
    fig, axis = plt.subplots(figsize=(6.1, 2.9))
    ypos = np.arange(len(pairs))
    axis.errorbar(
        centers,
        ypos,
        xerr=np.vstack([centers - lowers, uppers - centers]),
        fmt="o",
        color="#2563EB",
        capsize=4,
        linewidth=1.4,
    )
    axis.axvline(0, color="#111827", linewidth=1, linestyle="--")
    axis.set_yticks(ypos, [label for _, label in pairs])
    axis.set_xlabel("Paired MAE difference versus Standard SC")
    axis.set_title("Event-cluster bootstrap uncertainty")
    axis.grid(axis="x", alpha=0.22)
    save_figure(
        fig,
        FIGURES / "fig_paired_bootstrap.pdf",
        "Paired MAE bootstrap intervals",
        ["artifacts/stable_synthetic_stable_full_v2_bootstrap.csv"],
        outputs,
    )

    tier_counts = summary["evidence_tiers"]
    labels = ["Supported candidate", "Not supported", "Inconclusive"]
    values = [
        tier_counts["supported_candidate_discontinuity"],
        tier_counts["not_supported_by_available_evidence"],
        tier_counts["inconclusive_insufficient_evidence"],
    ]
    fig, axis = plt.subplots(figsize=(5.8, 3.0))
    bars = axis.bar(labels, values, color=[COLORS[label] for label in labels])
    axis.bar_label(bars, padding=3)
    axis.set_ylabel("Anchors")
    axis.set_title("Exploratory evidence tiers for all anchors")
    axis.tick_params(axis="x", rotation=14)
    axis.grid(axis="y", alpha=0.22)
    save_figure(
        fig,
        FIGURES / "fig_evidence_tiers.pdf",
        "Exploratory evidence-tier counts",
        ["artifacts/real_transition_88101_evidence_tier_summary.json"],
        outputs,
    )

    time_placebo = data["time_placebo"]
    complete = time_placebo.loc[
        time_placebo["status"].astype(str).str.startswith("complete_")
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    placebo_categories = [">=50 dates", "100 dates", "Incomplete"]
    placebo_counts = [
        int((complete["placebo_count"] >= 50).sum()),
        int((complete["placebo_count"] >= 100).sum()),
        int((~time_placebo["status"].astype(str).str.startswith("complete_")).sum()),
    ]
    bars = axes[0].bar(placebo_categories, placebo_counts, color=["#2563EB", "#7C3AED", "#94A3B8"])
    axes[0].bar_label(bars, padding=3)
    axes[0].set_title("Time-placebo availability")
    axes[0].set_ylabel("Events")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].grid(axis="y", alpha=0.22)
    axes[1].hist(
        complete["placebo_p_value"].dropna(),
        bins=np.linspace(0, 1, 11),
        color="#0F766E",
        edgecolor="white",
    )
    axes[1].axvline(0.10, color="#DC2626", linestyle="--", linewidth=1)
    axes[1].set_title("Raw time-placebo probability")
    axes[1].set_xlabel("Probability")
    axes[1].set_ylabel("Events")
    axes[1].grid(axis="y", alpha=0.22)
    fig.tight_layout()
    save_figure(
        fig,
        FIGURES / "fig_placebos.pdf",
        "Time placebo availability and raw probabilities",
        ["artifacts/time_placebo_summary.csv"],
        outputs,
    )

    coverage = data["coverage"]
    conditional = coverage.loc[
        (coverage["interval_type"] == "conditional_block_bootstrap")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].set_index("method").loc[list(METHOD_ORDER)]
    conformal = coverage.loc[
        (coverage["interval_type"] == "split_conformal")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ].set_index("method").loc[list(METHOD_ORDER)]
    fig, axis = plt.subplots(figsize=(7.0, 3.0))
    x = np.arange(len(METHOD_ORDER))
    width = 0.36
    axis.bar(
        x - width / 2,
        conditional["empirical_coverage"],
        width,
        label="Fixed-weight, nominal 95%",
        color="#2563EB",
    )
    axis.bar(
        x + width / 2,
        conformal["empirical_coverage"],
        width,
        label="Split-conformal, nominal 90%",
        color="#7C3AED",
    )
    axis.axhline(0.95, color="#2563EB", linestyle="--", linewidth=1)
    axis.axhline(0.90, color="#7C3AED", linestyle="--", linewidth=1)
    axis.set_xticks(x, [METHOD_LABELS[method] for method in METHOD_ORDER], rotation=22)
    axis.set_ylim(0.5, 1.03)
    axis.set_ylabel("Empirical coverage")
    axis.set_title("Held-out synthetic interval coverage")
    axis.legend(fontsize=7, loc="lower right")
    axis.grid(axis="y", alpha=0.22)
    save_figure(
        fig,
        FIGURES / "fig_interval_coverage.pdf",
        "Held-out interval coverage",
        ["artifacts/synthetic_interval_coverage_v2_summary.csv"],
        outputs,
    )

    screen = data["screening"].loc[
        data["screening"]["minimum_donors_required"] == 3
    ].set_index("setting")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    settings = ["distance_50", "primary", "distance_200"]
    labels = ["50 km", "100 km", "200 km"]
    values = [
        int(screen.loc[setting, "eligible_anchors_after_donor_threshold"])
        for setting in settings
    ]
    bars = axes[0].bar(labels, values, color=["#94A3B8", "#2563EB", "#7C3AED"])
    axes[0].bar_label(bars, padding=3)
    axes[0].set_ylabel("Anchors with >=3 donors")
    axes[0].set_title("Geographic donor-radius sensitivity")
    axes[0].grid(axis="y", alpha=0.22)
    tier_sensitivity = data["tier_sensitivity"].pivot(
        index="setting", columns="evidence_tier", values="anchor_count"
    ).loc[["strict", "primary", "lenient"]]
    bottom = np.zeros(3)
    for column, label, color in (
        ("supported_candidate_discontinuity", "Supported", "#2563EB"),
        ("not_supported_by_available_evidence", "Not supported", "#F59E0B"),
        ("inconclusive_insufficient_evidence", "Inconclusive", "#94A3B8"),
    ):
        values = tier_sensitivity[column].to_numpy()
        axes[1].bar(tier_sensitivity.index, values, bottom=bottom, label=label, color=color)
        bottom += values
    axes[1].set_title("Evidence-tier threshold sensitivity")
    axes[1].set_ylabel("Anchors")
    axes[1].legend(fontsize=7)
    axes[1].grid(axis="y", alpha=0.22)
    fig.tight_layout()
    save_figure(
        fig,
        FIGURES / "fig_screening_sensitivity.pdf",
        "Screening and evidence-tier sensitivity",
        [
            "artifacts/screening_sensitivity_summary.csv",
            "artifacts/evidence_tier_sensitivity_v2_summary.csv",
        ],
        outputs,
    )

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    poc = summary["hourly_same_site_poc"]
    labels = ["Candidates", "Usable pairs", "Sign agreement"]
    values = [
        poc["candidate_events"],
        poc["usable_paired_events"],
        poc["daily_hourly_direction_agreement"],
    ]
    bars = axes[0].bar(labels, values, color=["#94A3B8", "#0F766E", "#2563EB"])
    axes[0].bar_label(bars, padding=3)
    axes[0].set_ylim(0, max(values) * 1.25)
    axes[0].set_title("Same-site POC contextual evidence")
    axes[0].set_ylabel("Events")
    axes[0].tick_params(axis="x", rotation=18)
    axes[0].grid(axis="y", alpha=0.22)
    external = summary["external_document_review"]
    bars = axes[1].bar(
        ["Reviewed cases", "Dated site-specific\nconfirmations"],
        [
            external["reviewed_events"],
            external["site_specific_dated_confirmations"],
        ],
        color=["#94A3B8", "#DC2626"],
    )
    axes[1].bar_label(bars, padding=3)
    axes[1].set_ylim(0, max(external["reviewed_events"], 1) * 1.25)
    axes[1].set_title("Targeted external-document review")
    axes[1].set_ylabel("Cases")
    axes[1].grid(axis="y", alpha=0.22)
    fig.tight_layout()
    save_figure(
        fig,
        FIGURES / "fig_external_evidence.pdf",
        "External evidence availability",
        [
            "artifacts/hourly_poc_validation_summary.csv",
            "artifacts/external_document_review_summary.json",
        ],
        outputs,
    )


def load_data() -> dict[str, Any]:
    return {
        "metrics": pd.read_csv(
            ROOT / "artifacts/stable_synthetic_stable_full_v2_metrics.csv"
        ),
        "bootstrap": pd.read_csv(
            ROOT / "artifacts/stable_synthetic_stable_full_v2_bootstrap.csv"
        ),
        "ablation": pd.read_csv(
            ROOT / "artifacts/reliability_ablation_stable_full_v2_metrics.csv"
        ),
        "audit": pd.read_csv(ROOT / "artifacts/real_transition_88101_event_audit.csv"),
        "method_results": pd.read_csv(
            ROOT / "artifacts/real_transition_88101_method_results.csv"
        ),
        "intervals": pd.read_csv(
            ROOT / "artifacts/real_transition_88101_event_intervals.csv"
        ),
        "nested": pd.read_csv(
            ROOT / "artifacts/real_transition_88101_nested_selection_intervals.csv"
        ),
        "loo": pd.read_csv(ROOT / "artifacts/leave_one_donor_out_summary.csv"),
        "time_placebo": pd.read_csv(ROOT / "artifacts/time_placebo_summary.csv"),
        "date_permutations": pd.read_csv(
            ROOT / "artifacts/time_placebo_date_permutations.csv"
        ),
        "donor_placebos": pd.read_csv(
            ROOT / "artifacts/donor_as_treated_placebos.csv"
        ),
        "tiers": pd.read_csv(
            ROOT / "artifacts/real_transition_88101_evidence_tiers.csv"
        ),
        "tier_sensitivity": pd.read_csv(
            ROOT / "artifacts/evidence_tier_sensitivity_v2_summary.csv"
        ),
        "coverage": pd.read_csv(
            ROOT / "artifacts/synthetic_interval_coverage_v2_summary.csv"
        ),
        "windows": pd.read_csv(
            ROOT / "artifacts/effect_window_sensitivity_summary.csv"
        ),
        "reporting": pd.read_csv(
            ROOT / "artifacts/reporting_scale_sensitivity_summary.csv"
        ),
        "screening": pd.read_csv(
            ROOT / "artifacts/screening_sensitivity_summary.csv"
        ),
        "risk": pd.read_csv(
            ROOT / "artifacts/synthetic_risk_coverage_stable_full_v2.csv"
        ),
    }


def add_output_hashes(outputs: list[dict[str, Any]]) -> None:
    for output in outputs:
        path = LATEX_ROOT / output["path"]
        output["bytes"] = path.stat().st_size
        output["sha256"] = sha256(path)


def write_assets() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    verify_frozen_inputs(summary)
    data = load_data()
    GENERATED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []

    macros_path = GENERATED / "evidence_macros.tex"
    write_text(macros_path, build_macros(summary, data["metrics"], data["nested"]))
    outputs.append(
        {
            "path": str(macros_path.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "latex_macros",
            "sources": ["configs/current_evidence_summary_v2.json"],
        }
    )
    claim_values_path = GENERATED / "claim_value_manifest.json"
    write_text(
        claim_values_path,
        json.dumps(build_claim_value_manifest(summary, data), indent=2) + "\n",
    )
    outputs.append(
        {
            "path": str(claim_values_path.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "claim_value_manifest",
            "sources": ["configs/current_evidence_summary_v2.json"],
        }
    )
    for path, content in create_tables(summary, data).items():
        write_text(path, content)
        outputs.append(
            {
                "path": str(path.relative_to(LATEX_ROOT)).replace("\\", "/"),
                "kind": "latex_table",
                "sources": ["configs/current_evidence_summary_v2.json"],
            }
        )
    create_figures(summary, data, outputs)
    add_output_hashes(outputs)
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "generator": "paper/latex/scripts/generate_paper_assets.py",
        "frozen_evidence": summary["frozen_evidence"],
        "result_label": summary["result_label"],
        "input_summary_sha256": sha256(SUMMARY_PATH),
        "input_artifact_sources": [
            {"path": path, "sha256": source_hashes(summary)[path]}
            for path in REQUIRED_ARTIFACTS
        ],
        "outputs": outputs,
    }
    write_text(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")
    print(f"Generated {len(outputs)} paper assets at {GENERATED.relative_to(ROOT)}")


def check_assets() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    verify_frozen_inputs(summary)
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Missing paper asset manifest: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("input_summary_sha256") != sha256(SUMMARY_PATH):
        raise RuntimeError("Paper asset manifest does not match current evidence summary.")
    if manifest.get("frozen_evidence") != summary["frozen_evidence"]:
        raise RuntimeError("Paper asset manifest has a different frozen evidence identity.")
    errors = []
    for output in manifest.get("outputs", []):
        path = LATEX_ROOT / output["path"]
        if not path.is_file():
            errors.append(f"{output['path']}:missing")
        elif sha256(path) != output.get("sha256"):
            errors.append(f"{output['path']}:sha256_mismatch")
    if errors:
        raise RuntimeError("Paper asset validation failed: " + ", ".join(errors))
    print(f"Verified {len(manifest['outputs'])} generated paper assets.")


def main() -> None:
    args = parse_args()
    if args.write:
        write_assets()
    else:
        check_assets()


if __name__ == "__main__":
    main()
