"""Build the formal report from a clean set of known intermediates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from matplotlib import image as mpl_image


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
BUILD_DIR = LATEX_ROOT / "build"
RENDER_DIR = LATEX_ROOT / "rendered_pages"
QA_CROP_DIR = LATEX_ROOT / "qa_page_crops"
PDF_PATH = BUILD_DIR / "main.pdf"
NAMED_BUILD_PDF = BUILD_DIR / "MetaShift_Bench_Yau_2026.pdf"
FINAL_PDF = LATEX_ROOT / "MetaShift_Bench_Yau_2026.pdf"
REPORT_PATH = LATEX_ROOT / "generated" / "build_report.json"
CLEAN_BUILD_PATH = LATEX_ROOT / "generated" / "clean_build_record.json"
VISUAL_PREFLIGHT_PATH = LATEX_ROOT / "generated" / "visual_preflight.json"
FONT_AUDIT_PATH = LATEX_ROOT / "generated" / "font_audit.json"
FIGURE_LAYOUT_QA_PATH = LATEX_ROOT / "generated" / "figure_layout_qa.json"
V05_FIGURE_LAYOUT_QA_PATH = LATEX_ROOT / "generated" / "v05_figure_layout_qa.json"
FINAL_FIGURE_QA_PATH = LATEX_ROOT / "generated" / "final_figure_placement_qa.json"
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
FINAL_PRINT_WIDTH_PT = 453.54
FIGURE_CAPTION_MARKERS = {
    "fig_v05_answerability_frontier.png": (
        "heldout",
        "finitepolicy",
        "answerability",
        "frontiers",
        "information",
        "channel",
    ),
    "fig_v05_structural_margin.png": (
        "normalized",
        "structuralmargin",
        "phase",
        "diagram",
        "certificate",
        "coverage",
    ),
    "fig_v05_risk_coverage.png": (
        "riskcoverage",
        "positions",
        "predeclared",
        "heldout",
        "policies",
        "certificate",
    ),
    "fig_v05_certificate_validity.png": (
        "supplementary",
        "certificatevalidity",
        "summary",
        "observed",
        "errors",
        "bounded",
        "generator",
    ),
    "fig_v05_failure_mode_map.png": (
        "retained",
        "failure",
        "signal",
        "nominal",
        "donor",
        "participation",
    ),
    "fig_v05_scope_boundary.png": (
        "structural",
        "answerability",
        "boundary",
        "heldout",
        "margin",
        "certificate",
        "forcedcomparative",
    ),
    "fig_stable_synthetic_example.pdf": (
        "deterministic",
        "stableregime",
        "synthetic",
        "illustration",
        "injected",
        "effect",
    ),
    "fig_audit_pipeline.pdf": (
        "aqs",
        "deploymentaudit",
        "workflow",
        "shared",
        "preprocessing",
        "observational",
    ),
    "fig_donor_construction.pdf": (
        "physicalsite",
        "donor",
        "construction",
        "availability",
        "frozen",
        "88101",
        "inventory",
    ),
    "fig_window_protocol.pdf": (
        "calibration",
        "displayed",
        "preanchor",
        "windows",
        "overlap",
        "postanchor",
    ),
    "fig_split_integrity.pdf": (
        "connectedcomponent",
        "split",
        "integrity",
        "stableregime",
        "physical",
        "input",
    ),
    "fig_synthetic_metrics.pdf": (
        "heldout",
        "stableregime",
        "comparison",
        "crosssite",
        "methods",
        "regional",
    ),
    "fig_perturbation_metrics.pdf": (
        "perturbationfamily",
        "comparison",
        "localeffect",
        "mae",
        "macrof1",
    ),
    "fig_cross_site_scope_metrics.pdf": (
        "crosssite",
        "targetonly",
        "independent",
        "heldout",
        "stableregime",
        "scope",
        "task",
    ),
    "fig_paired_bootstrap.pdf": ("paired", "eventcluster", "bootstrap", "intervals"),
    "fig_event_accounting.pdf": (
        "aqs",
        "audit",
        "accounting",
        "metadata",
        "anchors",
        "donorinsufficient",
    ),
    "fig_placebos.pdf": (
        "supplementary",
        "timeplacebo",
        "availability",
        "raw",
        "withinevent",
        "placeboscore",
        "distribution",
    ),
    "fig_interval_coverage.pdf": ("heldout", "synthetic", "coverage", "width"),
    "fig_screening_sensitivity.pdf": ("predeclared", "evidencetier", "sensitivity"),
    "fig_external_evidence.pdf": ("contextualevidence", "ladders", "unavailable"),
    "fig_case_studies_complete.pdf": (
        "deterministically",
        "selected",
        "complete",
        "representative",
    ),
    "fig_case_studies_abstention.pdf": (
        "deterministic",
        "representative",
        "abstention",
    ),
    "fig_applicability_map.pdf": ("claimboundary", "matrix", "aqs", "audit"),
    "fig_anchor_concentration.pdf": (
        "descriptive",
        "concentration",
        "reported",
        "88101",
        "metadata",
        "anchors",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the formal MetaShift-Bench report.")
    parser.add_argument(
        "--skip-final-compliance",
        action="store_true",
        help=(
            "Compatibility option allowed only with --staged-only; final builds always "
            "run final compliance before publishing the canonical PDF."
        ),
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


def validate_build_options(args: argparse.Namespace) -> None:
    if args.skip_final_compliance and not args.staged_only:
        raise ValueError(
            "--skip-final-compliance is only permitted with --staged-only; "
            "a final build must pass final compliance before publication."
        )


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def require_command(name: str) -> str:
    location = shutil.which(name)
    if location is None:
        raise RuntimeError(f"Required command is unavailable: {name}")
    return location


def require_bbox_pdftotext(pdfinfo: str) -> str:
    """Find a pdftotext executable that can emit word bounding boxes."""

    pdfinfo_path = Path(pdfinfo)
    candidates = [
        pdfinfo_path.with_name("pdftotext" + pdfinfo_path.suffix),
        Path(require_command("pdftotext")),
    ]
    checked: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in checked or not resolved.is_file():
            continue
        checked.add(resolved)
        completed = subprocess.run(
            [str(resolved), "-h"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if "-bbox" in completed.stdout:
            return str(resolved)
    raise RuntimeError(
        "Required command is unavailable: a pdftotext executable with -bbox support."
    )


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


def require_clean_final_worktree(
    source_worktree_status: list[str], *, staged_only: bool
) -> None:
    if source_worktree_status and not staged_only:
        raise RuntimeError(
            "A final build requires a clean Git worktree at build start. "
            "Commit or resolve report-source changes before publishing."
        )


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
    for dpi in (150, 300):
        for directory_name in ("pages", "crops"):
            directory = QA_CROP_DIR / f"{directory_name}-{dpi}"
            directory.mkdir(parents=True, exist_ok=True)
            for page in directory.glob("*.png"):
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


def pdf_page_size_points(pdfinfo: str, path: Path) -> tuple[float, float]:
    page_size = pdf_info(pdfinfo, path).get("Page size", "")
    match = re.search(r"([0-9.]+)\s+x\s+([0-9.]+)\s+pts", page_size)
    if match is None:
        raise RuntimeError(f"Could not determine PDF page size for {path}: {page_size}")
    return float(match.group(1)), float(match.group(2))


def source_figure_dimensions(pdfinfo: str, path: Path) -> tuple[float, float]:
    """Return an aspect-preserving source size for vector or raster figures."""

    if path.suffix.casefold() == ".png":
        width_px, height_px = png_dimensions(path)
        return float(width_px), float(height_px)
    return pdf_page_size_points(pdfinfo, path)


def render_pages(
    pdftoppm: str, pdf: Path, directory: Path, dpi: int
) -> list[tuple[Path, int, int]]:
    directory.mkdir(parents=True, exist_ok=True)
    run([pdftoppm, "-png", "-r", str(dpi), str(pdf), str(directory / "page")], LATEX_ROOT)
    pages = sorted(directory.glob("page-*.png"))
    if not pages:
        raise RuntimeError(f"PDF rendering produced no pages at {dpi} DPI.")
    records = []
    for page in pages:
        width, height = png_dimensions(page)
        if width < 500 or height < 500 or page.stat().st_size == 0:
            raise RuntimeError(f"Rendered page failed visual preflight: {page}")
        records.append((page, width, height))
    return records


def _normalized_word(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def extract_caption_locations(
    pdftotext: str, pdf: Path
) -> dict[str, dict[str, float | int]]:
    """Locate each final-PDF caption from Poppler word coordinates."""

    output = subprocess.check_output(
        [pdftotext, "-bbox", str(pdf), "-"],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        root = ET.fromstring(output)
    except ET.ParseError as error:
        raise RuntimeError("Could not parse pdftotext bounding-box output.") from error
    pages = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "page"]
    matches: dict[str, dict[str, float | int]] = {}
    for page_number, page in enumerate(pages, start=1):
        words = [
            (
                _normalized_word(word.text or ""),
                float(word.attrib["yMin"]),
                float(word.attrib["yMax"]),
            )
            for word in page.iter()
            if word.tag.rsplit("}", 1)[-1] == "word" and (word.text or "").strip()
        ]
        normalized_words = [word[0] for word in words]
        for figure_name, markers in FIGURE_CAPTION_MARKERS.items():
            if figure_name in matches:
                continue
            for index, (token, y_min, y_max) in enumerate(words):
                if token != "figure":
                    continue
                nearby = set(normalized_words[index + 1 : index + 56])
                if all(marker in nearby for marker in markers):
                    matches[figure_name] = {
                        "page": page_number,
                        "caption_y_min_pt": y_min,
                        "caption_y_max_pt": y_max,
                        "page_width_pt": float(page.attrib["width"]),
                        "page_height_pt": float(page.attrib["height"]),
                    }
                    break
    missing = sorted(set(FIGURE_CAPTION_MARKERS) - set(matches))
    if missing:
        raise RuntimeError(
            "Could not locate final-PDF captions for: " + ", ".join(missing)
        )
    return matches


def crop_figure_from_page(
    source: Path,
    destination: Path,
    *,
    page_width_pt: float,
    page_height_pt: float,
    caption_y_min_pt: float,
    figure_width_pt: float,
    figure_height_pt: float,
) -> tuple[int, int]:
    image = mpl_image.imread(source)
    image_height, image_width = image.shape[:2]
    left_pt = max(0.0, (page_width_pt - figure_width_pt) / 2.0 - 18.0)
    right_pt = min(page_width_pt, (page_width_pt + figure_width_pt) / 2.0 + 18.0)
    top_pt = max(0.0, caption_y_min_pt - figure_height_pt - 14.0)
    bottom_pt = min(page_height_pt, caption_y_min_pt + 54.0)
    left = max(0, int(round(left_pt / page_width_pt * image_width)))
    right = min(image_width, int(round(right_pt / page_width_pt * image_width)))
    top = max(0, int(round(top_pt / page_height_pt * image_height)))
    bottom = min(image_height, int(round(bottom_pt / page_height_pt * image_height)))
    if right - left < 200 or bottom - top < 100:
        raise RuntimeError(
            f"Final-page crop for {source.name} is unexpectedly small: "
            f"{right - left}x{bottom - top} pixels."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    mpl_image.imsave(destination, image[top:bottom, left:right])
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"Failed to write final-page crop: {destination}")
    return png_dimensions(destination)


def write_final_figure_placement_qa(
    pdftoppm: str, pdftotext: str, pdfinfo: str, pdf: Path
) -> dict[str, object]:
    layout_records: dict[str, dict[str, object]] = {}
    for layout_path in (FIGURE_LAYOUT_QA_PATH, V05_FIGURE_LAYOUT_QA_PATH):
        if not layout_path.is_file():
            raise FileNotFoundError(f"Missing source geometry record: {layout_path}")
        layout_qa = json.loads(layout_path.read_text(encoding="utf-8"))
        for record in layout_qa.get("figures", []):
            if not isinstance(record, dict) or not isinstance(record.get("figure"), str):
                continue
            figure = str(record["figure"])
            if figure in layout_records:
                raise RuntimeError(f"Duplicate source geometry record: {figure}")
            layout_records[figure] = record
    missing_layouts = sorted(set(FIGURE_CAPTION_MARKERS) - set(layout_records))
    if missing_layouts:
        raise RuntimeError(
            "Missing source geometry records for: " + ", ".join(missing_layouts)
        )
    caption_locations = extract_caption_locations(pdftotext, pdf)
    rendered_by_dpi = {
        dpi: render_pages(pdftoppm, pdf, QA_CROP_DIR / f"pages-{dpi}", dpi)
        for dpi in (150, 300)
    }
    figure_records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for figure_name in FIGURE_CAPTION_MARKERS:
        location = caption_locations[figure_name]
        source_figure = LATEX_ROOT / "generated" / "figures" / figure_name
        source_width_pt, source_height_pt = source_figure_dimensions(pdfinfo, source_figure)
        printed_width_pt = float(layout_records[figure_name]["final_print_width_pt"])
        printed_height_pt = source_height_pt / source_width_pt * printed_width_pt
        page_number = int(location["page"])
        dpi_records: dict[str, object] = {}
        for dpi, pages in rendered_by_dpi.items():
            if page_number > len(pages):
                failures.append(
                    {
                        "issue": "caption_page_outside_rendered_page_range",
                        "figure": figure_name,
                        "dpi": dpi,
                    }
                )
                continue
            page_path, _, _ = pages[page_number - 1]
            crop_path = (
                QA_CROP_DIR
                / f"crops-{dpi}"
                / f"{Path(figure_name).stem}-page-{page_number:02d}.png"
            )
            crop_width, crop_height = crop_figure_from_page(
                page_path,
                crop_path,
                page_width_pt=float(location["page_width_pt"]),
                page_height_pt=float(location["page_height_pt"]),
                caption_y_min_pt=float(location["caption_y_min_pt"]),
                figure_width_pt=printed_width_pt,
                figure_height_pt=printed_height_pt,
            )
            dpi_records[str(dpi)] = {
                "path": str(crop_path.relative_to(ROOT)).replace("\\", "/"),
                "width_px": crop_width,
                "height_px": crop_height,
                "bytes": crop_path.stat().st_size,
            }
        figure_records.append(
            {
                "figure": figure_name,
                "page": page_number,
                "caption_y_min_pt": round(float(location["caption_y_min_pt"]), 2),
                "final_print_width_pt": round(printed_width_pt, 2),
                "final_print_height_pt": round(printed_height_pt, 2),
                "source_layout_checks_passed": layout_records[figure_name].get(
                    "all_checks_passed"
                )
                is True,
                "page_crops": dpi_records,
                "visual_inspection": "150_and_300_dpi_crops_rendered",
            }
        )
    expected_crops = len(FIGURE_CAPTION_MARKERS) * 2
    actual_crops = sum(len(record["page_crops"]) for record in figure_records)
    report = {
        "schema_version": 1,
        "source_pdf": str(pdf.relative_to(ROOT)).replace("\\", "/"),
        "source_pdf_sha256": sha256(pdf),
        "required_figure_count": len(FIGURE_CAPTION_MARKERS),
        "crop_dpi": [150, 300],
        "rendered_page_counts": {
            str(dpi): len(pages) for dpi, pages in rendered_by_dpi.items()
        },
        "expected_crop_count": expected_crops,
        "actual_crop_count": actual_crops,
        "figures": figure_records,
        "visual_overflow_failures": len(failures),
        "failures": failures,
        "all_checks_passed": (
            not failures
            and actual_crops == expected_crops
            and all(bool(record["source_layout_checks_passed"]) for record in figure_records)
        ),
    }
    write_json(FINAL_FIGURE_QA_PATH, report)
    return report


def copy_pdf(source: Path, destination: Path) -> None:
    try:
        shutil.copy2(source, destination)
    except PermissionError as error:
        raise RuntimeError(
            "The canonical final PDF is locked by another application. Close the "
            "viewer for paper\\latex\\MetaShift_Bench_Yau_2026.pdf and rebuild."
        ) from error


def publish_verified_pdf(candidate: Path) -> None:
    """Atomically publish a candidate only after its staged compliance check passed."""

    candidate_hash = sha256(candidate)
    previous_pdf: Path | None = None
    previous_hash = ""
    if FINAL_PDF.is_file():
        with tempfile.NamedTemporaryFile(
            dir=BUILD_DIR,
            prefix=".previous_canonical_",
            suffix=".pdf",
            delete=False,
        ) as temporary:
            previous_pdf = Path(temporary.name)
        copy_pdf(FINAL_PDF, previous_pdf)
        previous_hash = sha256(previous_pdf)

    published = False
    try:
        copy_pdf(candidate, FINAL_PDF)
        published = True
        if sha256(FINAL_PDF) != candidate_hash:
            raise RuntimeError("Canonical final PDF differs from the verified candidate.")
        run([sys.executable, "scripts/verify_formal_report.py"], LATEX_ROOT)
    except Exception:
        if published:
            if not FINAL_PDF.is_file() or sha256(FINAL_PDF) != candidate_hash:
                raise RuntimeError(
                    "Cannot safely restore the previous canonical PDF because it changed "
                    "after the candidate publication attempt."
                )
            if previous_pdf is None:
                FINAL_PDF.unlink()
            else:
                copy_pdf(previous_pdf, FINAL_PDF)
                if sha256(FINAL_PDF) != previous_hash:
                    raise RuntimeError("Restored canonical PDF does not match its backup.")
        raise
    finally:
        if previous_pdf is not None and previous_pdf.is_file():
            previous_pdf.unlink()


def main() -> None:
    args = parse_args()
    validate_build_options(args)
    pdflatex = require_command("pdflatex")
    bibtex = require_command("bibtex")
    pdftoppm = require_command("pdftoppm")
    pdfinfo = require_command("pdfinfo")
    pdftotext = require_bbox_pdftotext(pdfinfo)
    source_commit = git_commit()
    source_worktree_status = git_worktree_status()
    require_clean_final_worktree(
        source_worktree_status, staged_only=args.staged_only
    )
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

    run(
        [
            sys.executable,
            "scripts/verify_v05_frozen_result_provenance.py",
            "--verify-results",
        ],
        ROOT,
    )
    run(
        [sys.executable, "scripts/verify_v05_answerability_asset_determinism.py"],
        LATEX_ROOT,
    )
    run(
        [sys.executable, "scripts/verify_v05_answerability_assets.py"],
        LATEX_ROOT,
    )
    run(
        [sys.executable, "scripts/verify_v05_claim_ledger.py", "--require-assets"],
        LATEX_ROOT,
    )
    run([sys.executable, "scripts/generate_paper_assets.py", "--write"], LATEX_ROOT)
    run([sys.executable, "scripts/verify_figures.py"], LATEX_ROOT)
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

    copy_pdf(PDF_PATH, NAMED_BUILD_PDF)
    staged_only = args.staged_only
    audited_pdf = NAMED_BUILD_PDF

    rendered_pages = render_pages(pdftoppm, audited_pdf, RENDER_DIR, 144)
    page_records = []
    for page, width, height in rendered_pages:
        page_records.append(
            {
                "page": page.name,
                "bytes": page.stat().st_size,
                "width_px": width,
                "height_px": height,
            }
        )
    final_figure_qa = write_final_figure_placement_qa(
        pdftoppm, pdftotext, pdfinfo, audited_pdf
    )
    if final_figure_qa.get("all_checks_passed") is not True:
        raise RuntimeError("Final-page figure crop QA did not pass.")
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
            "high_resolution_page_renders": final_figure_qa["rendered_page_counts"],
            "final_figure_placement_qa": str(
                FINAL_FIGURE_QA_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
        },
    )
    font_command = [
        sys.executable,
        "scripts/verify_pdf_fonts.py",
        "--pdf",
        "build/MetaShift_Bench_Yau_2026.pdf",
        "--include-generated-figures",
    ]
    run(font_command, LATEX_ROOT)

    metadata = pdf_info(pdfinfo, audited_pdf)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_git_commit": source_commit,
        "source_worktree_clean_at_start": not source_worktree_status,
        "source_worktree_status_at_start": source_worktree_status,
        "build_mode": "staged_only" if staged_only else "final",
        "build_pdf": str(NAMED_BUILD_PDF.relative_to(ROOT)).replace("\\", "/"),
        "candidate_pdf": str(NAMED_BUILD_PDF.relative_to(ROOT)).replace("\\", "/"),
        "candidate_pdf_sha256": sha256(NAMED_BUILD_PDF),
        "final_pdf": (
            None
            if staged_only
            else str(FINAL_PDF.relative_to(ROOT)).replace("\\", "/")
        ),
        "pdf_bytes": audited_pdf.stat().st_size,
        "pdf_sha256": sha256(audited_pdf),
        "build_pdf_sha256": sha256(NAMED_BUILD_PDF),
        "rendered_page_count": len(rendered_pages),
        "overfull_hbox_warnings": overfull,
        "pdf_metadata": {
            "Title": metadata.get("Title", ""),
            "Author": metadata.get("Author", ""),
            "Subject": metadata.get("Subject", ""),
        },
        "frozen_evidence_summary": "configs/current_evidence_summary_v2.json",
        "frozen_v05_result_manifest": "configs/v05_frozen_result_manifest.json",
        "clean_build_record": str(CLEAN_BUILD_PATH.relative_to(ROOT)).replace("\\", "/"),
        "visual_preflight": str(VISUAL_PREFLIGHT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "final_figure_placement_qa": str(
            FINAL_FIGURE_QA_PATH.relative_to(ROOT)
        ).replace("\\", "/"),
        "font_audit": str(FONT_AUDIT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "build_commands": [
            "verify_v05_frozen_result_provenance --verify-results",
            "verify_v05_answerability_asset_determinism",
            "verify_v05_answerability_assets",
            "verify_v05_claim_ledger --require-assets",
            "generate_paper_assets --write",
            "verify_figures",
            "verify_claim_ledger --require-assets",
            "verify_paper_source",
            "verify_references",
            "verify_paper_asset_determinism",
            "pdflatex, bibtex, pdflatex, pdflatex",
            "pdftoppm -png -r 144, 150, 300",
            "pdftotext -bbox for figure-page crop locations",
            "verify_pdf_fonts",
        ]
        + (
            []
            if staged_only
            else [
                "verify_formal_report --candidate-pdf build/MetaShift_Bench_Yau_2026.pdf",
                "verify_formal_report after transactional canonical publication",
            ]
        ),
    }
    write_json(REPORT_PATH, report)
    if not staged_only:
        run(
            [
                sys.executable,
                "scripts/verify_formal_report.py",
                "--candidate-pdf",
                "build/MetaShift_Bench_Yau_2026.pdf",
            ],
            LATEX_ROOT,
        )
        publish_verified_pdf(NAMED_BUILD_PDF)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
