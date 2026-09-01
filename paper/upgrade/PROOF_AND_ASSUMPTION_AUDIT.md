# Phase 2: Proof and Assumption Audit

**Phase 2 status: RESOLVED BY A SCOPED ROUTE 2.** The initial broad claim is
invalid, but Gate A now passes for the bounded theory contract in
[`THEORY_SPECIFICATION.md`](THEORY_SPECIFICATION.md). No v0.4 experiment,
protocol freeze, or manuscript rewrite was authorized while this initial
counterexample was investigated.

## Finding

The proposed v0.4 identifiability argument contains two assumptions that the
current v0.3.2 implementation does not satisfy across every perturbation
family. This is a theory-to-implementation scope defect in the proposed
upgrade, not a modification or invalidation of frozen v0.3.2 evidence.

A controlled, in-memory unit check of `metashift.synthetic.inject_perturbation`
and `scripts.run_stable_synthetic_benchmark.variant_specs` found:

| Paired family | Target arrays exactly equal under the v0.3.2 runner's seeds? |
| --- | --- |
| additive step | Yes |
| proportional step | Yes |
| gradual drift | Yes |
| temporary step | Yes |
| variance increase | No |

For the variance_increase pair, the maximum absolute difference in the
controlled check was `1.85364231151`. The runner derives a separate random
seed from each perturbation's `variant_index`; local variance and regional
variance therefore receive different target-noise realizations. Consequently,
the proposition `X^L = X^R` is not true for every v0.3.2 perturbation family.

The same check found that a raw additive shared shock has unequal increments on
the main log scale: `log1p(X + h) - log1p(X)` depends on `X`. Its controlled
target-versus-donor maximum difference was `0.0408217929896`. The v0.3.2
ranking score uses the log residual, so a raw_additive shared injection is not
an exact cancellation result for that score. The same nonlinearity applies to
raw proportional shocks because `log1p((1 + p)X) - log1p(X)` depends on `X`.

## Exact statements that match the implementation

Let `z_t = log1p(x_t)` and let the implementation's available-donor composite
be

```
q_t = sum_j(w_j * a_jt * z_jt) / sum_j(w_j * a_jt),
```

where `a_jt` indicates that donor `j` is available on date `t`; the
denominator is positive after the existing minimum-available-donor filter.
The effective weights therefore sum to one on each retained date, even when a
donor is missing.

For a transformed-scale shared perturbation satisfying

```
z'_target,t = z_target,t + h_t
z'_j,t      = z_j,t + h_t
```

for every available donor on the retained date, the implemented log residual
`r_t = z_target,t - q_t - b` satisfies `r'_t = r_t`. This is an exact
algebraic statement. It does not require that the stored nominal weights sum to
one before availability normalization, but it does require that the same
`h_t` reaches the target and every included donor.

The implementation also returns an auxiliary raw residual. Under a raw-scale
additive shared perturbation, that raw residual cancels exactly under the
analogous availability-normalized condition. However, v0.3.2 classification
and ranking use the log residual and standardized log score, so the raw-scale
statement cannot justify an exact claim about the primary ranking result.

## Claims that must not be made

- Do not state that all five frozen v0.3.2 local/regional families provide
  exact target-only observational equivalence.
- Do not describe raw_additive, raw proportional, raw drift, or raw variance
  regional injections as exact cancellation tests for the primary log score.
- Do not infer real-event causal attribution, physical instrument failure, or
  measurement bias from either algebraic result.
- Do not use approximate cancellation in existing v0.3.2 outcomes as proof of
  a theorem.

The target-only equivalence proposition can be used only for an explicitly
paired construction with one identical target realization in the local and
regional arms. For a deterministic score function, equal target arrays then
imply equal target-only scores. That statement is limited to the constructed
benchmark; it says nothing about all real-world single-series methods.

## Required v0.4 repair before Gate A

1. Specify a `pair_id` and a shared target perturbation realization for every
   local/regional pair, including stochastic variance changes.
2. Separate an **exact algebraic regime** from raw-scale stress-test regimes:
   the former must inject common additive perturbations on the exact residual
   scale; the latter must be reported as robustness tests rather than theorem
   verification.
3. Add code-level tests that fail on any unequal paired target array, unequal
   deterministic target-only score, or nonzero residual under the declared
   exact shared-shock regime.
4. State donor availability normalization, transform scale, common-shock
   scope, and non-causal interpretation in the formal proposition.
5. Re-run the theory audit before writing
   `THEORY_SPECIFICATION.md` or declaring Gate A passed.

No frozen v0.3.2 artifact was edited, regenerated, or reinterpreted while
performing this audit.

## Recovery disposition

The required repair has been implemented separately from the frozen
v0.3.2 generator:

1. `PERTURBATION_EQUIVALENCE_MATRIX.csv` classifies every frozen family and
   limits exact target identity to the four verified deterministic pairs.
2. `THEORY_SPECIFICATION.md` distinguishes algebraic transformed-scale
   invariance from raw floating-point verification within \(10^{-12}\), and
   gives clipping-aware approximate bounds for raw-scale stress cases.
3. `metashift/identifiability.py` requires a pair identifier, validates any
   recorded pair-derived seed, and records a canonical schedule hash.
4. `BLIND_SET_POWER_AND_FEASIBILITY.md` limits the isolated AQS source to
   non-confirmatory stress feasibility; it selects only a newly generated
   analysis-scale core for a later pre-outcome synthetic contract.

`THEORY_ROUTE_DECISION.md` selects Route 2. The tracked Gate A verifier and
theory-to-code tests must pass before the separate Phase 3 protocol is frozen.
