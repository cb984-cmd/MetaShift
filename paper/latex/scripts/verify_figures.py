"""Validate the formal report's evidence-bound figure set and its logical invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "figure_qa_validation.json"

REQUIRED_FIGURES = (
    "fig_stable_synthetic_example.pdf",
    "fig_donor_construction.pdf",
    "fig_window_protocol.pdf",
    "fig_audit_pipeline.pdf",
    "fig_split_integrity.pdf",
    "fig_synthetic_metrics.pdf",
    "fig_perturbation_metrics.pdf",
    "fig_paired_bootstrap.pdf",
    "fig_event_accounting.pdf",
    "fig_placebos.pdf",
    "fig_interval_coverage.pdf",
    "fig_screening_sensitivity.pdf",
    "fig_external_evidence.pdf",
    "fig_case_studies.pdf",
    "fig_applicability_map.pdf",
    "fig_anchor_concentration.pdf",
)

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
    "fig_paired_bootstrap.pdf": {
        "artifacts/stable_synthetic_stable_full_v2_bootstrap.csv",
    },
    "fig_event_accounting.pdf": {
        "artifacts/real_transition_88101_event_audit.csv",
        "artifacts/real_transition_88101_evidence_tiers.csv",
    },
    "fig_placebos.pdf": {"artifacts/time_placebo_summary.csv"},
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
    "fig_case_studies.pdf": {
        "paper/latex/configs/case_study_rendering_v2.json",
        "artifacts/real_transition_88101_method_results.csv",
        "artifacts/time_placebo_summary.csv",
    },
    "fig_applicability_map.pdf": {
        "artifacts/real_transition_88101_event_audit.csv",
        "artifacts/real_transition_88101_evidence_tier_summary.json",
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
        if any(token in content.lower() for token in (b"todo", b"tbd", b"placeholder")):
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

    accounting_violations: list[dict[str, Any]] = []
    audit = pd.read_csv(ROOT / "artifacts" / "real_transition_88101_event_audit.csv")
    tiers = pd.read_csv(
        ROOT / "artifacts" / "real_transition_88101_evidence_tiers.csv"
    )
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
    if not (
        statuses["insufficient_geographic_donors"]
        + statuses["estimator_input_failure"]
        + statuses["complete"]
        == 563
        and tier_counts["supported_candidate_discontinuity"] == 34
        and tier_counts["not_supported_by_available_evidence"] == 122
        and tier_counts["inconclusive_insufficient_evidence"] == 407
    ):
        accounting_violations.append({"issue": "headline_accounting_invariant_failed"})
    checks.append(check("anchor_and_tier_accounting", accounting_violations))

    split_violations: list[dict[str, Any]] = []
    split = load_json(ROOT / "artifacts" / "stable_synthetic_case_split_audit.json")
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
    placebo = pd.read_csv(ROOT / "artifacts" / "time_placebo_summary.csv")
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
        or unavailable != 71
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
    case_record = output_records.get("generated/figures/fig_case_studies.pdf", {})
    if "artifacts/time_placebo_scores.csv" in case_record.get("sources", []):
        placebo_violations.append({"issue": "case_figure_uses_unfrozen_score_series"})
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
        "checks": checks,
        "all_checks_passed": all(bool(item["passed"]) for item in checks),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
