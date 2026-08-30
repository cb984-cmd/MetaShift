"""Download QA collocation records for preselected MetaShift Tier C candidates."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


API_ENDPOINT = "https://aqs.epa.gov/data/api/qaCollocatedAssessments/bySite"
ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
OUTPUT_DIR = Path("data/raw/aqs_qa")
MANIFEST_PATH = Path("artifacts/qa_collocation_manifest.json")


def api_credentials() -> tuple[str, str]:
    email = os.environ.get("AQS_API_EMAIL")
    key = os.environ.get("AQS_API_KEY")
    if not email or not key:
        raise RuntimeError(
            "AQS_API_EMAIL and AQS_API_KEY must be set in the process environment."
        )
    return email, key


def fetch_site(
    email: str,
    key: str,
    state: str,
    county: str,
    site: str,
    anchor_date: pd.Timestamp,
) -> tuple[dict[str, object], dict[str, object]]:
    start = (anchor_date - timedelta(days=120)).strftime("%Y%m%d")
    end = (anchor_date + timedelta(days=120)).strftime("%Y%m%d")
    query = urlencode(
        {
            "email": email,
            "key": key,
            "param": "88101",
            "bdate": start,
            "edate": end,
            "state": state,
            "county": county,
            "site": site,
        }
    )
    # Do not print this URL: it contains credentials.
    with urlopen(f"{API_ENDPOINT}?{query}", timeout=60) as response:
        payload = json.load(response)
    provenance = {
        "service": "qaCollocatedAssessments/bySite",
        "parameter": "88101",
        "state": state,
        "county": county,
        "site": site,
        "begin_date": start,
        "end_date": end,
        "api_status": payload.get("Header", [{}])[0].get("status"),
        "api_message": payload.get("Header", [{}])[0].get("request_time"),
    }
    return payload, provenance


def main() -> None:
    email, key = api_credentials()
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    tier_c = anchors.loc[pd.to_numeric(anchors["colocated_control_count"]) >= 1].copy()
    if tier_c.empty:
        raise ValueError("No same-site alternate-POC candidates are available.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for _, row in tier_c.iterrows():
        anchor_id = str(row["anchor_id"])
        try:
            payload, provenance = fetch_site(
                email,
                key,
                str(row["State Code"]),
                str(row["County Code"]),
                str(row["Site Num"]),
                pd.Timestamp(row["start_date"]),
            )
        except HTTPError as error:
            # An individual site can be rejected by the API (for example, an
            # unsupported county/site combination). Preserve that failure in
            # the manifest rather than silently excluding the candidate.
            manifest.append(
                {
                    "anchor_id": anchor_id,
                    "service": "qaCollocatedAssessments/bySite",
                    "parameter": "88101",
                    "state": str(row["State Code"]),
                    "county": str(row["County Code"]),
                    "site": str(row["Site Num"]),
                    "api_status": error.code,
                    "api_error": error.reason,
                    "record_count": None,
                }
            )
            print(f"QA request rejected for {anchor_id}: HTTP {error.code} {error.reason}")
            continue

        filename = f"{anchor_id}.json"
        output_path = OUTPUT_DIR / filename
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        provenance.update(
            {
                "anchor_id": anchor_id,
                "path": str(output_path),
                "record_count": len(payload.get("Data", [])),
            }
        )
        manifest.append(provenance)
        print(
            f"Downloaded QA response for {anchor_id}: "
            f"{provenance['record_count']} records"
        )

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
