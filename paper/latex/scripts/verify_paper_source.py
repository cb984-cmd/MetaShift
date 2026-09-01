"""Check formal-paper source structure, citations, generated inputs, and boundaries."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
MAIN_PATH = LATEX_ROOT / "main.tex"
METADATA_PATH = LATEX_ROOT / "metadata.tex"
BIB_PATH = LATEX_ROOT / "references.bib"
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
V05_ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "v05_answerability_asset_manifest.json"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "paper_source_validation.json"
REQUIRED_INPUTS = (
    "sections/cover",
    "sections/frontmatter",
    "sections/introduction",
    "sections/problem",
    "sections/related_work",
    "sections/data",
    "sections/framework",
    "sections/experiments",
    "sections/results",
    "sections/case_studies",
    "sections/discussion",
    "sections/limitations",
    "sections/reproducibility",
    "sections/conclusion",
    "sections/appendix",
    "sections/acknowledgements",
)
REQUIRED_SECTION_TITLES = (
    "Introduction",
    "Problem formulation and claim boundaries",
    "Background and related work",
    "Data and benchmark construction",
    "MetaShift-Bench audit framework",
    "Experimental design",
    "Results",
    "Representative case studies",
    "Discussion",
    "Limitations and threats to validity",
    "Reproducibility, integrity, and contributions",
    "Conclusion",
    "Supplementary protocol details",
    "Case-study reconstruction contract",
    "Acknowledgements, contribution statement, and required disclosures",
)
REQUIRED_GENERATED_INPUTS = (
    "generated/evidence_macros",
    "generated/tables/table_data_summary",
    "generated/tables/table_synthetic_metrics",
    "generated/tables/table_all_methods",
    "generated/tables/table_perturbation_metrics",
    "generated/tables/table_paired_bootstrap",
    "generated/tables/table_ablation",
    "generated/tables/table_evidence_tier_rules",
    "generated/tables/table_claim_boundaries",
    "generated/tables/table_real_audit",
    "generated/tables/table_placebo_external",
    "generated/tables/table_interval_coverage",
    "generated/tables/table_window_scale_sensitivity",
    "generated/tables/table_screening_sensitivity",
    "generated/tables/table_case_studies",
    "generated/tables/table_reproducibility",
    "generated/tables/table_anchor_concentration",
)
REQUIRED_GENERATED_FIGURES = (
    "fig_stable_synthetic_example.pdf",
    "fig_audit_pipeline.pdf",
    "fig_donor_construction.pdf",
    "fig_window_protocol.pdf",
    "fig_split_integrity.pdf",
    "fig_synthetic_metrics.pdf",
    "fig_perturbation_metrics.pdf",
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
REQUIRED_V05_GENERATED_INPUTS = (
    "generated/v05_answerability_macros",
    "generated/tables/table_v05_frontier",
    "generated/tables/table_v05_certificate",
    "generated/tables/table_v05_failure_accounting",
)
REQUIRED_V05_GENERATED_FIGURES = (
    "fig_v05_answerability_frontier.png",
    "fig_v05_structural_margin.png",
    "fig_v05_risk_coverage.png",
    "fig_v05_certificate_validity.png",
    "fig_v05_failure_mode_map.png",
)
LEGACY_FIGURE_NAMES = (
    "fig_local_regional_schematic.pdf",
    "fig_data_construction.pdf",
    "fig_event_flow.pdf",
    "fig_evidence_tiers.pdf",
    "fig_case_studies.pdf",
)
REQUIRED_MACRO_USAGES = (
    r"\EvidenceTag",
    r"\TotalAnchors",
    r"\ThreeDonorAnchors",
    r"\CompleteComparisons",
    r"\InsufficientDonorAnchors",
    r"\InputFailureAnchors",
    r"\SupportedCandidates",
    r"\NotSupportedEvents",
    r"\InconclusiveEvents",
)
REQUIRED_CITATION_KEYS = frozenset(
    {
        "abadie2010",
        "arkhangelsky2021",
        "benjamini1995",
        "benmichael2021",
        "berk2013",
        "callaway2021",
        "epa_airdata_formats",
        "fryzlewicz2014",
        "grange2019",
        "killick2012",
        "kuensch1989",
        "lei2018",
        "menne2009",
        "truong2020",
        "xu2017",
    }
)
REQUIRED_V05_CITATION_KEYS = frozenset(
    {
        "abadie2021",
        "bai1998",
        "barberlimits2021",
        "barigozzi2018",
        "bartlett2008",
        "blackwell1951",
        "blackwell1953",
        "cauchois2024",
        "chow1970",
        "chowwillsky1984",
        "elyaniv2010",
        "franc2023",
        "geifman2017",
        "goren2024",
        "krysander2008",
        "ratner2016",
        "taiebat2017",
        "williams2012",
    }
)
FORBIDDEN_PHRASES = (
    "metashift significantly outperforms standard synthetic control",
    "metashift is significantly superior",
    "method code changes prove",
    "method code transition proves",
    "confirmed instrument failure",
    "instrument failures were discovered",
    "recovered the true pollution concentration",
    "real-event intervals have calibrated 95% coverage",
    "qa validation confirms measurement bias",
)
LEGACY_SECTION_PATHS = (LATEX_ROOT / "sections" / "methods.tex",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate LaTeX report source.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Report path, relative to the LaTeX project by default.",
    )
    return parser.parse_args()


def resolve_from_latex(path: Path) -> Path:
    return path if path.is_absolute() else LATEX_ROOT / path


def read_tex_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in [
        METADATA_PATH,
        MAIN_PATH,
        *(LATEX_ROOT / "sections").glob("*.tex"),
    ]:
        if path.is_file():
            sources[str(path.relative_to(LATEX_ROOT)).replace("\\", "/")] = path.read_text(
                encoding="utf-8"
            )
    return sources


def load_asset_manifest(violations: list[dict[str, object]]) -> dict[str, Any]:
    if not ASSET_MANIFEST_PATH.is_file():
        violations.append({"issue": "missing_asset_manifest"})
        return {}
    try:
        manifest = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        violations.append({"issue": "invalid_asset_manifest", "error": str(error)})
        return {}
    if not isinstance(manifest, dict):
        violations.append({"issue": "asset_manifest_is_not_object"})
        return {}
    return manifest


def load_v05_asset_manifest(violations: list[dict[str, object]]) -> dict[str, Any]:
    if not V05_ASSET_MANIFEST_PATH.is_file():
        violations.append({"issue": "missing_v05_asset_manifest"})
        return {}
    try:
        manifest = json.loads(V05_ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        violations.append({"issue": "invalid_v05_asset_manifest", "error": str(error)})
        return {}
    if not isinstance(manifest, dict):
        violations.append({"issue": "v05_asset_manifest_is_not_object"})
        return {}
    return manifest


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    sources = read_tex_sources()
    main_source = sources.get("main.tex", "")
    metadata = sources.get("metadata.tex", "")
    combined = "\n".join(sources.values())
    violations: list[dict[str, object]] = []

    input_positions: list[tuple[str, int]] = []
    for required in REQUIRED_INPUTS:
        token = rf"\input{{{required}}}"
        position = main_source.find(token)
        if position == -1:
            violations.append({"issue": "missing_required_input", "input": required})
        else:
            input_positions.append((required, position))
    if input_positions != sorted(input_positions, key=lambda item: item[1]):
        violations.append({"issue": "report_sections_are_out_of_order"})

    conclusion_position = main_source.find(r"\input{sections/conclusion}")
    bibliography_position = main_source.find(r"\bibliography{references}")
    appendix_position = main_source.find(r"\input{sections/appendix}")
    acknowledgements_position = main_source.find(r"\input{sections/acknowledgements}")
    if bibliography_position <= conclusion_position:
        violations.append({"issue": "references_do_not_follow_main_text"})
    if appendix_position <= bibliography_position:
        violations.append({"issue": "appendices_do_not_follow_references"})
    if acknowledgements_position <= appendix_position:
        violations.append({"issue": "acknowledgements_do_not_follow_appendices"})

    for title in REQUIRED_SECTION_TITLES:
        heading_pattern = rf"\\(?:section|subsection|subsubsection)\*?\{{{re.escape(title)}\}}"
        if re.search(heading_pattern, combined) is None:
            violations.append({"issue": "missing_section_title", "title": title})
    for generated_input in REQUIRED_GENERATED_INPUTS:
        if rf"\input{{{generated_input}}}" not in combined:
            violations.append(
                {"issue": "missing_generated_input", "input": generated_input}
            )
    for generated_input in REQUIRED_V05_GENERATED_INPUTS:
        if rf"\input{{{generated_input}}}" not in combined:
            violations.append(
                {"issue": "missing_v05_generated_input", "input": generated_input}
            )
    for figure in REQUIRED_GENERATED_FIGURES:
        if rf"\includegraphics" not in combined or figure not in combined:
            violations.append({"issue": "missing_generated_figure", "figure": figure})
    for figure in REQUIRED_V05_GENERATED_FIGURES:
        if rf"\includegraphics" not in combined or figure not in combined:
            violations.append({"issue": "missing_v05_generated_figure", "figure": figure})
    for figure in LEGACY_FIGURE_NAMES:
        if figure in combined:
            violations.append({"issue": "superseded_figure_reference", "figure": figure})
    for macro in REQUIRED_MACRO_USAGES:
        if macro not in combined:
            violations.append({"issue": "missing_evidence_macro", "macro": macro})
    for legacy_path in LEGACY_SECTION_PATHS:
        if legacy_path.is_file():
            violations.append(
                {
                    "issue": "obsolete_unreferenced_section_present",
                    "path": str(legacy_path.relative_to(LATEX_ROOT)).replace("\\", "/"),
                }
            )

    lower = combined.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lower:
            violations.append({"issue": "forbidden_claim_phrase", "phrase": phrase})
    if "human completion required" not in lower:
        violations.append({"issue": "human_completion_boundary_missing"})
    if "no taxonomy-stratified analysis is reported" not in re.sub(r"\s+", " ", lower):
        violations.append({"issue": "taxonomy_human_block_missing"})
    metadata_checks = {
        "pdf_title": (
            "pdftitle={MetaShift-Bench: A Target-Fixed Benchmark for Selective Scope Answerability}"
            in metadata
        ),
        "pdf_author_placeholder": "pdfauthor={Human completion required}" in metadata,
        "pdf_subject": "pdfsubject={Formal research report" in metadata,
        "embedded_generated_macros": r"\input{generated/evidence_macros}" in metadata,
        "embedded_v05_generated_macros": r"\input{generated/v05_answerability_macros}"
        in metadata,
    }
    for name, passed in metadata_checks.items():
        if not passed:
            violations.append({"issue": "missing_pdf_metadata_or_macro", "name": name})

    cited = set()
    for cite_group in re.findall(r"\\cite[a-zA-Z*]*\{([^}]+)\}", combined):
        cited.update(key.strip() for key in cite_group.split(",") if key.strip())
    bibliography = BIB_PATH.read_text(encoding="utf-8") if BIB_PATH.is_file() else ""
    defined = set(re.findall(r"@\w+\{([^,]+),", bibliography))
    missing_citations = sorted(cited - defined)
    if missing_citations:
        violations.append(
            {"issue": "undefined_bibliography_keys", "keys": missing_citations}
        )
    unused_bibliography_keys = sorted(defined - cited)
    if unused_bibliography_keys:
        violations.append(
            {"issue": "unused_bibliography_keys", "keys": unused_bibliography_keys}
        )
    if len(cited) < 30:
        violations.append({"issue": "insufficient_citation_breadth", "count": len(cited)})
    missing_required_citations = sorted(
        (REQUIRED_CITATION_KEYS | REQUIRED_V05_CITATION_KEYS) - cited
    )
    if missing_required_citations:
        violations.append(
            {
                "issue": "missing_required_citation_categories",
                "keys": missing_required_citations,
            }
        )

    asset_manifest = load_asset_manifest(violations)
    outputs = asset_manifest.get("outputs", [])
    output_paths = {
        str(output.get("path"))
        for output in outputs
        if isinstance(output, dict) and isinstance(output.get("path"), str)
    }
    required_asset_paths = {
        "generated/evidence_macros.tex",
        "generated/claim_value_manifest.json",
        "generated/case_study_manifest.json",
        "generated/synthetic_motivating_example_manifest.json",
        "generated/figure_layout_qa.json",
        *(
            "generated/tables/" + generated_input.rsplit("/", 1)[-1] + ".tex"
            for generated_input in REQUIRED_GENERATED_INPUTS
            if generated_input.startswith("generated/tables/")
        ),
        *("generated/figures/" + figure for figure in REQUIRED_GENERATED_FIGURES),
    }
    missing_asset_manifest_records = sorted(required_asset_paths - output_paths)
    if missing_asset_manifest_records:
        violations.append(
            {
                "issue": "required_asset_missing_from_manifest",
                "paths": missing_asset_manifest_records,
            }
        )
    if asset_manifest.get("schema_version") != 4:
        violations.append(
            {
                "issue": "asset_manifest_schema_version_mismatch",
                "actual": asset_manifest.get("schema_version"),
            }
        )
    if asset_manifest.get("result_label") != "stable_full_v2":
        violations.append(
            {
                "issue": "asset_manifest_result_label_mismatch",
                "actual": asset_manifest.get("result_label"),
            }
        )
    if len(outputs) < 38:
        violations.append(
            {"issue": "insufficient_generated_assets", "actual": len(outputs), "minimum": 38}
        )
    for relative_path in sorted(required_asset_paths):
        path = LATEX_ROOT / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            violations.append(
                {"issue": "missing_or_empty_required_generated_asset", "path": relative_path}
            )

    v05_assets = load_v05_asset_manifest(violations)
    v05_output_records = {
        str(output.get("path")): output
        for output in v05_assets.get("outputs", [])
        if isinstance(output, dict) and isinstance(output.get("path"), str)
    }
    expected_v05_asset_paths = {
        "generated/v05_answerability_macros.tex",
        "generated/v05_claim_value_manifest.json",
        *(
            "generated/tables/" + generated_input.rsplit("/", 1)[-1] + ".tex"
            for generated_input in REQUIRED_V05_GENERATED_INPUTS
            if generated_input.startswith("generated/tables/")
        ),
        *("generated/figures/" + figure for figure in REQUIRED_V05_GENERATED_FIGURES),
        "generated/v05_figure_layout_qa.json",
    }
    missing_v05_records = sorted(expected_v05_asset_paths - set(v05_output_records))
    if missing_v05_records:
        violations.append(
            {
                "issue": "required_v05_asset_missing_from_manifest",
                "paths": missing_v05_records,
            }
        )
    for relative_path in sorted(expected_v05_asset_paths):
        path = LATEX_ROOT / relative_path
        record = v05_output_records.get(relative_path, {})
        if not path.is_file() or path.stat().st_size == 0:
            violations.append(
                {"issue": "missing_or_empty_v05_generated_asset", "path": relative_path}
            )
        elif record.get("sha256") is not None:
            import hashlib

            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != record.get("sha256"):
                violations.append(
                    {"issue": "v05_generated_asset_hash_mismatch", "path": relative_path}
                )
    if (
        v05_assets.get("schema_version") != 1
        or v05_assets.get("protocol_id") != "v0.5-answerability-frontier"
        or v05_assets.get("execution_freeze_tag") != "v0.5.0-answerability-freeze"
        or v05_assets.get("execution_claim_tag")
        != "v0.5.0-answerability-execution-claim"
    ):
        violations.append({"issue": "v05_asset_manifest_identity_mismatch"})

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_files": sorted(sources),
        "citation_count": len(cited),
        "bibliography_entry_count": len(defined),
        "asset_output_count": len(outputs),
        "v05_asset_output_count": len(v05_output_records),
        "all_checks_passed": not violations,
        "violations": violations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
