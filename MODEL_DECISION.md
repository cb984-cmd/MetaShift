# MetaShift model decision

> **Integrity remediation complete (2026-08-31):** All cross-site results have
> been rebuilt with physical-site-unique geographic donors in
> `v0.3.2-evidence-final`. The
> decision not to claim MetaShift superiority remains in force.

**Decision date:** 2026-08-30  
**Decision:** Stop algorithm-optimization iterations and proceed on the
**MetaShift-Bench** route.

## Protected final test

The V2 target-event final test was defined as Illinois (`17`) and
Massachusetts (`25`). Its manifest contains 67 event identifiers with SHA256:

`452d7a0ceb8f9c0ce16a92efa0112b5ade052f1857cbd066998bfdcb24791290`

No performance result, selected shape, effect estimate, or test metric was
calculated for these target events during model development. The test-access
log records only the manifest-freezing action.

## Development evidence

Two bounded, pre-event-only optimization rounds were evaluated on development
target events. The values below are local-effect MAE on
`log(1 + PM2.5)` in the 40-event, five-strength development experiment.

| Method / round | Additive local MAE | Best non-MetaShift MAE | Relative change | Complex local-shape MAE |
| --- | ---: | ---: | ---: | ---: |
| Fixed reliability prior | 0.026464 | 0.024983 | +5.93% | 0.055894 |
| Per-event pre-period CV | 0.024945 | 0.024983 | -0.15% | 0.057211 |
| Standard synthetic control | 0.024983 | 0.024983 | reference | 0.060211 |

The cross-validated version modestly reduced the regional residual score
(0.059349 versus 0.060617 for standard synthetic control) but did not meet
the predefined 15% aggregate MAE-improvement criterion. It also did not show
a stable advantage across the complex local-shape profile.

## Rationale

The fixed reliability-prior round over-constrained donor weights for some
target states and larger injected shifts. The cross-validated round addressed
that mechanism, but its additive MAE gain was effectively zero and it worsened
the aggregate complex-shape profile. These constitute two consecutive rounds
without stable, predeclared improvement.

Further tuning against the same development cases would increase selection
bias. The final-test target states must not be used to rescue the algorithm
claim. Accordingly, the project will not claim that MetaShift is significantly
superior to standard synthetic control.

## Superseded preliminary synthetic runs

Early smoke and development runs injected synthetic effects at real Method Code
anchors. An unknown real discontinuity could therefore have been present beneath
the injected signal. Those numerical results are retained as implementation
diagnostics only and are excluded from all benchmark claims.

The replacement benchmark draws pseudo-anchors only from stable target and
donor method regimes. It contains 146 distinct physical target sites: 66
threshold-calibration sites and 80 evaluation sites, with five fixed effect
strengths per case. Calibration and evaluation have disjoint complete
target-plus-donor physical input footprints. Each local and matched regional
perturbation variant has 400 evaluation samples.

On the frozen `stable_full_v2` replacement benchmark, standard synthetic
control had local-effect MAE 0.09983, macro-F1 0.81641, AUPRC 0.91476, and
regional false-positive rate 0.140. Fixed reliability-prior and
cross-validated MetaShift had MAE 0.10344/0.09742, macro-F1 0.79515/0.80916,
AUPRC 0.89832/0.90178, and regional false-positive rate 0.150/0.135. The
paired 95% bootstrap interval for fixed reliability-prior MetaShift minus
standard synthetic control was [-0.00401, 0.01163]; the cross-validated interval was
[-0.00772, 0.00347]. Both cross zero. These results fail the algorithm-route
criterion for confidence-supported aggregate MAE improvement and do not
support a general superiority claim.

## MetaShift-Bench scope

The remaining contribution is a reproducible, metadata-anchored PM2.5
method-transition event benchmark and comparative audit:

1. reconstruct all 563 initial eligible events from EPA AQS data;
2. compare MetaShift and five baselines under identical event and donor rules;
3. complete six synthetic perturbation classes, placebos, key ablations, real
   event auditing, same-site POC/QA evidence, and independent 88502 analysis;
4. report coverage, exclusions, nulls, failure modes, and limitations; and
5. preserve the distinction between a reported Method Code transition and an
   independently confirmed physical instrument or measurement bias.

Any future result using Illinois/Massachusetts as part of the full benchmark
audit will be explicitly labeled as an observational benchmark audit, **not**
as V2 algorithm-test evidence and never used for model selection.
