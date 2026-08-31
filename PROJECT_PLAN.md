# MetaShift execution plan

**Updated:** 2026-08-31
**Research status:** MetaShift-Bench paper-strengthening extension active;
algorithm-superiority claim closed.

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
  benchmark: 146 distinct physical target sites, 66 calibration / 80
  evaluation, five fixed strengths, and 400 evaluation samples per local or
  matched regional perturbation variant. The complete input footprints are
  disjoint, and clean default/locked-environment reconstructions match.

## MetaShift-Bench execution

- [x] **M0 — Close bounded MetaShift v2.** The V2 primitives and two
  development rounds are retained as comparative evidence; no further
  optimization is permitted.
- [x] **B1 — Complete stable synthetic benchmark.** The input-isolated
  benchmark has six perturbation families with 400 independent evaluation
  samples each, fixed seeds, threshold calibration separation, F1/AUPRC, effect
  error, coverage, and event-cluster bootstrap intervals.
- [x] **B2 — Freeze benchmark release configuration.** The corrected manifest
  hash is `4e0f66af...1b1ca01b`; default and locked-environment reconstructions
  matched every one of 34 core result hashes.
- [x] **B3 — Audit all 563 real metadata anchors.** Report eligibility,
  pre-fit, effects, abstentions, and failure reasons without treating anchors
  as confirmed bias labels.
- [x] **B4 — Quantify real-event uncertainty and donor dependence.** All 261
  complete cross-site events have 1,000-repetition conditional block-bootstrap
  intervals; leave-one-donor-out sensitivity completes all removals for 260
  events and records the single unavailable removal.
- [x] **B5 — Synthesize observational evidence tiers.** All 563 anchors are
  transparently categorized as supported candidate (36), not supported (113),
  or inconclusive (414) using fixed quality, selection-aware nested interval,
  50--100 date placebo/FDR, and donor-sensitivity diagnostics; no tier is a
  physical-causality label.

## Validation and analysis

- [x] **V1 — Run real transition audit.** Report every eligible event's
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
- [x] **V5 — Revise evidence commitments to match available labels.** The
  protocol no longer claims a labeled real exceptional-event accuracy analysis;
  it defines the completed synthetic regional, time, and donor placebos as
  environmental negative controls and records QA limitations.

## Deliverables

- [x] Reproducible benchmark tables and six figures generated only from saved
  CSVs.
- [x] Frozen configuration, source manifests, run manifest, test-access log,
  two-environment hash comparison, and machine-readable
  `results/release_gate.json`. The prior v0.1.0 release applies to the
  superseded split; the corrected evidence is v0.2.0.
- [x] Evidence-backed English research-report draft and claim-to-artifact map,
  with identity, contribution, and AI-disclosure verification placeholders.

## Final code-stage result

## Post-review remediation

- [x] Detect and retire the prior synthetic split's target/selected-donor
  overlap across calibration and evaluation.
- [x] Rebuild deterministic connected components of the complete
  target-plus-donor physical-site graph: 66 calibration targets and 80
  evaluation targets now have zero shared input sites.
- [x] Recompute the primary synthetic benchmark, reliability ablations,
  main/ablation alignment, risk-coverage curve, and the 45/60/90-day
  method-stability-aware window sensitivity locally.
- [x] Make release-gate failure exit nonzero, block stale/failed evidence-bundle
  export, and invalidate hourly API responses unless their fresh manifest hash
  matches. A direct refresh accepted 9/11 current hourly POC responses and
  retained two API failures as unavailable.
- [x] Centralize synthetic random seeds and verify all 7,300 shared Standard
  SC rows match exactly between the primary benchmark and ablation experiment.
- [x] Add conditional 1,000-repetition moving-block intervals for all 261
  complete real events and three cross-site methods.
- [x] Add leave-one-donor-out refits: 260 events completed every removal; one
  unavailable removal is retained with its reason.
- [x] Revise the protocol to remove an unsupported labeled real
  exceptional-event claim while retaining synthetic regional, time, and donor
  negative controls.
- [x] Add `requirements-lock.txt` and public GitHub Actions unit-test CI.
- [x] Rebuild under the corrected fixed configuration in default and lock-file
  environments; 34 core-result hashes match exactly.
- [x] Publish a new safe, versioned evidence bundle after a final sensitive-data
  scan:
  [v0.2.0-paper-evidence](https://github.com/cb984-cmd/MetaShift/releases/tag/v0.2.0-paper-evidence)
  points to the verified evidence commit
  [`a738f03`](https://github.com/cb984-cmd/MetaShift/commit/a738f039915abadfce37c274f210578e9319310e).
  The prior
  [v0.1.0-benchmark-evidence](https://github.com/cb984-cmd/MetaShift/releases/tag/v0.1.0-benchmark-evidence)
  release documents the superseded split and is not the paper-evidence release.
- [x] Attach a complete public-safe process archive to v0.2.0: 269 safe
  generated outputs, an exact source snapshot, and Git history. Its manifest
  records every file hash and explicitly excludes raw EPA archives, raw AQS API
  responses, credentials, and virtual environments.

**Baseline code and research stage:** complete for the MetaShift-Bench route.
The algorithm-superiority route remains closed: on the corrected stable
benchmark, MetaShift's lower effect-MAE point estimates versus standard
synthetic control still have bootstrap confidence intervals crossing zero,
while Macro-F1/AUPRC do not meet the predeclared algorithm thresholds. The
publishable contribution is the reproducible benchmark, full metadata-anchor
audit, graded evidence hierarchy, comparative results, and documented
applicability boundary.

## Paper-strengthening extension

The v0.2.0 release is retained as an immutable archived baseline. New analyses
are governed by `configs/paper_extension_protocol_v1.json`; they cannot select
or tune against the already viewed 80-site stable-synthetic evaluation set.

- [x] **E0 — Freeze extension protocol.** Define taxonomy, observational
  stratification, uncertainty-calibration, representativeness, and new-model
  boundaries before reading extension outcomes.
- [!] **E1 — Freeze and review Method Code taxonomy.** A 34-pair,
  metadata-only table covers all 563 anchors and is validated without outcome
  data. Student/teacher row-level review is required before stratification.
- [!] **E2 — Calibrate synthetic uncertainty intervals.** The frozen 66/80
  run completed 23,360 known-effect instances with 1,000 repetitions each.
  Conditional nominal-95% intervals undercovered on evaluation (62.47%--67.56%
  by method), while target-cluster nominal-90% split-conformal intervals
  overcovered (98.22%--99.56%). No post-evaluation tuning is permitted; fixed
  intervals are conditional diagnostics, not coverage-calibrated confidence
  intervals.
- [ ] **E2b — Test selection-aware interval coverage.** The current synthetic
  coverage result applies to fixed-weight conditional intervals. Any
  selection-aware coverage study requires a separately frozen, computationally
  feasible protocol and may not tune against the viewed 80-site split.
- [x] **E3 — Analyze auditability and selection boundaries.** v2 retains all
  563 anchors, including one separate “Outside EPA mapped regions” record, and
  excludes effect estimates, evidence tiers, and synthetic labels. It finds
  261 complete comparisons and 302 unavailable comparisons; nearest qualified
  donor distance is the largest descriptive difference (32.6 km vs 63.9 km;
  pooled standardized difference −1.20). These are applicability boundaries,
  not inferred measurement effects.
- [ ] **E4 — Run taxonomy-stratified descriptive analysis.** Blocked until E1
  receives independent human review.
- [x] **E5 — Re-run evidence-tier sensitivity with varying q thresholds.** v2
  preserves all 563 primary labels exactly and yields 0/36/53 supported
  candidates under strict/primary/lenient thresholds. Its funnel makes visible
  that only 77 events reach the adequate-placebo stage and q≤0.05 eliminates
  all 44 strict raw-p survivors; results remain exploratory evidence labels.
- [!] **E6 — Strengthen same-site overlap and cross-family document evidence.**
  The overlap-consistency protocol fixes daily/hourly eligibility and
  direction/rank comparisons before joining cross-site residual outputs.
- [ ] **E7 — Write the formal competition report.** Requires E1--E6 evidence
  and a new release; any new learned method additionally requires its own
  blind, input-disjoint test manifest.

## Human submission handoff

The verified baseline evidence release remains pinned to
[`a738f03`](https://github.com/cb984-cmd/MetaShift/commit/a738f039915abadfce37c274f210578e9319310e);
no new model tuning or selective-decision development may reuse its viewed
80-site evaluation inputs.

- [ ] Students and supervising teacher independently reproduce and explain the
  submitted methods, code, data rules, results, and limitations.
- [ ] Complete the author-contribution and AI-assistance records from verified
  project history, then obtain the required signatures and institutional forms.
- [ ] Replace manuscript identity placeholders and perform the final human
  citation, formatting, and submission-package review.
