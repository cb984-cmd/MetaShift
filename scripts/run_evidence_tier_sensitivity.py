"""Evaluate predeclared evidence-tier threshold sensitivity settings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.evidence import evidence_tier  # noqa: E402


INPUT_PATH = Path("artifacts/real_transition_88101_evidence_tiers.csv")
CONFIG_PATH = Path("configs/evidence_tier_sensitivity_v1.json")
DETAIL_PATH = Path("artifacts/evidence_tier_sensitivity_details.csv")
SUMMARY_PATH = Path("artifacts/evidence_tier_sensitivity_summary.csv")


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def main() -> None:
    data = pd.read_csv(INPUT_PATH)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for setting in config["settings"]:
        for _, event in data.iterrows():
            p_value = (
                float(event["placebo_p_value"])
                if pd.notna(event.get("placebo_p_value"))
                else None
            )
            q_value = (
                float(event["placebo_q_value"])
                if pd.notna(event.get("placebo_q_value"))
                else None
            )
            stability = (
                float(event["leave_one_donor_out_direction_fraction"])
                if pd.notna(event.get("leave_one_donor_out_direction_fraction"))
                else None
            )
            tier, reasons = evidence_tier(
                audit_complete=event["audit_status"] == "complete",
                quality_gate_passed=as_bool(event.get("quality_gate_passed")),
                ci_excludes_zero=as_bool(event.get("ci_excludes_zero")),
                placebo_available=str(event.get("placebo_status")).startswith(
                    "complete_"
                ),
                placebo_count=int(event["placebo_count"])
                if pd.notna(event.get("placebo_count"))
                else None,
                placebo_p_value=p_value,
                placebo_q_value=q_value,
                donor_sensitivity_available=stability is not None,
                donor_direction_fraction=stability,
                min_placebo_count=int(config["minimum_unique_placebos"]),
                placebo_cutoff=float(setting["raw_placebo_p_cutoff"]),
                q_cutoff=float(config["bh_q_cutoff"]),
                donor_stability_cutoff=float(
                    setting["donor_direction_fraction_cutoff"]
                ),
            )
            rows.append(
                {
                    "setting": setting["name"],
                    "anchor_id": event["anchor_id"],
                    "evidence_tier": tier.value,
                    "evidence_reasons": ";".join(reasons),
                }
            )

    details = pd.DataFrame(rows)
    summary = (
        details.groupby(["setting", "evidence_tier"])
        .size()
        .rename("anchor_count")
        .reset_index()
        .sort_values(["setting", "evidence_tier"])
    )
    details.to_csv(DETAIL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    print(summary.to_string(index=False))
    print(f"Wrote {DETAIL_PATH} and {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
