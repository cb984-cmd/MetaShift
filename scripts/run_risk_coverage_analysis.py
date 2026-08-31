"""Evaluate pre-fit quality gating on independent stable synthetic cases."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path("artifacts/stable_synthetic_stable_full_v1_event_results.csv")
OUTPUT_PATH = Path("artifacts/synthetic_risk_coverage_curve.csv")
SUMMARY_PATH = Path("artifacts/real_event_coverage_summary.json")
METHODS = (
    "nearest_neighbor_did",
    "standard_synthetic_control",
    "metashift_v1_fixed",
    "metashift_v2_cv",
)
TARGET_COVERAGES = tuple(np.arange(0.1, 1.01, 0.1))


def main() -> None:
    data = pd.read_csv(INPUT_PATH)
    eligible = data.loc[
        data["method"].isin(METHODS)
        & (data["is_local"] == 1)
        & data["true_local_log_effect"].notna()
        & data["pre_fit_rmse"].notna()
    ].copy()
    rows = []
    for method, group in eligible.groupby("method", sort=True):
        calibration_quality = (
            group.loc[group["split"] == "calibration"]
            .groupby("case_id")["pre_fit_rmse"]
            .first()
        )
        evaluation = group.loc[group["split"] == "evaluation"].copy()
        evaluation_quality = evaluation.groupby("case_id")["pre_fit_rmse"].first()
        for target_coverage in TARGET_COVERAGES:
            threshold = float(calibration_quality.quantile(target_coverage))
            kept_cases = evaluation_quality.loc[
                evaluation_quality <= threshold
            ].index
            kept = evaluation.loc[evaluation["case_id"].isin(kept_cases)]
            rows.append(
                {
                    "method": method,
                    "target_calibration_coverage": target_coverage,
                    "pre_fit_rmse_threshold": threshold,
                    "evaluation_case_coverage": len(kept_cases)
                    / evaluation_quality.index.nunique(),
                    "evaluation_cases": len(kept_cases),
                    "evaluation_local_effect_instances": len(kept),
                    "local_effect_mae_log": float(kept["absolute_effect_error"].mean())
                    if len(kept)
                    else np.nan,
                }
            )
    output = pd.DataFrame(rows)
    output.to_csv(OUTPUT_PATH, index=False)

    audit = pd.read_csv("artifacts/real_transition_88101_event_audit.csv")
    complete = audit.loc[audit["audit_status"] == "complete"]
    coverage = {
        "all_metadata_anchors": len(audit),
        "common_comparative_estimates": len(complete),
        "common_comparison_coverage": len(complete) / len(audit),
        "metashift_quality_gate_passed": int(
            complete["metashift_quality_gate_passed"].astype("string")
            .str.lower()
            .eq("true")
            .sum()
        ),
        "quality_gate_coverage_of_complete_estimates": float(
            complete["metashift_quality_gate_passed"].astype("string")
            .str.lower()
            .eq("true")
            .mean()
        ),
        "interpretation": (
            "Real-event coverage is evidence availability, not classification "
            "accuracy because real physical-bias labels are unavailable."
        ),
    }
    import json

    SUMMARY_PATH.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    print(output.to_string(index=False))
    print(coverage)


if __name__ == "__main__":
    main()
