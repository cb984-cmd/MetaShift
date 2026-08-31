"""Require two regenerated formal-paper asset manifests to have identical hashes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


LATEX_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = LATEX_ROOT / "generated" / "asset_manifest.json"
DEFAULT_OUTPUT = LATEX_ROOT / "generated" / "asset_determinism_validation.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def output_hashes() -> dict[str, str]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Missing generated asset manifest: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}
    for output in manifest.get("outputs", []):
        relative_path = str(output["path"])
        path = LATEX_ROOT / relative_path
        expected_hash = str(output["sha256"])
        if not path.is_file():
            raise FileNotFoundError(f"Missing generated asset: {path}")
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Manifest hash mismatch before determinism comparison: {relative_path}"
            )
        hashes[relative_path] = actual_hash
    if not hashes:
        raise RuntimeError("Asset manifest contains no generated outputs.")
    return hashes


def manifest_hash() -> str:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Missing generated asset manifest: {MANIFEST_PATH}")
    return sha256(MANIFEST_PATH)


def regenerate() -> None:
    subprocess.run(
        [sys.executable, "scripts/generate_paper_assets.py", "--write"],
        cwd=LATEX_ROOT,
        check=True,
    )


def main() -> None:
    regenerate()
    first = output_hashes()
    first_manifest_hash = manifest_hash()
    regenerate()
    second = output_hashes()
    second_manifest_hash = manifest_hash()
    changed = {
        path: {"first": first.get(path), "second": second.get(path)}
        for path in sorted(set(first) | set(second))
        if first.get(path) != second.get(path)
    }
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "generator": "paper/latex/scripts/generate_paper_assets.py",
        "output_count": len(second),
        "manifest_hashes": {
            "first": first_manifest_hash,
            "second": second_manifest_hash,
            "match": first_manifest_hash == second_manifest_hash,
        },
        "all_hashes_match": not changed and first_manifest_hash == second_manifest_hash,
        "changed_outputs": changed,
    }
    DEFAULT_OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_hashes_match"] else 1)


if __name__ == "__main__":
    main()
