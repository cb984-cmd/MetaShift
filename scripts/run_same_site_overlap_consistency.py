"""Compare saved same-site POC overlap effects with hourly and cross-site outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.overlap import direction_agreement, paired_spearman  # noqa: E402


CONFIG_PATH = Path("configs/same_site_overlap_consistency_v1.json")
DAILY_PATH = Path("artifacts/colocated_validation.csv")
HOURLY_PATH = Path("artifacts/hourly_poc_validation_summary.csv")
METHOD_PATH = Path("artifacts/real_transition_88101_method_results.csv")
DETAIL_PATH = Path("artifacts/same_site_overlap_consistency_v1_details.csv")
SUMMARY_PATH = Path("artifacts/same_site_overlap_consistency_v1_summary.csv")
MANIFEST_PATH = Path("artifacts/same_site_overlap_consistency_v1_manifest.json")


def comparison_summary(
    details: pd.DataFrame,
    *,
    comparison: str,
    method: str,
    left_column: str,
    right_column: str,
) -> dict[str, object]:
    """Summarize direction and rank agreement for one prespecified comparison."""

    subset = details.loc[details["method"] == method].copy()
    left = pd.to_numeric(subset[left_column], errors="coerce").to_numpy(dtype=float)
    right = pd.to_numeric(subset[right_column], errors="coerce").to_numpy(dtype=float)
    agreements = [
        direction_agreement(left_value, right_value)
        for left_value, right_value in zip(left, right, strict=True)
    ]
    valid_agreements = [value for value in agreements if value is not None]
    paired_count, correlation = paired_spearman(left, right)
    return {
        "comparison": comparison,
        "method": method,
        "eligible_same_site_events": len(subset),
        "finite_paired_effects": paired_count,
        "nonzero_direction_pairs": len(valid_agreements),
        "direction_agreement_count": int(sum(valid_agreements)),
        "direction_agreement_fraction": (
            float(np.mean(valid_agreements)) if valid_agreements else np.nan
        ),
        "spearman_rank_correlation": correlation,
        "interpretation": (
            "Consistency context only; agreement does not establish physical "
            "instrument identity, ground-truth bias, or causal mechanism."
        ),
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    daily = pd.read_csv(DAILY_PATH)
    hourly = pd.read_csv(HOURLY_PATH)
    methods = pd.read_csv(METHOD_PATH)
    minimum_daily = int(config["minimum_paired_daily_observations_per_period"])
    if len(daily) < 10 or (
        daily[["paired_pre_days", "paired_post_days"]] < minimum_daily
    ).any().any():
        raise ValueError(
            "Same-site overlap analysis requires at least 10 qualified daily pairs."
        )
    hourly = hourly.loc[
        hourly["status"] == "paired_hourly_pre_post_available",
        [
            "anchor_id",
            "paired_pre_hours",
            "paired_post_hours",
            "hourly_difference_change_ug_m3",
            "daily_difference_change_ug_m3",
            "hourly_daily_direction_agreement",
        ],
    ]
    minimum_hourly = int(config["minimum_paired_hourly_observations_per_period"])
    if len(hourly) and (
        hourly[["paired_pre_hours", "paired_post_hours"]] < minimum_hourly
    ).any().any():
        raise ValueError("Available hourly pairs do not satisfy the frozen minimum.")
    rows: list[pd.DataFrame] = []
    daily_hourly = daily.merge(
        hourly, on="anchor_id", how="left", validate="one_to_one"
    ).assign(method="same_site_reference")
    for method in config["cross_site_methods"]:
        cross_site = methods.loc[
            methods["method"] == method, ["anchor_id", "raw_effect_ug_m3"]
        ].rename(columns={"raw_effect_ug_m3": "cross_site_raw_effect_ug_m3"})
        detail = (
            daily_hourly.merge(
                cross_site, on="anchor_id", how="left", validate="one_to_one"
            )
            .assign(method=method)
        )
        detail["same_site_daily_vs_cross_site_direction_agreement"] = [
            direction_agreement(left, right)
            for left, right in zip(
                detail["target_minus_reference_effect_ug_m3"],
                detail["cross_site_raw_effect_ug_m3"],
                strict=True,
            )
        ]
        rows.append(detail)
    details = pd.concat(rows, ignore_index=True)
    summaries = [
        comparison_summary(
            daily_hourly,
            comparison="same_site_daily_vs_same_site_hourly",
            method="same_site_reference",
            left_column="target_minus_reference_effect_ug_m3",
            right_column="hourly_difference_change_ug_m3",
        )
    ]
    summaries.extend(
        comparison_summary(
            details,
            comparison="same_site_daily_vs_cross_site_raw_residual",
            method=method,
            left_column="target_minus_reference_effect_ug_m3",
            right_column="cross_site_raw_effect_ug_m3",
        )
        for method in config["cross_site_methods"]
    )
    summary = pd.DataFrame(summaries)
    manifest = {
        "analysis_id": config["analysis_id"],
        "qualified_daily_same_site_events": len(daily),
        "qualified_hourly_same_site_events": len(hourly),
        "cross_site_methods": config["cross_site_methods"],
        "interpretation_boundary": config["interpretation_boundary"],
    }
    DETAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    details.to_csv(DETAIL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(summary.to_string(index=False))
    print(f"Wrote {DETAIL_PATH}, {SUMMARY_PATH}, and {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
