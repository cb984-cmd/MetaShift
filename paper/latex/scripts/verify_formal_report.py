"""Verify the formal report's source-to-PDF compliance handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
MAIN_PATH = LATEX_ROOT / "main.tex"
METADATA_PATH = LATEX_ROOT / "metadata.tex"
COVER_PATH = LATEX_ROOT / "sections" / "cover.tex"
FRONTMATTER_PATH = LATEX_ROOT / "sections" / "frontmatter.tex"
ACKNOWLEDGEMENTS_PATH = LATEX_ROOT / "sections" / "acknowledgements.tex"
HUMAN_CHECKLIST_PATH = LATEX_ROOT / "HUMAN_COMPLETION_CHECKLIST.md"
SELF_REVIEW_PATH = LATEX_ROOT / "PAPER_SELF_REVIEW.md"
COMPLETION_REPORT_PATH = LATEX_ROOT / "REVISION_COMPLETION_REPORT.md"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
V05_RESULT_MANIFEST_PATH = ROOT / "configs" / "v05_frozen_result_manifest.json"
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
V05_ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "v05_answerability_asset_manifest.json"
V05_ASSET_VALIDATION_PATH = LATEX_ROOT / "generated" / "v05_answerability_asset_validation.json"
V05_ASSET_DETERMINISM_PATH = (
    LATEX_ROOT / "generated" / "v05_answerability_asset_determinism.json"
)
V05_LEDGER_REPORT_PATH = LATEX_ROOT / "generated" / "v05_claim_ledger_validation.json"
LEDGER_REPORT_PATH = LATEX_ROOT / "generated" / "claim_ledger_validation.json"
SOURCE_REPORT_PATH = LATEX_ROOT / "generated" / "paper_source_validation.json"
REFERENCE_REPORT_PATH = LATEX_ROOT / "generated" / "reference_validation.json"
ASSET_DETERMINISM_REPORT_PATH = (
    LATEX_ROOT / "generated" / "asset_determinism_validation.json"
)
BUILD_REPORT_PATH = LATEX_ROOT / "generated" / "build_report.json"
CLEAN_BUILD_PATH = LATEX_ROOT / "generated" / "clean_build_record.json"
VISUAL_PREFLIGHT_PATH = LATEX_ROOT / "generated" / "visual_preflight.json"
FONT_AUDIT_PATH = LATEX_ROOT / "generated" / "font_audit.json"
FIGURE_QA_PATH = LATEX_ROOT / "generated" / "figure_qa_validation.json"
FIGURE_LAYOUT_QA_PATH = LATEX_ROOT / "generated" / "figure_layout_qa.json"
FINAL_FIGURE_QA_PATH = LATEX_ROOT / "generated" / "final_figure_placement_qa.json"
FINAL_PDF_PATH = LATEX_ROOT / "MetaShift_Bench_Yau_2026.pdf"
NAMED_BUILD_PDF_PATH = LATEX_ROOT / "build" / "MetaShift_Bench_Yau_2026.pdf"
RENDER_DIR = LATEX_ROOT / "rendered_pages"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "formal_report_compliance.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate formal-report structure, frozen evidence, and PDF handoff."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Report path, relative to the LaTeX project by default.",
    )
    parser.add_argument(
        "--candidate-pdf",
        type=Path,
        help=(
            "Verify a staged final-build candidate before it replaces the canonical "
            "PDF. The build report must identify the same candidate."
        ),
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_json(
    path: Path, violations: list[dict[str, object]], name: str
) -> dict[str, Any]:
    if not path.is_file():
        violations.append({"issue": "missing_json_record", "record": name, "path": str(path)})
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        violations.append(
            {
                "issue": "invalid_json_record",
                "record": name,
                "path": str(path),
                "error": str(error),
            }
        )
        return {}
    if not isinstance(value, dict):
        violations.append({"issue": "json_record_is_not_object", "record": name})
        return {}
    return value


def add_check(
    checks: list[dict[str, object]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def source_word_count() -> int:
    sources = [
        MAIN_PATH,
        METADATA_PATH,
        *(LATEX_ROOT / "sections").glob("*.tex"),
    ]
    text = "\n".join(read_text(path) for path in sources)
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\[A-Za-z@]+[*]?(?:\[[^]]*\])?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9.'/-]*", text))


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    candidate_pdf = (
        resolve_from_latex(args.candidate_pdf) if args.candidate_pdf is not None else None
    )
    audited_pdf = candidate_pdf if candidate_pdf is not None else FINAL_PDF_PATH
    record_violations: list[dict[str, object]] = []
    summary = load_json(SUMMARY_PATH, record_violations, "frozen_evidence_summary")
    v05_result = load_json(
        V05_RESULT_MANIFEST_PATH, record_violations, "v05_frozen_result_manifest"
    )
    assets = load_json(ASSET_MANIFEST_PATH, record_violations, "asset_manifest")
    v05_assets = load_json(
        V05_ASSET_MANIFEST_PATH, record_violations, "v05_answerability_asset_manifest"
    )
    v05_asset_validation = load_json(
        V05_ASSET_VALIDATION_PATH,
        record_violations,
        "v05_answerability_asset_validation",
    )
    v05_asset_determinism = load_json(
        V05_ASSET_DETERMINISM_PATH,
        record_violations,
        "v05_answerability_asset_determinism",
    )
    v05_ledger = load_json(
        V05_LEDGER_REPORT_PATH, record_violations, "v05_claim_ledger_validation"
    )
    ledger = load_json(LEDGER_REPORT_PATH, record_violations, "claim_ledger_validation")
    source = load_json(SOURCE_REPORT_PATH, record_violations, "paper_source_validation")
    references = load_json(REFERENCE_REPORT_PATH, record_violations, "reference_validation")
    asset_determinism = load_json(
        ASSET_DETERMINISM_REPORT_PATH, record_violations, "asset_determinism_validation"
    )
    build = load_json(BUILD_REPORT_PATH, record_violations, "build_report")
    clean_build = load_json(CLEAN_BUILD_PATH, record_violations, "clean_build_record")
    visual_preflight = load_json(
        VISUAL_PREFLIGHT_PATH, record_violations, "visual_preflight"
    )
    font_audit = load_json(FONT_AUDIT_PATH, record_violations, "font_audit")
    figure_qa = load_json(FIGURE_QA_PATH, record_violations, "figure_qa_validation")
    figure_layout_qa = load_json(
        FIGURE_LAYOUT_QA_PATH, record_violations, "figure_layout_qa"
    )
    final_figure_qa = load_json(
        FINAL_FIGURE_QA_PATH, record_violations, "final_figure_placement_qa"
    )

    checks: list[dict[str, object]] = []
    main_source = read_text(MAIN_PATH)
    metadata = read_text(METADATA_PATH)
    cover = read_text(COVER_PATH)
    frontmatter = read_text(FRONTMATTER_PATH)
    acknowledgements = read_text(ACKNOWLEDGEMENTS_PATH)
    human_checklist = read_text(HUMAN_CHECKLIST_PATH)
    all_sections = "\n".join(
        read_text(path) for path in (LATEX_ROOT / "sections").glob("*.tex")
    )

    required_inputs = (
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
    input_positions = [
        main_source.find(rf"\input{{{item}}}") for item in required_inputs
    ]
    bibliography_position = main_source.find(r"\bibliography{references}")
    structure_ok = (
        "a4paper" in main_source
        and r"\tableofcontents" in main_source
        and r"\section*{Abstract}" in frontmatter
        and r"\textbf{Keywords:}" in frontmatter
        and all(position >= 0 for position in input_positions)
        and input_positions == sorted(input_positions)
        and bibliography_position > input_positions[13]
        and input_positions[14] > bibliography_position
        and input_positions[15] > input_positions[14]
    )
    add_check(
        checks,
        "official_order_and_required_sections",
        structure_ok,
        "The formal narrative, references, appendix, and required disclosures appear in order.",
    )

    placeholders_ok = (
        all(
            token in metadata
            for token in (
                r"\StudentAuthors",
                r"\SchoolAffiliation",
                r"\SupervisingTeachers",
                r"\ReportDate",
            )
        )
        and "HUMAN COMPLETION REQUIRED" in cover
        and "HUMAN COMPLETION REQUIRED" in acknowledgements
        and "HUMAN REVIEW REQUIRED" in human_checklist
    )
    add_check(
        checks,
        "human_only_submission_fields_preserved",
        placeholders_ok,
        "Identity, contribution, advisor, AI-use, and attestation fields remain human-only.",
    )

    frozen = summary.get("frozen_evidence", {})
    expected_tag = "v0.3.2-evidence-final"
    expected_commit = "57d678ecabebff724d898abe626c9ef80538775b"
    expected_release = (
        "https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final"
    )
    frozen_ok = (
        frozen.get("tag") == expected_tag
        and frozen.get("commit") == expected_commit
        and frozen.get("release_url") == expected_release
        and assets.get("frozen_evidence") == frozen
        and assets.get("result_label") == "stable_full_v2"
        and r"\input{generated/evidence_macros}" in metadata
        and r"\EvidenceTag" in all_sections
        and r"\EvidenceCommit" in all_sections
    )
    add_check(
        checks,
        "frozen_evidence_binding",
        frozen_ok,
        "The report and generated assets bind to the immutable v0.3.2 evidence release.",
    )

    v05_receipt = next(
        (
            record
            for record in v05_result.get("artifacts", [])
            if isinstance(record, dict)
            and record.get("path")
            == "artifacts/v05_answerability_frontier/v05_execution_receipt.json"
        ),
        {},
    )
    v05_ok = (
        v05_result.get("manifest_id") == "v0.5.0-frozen-result-provenance"
        and v05_result.get("evidence_status") == "frozen_one_time_execution_verified"
        and v05_result.get("execution_authority", {}).get("execution_freeze_tag")
        == "v0.5.0-answerability-freeze"
        and v05_result.get("execution_authority", {}).get("execution_claim_tag")
        == "v0.5.0-answerability-execution-claim"
        and v05_assets.get("protocol_id") == "v0.5-answerability-frontier"
        and v05_assets.get("source_receipt", {}).get("sha256") == v05_receipt.get("sha256")
        and v05_asset_validation.get("all_checks_passed") is True
    )
    add_check(
        checks,
        "frozen_v05_scope_answerability_binding",
        v05_ok,
        "The report's v0.5 tables and figures remain bound to the one-time frozen receipt.",
    )

    ledger_ok = (
        ledger.get("all_checks_passed") is True
        and ledger.get("claim_count", 0) == 39
        and ledger.get("asset_reference_count", 0) >= 60
    )
    add_check(
        checks,
        "claim_ledger_validation",
        ledger_ok,
        "All 39 quantitative formal-paper claims map to hash-verified sources and assets.",
    )

    source_ok = (
        source.get("all_checks_passed") is True
        and source.get("citation_count", 0) >= 30
        and source.get("citation_count", 0) == source.get("bibliography_entry_count", -1)
        and source.get("asset_output_count", 0) >= 32
    )
    add_check(
        checks,
        "source_and_citation_validation",
        source_ok and references.get("all_checks_passed") is True,
        "All cited references are defined, used, structurally complete, and broad enough for the report.",
    )

    add_check(
        checks,
        "generated_asset_determinism",
        assets.get("schema_version") == 4
        and len(assets.get("outputs", [])) >= 38
        and asset_determinism.get("all_hashes_match") is True
        and asset_determinism.get("output_count", 0) >= 38,
        "Two independent paper-asset generations have identical hashes for 38 or more outputs.",
    )

    v05_presentation_ok = (
        v05_assets.get("schema_version") == 1
        and len(v05_assets.get("outputs", [])) == 11
        and v05_asset_validation.get("all_checks_passed") is True
        and v05_asset_determinism.get("all_hashes_match") is True
        and v05_asset_determinism.get("output_count") == 11
    )
    add_check(
        checks,
        "v05_receipt_bound_presentation_assets",
        v05_presentation_ok,
        "Five v0.5 figures, three tables, and claim-value metadata are receipt-bound.",
    )

    v05_ledger_ok = (
        v05_ledger.get("all_checks_passed") is True
        and v05_ledger.get("claim_count") == 12
        and v05_ledger.get("asset_reference_count", 0) >= 20
        and v05_ledger.get("verification_status_counts")
        == {"verified_frozen_v05_evidence": 12}
    )
    add_check(
        checks,
        "v05_claim_ledger_validation",
        v05_ledger_ok,
        "All 12 v0.5 manuscript claims are recomputed from receipt-bound frozen evidence.",
    )

    figure_qa_ok = (
        figure_qa.get("all_checks_passed") is True
        and figure_qa.get("required_figure_count") == 17
        and len(figure_qa.get("checks", [])) >= 11
    )
    add_check(
        checks,
        "figure_logical_and_vector_validation",
        figure_qa_ok,
        "All 17 figures pass source-hash, vector, accounting, isolation, interval, and display-contract checks.",
    )

    final_figure_qa_ok = (
        figure_layout_qa.get("all_checks_passed") is True
        and figure_layout_qa.get("required_figure_count") == 17
        and load_json(
            V05_ASSET_MANIFEST_PATH,
            record_violations,
            "v05_answerability_asset_manifest_for_figures",
        ).get("schema_version")
        == 1
        and final_figure_qa.get("all_checks_passed") is True
        and final_figure_qa.get("required_figure_count") == 22
        and final_figure_qa.get("source_pdf_sha256") == build.get("pdf_sha256")
        and final_figure_qa.get("crop_dpi") == [150, 300]
    )
    add_check(
        checks,
        "final_print_geometry_and_crop_review",
        final_figure_qa_ok,
        "All 22 figures have measured source geometry plus 150- and 300-DPI final-page crop records.",
    )

    normalized_sections = normalized(all_sections)
    taxonomy_and_boundary_ok = (
        "no taxonomy-stratified analysis is reported" in normalized_sections.lower()
        and "does not support a general MetaShift superiority claim" in normalized(frontmatter)
        and "diagnostic rather than calibrated" in normalized_sections
        and "not a verified intervention" in normalized_sections
        and "not an estimate of a causal physical bias" in normalized_sections
    )
    add_check(
        checks,
        "scientific_and_human_boundaries",
        taxonomy_and_boundary_ok,
        "The report preserves no-superiority, no-causal-instrument, and no-calibrated-real-interval boundaries.",
    )

    pages = sorted(RENDER_DIR.glob("page-*.png"))
    pdf_hash = sha256(audited_pdf) if audited_pdf.is_file() else ""
    named_pdf_hash = sha256(NAMED_BUILD_PDF_PATH) if NAMED_BUILD_PDF_PATH.is_file() else ""
    candidate_path = (
        str(candidate_pdf.relative_to(ROOT)).replace("\\", "/")
        if candidate_pdf is not None and candidate_pdf.is_file()
        else ""
    )
    candidate_contract_ok = (
        candidate_pdf is None
        or (
            candidate_pdf == NAMED_BUILD_PDF_PATH
            and build.get("candidate_pdf") == candidate_path
            and build.get("candidate_pdf_sha256") == pdf_hash
        )
    )
    pdf_ok = (
        audited_pdf.is_file()
        and audited_pdf.stat().st_size > 100_000
        and audited_pdf.read_bytes()[:5] == b"%PDF-"
        and NAMED_BUILD_PDF_PATH.is_file()
        and pdf_hash == named_pdf_hash
        and build.get("final_pdf") == "paper/latex/MetaShift_Bench_Yau_2026.pdf"
        and build.get("build_pdf") == "paper/latex/build/MetaShift_Bench_Yau_2026.pdf"
        and build.get("build_mode") == "final"
        and build.get("source_worktree_clean_at_start") is True
        and build.get("pdf_bytes") == audited_pdf.stat().st_size
        and build.get("pdf_sha256") == pdf_hash
        and build.get("build_pdf_sha256") == named_pdf_hash
        and build.get("rendered_page_count") == len(pages)
        and len(pages) > 1
        and build.get("overfull_hbox_warnings") == 0
        and build.get("pdf_metadata", {}).get("Title")
        == "MetaShift-Bench: A Target-Fixed Benchmark for Selective Scope Answerability"
        and build.get("pdf_metadata", {}).get("Author") == "Human completion required"
        and candidate_contract_ok
    )
    add_check(
        checks,
        "compiled_pdf_and_metadata_integrity",
        pdf_ok,
        "Named build and final PDF copies match by SHA-256, include intended metadata, and have no overfull boxes.",
    )

    clean_build_ok = (
        clean_build.get("all_known_outputs_removed_before_build") is True
        and isinstance(clean_build.get("source_git_commit"), str)
        and len(clean_build.get("source_git_commit", "")) == 40
        and clean_build.get("source_worktree_clean_at_start") is True
        and clean_build.get("source_git_commit") == build.get("source_git_commit")
        and build.get("clean_build_record")
        == "paper/latex/generated/clean_build_record.json"
    )
    add_check(
        checks,
        "clean_build_record",
        clean_build_ok,
        "Only named LaTeX intermediates and rendered review pages are removed before rebuilding.",
    )

    visual_preflight_ok = (
        visual_preflight.get("review_type") == "automated rendered-page preflight"
        and visual_preflight.get("all_pages_rendered_and_nontrivial") is True
        and visual_preflight.get("page_count") == len(pages)
        and len(visual_preflight.get("pages", [])) == len(pages)
        and build.get("visual_preflight")
        == "paper/latex/generated/visual_preflight.json"
    )
    add_check(
        checks,
        "rendered_page_preflight",
        visual_preflight_ok,
        "Every final-PDF page is rendered to a nontrivial PNG for presentation review.",
    )

    font_ok = (
        font_audit.get("all_checks_passed") is True
        and font_audit.get("pdf_count", 0) >= 18
        and font_audit.get("font_count", 0) > 0
        and build.get("font_audit") == "paper/latex/generated/font_audit.json"
    )
    add_check(
        checks,
        "non_type3_embedded_font_audit",
        font_ok,
        "Final PDF and all generated vector figures have no Type 3 or unembedded font.",
    )

    self_review = read_text(SELF_REVIEW_PATH)
    completion = read_text(COMPLETION_REPORT_PATH)
    review_documents_ok = (
        "Evidence-based self-review" in self_review
        and "v0.3.2-evidence-final" in self_review
        and "v0.5-answerability-frontier" in self_review
        and "V05_CLAIM_EVIDENCE_LEDGER.csv" in self_review
        and "Revision completion report" in completion
        and "v0.3.2-evidence-final" in completion
        and "v0.5.0-answerability-freeze" in completion
        and "HUMAN REVIEW REQUIRED" in completion
    )
    add_check(
        checks,
        "self_review_and_completion_handoff",
        review_documents_ok,
        "The review and completion records distinguish frozen v0.3.2/v0.5 evidence from human-only submission work.",
    )

    word_count = source_word_count()
    add_check(
        checks,
        "substantive_report_length",
        word_count >= 5_500,
        "The formal report has at least 5,500 source words across its scientific narrative.",
    )

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "formal_report": "paper/latex/MetaShift_Bench_Yau_2026.pdf",
        "verification_mode": "candidate" if candidate_pdf is not None else "canonical",
        "verified_pdf": str(audited_pdf.relative_to(ROOT)).replace("\\", "/"),
        "frozen_evidence": frozen,
        "source_word_count_estimate": word_count,
        "compiled_pdf": {
            "bytes": audited_pdf.stat().st_size if audited_pdf.is_file() else 0,
            "sha256": pdf_hash,
            "rendered_page_count": len(pages),
        },
        "human_completion_status": "required",
        "taxonomy_status": "human_blocked",
        "record_violations": record_violations,
        "checks": checks,
        "all_checks_passed": not record_violations
        and all(bool(check["passed"]) for check in checks),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
