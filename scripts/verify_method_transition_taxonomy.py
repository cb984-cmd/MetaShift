"""Verify frozen Method Code taxonomy coverage before outcome stratification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.taxonomy import load_transition_taxonomy  # noqa: E402


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
TAXONOMY_PATH = Path("configs/method_transition_taxonomy_v1.csv")
OUTPUT_PATH = Path("artifacts/method_transition_taxonomy_audit.json")


def main() -> None:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    taxonomy = load_transition_taxonomy(TAXONOMY_PATH, anchors)
    with_counts = anchors.merge(
        taxonomy,
        left_on=[
            "previous_method_code",
            "previous_method_name",
            "method_code",
            "method_name",
        ],
        right_on=[
            "old_method_code",
            "old_method_name",
            "new_method_code",
            "new_method_name",
        ],
        how="left",
        validate="many_to_one",
    )
    if with_counts["transition_class"].isna().any():
        raise ValueError("A taxonomy-validated pair failed to merge with an anchor.")
    summary = (
        with_counts.groupby("transition_class", sort=True)
        .size()
        .astype(int)
        .to_dict()
    )
    payload = {
        "taxonomy_path": str(TAXONOMY_PATH),
        "taxonomy_transition_pairs": len(taxonomy),
        "metadata_anchor_count": len(anchors),
        "anchor_counts_by_transition_class": summary,
        "review_statuses": sorted(taxonomy["review_status"].unique().tolist()),
        "outcome_data_read": False,
        "status": (
            "Taxonomy validated against Method Code metadata only; it must receive "
            "student/teacher review before being represented as human-verified."
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
