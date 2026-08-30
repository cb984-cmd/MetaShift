"""Capture and compare deterministic hashes for MetaShift-Bench core results."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


CORE_ARTIFACTS = (
    Path("artifacts/data_gate/data_manifest.csv"),
    Path("artifacts/stable_synthetic_stable_full_v1_metrics.csv"),
    Path("artifacts/stable_synthetic_stable_full_v1_bootstrap.csv"),
    Path("artifacts/reliability_ablation_stable_full_v1_metrics.csv"),
    Path("artifacts/real_transition_88101_event_audit.csv"),
    Path("artifacts/real_transition_88101_method_results.csv"),
    Path("artifacts/time_placebo_summary.csv"),
    Path("artifacts/time_placebo_date_permutations.csv"),
    Path("artifacts/external_validation_evidence.csv"),
    Path("artifacts/data_gate_88502/data_manifest.csv"),
    Path("artifacts/real_transition_88502_event_audit.csv"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture or compare result hashes.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--label", required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--first", required=True, type=Path)
    compare.add_argument("--second", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture(label: str) -> Path:
    missing = [str(path) for path in CORE_ARTIFACTS if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Cannot capture missing core artifacts: {missing}")
    payload = {
        "label": label,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "artifacts": {str(path): sha256(path) for path in CORE_ARTIFACTS},
    }
    output = Path("artifacts") / f"reproducibility_hashes_{label}.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output)
    return output


def compare(first: Path, second: Path) -> Path:
    left = json.loads(first.read_text(encoding="utf-8"))["artifacts"]
    right = json.loads(second.read_text(encoding="utf-8"))["artifacts"]
    keys = sorted(set(left) | set(right))
    comparisons = [
        {"artifact": key, "first": left.get(key), "second": right.get(key), "match": left.get(key) == right.get(key)}
        for key in keys
    ]
    payload = {
        "first": str(first),
        "second": str(second),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "all_core_artifacts_match": all(item["match"] for item in comparisons),
        "comparisons": comparisons,
    }
    output = Path("results") / "reproducibility_comparison.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["all_core_artifacts_match"]:
        raise SystemExit(1)
    return output


def main() -> None:
    args = parse_args()
    if args.command == "capture":
        capture(args.label)
    else:
        compare(args.first, args.second)


if __name__ == "__main__":
    main()
