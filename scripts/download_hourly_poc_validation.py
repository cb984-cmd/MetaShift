"""Download narrow AQS hourly windows for same-site alternate-POC audits."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


API_ENDPOINT = "https://aqs.epa.gov/data/api/sampleData/bySite"
ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
CONTROLS_PATH = Path("artifacts/data_gate/colocated_controls.csv")
RAW_DIR = Path("data/raw/aqs_hourly_poc")
MANIFEST_PATH = Path("artifacts/hourly_poc_download_manifest.json")


def credentials() -> tuple[str, str]:
    email = os.environ.get("AQS_API_EMAIL")
    key = os.environ.get("AQS_API_KEY")
    if not email or not key:
        raise RuntimeError(
            "AQS_API_EMAIL and AQS_API_KEY must be present in the process environment."
        )
    return email, key


def fetch_site(
    email: str,
    key: str,
    state: str,
    county: str,
    site: str,
    anchor_date: pd.Timestamp,
) -> dict[str, object]:
    query = urlencode(
        {
            "email": email,
            "key": key,
            "param": "88101",
            "bdate": (anchor_date - timedelta(days=75)).strftime("%Y%m%d"),
            "edate": (anchor_date + timedelta(days=75)).strftime("%Y%m%d"),
            "state": state,
            "county": county,
            "site": site,
        }
    )
    # Never log the assembled URL because it contains credentials.
    with urlopen(f"{API_ENDPOINT}?{query}", timeout=120) as response:
        return json.load(response)


def main() -> None:
    email, key = credentials()
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    anchors["start_date"] = pd.to_datetime(anchors["start_date"])
    controls = pd.read_csv(CONTROLS_PATH, dtype="string")
    candidate_ids = set(controls["anchor_id"])
    candidates = anchors.loc[anchors["anchor_id"].isin(candidate_ids)]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    # Invalidate the previous manifest before any request so an interrupted refresh
    # cannot authorize stale responses in the downstream analysis.
    MANIFEST_PATH.write_text("[]\n", encoding="utf-8")
    for _, row in candidates.iterrows():
        anchor_id = str(row["anchor_id"])
        raw_path = RAW_DIR / f"{anchor_id}.json"
        temporary_path = raw_path.with_suffix(".json.tmp")
        if raw_path.is_file():
            raw_path.unlink()
        if temporary_path.is_file():
            temporary_path.unlink()
        try:
            payload = fetch_site(
                email,
                key,
                str(row["State Code"]),
                str(row["County Code"]),
                str(row["Site Num"]),
                pd.Timestamp(row["start_date"]),
            )
            serialized_payload = json.dumps(payload, indent=2)
            headers = payload.get("Header")
            if (
                not isinstance(headers, list)
                or not headers
                or not isinstance(headers[0], dict)
            ):
                raise ValueError("Hourly API response lacks a valid Header record.")
            header = headers[0]
            if header.get("status") != "Success":
                raise ValueError(
                    f"Hourly API returned non-success status: {header.get('status')!r}"
                )
            temporary_path.write_text(serialized_payload, encoding="utf-8")
            temporary_path.replace(raw_path)
            manifest.append(
                {
                    "anchor_id": anchor_id,
                    "state": str(row["State Code"]),
                    "county": str(row["County Code"]),
                    "site": str(row["Site Num"]),
                    "begin_date": (pd.Timestamp(row["start_date"]) - timedelta(days=75)).strftime("%Y%m%d"),
                    "end_date": (pd.Timestamp(row["start_date"]) + timedelta(days=75)).strftime("%Y%m%d"),
                    "api_status": header.get("status"),
                    "request_succeeded": True,
                    "record_count": len(payload.get("Data", [])),
                    "raw_path": str(raw_path),
                    "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                }
            )
            print(f"Downloaded hourly POC window for {anchor_id}")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            manifest.append(
                {
                    "anchor_id": anchor_id,
                    "state": str(row["State Code"]),
                    "county": str(row["County Code"]),
                    "site": str(row["Site Num"]),
                    "api_status": getattr(error, "code", None),
                    "request_succeeded": False,
                    "api_error": str(error),
                    "record_count": None,
                }
            )
            print(f"Hourly POC request failed for {anchor_id}: {error}")
    manifest_temporary_path = MANIFEST_PATH.with_suffix(".json.tmp")
    manifest_temporary_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest_temporary_path.replace(MANIFEST_PATH)
    print(f"Wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
