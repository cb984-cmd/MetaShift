"""Create the V2 target-event test manifest without evaluating those events."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.splits import (
    V2_FINAL_TEST_STATES,
    append_access_log,
    final_test_events,
    split_sha256,
)


ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
MANIFEST_PATH = Path("configs/v2_final_test_manifest.json")
ACCESS_LOG_PATH = Path("artifacts/test_access_log.jsonl")


def main() -> None:
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    test_events = final_test_events(anchors)
    digest = split_sha256(test_events)
    manifest = {
        "purpose": "MetaShift v2 state-disjoint final target-event evaluation",
        "target_states": sorted(V2_FINAL_TEST_STATES),
        "event_count": len(test_events),
        "event_id_sha256": digest,
        "outcome_accessed": False,
        "status": "Frozen target IDs only; no performance result has been calculated.",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    append_access_log(
        ACCESS_LOG_PATH,
        action="freeze_manifest",
        purpose="Hash held-out target event identifiers without evaluating outcomes.",
        split_hash=digest,
        event_count=len(test_events),
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
