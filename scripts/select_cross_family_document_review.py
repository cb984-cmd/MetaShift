"""Freeze an outcome-blind cross-analyzer-family public-document review sample."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import deque
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from metashift.taxonomy import load_transition_taxonomy  # noqa: E402


CONFIG_PATH = Path("configs/cross_family_document_review_v1.json")
ANCHORS_PATH = Path("artifacts/data_gate/anchor_inventory.csv")
OUTPUT_PATH = Path("artifacts/cross_family_document_review_selection_v1.csv")
MANIFEST_PATH = Path("artifacts/cross_family_document_review_selection_v1_manifest.json")


def selection_hash(anchor_id: str) -> str:
    """Return an OS-independent deterministic tie-breaker for an anchor."""

    return hashlib.sha256(anchor_id.encode("utf-8")).hexdigest()


def select_round_robin(
    candidates: pd.DataFrame, sample_size: int
) -> pd.DataFrame:
    """Select an outcome-blind, pair-stratified deterministic sample."""

    if sample_size <= 0:
        raise ValueError("Document-review sample size must be positive.")
    if len(candidates) < sample_size:
        raise ValueError(
            f"Only {len(candidates)} eligible cross-family anchors for "
            f"requested sample size {sample_size}."
        )
    ranked = candidates.copy()
    ranked["selection_hash"] = ranked["anchor_id"].astype(str).map(selection_hash)
    ranked["transition_pair"] = (
        ranked["previous_method_code"].astype(str)
        + " -> "
        + ranked["method_code"].astype(str)
    )
    ranked["transition_pair_anchor_count"] = ranked.groupby(
        "transition_pair"
    )["anchor_id"].transform("size")
    pair_order = (
        ranked.loc[:, ["transition_pair", "transition_pair_anchor_count"]]
        .drop_duplicates()
        .sort_values(
            ["transition_pair_anchor_count", "transition_pair"],
            ascending=[False, True],
            kind="stable",
        )
    )
    queues = {
        pair: deque(
            group.sort_values(["selection_hash", "anchor_id"], kind="stable")
            .to_dict("records")
        )
        for pair, group in ranked.groupby("transition_pair", sort=False)
    }
    selected: list[dict[str, object]] = []
    while len(selected) < sample_size:
        progressed = False
        for pair in pair_order["transition_pair"]:
            queue = queues[str(pair)]
            if not queue:
                continue
            selected.append(queue.popleft())
            progressed = True
            if len(selected) == sample_size:
                break
        if not progressed:
            raise RuntimeError("Round-robin selection exhausted before target size.")
    result = pd.DataFrame(selected)
    result.insert(0, "selection_rank", range(1, len(result) + 1))
    result["selection_basis"] = (
        "Outcome-blind transition-pair round-robin; SHA256(anchor_id) tie-breaker."
    )
    return result.sort_values("selection_rank", kind="stable").reset_index(drop=True)


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    anchors = pd.read_csv(ANCHORS_PATH, dtype="string")
    taxonomy = load_transition_taxonomy(Path(config["taxonomy_path"]), anchors)
    candidates = anchors.merge(
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
        how="inner",
        validate="many_to_one",
    )
    candidates = candidates.loc[
        candidates["transition_class"] == config["eligible_transition_class"]
    ].copy()
    selected = select_round_robin(candidates, int(config["sample_size"]))
    retained_columns = [
        "selection_rank",
        "anchor_id",
        "State Code",
        "County Code",
        "Site Num",
        "POC",
        "start_date",
        "previous_method_code",
        "previous_method_name",
        "method_code",
        "method_name",
        "old_analyzer_family",
        "new_analyzer_family",
        "transition_class",
        "nda_related",
        "transition_pair",
        "transition_pair_anchor_count",
        "selection_hash",
        "selection_basis",
    ]
    selected = selected.loc[:, retained_columns]
    if len(selected) != int(config["sample_size"]):
        raise RuntimeError("Document-review selection did not reach the frozen size.")
    manifest = {
        "analysis_id": config["analysis_id"],
        "selected_anchor_count": len(selected),
        "eligible_cross_family_anchor_count": len(candidates),
        "selection_rule": config["selection_rule"],
        "selection_inputs": config["selection_inputs"],
        "forbidden_selection_inputs": config["forbidden_selection_inputs"],
        "outcome_data_read": False,
        "taxonomy_review_statuses": sorted(taxonomy["review_status"].unique().tolist()),
        "interpretation_boundary": config["interpretation_boundary"],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(OUTPUT_PATH, index=False)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(selected.to_string(index=False))


if __name__ == "__main__":
    main()
