"""Verify that v0.5 manuscript assets remain receipt-bound and presentation-safe."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


LATEX_ROOT = Path(__file__).resolve().parents[1]
ROOT = LATEX_ROOT.parents[1]
GENERATED = LATEX_ROOT / "generated"
MANIFEST_PATH = GENERATED / "v05_answerability_asset_manifest.json"
LAYOUT_PATH = GENERATED / "v05_figure_layout_qa.json"
SOURCE_RECEIPT_PATH = ROOT / "artifacts" / "v05_answerability_frontier" / "v05_execution_receipt.json"
SOURCE_FIGURE_DIRECTORY = ROOT / "figures" / "v05_answerability_frontier"
SOURCE_FIGURE_MANIFEST = SOURCE_FIGURE_DIRECTORY / "v05_figure_manifest.json"
FROZEN_RESULT_MANIFEST = ROOT / "configs" / "v05_frozen_result_manifest.json"
OUTPUT_PATH = GENERATED / "v05_answerability_asset_validation.json"

EXPECTED_OUTPUTS = {
    "generated/v05_answerability_macros.tex",
    "generated/v05_claim_value_manifest.json",
    "generated/tables/table_v05_frontier.tex",
    "generated/tables/table_v05_certificate.tex",
    "generated/tables/table_v05_failure_accounting.tex",
    "generated/figures/fig_v05_answerability_frontier.png",
    "generated/figures/fig_v05_structural_margin.png",
    "generated/figures/fig_v05_risk_coverage.png",
    "generated/figures/fig_v05_certificate_validity.png",
    "generated/figures/fig_v05_failure_mode_map.png",
    "generated/v05_figure_layout_qa.json",
}
EXPECTED_FIGURES = {
    "fig_v05_answerability_frontier.png": "v05_answerability_frontier.png",
    "fig_v05_structural_margin.png": "v05_structural_margin_phase_diagram.png",
    "fig_v05_risk_coverage.png": "v05_risk_coverage.png",
    "fig_v05_certificate_validity.png": "v05_certificate_validity_table.png",
    "fig_v05_failure_mode_map.png": "v05_failure_mode_map.png",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def check(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "passed": passed, "detail": detail}


def root_relative_path(relative_path: str) -> Path:
    path = (LATEX_ROOT / relative_path).resolve()
    latex_root = LATEX_ROOT.resolve()
    if path == latex_root or latex_root not in path.parents:
        raise ValueError(f"Asset path escapes LaTeX root: {relative_path}")
    return path


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    checks: list[dict[str, object]] = []

    outputs = manifest.get("outputs", [])
    output_paths = {
        str(record.get("path")): record
        for record in outputs
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    output_inventory_ok = (
        manifest.get("schema_version") == 1
        and manifest.get("protocol_id") == "v0.5-answerability-frontier"
        and manifest.get("execution_freeze_tag") == "v0.5.0-answerability-freeze"
        and manifest.get("execution_claim_tag") == "v0.5.0-answerability-execution-claim"
        and set(output_paths) == EXPECTED_OUTPUTS
    )
    checks.append(
        check(
            "asset_manifest_identity_and_inventory",
            output_inventory_ok,
            "The manuscript manifest names exactly the expected receipt-bound v0.5 assets.",
        )
    )

    output_hashes_ok = True
    output_hash_errors: list[str] = []
    for relative_path, record in output_paths.items():
        try:
            path = root_relative_path(relative_path)
        except ValueError as error:
            output_hashes_ok = False
            output_hash_errors.append(str(error))
            continue
        if (
            not path.is_file()
            or record.get("bytes") != path.stat().st_size
            or record.get("sha256") != sha256(path)
        ):
            output_hashes_ok = False
            output_hash_errors.append(relative_path)
    checks.append(
        check(
            "generated_output_hashes",
            output_hashes_ok,
            "All manuscript assets match the asset manifest."
            if output_hashes_ok
            else "Mismatched assets: " + ", ".join(output_hash_errors),
        )
    )

    receipt_hash = sha256(SOURCE_RECEIPT_PATH) if SOURCE_RECEIPT_PATH.is_file() else ""
    receipt_record = manifest.get("source_receipt", {})
    frozen_manifest = load_json(FROZEN_RESULT_MANIFEST)
    frozen_receipt = next(
        (
            record
            for record in frozen_manifest.get("artifacts", [])
            if isinstance(record, dict)
            and record.get("path")
            == "artifacts/v05_answerability_frontier/v05_execution_receipt.json"
        ),
        {},
    )
    receipt_ok = (
        receipt_record == {
            "path": "artifacts/v05_answerability_frontier/v05_execution_receipt.json",
            "sha256": receipt_hash,
        }
        and frozen_receipt.get("sha256") == receipt_hash
        and frozen_manifest.get("evidence_status") == "frozen_one_time_execution_verified"
    )
    checks.append(
        check(
            "frozen_receipt_binding",
            receipt_ok,
            "The manuscript asset chain is bound to the frozen result receipt.",
        )
    )

    source_figure_manifest = load_json(SOURCE_FIGURE_MANIFEST)
    source_figure_record = manifest.get("source_figure_manifest", {})
    figures = source_figure_manifest.get("figures", {})
    source_figure_ok = (
        source_figure_record
        == {
            "path": "figures/v05_answerability_frontier/v05_figure_manifest.json",
            "sha256": sha256(SOURCE_FIGURE_MANIFEST),
        }
        and source_figure_manifest.get("source_receipt_sha256") == receipt_hash
        and isinstance(figures, dict)
    )
    for output_name, source_name in EXPECTED_FIGURES.items():
        source = SOURCE_FIGURE_DIRECTORY / source_name
        destination = GENERATED / "figures" / output_name
        declared = figures.get(source_name, {}) if isinstance(figures, dict) else {}
        if (
            not source.is_file()
            or not destination.is_file()
            or declared.get("sha256") != sha256(source)
            or declared.get("bytes") != source.stat().st_size
            or sha256(source) != sha256(destination)
        ):
            source_figure_ok = False
    checks.append(
        check(
            "source_figure_manifest_and_copy_binding",
            source_figure_ok,
            "Every manuscript figure is byte-identical to a receipt-bound source figure.",
        )
    )

    layout = load_json(LAYOUT_PATH)
    layout_figures = {
        str(record.get("figure")): record
        for record in layout.get("figures", [])
        if isinstance(record, dict) and isinstance(record.get("figure"), str)
    }
    layout_ok = (
        layout.get("schema_version") == 1
        and layout.get("protocol_id") == "v0.5-answerability-frontier"
        and layout.get("source_receipt_sha256") == receipt_hash
        and layout.get("required_figure_count") == len(EXPECTED_FIGURES)
        and layout.get("all_checks_passed") is True
        and set(layout_figures) == set(EXPECTED_FIGURES)
        and all(
            record.get("all_checks_passed") is True
            and float(record.get("effective_print_ppi", 0)) >= 200.0
            and float(record.get("final_print_width_pt", 0)) >= 450.0
            for record in layout_figures.values()
        )
    )
    checks.append(
        check(
            "raster_figure_resolution_and_layout",
            layout_ok,
            "All five receipt-verified raster figures meet the predeclared print-resolution contract.",
        )
    )

    macro_path = GENERATED / "v05_answerability_macros.tex"
    table_paths = [
        GENERATED / "tables" / "table_v05_frontier.tex",
        GENERATED / "tables" / "table_v05_certificate.tex",
        GENERATED / "tables" / "table_v05_failure_accounting.tex",
    ]
    contents = "\n".join(
        path.read_text(encoding="utf-8") for path in [macro_path, *table_paths]
    )
    content_ok = all(
        token in contents
        for token in (
            r"\VFiveComparativeFrontierTwenty",
            r"\VFiveCertificateCoverage",
            "0.603746",
            "0.195208",
            "0.390612",
            "140,403",
            "46,080",
        )
    )
    checks.append(
        check(
            "expected_frozen_result_values_rendered",
            content_ok,
            "The report tables and macros contain the frozen primary answerability values.",
        )
    )

    report = {
        "scope": "Receipt-bound v0.5 manuscript asset validation; no execution or retuning.",
        "asset_manifest": "paper/latex/generated/v05_answerability_asset_manifest.json",
        "all_checks_passed": all(bool(item["passed"]) for item in checks),
        "checks": checks,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
