"""Build the formal report, render every page, and record build diagnostics."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
BUILD_DIR = LATEX_ROOT / "build"
RENDER_DIR = LATEX_ROOT / "rendered_pages"
PDF_PATH = BUILD_DIR / "main.pdf"
FINAL_PDF = LATEX_ROOT / "MetaShift_Bench_Yau_2026.pdf"
REPORT_PATH = LATEX_ROOT / "generated" / "build_report.json"


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def require_command(name: str) -> str:
    location = shutil.which(name)
    if location is None:
        raise RuntimeError(f"Required command is unavailable: {name}")
    return location


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_render_dir() -> None:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    for page in RENDER_DIR.glob("page-*.png"):
        page.unlink()


def main() -> None:
    pdflatex = require_command("pdflatex")
    bibtex = require_command("bibtex")
    pdftoppm = require_command("pdftoppm")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    run([sys.executable, "scripts/generate_paper_assets.py", "--write"], LATEX_ROOT)
    run(
        [sys.executable, "scripts/verify_claim_ledger.py", "--require-assets"],
        LATEX_ROOT,
    )
    run([sys.executable, "scripts/verify_paper_source.py"], LATEX_ROOT)
    run([sys.executable, "scripts/verify_references.py"], LATEX_ROOT)
    latex_command = [
        pdflatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory=build",
        "main.tex",
    ]
    run(latex_command, LATEX_ROOT)
    run([bibtex, "build/main"], LATEX_ROOT)
    run(latex_command, LATEX_ROOT)
    run(latex_command, LATEX_ROOT)

    if not PDF_PATH.is_file() or PDF_PATH.stat().st_size == 0:
        raise RuntimeError("LaTeX did not produce a nonempty PDF.")
    log_path = BUILD_DIR / "main.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    overfull = log.count("Overfull \\hbox")
    if overfull:
        raise RuntimeError(f"LaTeX log contains {overfull} overfull hbox warnings.")

    clean_render_dir()
    run(
        [pdftoppm, "-png", "-r", "144", str(PDF_PATH), str(RENDER_DIR / "page")],
        LATEX_ROOT,
    )
    pages = sorted(RENDER_DIR.glob("page-*.png"))
    if not pages:
        raise RuntimeError("PDF page rendering did not produce page images.")
    shutil.copy2(PDF_PATH, FINAL_PDF)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_git_commit": git_commit(),
        "pdf": str(FINAL_PDF.relative_to(ROOT)).replace("\\", "/"),
        "pdf_bytes": FINAL_PDF.stat().st_size,
        "pdf_sha256": sha256(FINAL_PDF),
        "rendered_page_count": len(pages),
        "overfull_hbox_warnings": overfull,
        "frozen_evidence_summary": "configs/current_evidence_summary_v2.json",
        "build_commands": [
            "generate_paper_assets --write",
            "verify_claim_ledger --require-assets",
            "verify_paper_source",
            "verify_references",
            "pdflatex, bibtex, pdflatex, pdflatex",
            "pdftoppm -png -r 144",
            "verify_formal_report",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    run([sys.executable, "scripts/verify_formal_report.py"], LATEX_ROOT)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
