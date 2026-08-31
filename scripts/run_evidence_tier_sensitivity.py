"""Evaluate predeclared evidence-tier threshold sensitivity settings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.evidence import EvidenceTier, evidence_tier  # noqa: E402


INPUT_PATH = Path("artifacts/real_transition_88101_evidence_tiers.csv")
CONFIG_PATH = Path("configs/evidence_tier_sensitivity_v2.json")
DETAIL_PATH = Path("artifacts/evidence_tier_sensitivity_v2_details.csv")
SUMMARY_PATH = Path("artifacts/evidence_tier_sensitivity_v2_summary.csv")
FUNNEL_PATH = Path("artifacts/evidence_tier_sensitivity_v2_funnel.csv")


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def condition_flags(
    event: pd.Series, setting: dict[str, object], minimum_unique_placebos: int
) -> dict[str, bool]:
    """Expose fixed evidence gates so their sequential attrition is auditable."""

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
    sufficient_placebos = (
        str(event.get("placebo_status")).startswith("complete_")
        and pd.notna(event.get("placebo_count"))
        and int(event["placebo_count"]) >= minimum_unique_placebos
    )
    return {
        "audit_complete": event["audit_status"] == "complete",
        "quality_gate_passed": as_bool(event.get("quality_gate_passed")),
        "selection_interval_excludes_zero": as_bool(
            event.get("selection_ci_excludes_zero")
        ),
        "sufficient_time_placebos": sufficient_placebos,
        "raw_placebo_p_passes": (
            p_value is not None
            and p_value <= float(setting["raw_placebo_p_cutoff"])
        ),
        "bh_q_passes": q_value is not None
        and q_value <= float(setting["bh_q_cutoff"]),
        "donor_direction_passes": (
            stability is not None
            and stability >= float(setting["donor_direction_fraction_cutoff"])
        ),
    }


def funnel_summary(
    details: pd.DataFrame, funnel_order: list[str]
) -> pd.DataFrame:
    """Count sequentially surviving anchors without hiding gate-specific attrition."""

    rows: list[dict[str, object]] = []
    for setting, group in details.groupby("setting", sort=True):
        survivors = pd.Series(True, index=group.index)
        previous_count = len(group)
        rows.append(
            {
                "setting": setting,
                "stage": "all_anchors",
                "anchor_count": previous_count,
                "excluded_at_stage": 0,
            }
        )
        for column in funnel_order:
            survivors &= group[column].astype(bool)
            count = int(survivors.sum())
            rows.append(
                {
                    "setting": setting,
                    "stage": column,
                    "anchor_count": count,
                    "excluded_at_stage": previous_count - count,
                }
            )
            previous_count = count
    return pd.DataFrame(rows)


def complete_tier_summary(
    details: pd.DataFrame, setting_names: list[str]
) -> pd.DataFrame:
    """Keep zero-count tiers visible in every prespecified setting."""

    index = pd.MultiIndex.from_product(
        [setting_names, [tier.value for tier in EvidenceTier]],
        names=["setting", "evidence_tier"],
    )
    return (
        details.groupby(["setting", "evidence_tier"], sort=True)
        .size()
        .reindex(index, fill_value=0)
        .rename("anchor_count")
        .reset_index()
    )


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
            flags = condition_flags(
                event, setting, int(config["minimum_unique_placebos"])
            )
            tier, reasons = evidence_tier(
                audit_complete=flags["audit_complete"],
                quality_gate_passed=flags["quality_gate_passed"],
                ci_excludes_zero=flags["selection_interval_excludes_zero"],
                placebo_available=flags["sufficient_time_placebos"],
                placebo_count=int(event["placebo_count"])
                if pd.notna(event.get("placebo_count"))
                else None,
                placebo_p_value=p_value,
                placebo_q_value=q_value,
                donor_sensitivity_available=stability is not None,
                donor_direction_fraction=stability,
                min_placebo_count=int(config["minimum_unique_placebos"]),
                placebo_cutoff=float(setting["raw_placebo_p_cutoff"]),
                q_cutoff=float(setting["bh_q_cutoff"]),
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
                    **flags,
                }
            )

    details = pd.DataFrame(rows)
    summary = complete_tier_summary(
        details, [str(setting["name"]) for setting in config["settings"]]
    )
    funnel = funnel_summary(details, list(config["funnel_order"]))
    if not summary.groupby("setting")["anchor_count"].sum().eq(len(data)).all():
        raise RuntimeError("Evidence-tier summaries do not cover every anchor.")
    details.to_csv(DETAIL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    funnel.to_csv(FUNNEL_PATH, index=False)
    print(summary.to_string(index=False))
    print("\nEvidence funnel:")
    print(funnel.to_string(index=False))
    print(f"Wrote {DETAIL_PATH}, {SUMMARY_PATH}, and {FUNNEL_PATH}")


if __name__ == "__main__":
    main()
