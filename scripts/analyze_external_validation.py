"""Summarize same-site POC and QA-collocation evidence without overclaiming."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
QA_MANIFEST_PATH = Path("artifacts/qa_collocation_manifest.json")
POC_PATH = Path("artifacts/colocated_validation.csv")
QA_PAIR_PATH = Path("artifacts/qa_collocation_pair_summary.csv")
EVIDENCE_PATH = Path("artifacts/external_validation_evidence.csv")


def target_or_reference_difference(
    record: dict[str, object], target_poc: str
) -> tuple[str, str, float, str, str] | None:
    """Orient a QA pair as target POC minus the other POC."""

    primary_poc = str(record.get("primary_poc"))
    collocated_poc = str(record.get("collocated_poc"))
    primary_value = record.get("primary_value")
    collocated_value = record.get("assessment_value")
    if primary_value is None or collocated_value is None:
        return None
    if target_poc == primary_poc:
        return (
            primary_poc,
            collocated_poc,
            float(primary_value) - float(collocated_value),
            str(record.get("primary_method_code")),
            str(record.get("colloctated_method_code")),
        )
    if target_poc == collocated_poc:
        return (
            collocated_poc,
            primary_poc,
            float(collocated_value) - float(primary_value),
            str(record.get("colloctated_method_code")),
            str(record.get("primary_method_code")),
        )
    return None


def summarize_qa_pair(
    anchor_id: str,
    anchor_date: pd.Timestamp,
    target_poc: str,
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    oriented = []
    for record in records:
        value = target_or_reference_difference(record, target_poc)
        if value is None:
            continue
        observed_target_poc, reference_poc, difference, target_method, reference_method = value
        assessment_date = pd.Timestamp(str(record["assessment_date"]))
        oriented.append(
            {
                "anchor_id": anchor_id,
                "anchor_date": anchor_date.date().isoformat(),
                "target_poc": observed_target_poc,
                "reference_poc": reference_poc,
                "assessment_date": assessment_date,
                "target_minus_reference_ug_m3": difference,
                "target_method_code_at_assessment": target_method,
                "reference_method_code_at_assessment": reference_method,
            }
        )
    if not oriented:
        return []

    values = pd.DataFrame(oriented)
    result = []
    for reference_poc, group in values.groupby("reference_poc", sort=True):
        pre = group.loc[
            (group["assessment_date"] >= anchor_date - pd.Timedelta(days=120))
            & (group["assessment_date"] < anchor_date),
            "target_minus_reference_ug_m3",
        ]
        post = group.loc[
            (group["assessment_date"] >= anchor_date)
            & (group["assessment_date"] <= anchor_date + pd.Timedelta(days=120)),
            "target_minus_reference_ug_m3",
        ]
        effect = np.nan
        if len(pre) >= 3 and len(post) >= 3:
            effect = float(np.median(post) - np.median(pre))
        result.append(
            {
                "anchor_id": anchor_id,
                "anchor_date": anchor_date.date().isoformat(),
                "target_poc": target_poc,
                "reference_poc": reference_poc,
                "qa_pair_records": len(group),
                "qa_pre_records": len(pre),
                "qa_post_records": len(post),
                "qa_pre_median_difference_ug_m3": float(np.median(pre))
                if len(pre)
                else np.nan,
                "qa_post_median_difference_ug_m3": float(np.median(post))
                if len(post)
                else np.nan,
                "qa_difference_change_ug_m3": effect,
                "validation_status": "paired_pre_post_available"
                if np.isfinite(effect)
                else "insufficient_matched_pre_post_qa_records",
                "interpretation_boundary": (
                    "QA collocation is external comparative evidence; it does not "
                    "independently prove the physical cause of a Method Code transition."
                ),
            }
        )
    return result


def main() -> None:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    anchor_by_id = anchors.set_index("anchor_id")
    qa_manifest = json.loads(QA_MANIFEST_PATH.read_text(encoding="utf-8"))

    qa_rows: list[dict[str, object]] = []
    evidence_rows: list[dict[str, object]] = []
    for entry in qa_manifest:
        anchor_id = str(entry["anchor_id"])
        anchor = anchor_by_id.loc[anchor_id]
        target_poc = str(anchor["POC"])
        record_count = entry.get("record_count")
        if not isinstance(record_count, int) or record_count == 0:
            evidence_rows.append(
                {
                    "anchor_id": anchor_id,
                    "evidence_source": "qa_collocation",
                    "evidence_status": "api_error_or_no_records",
                    "records": record_count,
                    "effect_ug_m3": np.nan,
                }
            )
            continue
        response_path = Path(str(entry["path"]))
        payload = json.loads(response_path.read_text(encoding="utf-8"))
        pairs = summarize_qa_pair(
            anchor_id,
            pd.Timestamp(anchor["start_date"]),
            target_poc,
            payload.get("Data", []),
        )
        if not pairs:
            evidence_rows.append(
                {
                    "anchor_id": anchor_id,
                    "evidence_source": "qa_collocation",
                    "evidence_status": "target_poc_not_present_in_qa_pairs",
                    "records": record_count,
                    "effect_ug_m3": np.nan,
                }
            )
        else:
            qa_rows.extend(pairs)
            for pair in pairs:
                evidence_rows.append(
                    {
                        "anchor_id": anchor_id,
                        "evidence_source": "qa_collocation",
                        "evidence_status": pair["validation_status"],
                        "records": pair["qa_pair_records"],
                        "effect_ug_m3": pair["qa_difference_change_ug_m3"],
                    }
                )

    poc = pd.read_csv(POC_PATH, dtype="string")
    for column in [
        "paired_pre_days",
        "paired_post_days",
        "target_minus_reference_effect_ug_m3",
        "robust_standardized_effect",
    ]:
        poc[column] = pd.to_numeric(poc[column])
    for _, row in poc.iterrows():
        evidence_rows.append(
            {
                "anchor_id": row["anchor_id"],
                "evidence_source": "same_site_alternate_poc",
                "evidence_status": "paired_pre_post_available"
                if row["paired_pre_days"] >= 30 and row["paired_post_days"] >= 30
                else "insufficient_paired_pre_post_records",
                "records": int(row["paired_pre_days"] + row["paired_post_days"]),
                "effect_ug_m3": row["target_minus_reference_effect_ug_m3"],
            }
        )

    qa_summary = pd.DataFrame(qa_rows)
    evidence = pd.DataFrame(evidence_rows)
    qa_summary.to_csv(QA_PAIR_PATH, index=False)
    evidence.to_csv(EVIDENCE_PATH, index=False)
    print("External validation evidence status:")
    print(
        evidence.groupby(["evidence_source", "evidence_status"], dropna=False)
        .size()
        .rename("records")
        .reset_index()
        .to_string(index=False)
    )
    print(f"\nWrote {QA_PAIR_PATH} and {EVIDENCE_PATH}")


if __name__ == "__main__":
    main()
