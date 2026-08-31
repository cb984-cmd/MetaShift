"""Verify that shared baseline rows use identical synthetic inputs and seeds."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


MAIN_PATH = Path("artifacts/stable_synthetic_stable_full_v1_event_results.csv")
ABLATION_PATH = Path("artifacts/reliability_ablation_stable_full_v1_event_results.csv")
OUTPUT_PATH = Path("artifacts/benchmark_ablation_alignment.json")
KEYS = ["case_id", "split", "perturbation", "magnitude", "random_seed"]
COLUMNS = ["estimated_log_effect", "absolute_effect_error", "ranking_score"]
SHARED_METHOD = "standard_synthetic_control"
TOLERANCE = 1e-10


def main() -> None:
    main = pd.read_csv(MAIN_PATH)
    ablation = pd.read_csv(ABLATION_PATH)
    left = main.loc[main["method"] == SHARED_METHOD, KEYS + COLUMNS].copy()
    right = ablation.loc[
        ablation["method"] == SHARED_METHOD, KEYS + COLUMNS
    ].copy()
    joined = left.merge(right, on=KEYS, how="outer", suffixes=("_main", "_ablation"), indicator=True)
    missing_rows = int((joined["_merge"] != "both").sum())
    maximum_differences = {}
    for column in COLUMNS:
        left_values = joined[f"{column}_main"].to_numpy(dtype=float)
        right_values = joined[f"{column}_ablation"].to_numpy(dtype=float)
        equal = np.isclose(
            left_values, right_values, rtol=0.0, atol=TOLERANCE, equal_nan=True
        )
        maximum_differences[column] = float(
            np.nanmax(np.abs(left_values - right_values))
        ) if np.any(np.isfinite(left_values - right_values)) else 0.0
        if not equal.all():
            missing_rows += int((~equal).sum())

    payload = {
        "shared_method": SHARED_METHOD,
        "comparison_rows": len(joined),
        "tolerance": TOLERANCE,
        "maximum_absolute_differences": maximum_differences,
        "all_rows_aligned": missing_rows == 0,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["all_rows_aligned"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
