# Taxonomy human review packet

**Status:** Not reviewed; human action is required. This packet is a
metadata-only handoff template, not evidence that any transition represents a
physical instrument replacement, measurement bias, or causal mechanism.

## Frozen input

The packet transcribes exactly the 34 directed transition pairs from
[`configs/method_transition_taxonomy_v1.csv`](../../configs/method_transition_taxonomy_v1.csv),
whose canonical Git-LF SHA-256 is
`31485dc86fd1d3dd9715bc9f1057856dab8d89e399ebbaaff206374f76b4fcf2`.
That source was frozen in `v0.3.2-evidence-final`; it contains Method Codes,
reported Method Names, proposed metadata-only classes, and predeclared
official-source locators. It contains no outcome, effect, residual, evidence
tier, prediction, score, threshold, or post-transition-ranking field.
The verifier normalizes Windows CRLF checkouts to those Git-LF bytes before
checking the source identity.

[`TAXONOMY_HUMAN_REVIEW_PACKET.csv`](TAXONOMY_HUMAN_REVIEW_PACKET.csv)
provides one row per pair. Every row deliberately begins with
`human_review_decision = pending_human_review`; all human evidence, initials,
dates, and notes are blank.

## Required human procedure

1. Independently access each row's `frozen_official_source` and record a
   stable, row-specific source locator, page/section or document revision, and
   UTC access time in a working copy outside Git.
2. Check that the old and new Method Codes and Method Names are accurately
   represented by the cited official source. Review the proposed analyzer
   family, transition class, Network Data Alignment flag, and
   same-hardware-family flag only from those metadata sources.
3. Set the working-copy decision to exactly one of
   `confirmed_as_recorded`, `revised_by_human`, or
   `unresolved_after_human_review`. A pending or unresolved row is not
   eligible for stratification.
4. A student reviewer and supervising teacher must separately record initials
   and the review date for every finalized row. They must reconcile any
   disagreement and preserve the supporting source locator.
5. Keep signed records, personal identifiers, and any completed working copy
   outside Git. Do not overwrite the tracked blank packet or modify the frozen
   v1 source table as a substitute for this review.

## Acceptance boundary

No taxonomy-stratified computation, figure, result, or manuscript claim may
begin until all 34 rows have independent human decisions, accessible official
source evidence, reconciliation of discrepancies, and explicit student/teacher
approval. Even after approval, a reviewed taxonomy supports descriptive
metadata strata only; it does not prove equipment history or a causal
measurement effect.

`scripts/verify_taxonomy_human_review_packet.py` verifies that the tracked
template retains exact 34-row frozen-source coverage and has not auto-filled a
human review. It cannot and does not validate a completed human review.
