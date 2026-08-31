"""Validate the structured external-document review's conservative boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


INPUT_PATH = Path("paper/EXTERNAL_DOCUMENT_REVIEW.csv")
OUTPUT_PATH = Path("artifacts/external_document_review_summary.json")


def main() -> None:
    review = pd.read_csv(INPUT_PATH)
    required = {
        "event_id",
        "classification",
        "site_specific_dated_confirmation",
        "source_url",
        "review_outcome",
    }
    missing = required.difference(review.columns)
    if missing:
        raise ValueError(f"External review lacks columns: {sorted(missing)}")
    direct = review["site_specific_dated_confirmation"].astype("string").str.lower().eq(
        "true"
    )
    payload = {
        "reviewed_events": len(review),
        "classification_counts": review["classification"].value_counts().to_dict(),
        "site_specific_dated_confirmations": int(direct.sum()),
        "all_rows_have_official_source_url": bool(
            review["source_url"].astype("string").str.startswith("https://").all()
        ),
        "interpretation": (
            "The review corroborates reported AQS context but does not provide "
            "site-specific dated physical-change confirmations."
        ),
    }
    if (
        payload["reviewed_events"] != 20
        or payload["site_specific_dated_confirmations"] != 0
        or not payload["all_rows_have_official_source_url"]
    ):
        raise ValueError(
            "External-document review does not match its documented conservative scope."
        )
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
