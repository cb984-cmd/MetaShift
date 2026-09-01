# Gate A Recovery Log

**Status:** Gate A passed via the scoped Route 2 decision. This log records
the failed broad formulation and the narrower retained propositions. It does
not alter the frozen `v0.3.2-evidence-final` artifacts and is not a claim of
priority.

## Rejected formulation: one exact theorem for all v0.3.2 families

**Attempted claim:** Every v0.3.2 local/regional pair has the same target path,
and every regional perturbation exactly cancels in the primary residual.

**Counterexamples:**

1. `variance_increase` uses different fixed `variant_index` inputs in
   `benchmark_seed`. The local and regional stored target arrays therefore
   differ; the controlled maximum absolute difference is
   `1.85364231151`.
2. The primary residual uses `log1p(clip(raw, lower=0))`. A shared raw
   additive or proportional perturbation has a value-dependent transformed
   increment, so it cannot generally cancel exactly. The controlled additive
   target/donor increment difference is `0.0408217929896`.

**Disposition:** Rejected. See
[`PROOF_AND_ASSUMPTION_AUDIT.md`](PROOF_AND_ASSUMPTION_AUDIT.md) and
[`PERTURBATION_EQUIVALENCE_MATRIX.csv`](PERTURBATION_EQUIVALENCE_MATRIX.csv).

## Retained formulation: exact target-only equivalence

**Scope:** The four deterministic frozen families: additive step,
proportional step, gradual drift, and temporary step.

**Claim:** Their matched local and regional records have exactly the same
target array. Therefore any deterministic statistic that receives only that
array has exactly the same value in the matched pair.

**Evidence:** `tests/test_v04_theory_scope.py` creates every frozen pair using
the runner's seed rule and verifies exact array equality for the four
deterministic families. This is a constructed-benchmark input statement, not
a claim about all real single-station procedures.

**Disposition:** Retained as an exact, bounded proposition.

## Rejected formulation: frozen variance as a distributional proof

**Attempted claim:** Different variance arrays nevertheless prove equality in
distribution.

**Reason rejected:** The v0.3.2 evaluation fixes an unequal seed for each arm.
Conditional on those recorded seeds, each pseudorandom target array is
deterministic and unequal. The code uses the same Gaussian branch and
parameters, but it does not define an arm-invariant random-seed experiment.

**Disposition:** Do not claim a distributional result for frozen records. A
future distributional proposition must explicitly randomize or share the
innovation independently of the arm label.

## Retained formulation: clipping-aware approximate residual bound

**Scope:** Shared raw additive, proportional, drift, and temporary
perturbations; regional variance only as a conditional stress-family bound,
not as a paired target-equivalence result.

**Claim:** On each retained date, the primary residual contribution from a
shared raw-scale perturbation is bounded by its transformed-increment
Lipschitz constant times the availability-normalized target/donor mismatch.

**Evidence:** The analytic conditions and median extension are specified in
[`THEORY_SPECIFICATION.md`](THEORY_SPECIFICATION.md). Numerical tests cover
the clipping rule, availability normalization, the sharper nonnegative-domain
additive constant, proportional changes, and median stability in
`tests/test_v04_identifiability_core.py`.

**Disposition:** Retained. It is an applicability bound, not causal
identification and not an exact cancellation claim.

## Retained formulation: a separate exact analysis-scale core

**Claim:** A new v0.4 pair with one declared `pair_id`, one schedule hash, one
shared target schedule, and transformed-scale regional donor increments has
exact target identity and algebraic primary-residual invariance over the real
numbers. The raw inverse/re-transform implementation verifies numerical
invariance within a declared floating-point tolerance.

**Evidence:** `metashift/identifiability.py` constructs the pair without
modifying v0.3.2. The pair-specific schedule seed contains no scope arm label.
`tests/test_v04_identifiability_core.py` checks equal target arrays and
residual invariance within \(10^{-12}\) after the raw round trip, including
missing donors and availability normalization.

**Disposition:** Retained pending the independent Gate A verification and
pre-outcome protocol freeze.
