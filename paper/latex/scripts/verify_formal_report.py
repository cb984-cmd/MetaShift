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
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
LEDGER_REPORT_PATH = LATEX_ROOT / "generated" / "claim_ledger_validation.json"
SOURCE_REPORT_PATH = LATEX_ROOT / "generated" / "paper_source_validation.json"
REFERENCE_REPORT_PATH = LATEX_ROOT / "generated" / "reference_validation.json"
ASSET_DETERMINISM_REPORT_PATH = (
    LATEX_ROOT / "generated" / "asset_determinism_validation.json"
)
BUILD_REPORT_PATH = LATEX_ROOT / "generated" / "build_report.json"
FINAL_PDF_PATH = LATEX_ROOT / "MetaShift_Bench_Yau_2026.pdf"
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


def load_json(path: Path, violations: list[dict[str, object]], name: str) -> dict[str, Any]:
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

    checks: list[dict[str, object]] = []
    main = read_text(MAIN_PATH)
    metadata = read_text(METADATA_PATH)
    cover = read_text(COVER_PATH)
    frontmatter = read_text(FRONTMATTER_PATH)
    acknowledgements = read_text(ACKNOWLEDGEMENTS_PATH)
    human_checklist = read_text(HUMAN_CHECKLIST_PATH)

    required_sections = (
        "Introduction",
        "Background and related work",
        "Data and event construction",
        "Methods",
        "Experimental design",
        "Results",
        "Discussion",
        "Limitations and threats to validity",
        "Conclusion",
        "Acknowledgements, contribution statement, and required disclosures",
    )
    all_sections = "\n".join(
        read_text(path) for path in (LATEX_ROOT / "sections").glob("*.tex")
    )
    structure_ok = (
        "a4paper" in main
        and r"\tableofcontents" in main
        and r"\section*{Abstract}" in frontmatter
        and r"\textbf{Keywords:}" in frontmatter
        and main.find(r"\bibliography{references}") > main.find(r"\input{sections/conclusion}")
        and main.find(r"\input{sections/acknowledgements}") > main.find(r"\bibliography{references}")
        and all(rf"\section{{{title}}}" in all_sections for title in required_sections)
    )
    add_check(
        checks,
        "official_order_and_required_sections",
        structure_ok,
        "A4 title page, abstract, keywords, contents, main sections, references, and disclosures are present in order.",
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
        and ledger.get("claim_count", 0) >= 32
        and ledger.get("asset_reference_count", 0) >= 51
    )
    add_check(
        checks,
        "claim_ledger_validation",
        ledger_ok,
        "Every quantitative formal-paper claim is mapped to hash-verified frozen evidence and an asset.",
    )

    source_ok = (
        source.get("all_checks_passed") is True
        and source.get("citation_count", 0) == source.get("bibliography_entry_count", -1)
    )
    add_check(
        checks,
        "source_and_citation_validation",
        source_ok and references.get("all_checks_passed") is True,
        "All cited references are defined, used, and structurally complete.",
    )

    add_check(
        checks,
        "generated_asset_determinism",
        asset_determinism.get("all_hashes_match") is True
        and asset_determinism.get("output_count", 0) >= 20,
        "Two independent paper-asset generations have identical asset and manifest hashes.",
    )

    taxonomy_and_boundary_ok = (
        "No taxonomy-stratified analysis is reported" in all_sections
        and "does not support a general MetaShift" in frontmatter
        and "not a calibrated" in all_sections
    )
    add_check(
        checks,
        "scientific_and_human_boundaries",
        taxonomy_and_boundary_ok,
        "The report preserves no-superiority, no-causal-instrument, and no-calibrated-real-interval boundaries.",
    )

    rendered_pages = sorted(RENDER_DIR.glob("page-*.png"))
    pdf_hash = sha256(FINAL_PDF_PATH) if FINAL_PDF_PATH.is_file() else ""
    pdf_ok = (
        FINAL_PDF_PATH.is_file()
        and FINAL_PDF_PATH.stat().st_size > 100_000
        and FINAL_PDF_PATH.read_bytes()[:5] == b"%PDF-"
        and build.get("pdf") == "paper/latex/MetaShift_Bench_Yau_2026.pdf"
        and build.get("pdf_bytes") == FINAL_PDF_PATH.stat().st_size
        and build.get("pdf_sha256") == pdf_hash
        and build.get("rendered_page_count") == len(rendered_pages)
        and len(rendered_pages) > 1
        and build.get("overfull_hbox_warnings") == 0
    )
    add_check(
        checks,
        "compiled_pdf_and_rendered_page_integrity",
        pdf_ok,
        "The final PDF is nonempty, hash-recorded, rendered, and free of overfull boxes.",
    )

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "formal_report": "paper/latex/MetaShift_Bench_Yau_2026.pdf",
        "frozen_evidence": frozen,
        "source_word_count_estimate": source_word_count(),
        "compiled_pdf": {
            "bytes": FINAL_PDF_PATH.stat().st_size if FINAL_PDF_PATH.is_file() else 0,
            "sha256": pdf_hash,
            "rendered_page_count": len(rendered_pages),
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
