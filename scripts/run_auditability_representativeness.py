"""Describe which metadata anchors can receive a common counterfactual audit."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from metashift.auditability import (  # noqa: E402
    epa_region,
    fit_ridge_logistic,
    standardized_mean_difference,
)
from run_feasibility_prototype import load_series  # noqa: E402


CONFIG_PATH = Path("configs/auditability_representativeness_v2.json")
ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
CONTROLS_PATH = Path("artifacts/data_gate/geographic_controls.csv")
COORDINATES_PATH = Path("artifacts/real_transition_88101_anchor_coordinates.csv")
EVENT_OUTPUT_PATH = Path("artifacts/auditability_representativeness_v2_events.csv")
COVERAGE_OUTPUT_PATH = Path("artifacts/auditability_representativeness_v2_coverage.csv")
SMD_OUTPUT_PATH = Path(
    "artifacts/auditability_representativeness_v2_standardized_differences.csv"
)
MODEL_OUTPUT_PATH = Path("artifacts/auditability_representativeness_v2_model.csv")
MANIFEST_OUTPUT_PATH = Path("artifacts/auditability_representativeness_v2_manifest.json")
SERIES_KEYS = ("State Code", "County Code", "Site Num", "POC")


def coverage_table(events: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Summarize descriptive audit coverage for a predeclared grouping."""

    table = (
        events.groupby(dimension, dropna=False, sort=True)
        .agg(
            anchor_count=("anchor_id", "size"),
            auditable_count=("auditable", "sum"),
        )
        .reset_index()
    )
    table["unavailable_count"] = table["anchor_count"] - table["auditable_count"]
    table["auditable_fraction"] = table["auditable_count"] / table["anchor_count"]
    table.insert(0, "dimension", dimension)
    table = table.rename(columns={dimension: "group"})
    return table


def standardized_differences(
    events: pd.DataFrame, features: list[str]
) -> pd.DataFrame:
    """Compare predeclared numeric covariates without imputing unavailable events."""

    rows = []
    complete = events.loc[events["auditable"]]
    unavailable = events.loc[~events["auditable"]]
    for feature in features:
        left = pd.to_numeric(complete[feature], errors="coerce").dropna()
        right = pd.to_numeric(unavailable[feature], errors="coerce").dropna()
        rows.append(
            {
                "feature": feature,
                "complete_count": len(left),
                "unavailable_count": len(right),
                "complete_mean": float(left.mean()),
                "unavailable_mean": float(right.mean()),
                "standardized_mean_difference_complete_minus_unavailable": (
                    standardized_mean_difference(left, right)
                ),
            }
        )
    return pd.DataFrame(rows)


def build_event_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build pre-outcome auditability features from frozen anchor metadata."""

    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    audit = pd.read_csv(AUDIT_PATH, dtype="string")
    controls = pd.read_csv(CONTROLS_PATH, dtype="string")
    coordinates = pd.read_csv(COORDINATES_PATH, dtype="string")
    if len(anchors) != 563 or len(audit) != len(anchors):
        raise ValueError("Auditability analysis requires the complete 563-anchor inventory.")
    audit_status = audit.loc[:, ["anchor_id", "audit_status"]]
    events = anchors.merge(audit_status, on="anchor_id", how="left", validate="one_to_one")
    if events["audit_status"].isna().any():
        raise ValueError("At least one anchor has no audit status.")
    control_stats = (
        controls.assign(
            distance_km=pd.to_numeric(controls["distance_km"]),
            correlation=pd.to_numeric(controls["pre_transition_log_correlation"]),
        )
        .groupby("anchor_id", sort=False)
        .agg(
            nearest_qualified_control_distance_km=("distance_km", "min"),
            mean_qualified_control_correlation=("correlation", "mean"),
        )
        .reset_index()
    )
    events = events.merge(control_stats, on="anchor_id", how="left", validate="one_to_one")
    coordinate_columns = ["anchor_id", "Latitude", "Longitude"]
    events = events.merge(
        coordinates.loc[:, coordinate_columns],
        on="anchor_id",
        how="left",
        validate="one_to_one",
    )
    if events[["Latitude", "Longitude"]].isna().any().any():
        raise ValueError("All anchors require coordinates for coverage mapping.")

    series = load_series("88101")
    pocs_per_site = Counter(key[:3] for key in series)
    previous_run_medians: list[float] = []
    for _, event in events.iterrows():
        key = tuple(str(event[column]) for column in SERIES_KEYS)
        target = series.get(key)
        if target is None:
            raise KeyError(f"Anchor target series missing from canonical data: {key}")
        previous_run = target.loc[
            pd.Timestamp(event["previous_start_date"]) : pd.Timestamp(
                event["previous_end_date"]
            )
        ].dropna()
        if len(previous_run) < 45:
            raise ValueError(
                f"Anchor {event['anchor_id']} lacks 45 prior-method-run values."
            )
        previous_run_medians.append(float(previous_run.median()))

    events["start_date"] = pd.to_datetime(events["start_date"])
    events["anchor_year"] = events["start_date"].dt.year
    events["epa_region"] = [epa_region(value) for value in events["State Code"]]
    events["transition_pair"] = (
        events["previous_method_code"].astype(str)
        + " -> "
        + events["method_code"].astype(str)
    )
    events["auditable"] = events["audit_status"].eq("complete")
    events["site_poc_count"] = [
        pocs_per_site[
            tuple(str(event[column]) for column in ("State Code", "County Code", "Site Num"))
        ]
        for _, event in events.iterrows()
    ]
    events["target_previous_method_run_median_ug_m3"] = previous_run_medians
    events["urban_rural_status"] = "not_available_in_aqs_daily_slice"
    for column in (
        "pre_span_days",
        "post_span_days",
        "transition_gap_days",
        "geographic_control_count",
        "colocated_control_count",
        "nearest_qualified_control_distance_km",
        "mean_qualified_control_correlation",
        "site_poc_count",
        "target_previous_method_run_median_ug_m3",
        "Latitude",
        "Longitude",
    ):
        events[column] = pd.to_numeric(events[column], errors="raise")
    return events, anchors


def descriptive_logistic_model(
    events: pd.DataFrame, features: list[str], ridge_penalty: float
) -> pd.DataFrame:
    """Fit a noncausal model only where a candidate donor context exists."""

    subpopulation = events.loc[events["geographic_control_count"] >= 1].copy()
    model_features = subpopulation.loc[:, features].copy()
    for feature in features:
        if model_features[feature].isna().any():
            median = float(model_features[feature].median())
            model_features[feature] = model_features[feature].fillna(median)
    fit = fit_ridge_logistic(
        model_features, subpopulation["auditable"].astype(int), ridge_penalty
    )
    return pd.DataFrame(
        {
            "feature": features,
            "standardized_log_odds_coefficient": fit.coefficients,
            "standardized_odds_ratio": np.exp(fit.coefficients),
            "feature_mean_in_model_subpopulation": fit.feature_means,
            "feature_standard_deviation_in_model_subpopulation": fit.feature_scales,
            "observations": fit.observations,
            "auditable_outcomes": fit.positive_outcomes,
            "ridge_penalty": fit.ridge_penalty,
            "interpretation": (
                "Descriptive association among anchors with at least one qualified "
                "geographic donor; not a physical-bias or causal model."
            ),
        }
    )


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    events, _ = build_event_table()
    if events["epa_region"].eq("unmapped").any():
        raise ValueError("All anchor state codes must map to an EPA region.")
    coverage = pd.concat(
        [
            coverage_table(events, "epa_region"),
            coverage_table(events, "anchor_year"),
            coverage_table(events, "transition_pair"),
            coverage_table(events, "audit_status"),
        ],
        ignore_index=True,
    )
    numeric_features = [
        feature
        for feature in config["descriptive_features"]
        if feature
        not in {
            "epa_region",
            "anchor_year",
            "transition_pair",
        }
    ]
    differences = standardized_differences(events, numeric_features)
    model_config = config["descriptive_logistic_model"]
    model = descriptive_logistic_model(
        events, list(model_config["features"]), float(model_config["ridge_penalty"])
    )
    manifest = {
        "analysis_id": config["analysis_id"],
        "metadata_anchor_count": len(events),
        "auditable_count": int(events["auditable"].sum()),
        "unavailable_count": int((~events["auditable"]).sum()),
        "model_subpopulation_count": int(
            (events["geographic_control_count"] >= 1).sum()
        ),
        "outcome_data_used": ["audit_status"],
        "outcome_data_not_used": config["reporting"]["forbidden_outcome_inputs"],
        "urban_rural_status": config["unavailable_feature"],
        "interpretation_boundary": config["interpretation_boundary"],
    }
    EVENT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENT_OUTPUT_PATH, index=False)
    coverage.to_csv(COVERAGE_OUTPUT_PATH, index=False)
    differences.to_csv(SMD_OUTPUT_PATH, index=False)
    model.to_csv(MODEL_OUTPUT_PATH, index=False)
    MANIFEST_OUTPUT_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print("\nRegional coverage:")
    print(
        coverage.loc[coverage["dimension"] == "epa_region"].to_string(index=False)
    )
    print(f"\nWrote {EVENT_OUTPUT_PATH}, {COVERAGE_OUTPUT_PATH}, {SMD_OUTPUT_PATH}, "
          f"{MODEL_OUTPUT_PATH}, and {MANIFEST_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
