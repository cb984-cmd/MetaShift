"""Build the formal report from a clean set of known intermediates."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
BUILD_DIR = LATEX_ROOT / "build"
RENDER_DIR = LATEX_ROOT / "rendered_pages"
PDF_PATH = BUILD_DIR / "main.pdf"
NAMED_BUILD_PDF = BUILD_DIR / "MetaShift_Bench_Yau_2026.pdf"
FINAL_PDF = LATEX_ROOT / "MetaShift_Bench_Yau_2026.pdf"
REPORT_PATH = LATEX_ROOT / "generated" / "build_report.json"
CLEAN_BUILD_PATH = LATEX_ROOT / "generated" / "clean_build_record.json"
VISUAL_PREFLIGHT_PATH = LATEX_ROOT / "generated" / "visual_preflight.json"
FONT_AUDIT_PATH = LATEX_ROOT / "generated" / "font_audit.json"
KNOWN_BUILD_OUTPUTS = (
    "main.aux",
    "main.bbl",
    "main.blg",
    "main.log",
    "main.out",
    "main.pdf",
    "main.toc",
    "main.synctex.gz",
    "main.fls",
    "main.fdb_latexmk",
    "MetaShift_Bench_Yau_2026.pdf",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the formal MetaShift-Bench report.")
    parser.add_argument(
        "--skip-final-compliance",
        action="store_true",
        help="Build and record diagnostics without invoking the final compliance handoff.",
    )
    parser.add_argument(
        "--staged-only",
        action="store_true",
        help=(
            "Validate the named build PDF without overwriting the canonical final PDF. "
            "This mode cannot pass final compliance."
        ),
    )
    return parser.parse_args()


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


def git_worktree_status() -> list[str]:
    output = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return output.splitlines()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def clean_known_build_outputs() -> list[str]:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    removed = []
    for name in KNOWN_BUILD_OUTPUTS:
        path = BUILD_DIR / name
        if path.is_file():
            path.unlink()
            removed.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    for page in RENDER_DIR.glob("page-*.png"):
        page.unlink()
        removed.append(str(page.relative_to(ROOT)).replace("\\", "/"))
    return removed


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise RuntimeError(f"Rendered page is not a valid PNG with an IHDR header: {path}")
    return struct.unpack(">II", header[16:24])


def pdf_info(pdfinfo: str, path: Path) -> dict[str, str]:
    output = subprocess.check_output(
        [pdfinfo, str(path)], text=True, encoding="utf-8", errors="replace"
    )
    return {
        key.strip(): value.strip()
        for line in output.splitlines()
        if ":" in line
        for key, value in [line.split(":", 1)]
    }


def main() -> None:
    args = parse_args()
    pdflatex = require_command("pdflatex")
    bibtex = require_command("bibtex")
    pdftoppm = require_command("pdftoppm")
    pdfinfo = require_command("pdfinfo")
    source_commit = git_commit()
    source_worktree_status = git_worktree_status()
    removed = clean_known_build_outputs()
    write_json(
        CLEAN_BUILD_PATH,
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_git_commit": source_commit,
            "source_worktree_clean_at_start": not source_worktree_status,
            "source_worktree_status_at_start": source_worktree_status,
            "build_directory": str(BUILD_DIR.relative_to(ROOT)).replace("\\", "/"),
            "removed_known_intermediates": removed,
            "known_output_names": list(KNOWN_BUILD_OUTPUTS),
            "all_known_outputs_removed_before_build": True,
        },
    )

    run([sys.executable, "scripts/generate_paper_assets.py", "--write"], LATEX_ROOT)
    run(
        [sys.executable, "scripts/verify_claim_ledger.py", "--require-assets"],
        LATEX_ROOT,
    )
    run([sys.executable, "scripts/verify_paper_source.py"], LATEX_ROOT)
    run([sys.executable, "scripts/verify_references.py"], LATEX_ROOT)
    run([sys.executable, "scripts/verify_paper_asset_determinism.py"], LATEX_ROOT)
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
    log = (
        log_path.read_text(encoding="utf-8", errors="replace")
        if log_path.is_file()
        else ""
    )
    overfull = log.count("Overfull \\hbox")
    if overfull:
        raise RuntimeError(f"LaTeX log contains {overfull} overfull hbox warnings.")
    unresolved = [
        marker
        for marker in (
            "There were undefined references",
            "There were undefined citations",
            "multiply-defined labels",
        )
        if marker in log
    ]
    if unresolved:
        raise RuntimeError(
            "LaTeX log contains unresolved references or duplicate labels: "
            + ", ".join(unresolved)
        )

    shutil.copy2(PDF_PATH, NAMED_BUILD_PDF)
    staged_only = args.staged_only
    if not staged_only:
        try:
            shutil.copy2(PDF_PATH, FINAL_PDF)
        except PermissionError as error:
            raise RuntimeError(
                "The canonical final PDF is locked by another application. Close the "
                "viewer for paper\\latex\\MetaShift_Bench_Yau_2026.pdf and rebuild."
            ) from error
        if sha256(NAMED_BUILD_PDF) != sha256(FINAL_PDF):
            raise RuntimeError("Named build PDF and final PDF differ.")
    audited_pdf = NAMED_BUILD_PDF if staged_only else FINAL_PDF

    run(
        [pdftoppm, "-png", "-r", "144", str(audited_pdf), str(RENDER_DIR / "page")],
        LATEX_ROOT,
    )
    pages = sorted(RENDER_DIR.glob("page-*.png"))
    if not pages:
        raise RuntimeError("PDF page rendering did not produce page images.")
    page_records = []
    for page in pages:
        width, height = png_dimensions(page)
        if width < 500 or height < 500 or page.stat().st_size == 0:
            raise RuntimeError(f"Rendered page failed visual preflight: {page}")
        page_records.append(
            {
                "page": page.name,
                "bytes": page.stat().st_size,
                "width_px": width,
                "height_px": height,
            }
        )
    write_json(
        VISUAL_PREFLIGHT_PATH,
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "review_type": "automated rendered-page preflight",
            "manual_review_required": True,
            "source_pdf": str(audited_pdf.relative_to(ROOT)).replace("\\", "/"),
            "page_count": len(page_records),
            "all_pages_rendered_and_nontrivial": True,
            "pages": page_records,
        },
    )
    font_command = [sys.executable, "scripts/verify_pdf_fonts.py"]
    if staged_only:
        font_command.extend(["--pdf", "build/MetaShift_Bench_Yau_2026.pdf"])
    run(font_command, LATEX_ROOT)

    metadata = pdf_info(pdfinfo, audited_pdf)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_git_commit": source_commit,
        "source_worktree_clean_at_start": not source_worktree_status,
        "source_worktree_status_at_start": source_worktree_status,
        "build_mode": "staged_only" if staged_only else "final",
        "build_pdf": str(NAMED_BUILD_PDF.relative_to(ROOT)).replace("\\", "/"),
        "final_pdf": (
            None
            if staged_only
            else str(FINAL_PDF.relative_to(ROOT)).replace("\\", "/")
        ),
        "pdf_bytes": audited_pdf.stat().st_size,
        "pdf_sha256": sha256(audited_pdf),
        "build_pdf_sha256": sha256(NAMED_BUILD_PDF),
        "rendered_page_count": len(pages),
        "overfull_hbox_warnings": overfull,
        "pdf_metadata": {
            "Title": metadata.get("Title", ""),
            "Author": metadata.get("Author", ""),
            "Subject": metadata.get("Subject", ""),
        },
        "frozen_evidence_summary": "configs/current_evidence_summary_v2.json",
        "clean_build_record": str(CLEAN_BUILD_PATH.relative_to(ROOT)).replace("\\", "/"),
        "visual_preflight": str(VISUAL_PREFLIGHT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "font_audit": str(FONT_AUDIT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "build_commands": [
            "generate_paper_assets --write",
            "verify_claim_ledger --require-assets",
            "verify_paper_source",
            "verify_references",
            "verify_paper_asset_determinism",
            "pdflatex, bibtex, pdflatex, pdflatex",
            "pdftoppm -png -r 144",
            "verify_pdf_fonts",
        ]
        + ([] if staged_only else ["verify_formal_report"]),
    }
    write_json(REPORT_PATH, report)
    if not args.skip_final_compliance and not staged_only:
        run([sys.executable, "scripts/verify_formal_report.py"], LATEX_ROOT)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
