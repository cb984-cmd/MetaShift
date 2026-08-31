"""Build a saved coordinate table for all audited AQS metadata anchors."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_path in (PROJECT_ROOT, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scan_data_gate import DEFAULT_CONFIG, SERIES_KEYS, ensure_archives, load_canonical_signal  # noqa: E402


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
AUDIT_PATH = Path("artifacts/real_transition_88101_event_audit.csv")
TIERS_PATH = Path("artifacts/real_transition_88101_evidence_tiers.csv")
OUTPUT_PATH = Path("artifacts/real_transition_88101_anchor_coordinates.csv")


def main() -> None:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    audit = pd.read_csv(AUDIT_PATH, dtype="string")[
        ["anchor_id", "audit_status"]
    ]
    tiers = pd.read_csv(TIERS_PATH, dtype="string")[
        ["anchor_id", "evidence_tier"]
    ]
    data = load_canonical_signal(
        ensure_archives(Path("data/raw"), DEFAULT_CONFIG.years, download=False),
        "88101",
    )
    coordinates = (
        data.groupby(SERIES_KEYS, observed=True)[["Latitude", "Longitude"]]
        .median()
        .reset_index()
    )
    output = (
        anchors.merge(coordinates, on=SERIES_KEYS, how="left")
        .merge(audit, on="anchor_id", how="left")
        .merge(tiers, on="anchor_id", how="left")
    )
    if output[["Latitude", "Longitude"]].isna().any().any():
        raise ValueError("One or more anchors have no canonical AQS coordinates.")
    output.to_csv(OUTPUT_PATH, index=False)
    print(
        {
            "anchors": len(output),
            "audit_statuses": output["audit_status"].value_counts().to_dict(),
            "evidence_tiers": output["evidence_tier"].value_counts().to_dict(),
        }
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
