# MetaShift execution plan

**Updated:** 2026-08-30  
**Research status:** development phase; no final performance claim is frozen.

## Evidence rule

The project is scoped as a metadata-anchored audit and evaluation benchmark.
MetaShift remains one transparent cross-site counterfactual estimator in the
comparison set; it is not claimed to outperform standard synthetic control
unless a separately designed and independently held-out study supports that
claim. A Method Code transition is a metadata anchor, not proof of physical
instrument replacement or measurement bias.

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

## Active benchmark work

- [x] **M1 — Document comparative model result.** The development-selected
  MetaShift configuration did not beat standard synthetic control on the frozen
  2023--2025 paired test (MAE 0.02210 versus 0.02146; regional residual score
  0.05672 versus 0.05180). This null comparison is retained in the benchmark.
- [ ] **M2 — Complete synthetic perturbations.** Add proportional changes,
  gradual drift, temporary effects, variance shifts, and matched regional
  controls. Report the full comparative profile rather than an unsupported
  single-method superiority claim.
- [ ] **M3 — Freeze benchmark configuration.** Save event splits, random
  seeds, perturbation rules, and evaluation rules before final results.

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
