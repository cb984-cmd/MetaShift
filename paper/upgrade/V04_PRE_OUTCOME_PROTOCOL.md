# v0.4 Pre-Outcome Protocol: Identifiability Core and Stress Suite

**Status:** The initial `v0.4.0-protocol-freeze` tag is retained as a
protocol-only historical record. Its pre-execution audit identified missing
implementation-binding details before any result existed. The unrun
`v0.4.0-execution-freeze` tag is also retained as historical evidence: its
audit found that no independently committed post-execution result verifier was
present. Neither tag produced an output directory or attempt record. Both are
superseded before outcome generation by the corrected manifest and future
`v0.4.1-execution-freeze` tag. The current protocol state is
`execution_freeze_candidate`: it is not an execution freeze until the runner,
result verifier, tests, and source hashes are committed and separately tagged.
**Machine-readable authority:**
[`configs/v04_identifiability_protocol.json`](../../configs/v04_identifiability_protocol.json).

## Purpose and boundary

This protocol evaluates a narrow synthetic-contract claim:

> Under explicitly matched alternatives, target-only observations can detect a
> change yet contain no scope information for distinguishing a target-local
> change from a target-plus-donor change; comparative information can support a
> separate, selectively answered scope audit.

The protocol does not test whether MetaShift is superior to standard synthetic
control. It makes no causal claim about AQS Method Code anchors, instruments,
faults, bias, pollution truth, or real monitoring networks. Frozen v0.3.2
artifacts are not inputs to any v0.4 threshold, weight, model, or result
decision.

## Input and split contract

The primary source is a new, independently generated set of 360 synthetic
components: 120 calibration and 240 evaluation. The source contains no
physical-site identifiers or observations and cannot overlap the v0.3.2
294-site footprint. Each component has one target, four donors, 300 daily
observations, and a fixed anchor at day 180. The component generator, seed
offsets, analysis-scale parameters, raw conversion, and donor-missingness
rule are all fixed in the JSON authority.

The authoritative generator starts at 2030-01-01. It initializes the common
AR(1) process from its stated stationary normal distribution, draws its
chronological innovations first, then target innovations, then the
row-major donor innovation array. A separate deterministic availability seed
draws one uniform per date and, only when it falls below 0.10, one uniform
integer identifying the single missing donor. The complete numerical rules,
including stress seeds, raw-variance MAD definition, and interval endpoints,
are machine-readable in the protocol configuration.

No candidate AQS signal array, post-window observation, residual, fitted
weight, score, classification, tier, or forward-time data is accessed by this
protocol. The six isolated AQS metadata components remain a separately
possible, non-confirmatory stress source and are not read or selected here.

## Exact analysis-scale layer

For every component and each of two declared schedule families, the protocol
constructs one L/R pair and one N event:

| State | Target | Donors |
| --- | --- | --- |
| N | Base analysis-scale path | Base paths |
| L | Base target plus the shared pair schedule | Base donor paths |
| R | Same base target plus the same realized pair schedule | Every available base donor plus that schedule |

The schedule is exactly zero before the anchor. It is generated once from a
pair ID that excludes the scope label, recorded by canonical SHA-256, and
must keep every affected analysis-scale value in the inverse-transform domain.
The raw result is obtained with \(\exp(z)-1\). Thus L and R store exactly the
same target raw array, while their comparative input differs only in the donor
schedule.

The algebraic residual-invariance claim is exact over real arithmetic. The
actual raw inverse/re-transform execution is required to agree within
\(10^{-12}\), which is a numerical implementation condition rather than a
bitwise-equality claim.

## Predeclared evaluation

Weights are fixed at 0.25 per donor, then availability-normalized by the
existing estimator. No weights or model parameters are fitted from v0.4
outcomes. The target-only score is
\(\left|\operatorname{med}(z_\mathrm{post})-\operatorname{med}(z_\mathrm{pre})\right|\).
The calibration split alone selects:

1. the target-only N-versus-change detection threshold by macro-F1;
2. the comparative L-versus-R scope threshold by macro-F1; and
3. four selective-answer operating cutoffs, the 0, 25, 50, and 75 percent
   quantiles of calibration scope confidence.

The exact selected numeric values are unknown until calibration is generated.
Threshold candidates, tie-breaking, score direction, finite-score failure
handling, and linear quantile interpolation are fixed in the machine-readable
authority. They are recorded once and transferred unchanged to evaluation. Evaluation
reports complete N/L/R accounting, target-only L/R score identity, detection
metrics, forced-answer scope metrics, and answered-case risk/coverage with
machine-readable abstention reasons. Scope selection is based only on
comparative scope confidence: detection is deliberately reported as a separate
task and is not a scope-selection gate. Bootstrap intervals resample synthetic
component IDs, never individual correlated event rows.

If an operating point answers no evaluation cases, the output must report
coverage zero, a null answered-case error, and status `no_answered_cases`; it
must not call that zero risk. For bootstrap answered-case risk, only
replications with at least one answered case are eligible. The output records
their count and reports `insufficient_valid_repetitions` instead of fabricating
an interval if fewer than 950 of 1,000 are valid.

The expected totals are 720 calibration events, 1,440 evaluation events, and
1,440 L/R scope events overall. A mismatch, a violation of paired target
identity, a threshold-selection leak, or an unaccounted failure rejects the
run.

## Raw-scale stress layer

The separately frozen stress suite uses the same new synthetic panels, not
AQS. It applies five regional raw-scale perturbations: additive,
proportional, gradual, temporary, and shared variance. It reports only
residual-leakage bounds and whether they hold. The raw families are not
theorem evidence, physical models, or a performance contest. A failed bound
is an execution defect that blocks interpretation.

## One-time execution rule

The protocol-only specification may be tagged
`v0.4.0-protocol-freeze`, but that tag alone cannot authorize execution. The
unrun `v0.4.0-execution-freeze` tag also cannot authorize execution because it
lacks a precommitted post-execution result verifier. Before the benchmark is
generated, the complete runner, independent post-execution result verifier,
and all contract tests must be implemented, committed, verified, and tagged
`v0.4.1-execution-freeze`. An execution manifest will bind the corrected
protocol SHA-256 and hashes of every allowlisted source file at that tag. The
runner must verify a clean worktree, that HEAD equals the resolved
execution-tag commit through a local annotated tag, that `origin` exposes the
same peeled annotated tag commit, and that current input hashes match the tag.
It will
atomically acquire a
durable attempt record and refuse every later attempt, even after a partial
failure. Its started, failed, or completed receipt must bind the protocol
SHA-256, execution commit and tag, input-allowlist hashes, complete event
accounting, and every non-self payload output SHA-256; the durable attempt
record records the final receipt hash to avoid a self-referential checksum.
Source hashes use UTF-8 text bytes with CRLF normalized to LF, matching Git
blob content across Windows and non-Windows worktrees; generated output hashes
remain hashes of their exact written bytes.

Only pre-outcome unit and protocol-contract tests may run before the execution
freeze tag. The precommitted post-execution result verifier must recompute and
check receipt and payload hashes, N/L/R and split accounting, calibration-only
threshold provenance, scope risk/coverage and abstentions, component bootstrap
validity, raw-scale stress bounds, and the exact input allowlist before any
scientific interpretation. It first requires the same local annotated tag and
peeled `origin` tag, loads the protocol and manifest from Git blobs at that
tag, and confirms every allowlisted working-tree source hash matches its tagged
blob. Only then does it replay the deterministic core and stress suite in
memory; it never invokes the output-writing entrypoint or creates another
attempt record.
The full result files named in the output contract must not exist at freeze
time. Any implementation defect found before generating those files must be
fixed and reverified before the tag; a defect found after generation must
preserve the original receipt and be reported rather than silently rerunning.
