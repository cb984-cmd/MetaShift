"""Validate that every formal-report reference is cited and structurally complete."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
BIB_PATH = LATEX_ROOT / "references.bib"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "reference_validation.json"
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
URL_PATTERN = re.compile(r"https://[^\s}]+", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate formal-report references without network access."
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


def cited_keys() -> set[str]:
    sources = [
        LATEX_ROOT / "main.tex",
        LATEX_ROOT / "metadata.tex",
        *(LATEX_ROOT / "sections").glob("*.tex"),
    ]
    cited: set[str] = set()
    for source in sources:
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8")
        for cite_group in re.findall(r"\\cite[a-zA-Z*]*\{([^}]+)\}", text):
            cited.update(key.strip() for key in cite_group.split(",") if key.strip())
    return cited


def parse_entries(text: str) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    entry_pattern = re.compile(
        r"@(?P<entry_type>\w+)\{(?P<key>[^,]+),(?P<body>.*?)(?=\n\})",
        re.DOTALL,
    )
    field_pattern = re.compile(
        r"(?m)^\s*(?P<name>[A-Za-z]+)\s*=\s*(?P<value>.+?)(?:,\s*)?$"
    )
    for match in entry_pattern.finditer(text):
        fields = {
            field.group("name").lower(): field.group("value").strip()
            for field in field_pattern.finditer(match.group("body"))
        }
        entries[match.group("key").strip()] = {
            "entry_type": match.group("entry_type").lower(),
            "fields": fields,
        }
    return entries


def main() -> None:
    args = parse_args()
    output_path = resolve_from_latex(args.output)
    violations: list[dict[str, object]] = []
    if not BIB_PATH.is_file():
        violations.append({"issue": "missing_references_file", "path": str(BIB_PATH)})
        entries: dict[str, dict[str, object]] = {}
    else:
        entries = parse_entries(BIB_PATH.read_text(encoding="utf-8"))
    cited = cited_keys()
    defined = set(entries)

    if not entries:
        violations.append({"issue": "no_bibliography_entries"})
    missing = sorted(cited - defined)
    if missing:
        violations.append({"issue": "undefined_citations", "keys": missing})
    unused = sorted(defined - cited)
    if unused:
        violations.append({"issue": "unused_bibliography_entries", "keys": unused})

    urls: list[str] = []
    doi_count = 0
    for key, entry in sorted(entries.items()):
        entry_type = str(entry["entry_type"])
        fields = entry["fields"]
        required = (
            ("author", "title", "journal", "year", "doi")
            if entry_type == "article"
            else ("author", "title", "year", "howpublished")
        )
        missing_fields = [field for field in required if not fields.get(field)]
        if missing_fields:
            violations.append(
                {
                    "issue": "missing_required_reference_field",
                    "key": key,
                    "fields": missing_fields,
                }
            )
        if entry_type == "article" and fields.get("doi"):
            doi_count += 1
            doi = str(fields["doi"]).strip("{}")
            if not DOI_PATTERN.fullmatch(doi):
                violations.append(
                    {"issue": "malformed_doi", "key": key, "doi": doi}
                )
        for value in fields.values():
            urls.extend(URL_PATTERN.findall(str(value)))

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "references": "paper/latex/references.bib",
        "citation_count": len(cited),
        "bibliography_entry_count": len(entries),
        "doi_count": doi_count,
        "https_url_count": len(urls),
        "all_checks_passed": not violations,
        "violations": violations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
