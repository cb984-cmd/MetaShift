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
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
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
    record_violations: list[dict[str, object]] = []
    summary = load_json(SUMMARY_PATH, record_violations, "frozen_evidence_summary")
    assets = load_json(ASSET_MANIFEST_PATH, record_violations, "asset_manifest")
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
        and r"\EvidenceTag" in frontmatter
    )
    add_check(
        checks,
        "frozen_evidence_binding",
        frozen_ok,
        "The report and generated assets bind to the immutable v0.3.2 evidence release.",
    )

    ledger_ok = (
        ledger.get("all_checks_passed") is True
        and ledger.get("claim_count", 0) == 36
        and ledger.get("asset_reference_count", 0) >= 60
    )
    add_check(
        checks,
        "claim_ledger_validation",
        ledger_ok,
        "All 36 quantitative formal-paper claims map to hash-verified sources and assets.",
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
        assets.get("schema_version") == 3
        and len(assets.get("outputs", [])) >= 32
        and asset_determinism.get("all_hashes_match") is True
        and asset_determinism.get("output_count", 0) >= 32,
        "Two independent paper-asset generations have identical hashes for 32 or more outputs.",
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
    pdf_hash = sha256(FINAL_PDF_PATH) if FINAL_PDF_PATH.is_file() else ""
    named_pdf_hash = sha256(NAMED_BUILD_PDF_PATH) if NAMED_BUILD_PDF_PATH.is_file() else ""
    pdf_ok = (
        FINAL_PDF_PATH.is_file()
        and FINAL_PDF_PATH.stat().st_size > 100_000
        and FINAL_PDF_PATH.read_bytes()[:5] == b"%PDF-"
        and NAMED_BUILD_PDF_PATH.is_file()
        and pdf_hash == named_pdf_hash
        and build.get("final_pdf") == "paper/latex/MetaShift_Bench_Yau_2026.pdf"
        and build.get("build_pdf") == "paper/latex/build/MetaShift_Bench_Yau_2026.pdf"
        and build.get("build_mode") == "final"
        and build.get("source_worktree_clean_at_start") is True
        and build.get("pdf_bytes") == FINAL_PDF_PATH.stat().st_size
        and build.get("pdf_sha256") == pdf_hash
        and build.get("build_pdf_sha256") == named_pdf_hash
        and build.get("rendered_page_count") == len(pages)
        and len(pages) > 1
        and build.get("overfull_hbox_warnings") == 0
        and build.get("pdf_metadata", {}).get("Title")
        == "MetaShift-Bench: A Metadata-Anchored Audit Benchmark for PM2.5 Method-Transition Discontinuities"
        and build.get("pdf_metadata", {}).get("Author") == "Human completion required"
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
        and font_audit.get("pdf_count", 0) >= 15
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
        and "Revision completion report" in completion
        and "v0.3.2-evidence-final" in completion
        and "HUMAN REVIEW REQUIRED" in completion
    )
    add_check(
        checks,
        "self_review_and_completion_handoff",
        review_documents_ok,
        "The review and completion records distinguish technical completion from human-only submission work.",
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
        "frozen_evidence": frozen,
        "source_word_count_estimate": word_count,
        "compiled_pdf": {
            "bytes": FINAL_PDF_PATH.stat().st_size if FINAL_PDF_PATH.is_file() else 0,
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
