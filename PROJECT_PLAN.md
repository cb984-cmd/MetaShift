# MetaShift execution plan

**Updated:** 2026-08-30  
**Research status:** development phase; no final performance claim is frozen.

## Evidence rule

MetaShift is retained only if it improves on the preregistered comparison set in
at least two primary metrics without relying on selected cases. A Method Code
transition is a metadata anchor, not proof of physical instrument replacement
or measurement bias.

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

## Active model work

- [x] **M1 — Tune reliability constraints on development events.** A 30-event
  pre-2023 complete-case development search selected ridge=0.1 and
  graph-prior=0.1 by local-effect MAE. MetaShift MAE was 0.02365 log versus
  0.02965 for standard synthetic control (absolute gain 0.00600). This is
  provisional until the frozen held-out evaluation; it must not be retuned on
  final-test events.
- [!] **M2 — Reliability-constraint evidence gap.** On the frozen 2023--2025
  paired 30-event test, MetaShift had 0.02210 local-effect MAE versus 0.02146
  for standard synthetic control, and a higher regional residual score
  (0.05672 versus 0.05180). The development advantage did not reproduce.
  Parameters will not be retuned on this held-out set. The enhanced-algorithm
  claim is blocked pending an independently retestable redesign or a narrower
  benchmark-and-audit contribution.
- [ ] **M3 — Complete synthetic perturbations.** Add proportional changes,
  gradual drift, temporary effects, variance shifts, and matched regional
  controls. Report AUPRC, effect MAE, localization error, and false attribution.
- [ ] **M4 — Freeze the model.** Save the selected configuration, event split,
  random seeds, and evaluation rules before final test results are inspected.

## Validation and analysis

- [ ] **V1 — Run real transition audit.** Report every eligible event's
  pre-fit, effect, uncertainty, and failure reason; do not select only strong
  examples.
- [ ] **V2 — Analyze QA and same-site POC evidence.** Use it only as graded
  external consistency evidence, never as unquestioned physical ground truth.
- [ ] **V3 — Run placebos and ablations.** Time, donor-as-treated, date
  permutation, and regional shock placebos; eight preregistered ablations.
- [ ] **V4 — Run 88502 sensitivity analysis.** Keep it independent of the
  88101 primary analysis.

## Deliverables

- [ ] Reproducible benchmark tables and figures generated only from saved CSVs.
- [ ] Frozen result package, source manifest, run log, and environment record.
- [ ] Research report with limitations, null results, and contribution records.
