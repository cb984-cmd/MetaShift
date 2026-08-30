"""Immutable target-event split definitions and test-access audit utilities."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


V2_FINAL_TEST_STATES = frozenset({"17", "25"})


def canonical_event_ids(events: pd.DataFrame) -> list[str]:
    """Return the sorted identifiers used to hash an event split."""

    if "anchor_id" not in events.columns:
        raise ValueError("Events must contain an anchor_id column.")
    return sorted(events["anchor_id"].astype(str).tolist())


def split_sha256(events: pd.DataFrame) -> str:
    """Hash only target event IDs, not raw observations or performance results."""

    payload = "\n".join(canonical_event_ids(events)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def final_test_events(events: pd.DataFrame) -> pd.DataFrame:
    """Select the V2 held-out target-state events without calculating outcomes."""

    required = {"State Code", "anchor_id"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"Events lack split fields: {sorted(missing)}")
    return events.loc[events["State Code"].astype(str).isin(V2_FINAL_TEST_STATES)].copy()


def append_access_log(
    path: Path,
    *,
    action: str,
    purpose: str,
    split_hash: str,
    event_count: int,
) -> None:
    """Append an immutable-style record of access to held-out target IDs."""

    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "action": action,
        "purpose": purpose,
        "split_sha256": split_hash,
        "event_count": event_count,
    }
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(entry, sort_keys=True) + "\n")
