"""Validate the formal report's evidence-bound figure set and its logical invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
FIGURES = LATEX_ROOT / "generated" / "figures"
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
WINDOW_CONFIG_PATH = LATEX_ROOT / "configs" / "window_protocol_audit_v1.json"
EXTERNAL_CONFIG_PATH = LATEX_ROOT / "configs" / "external_evidence_rendering_v1.json"
CASE_MANIFEST_PATH = LATEX_ROOT / "generated" / "case_study_manifest.json"
LAYOUT_QA_PATH = LATEX_ROOT / "generated" / "figure_layout_qa.json"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "figure_qa_validation.json"

REQUIRED_FIGURES = (
    "fig_stable_synthetic_example.pdf",
    "fig_donor_construction.pdf",
    "fig_window_protocol.pdf",
    "fig_audit_pipeline.pdf",
    "fig_split_integrity.pdf",
    "fig_synthetic_metrics.pdf",
    "fig_perturbation_metrics.pdf",
    "fig_cross_site_scope_metrics.pdf",
    "fig_paired_bootstrap.pdf",
    "fig_event_accounting.pdf",
    "fig_placebos.pdf",
    "fig_interval_coverage.pdf",
    "fig_screening_sensitivity.pdf",
    "fig_external_evidence.pdf",
    "fig_case_studies_complete.pdf",
    "fig_case_studies_abstention.pdf",
    "fig_applicability_map.pdf",
    "fig_anchor_concentration.pdf",
)

STRICT_NODE_GEOMETRY_FIGURES = {
    "fig_donor_construction.pdf",
    "fig_audit_pipeline.pdf",
    "fig_applicability_map.pdf",
}

REQUIRED_FIGURE_SOURCES = {
    "fig_stable_synthetic_example.pdf": {
        "paper/latex/configs/synthetic_motivating_example_v1.json",
        "artifacts/stable_synthetic_cases.csv",
        "artifacts/stable_synthetic_case_donors.csv",
    },
    "fig_donor_construction.pdf": {
        "configs/benchmark_release_v2.json",
        "artifacts/real_transition_88101_event_audit.csv",
    },
    "fig_window_protocol.pdf": {
        "paper/latex/configs/window_protocol_audit_v1.json",
        "metashift/counterfactual.py",
    },
    "fig_audit_pipeline.pdf": {
        "configs/benchmark_release_v2.json",
        "configs/evidence_tier_primary_v1.json",
        "artifacts/real_transition_88101_event_audit.csv",
        "artifacts/stable_synthetic_case_split_audit.json",
    },
    "fig_split_integrity.pdf": {
        "artifacts/stable_synthetic_case_manifest.json",
        "artifacts/stable_synthetic_case_split_audit.json",
    },
    "fig_synthetic_metrics.pdf": {
        "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
    },
    "fig_perturbation_metrics.pdf": {
        "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
    },
    "fig_cross_site_scope_metrics.pdf": {
        "artifacts/stable_synthetic_stable_full_v2_metrics.csv",
    },
    "fig_paired_bootstrap.pdf": {
        "artifacts/stable_synthetic_stable_full_v2_bootstrap.csv",
    },
    "fig_event_accounting.pdf": {
        "artifacts/real_transition_88101_event_audit.csv",
        "artifacts/real_transition_88101_evidence_tiers.csv",
    },
    "fig_placebos.pdf": {
        "artifacts/real_transition_88101_event_audit.csv",
        "artifacts/time_placebo_summary.csv",
    },
    "fig_interval_coverage.pdf": {
        "artifacts/synthetic_interval_coverage_v2_summary.csv",
    },
    "fig_screening_sensitivity.pdf": {
        "configs/evidence_tier_sensitivity_v2.json",
        "artifacts/screening_sensitivity_summary.csv",
        "artifacts/evidence_tier_sensitivity_v2_summary.csv",
    },
    "fig_external_evidence.pdf": {
        "paper/latex/configs/external_evidence_rendering_v1.json",
        "artifacts/external_validation_evidence.csv",
        "artifacts/hourly_poc_validation_summary.csv",
        "artifacts/external_document_review_summary.json",
        "artifacts/real_transition_88502_event_audit.csv",
    },
    "fig_case_studies_complete.pdf": {
        "paper/latex/configs/case_study_rendering_v2.json",
        "artifacts/real_transition_88101_method_results.csv",
        "artifacts/time_placebo_summary.csv",
    },
    "fig_case_studies_abstention.pdf": {
        "paper/latex/configs/case_study_rendering_v2.json",
        "artifacts/real_transition_88101_method_results.csv",
        "artifacts/time_placebo_summary.csv",
    },
    "fig_applicability_map.pdf": {
        "artifacts/real_transition_88101_event_audit.csv",
        "artifacts/real_transition_88101_evidence_tier_summary.json",
        "artifacts/real_transition_88101_evidence_tiers.csv",
    },
    "fig_anchor_concentration.pdf": {
        "artifacts/real_transition_88101_event_audit.csv",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate formal-report figures.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output report path, relative to the LaTeX project by default.",
    )
    return parser.parse_args()


def resolve_from_latex(path: Path) -> Path:
    return path if path.is_absolute() else LATEX_ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decoded_pdf_stream_content(content: bytes) -> bytes:
    """Inspect decoded content streams rather than random compressed byte runs."""

    decoded = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", content, re.DOTALL):
        try:
            decoded.append(zlib.decompress(stream))
        except zlib.error:
            continue
    return b"\n".join(decoded).lower()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def check(name: str, violations: list[dict[str, Any]]) -> dict[str, Any]:
    return {"name": name, "passed": not violations, "violations": violations}


def window_contract_violations(config: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    windows = config.get("windows")
    if not isinstance(windows, dict):
        return [{"issue": "missing_windows"}]
    expected = {
        "calibration": (-180, -15, 166),
        "pre": (-60, -1, 60),
        "post": (0, 59, 60),
    }
    for name, (start, end, count) in expected.items():
        record = windows.get(name)
        if not isinstance(record, dict):
            violations.append({"issue": "missing_window", "window": name})
            continue
        actual = (
            record.get("start_offset_days"),
            record.get("end_offset_days"),
            record.get("inclusive_calendar_dates"),
        )
        if actual != (start, end, count):
            violations.append(
                {
                    "issue": "incorrect_window_bounds",
                    "window": name,
                    "expected": [start, end, count],
                    "actual": list(actual),
                }
            )
    if windows.get("calibration_pre_overlap_calendar_dates") != 46:
        violations.append(
            {
                "issue": "incorrect_calibration_pre_overlap",
                "expected": 46,
                "actual": windows.get("calibration_pre_overlap_calendar_dates"),
            }
        )
    return violations


def source_hashes(manifest: dict[str, Any]) -> dict[str, str]:
    records = (
        manifest.get("input_artifact_sources", []),
        manifest.get("presentation_input_sources", []),
    )
    return {
        str(record["path"]): str(record["sha256"])
        for group in records
        for record in group
        if isinstance(record, dict)
        and isinstance(record.get("path"), str)
        and isinstance(record.get("sha256"), str)
    }


def expected_status_counts(summary: dict[str, Any]) -> dict[str, int]:
    real = summary["real_event_audit"]
    return {
        "complete": int(real["complete_comparisons"]),
        "insufficient_geographic_donors": int(real["insufficient_geographic_donors"]),
        "estimator_input_failure": int(real["estimator_input_failure"]),
    }


def figure_partition_counts(
    audit: pd.DataFrame,
    tiers: pd.DataFrame,
    placebo: pd.DataFrame,
    split: dict[str, Any],
) -> dict[str, dict[str, int]]:
    """Derive every redesigned count partition directly from frozen inputs."""

    statuses = Counter(audit["audit_status"])
    tier_counts = Counter(tiers["evidence_tier"])
    complete_tiers = Counter(
        tiers.loc[tiers["audit_status"] == "complete", "evidence_tier"]
    )
    donor_counts = pd.to_numeric(audit["geographic_control_candidates"], errors="raise")
    complete_placebo = placebo.loc[
        placebo["status"].astype(str).str.startswith("complete_")
    ].copy()
    placebo_counts = pd.to_numeric(
        complete_placebo["placebo_count"], errors="raise"
    )
    at_least_50 = int((placebo_counts >= 50).sum())
    at_least_100 = int((placebo_counts >= 100).sum())
    complete = int(statuses["complete"])
    donor_insufficient = int(statuses["insufficient_geographic_donors"])
    input_failure = int(statuses["estimator_input_failure"])
    supported = int(complete_tiers["supported_candidate_discontinuity"])
    not_supported = int(complete_tiers["not_supported_by_available_evidence"])
    complete_inconclusive = int(
        complete_tiers["inconclusive_insufficient_evidence"]
    )
    return {
        "donor_construction": {
            "total_anchors": int(len(audit)),
            "zero_sites": int((donor_counts == 0).sum()),
            "one_site": int((donor_counts == 1).sum()),
            "two_sites": int((donor_counts == 2).sum()),
            "at_least_three_sites": int((donor_counts >= 3).sum()),
            "at_least_one_site": int((donor_counts >= 1).sum()),
        },
        "workflow": {
            "total_anchors": int(len(audit)),
            "complete_comparisons": complete,
            "availability_abstentions": donor_insufficient + input_failure,
            "calibration_targets": int(split["calibration_physical_sites"]),
            "evaluation_targets": int(split["evaluation_physical_sites"]),
        },
        "event_accounting": {
            "total_anchors": int(len(audit)),
            "donor_insufficient": donor_insufficient,
            "input_failure": input_failure,
            "complete_comparisons": complete,
            "supported_candidates": supported,
            "not_supported": not_supported,
            "complete_inconclusive": complete_inconclusive,
            "overall_inconclusive": donor_insufficient
            + input_failure
            + complete_inconclusive,
        },
        "placebos": {
            "complete_comparisons": complete,
            "all_placebo_rows": int(len(placebo)),
            "eligible_placebo_rows": int(len(complete_placebo)),
            "fewer_than_50": complete - at_least_50,
            "from_50_to_99": at_least_50 - at_least_100,
            "at_least_50": at_least_50,
            "at_least_100": at_least_100,
            "finite_probability_rows": int(
                pd.to_numeric(
                    complete_placebo.loc[
                        placebo_counts >= 50, "placebo_p_value"
                    ],
                    errors="coerce",
                )
                .notna()
                .sum()
            ),
        },
        "applicability_matrix": {
            "total_anchors": int(len(audit)),
            "donor_insufficient": donor_insufficient,
            "input_failure": input_failure,
            "complete_comparisons": complete,
            "supported_candidates": supported,
            "not_supported": not_supported,
            "complete_inconclusive": complete_inconclusive,
        },
        "all_evidence_tiers": {
            key: int(value) for key, value in tier_counts.items()
        },
    }


def figure_partition_violations(
    summary: dict[str, Any], counts: dict[str, dict[str, int]]
) -> list[dict[str, Any]]:
    """Check count semantics independently of figure rendering."""

    violations: list[dict[str, Any]] = []
    statuses = expected_status_counts(summary)
    evidence_tiers = {
        key: int(value) for key, value in summary["evidence_tiers"].items()
    }
    donor = counts["donor_construction"]
    workflow = counts["workflow"]
    accounting = counts["event_accounting"]
    placebos = counts["placebos"]
    applicability = counts["applicability_matrix"]

    if (
        donor["zero_sites"]
        + donor["one_site"]
        + donor["two_sites"]
        + donor["at_least_three_sites"]
        != donor["total_anchors"]
    ):
        violations.append({"issue": "donor_availability_partition_does_not_reconcile"})
    if donor["at_least_one_site"] != int(
        summary["data_gate"]["anchors_with_one_distinct_physical_donor"]
    ):
        violations.append(
            {
                "issue": "one_or_more_donor_sites_mismatch",
                "actual": donor["at_least_one_site"],
            }
        )
    if donor["at_least_three_sites"] != int(
        summary["data_gate"]["anchors_with_three_distinct_physical_donors"]
    ):
        violations.append(
            {
                "issue": "three_or_more_donor_sites_mismatch",
                "actual": donor["at_least_three_sites"],
            }
        )
    if donor["total_anchors"] != int(summary["real_event_audit"]["total_anchors"]):
        violations.append(
            {
                "issue": "donor_availability_total_mismatch",
                "actual": donor["total_anchors"],
            }
        )

    if workflow["complete_comparisons"] + workflow["availability_abstentions"] != workflow[
        "total_anchors"
    ]:
        violations.append({"issue": "workflow_availability_partition_does_not_reconcile"})
    if workflow["complete_comparisons"] != statuses["complete"]:
        violations.append(
            {
                "issue": "workflow_complete_comparison_mismatch",
                "actual": workflow["complete_comparisons"],
            }
        )
    if workflow["calibration_targets"] != int(
        summary["synthetic_benchmark"]["calibration_case_count"]
    ) or workflow["evaluation_targets"] != int(
        summary["synthetic_benchmark"]["evaluation_case_count"]
    ):
        violations.append(
            {
                "issue": "workflow_synthetic_split_mismatch",
                "actual": {
                    "calibration_targets": workflow["calibration_targets"],
                    "evaluation_targets": workflow["evaluation_targets"],
                },
            }
        )

    if (
        accounting["donor_insufficient"]
        + accounting["input_failure"]
        + accounting["complete_comparisons"]
        != accounting["total_anchors"]
    ):
        violations.append({"issue": "event_availability_partition_does_not_reconcile"})
    if (
        accounting["supported_candidates"]
        + accounting["not_supported"]
        + accounting["complete_inconclusive"]
        != accounting["complete_comparisons"]
    ):
        violations.append({"issue": "event_tier_partition_does_not_reconcile"})
    if (
        accounting["supported_candidates"]
        + accounting["not_supported"]
        + accounting["overall_inconclusive"]
        != accounting["total_anchors"]
    ):
        violations.append({"issue": "event_overall_partition_does_not_reconcile"})
    if accounting["supported_candidates"] != evidence_tiers[
        "supported_candidate_discontinuity"
    ] or accounting["not_supported"] != evidence_tiers[
        "not_supported_by_available_evidence"
    ] or accounting["overall_inconclusive"] != evidence_tiers[
        "inconclusive_insufficient_evidence"
    ]:
        violations.append(
            {
                "issue": "event_accounting_evidence_tier_summary_mismatch",
                "actual": {
                    "supported": accounting["supported_candidates"],
                    "not_supported": accounting["not_supported"],
                    "overall_inconclusive": accounting["overall_inconclusive"],
                },
            }
        )

    if (
        placebos["fewer_than_50"]
        + placebos["from_50_to_99"]
        + placebos["at_least_100"]
        != placebos["complete_comparisons"]
    ):
        violations.append({"issue": "placebo_availability_partition_does_not_reconcile"})
    if placebos["all_placebo_rows"] != placebos["complete_comparisons"]:
        violations.append(
            {
                "issue": "placebo_rows_do_not_cover_complete_comparisons",
                "actual": placebos["all_placebo_rows"],
            }
        )
    if placebos["eligible_placebo_rows"] != placebos["at_least_50"]:
        violations.append(
            {
                "issue": "eligible_placebo_rows_mismatch",
                "actual": placebos["eligible_placebo_rows"],
            }
        )
    if placebos["at_least_50"] != int(
        summary["placebos"]["complete_with_at_least_50"]
    ) or placebos["at_least_100"] != int(
        summary["placebos"]["complete_with_100"]
    ):
        violations.append(
            {
                "issue": "placebo_threshold_summary_mismatch",
                "actual": {
                    "at_least_50": placebos["at_least_50"],
                    "at_least_100": placebos["at_least_100"],
                },
            }
        )
    if placebos["finite_probability_rows"] != placebos["at_least_50"]:
        violations.append(
            {
                "issue": "placebo_histogram_has_missing_eligible_probabilities",
                "actual": placebos["finite_probability_rows"],
            }
        )

    if (
        applicability["donor_insufficient"]
        + applicability["input_failure"]
        + applicability["complete_comparisons"]
        != applicability["total_anchors"]
    ):
        violations.append(
            {"issue": "applicability_matrix_availability_rows_do_not_reconcile"}
        )
    if (
        applicability["supported_candidates"]
        + applicability["not_supported"]
        + applicability["complete_inconclusive"]
        != applicability["complete_comparisons"]
    ):
        violations.append(
            {"issue": "applicability_matrix_tier_row_does_not_reconcile"}
        )
    return violations


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    summary = load_json(SUMMARY_PATH)
    manifest = load_json(ASSET_MANIFEST_PATH)
    output_records = {
        str(record["path"]): record
        for record in manifest.get("outputs", [])
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    frozen_hashes = source_hashes(manifest)
    checks: list[dict[str, Any]] = []

    manifest_violations: list[dict[str, Any]] = []
    if manifest.get("frozen_evidence") != summary.get("frozen_evidence"):
        manifest_violations.append({"issue": "frozen_evidence_mismatch"})
    if manifest.get("result_label") != "stable_full_v2":
        manifest_violations.append(
            {"issue": "result_label_mismatch", "actual": manifest.get("result_label")}
        )
    checks.append(check("frozen_figure_manifest_identity", manifest_violations))

    figure_violations: list[dict[str, Any]] = []
    for name in REQUIRED_FIGURES:
        relative = f"generated/figures/{name}"
        record = output_records.get(relative)
        path = FIGURES / name
        if record is None:
            figure_violations.append(
                {"issue": "missing_manifest_record", "figure": name}
            )
            continue
        if not path.is_file() or path.stat().st_size < 10_000:
            figure_violations.append(
                {"issue": "missing_or_small_figure", "figure": name}
            )
            continue
        content = path.read_bytes()
        if not content.startswith(b"%PDF-"):
            figure_violations.append({"issue": "not_pdf", "figure": name})
        if re.search(rb"/Subtype\s*/Image\b", content):
            figure_violations.append({"issue": "embedded_raster", "figure": name})
        decoded_content = decoded_pdf_stream_content(content)
        if any(
            token in decoded_content for token in (b"todo", b"tbd", b"placeholder")
        ):
            figure_violations.append({"issue": "placeholder_text", "figure": name})
        if sha256(path) != record.get("sha256"):
            figure_violations.append({"issue": "manifest_hash_mismatch", "figure": name})
        actual_sources = set(record.get("sources", []))
        missing_sources = sorted(REQUIRED_FIGURE_SOURCES[name] - actual_sources)
        if missing_sources:
            figure_violations.append(
                {
                    "issue": "missing_required_figure_sources",
                    "figure": name,
                    "sources": missing_sources,
                }
            )
        for source in actual_sources:
            source_path = ROOT / source
            expected_hash = frozen_hashes.get(source)
            if not source_path.is_file():
                figure_violations.append(
                    {"issue": "missing_figure_source", "figure": name, "source": source}
                )
            elif expected_hash is None:
                figure_violations.append(
                    {
                        "issue": "unhashed_figure_source",
                        "figure": name,
                        "source": source,
                    }
                )
            elif sha256(source_path) != expected_hash:
                figure_violations.append(
                    {
                        "issue": "changed_figure_source",
                        "figure": name,
                        "source": source,
                    }
                )
    checks.append(check("vector_figures_and_hashed_sources", figure_violations))

    layout_violations: list[dict[str, Any]] = []
    layout_qa = load_json(LAYOUT_QA_PATH)
    if layout_qa.get("frozen_evidence") != summary.get("frozen_evidence"):
        layout_violations.append({"issue": "layout_qa_frozen_evidence_mismatch"})
    if layout_qa.get("result_label") != "stable_full_v2":
        layout_violations.append({"issue": "layout_qa_result_label_mismatch"})
    layout_records = {
        str(record.get("figure")): record
        for record in layout_qa.get("figures", [])
        if isinstance(record, dict) and isinstance(record.get("figure"), str)
    }
    if (
        layout_qa.get("schema_version") != 1
        or layout_qa.get("required_figure_count") != len(REQUIRED_FIGURES)
        or layout_qa.get("all_checks_passed") is not True
    ):
        layout_violations.append({"issue": "invalid_figure_layout_qa_header"})
    for name in REQUIRED_FIGURES:
        layout_record = layout_records.get(name)
        manifest_layout = output_records.get(
            f"generated/figures/{name}", {}
        ).get("layout_qa")
        if not isinstance(layout_record, dict):
            layout_violations.append({"issue": "missing_layout_record", "figure": name})
            continue
        if layout_record != manifest_layout:
            layout_violations.append(
                {"issue": "layout_record_does_not_match_asset_manifest", "figure": name}
            )
        required_flags = (
            "all_checks_passed",
            "text_inside_nodes_passed",
            "annotation_overlap_passed",
            "canvas_boundary_passed",
            "legend_data_overlap_passed",
            "typography_passed",
            "grayscale_passed",
        )
        failed_flags = [
            flag for flag in required_flags if layout_record.get(flag) is not True
        ]
        if failed_flags:
            layout_violations.append(
                {
                    "issue": "layout_check_failed",
                    "figure": name,
                    "checks": failed_flags,
                }
            )
        if name in STRICT_NODE_GEOMETRY_FIGURES and (
            layout_record.get("strict_node_geometry_checked") is not True
            or layout_record.get("strict_node_geometry_passed") is not True
        ):
            layout_violations.append(
                {
                    "issue": "strict_node_geometry_check_failed",
                    "figure": name,
                }
            )
        if float(layout_record.get("final_print_width_pt", 0.0)) < 450.0:
            layout_violations.append(
                {"issue": "figure_print_width_too_small", "figure": name}
            )
        if float(layout_record.get("smallest_font_size_print_pt", 0.0)) < 8.5:
            layout_violations.append(
                {"issue": "figure_text_below_8_5pt", "figure": name}
            )
        visual_inspection = layout_record.get("visual_inspection")
        if not isinstance(visual_inspection, dict) or visual_inspection.get(
            "source_rendered_geometry"
        ) != "passed":
            layout_violations.append(
                {"issue": "source_rendered_geometry_not_passed", "figure": name}
            )
    checks.append(
        check(
            "measured_typography_geometry_and_grayscale",
            layout_violations,
        )
    )

    accounting_violations: list[dict[str, Any]] = []
    audit = pd.read_csv(ROOT / "artifacts" / "real_transition_88101_event_audit.csv")
    tiers = pd.read_csv(
        ROOT / "artifacts" / "real_transition_88101_evidence_tiers.csv"
    )
    split = load_json(ROOT / "artifacts" / "stable_synthetic_case_split_audit.json")
    placebo = pd.read_csv(ROOT / "artifacts" / "time_placebo_summary.csv")
    statuses = Counter(audit["audit_status"])
    expected_status = expected_status_counts(summary)
    if statuses != Counter(expected_status):
        accounting_violations.append(
            {
                "issue": "audit_status_counts_mismatch",
                "expected": expected_status,
                "actual": dict(statuses),
            }
        )
    if len(audit) != int(summary["real_event_audit"]["total_anchors"]):
        accounting_violations.append(
            {"issue": "total_anchor_count_mismatch", "actual": len(audit)}
        )
    tier_counts = Counter(tiers["evidence_tier"])
    expected_tiers = {
        key: int(value) for key, value in summary["evidence_tiers"].items()
    }
    if tier_counts != Counter(expected_tiers):
        accounting_violations.append(
            {
                "issue": "tier_counts_mismatch",
                "expected": expected_tiers,
                "actual": dict(tier_counts),
            }
        )
    complete_tiers = Counter(
        tiers.loc[tiers["audit_status"] == "complete", "evidence_tier"]
    )
    if sum(complete_tiers.values()) != expected_status["complete"]:
        accounting_violations.append(
            {
                "issue": "complete_tiers_do_not_reconcile",
                "actual": dict(complete_tiers),
            }
        )
    checks.append(check("anchor_and_tier_accounting", accounting_violations))

    partition_counts = figure_partition_counts(audit, tiers, placebo, split)
    checks.append(
        check(
            "redesigned_figure_partition_semantics",
            figure_partition_violations(summary, partition_counts),
        )
    )

    split_violations: list[dict[str, Any]] = []
    required_split = {
        "calibration_cases": 66,
        "evaluation_cases": 80,
        "calibration_physical_sites": 66,
        "evaluation_physical_sites": 80,
        "duplicate_physical_sites_anywhere": 0,
        "physical_sites_shared_across_splits": 0,
        "all_input_physical_sites_shared_across_splits": 0,
        "target_donor_cross_split_overlaps": 0,
        "duplicate_physical_donors_within_case": 0,
        "all_input_physical_sites_disjoint": True,
    }
    for key, expected in required_split.items():
        if split.get(key) != expected:
            split_violations.append(
                {"issue": "split_invariant_mismatch", "key": key, "actual": split.get(key)}
            )
    checks.append(check("complete_input_footprint_isolation", split_violations))

    placebo_violations: list[dict[str, Any]] = []
    complete_placebo = placebo.loc[
        placebo["status"].astype(str).str.startswith("complete_")
    ]
    at_50 = int((complete_placebo["placebo_count"] >= 50).sum())
    at_100 = int((complete_placebo["placebo_count"] >= 100).sum())
    unavailable = expected_status["complete"] - at_50
    expected_placebos = summary["placebos"]
    if (
        at_50 != int(expected_placebos["complete_with_at_least_50"])
        or at_100 != int(expected_placebos["complete_with_100"])
        or at_50 + unavailable != expected_status["complete"]
        or at_100 > at_50
    ):
        placebo_violations.append(
            {
                "issue": "nested_placebo_arithmetic_mismatch",
                "complete": expected_status["complete"],
                "at_least_50": at_50,
                "at_least_100": at_100,
                "unavailable": unavailable,
            }
        )
    for case_figure in (
        "fig_case_studies_complete.pdf",
        "fig_case_studies_abstention.pdf",
    ):
        case_record = output_records.get(f"generated/figures/{case_figure}", {})
        if "artifacts/time_placebo_scores.csv" in case_record.get("sources", []):
            placebo_violations.append(
                {
                    "issue": "case_figure_uses_unfrozen_score_series",
                    "figure": case_figure,
                }
            )
    checks.append(check("nested_placebo_availability", placebo_violations))

    interval_violations: list[dict[str, Any]] = []
    coverage = pd.read_csv(ROOT / "artifacts" / "synthetic_interval_coverage_v2_summary.csv")
    methods = {
        "standard_synthetic_control",
        "metashift_v1_fixed",
        "metashift_v2_cv",
        "nearest_neighbor_did",
    }
    for interval_type, nominal in (
        ("conditional_block_bootstrap", 0.95),
        ("split_conformal", 0.90),
    ):
        rows = coverage.loc[
            (coverage["interval_type"] == interval_type)
            & (coverage["split"] == "evaluation")
            & (coverage["stratum_type"] == "all")
        ]
        if (
            set(rows["method"]) != methods
            or len(rows) != len(methods)
            or not rows["nominal_coverage"].eq(nominal).all()
            or not rows["empirical_coverage"].between(0, 1).all()
            or not (rows["mean_interval_width_log"] > 0).all()
        ):
            interval_violations.append(
                {
                    "issue": "interval_coverage_or_width_invariant_failed",
                    "interval_type": interval_type,
                }
            )
    checks.append(check("interval_nominal_coverage_and_width", interval_violations))

    window_violations = window_contract_violations(load_json(WINDOW_CONFIG_PATH))
    checks.append(check("inclusive_window_protocol", window_violations))

    external_violations: list[dict[str, Any]] = []
    external_config = load_json(EXTERNAL_CONFIG_PATH)
    qa = pd.read_csv(ROOT / "artifacts" / "external_validation_evidence.csv")
    qa = qa.loc[qa["evidence_source"] == "qa_collocation"]
    qa_counts = {
        "candidates": int(len(qa)),
        "target_poc_matched": int(
            (qa["evidence_status"] == "insufficient_matched_pre_post_qa_records").sum()
        ),
        "adequate_matched_pre_post": int(
            (qa["evidence_status"] == "paired_pre_post_available").sum()
        ),
    }
    expected_qa = {
        key: int(value)
        for key, value in external_config["qa_collocation_evidence"][
            "expected_counts"
        ].items()
    }
    if qa_counts != expected_qa or qa_counts != {
        "candidates": 12,
        "target_poc_matched": 2,
        "adequate_matched_pre_post": 0,
    }:
        external_violations.append(
            {
                "issue": "qa_evidence_ladder_mismatch",
                "expected": expected_qa,
                "actual": qa_counts,
            }
        )
    checks.append(check("external_evidence_ladder", external_violations))

    concentration_violations: list[dict[str, Any]] = []
    dates = pd.to_datetime(audit["anchor_date"], errors="raise")
    anchors_2023 = audit.loc[dates.dt.year == 2023]
    codes = anchors_2023[["old_method_code", "new_method_code"]].apply(
        pd.to_numeric, errors="raise"
    )
    counts = {
        "anchors_2023": int(len(anchors_2023)),
        "236_to_636": int(
            ((codes["old_method_code"] == 236) & (codes["new_method_code"] == 636)).sum()
        ),
        "238_to_638": int(
            ((codes["old_method_code"] == 238) & (codes["new_method_code"] == 638)).sum()
        ),
    }
    if counts != {
        "anchors_2023": 393,
        "236_to_636": 234,
        "238_to_638": 120,
    }:
        concentration_violations.append(
            {"issue": "descriptive_2023_concentration_mismatch", "actual": counts}
        )
    checks.append(
        check("appendix_only_descriptive_2023_concentration", concentration_violations)
    )

    case_violations: list[dict[str, Any]] = []
    case_manifest = load_json(CASE_MANIFEST_PATH)
    cases = case_manifest.get("cases", [])
    expected_case_ids = {
        "12-057-0113-poc1-2023-12-01",
        "06-031-0004-poc8-2021-01-12",
        "01-103-0011-poc3-2023-02-01",
    }
    if {case.get("anchor_id") for case in cases} != expected_case_ids:
        case_violations.append({"issue": "deterministic_case_ids_mismatch"})
    for case in cases:
        error = case.get("reconstruction_absolute_error")
        if error is not None and float(error) > 1e-9:
            case_violations.append(
                {
                    "issue": "case_reconstruction_error_exceeds_tolerance",
                    "anchor_id": case.get("anchor_id"),
                    "absolute_error": error,
                }
            )
    checks.append(check("deterministic_case_reconstruction", case_violations))

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "frozen_evidence": summary["frozen_evidence"],
        "result_label": manifest.get("result_label"),
        "required_figure_count": len(REQUIRED_FIGURES),
        "redesigned_figure_partition_counts": partition_counts,
        "checks": checks,
        "all_checks_passed": all(bool(item["passed"]) for item in checks),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
