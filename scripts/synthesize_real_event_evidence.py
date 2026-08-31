"""Combine saved real-anchor evidence into transparent observational tiers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.evidence import evidence_tier  # noqa: E402


ARTIFACTS = Path("artifacts")
OUTPUT_PATH = ARTIFACTS / "real_transition_88101_evidence_tiers.csv"
SUMMARY_PATH = ARTIFACTS / "real_transition_88101_evidence_tier_summary.json"
CASE_SELECTION_PATH = ARTIFACTS / "real_transition_88101_case_selection.csv"


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def main() -> None:
    audit = pd.read_csv(ARTIFACTS / "real_transition_88101_event_audit.csv")
    methods = pd.read_csv(ARTIFACTS / "real_transition_88101_method_results.csv")
    intervals = pd.read_csv(ARTIFACTS / "real_transition_88101_event_intervals.csv")
    placebos = pd.read_csv(ARTIFACTS / "time_placebo_summary.csv")
    donor_sensitivity = pd.read_csv(ARTIFACTS / "leave_one_donor_out_summary.csv")

    meta = methods.loc[
        methods["method"] == "metashift_v1_fixed",
        [
            "anchor_id",
            "log_effect",
            "raw_effect_ug_m3",
            "standardized_score",
            "quality_gate_passed",
            "quality_gate_reason",
        ],
    ]
    meta_interval = intervals.loc[
        intervals["method"] == "metashift_v1_fixed",
        ["anchor_id", "ci95_lower", "ci95_upper", "ci_excludes_zero"],
    ]
    combined = (
        audit.merge(meta, on="anchor_id", how="left")
        .merge(meta_interval, on="anchor_id", how="left")
        .merge(
            placebos[
                ["anchor_id", "status", "placebo_count", "placebo_p_value"]
            ].rename(columns={"status": "placebo_status"}),
            on="anchor_id",
            how="left",
        )
        .merge(
            donor_sensitivity[
                [
                    "anchor_id",
                    "summary_status",
                    "direction_stable_all_donors",
                    "direction_flip_count",
                    "leave_one_out_max_abs_deviation",
                ]
            ],
            on="anchor_id",
            how="left",
        )
    )

    tiers = []
    reasons = []
    for _, row in combined.iterrows():
        placebo_value = row.get("placebo_p_value")
        placebo_p_value = (
            float(placebo_value) if pd.notna(placebo_value) else None
        )
        tier, tier_reasons = evidence_tier(
            audit_complete=row["audit_status"] == "complete",
            quality_gate_passed=as_bool(row.get("quality_gate_passed")),
            ci_excludes_zero=as_bool(row.get("ci_excludes_zero")),
            placebo_available=row.get("placebo_status") == "complete",
            placebo_p_value=placebo_p_value,
            donor_sensitivity_available=row.get("summary_status")
            in {"complete", "partial_after_donor_removal"},
            donor_direction_stable=as_bool(row.get("direction_stable_all_donors")),
        )
        tiers.append(tier.value)
        reasons.append(";".join(tier_reasons))
    combined["evidence_tier"] = tiers
    combined["evidence_reasons"] = reasons
    combined["classification_scope"] = (
        "Exploratory evidence synthesis from predeclared quality, conditional "
        "interval, time-placebo, and donor-sensitivity diagnostics; not a "
        "physical-causality label."
    )
    combined.to_csv(OUTPUT_PATH, index=False)

    summary = {
        "classification_scope": combined["classification_scope"].iloc[0],
        "placebo_cutoff": 0.10,
        "counts": combined["evidence_tier"].value_counts().to_dict(),
        "reason_counts": (
            combined["evidence_reasons"]
            .loc[combined["evidence_reasons"] != ""]
            .str.split(";")
            .explode()
            .value_counts()
            .to_dict()
        ),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    supported = combined.loc[
        combined["evidence_tier"] == "supported_candidate_discontinuity"
    ].sort_values("standardized_score", ascending=False)
    case_rows = []
    if not supported.empty:
        case_rows.append({**supported.iloc[0].to_dict(), "selection_role": "highest_supported_score"})
        case_rows.append(
            {
                **supported.iloc[len(supported) // 2].to_dict(),
                "selection_role": "median_supported_score",
            }
        )
    not_supported = combined.loc[
        combined["evidence_tier"] == "not_supported_by_available_evidence"
    ].sort_values("standardized_score", ascending=False)
    if not not_supported.empty:
        case_rows.append(
            {
                **not_supported.iloc[0].to_dict(),
                "selection_role": "highest_score_not_supported",
            }
        )
    inconclusive = combined.loc[
        combined["evidence_tier"] == "inconclusive_insufficient_evidence"
    ]
    if not inconclusive.empty:
        case_rows.append(
            {
                **inconclusive.iloc[0].to_dict(),
                "selection_role": "first_inconclusive_by_event_order",
            }
        )
    pd.DataFrame(case_rows).to_csv(CASE_SELECTION_PATH, index=False)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {OUTPUT_PATH}, {SUMMARY_PATH}, and {CASE_SELECTION_PATH}")


if __name__ == "__main__":
    main()
