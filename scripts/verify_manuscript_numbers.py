"""Verify numeric claims in the manuscript against generated result artifacts."""

from __future__ import annotations

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
        ARTIFACTS / "stable_synthetic_stable_full_v1_metrics.csv"
    )
    aggregate = metrics.loc[metrics["perturbation_family"].isna()].set_index("method")
    bootstrap = pd.read_csv(
        ARTIFACTS / "stable_synthetic_stable_full_v1_bootstrap.csv"
    ).set_index("comparison")
    ablation = pd.read_csv(
        ARTIFACTS / "reliability_ablation_stable_full_v1_metrics.csv"
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
    risk_coverage = pd.read_csv(ARTIFACTS / "synthetic_risk_coverage_curve.csv")
    effect_windows = pd.read_csv(
        ARTIFACTS / "effect_window_sensitivity_summary.csv"
    )
    screening = pd.read_csv(ARTIFACTS / "screening_sensitivity_summary.csv")
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
            f"Selection-aware nested intervals complete all {len(nested)} real "
            f"comparison events with 1,000 repetitions each."
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
            f"{int(external_documents['site_specific_dated_confirmations'])} dated, "
            "site-specific confirmations"
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
    manuscript = PAPER_PATH.read_text(encoding="utf-8")
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
        "manuscript": str(PAPER_PATH.relative_to(ROOT)),
        "all_numbers_match": all(check["passed"] for check in checks),
        "checks": checks,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    failed = [check["name"] for check in checks if not check["passed"]]
    print(json.dumps(output, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
