"""Require two v0.5 manuscript-asset generations to have identical hashes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = LATEX_ROOT / "generated" / "v05_answerability_asset_manifest.json"
OUTPUT_PATH = LATEX_ROOT / "generated" / "v05_answerability_asset_determinism.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def regenerate() -> None:
    subprocess.run(
        [sys.executable, "scripts/generate_v05_answerability_assets.py", "--write"],
        cwd=LATEX_ROOT,
        check=True,
    )


def output_hashes() -> dict[str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}
    for record in manifest["outputs"]:
        path = LATEX_ROOT / record["path"]
        if not path.is_file() or sha256(path) != record["sha256"]:
            raise RuntimeError(f"Manifest hash mismatch: {record['path']}")
        hashes[str(record["path"])] = str(record["sha256"])
    return hashes


def main() -> None:
    regenerate()
    first = output_hashes()
    first_manifest = sha256(MANIFEST_PATH)
    regenerate()
    second = output_hashes()
    second_manifest = sha256(MANIFEST_PATH)
    changed = {
        path: {"first": first.get(path), "second": second.get(path)}
        for path in sorted(set(first) | set(second))
        if first.get(path) != second.get(path)
    }
    report = {
        "scope": "Deterministic receipt-bound v0.5 presentation-asset generation.",
        "generator": "paper/latex/scripts/generate_v05_answerability_assets.py",
        "output_count": len(second),
        "manifest_hashes": {
            "first": first_manifest,
            "second": second_manifest,
            "match": first_manifest == second_manifest,
        },
        "changed_outputs": changed,
        "all_hashes_match": not changed and first_manifest == second_manifest,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_hashes_match"] else 1)


if __name__ == "__main__":
    main()
