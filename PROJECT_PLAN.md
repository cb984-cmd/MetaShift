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

- [ ] **M1 — Tune reliability constraints on development events.** Search the
  predeclared ridge and graph-prior penalties using development events only;
  preserve a held-out time period for final reporting.
- [ ] **M2 — Add reliability features.** Compare correlation, distance,
  paired-observation coverage, donor concentration, and pre-fit diagnostics.
  Retain a feature only if it improves held-out development performance.
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
