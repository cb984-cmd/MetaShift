"""Select representative real-anchor cases with deterministic, non-cherry-picked rules."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("artifacts/real_transition_88101_evidence_tiers.csv")
OUTPUT_PATH = Path("artifacts/real_transition_88101_case_study_selection.csv")


def diverse_select(
    candidates: pd.DataFrame, count: int, role: str, rationale: str
) -> list[dict[str, object]]:
    """Prefer different states and transition pairs, then retain deterministic order."""

    selected: list[dict[str, object]] = []
    seen_states: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    ordered = candidates.sort_values(
        ["absolute_standardized_score", "anchor_id"],
        ascending=[False, True],
        kind="stable",
    )
    for pass_index in range(3):
        for _, row in ordered.iterrows():
            if len(selected) >= count:
                break
            state = str(row["target_state"])
            pair = (str(row["old_method_code"]), str(row["new_method_code"]))
            if pass_index == 0 and (state in seen_states or pair in seen_pairs):
                continue
            if pass_index == 1 and state in seen_states:
                continue
            if any(item["anchor_id"] == row["anchor_id"] for item in selected):
                continue
            selected.append(
                {
                    "anchor_id": row["anchor_id"],
                    "case_group": role,
                    "selection_rank": len(selected) + 1,
                    "selection_rule": rationale,
                    "target_state": row["target_state"],
                    "old_method_code": row["old_method_code"],
                    "new_method_code": row["new_method_code"],
                    "evidence_tier": row["evidence_tier"],
                    "evidence_reasons": row["evidence_reasons"],
                    "absolute_standardized_score": row["absolute_standardized_score"],
                }
            )
            seen_states.add(state)
            seen_pairs.add(pair)
        if len(selected) >= count:
            break
    if len(selected) != count:
        raise ValueError(f"Only selected {len(selected)} of {count} required {role} cases.")
    return selected


def main() -> None:
    events = pd.read_csv(INPUT_PATH)
    events["absolute_standardized_score"] = events["standardized_score"].abs()
    selected = []
    selected.extend(
        diverse_select(
            events.loc[
                events["evidence_tier"] == "supported_candidate_discontinuity"
            ],
            3,
            "supported_candidate",
            "Highest absolute standardized score, preferentially diverse target states and transition pairs.",
        )
    )
    selected.extend(
        diverse_select(
            events.loc[
                (events["evidence_tier"] == "not_supported_by_available_evidence")
                & (events["audit_status"] == "complete")
            ],
            3,
            "not_supported",
            "Highest absolute standardized score among complete but unsupported events, preferentially diverse states and transition pairs.",
        )
    )
    inconclusive = events.loc[
        events["evidence_tier"] == "inconclusive_insufficient_evidence"
    ].copy()
    # For unavailable-counterfactual cases the score may be missing; alphabetical
    # ordering is a reproducible way to show the failure boundary.
    inconclusive["absolute_standardized_score"] = inconclusive[
        "absolute_standardized_score"
    ].fillna(-1.0)
    selected.extend(
        diverse_select(
            inconclusive,
            3,
            "inconclusive",
            "First deterministic high-information inconclusive cases under score then event-ID order; displays missing-evidence boundaries.",
        )
    )
    output = pd.DataFrame(selected)
    output.to_csv(OUTPUT_PATH, index=False)
    print(output.to_string(index=False))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
