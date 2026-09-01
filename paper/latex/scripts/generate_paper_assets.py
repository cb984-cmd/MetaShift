"""Generate formal-paper tables, macros, and vector figures from frozen evidence.

This script is intentionally read-only with respect to analysis artifacts. It
accepts only the tracked v0.3.2 evidence summary plus locally available,
hash-verified saved artifacts and writes paper-local derivative assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
LATEX_ROOT = Path(__file__).resolve().parents[1]
GENERATED = LATEX_ROOT / "generated"
TABLES = GENERATED / "tables"
FIGURES = GENERATED / "figures"
MANIFEST_PATH = GENERATED / "asset_manifest.json"
LAYOUT_QA_PATH = GENERATED / "figure_layout_qa.json"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
CASE_RENDERING_CONFIG_PATH = LATEX_ROOT / "configs" / "case_study_rendering_v2.json"
SYNTHETIC_EXAMPLE_CONFIG_PATH = (
    LATEX_ROOT / "configs" / "synthetic_motivating_example_v1.json"
)
EXTERNAL_EVIDENCE_CONFIG_PATH = (
    LATEX_ROOT / "configs" / "external_evidence_rendering_v1.json"
)
WINDOW_PROTOCOL_CONFIG_PATH = LATEX_ROOT / "configs" / "window_protocol_audit_v1.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from metashift.counterfactual import (
    donor_weights,
    estimate_metadata_anchor,
    reliability_constrained_weights,
    weighted_donor_series,
)
from metashift.synthetic import PerturbationKind, inject_perturbation

from figure_factory import create_revised_figures, inspect_figure_layout

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
    "ablation_no_graph_prior": "No reliability-prior penalty",
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

ALL_METHOD_ORDER = (
    "standard_synthetic_control",
    "metashift_v1_fixed",
    "metashift_v2_cv",
    "nearest_neighbor_did",
    "bayesian_mean_shift",
    "before_after_median",
    "cusum",
    "rolling_mad",
    "pelt",
)

FAMILY_ORDER = (
    "additive_step",
    "proportional_step",
    "gradual_drift",
    "temporary_step",
    "variance_increase",
)

FAMILY_LABELS = {
    "additive_step": "Additive\nstep",
    "proportional_step": "Proportional\nstep",
    "gradual_drift": "Gradual\ndrift",
    "temporary_step": "Temporary\nstep",
    "variance_increase": "Variance\nincrease",
}

COLORS = {
    "Standard SC": "#4C566A",
    "MetaShift fixed": "#3B82F6",
    "MetaShift CV": "#7C3AED",
    "Nearest-neighbor DiD": "#0F766E",
    "Supported candidate": "#2563EB",
    "Not supported": "#F59E0B",
    "Inconclusive": "#94A3B8",
}

CASE_COLUMNS = [
    "State Code",
    "County Code",
    "Site Num",
    "POC",
    "Sample Duration",
    "Date Local",
    "Arithmetic Mean",
    "Observation Percent",
    "Event Type",
]

CASE_DTYPES = {
    "State Code": "string",
    "County Code": "string",
    "Site Num": "string",
    "POC": "string",
    "Sample Duration": "category",
    "Arithmetic Mean": "float64",
    "Observation Percent": "float64",
    "Event Type": "category",
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


def metric_display(value: object, places: int) -> str:
    return "N/A" if pd.isna(value) else format_decimal(float(value), places)


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


def relative_to_root(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def safe_root_path(relative_path: str) -> Path:
    candidate = ROOT / Path(relative_path)
    try:
        candidate.resolve().relative_to(ROOT.resolve())
    except ValueError as error:
        raise RuntimeError(f"Presentation input escapes repository root: {relative_path}") from error
    return candidate


def load_case_rendering_config() -> dict[str, Any]:
    if not CASE_RENDERING_CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"Missing deterministic case-study configuration: {CASE_RENDERING_CONFIG_PATH}"
        )
    config = json.loads(CASE_RENDERING_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError("Case-study rendering configuration must be a JSON object.")
    return config


def load_json_config(path: Path, description: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {description}: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError(f"{description} must be a JSON object.")
    return config


def verify_hashed_record(
    record: object, field: str, description: str
) -> tuple[str, str]:
    if not isinstance(record, dict):
        raise RuntimeError(f"{description} lacks {field}.")
    relative_path = record.get("path")
    expected_hash = record.get("sha256")
    if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
        raise RuntimeError(f"{description} {field} must specify path and sha256.")
    path = safe_root_path(relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"Missing {description} input: {path}")
    if sha256(path) != expected_hash:
        raise RuntimeError(f"{description} input checksum mismatch: {relative_path}")
    return relative_path, expected_hash


def verify_case_rendering_inputs() -> dict[str, Any]:
    config = load_case_rendering_config()
    expected_identity = {
        "schema_version": 2,
        "evidence_version": "v0.3.2",
        "evidence_tag": "v0.3.2-evidence-final",
    }
    for field, expected in expected_identity.items():
        if config.get(field) != expected:
            raise RuntimeError(
                f"Case-study rendering configuration has unexpected {field}: "
                f"{config.get(field)!r}"
            )
    for field in ("source_manifest", "geographic_controls"):
        verify_hashed_record(record=config.get(field), field=field, description="Case-study configuration")
    if not isinstance(config.get("selection"), dict) or not isinstance(
        config.get("reconstruction"), dict
    ):
        raise RuntimeError("Case-study configuration lacks selection or reconstruction rules.")
    return config


def verify_synthetic_example_inputs() -> dict[str, Any]:
    config = load_json_config(
        SYNTHETIC_EXAMPLE_CONFIG_PATH, "synthetic motivating-example configuration"
    )
    expected_identity = {
        "schema_version": 1,
        "evidence_version": "v0.3.2",
        "evidence_tag": "v0.3.2-evidence-final",
    }
    for field, expected in expected_identity.items():
        if config.get(field) != expected:
            raise RuntimeError(
                f"Synthetic motivating-example configuration has unexpected {field}: "
                f"{config.get(field)!r}"
            )
    for field in ("stable_cases", "stable_case_donors"):
        verify_hashed_record(
            record=config.get(field),
            field=field,
            description="Synthetic motivating-example configuration",
        )
    selection = config.get("selection")
    injection = config.get("injection")
    display = config.get("display")
    if not all(isinstance(value, dict) for value in (selection, injection, display)):
        raise RuntimeError(
            "Synthetic motivating-example configuration lacks selection, injection, or display."
        )
    return config


def verify_external_evidence_inputs() -> dict[str, Any]:
    config = load_json_config(
        EXTERNAL_EVIDENCE_CONFIG_PATH, "external-evidence rendering configuration"
    )
    if (
        config.get("schema_version") != 1
        or config.get("evidence_version") != "v0.3.2"
        or config.get("evidence_tag") != "v0.3.2-evidence-final"
    ):
        raise RuntimeError("External-evidence rendering configuration identity is invalid.")
    path, _ = verify_hashed_record(
        record=config.get("qa_collocation_evidence"),
        field="qa_collocation_evidence",
        description="External-evidence rendering configuration",
    )
    qa_config = config["qa_collocation_evidence"]
    expected = qa_config.get("expected_counts")
    if not isinstance(expected, dict):
        raise RuntimeError("External-evidence rendering configuration lacks expected QA counts.")
    records = pd.read_csv(safe_root_path(path))
    qa = records.loc[records["evidence_source"] == "qa_collocation"]
    actual = {
        "candidates": int(len(qa)),
        "target_poc_matched": int(
            (
                qa["evidence_status"]
                == "insufficient_matched_pre_post_qa_records"
            ).sum()
        ),
        "adequate_matched_pre_post": int(
            (qa["evidence_status"] == "paired_pre_post_available").sum()
        ),
    }
    if actual != {key: int(value) for key, value in expected.items()}:
        raise RuntimeError(
            f"External-evidence QA counts do not match the display contract: {actual}"
        )
    return config


def verify_window_protocol_inputs() -> dict[str, Any]:
    config = load_json_config(
        WINDOW_PROTOCOL_CONFIG_PATH, "window-protocol audit configuration"
    )
    if (
        config.get("schema_version") != 1
        or config.get("evidence_version") != "v0.3.2"
        or config.get("evidence_tag") != "v0.3.2-evidence-final"
    ):
        raise RuntimeError("Window-protocol audit configuration identity is invalid.")
    sources = config.get("implementation_sources")
    windows = config.get("windows")
    if not isinstance(sources, list) or not isinstance(windows, dict):
        raise RuntimeError("Window-protocol audit configuration lacks sources or windows.")
    for source in sources:
        verify_hashed_record(
            record=source,
            field="implementation_source",
            description="Window-protocol audit configuration",
        )
    calibration = windows.get("calibration")
    pre = windows.get("pre")
    post = windows.get("post")
    if not all(isinstance(value, dict) for value in (calibration, pre, post)):
        raise RuntimeError("Window-protocol audit configuration lacks window definitions.")
    required_offsets = {
        "calibration": (-180, -15, 166),
        "pre": (-60, -1, 60),
        "post": (0, 59, 60),
    }
    for name, (start, end, expected_count) in required_offsets.items():
        record = windows[name]
        if (
            int(record.get("start_offset_days", 999)) != start
            or int(record.get("end_offset_days", 999)) != end
            or int(record.get("inclusive_calendar_dates", -1)) != expected_count
        ):
            raise RuntimeError(f"Window-protocol audit has invalid {name} bounds.")
    overlap = int(windows.get("calibration_pre_overlap_calendar_dates", -1))
    if overlap != 46:
        raise RuntimeError("Window-protocol audit must record the 46-date pre-window overlap.")
    return config


def presentation_input_sources(
    case_config: dict[str, Any],
    synthetic_config: dict[str, Any],
    external_config: dict[str, Any],
    window_config: dict[str, Any],
) -> list[dict[str, str]]:
    paths = [
        CASE_RENDERING_CONFIG_PATH,
        SYNTHETIC_EXAMPLE_CONFIG_PATH,
        EXTERNAL_EVIDENCE_CONFIG_PATH,
        WINDOW_PROTOCOL_CONFIG_PATH,
        ROOT / "configs" / "benchmark_release_v2.json",
        ROOT / "configs" / "evidence_tier_primary_v1.json",
        ROOT / "configs" / "evidence_tier_sensitivity_v2.json",
        safe_root_path(str(case_config["source_manifest"]["path"])),
        safe_root_path(str(case_config["geographic_controls"]["path"])),
        safe_root_path(str(synthetic_config["stable_cases"]["path"])),
        safe_root_path(str(synthetic_config["stable_case_donors"]["path"])),
        safe_root_path(str(external_config["qa_collocation_evidence"]["path"])),
        *(
            safe_root_path(str(record["path"]))
            for record in window_config["implementation_sources"]
        ),
    ]
    return [
        {"path": relative_to_root(path), "sha256": sha256(path)}
        for path in paths
    ]


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
    verify_case_rendering_inputs()
    verify_synthetic_example_inputs()
    verify_external_evidence_inputs()
    verify_window_protocol_inputs()


def latex_table(
    label: str,
    caption: str,
    alignment: str,
    headers: list[str],
    rows: list[list[str]],
    note: str,
    size: str = r"\small",
    scale_to_width: bool = False,
    placement: str = "tbp",
) -> str:
    lines = [
        rf"\begin{{table}}[{placement}]",
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


def normalized_code(value: object, width: int) -> str:
    return str(value).strip().zfill(width)


def load_case_series(config: dict[str, Any]) -> dict[tuple[str, str, str, str], pd.Series]:
    """Load only the checksum-pinned public archives needed for display reconstruction."""
    source_manifest_path = safe_root_path(str(config["source_manifest"]["path"]))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(source_manifest, list) or not source_manifest:
        raise RuntimeError("Case-study source manifest must contain archive records.")
    parameter_code = str(config["reconstruction"]["parameter_code"])
    archive_records = sorted(
        (
            record
            for record in source_manifest
            if isinstance(record, dict)
            and str(record.get("parameter_code")) == parameter_code
        ),
        key=lambda record: int(record["year"]),
    )
    if len(archive_records) != len(source_manifest):
        raise RuntimeError(
            "Case-study source manifest contains an unexpected non-primary parameter."
        )
    frames: list[pd.DataFrame] = []
    for record in archive_records:
        relative_path = str(record.get("path", ""))
        csv_member = str(record.get("csv_member", ""))
        expected_hash = str(record.get("sha256", ""))
        raw_path = safe_root_path(relative_path)
        if not raw_path.is_file():
            raise FileNotFoundError(
                "Case-study reconstruction requires the checksum-pinned public "
                f"archive: {raw_path}"
            )
        if sha256(raw_path) != expected_hash:
            raise RuntimeError(f"Raw archive checksum mismatch: {relative_path}")
        with zipfile.ZipFile(raw_path) as archive:
            if csv_member not in archive.namelist():
                raise RuntimeError(
                    f"Expected CSV member {csv_member!r} is absent from {relative_path}"
                )
            with archive.open(csv_member) as source:
                frame = pd.read_csv(
                    source,
                    usecols=CASE_COLUMNS,
                    dtype=CASE_DTYPES,
                    parse_dates=["Date Local"],
                    low_memory=False,
                )
        included = frame["Event Type"].astype("string").fillna("") != "Excluded"
        valid = (
            (frame["Sample Duration"] == "24-HR BLK AVG")
            & included
            & frame["Arithmetic Mean"].notna()
            & np.isfinite(frame["Arithmetic Mean"])
            & (frame["Observation Percent"] >= 75)
        )
        retained = frame.loc[
            valid,
            ["State Code", "County Code", "Site Num", "POC", "Date Local", "Arithmetic Mean"],
        ].copy()
        retained["State Code"] = retained["State Code"].str.zfill(2)
        retained["County Code"] = retained["County Code"].str.zfill(3)
        retained["Site Num"] = retained["Site Num"].str.zfill(4)
        frames.append(retained)
    canonical = pd.concat(frames, ignore_index=True)
    identity = ["State Code", "County Code", "Site Num", "POC", "Date Local"]
    if canonical.duplicated(identity).any():
        raise RuntimeError("Checksum-pinned case-study data contain duplicate monitor-days.")
    return {
        tuple(str(value) for value in key): group.set_index("Date Local")[
            "Arithmetic Mean"
        ].sort_index()
        for key, group in canonical.groupby(
            ["State Code", "County Code", "Site Num", "POC"],
            observed=True,
            sort=True,
        )
    }


def select_case_rows(data: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    tiers = data["tiers"].copy()
    selection_rules = config["selection"]
    selections = (
        (
            "Supported candidate",
            selection_rules["supported_candidate"],
            "median_standardized_score",
        ),
        (
            "Not supported",
            selection_rules["not_supported"],
            "median_standardized_score",
        ),
        (
            "Inconclusive: no qualified counterfactual",
            selection_rules["inconclusive_missing_counterfactual"],
            "lexicographic_anchor_id",
        ),
    )
    selected: list[dict[str, Any]] = []
    for label, rule, strategy in selections:
        candidates = tiers.loc[
            (tiers["evidence_tier"] == rule["evidence_tier"])
            & (tiers["audit_status"] == rule["required_audit_status"])
        ].copy()
        if candidates.empty:
            raise RuntimeError(f"No deterministic case candidate is available for {label}.")
        if strategy == "median_standardized_score":
            if candidates["standardized_score"].isna().any():
                raise RuntimeError(f"Case candidates for {label} lack standardized scores.")
            median_score = float(candidates["standardized_score"].median())
            candidates["selection_distance"] = (
                candidates["standardized_score"] - median_score
            ).abs()
            row = candidates.sort_values(
                ["selection_distance", "anchor_id"], kind="stable"
            ).iloc[0]
        else:
            median_score = None
            row = candidates.sort_values("anchor_id", kind="stable").iloc[0]
        record = row.to_dict()
        record["case_group"] = label
        record["selection_strategy"] = strategy
        record["selection_rule"] = str(rule["rule"])
        record["within_group_median_standardized_score"] = median_score
        selected.append(record)
    return selected


def as_optional_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def as_optional_text(value: object) -> str:
    return "" if pd.isna(value) else str(value)


def build_case_records(
    data: dict[str, Any],
    config: dict[str, Any],
    series: dict[tuple[str, str, str, str], pd.Series] | None = None,
) -> list[dict[str, Any]]:
    selected_cases = select_case_rows(data, config)
    if series is None:
        series = load_case_series(config)
    controls = pd.read_csv(
        safe_root_path(str(config["geographic_controls"]["path"])), dtype="string"
    )
    for column in (
        "distance_km",
        "pre_transition_paired_days",
        "pre_transition_log_correlation",
        "rank",
    ):
        controls[column] = pd.to_numeric(controls[column])
    maximum_donors = int(config["reconstruction"]["maximum_ranked_donors"])
    method_results = data["method_results"]
    records: list[dict[str, Any]] = []
    for selected in selected_cases:
        target_key = (
            normalized_code(selected["target_state"], 2),
            normalized_code(selected["target_county"], 3),
            normalized_code(selected["target_site"], 4),
            str(selected["target_poc"]).strip(),
        )
        if target_key not in series:
            raise RuntimeError(
                "Checksum-pinned source archives lack selected target series: "
                + "-".join(target_key)
            )
        anchor_id = str(selected["anchor_id"])
        anchor_date = pd.Timestamp(selected["anchor_date"])
        visible_start = anchor_date - pd.Timedelta(
            days=int(config["reconstruction"]["visible_days_before_anchor"])
        )
        visible_end = anchor_date + pd.Timedelta(
            days=int(config["reconstruction"]["visible_days_after_anchor"])
        )
        placebo_rows = data["time_placebo"].loc[
            data["time_placebo"]["anchor_id"].astype("string") == anchor_id
        ]
        if len(placebo_rows) > 1:
            raise RuntimeError(f"Expected at most one time-placebo row for {anchor_id}.")
        placebo = placebo_rows.iloc[0] if len(placebo_rows) == 1 else None
        record: dict[str, Any] = {
            "case_group": str(selected["case_group"]),
            "selection_strategy": str(selected["selection_strategy"]),
            "selection_rule": str(selected["selection_rule"]),
            "selection_median_score": selected[
                "within_group_median_standardized_score"
            ],
            "anchor_id": anchor_id,
            "anchor_date": anchor_date,
            "audit_status": str(selected["audit_status"]),
            "audit_reason": as_optional_text(selected.get("audit_reason")),
            "evidence_tier": str(selected["evidence_tier"]),
            "evidence_reasons": as_optional_text(selected.get("evidence_reasons")),
            "target": series[target_key],
            "visible_start": visible_start,
            "visible_end": visible_end,
            "log_effect": as_optional_float(selected.get("log_effect")),
            "fixed_interval": (
                as_optional_float(selected.get("ci95_lower")),
                as_optional_float(selected.get("ci95_upper")),
            ),
            "nested_interval": (
                as_optional_float(selected.get("selection_ci95_lower")),
                as_optional_float(selected.get("selection_ci95_upper")),
            ),
            "placebo_count": as_optional_float(selected.get("placebo_count")),
            "placebo_p_value": as_optional_float(selected.get("placebo_p_value")),
            "placebo_actual_score": (
                as_optional_float(placebo.get("actual_standardized_score"))
                if placebo is not None
                else None
            ),
            "placebo_median_score": (
                as_optional_float(placebo.get("placebo_median_score"))
                if placebo is not None
                else None
            ),
            "leave_one_donor_out_fraction": as_optional_float(
                selected.get("leave_one_donor_out_direction_fraction")
            ),
        }
        if record["audit_status"] != "complete":
            records.append(record)
            continue
        selected_controls = (
            controls.loc[controls["anchor_id"] == anchor_id]
            .sort_values("rank", kind="stable")
            .head(maximum_donors)
            .copy()
        )
        if len(selected_controls) < 3:
            raise RuntimeError(
                f"Saved complete case {anchor_id} has fewer than three selected donors."
            )
        donor_columns: dict[str, pd.Series] = {}
        for donor in selected_controls.itertuples(index=False):
            donor_key = (
                normalized_code(donor.control_state_code, 2),
                normalized_code(donor.control_county_code, 3),
                normalized_code(donor.control_site_num, 4),
                str(donor.control_poc).strip(),
            )
            if donor_key not in series:
                raise RuntimeError(
                    "Checksum-pinned source archives lack selected donor series: "
                    + "-".join(donor_key)
                )
            donor_columns["-".join(donor_key)] = series[donor_key]
        donors = pd.DataFrame(donor_columns)
        metadata = selected_controls.copy()
        metadata.index = donors.columns
        prior = donor_weights(metadata)
        calibration = slice(
            anchor_date - pd.Timedelta(days=180),
            anchor_date - pd.Timedelta(days=15),
        )
        weights = reliability_constrained_weights(
            record["target"].loc[calibration],
            donors.loc[calibration],
            prior,
            ridge_penalty=0.1,
            prior_penalty=0.1,
        )
        estimate = estimate_metadata_anchor(
            record["target"], donors, weights, anchor_date
        )
        saved = method_results.loc[
            (method_results["anchor_id"] == anchor_id)
            & (method_results["method"] == "metashift_v1_fixed")
        ]
        if len(saved) != 1:
            raise RuntimeError(
                f"Expected exactly one saved fixed-MetaShift result for {anchor_id}."
            )
        saved_log_effect = float(saved.iloc[0]["log_effect"])
        reconstructed_log_effect = float(estimate.log_effect)
        absolute_error = abs(saved_log_effect - reconstructed_log_effect)
        if absolute_error > 1e-9:
            raise RuntimeError(
                f"Case reconstruction does not match frozen effect for {anchor_id}: "
                f"{absolute_error:.3g}"
            )
        raw_donor, _ = weighted_donor_series(donors, weights, logarithmic=False)
        log_target = np.log1p(record["target"].clip(lower=0))
        log_donor, _ = weighted_donor_series(donors, weights, logarithmic=True)
        raw_calibration = pd.concat(
            [record["target"].rename("target"), raw_donor.rename("donor")],
            axis="columns",
            sort=False,
        ).loc[calibration].dropna()
        log_calibration = pd.concat(
            [log_target.rename("target"), log_donor.rename("donor")],
            axis="columns",
            sort=False,
        ).loc[calibration].dropna()
        if raw_calibration.empty or log_calibration.empty:
            raise RuntimeError(
                f"Case reconstruction has no retained calibration overlap for {anchor_id}."
            )
        record.update(
            {
                "donors": donors,
                "counterfactual": raw_donor
                + float(np.median(raw_calibration["target"] - raw_calibration["donor"])),
                "residual": log_target
                - log_donor
                - float(
                    np.median(log_calibration["target"] - log_calibration["donor"])
                ),
                "selected_donors": [
                    {
                        "physical_site": "-".join(
                            [
                                normalized_code(donor.control_state_code, 2),
                                normalized_code(donor.control_county_code, 3),
                                normalized_code(donor.control_site_num, 4),
                            ]
                        ),
                        "poc": str(donor.control_poc).strip(),
                        "distance_km": float(donor.distance_km),
                        "pre_event_log_correlation": float(
                            donor.pre_transition_log_correlation
                        ),
                    }
                    for donor in selected_controls.itertuples(index=False)
                ],
                "weights": {key: float(value) for key, value in weights.items()},
                "saved_log_effect": saved_log_effect,
                "reconstructed_log_effect": reconstructed_log_effect,
                "reconstruction_absolute_error": absolute_error,
            }
        )
        records.append(record)
    return records


def build_synthetic_motivating_example(
    config: dict[str, Any],
    series: dict[tuple[str, str, str, str], pd.Series],
) -> dict[str, Any]:
    """Reconstruct a deterministic display-only synthetic example from pinned inputs."""

    cases = pd.read_csv(
        safe_root_path(str(config["stable_cases"]["path"])), dtype="string"
    )
    donors = pd.read_csv(
        safe_root_path(str(config["stable_case_donors"]["path"])), dtype="string"
    )
    for column in (
        "rank",
        "distance_km",
        "pre_transition_paired_days",
        "pre_transition_log_correlation",
    ):
        donors[column] = pd.to_numeric(donors[column], errors="raise")
    evaluation = cases.loc[cases["split"] == "evaluation"].sort_values(
        "case_id", kind="stable"
    )
    if evaluation.empty:
        raise RuntimeError("Synthetic motivating example has no evaluation cases.")
    selected = evaluation.iloc[0]
    expected_case_id = str(config["selection"]["expected_case_id"])
    if str(selected["case_id"]) != expected_case_id:
        raise RuntimeError(
            "Synthetic motivating example selection differs from its frozen display contract."
        )
    target_key = (
        str(selected["State Code"]).zfill(2),
        str(selected["County Code"]).zfill(3),
        str(selected["Site Num"]).zfill(4),
        str(selected["POC"]),
    )
    target = series.get(target_key)
    if target is None:
        raise RuntimeError(
            "Checksum-pinned archives lack the selected stable target series: "
            + "-".join(target_key)
        )
    selected_donors = donors.loc[donors["case_id"] == selected["case_id"]].sort_values(
        "rank", kind="stable"
    )
    if len(selected_donors) < 3:
        raise RuntimeError("Synthetic motivating example has fewer than three donors.")
    donor_columns: dict[str, pd.Series] = {}
    for donor in selected_donors.itertuples(index=False):
        donor_key = (
            str(donor.control_state_code).zfill(2),
            str(donor.control_county_code).zfill(3),
            str(donor.control_site_num).zfill(4),
            str(donor.control_poc),
        )
        values = series.get(donor_key)
        if values is None:
            raise RuntimeError(
                "Checksum-pinned archives lack the selected stable donor series: "
                + "-".join(donor_key)
            )
        donor_columns["-".join(donor_key)] = values
    donor_frame = pd.DataFrame(donor_columns).sort_index()
    metadata = selected_donors.copy()
    metadata.index = donor_frame.columns
    anchor_date = pd.Timestamp(selected["pseudo_anchor_date"])
    calibration = slice(
        anchor_date - pd.Timedelta(days=180),
        anchor_date - pd.Timedelta(days=15),
    )
    prior = donor_weights(metadata)
    weights = reliability_constrained_weights(
        target.loc[calibration],
        donor_frame.loc[calibration],
        prior,
        ridge_penalty=0.1,
        prior_penalty=0.1,
    )
    pre_values = target.loc[calibration].dropna().to_numpy(dtype=float)
    if len(pre_values) < 60:
        raise RuntimeError("Synthetic motivating example lacks 60 calibration observations.")
    robust_scale = max(
        1.4826 * float(np.median(np.abs(pre_values - np.median(pre_values)))), 0.5
    )
    multiplier = float(config["injection"]["magnitude_multiplier"])
    magnitude = robust_scale * 2 * multiplier
    display_before = int(config["display"]["days_before_anchor"])
    display_after = int(config["display"]["days_after_anchor"])
    visible = slice(
        anchor_date - pd.Timedelta(days=display_before),
        anchor_date + pd.Timedelta(days=display_after),
    )
    raw_donor, _ = weighted_donor_series(donor_frame, weights, logarithmic=False)
    raw_calibration = pd.concat(
        [target.rename("target"), raw_donor.rename("donor")],
        axis="columns",
        sort=False,
    ).loc[calibration].dropna()
    log_target = np.log1p(target.clip(lower=0.0))
    log_donor, _ = weighted_donor_series(donor_frame, weights, logarithmic=True)
    log_calibration = pd.concat(
        [log_target.rename("target"), log_donor.rename("donor")],
        axis="columns",
        sort=False,
    ).loc[calibration].dropna()
    if raw_calibration.empty or log_calibration.empty:
        raise RuntimeError("Synthetic motivating example has no donor calibration overlap.")
    raw_offset = float(np.median(raw_calibration["target"] - raw_calibration["donor"]))
    log_offset = float(np.median(log_calibration["target"] - log_calibration["donor"]))

    variants: dict[str, pd.DataFrame] = {}
    for label, field in (("local", "local_kind"), ("regional", "regional_kind")):
        changed_target, changed_donors, _ = inject_perturbation(
            target,
            donor_frame,
            anchor_date,
            PerturbationKind(str(config["injection"][field])),
            magnitude,
            random_seed=int(config["injection"]["random_seed"]),
        )
        changed_raw_donor, _ = weighted_donor_series(
            changed_donors, weights, logarithmic=False
        )
        changed_log_donor, _ = weighted_donor_series(
            changed_donors, weights, logarithmic=True
        )
        display = pd.concat(
            [
                changed_target.rename("target"),
                (changed_raw_donor + raw_offset).rename("donor_composite"),
                (
                    np.log1p(changed_target.clip(lower=0.0))
                    - changed_log_donor
                    - log_offset
                ).rename("residual"),
            ],
            axis="columns",
            sort=False,
        ).loc[visible]
        display["relative_day"] = (display.index - anchor_date).days
        variants[label] = display
    return {
        "case_id": str(selected["case_id"]),
        "anchor_date": anchor_date,
        "magnitude": magnitude,
        "weights": {key: float(value) for key, value in weights.items()},
        "variants": variants,
    }


def case_study_manifest(
    summary: dict[str, Any], config: dict[str, Any], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    compact_cases = []
    for case in cases:
        compact_cases.append(
            {
                "case_group": case["case_group"],
                "selection_strategy": case["selection_strategy"],
                "selection_rule": case["selection_rule"],
                "within_group_median_standardized_score": case["selection_median_score"],
                "anchor_id": case["anchor_id"],
                "anchor_date": case["anchor_date"].date().isoformat(),
                "audit_status": case["audit_status"],
                "audit_reason": case["audit_reason"],
                "evidence_tier": case["evidence_tier"],
                "evidence_reasons": case["evidence_reasons"],
                "saved_log_effect": case.get("saved_log_effect"),
                "reconstructed_log_effect": case.get("reconstructed_log_effect"),
                "reconstruction_absolute_error": case.get(
                    "reconstruction_absolute_error"
                ),
                "fixed_interval": list(case["fixed_interval"]),
                "nested_interval": list(case["nested_interval"]),
                "placebo_count": case["placebo_count"],
                "placebo_p_value": case["placebo_p_value"],
                "placebo_actual_score": case["placebo_actual_score"],
                "placebo_median_score": case["placebo_median_score"],
                "leave_one_donor_out_direction_fraction": case[
                    "leave_one_donor_out_fraction"
                ],
                "selected_donors": case.get("selected_donors", []),
            }
        )
    return {
        "schema_version": 1,
        "purpose": "Display-only deterministic representative-case reconstruction.",
        "frozen_evidence": summary["frozen_evidence"],
        "result_label": summary["result_label"],
        "case_rendering_configuration": {
            "path": relative_to_root(CASE_RENDERING_CONFIG_PATH),
            "sha256": sha256(CASE_RENDERING_CONFIG_PATH),
        },
        "source_manifest": config["source_manifest"],
        "geographic_controls": config["geographic_controls"],
        "cases": compact_cases,
    }


def build_claim_value_manifest(
    summary: dict[str, Any],
    data: dict[str, Any],
    cases: list[dict[str, Any]],
    case_config: dict[str, Any],
    window_config: dict[str, Any],
    external_config: dict[str, Any],
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
    stable_manifest = data["stable_manifest"]
    anchor_dates = pd.to_datetime(audit["anchor_date"], errors="raise")
    anchors_2023 = audit.loc[anchor_dates.dt.year == 2023]
    pair_counts_2023 = (
        anchors_2023.assign(
            old_method_code=anchors_2023["old_method_code"].astype(str),
            new_method_code=anchors_2023["new_method_code"].astype(str),
        )
        .groupby(["old_method_code", "new_method_code"], dropna=False)
        .size()
        .sort_values(ascending=False)
    )
    paired_alignment_count = int(
        pair_counts_2023.loc[("236", "636")]
        + pair_counts_2023.loc[("238", "638")]
    )
    qa_counts = external_config["qa_collocation_evidence"]["expected_counts"]
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
        "Q08": ["reliability-prior", "cross-validated"],
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
        "Q33": [str(len(ALL_METHOD_ORDER)), "N/A"],
        "Q34": [
            str(len(FAMILY_ORDER)),
            str(
                int(
                    aggregate.loc[
                        "standard_synthetic_control", "evaluation_instances"
                    ]
                    / len(FAMILY_ORDER)
                )
            ),
        ],
        "Q35": [
            str(
                stable_manifest["case_source_counts"][
                    "method_transition_stable_regime"
                ]
            ),
            str(
                stable_manifest["case_source_counts"][
                    "all_monitor_stable_regime"
                ]
            ),
        ],
        "Q36": [
            *(str(case["anchor_id"]) for case in cases),
            "1e-9",
        ],
        "Q37": [
            f"{len(anchors_2023)}/{len(audit)}",
            percent(len(anchors_2023) / len(audit), 1).replace(r"\%", "%"),
            f"{paired_alignment_count}/{len(anchors_2023)}",
            percent(paired_alignment_count / len(anchors_2023), 1).replace(
                r"\%", "%"
            ),
        ],
        "Q38": [
            "t0-180 through t0-15",
            str(window_config["windows"]["calibration"]["inclusive_calendar_dates"]),
            str(window_config["windows"]["calibration_pre_overlap_calendar_dates"]),
        ],
        "Q39": [
            str(qa_counts["candidates"]),
            str(qa_counts["target_poc_matched"]),
            str(qa_counts["adequate_matched_pre_post"]),
        ],
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


def create_tables(
    summary: dict[str, Any],
    data: dict[str, Any],
    cases: list[dict[str, Any]],
) -> dict[Path, str]:
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
    stable_manifest = data["stable_manifest"]

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
            [
                "Stable pseudo-anchors from Method Code regimes",
                str(
                    stable_manifest["case_source_counts"][
                        "method_transition_stable_regime"
                    ]
                ),
            ],
            [
                "Stable pseudo-anchors from all-monitor regimes",
                str(
                    stable_manifest["case_source_counts"][
                        "all_monitor_stable_regime"
                    ]
                ),
            ],
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
                format_decimal(row["local_effect_mae_log"], 3),
                format_decimal(row["average_precision"], 3),
                format_decimal(row["macro_f1"], 3),
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
        placement="!ht",
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
                format_decimal(row["mae_difference_log"], 3),
                "["
                + format_decimal(row["bootstrap_95ci_lower"], 3)
                + ", "
                + format_decimal(row["bootstrap_95ci_upper"], 3)
                + "]",
                str(int(row["clusters"])),
            ]
        )
    tables[TABLES / "table_paired_bootstrap.tex"] = latex_table(
        "paired-bootstrap",
        "Paired event-cluster bootstrap for local-effect MAE differences.",
        "lrrr",
        ["Comparison", "Difference", "95\\% bootstrap interval", "Clusters"],
        paired_rows,
        "Difference is MetaShift minus standard synthetic control; negative values "
        "favor MetaShift on MAE. Both bootstrap intervals include zero.",
        placement="!ht",
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
                format_decimal(complete_method[method], 3),
            ]
        )
    real_audit_lines = [
        r"\begin{table}[!ht]",
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
        latex_row(
            ["Method", "Events", "Fixed conditional interval excludes 0", "Median log effect"]
        ),
        r"\midrule",
        *(latex_row(row) for row in interval_rows),
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{0.94\linewidth}",
        r"\footnotesize\textit{Note.} Nested selection-aware intervals are available for "
        + f"{len(nested)}/{int(audit_counts['complete'])} complete events; "
        + f"{int(nested['selection_ci_excludes_zero'].sum())} exclude zero. Their mean "
        + f"width is {format_decimal((nested['selection_ci95_upper'] - nested['selection_ci95_lower']).mean(), 3)} "
        + f"log units versus {format_decimal(fixed_width, 3)} for fixed-weight MetaShift intervals. "
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
                percent(conditional_row["empirical_coverage"], 1),
                format_decimal(conditional_row["mean_interval_width_log"], 3),
                percent(conformal_row["empirical_coverage"], 1),
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
        placement="!ht",
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
    all_method_rows = []
    for method in ALL_METHOD_ORDER:
        row = aggregate.loc[method]
        all_method_rows.append(
            [
                METHOD_LABELS[method],
                metric_display(row["local_effect_mae_log"], 5),
                metric_display(row["average_precision"], 5),
                metric_display(row["macro_f1"], 5),
                metric_display(row["false_positive_rate"], 3),
            ]
        )
    tables[TABLES / "table_all_methods.tex"] = latex_table(
        "all-methods",
        "Complete frozen aggregate comparison of all benchmark methods.",
        "lrrrr",
        ["Method", "Local-effect MAE", "AUPRC", "Macro-F1", "Regional FPR"],
        all_method_rows,
        "All values are aggregates over the held-out stable-regime evaluation "
        "partition. Lower MAE and regional FPR are preferable; higher AUPRC and "
        "macro-F1 are preferable. N/A means that the method supplies no "
        "local-effect magnitude estimate for that perturbation design, not that "
        "the method was omitted.",
        size=r"\scriptsize",
        scale_to_width=True,
        placement="!ht",
    )
    family_metrics = metrics.loc[metrics["perturbation_family"].notna()].set_index(
        ["perturbation_family", "method"]
    )
    family_rows = []
    for family in FAMILY_ORDER:
        for method in ALL_METHOD_ORDER:
            row = family_metrics.loc[(family, method)]
            family_rows.append(
                [
                    FAMILY_LABELS[family].replace("\n", " "),
                    METHOD_LABELS[method],
                    metric_display(row["local_effect_mae_log"], 5),
                    metric_display(row["average_precision"], 5),
                    metric_display(row["macro_f1"], 5),
                    metric_display(row["false_positive_rate"], 3),
                ]
            )
    perturbation_lines = [
        r"{\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\renewcommand{\arraystretch}{1.03}",
        r"\begin{longtable}{@{}p{0.20\linewidth}p{0.20\linewidth}rrrr@{}}",
        r"\caption{Perturbation-family-specific held-out synthetic metrics for all methods.}"
        r"\label{tab:perturbation-metrics}\\",
        r"\toprule",
        latex_row(
            [
                "Paired perturbation family",
                "Method",
                "MAE",
                "AUPRC",
                "Macro-F1",
                "Regional FPR",
            ]
        ),
        r"\midrule",
        r"\endfirsthead",
        r"\multicolumn{6}{l}{\small\itshape Table \ref{tab:perturbation-metrics}, continued}\\",
        r"\toprule",
        latex_row(
            [
                "Paired perturbation family",
                "Method",
                "MAE",
                "AUPRC",
                "Macro-F1",
                "Regional FPR",
            ]
        ),
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\multicolumn{6}{p{0.92\linewidth}}{\footnotesize\textit{Note.} Each family"
        r" aggregates its target-only local perturbation and its matched target-and-donor"
        r" regional variant. Consequently, regional FPR is assessed within the same"
        r" paired family; the rows are not local-only effect estimates. N/A has the"
        r" same meaning as in Table~\ref{tab:all-methods}.}\\",
        r"\endfoot",
        *(latex_row(row) for row in family_rows),
        r"\end{longtable}",
        r"}",
        "",
    ]
    tables[TABLES / "table_perturbation_metrics.tex"] = "\n".join(perturbation_lines)
    tier_rules = json.loads(
        (ROOT / "configs" / "evidence_tier_primary_v1.json").read_text(encoding="utf-8")
    )
    tables[TABLES / "table_evidence_tier_rules.tex"] = latex_table(
        "evidence-tier-rules",
        "Predeclared primary evidence-tier rules and abstention outcomes.",
        r"p{0.39\linewidth}rp{0.40\linewidth}",
        ["Required diagnostic or condition", "Threshold", "Audit outcome"],
        [
            [
                "Complete common-method comparison",
                "required",
                r"Missing input $\Rightarrow$ inconclusive",
            ],
            [
                "Selection-aware nested interval",
                "required",
                r"Unavailable $\Rightarrow$ inconclusive",
            ],
            [
                "Unique stable post-transition time placebos",
                str(tier_rules["minimum_unique_placebos"]),
                r"Fewer dates $\Rightarrow$ inconclusive",
            ],
            [
                "Raw time-placebo probability",
                format_decimal(tier_rules["raw_placebo_p_cutoff"], 2),
                r"Above cutoff $\Rightarrow$ not supported",
            ],
            [
                "BH-adjusted time-placebo q value",
                format_decimal(tier_rules["bh_q_cutoff"], 2),
                r"Unavailable $\Rightarrow$ inconclusive; above cutoff $\Rightarrow$ not supported",
            ],
            [
                "Fixed-weight conditional diagnostic interval",
                "exclude 0",
                r"Otherwise $\Rightarrow$ not supported",
            ],
            [
                "Leave-one-donor-out direction fraction",
                format_decimal(tier_rules["donor_direction_fraction_cutoff"], 2),
                r"Below cutoff $\Rightarrow$ not supported",
            ],
            [
                "All available required conditions",
                "pass",
                "Supported candidate discontinuity",
            ],
        ],
        "The rules synthesize observational diagnostics; they are not a supervised "
        "classifier, instrument-fault label, or physical-causality test. The nested "
        "interval is required for tier assignment but is not claimed to have "
        "synthetic coverage calibration.",
        size=r"\scriptsize",
    )
    tables[TABLES / "table_claim_boundaries.tex"] = latex_table(
        "claim-boundaries",
        "Claim boundaries imposed by the MetaShift-Bench protocol.",
        r"p{0.30\linewidth}p{0.30\linewidth}p{0.30\linewidth}",
        ["The evidence can support", "The evidence does not establish", "Required interpretation"],
        [
            [
                "A reproducible metadata-anchored local residual audit",
                "That a Method Code transition is a physical replacement or fault",
                "Treat the transition as an anchor, not physical ground truth.",
            ],
            [
                "Benchmark-specific synthetic trade-offs among frozen methods",
                "A robust aggregate MetaShift superiority claim",
                "Report the paired intervals and retain the negative result.",
            ],
            [
                "Protocol-defined evidence tiers and abstentions",
                "Instrument bias, true pollution correction, or causal attribution",
                "Use tiers only to prioritize further records-based review.",
            ],
            [
                "Conditional interval behavior on frozen synthetic data",
                "Coverage-calibrated confidence intervals for real-event physical bias",
                "Describe real-event intervals as diagnostic.",
            ],
        ],
        "These boundaries are design constraints, not post hoc caveats.",
        size=r"\scriptsize",
    )

    def interval_text(interval: tuple[float | None, float | None]) -> str:
        lower, upper = interval
        if lower is None or upper is None:
            return "N/A"
        return "[" + format_decimal(lower, 5) + ", " + format_decimal(upper, 5) + "]"

    def display_case_anchor(anchor_id: str) -> str:
        parts = anchor_id.split("-")
        if len(parts) != 7:
            return r"\texttt{" + latex_escape(anchor_id) + "}"
        return (
            r"\texttt{"
            + latex_escape("-".join(parts[:3]))
            + r"}\newline\texttt{"
            + latex_escape("-".join(parts[3:]))
            + "}"
        )

    case_rows = []
    for case in cases:
        group_label = (
            "Inconclusive"
            if case["case_group"].startswith("Inconclusive")
            else case["case_group"]
        )
        if case["audit_status"] == "complete":
            diagnostic = (
                "Effect "
                + metric_display(case["log_effect"], 5)
                + "; fixed "
                + interval_text(case["fixed_interval"])
                + "; nested "
                + interval_text(case["nested_interval"])
            )
            disposition = "Complete"
        else:
            diagnostic = "No counterfactual, effect, or interval is imputed."
            disposition = "Donor insufficient"
        case_rows.append(
            [
                group_label,
                display_case_anchor(str(case["anchor_id"])),
                disposition,
                diagnostic,
            ]
        )
    tables[TABLES / "table_case_studies.tex"] = latex_table(
        "case-studies",
        "Deterministically selected representative audit cases.",
        r"@{}p{0.16\linewidth}p{0.23\linewidth}p{0.17\linewidth}p{0.34\linewidth}@{}",
        [
            "Case",
            "Metadata anchor",
            "Disposition",
            "Saved diagnostic summary",
        ],
        case_rows,
        "Supported and not-supported cases minimize absolute distance to their "
        "within-tier median standardized score, with anchor ID tie-breaking. The "
        "inconclusive case is the lexicographically first donor-insufficient "
        "anchor and deliberately has no counterfactual or interval. Intervals are "
        "diagnostic, not calibrated physical-bias confidence intervals.",
        size=r"\footnotesize",
    )
    anchor_dates = pd.to_datetime(audit["anchor_date"], errors="raise")
    anchors_2023 = audit.loc[anchor_dates.dt.year == 2023].copy()
    pair_counts = (
        anchors_2023.assign(
            old_method_code=anchors_2023["old_method_code"].astype(str),
            new_method_code=anchors_2023["new_method_code"].astype(str),
        )
        .groupby(
            [
                "old_method_code",
                "new_method_code",
                "old_method_name",
                "new_method_name",
            ],
            dropna=False,
        )
        .size()
        .sort_values(ascending=False)
    )
    top_pairs = pair_counts.head(2)
    paired_count = int(top_pairs.sum())
    top_date = (
        anchors_2023.assign(anchor_date=anchor_dates.loc[anchors_2023.index])
        .groupby("anchor_date")
        .size()
        .sort_values(ascending=False)
        .index[0]
    )
    top_date_count = int(
        (
            anchor_dates.loc[anchors_2023.index] == top_date
        ).sum()
    )
    top_state = anchors_2023["target_state"].astype(str).value_counts().index[0]
    top_state_count = int(
        (anchors_2023["target_state"].astype(str) == top_state).sum()
    )
    def abbreviated_reported_name(name: str) -> str:
        model = "T640X" if "T640X" in name else "T640" if "T640" in name else "reported method"
        status = (
            "alignment-enabled"
            if "Network Data Alignment enabled" in name
            else "baseline reported name"
        )
        return f"{model}, {status}"

    concentration_rows = []
    for (old_code, new_code, old_name, new_name), count in top_pairs.items():
        concentration_rows.append(
            [
                latex_escape(old_code),
                latex_escape(new_code),
                latex_escape(
                    abbreviated_reported_name(str(old_name))
                    + " -> "
                    + abbreviated_reported_name(str(new_name))
                ),
                str(int(count)),
            ]
        )
    tables[TABLES / "table_anchor_concentration.tex"] = latex_table(
        "anchor-concentration",
        "Appendix-only temporal concentration of reported 88101 metadata anchors.",
        r"rrp{0.52\linewidth}r",
        ["Old code", "New code", "Abbreviated reported metadata change", "Count"],
        concentration_rows,
        "Of "
        + str(len(anchors_2023))
        + " 2023 anchors, these two pairs account for "
        + str(paired_count)
        + " ("
        + percent(paired_count / len(anchors_2023), 1)
        + "). The largest date is "
        + top_date.date().isoformat()
        + " ("
        + str(top_date_count)
        + "), and the largest state-code subtotal is "
        + str(top_state)
        + " ("
        + str(top_state_count)
        + "). Descriptions abbreviate reported AQS Method Name strings; they do not establish a cause.",
        size=r"\footnotesize",
    )
    return tables


def save_figure(
    figure: plt.Figure, path: Path, title: str, sources: list[str], outputs: list[dict[str, Any]]
) -> None:
    layout_qa = inspect_figure_layout(figure, path.name)
    if not layout_qa["all_checks_passed"]:
        raise RuntimeError(
            "Figure layout QA failed for "
            + path.name
            + ": "
            + json.dumps(layout_qa["violations"], sort_keys=True)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        path,
        format="pdf",
        metadata={
            "Title": title,
            "Creator": "MetaShift-Bench formal-paper asset generator",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(figure)
    outputs.append(
        {
            "path": str(path.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "vector_figure",
            "sources": sources,
            "layout_qa": layout_qa,
        }
    )


# Retained only as a historical implementation reference; write_assets uses
# figure_factory.create_revised_figures for every current report figure.
def _retired_create_case_study_figure(
    cases: list[dict[str, Any]], outputs: list[dict[str, Any]]
) -> None:
    figure, axes = plt.subplots(3, len(cases), figsize=(8.35, 8.8), squeeze=False)
    for column, case in enumerate(cases):
        top, middle, bottom = axes[:, column]
        anchor_date = case["anchor_date"]
        visible_slice = slice(case["visible_start"], case["visible_end"])
        target = case["target"].loc[visible_slice]
        top.plot(target, color="#111827", linewidth=1.2, label="Target")
        top.axvline(anchor_date, color="#DC2626", linestyle="--", linewidth=1)
        top.axvspan(
            anchor_date - pd.Timedelta(days=60),
            anchor_date - pd.Timedelta(days=1),
            color="#DBEAFE",
            alpha=0.42,
            linewidth=0,
        )
        top.axvspan(
            anchor_date,
            anchor_date + pd.Timedelta(days=59),
            color="#FDE68A",
            alpha=0.36,
            linewidth=0,
        )
        top.set_title(
            case["case_group"].replace(": no qualified counterfactual", ""),
            fontsize=9,
            fontweight="bold",
        )
        top.set_ylabel(r"PM$_{2.5}$ ($\mu$g/m$^3$)")
        top.grid(axis="y", alpha=0.22)
        if case["audit_status"] == "complete":
            counterfactual = case["counterfactual"].loc[visible_slice]
            top.plot(
                counterfactual,
                color="#2563EB",
                linewidth=1.1,
                label="Reliability-prior counterfactual",
            )
            residual = case["residual"].loc[visible_slice]
            middle.plot(residual, color="#7C3AED", linewidth=1.1)
            middle.axhline(0, color="#111827", linewidth=0.8)
            middle.axvline(anchor_date, color="#DC2626", linestyle="--", linewidth=1)
            middle.axvspan(
                anchor_date - pd.Timedelta(days=60),
                anchor_date - pd.Timedelta(days=1),
                color="#DBEAFE",
                alpha=0.42,
                linewidth=0,
            )
            middle.axvspan(
                anchor_date,
                anchor_date + pd.Timedelta(days=59),
                color="#FDE68A",
                alpha=0.36,
                linewidth=0,
            )
            middle.set_ylabel("Centered log residual")
            middle.grid(axis="y", alpha=0.22)
            fixed_lower, fixed_upper = case["fixed_interval"]
            nested_lower, nested_upper = case["nested_interval"]
            effect = case["log_effect"]
            bottom.axvline(0, color="#111827", linewidth=0.8)
            if fixed_lower is not None and fixed_upper is not None:
                bottom.plot(
                    [fixed_lower, fixed_upper],
                    [1, 1],
                    color="#2563EB",
                    linewidth=2.2,
                    solid_capstyle="butt",
                )
                bottom.plot(effect, 1, "o", color="#2563EB", markersize=4)
            if nested_lower is not None and nested_upper is not None:
                bottom.plot(
                    [nested_lower, nested_upper],
                    [0, 0],
                    color="#7C3AED",
                    linewidth=2.2,
                    solid_capstyle="butt",
                )
                bottom.plot(effect, 0, "o", color="#7C3AED", markersize=4)
            bottom.set_yticks([0, 1], ["Nested", "Fixed"])
            bottom.set_xlabel("Protocol-defined log effect")
            bottom.grid(axis="x", alpha=0.22)
            placebo_count = case["placebo_count"]
            placebo_p_value = case["placebo_p_value"]
            donor_fraction = case["leave_one_donor_out_fraction"]
            bottom.text(
                0.02,
                0.96,
                "Time placebos: "
                + (
                    "unavailable"
                    if placebo_count is None
                    else f"n={int(placebo_count)}, p={placebo_p_value:.3f}"
                )
                + "\nLOO direction fraction: "
                + (
                    "unavailable"
                    if donor_fraction is None
                    else format_decimal(donor_fraction, 2)
                ),
                transform=bottom.transAxes,
                va="top",
                fontsize=7,
            )
        else:
            middle.axis("off")
            middle.text(
                0.5,
                0.60,
                "No qualified geographic\ncounterfactual is constructed.",
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                transform=middle.transAxes,
            )
            middle.text(
                0.5,
                0.29,
                latex_escape(case["audit_reason"]),
                ha="center",
                va="center",
                fontsize=7,
                wrap=True,
                transform=middle.transAxes,
            )
            bottom.axis("off")
            bottom.text(
                0.5,
                0.57,
                "Abstention is an audit result.\n"
                "No effect estimate or interval is imputed.",
                ha="center",
                va="center",
                fontsize=8.5,
                transform=bottom.transAxes,
            )
        top.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        top.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        middle.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        middle.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        for axis in (top, middle):
            axis.tick_params(axis="x", labelrotation=32, labelsize=7)
            axis.tick_params(axis="y", labelsize=7)
        top.text(
            0.01,
            1.02,
            f"{case['anchor_id']} | {anchor_date.date().isoformat()}",
            transform=top.transAxes,
            fontsize=6.5,
            va="bottom",
        )
        if column == 0:
            top.legend(fontsize=6.7, loc="upper left")
    figure.suptitle(
        "Deterministic display-only representative cases: target/counterfactual, residual, and diagnostics",
        y=0.995,
        fontsize=10,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.975))
    save_figure(
        figure,
        FIGURES / "fig_case_studies.pdf",
        "Deterministic representative MetaShift-Bench cases",
        [
            "artifacts/real_transition_88101_evidence_tiers.csv",
            "artifacts/real_transition_88101_method_results.csv",
            "artifacts/real_transition_88101_event_intervals.csv",
            "paper/latex/configs/case_study_rendering_v1.json",
            "artifacts/data_gate/source_manifest.json",
            "artifacts/data_gate/geographic_controls.csv",
        ],
        outputs,
    )


def _retired_create_figures(
    summary: dict[str, Any],
    data: dict[str, Any],
    cases: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.dpi": 160,
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    x = np.arange(-60, 61)
    baseline = 0.15 * np.sin(x / 11) + 0.03 * np.cos(x / 5)
    local_target = baseline + np.where(x >= 0, 0.72, 0.0)
    local_reference = baseline + 0.03
    regional_target = baseline + np.where(x >= 0, 0.58, 0.0)
    regional_reference = baseline + np.where(x >= 0, 0.61, 0.0)
    figure, axes = plt.subplots(1, 2, figsize=(7.1, 2.65), sharey=True)
    for axis, target, reference, title in (
        (
            axes[0],
            local_target,
            local_reference,
            "Target-local perturbation",
        ),
        (
            axes[1],
            regional_target,
            regional_reference,
            "Matched regional perturbation",
        ),
    ):
        axis.plot(x, target, color="#111827", linewidth=1.6, label="Target")
        axis.plot(x, reference, color="#2563EB", linewidth=1.4, label="Reference")
        axis.axvline(0, color="#DC2626", linestyle="--", linewidth=1)
        axis.set_title(title)
        axis.set_xlabel("Days relative to pseudo-anchor")
        axis.grid(axis="y", alpha=0.22)
    axes[0].set_ylabel("Illustrative normalized signal")
    axes[0].legend(fontsize=7, loc="upper left")
    figure.suptitle(
        "Local-versus-regional discrimination target (schematic, not observed data)",
        y=1.02,
        fontsize=10,
    )
    figure.tight_layout()
    save_figure(
        figure,
        FIGURES / "fig_local_regional_schematic.pdf",
        "Local versus regional perturbation schematic",
        ["configs/benchmark_release_v2.json"],
        outputs,
    )

    figure, axis = plt.subplots(figsize=(7.25, 3.25))
    axis.axis("off")
    nodes = [
        (0.07, 0.76, "Public EPA\nbulk archives", "#E0F2FE"),
        (0.28, 0.76, "Canonical daily\nmonitor series", "#DBEAFE"),
        (0.49, 0.76, "Persistent\nmetadata anchors", "#EDE9FE"),
        (0.70, 0.76, "Distinct physical\ndonor screening", "#DCFCE7"),
        (0.23, 0.26, "Known-truth\nstable synthetic study", "#FEF3C7"),
        (0.52, 0.26, "Complete real-event audit:\ncomparison or failure reason", "#FEE2E2"),
        (0.81, 0.26, "Layered diagnostics\nand abstention tiers", "#E2E8F0"),
    ]
    for xpos, ypos, label, color in nodes:
        axis.text(
            xpos,
            ypos,
            label,
            ha="center",
            va="center",
            fontsize=8,
            bbox={
                "boxstyle": "round,pad=0.45",
                "facecolor": color,
                "edgecolor": "#475569",
                "linewidth": 0.8,
            },
            transform=axis.transAxes,
        )
    arrows = [
        ((0.15, 0.76), (0.20, 0.76)),
        ((0.36, 0.76), (0.41, 0.76)),
        ((0.57, 0.76), (0.62, 0.76)),
        ((0.70, 0.65), (0.52, 0.35)),
        ((0.69, 0.65), (0.29, 0.35)),
        ((0.62, 0.26), (0.71, 0.26)),
    ]
    for start, end in arrows:
        axis.annotate(
            "",
            xy=end,
            xytext=start,
            xycoords="axes fraction",
            arrowprops={"arrowstyle": "->", "color": "#475569", "lw": 1.0},
        )
    axis.text(
        0.5,
        0.02,
        "The arrows describe an evidence workflow; a metadata anchor is not physical-instrument ground truth.",
        ha="center",
        va="bottom",
        fontsize=7.5,
        transform=axis.transAxes,
    )
    save_figure(
        figure,
        FIGURES / "fig_audit_pipeline.pdf",
        "MetaShift-Bench audit pipeline schematic",
        [
            "configs/benchmark_release_v2.json",
            "configs/evidence_tier_primary_v1.json",
            "artifacts/real_transition_88101_event_audit.csv",
        ],
        outputs,
    )

    audit_dates = pd.to_datetime(data["audit"]["anchor_date"])
    donor_candidates = pd.to_numeric(
        data["audit"]["geographic_control_candidates"], errors="raise"
    )
    figure, axes = plt.subplots(1, 2, figsize=(7.1, 2.9))
    years = list(range(2019, 2026))
    year_counts = audit_dates.dt.year.value_counts().reindex(years, fill_value=0)
    bars = axes[0].bar(years, year_counts.values, color="#2563EB")
    axes[0].bar_label(bars, padding=2, fontsize=7)
    axes[0].set_xticks(years, [str(year) for year in years], rotation=30)
    axes[0].set_ylabel("Metadata anchors")
    axes[0].set_title("Anchor dates in the audited snapshot")
    axes[0].grid(axis="y", alpha=0.22)
    donor_bins = pd.cut(
        donor_candidates,
        bins=[-1, 0, 1, 2, 999],
        labels=["0", "1", "2", "3+"],
    ).value_counts().reindex(["0", "1", "2", "3+"], fill_value=0)
    bars = axes[1].bar(
        donor_bins.index.astype(str),
        donor_bins.values,
        color=["#94A3B8", "#CBD5E1", "#F59E0B", "#0F766E"],
    )
    axes[1].bar_label(bars, padding=2, fontsize=7)
    axes[1].set_ylabel("Metadata anchors")
    axes[1].set_title("Prequalified distinct-donor candidates")
    axes[1].set_xlabel("Donors before common-method input checks")
    axes[1].grid(axis="y", alpha=0.22)
    figure.tight_layout()
    save_figure(
        figure,
        FIGURES / "fig_data_construction.pdf",
        "Metadata anchor dates and donor availability",
        ["artifacts/real_transition_88101_event_audit.csv"],
        outputs,
    )

    split = load_json("artifacts/stable_synthetic_case_split_audit.json")
    figure, axis = plt.subplots(figsize=(7.1, 2.75))
    axis.axis("off")
    split_boxes = [
        (
            0.25,
            "Calibration\n"
            f"{split['calibration_physical_sites']} target sites\n"
            f"{split['calibration_input_physical_sites']} complete input sites",
            "#DBEAFE",
        ),
        (
            0.75,
            "Held-out evaluation\n"
            f"{split['evaluation_physical_sites']} target sites\n"
            f"{split['evaluation_input_physical_sites']} complete input sites",
            "#EDE9FE",
        ),
    ]
    for xpos, label, color in split_boxes:
        axis.text(
            xpos,
            0.55,
            label,
            ha="center",
            va="center",
            fontsize=10,
            bbox={
                "boxstyle": "round,pad=0.7",
                "facecolor": color,
                "edgecolor": "#475569",
                "linewidth": 1.0,
            },
            transform=axis.transAxes,
        )
    axis.plot(
        [0.47, 0.53],
        [0.55, 0.55],
        transform=axis.transAxes,
        color="#DC2626",
        linewidth=2,
        linestyle="--",
    )
    axis.text(
        0.50,
        0.34,
        f"{split['all_input_physical_sites_shared_across_splits']} shared physical input sites",
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color="#991B1B",
        transform=axis.transAxes,
    )
    axis.text(
        0.50,
        0.10,
        "Whole connected components of the target-plus-donor footprint graph were assigned before evaluation.",
        ha="center",
        va="center",
        fontsize=7.5,
        transform=axis.transAxes,
    )
    save_figure(
        figure,
        FIGURES / "fig_split_integrity.pdf",
        "Complete input-footprint split integrity",
        [
            "artifacts/stable_synthetic_case_manifest.json",
            "artifacts/stable_synthetic_case_split_audit.json",
        ],
        outputs,
    )

    family_metrics = data["metrics"].loc[
        data["metrics"]["perturbation_family"].notna()
    ].set_index(["method", "perturbation_family"])
    metric_specs = (
        ("local_effect_mae_log", "Local-effect MAE", "viridis_r", 5),
        ("average_precision", "AUPRC", "viridis", 3),
        ("macro_f1", "Macro-F1", "viridis", 3),
        ("false_positive_rate", "Regional FPR", "magma_r", 3),
    )
    figure, axes = plt.subplots(2, 2, figsize=(8.0, 7.5))
    for axis, (column, title, cmap, places) in zip(
        axes.flat, metric_specs, strict=True
    ):
        matrix = np.array(
            [
                [
                    family_metrics.loc[(method, family), column]
                    for family in FAMILY_ORDER
                ]
                for method in ALL_METHOD_ORDER
            ],
            dtype=float,
        )
        masked = np.ma.masked_invalid(matrix)
        image = axis.imshow(masked, aspect="auto", cmap=cmap)
        axis.set_title(title)
        axis.set_xticks(
            range(len(FAMILY_ORDER)),
            [FAMILY_LABELS[family] for family in FAMILY_ORDER],
            fontsize=7,
        )
        axis.set_yticks(
            range(len(ALL_METHOD_ORDER)),
            [METHOD_LABELS[method] for method in ALL_METHOD_ORDER],
            fontsize=7,
        )
        for row_index in range(matrix.shape[0]):
            for column_index in range(matrix.shape[1]):
                value = matrix[row_index, column_index]
                label = "N/A" if np.isnan(value) else format_decimal(value, places)
                text_color = "#111827" if np.isnan(value) or value < 0.55 else "white"
                axis.text(
                    column_index,
                    row_index,
                    label,
                    ha="center",
                    va="center",
                    fontsize=5.8,
                    color=text_color,
                )
        colorbar = figure.colorbar(image, ax=axis, fraction=0.045, pad=0.03)
        colorbar.ax.tick_params(labelsize=6)
    figure.suptitle(
        "All frozen methods across paired local/regional perturbation families",
        y=0.995,
        fontsize=10,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.978))
    save_figure(
        figure,
        FIGURES / "fig_perturbation_metrics.pdf",
        "Perturbation-family synthetic metrics for all methods",
        ["artifacts/stable_synthetic_stable_full_v2_metrics.csv"],
        outputs,
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
    _retired_create_case_study_figure(cases, outputs)


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
            ROOT / "artifacts/real_transition_88101_evidence_tiers.csv",
            dtype={
                "anchor_id": "string",
                "target_state": "string",
                "target_county": "string",
                "target_site": "string",
                "target_poc": "string",
            },
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
        "external_validation": pd.read_csv(
            ROOT / "artifacts/external_validation_evidence.csv"
        ),
        "secondary_audit": pd.read_csv(
            ROOT / "artifacts/real_transition_88502_event_audit.csv"
        ),
        "stable_manifest": load_json("artifacts/stable_synthetic_case_manifest.json"),
        "split_audit": load_json(
            "artifacts/stable_synthetic_case_split_audit.json"
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
    case_config = verify_case_rendering_inputs()
    synthetic_config = verify_synthetic_example_inputs()
    external_config = verify_external_evidence_inputs()
    window_config = verify_window_protocol_inputs()
    data = load_data()
    series = load_case_series(case_config)
    cases = build_case_records(data, case_config, series)
    synthetic_example = build_synthetic_motivating_example(
        synthetic_config, series
    )
    GENERATED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    legacy_case_figure = FIGURES / "fig_case_studies.pdf"
    if legacy_case_figure.is_file():
        legacy_case_figure.unlink()
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
        json.dumps(
            build_claim_value_manifest(
                summary,
                data,
                cases,
                case_config,
                window_config,
                external_config,
            ),
            indent=2,
        )
        + "\n",
    )
    outputs.append(
        {
            "path": str(claim_values_path.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "claim_value_manifest",
            "sources": [
                "configs/current_evidence_summary_v2.json",
                "artifacts/stable_synthetic_case_manifest.json",
                "artifacts/real_transition_88101_evidence_tiers.csv",
                "artifacts/real_transition_88101_method_results.csv",
                "paper/latex/configs/case_study_rendering_v2.json",
                "paper/latex/configs/window_protocol_audit_v1.json",
                "paper/latex/configs/external_evidence_rendering_v1.json",
            ],
        }
    )
    case_manifest_path = GENERATED / "case_study_manifest.json"
    write_text(
        case_manifest_path,
        json.dumps(case_study_manifest(summary, case_config, cases), indent=2) + "\n",
    )
    outputs.append(
        {
            "path": str(case_manifest_path.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "case_study_manifest",
            "sources": [
                "artifacts/real_transition_88101_evidence_tiers.csv",
                "artifacts/real_transition_88101_method_results.csv",
                "paper/latex/configs/case_study_rendering_v2.json",
                "artifacts/data_gate/source_manifest.json",
                "artifacts/data_gate/geographic_controls.csv",
            ],
        }
    )
    synthetic_manifest_path = GENERATED / "synthetic_motivating_example_manifest.json"
    write_text(
        synthetic_manifest_path,
        json.dumps(
            {
                "schema_version": 1,
                "purpose": "Display-only stable-window synthetic example.",
                "frozen_evidence": summary["frozen_evidence"],
                "result_label": summary["result_label"],
                "configuration": {
                    "path": relative_to_root(SYNTHETIC_EXAMPLE_CONFIG_PATH),
                    "sha256": sha256(SYNTHETIC_EXAMPLE_CONFIG_PATH),
                },
                "case_id": synthetic_example["case_id"],
                "anchor_date": synthetic_example["anchor_date"].date().isoformat(),
                "additive_magnitude": synthetic_example["magnitude"],
                "weights": synthetic_example["weights"],
            },
            indent=2,
        )
        + "\n",
    )
    outputs.append(
        {
            "path": str(synthetic_manifest_path.relative_to(LATEX_ROOT)).replace(
                "\\", "/"
            ),
            "kind": "synthetic_example_manifest",
            "sources": [
                "paper/latex/configs/synthetic_motivating_example_v1.json",
                "artifacts/stable_synthetic_cases.csv",
                "artifacts/stable_synthetic_case_donors.csv",
                "paper/latex/configs/case_study_rendering_v2.json",
            ],
        }
    )
    for path, content in create_tables(summary, data, cases).items():
        write_text(path, content)
        outputs.append(
            {
                "path": str(path.relative_to(LATEX_ROOT)).replace("\\", "/"),
                "kind": "latex_table",
                "sources": ["configs/current_evidence_summary_v2.json"],
            }
        )
    create_revised_figures(
        summary,
        data,
        cases,
        synthetic_example,
        window_config,
        external_config,
        FIGURES,
        save_figure,
        format_decimal,
        outputs,
    )
    figure_layouts = [
        output["layout_qa"]
        for output in outputs
        if output.get("kind") == "vector_figure"
        and isinstance(output.get("layout_qa"), dict)
    ]
    if len(figure_layouts) != 17:
        raise RuntimeError(
            "Expected 17 current formal-report figures, found "
            f"{len(figure_layouts)} layout records."
        )
    write_text(
        LAYOUT_QA_PATH,
        json.dumps(
            {
                "schema_version": 1,
                "frozen_evidence": summary["frozen_evidence"],
                "result_label": summary["result_label"],
                "required_figure_count": 17,
                "figures": figure_layouts,
                "all_checks_passed": all(
                    bool(record["all_checks_passed"]) for record in figure_layouts
                ),
            },
            indent=2,
        )
        + "\n",
    )
    outputs.append(
        {
            "path": str(LAYOUT_QA_PATH.relative_to(LATEX_ROOT)).replace("\\", "/"),
            "kind": "figure_layout_qa",
            "sources": ["configs/current_evidence_summary_v2.json"],
        }
    )
    add_output_hashes(outputs)
    manifest = {
        "schema_version": 4,
        "generator": "paper/latex/scripts/generate_paper_assets.py",
        "frozen_evidence": summary["frozen_evidence"],
        "result_label": summary["result_label"],
        "input_summary_sha256": sha256(SUMMARY_PATH),
        "input_artifact_sources": [
            {"path": path, "sha256": source_hashes(summary)[path]}
            for path in REQUIRED_ARTIFACTS
        ],
        "presentation_input_sources": presentation_input_sources(
            case_config,
            synthetic_config,
            external_config,
            window_config,
        ),
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
    for record in manifest.get("presentation_input_sources", []):
        if not isinstance(record, dict):
            errors.append("presentation_input_sources:invalid_record")
            continue
        relative_path = record.get("path")
        expected_hash = record.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            errors.append("presentation_input_sources:missing_path_or_hash")
            continue
        path = safe_root_path(relative_path)
        if not path.is_file():
            errors.append(f"{relative_path}:missing_presentation_input")
        elif sha256(path) != expected_hash:
            errors.append(f"{relative_path}:presentation_input_sha256_mismatch")
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
