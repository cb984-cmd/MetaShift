# MetaShift execution plan

**Updated:** 2026-08-30  
**Research status:** MetaShift-Bench execution; algorithm-superiority claim closed.

## Evidence rule

The project is scoped as a metadata-anchored audit and evaluation benchmark.
MetaShift remains one transparent cross-site counterfactual estimator in the
comparison set; it is not claimed to outperform standard synthetic control.
A Method Code transition is a metadata anchor, not proof of physical instrument
replacement or measurement bias.

## Current checkpoint

- [x] Build 2019--2025 AQS 88101 canonical daily dataset and provenance manifest.
- [x] Extract 563 eligible persistent Method Code transitions.
- [x] Establish 271 events with at least three eligible geographic donors.
- [x] Identify and audit 11 same-site alternate-POC candidates.
- [x] Implement pre-anchor-only reliability-constrained counterfactual weights.
- [x] Implement single-station and cross-site baseline interfaces.
- [x] Run initial paired 30-event synthetic local-versus-regional benchmark.
- [!] Diagnose initial result: MetaShift separates local from regional shocks,
  but does not yet beat standard synthetic control on local effect MAE.
- [x] Narrow main contribution to a reproducible event benchmark, evidence
  hierarchy, and comparative audit after the held-out result did not support an
  enhanced-estimator claim.
- [x] Approve one bounded MetaShift v2 redesign with a new state-disjoint final
  target-event test set (Illinois and Massachusetts); the previously viewed
  v1 time test remains archived and unavailable for v2 tuning.
- [x] Run an initial V2 development-only audit without accessing final-test
  target states: 40 complete cases from 141 candidates, with 37 passing the
  pre-fit quality gate and 9 having a dynamic-placebo p-value at most 0.10.
  The 101 explicit exclusions show that complete-case coverage is 28.4%, so
  V2 must report coverage rather than silently analyze only favorable events.
- [x] Extend the synthetic runner to additive/proportional steps, gradual
  drift, temporary shifts, variance changes, and matched regional shocks; a
  five-event development smoke run completed all six variants. Full
  development-scale results remain pending.
- [x] Close bounded V2 optimization after two development rounds without stable
  improvement over standard synthetic control. The untouched Illinois and
  Massachusetts V2 test is not used to rescue the claim; see
  [`MODEL_DECISION.md`](MODEL_DECISION.md).
- [x] Replace superseded anchor-injection smoke experiments with a stable-regime
  benchmark: 80 distinct target monitors, 40 calibration / 40 evaluation,
  five fixed strengths, and 200 evaluation samples per local or matched
  regional perturbation family. The resulting algorithm metrics do not meet
  the stated algorithm-route release criteria.

## MetaShift-Bench execution

- [x] **M0 — Close bounded MetaShift v2.** The V2 primitives and two
  development rounds are retained as comparative evidence; no further
  optimization is permitted.
- [x] **B1 — Complete stable synthetic benchmark.** Six perturbation families
  have 200 independent evaluation samples each, with fixed seeds, threshold
  calibration separation, F1/AUPRC, effect error, coverage, and event-cluster
  bootstrap intervals.
- [ ] **B2 — Freeze benchmark release configuration.** Version event rules,
  seeds, perturbations, baseline definitions, metrics, and rerun the release
  benchmark without changing them.
- [x] **B3 — Audit all 563 real metadata anchors.** Report eligibility,
  pre-fit, effects, abstentions, and failure reasons without treating anchors
  as confirmed bias labels.

## Validation and analysis

- [ ] **V1 — Run real transition audit.** Report every eligible event's
  pre-fit, effect, uncertainty, and failure reason; do not select only strong
  examples.
- [x] **V2 — Analyze QA and same-site POC evidence.** Eleven same-site
  alternate-POC candidates have paired records; downloaded QA responses have
  no candidate with both target-POC matching and at least three pre/post QA
  records. Use them only as graded
  external consistency evidence, never as unquestioned physical ground truth.
- [x] **V3 — Run placebos and key ablations.** Time, donor-as-treated, date
  resampling, and regional-shock placebos are complete; reliability-prior and
  regularization ablations are complete.
- [x] **V4 — Run 88502 sensitivity analysis.** The separate 88502 scan has
  34 anchors but only 3 complete common-method comparisons; it is retained as
  a limited sensitivity result and is never mixed with 88101.

## Deliverables

- [ ] Reproducible benchmark tables and figures generated only from saved CSVs.
- [ ] Frozen result package, source manifest, run log, and environment record.
- [ ] Research report with limitations, null results, and contribution records.
