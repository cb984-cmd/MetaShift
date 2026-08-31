"""Verify numeric claims in the manuscript against generated result artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
PAPER_PATH = ROOT / "paper/MANUSCRIPT_DRAFT.md"
OUTPUT_PATH = ROOT / "results/manuscript_number_verification.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Markdown manuscript numeric claims against frozen artifacts."
    )
    parser.add_argument(
        "--manuscript",
        type=Path,
        default=PAPER_PATH,
        help="Markdown manuscript path, relative to the repository root by default.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Verification JSON path, relative to the repository root by default.",
    )
    return parser.parse_args()


def resolve_from_root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def exact_table_row(
    method: str, mae: float | None, auprc: float, macro_f1: float, fpr: float
) -> str:
    mae_text = "N/A" if pd.isna(mae) else format_decimal(mae, 5)
    return (
        f"| {method} | {mae_text} | {format_decimal(auprc, 5)} | "
        f"{format_decimal(macro_f1, 5)} | {format_decimal(fpr, 3)} |"
    )


def format_decimal(value: float, places: int) -> str:
    """Use explicit decimal half-up rounding for manuscript display values."""

    quantum = Decimal("1").scaleb(-places)
    return str(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def collect_expectations() -> dict[str, str]:
    """Build exact display fragments from current frozen result artifacts."""

    data_gate = json.loads(
        (ARTIFACTS / "data_gate/summary.json").read_text(encoding="utf-8")
    )
    metrics = pd.read_csv(
        ARTIFACTS / "stable_synthetic_stable_full_v2_metrics.csv"
    )
    aggregate = metrics.loc[metrics["perturbation_family"].isna()].set_index("method")
    bootstrap = pd.read_csv(
        ARTIFACTS / "stable_synthetic_stable_full_v2_bootstrap.csv"
    ).set_index("comparison")
    ablation = pd.read_csv(
        ARTIFACTS / "reliability_ablation_stable_full_v2_metrics.csv"
    ).set_index("method")
    audit = pd.read_csv(ARTIFACTS / "real_transition_88101_event_audit.csv")
    intervals = pd.read_csv(
        ARTIFACTS / "real_transition_88101_event_intervals.csv"
    )
    nested = pd.read_csv(
        ARTIFACTS / "real_transition_88101_nested_selection_intervals.csv"
    )
    leave_one_out = pd.read_csv(ARTIFACTS / "leave_one_donor_out_summary.csv")
    placebos = pd.read_csv(ARTIFACTS / "time_placebo_summary.csv")
    evidence = json.loads(
        (ARTIFACTS / "real_transition_88101_evidence_tier_summary.json").read_text(
            encoding="utf-8"
        )
    )
    sensitivity_88502 = json.loads(
        (ARTIFACTS / "data_gate_88502/summary.json").read_text(encoding="utf-8")
    )
    audit_88502 = pd.read_csv(ARTIFACTS / "real_transition_88502_event_audit.csv")
    split_audit = json.loads(
        (ARTIFACTS / "stable_synthetic_case_split_audit.json").read_text(
            encoding="utf-8"
        )
    )
    risk_coverage = pd.read_csv(ARTIFACTS / "synthetic_risk_coverage_stable_full_v2.csv")
    effect_windows = pd.read_csv(
        ARTIFACTS / "effect_window_sensitivity_summary.csv"
    )
    screening = pd.read_csv(ARTIFACTS / "screening_sensitivity_summary.csv")
    coverage = pd.read_csv(ARTIFACTS / "synthetic_interval_coverage_v2_summary.csv")
    tier_sensitivity = pd.read_csv(
        ARTIFACTS / "evidence_tier_sensitivity_v2_summary.csv"
    ).pivot(index="setting", columns="evidence_tier", values="anchor_count")
    reporting_scale = pd.read_csv(
        ARTIFACTS / "reporting_scale_sensitivity_summary.csv"
    ).set_index("method")
    method_results = pd.read_csv(
        ARTIFACTS / "real_transition_88101_method_results.csv"
    )
    donor_placebos = pd.read_csv(ARTIFACTS / "donor_as_treated_placebos.csv")
    date_permutations = pd.read_csv(
        ARTIFACTS / "time_placebo_date_permutations.csv"
    )
    external_documents = json.loads(
        (ARTIFACTS / "external_document_review_summary.json").read_text(
            encoding="utf-8"
        )
    )

    complete_placebos = placebos[
        placebos["status"].astype("string").str.startswith("complete_")
    ]
    q_values = pd.read_csv(
        ARTIFACTS / "real_transition_88101_evidence_tiers.csv"
    )["placebo_q_value"]
    interval_counts = (
        intervals.groupby("method")["ci_excludes_zero"].sum().astype(int).to_dict()
    )
    complete_loo = leave_one_out.loc[
        leave_one_out["summary_status"] == "complete"
    ]
    donor_three = screening.loc[
        screening["minimum_donors_required"] == 3
    ].set_index("setting")["eligible_anchors_after_donor_threshold"]
    standard_risk = risk_coverage.loc[
        (risk_coverage["method"] == "standard_synthetic_control")
        & (risk_coverage["target_calibration_coverage"] == 0.9)
    ].iloc[0]
    standard_full_risk = risk_coverage.loc[
        (risk_coverage["method"] == "standard_synthetic_control")
        & (risk_coverage["target_calibration_coverage"] == 1.0)
    ].iloc[0]
    metashift_windows = effect_windows.loc[
        (effect_windows["method"] == "metashift_v1_fixed")
        & (effect_windows["status"] == "complete")
    ].set_index("comparison_window_days")
    unavailable_windows = effect_windows.loc[
        (effect_windows["method"] == "metashift_v1_fixed")
        & (effect_windows["status"] != "complete")
    ].set_index("comparison_window_days")
    method_medians = method_results.groupby("method")["log_effect"].median()
    conditional_coverage = coverage.loc[
        (coverage["interval_type"] == "conditional_block_bootstrap")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ]
    conformal_coverage = coverage.loc[
        (coverage["interval_type"] == "split_conformal")
        & (coverage["split"] == "evaluation")
        & (coverage["stratum_type"] == "all")
    ]
    date_resampling_upper_tail = (
        1 + (date_permutations["mean_score_difference"] <= 0).sum()
    ) / (len(date_permutations) + 1)
    complete_real_events = int((audit["audit_status"] == "complete").sum())

    expectations = {
        "canonical_records": f"| Canonical daily records | {int(data_gate['canonical_records']):,} |",
        "monitor_series": f"| Monitor time series | {int(data_gate['monitor_series']):,} |",
        "eligible_anchors": f"| Persistent Method Code anchors | {int(data_gate['eligible_anchors']):,} |",
        "anchors_one_donor": f"| Anchors with at least one geographic donor | {int(data_gate['anchors_with_one_geographic_control']):,} |",
        "anchors_three_donors": f"| Anchors with at least three geographic donors | {int(data_gate['anchors_with_three_geographic_controls']):,} |",
        "complete_real_audit": f"| Complete common-method comparison | {int((audit['audit_status'] == 'complete').sum())} |",
        "insufficient_donors": f"| Fewer than three geographic donors | {int((audit['audit_status'] == 'insufficient_geographic_donors').sum())} |",
        "input_failures": f"| Estimator input-window failure | {int((audit['audit_status'] == 'estimator_input_failure').sum())} |",
        "nested_intervals": (
            f"Selection-aware nested intervals are available for {len(nested)}/"
            f"{complete_real_events} complete real comparisons; each requested "
            "1,000 repetitions and retained at least "
            f"{int(nested['valid_repetitions'].min())} valid repetitions."
        ),
        "nested_zero_exclusion": (
            f"Selection-aware intervals exclude zero for "
            f"{int(nested['selection_ci_excludes_zero'].sum())}/{len(nested)} "
            "MetaShift events."
        ),
        "physical_site_split": (
            f"The {int(split_audit['calibration_physical_sites'])} calibration "
            f"sites and {int(split_audit['evaluation_physical_sites'])} evaluation "
            "sites have disjoint complete target-plus-donor physical input footprints"
        ),
        "stable_samples": (
            "Each perturbation variant has "
            f"{int(aggregate.loc['standard_synthetic_control', 'evaluation_instances'] / 10)} "
            "evaluation samples."
        ),
        "time_placebos": (
            f"{len(complete_placebos)} complete events have at least 50 unique "
            "stable post-transition time placebos."
        ),
        "time_placebos_100": (
            f"{int((placebos['placebo_count'] >= 100).sum())} of these have 100 "
            "unique placebos."
        ),
        "raw_placebo_screen": (
            f"{int((complete_placebos['placebo_p_value'] <= 0.10).sum())} events "
            "have raw within-event placebo probability at most 0.10;"
        ),
        "fdr_screen": (
            f"{int((q_values <= 0.10).sum())} events pass exploratory "
            "Benjamini-Hochberg q<=0.10 screening."
        ),
        "evidence_tiers": (
            f"Evidence tiers contain "
            f"{evidence['counts']['supported_candidate_discontinuity']} supported "
            f"candidates, {evidence['counts']['not_supported_by_available_evidence']} "
            f"not-supported events, and "
            f"{evidence['counts']['inconclusive_insufficient_evidence']} "
            "inconclusive events."
        ),
        "loo_direction": (
            f"{int(complete_loo['direction_stable_all_donors'].sum())}/"
            f"{len(complete_loo)} complete leave-one-donor-out events retain "
            "direction under every donor removal."
        ),
        "sensitivity_88502": (
            f"The independent 88502 pipeline has "
            f"{int(sensitivity_88502['eligible_anchors'])} eligible metadata anchors "
            f"and {int((audit_88502['audit_status'] == 'complete').sum())} "
            "complete common-method comparisons."
        ),
        "screening_radius": (
            f"With a minimum of three donors, the primary setting has "
            f"{int(donor_three['primary'])} eligible anchors; a 50 km radius has "
            f"{int(donor_three['distance_50'])} and a 200 km radius has "
            f"{int(donor_three['distance_200'])}."
        ),
        "screening_coverage_window": (
            "Across 70%, 75%, and 80% daily-coverage rules, the count is "
            f"{int(donor_three['coverage_70'])}, {int(donor_three['primary'])}, "
            f"and {int(donor_three['coverage_80'])}; across 45, 60, and 90-day "
            f"stable-window rules, it is {int(donor_three['window_45'])}, "
            f"{int(donor_three['primary'])}, and {int(donor_three['window_90'])}."
        ),
        "risk_coverage": (
            "chosen at the 90th calibration percentile retains "
            f"{int(standard_risk['evaluation_cases'])}/"
            f"{int(standard_full_risk['evaluation_cases'])} evaluation sites and "
            f"has local-effect MAE {format_decimal(standard_risk['local_effect_mae_log'], 5)}, "
            f"versus {format_decimal(standard_full_risk['local_effect_mae_log'], 5)} "
            "at full"
        ),
        "effect_window_stability": (
            "The 45-day window is complete for "
            f"{int(metashift_windows.loc[45, 'event_count'])}/{complete_real_events} "
            "events with "
            f"{format_decimal(100 * metashift_windows.loc[45, 'sign_agreement_with_60_day'], 1)}% "
            "direction agreement to 60 days; the 90-day window is complete for "
            f"{int(metashift_windows.loc[90, 'event_count'])}/{complete_real_events} "
            "events with "
            f"{format_decimal(100 * metashift_windows.loc[90, 'sign_agreement_with_60_day'], 1)}% "
            "agreement."
        ),
        "external_document_review": (
            f"A targeted review of {int(external_documents['reviewed_events'])} "
            "preselected official documentation cases also found "
            f"{int(external_documents['site_specific_dated_confirmations'])}/"
            f"{int(external_documents['reviewed_events'])} dated, "
            "site-specific confirmations"
        ),
        "donor_as_treated_placebos": (
            f"The donor-as-treated analysis contains {len(donor_placebos):,} "
            "records, with median standardized score "
            f"{format_decimal(donor_placebos['standardized_score'].median(), 5)}."
        ),
        "date_resampling_placebos": (
            f"The {len(date_permutations)}-resampling global comparison gives an "
            "upper-tail probability of "
            f"{format_decimal(date_resampling_upper_tail, 5)}"
        ),
        "real_effect_medians": (
            "is "
            f"{format_decimal(method_medians['metashift_v1_fixed'], 5)} for "
            "fixed-prior MetaShift, "
            f"{format_decimal(method_medians['standard_synthetic_control'], 5)} "
            "for standard synthetic control, and "
            f"{format_decimal(method_medians['nearest_neighbor_did'], 5)} "
            "for nearest-neighbor DiD."
        ),
        "effect_window_medians": (
            "The corresponding fixed-prior MetaShift median log effects are "
            f"{format_decimal(metashift_windows.loc[45, 'median_log_effect'], 5)}, "
            f"{format_decimal(metashift_windows.loc[60, 'median_log_effect'], 5)}, "
            f"and {format_decimal(metashift_windows.loc[90, 'median_log_effect'], 5)} "
            "for 45, 60, and 90 days. "
            f"{int(unavailable_windows.loc[45, 'event_count'])} 45-day and "
            f"{int(unavailable_windows.loc[90, 'event_count'])} 90-day events "
            "are unavailable"
        ),
        "reporting_scale": (
            "At the 60-day primary window, log-effect and raw-unit effect signs "
            "agree for "
            f"{format_decimal(100 * reporting_scale.loc['metashift_v1_fixed', 'log_raw_direction_agreement'], 1)}% "
            "of MetaShift events, "
            f"{format_decimal(100 * reporting_scale.loc['standard_synthetic_control', 'log_raw_direction_agreement'], 1)}% "
            "of standard synthetic-control events, and "
            f"{format_decimal(100 * reporting_scale.loc['nearest_neighbor_did', 'log_raw_direction_agreement'], 1)}% "
            "of nearest-neighbor events. Absolute log effects also have Spearman "
            "correlations of "
            f"{format_decimal(reporting_scale.loc['metashift_v1_fixed', 'spearman_abs_log_vs_raw'], 3)}, "
            f"{format_decimal(reporting_scale.loc['standard_synthetic_control', 'spearman_abs_log_vs_raw'], 3)}, "
            f"and {format_decimal(reporting_scale.loc['nearest_neighbor_did', 'spearman_abs_log_vs_raw'], 3)} "
            "with absolute raw effects"
        ),
        "tier_sensitivity": (
            "supported-candidate counts are "
            f"{int(tier_sensitivity.loc['strict', 'supported_candidate_discontinuity'])}, "
            f"{int(tier_sensitivity.loc['primary', 'supported_candidate_discontinuity'])}, "
            f"and {int(tier_sensitivity.loc['lenient', 'supported_candidate_discontinuity'])}. "
            "The corresponding not-supported counts are "
            f"{int(tier_sensitivity.loc['strict', 'not_supported_by_available_evidence'])}, "
            f"{int(tier_sensitivity.loc['primary', 'not_supported_by_available_evidence'])}, "
            f"and {int(tier_sensitivity.loc['lenient', 'not_supported_by_available_evidence'])}; "
            "all three settings retain "
            f"{int(tier_sensitivity.loc['primary', 'inconclusive_insufficient_evidence'])} "
            "inconclusive events."
        ),
        "conditional_coverage": (
            "conditional block-bootstrap intervals cover "
            f"{format_decimal(100 * conditional_coverage['empirical_coverage'].min(), 3)}%--"
            f"{format_decimal(100 * conditional_coverage['empirical_coverage'].max(), 3)}% "
            "of known truths across methods, despite "
            f"{int(conditional_coverage['event_instances'].iloc[0]):,} effect "
            "instances per method."
        ),
        "conformal_coverage": (
            "Nominal-90% split-conformal intervals cover "
            f"{format_decimal(100 * conformal_coverage['empirical_coverage'].min(), 4)}%--"
            f"{format_decimal(100 * conformal_coverage['empirical_coverage'].max(), 4)}%."
        ),
    }
    for method, row in aggregate.iterrows():
        expectations[f"aggregate:{method}"] = exact_table_row(
            {
                "standard_synthetic_control": "Standard synthetic control",
                "metashift_v1_fixed": "MetaShift fixed-prior",
                "metashift_v2_cv": "MetaShift cross-validated",
                "nearest_neighbor_did": "Nearest-neighbor DiD",
                "bayesian_mean_shift": "Bayesian mean shift",
                "before_after_median": "Before-after median",
                "cusum": "CUSUM",
                "pelt": "PELT",
                "rolling_mad": "Rolling-MAD",
            }[method],
            row["local_effect_mae_log"],
            row["average_precision"],
            row["macro_f1"],
            row["false_positive_rate"],
        )
    ablation_labels = {
        "standard_synthetic_control": "Standard synthetic control",
        "metashift_full_correlation_distance": "MetaShift full prior, ridge=0.1",
        "ablation_no_graph_prior": "No graph-prior penalty",
        "ablation_no_distance": "No distance term",
        "ablation_no_ridge": "No ridge penalty",
        "ablation_ridge_0_01": "Ridge=0.01",
        "ablation_ridge_1_0": "Ridge=1.0",
        "ablation_direct_reliability": "Direct reliability weights",
    }
    for method, label in ablation_labels.items():
        row = ablation.loc[method]
        expectations[f"ablation:{method}"] = (
            f"| {label} | {format_decimal(row['local_effect_mae_log'], 5)} | "
            f"{format_decimal(row['macro_f1'], 5)} | "
            f"{format_decimal(row['false_positive_rate'], 3)} |"
        )
    table4_labels = {
        "primary": "Primary: 75%, 60 days, 7-day gap, 100 km, rho>=0.60",
        "coverage_70": "Coverage 70%",
        "coverage_80": "Coverage 80%",
        "window_45": "Stable window 45 days",
        "window_90": "Stable window 90 days",
        "gap_3": "Transition gap 3 days",
        "gap_14": "Transition gap 14 days",
        "distance_50": "Donor radius 50 km",
        "distance_200": "Donor radius 200 km",
        "correlation_050": "Correlation rho>=0.50",
        "correlation_070": "Correlation rho>=0.70",
    }
    donor_three_rows = screening.loc[
        screening["minimum_donors_required"] == 3
    ].set_index("setting")
    for setting, label in table4_labels.items():
        row = donor_three_rows.loc[setting]
        expectations[f"screening_table:{setting}"] = (
            f"| {label} | {int(row['eligible_anchors_before_donor_threshold'])} | "
            f"{int(row['eligible_anchors_after_donor_threshold'])} |"
        )
    for comparison, row in bootstrap.iterrows():
        label = {
            "metashift_v1_fixed minus standard_synthetic_control": "fixed-prior MetaShift",
            "metashift_v2_cv minus standard_synthetic_control": "cross-validated MetaShift",
        }[comparison]
        expectations[f"bootstrap:{comparison}"] = (
            f"for {label} minus standard synthetic control is "
            f"{format_decimal(row['mae_difference_log'], 5)} (95% CI "
            f"[{format_decimal(row['bootstrap_95ci_lower'], 5)}, "
            f"{format_decimal(row['bootstrap_95ci_upper'], 5)}])"
        )
    for method, count in interval_counts.items():
        label = {
            "metashift_v1_fixed": "MetaShift",
            "standard_synthetic_control": "standard synthetic-control",
            "nearest_neighbor_did": "nearest-neighbor",
        }[method]
        expectations[f"conditional_interval:{method}"] = (
            f"{int(count)}/{len(audit.loc[audit['audit_status'] == 'complete'])} "
            f"{label} events"
        )
    return expectations


def main() -> None:
    args = parse_args()
    paper_path = resolve_from_root(args.manuscript)
    output_path = resolve_from_root(args.output)
    manuscript = paper_path.read_text(encoding="utf-8")
    normalized_manuscript = re.sub(r"\s+", " ", manuscript)
    expectations = collect_expectations()
    checks = []
    for name, fragment in expectations.items():
        checks.append(
            {
                "name": name,
                "passed": re.sub(r"\s+", " ", fragment) in normalized_manuscript,
                "expected_fragment": fragment,
            }
        )
    # Detect stale basic tier triplets that should not coexist with the generated
    # primary configuration after the manuscript has been updated.
    stale_patterns = [
        r"\b54\b.*\b113\b.*\b396\b",
        r"\b54\s+anchors\b",
    ]
    for pattern in stale_patterns:
        checks.append(
            {
                "name": f"no_stale_pattern:{pattern}",
                "passed": re.search(pattern, normalized_manuscript, flags=re.IGNORECASE)
                is None,
                "expected_fragment": "No obsolete evidence-tier count pattern",
            }
        )
    output = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
        ).strip(),
        "manuscript": str(paper_path.relative_to(ROOT)),
        "all_numbers_match": all(check["passed"] for check in checks),
        "checks": checks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    failed = [check["name"] for check in checks if not check["passed"]]
    print(json.dumps(output, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
