"""Run predeclared one-factor screening sensitivity analyses for AQS anchors."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/screening_sensitivity_v1.json"
OUTPUT_ROOT = ROOT / "artifacts/screening_sensitivity"
SUMMARY_PATH = ROOT / "artifacts/screening_sensitivity_summary.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all or selected predeclared AQS screening sensitivity settings."
    )
    parser.add_argument(
        "--settings",
        nargs="+",
        default=None,
        help="Optional names from configs/screening_sensitivity_v1.json.",
    )
    return parser.parse_args()


def arguments_for_setting(
    setting: dict[str, object], primary: dict[str, object], output_dir: Path
) -> list[str]:
    effective = dict(primary)
    if setting["parameter"] != "primary":
        effective[str(setting["parameter"])] = setting["value"]
    return [
        sys.executable,
        "scripts/scan_data_gate.py",
        "--output-dir",
        str(output_dir.relative_to(ROOT)),
        "--minimum-observation-percent",
        str(effective["minimum_observation_percent"]),
        "--minimum-window-days",
        str(effective["minimum_window_days"]),
        "--maximum-transition-gap-days",
        str(effective["maximum_transition_gap_days"]),
        "--minimum-correlation",
        str(effective["minimum_correlation"]),
        "--maximum-control-distance-km",
        str(effective["maximum_control_distance_km"]),
    ]


def summarize_setting(
    setting: dict[str, object],
    output_dir: Path,
    donor_thresholds: list[int],
) -> list[dict[str, object]]:
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    anchors = pd.read_csv(output_dir / "anchor_inventory.csv")
    rows = []
    for minimum_donors in donor_thresholds:
        rows.append(
            {
                "setting": setting["name"],
                "varied_parameter": setting["parameter"],
                "varied_value": setting["value"],
                "minimum_donors_required": minimum_donors,
                "canonical_records": summary["canonical_records"],
                "monitor_series": summary["monitor_series"],
                "eligible_anchors_before_donor_threshold": summary["eligible_anchors"],
                "eligible_anchors_after_donor_threshold": int(
                    (anchors["geographic_control_count"] >= minimum_donors).sum()
                ),
                "median_geographic_control_count": float(
                    anchors["geographic_control_count"].median()
                ),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    selected = config["settings"]
    if args.settings is not None:
        requested = set(args.settings)
        selected = [item for item in selected if item["name"] in requested]
        missing = requested.difference(item["name"] for item in selected)
        if missing:
            raise ValueError(f"Unknown screening sensitivity settings: {sorted(missing)}")
    rows = []
    for setting in selected:
        output_dir = OUTPUT_ROOT / str(setting["name"])
        command = arguments_for_setting(setting, config["primary"], output_dir)
        print("+", " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
        rows.extend(
            summarize_setting(
                setting, output_dir, config["minimum_donor_summary_values"]
            )
        )
    result = pd.DataFrame(rows)
    result.to_csv(SUMMARY_PATH, index=False)
    print(result.to_string(index=False))
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
