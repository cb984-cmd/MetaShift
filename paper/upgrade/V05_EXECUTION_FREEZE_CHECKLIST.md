# v0.5 Execution-Freeze Checklist

**Status:** completed and frozen. The pre-execution checklist remains a record of
its original gate; the verified post-execution facts are appended below and are
not a basis for rerunning or revising the protocol.

## Theory and design

- [x] Scope channels, frontier, gain, target-only scope limit, and nested-channel
  monotonicity are scoped in `V05_SCOPE_ANSWERABILITY_THEORY.md`.
- [x] The partial-scope result uses an analysis-scale affine score and
  availability-normalized weights.
- [x] The nominal-midpoint shortcut, unbounded-noise certificate, and raw-scale
  exactness claim are rejected in the adversarial audit.
- [x] Full 640-cell grid, q=0 negative control, intermediate abstention rule,
  calibration/evaluation split, and policy list are declared before outcomes.
- [x] Component-count and dependence-aware uncertainty limits are documented.
- [x] Focused literature audit has a bounded no-priority statement.

## Implementation and verification

- [x] Target-fixed pair generation, q=0 observation identity, availability
  normalization, raw leakage, robust certificate, and calibration isolation
  have direct tests.
- [x] Vectorized score implementation is cross-checked against
  `anchor_residual_windows` over every grid cell for one independent component.
- [x] Tests reject missing grid cells, target-identity corruption, external
  input paths, stale source hashes, incomplete schemas, and evaluation-side
  fitting.
- [x] Result schemas, failure map, certificate table, component bootstrap, and
  source-bound read-only replay verifier are implemented.
- [x] Figure generator requires successful full frozen-result verification
  before it reads receipt-hashed artifacts.
- [x] The requirements lock, CPython version, and installed package versions
  are part of the source-bound runtime contract.
- [x] All 150 existing unit tests pass with the v0.5 files present in the
  locked CPython 3.13 environment.
- [x] Remote one-time claim acquisition and the post-claim
  `claim_acquired_setup_failed` path have direct regression coverage.
- [x] CI run `33509140737` passed from the final pre-execution commit
  `14fd0fee4fb015e6c661299041e35ff704a27286`.
- [x] Manual source/diff and read-only provenance audits confirm no v0.3.2/v0.4
  frozen file changed.

## Freeze and one-time execution (completed)

- [x] Generate `configs/v05_answerability_execution_manifest.json` from final
  tracked source hashes.
- [x] Change protocol state to `execution_freeze_candidate`; rerun tracked-only
  protocol verifier with no v0.5 output present.
- [x] Commit the complete pre-outcome source state:
 `14fd0fee4fb015e6c661299041e35ff704a27286`.
- [x] Create and push an annotated `v0.5.0-answerability-freeze` tag pointing
 exactly to that commit.
- [x] The freeze-tagged execution manifest records output absence when it was
 created; the post-execution provenance audit verifies local/remote peeled-tag
 equality and every frozen source hash.
- [x] Atomically create and push the remote execution-claim tag; preserve it
 even if the subsequent local execution fails.
- [x] Execute `python scripts/run_v05_answerability_frontier.py --execute`
 exactly once; the durable attempt is `completed` with `failure_count: 0`.
- [x] Run the read-only result verifier and preserve every output and receipt
 hash. The result verifier was reported successful after execution; the receipt
 and attempt are sealed by `configs/v05_frozen_result_manifest.json`.

## Verified post-execution audit

- [x] The execution receipt records all expected accounting: 307,200 pair rows,
 614,400 scope-arm events, and 61,440 q=0 pair rows.
- [x] The receipt records target/pair identity, q=0 comparative-observation
 identity, and all 640 grid cells as satisfied.
- [x] The receipt's implementation-semantics check passed over 640 cells
 (maximum absolute difference `1.6653345369377348e-16`, tolerance `1e-12`).
- [x] `verify_v05_protocol_freeze.py --allow-existing-outputs` passes as a
 post-execution, read-only contract check.
- [x] Under the receipt-pinned CPython 3.13.14 environment with NumPy `2.5.2`,
 `verify_v05_frozen_result_provenance.py --verify-results` passes all byte,
 schema, receipt/attempt, annotated-tag, frozen-source, and full deterministic
 result-verifier checks. No output was changed by that check.
- [x] The historical unpinned local environment is not treated as a successful
 full replay: its NumPy `2.4.6` differs from receipt-pinned NumPy `2.5.2`, so
 the full verifier fails closed at runtime provenance. This failure remains
 recorded as validation of the runtime boundary, not as a frozen-result
 failure.
- [x] `V05_EXECUTION_AUDIT.md` records favorable and unfavorable outcomes,
 q=0 treatment, certificate limits, artifact bindings, and verifier status.

No weak result, failed certificate, or unexpected coverage value permits a
second execution or outcome-driven protocol revision.
