"""Reject Type 3 or unembedded fonts in formal-paper PDF outputs."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
FINAL_PDF = LATEX_ROOT / "MetaShift_Bench_Yau_2026.pdf"
FIGURES_DIR = LATEX_ROOT / "generated" / "figures"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "font_audit.json"
EMBEDDING_PATTERN = re.compile(
    r"\s(?P<embedded>yes|no)\s+(?P<subset>yes|no)\s+(?P<unicode>yes|no)"
    r"\s+\d+\s+\d+\s*$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit final-report and generated-figure fonts with pdffonts."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        action="append",
        default=[],
        help="PDF to audit; repeat to audit multiple paths.",
    )
    parser.add_argument(
        "--include-generated-figures",
        action="store_true",
        help="Audit all generated vector figures in addition to explicitly requested PDFs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON report path, relative to the LaTeX project by default.",
    )
    return parser.parse_args()


def resolve_from_latex(path: Path) -> Path:
    return path if path.is_absolute() else LATEX_ROOT / path


def audit_pdf(pdffonts: str, path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        return {
            "path": str(path),
            "font_count": 0,
            "type3_fonts": [],
            "unembedded_fonts": [],
            "error": "missing_or_empty_pdf",
        }
    process = subprocess.run(
        [pdffonts, str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = process.stdout.splitlines()
    separator_index = next(
        (index for index, line in enumerate(lines) if line.strip().startswith("---")),
        None,
    )
    entries = (
        [line for line in lines[separator_index + 1 :] if line.strip()]
        if separator_index is not None
        else []
    )
    type3_fonts = [line.strip() for line in entries if re.search(r"\btype\s*3\b", line, re.I)]
    unembedded_fonts = []
    for line in entries:
        match = EMBEDDING_PATTERN.search(line)
        if match is None:
            unembedded_fonts.append(line.strip())
        elif match.group("embedded").casefold() != "yes":
            unembedded_fonts.append(line.strip())
    return {
        "path": str(path),
        "font_count": len(entries),
        "type3_fonts": type3_fonts,
        "unembedded_fonts": unembedded_fonts,
    }


def main() -> None:
    args = parse_args()
    pdffonts = shutil.which("pdffonts")
    if pdffonts is None:
        raise RuntimeError("Required command is unavailable: pdffonts")
    output_path = resolve_from_latex(args.output)
    requested = [resolve_from_latex(path) for path in args.pdf]
    figures = sorted(FIGURES_DIR.glob("*.pdf"))
    targets = (
        [*requested, *figures]
        if requested and args.include_generated_figures
        else requested or [FINAL_PDF, *figures]
    )
    audits = [audit_pdf(pdffonts, path) for path in targets]
    violations = [
        {
            "path": audit["path"],
            "issue": issue,
            "fonts": audit[key],
        }
        for audit in audits
        for issue, key in (
            ("missing_or_empty_pdf", "error"),
            ("type3_fonts", "type3_fonts"),
            ("unembedded_fonts", "unembedded_fonts"),
        )
        if audit.get(key)
    ]
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "tool": "pdffonts",
        "pdf_count": len(audits),
        "font_count": sum(int(audit["font_count"]) for audit in audits),
        "all_checks_passed": not violations,
        "audits": audits,
        "violations": violations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
