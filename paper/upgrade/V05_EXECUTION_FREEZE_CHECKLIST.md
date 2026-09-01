# v0.5 Execution-Freeze Checklist

**Status:** pre-freeze. This checklist must be completed before the annotated
`v0.5.0-answerability-freeze` tag is created. It is intentionally not evidence
of a completed execution.

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
- [ ] CI passes from the final pre-execution commit.
- [x] Manual source/diff and read-only provenance audits confirm no v0.3.2/v0.4
  frozen file changed.

## Freeze and one-time execution

- [ ] Generate `configs/v05_answerability_execution_manifest.json` from final
  tracked source hashes.
- [ ] Change protocol state to `execution_freeze_candidate`; rerun tracked-only
  protocol verifier with no v0.5 output present.
- [ ] Commit the complete pre-outcome source state.
- [ ] Create and push an annotated `v0.5.0-answerability-freeze` tag pointing
  exactly to that commit.
- [ ] Verify clean checkout, local/remote peeled-tag equality, source hashes,
  and output absence.
- [ ] Atomically create and push the remote execution-claim tag; preserve it
  even if the subsequent local execution fails.
- [ ] Execute `python scripts/run_v05_answerability_frontier.py --execute`
  exactly once.
- [ ] Run the read-only result verifier, preserve every output and receipt hash,
  then render figures from receipt-verified artifacts.

No weak result, failed certificate, or unexpected coverage value permits a
second execution or outcome-driven protocol revision.
