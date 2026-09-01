# v0.5 Pre-outcome Protocol: Scope Answerability Frontier

**Protocol ID:** `v0.5-answerability-frontier`
**Status:** pre-execution design; no v0.5 evaluation artifact, attempt record, or
execution tag exists when this protocol is written.

## Research target

The protocol studies **synthetic scope answerability**, conditional on a
constructed target change. It asks whether a target-only channel or a
comparative target-plus-donor channel can answer a binary local-versus-shared
scope question at fixed observed held-out error tolerances. It does not study
real AQS mechanism, instrument replacement, causal bias, estimator superiority,
or an external-evidence channel.

The exact formal channel definitions, target-only limit, partial-scope algebra,
and structural-certificate conditions are in
[`V05_SCOPE_ANSWERABILITY_THEORY.md`](V05_SCOPE_ANSWERABILITY_THEORY.md).

## Design before outcomes

Each independently seeded component has 300 synthetic dates, a fixed anchor at
date index 180, one target, and four donors. The complete Cartesian grid has
640 cells:

\[
5\ q\text{ levels}\times4\ H\text{ levels}\times
2^5\text{ nuisance settings}=640.
\]

There are 120 calibration and 360 evaluation components, producing 76,800 and
230,400 matched-pair rows respectively. Every pair has two scope arms:

1. **Local:** the target receives the positive analysis-scale signal \(H\); no
   donor receives it.
2. **Shared:** the *identical target* receives \(H\); donor \(j\) receives
   \(\lambda_jH\).

The generator applies mismatch, availability, raw-scale common field, and
donor contamination identically in both arms after the scope distinction.
Target digests are required to be identical inside every pair and across every
`target_group_id`. At \(q=0\), the full comparative observation is also
identical between arms; it is reported as an impossibility negative control.

## Scope policies

The fixed policy set is:

| Policy | Allowed channel | Answer behavior |
| --- | --- | --- |
| Target-only forced | Target score only | Always predicts local |
| Comparative forced | Signed residual score | Calibration-only macro-F1 threshold |
| Confidence-selective comparative | Signed residual score | Calibration-only confidence cutoff separately selected for each tolerance |
| Certificate-selective comparative | Score plus declared synthetic design bounds | Abstains unless its robust structural interval separates |

The third policy must not be described as a risk guarantee. The fourth policy
is a simulation-design-information-assisted diagnostic: it sees known
participation and bounded-noise parameters unavailable in ordinary deployment.

The finite-policy frontier is calculated on held-out evaluation rows only after
all policies have been applied. At each reporting tolerance it considers every
predeclared confidence policy, including policies calibrated to a different
tolerance, plus the forced policy. It is not used to select a new policy.

## Structural abstention and partial scope

All \(0<q<1\) settings are binary-label `shared` arms, while remaining visibly
separate in every result table. A certificate must abstain on:

- every \(q=0\) pair;
- every pair whose predeclared lower structural margin is nonpositive; and
- every pair with a contract failure or envelope violation.

It may answer an intermediate shared arm only when its sufficient interval
condition is positive. This does not mean that partial scope is intrinsically
ambiguous, nor does it identify the numerical \(q\) or a physical mechanism.

## Blinding and execution contract

Calibration and evaluation have disjoint component identifiers and seed
streams. Only calibration rows can enter threshold or confidence-cutoff
selection. No pair IDs, component IDs, row ordering, target hashes,
participation, availability summaries, labels, oracle quantities, or grid
factor names can enter target-only or comparative score policies.

The future execution entrypoint will reject a dirty checkout, absent/mismatched
annotated remote tag, stale source binding, existing result directory, existing
attempt record, missing grid cell, duplicate grid cell, nonfinite output,
target-identity failure, and calibration/evaluation mixing. The source bundle,
result verifier, lockfile-bound CPython/runtime package contract, and figure
generator must be committed and hash-bound before the sole authorized
execution. Figure rendering will require successful tagged-source replay,
receipt hashes, attempt chain, schemas, and all result-verifier checks.

Before it creates a local attempt record, the executor must atomically push a
new annotated `v0.5.0-answerability-execution-claim` tag. A concurrent or
subsequent conforming checkout cannot push that tag and must refuse execution.
The remote claim binds the execution commit, freeze tag, protocol hash,
execution-manifest hash, allowlisted-source-bundle hash, and runtime-contract
hash; its annotated tag object is bound into the receipt and later compared to
the remote ref. Remote deletion or direct bypass of the executor is a
repository permission violation, not an allowed second run.
Immediately after that claim, the executor exclusively persists a `claimed`
attempt record before allocating the output directory; a directory-allocation
failure is retained as `claim_acquired_setup_failed`.

## Planned reports

The frozen result bundle must retain all policies, all grid cells, all
tolerances, q=0 outcomes, certificate failures, envelope violations, and
unfavorable results. It must produce the answerability frontier, Scope
Answerability Gain, policy risk/coverage table, component-cluster bootstrap,
normalized-margin phase diagram, risk--coverage plot, certificate-validity
table, and failure-mode map directly from preserved outputs.
