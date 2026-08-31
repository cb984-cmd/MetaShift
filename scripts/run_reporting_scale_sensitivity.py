"""Summarize concordance among log, raw-unit, and robust-score reporting scales."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


INPUT_PATH = Path("artifacts/effect_window_sensitivity_details.csv")
OUTPUT_PATH = Path("artifacts/reporting_scale_sensitivity_summary.csv")


def sign(values: pd.Series) -> pd.Series:
    return values.gt(0).astype(int) - values.lt(0).astype(int)


def main() -> None:
    details = pd.read_csv(INPUT_PATH)
    details = details.loc[
        (details["comparison_window_days"] == 60)
        & (details["status"] == "complete")
    ].copy()
    rows = []
    for method, group in details.groupby("method", sort=True):
        log_sign = sign(group["log_effect"])
        raw_sign = sign(group["raw_effect_ug_m3"])
        log_absolute = group["log_effect"].abs()
        raw_absolute = group["raw_effect_ug_m3"].abs()
        score_absolute = group["standardized_score"].abs()
        rows.append(
            {
                "method": method,
                "events": len(group),
                "log_raw_direction_agreement": float((log_sign == raw_sign).mean()),
                "spearman_abs_log_vs_raw": float(
                    spearmanr(log_absolute, raw_absolute).statistic
                ),
                "spearman_abs_log_vs_robust_score": float(
                    spearmanr(log_absolute, score_absolute).statistic
                ),
                "interpretation": (
                    "Reporting-scale concordance only; raw, log, and robust "
                    "standardized quantities are not interchangeable causal estimands."
                ),
            }
        )
    output = pd.DataFrame(rows)
    output.to_csv(OUTPUT_PATH, index=False)
    print(output.to_string(index=False))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
