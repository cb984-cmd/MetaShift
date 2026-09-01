# Gate A Theory Route Decision

**Decision:** **Route 2 -- selected.**

The broad v0.3.2 theorem was correctly rejected. The retained architecture
uses exact target identity only where it is verified, a clipping-aware
approximate residual bound for raw-scale stress families, and a separate
theorem-aligned v0.4 analysis-scale core. It does not assert a frozen
variance-family distributional result.

| Route | Validity | Literature overlap | Implementation cost | Pre-outcome feasibility | Novelty contribution | Overclaim risk | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Route 1: exact identity, frozen distributional extension, approximate bounds, exact core, stress families | Invalid for frozen v0.3.2 because its variance records condition on unequal fixed seeds. | Observational equivalence and decision bounds are established theory. | Moderate. | The exact core is feasible, but a frozen distributional extension is not. | Would be misleadingly stronger than the evidence. | High. | Rejected. |
| Route 2: exact deterministic subset, approximate bounds, exact core, variance as stress only | Valid under the conditions in `THEORY_SPECIFICATION.md`. | Component methods and elementary propositions are known; the contribution is the bounded benchmark contract and task separation. | Low to moderate; the pair contract and tests exist. | A pre-outcome, independently generated core can be frozen before any outcomes. | Supports a narrow, auditable information-versus-scope benchmark contribution. | Lowest among substantive routes. | **Selected.** |
| Route 3: exact subset and exact core without approximate bounds | Valid but unnecessarily weak. | Same known elementary theory. | Low. | Feasible. | Loses the useful, testable link between target/donor mismatch and raw-scale stress behavior. | Low. | Not selected. |
| Route 4: no theorem-centric framing | A valid fallback if the core or pre-outcome protocol fails. | Detection, event accounting, and abstention are already closely related to existing work. | Low. | Feasible but less differentiated. | Does not yet justify abandoning the narrower valid contract. | Low. | Reserved fallback. |

## Rationale

Route 2 is the strongest scientifically supported path because it neither
changes the frozen v0.3.2 generator nor treats different pseudorandom seed
realizations as a proof of equal frozen-record distributions. Its exact
algebra is isolated to a newly defined analysis-scale construction with a
pair-specific schedule and explicit floating-point tolerance. Its raw-scale
extension is a bound, not a cancellation assertion.

The Phase 0 source audit does not identify a sufficiently powered external
monitoring-network validation source: it finds six non-overlapping metadata
components but does not establish outcome independence or adequate precision.
Accordingly, the selected pre-outcome core can support only a synthetic
theorem-to-code and selective-risk/coverage claim. The AQS components remain a
separate descriptive realism-stress possibility, not confirmatory evidence.

## Gate A decision

**Gate A: PASS, with the following immutable scope restrictions.**

1. Frozen v0.3.2 evidence is retrospective and unchanged.
2. Only the four verified deterministic frozen families support exact
   target-only matched-pair identity.
3. No frozen variance-family distributional equivalence is claimed.
4. Exact residual invariance is an algebraic property of the new analysis-scale
   core; its raw inverse/re-transform implementation is tested to \(10^{-12}\).
5. Raw-scale families are assumption-stress cases with stated bounds, not
   physical causal models or exact-cancellation evidence.
6. The planned synthetic result cannot establish a broad external monitoring
   claim, instrument replacement, physical failure, measurement bias, or
   algorithm superiority.

The resulting contribution is sufficiently substantive to justify a
pre-registered v0.4 protocol only as a narrow identifiability-aware auditing
benchmark. It must be abandoned or narrowed further if the protocol,
implementation, or one-time evaluation violates this contract.
