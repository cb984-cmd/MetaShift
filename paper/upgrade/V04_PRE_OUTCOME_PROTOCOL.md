# v0.4 Pre-Outcome Protocol: Identifiability Core and Stress Suite

**Status:** Protocol-only specification complete; it is not an execution freeze
until the runner is implemented, tested, committed, and separately tagged.
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
machine-readable abstention reasons. Bootstrap intervals resample synthetic
component IDs, never individual correlated event rows.

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
`v0.4.0-protocol-freeze`, but that tag alone cannot authorize execution. Before
the benchmark is generated, the complete runner and all its contract tests
must be implemented, committed, verified, and tagged
`v0.4.0-execution-freeze`. The runner must verify a clean worktree and that
HEAD equals the resolved execution-tag commit. It will atomically acquire a
durable attempt record and refuse every later attempt, even after a partial
failure. Its started, failed, or completed receipt must bind the protocol
SHA-256, execution commit and tag, input-allowlist hashes, complete event
accounting, and every output SHA-256.

Only pre-outcome unit and protocol-contract tests may run before the execution
freeze tag.
The full result files named in the output contract must not exist at freeze
time. Any implementation defect found before generating those files must be
fixed and reverified before the tag; a defect found after generation must
preserve the original receipt and be reported rather than silently rerunning.
