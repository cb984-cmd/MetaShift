"""Validate the formal-paper claim ledger and generated asset references."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LATEX_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = LATEX_ROOT / "CLAIM_EVIDENCE_LEDGER.csv"
SUMMARY_PATH = ROOT / "configs" / "current_evidence_summary_v2.json"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "claim_ledger_validation.json"
CLAIM_VALUE_MANIFEST_PATH = LATEX_ROOT / "generated" / "claim_value_manifest.json"
ASSET_MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
VERIFIED_STATUS = "verified_frozen_evidence"
REQUIRED_COLUMNS = (
    "claim_id",
    "manuscript_section",
    "claim_text",
    "evidence_file",
    "evidence_version",
    "relevant_columns",
    "filters",
    "calculation",
    "generated_table_or_figure",
    "verification_status",
    "notes",
)
MANUSCRIPT_LOCATIONS = {
    "Abstract": ("sections/frontmatter.tex", r"\section*{Abstract}"),
    "Data": ("sections/data.tex", r"\section{AQS deployment audit data}"),
    "Problem": (
        "sections/problem.tex",
        r"\section{Problem formulation}",
    ),
    "Experiments": ("sections/experiments.tex", r"\section{Experimental design}"),
    "Framework": (
        "sections/framework.tex",
        r"\section{Selective audit methods}",
    ),
    "Results RQ1": (
        "sections/results.tex",
        r"\subsection{RQ3: Cross-site comparison separates the constructed task, but estimator superiority is not supported}",
    ),
    "Results RQ2": (
        "sections/results.tex",
        r"\subsection{RQ3: Cross-site comparison separates the constructed task, but estimator superiority is not supported}",
    ),
    "Results RQ3": (
        "sections/results.tex",
        r"\subsection{RQ4: A qualified AQS comparison is available for 228 of 563 anchors}",
    ),
    "Results RQ4": (
        "sections/results.tex",
        r"\subsection{RQ5: Calibration and contextual checks limit, rather than validate, real-data interpretation}",
    ),
    "Results RQ5": (
        "sections/results.tex",
        r"\subsection{RQ5: Calibration and contextual checks limit, rather than validate, real-data interpretation}",
    ),
    "Case studies": (
        "sections/case_studies.tex",
        r"\subsection{Representative AQS cases}",
    ),
    "Limitations": (
        "sections/limitations.tex",
        r"\section{Limitations}",
    ),
    "Reproducibility": (
        "sections/reproducibility.tex",
        r"\section{Reproducibility package}",
    ),
    "Conclusion": ("sections/conclusion.tex", r"\section{Conclusion}"),
    "Appendix": (
        "sections/appendix.tex",
        r"\section{Supplementary evidence and protocols}",
    ),
}
REQUIRED_CLAIM_IDS = frozenset(f"Q{index:02d}" for index in range(1, 40))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate formal-paper claim evidence and generated assets."
    )
    parser.add_argument(
        "--require-assets",
        action="store_true",
        help="Require every ledger-mapped table and figure to exist.",
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


def check_assets(
    asset_names: list[str], asset_manifest: dict[str, object]
) -> list[dict[str, str]]:
    violations = []
    manifest_outputs = {
        str(output["path"]): output
        for output in asset_manifest.get("outputs", [])
        if isinstance(output, dict) and isinstance(output.get("path"), str)
    }
    for asset_name in asset_names:
        if asset_name.startswith("table_") and asset_name.endswith(".tex"):
            path = LATEX_ROOT / "generated" / "tables" / asset_name
        elif asset_name.startswith("fig_") and asset_name.endswith(".pdf"):
            path = LATEX_ROOT / "generated" / "figures" / asset_name
        else:
            violations.append(
                {
                    "asset": asset_name,
                    "issue": "unsupported_asset_name",
                }
            )
            continue
        if not path.is_file() or path.stat().st_size == 0:
            violations.append(
                {
                    "asset": asset_name,
                    "issue": "missing_or_empty",
                }
            )
        else:
            manifest_record = manifest_outputs.get(
                str(path.relative_to(LATEX_ROOT)).replace("\\", "/")
            )
            if manifest_record is None:
                violations.append(
                    {"asset": asset_name, "issue": "missing_from_asset_manifest"}
                )
            elif sha256(path) != manifest_record.get("sha256"):
                violations.append(
                    {"asset": asset_name, "issue": "sha256_mismatch"}
                )
    return violations


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    artifact_hashes = {
        item["path"]: item["sha256"]
        for record_group in (
            "artifact_sources",
            "frozen_protocol_sources",
            "presentation_input_sources",
        )
        for item in summary.get(record_group, [])
        if isinstance(item, dict) and "path" in item and "sha256" in item
    }
    with LEDGER_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())

    schema_violations = []
    if fieldnames != REQUIRED_COLUMNS:
        schema_violations.append(
            {
                "issue": "unexpected_columns",
                "expected": list(REQUIRED_COLUMNS),
                "actual": list(fieldnames),
            }
        )
    claim_ids = [row.get("claim_id", "") for row in rows]
    if not rows:
        schema_violations.append({"issue": "empty_ledger"})
    if len(claim_ids) != len(set(claim_ids)) or any(not claim_id for claim_id in claim_ids):
        schema_violations.append({"issue": "claim_ids_not_unique_and_nonempty"})
    if set(claim_ids) != REQUIRED_CLAIM_IDS:
        schema_violations.append(
            {
                "issue": "required_claim_ids_mismatch",
                "missing": sorted(REQUIRED_CLAIM_IDS - set(claim_ids)),
                "unexpected": sorted(set(claim_ids) - REQUIRED_CLAIM_IDS),
            }
        )
    missing_fields = [
        {
            "row": index,
            "claim_id": row.get("claim_id", ""),
            "missing": [column for column in REQUIRED_COLUMNS if not row.get(column, "").strip()],
        }
        for index, row in enumerate(rows, start=2)
        if any(not row.get(column, "").strip() for column in REQUIRED_COLUMNS)
    ]
    status_violations = [
        {
            "row": index,
            "claim_id": row.get("claim_id", ""),
            "actual_status": row.get("verification_status", ""),
            "expected_status": VERIFIED_STATUS,
        }
        for index, row in enumerate(rows, start=2)
        if row.get("verification_status") != VERIFIED_STATUS
    ]
    location_violations = []
    for index, row in enumerate(rows, start=2):
        for location in (part.strip() for part in row["manuscript_section"].split(";")):
            location_record = MANUSCRIPT_LOCATIONS.get(location)
            if location_record is None:
                location_violations.append(
                    {
                        "row": index,
                        "claim_id": row["claim_id"],
                        "location": location,
                        "issue": "unknown_manuscript_location",
                    }
                )
                continue
            source_path, anchor = location_record
            manuscript_path = LATEX_ROOT / source_path
            if not manuscript_path.is_file():
                location_violations.append(
                    {
                        "row": index,
                        "claim_id": row["claim_id"],
                        "location": location,
                        "issue": "manuscript_location_file_missing",
                    }
                )
            elif anchor not in manuscript_path.read_text(encoding="utf-8"):
                location_violations.append(
                    {
                        "row": index,
                        "claim_id": row["claim_id"],
                        "location": location,
                        "issue": "manuscript_location_anchor_missing",
                    }
                )
    if CLAIM_VALUE_MANIFEST_PATH.is_file():
        claim_value_manifest = json.loads(
            CLAIM_VALUE_MANIFEST_PATH.read_text(encoding="utf-8")
        )
    else:
        claim_value_manifest = {}
    value_manifest_claims = claim_value_manifest.get("claims", {})
    claim_value_violations = []
    if claim_value_manifest.get("evidence_version") != summary["evidence_version"]:
        claim_value_violations.append(
            {
                "issue": "claim_value_manifest_evidence_version_mismatch",
                "actual": claim_value_manifest.get("evidence_version"),
            }
        )
    if set(value_manifest_claims) != set(claim_ids):
        claim_value_violations.append(
            {
                "issue": "claim_value_manifest_claim_ids_mismatch",
                "expected": sorted(claim_ids),
                "actual": sorted(value_manifest_claims),
            }
        )
    for index, row in enumerate(rows, start=2):
        value_record = value_manifest_claims.get(row["claim_id"], {})
        for fragment in value_record.get("expected_ledger_fragments", []):
            if normalize(str(fragment)) not in normalize(row["claim_text"]):
                claim_value_violations.append(
                    {
                        "row": index,
                        "claim_id": row["claim_id"],
                        "issue": "claim_text_missing_recomputed_fragment",
                        "fragment": fragment,
                    }
                )
    if ASSET_MANIFEST_PATH.is_file():
        asset_manifest = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        asset_manifest = {}
    for record in asset_manifest.get("presentation_input_sources", []):
        if isinstance(record, dict) and isinstance(record.get("path"), str) and isinstance(
            record.get("sha256"), str
        ):
            artifact_hashes[record["path"]] = record["sha256"]

    evidence_violations = []
    asset_names: list[str] = []
    unsafe_paths = ("data/raw/", "metashift-repro-venv/", "evidence_bundle/")
    for index, row in enumerate(rows, start=2):
        if row["evidence_version"] != summary["evidence_version"]:
            evidence_violations.append(
                {
                    "row": index,
                    "claim_id": row["claim_id"],
                    "issue": "evidence_version_mismatch",
                }
            )
        for relative_path in (part.strip() for part in row["evidence_file"].split(";")):
            if not relative_path:
                continue
            if relative_path.startswith(unsafe_paths):
                evidence_violations.append(
                    {
                        "row": index,
                        "claim_id": row["claim_id"],
                        "path": relative_path,
                        "issue": "unsafe_source_path",
                    }
                )
                continue
            path = ROOT / relative_path
            if not path.is_file():
                evidence_violations.append(
                    {
                        "row": index,
                        "claim_id": row["claim_id"],
                        "path": relative_path,
                        "issue": "missing_evidence_file",
                    }
                )
            else:
                expected_hash = artifact_hashes.get(relative_path)
                if expected_hash is None:
                    evidence_violations.append(
                        {
                            "row": index,
                            "claim_id": row["claim_id"],
                            "path": relative_path,
                            "issue": "source_not_hashed_in_frozen_summary",
                        }
                    )
                elif sha256(path) != expected_hash:
                    evidence_violations.append(
                        {
                            "row": index,
                            "claim_id": row["claim_id"],
                            "path": relative_path,
                            "issue": "source_hash_mismatch",
                        }
                    )
        asset_names.extend(
            part.strip()
            for part in row["generated_table_or_figure"].split(";")
            if part.strip()
        )
    asset_violations = (
        check_assets(asset_names, asset_manifest) if args.require_assets else []
    )
    checks = [
        {
            "name": "ledger_schema",
            "passed": not schema_violations,
            "violations": schema_violations,
        },
        {
            "name": "ledger_required_fields",
            "passed": not missing_fields,
            "violations": missing_fields,
        },
        {
            "name": "all_claims_marked_verified",
            "passed": not status_violations,
            "violations": status_violations,
        },
        {
            "name": "manuscript_locations",
            "passed": not location_violations,
            "violations": location_violations,
        },
        {
            "name": "claim_text_matches_recomputed_values",
            "passed": not claim_value_violations,
            "violations": claim_value_violations,
        },
        {
            "name": "frozen_evidence_inputs",
            "passed": not evidence_violations,
            "violations": evidence_violations,
        },
        {
            "name": "generated_asset_mapping",
            "passed": not asset_violations,
            "violations": asset_violations,
        },
    ]
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ledger": str(LEDGER_PATH.relative_to(ROOT)).replace("\\", "/"),
        "frozen_evidence": summary["frozen_evidence"],
        "input_summary_sha256": sha256(SUMMARY_PATH),
        "claim_count": len(rows),
        "asset_reference_count": len(asset_names),
        "verification_status_counts": dict(
            sorted(Counter(row["verification_status"] for row in rows).items())
        ),
        "all_checks_passed": all(check["passed"] for check in checks),
        "checks": checks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
