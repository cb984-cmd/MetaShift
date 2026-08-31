"""Check formal-paper source structure, citations, generated inputs, and boundaries."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
MAIN_PATH = LATEX_ROOT / "main.tex"
BIB_PATH = LATEX_ROOT / "references.bib"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "paper_source_validation.json"
REQUIRED_INPUTS = (
    "sections/cover",
    "sections/frontmatter",
    "sections/introduction",
    "sections/related_work",
    "sections/data",
    "sections/methods",
    "sections/experiments",
    "sections/results",
    "sections/discussion",
    "sections/limitations",
    "sections/conclusion",
    "sections/acknowledgements",
)
REQUIRED_SECTION_TITLES = (
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
REQUIRED_GENERATED_INPUTS = (
    "generated/evidence_macros",
    "generated/tables/table_data_summary",
    "generated/tables/table_synthetic_metrics",
    "generated/tables/table_paired_bootstrap",
    "generated/tables/table_real_audit",
    "generated/tables/table_interval_coverage",
    "generated/tables/table_reproducibility",
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
    sources = {}
    for path in [LATEX_ROOT / "metadata.tex", MAIN_PATH, *(LATEX_ROOT / "sections").glob("*.tex")]:
        if path.is_file():
            sources[str(path.relative_to(LATEX_ROOT)).replace("\\", "/")] = path.read_text(
                encoding="utf-8"
            )
    return sources


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    sources = read_tex_sources()
    main = sources.get("main.tex", "")
    combined = "\n".join(sources.values())
    violations: list[dict[str, object]] = []

    expected_input_positions = []
    for required in REQUIRED_INPUTS:
        token = rf"\input{{{required}}}"
        position = main.find(token)
        if position == -1:
            violations.append({"issue": "missing_required_input", "input": required})
        else:
            expected_input_positions.append((required, position))
    if expected_input_positions != sorted(expected_input_positions, key=lambda item: item[1]):
        violations.append({"issue": "report_sections_are_out_of_order"})
    if main.find(r"\bibliography{references}") < main.find(r"\input{sections/conclusion}"):
        violations.append({"issue": "references_do_not_follow_main_text"})
    if main.find(r"\input{sections/acknowledgements}") < main.find(
        r"\bibliography{references}"
    ):
        violations.append({"issue": "acknowledgements_do_not_follow_references"})

    for title in REQUIRED_SECTION_TITLES:
        if rf"\section{{{title}}}" not in combined:
            violations.append({"issue": "missing_section_title", "title": title})
    for generated_input in REQUIRED_GENERATED_INPUTS:
        if rf"\input{{{generated_input}}}" not in combined:
            violations.append(
                {"issue": "missing_generated_input", "input": generated_input}
            )
    for macro in REQUIRED_MACRO_USAGES:
        if macro not in combined:
            violations.append({"issue": "missing_evidence_macro", "macro": macro})

    lower = combined.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lower:
            violations.append({"issue": "forbidden_claim_phrase", "phrase": phrase})
    if "human completion required" not in lower:
        violations.append({"issue": "human_completion_boundary_missing"})
    if "no taxonomy-stratified analysis is reported" not in lower:
        violations.append({"issue": "taxonomy_human_block_missing"})

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
    if not cited:
        violations.append({"issue": "no_citations_found"})

    generated_files = [
        LATEX_ROOT / "generated" / "evidence_macros.tex",
        *(LATEX_ROOT / "generated" / "tables").glob("*.tex"),
        *(LATEX_ROOT / "generated" / "figures").glob("*.pdf"),
    ]
    missing_generated_files = [
        str(path.relative_to(LATEX_ROOT)).replace("\\", "/")
        for path in generated_files
        if not path.is_file() or path.stat().st_size == 0
    ]
    if missing_generated_files:
        violations.append(
            {"issue": "missing_or_empty_generated_file", "files": missing_generated_files}
        )

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_files": sorted(sources),
        "citation_count": len(cited),
        "bibliography_entry_count": len(defined),
        "all_checks_passed": not violations,
        "violations": violations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if not violations else 1)


if __name__ == "__main__":
    main()
