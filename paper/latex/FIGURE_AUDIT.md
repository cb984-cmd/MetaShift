# Figure audit: baseline and redesign contract

## Scope and evidence boundary

This audit records the presentation review of the historical v0.3.2 baseline
at source commit `9f89ad56d205acd616862982ef3643c6b6769c1b`. Its scientific
values remain bound to `v0.3.2-evidence-final`
(`57d678ecabebff724d898abe626c9ef80538775b`). The answerability-first
revision additionally includes receipt-bound v0.5 figures; it does not alter
any frozen result, threshold, estimator, donor rule, or viewed evaluation
partition.

All baseline scientific figures were inspected as vector PDFs and as rendered
pages of the 36-page report. The audit distinguishes a design schematic from a
data-derived graphic. A schematic may explain a protocol but may not support a
numeric or physical claim.

## Figure-by-figure audit

| Baseline figure | Baseline page | Purpose and frozen source | Audit finding | Required resolution |
| --- | ---: | --- | --- | --- |
| 1 `fig_local_regional_schematic.pdf` | 5 | Explain target-local versus matched-regional behavior; benchmark config | Generic curves are not a reproducible stable-window example. | Replace with a checksum-pinned held-out stable case and fixed local/regional additive injections. |
| 2 `fig_data_construction.pdf` | 10 | Anchor dates and donor availability; `real_transition_88101_event_audit.csv` | The unexplained 2023 spike is prominent in the main narrative. | Replace in the main text with physical-site donor construction; move the temporal concentration analysis to the appendix with an explicit non-causal limitation. |
| 3 `fig_audit_pipeline.pdf` | 11 | Workflow; frozen protocol, event audit, tier config | Minimal layout has crossing diagonal arrows and omits the parallel benchmark and audit branches. | Redraw as a top-down noncrossing workflow with synthetic and all-anchor audit branches. |
| 4 `fig_split_integrity.pdf` | 13 | Component split audit; stable manifest | Two boxes state counts but do not show target-plus-donor footprint components. | Show component allocation, target/donor footprint membership, split counts, and the zero-overlap barrier. |
| 5 `fig_synthetic_metrics.pdf` | 15 | Four cross-site aggregate metrics; `stable_full_v2` metrics | Bar charts obscure directional interpretation and rely on rotated labels. | Use compact horizontal dot displays with explicit higher/lower-is-better labels. |
| 6 `fig_perturbation_metrics.pdf` | 17 | All methods, metrics, and perturbation families; frozen metrics | Dense annotated heatmaps are illegible at report scale. | Show a decision-relevant main-text estimation/classification comparison; retain the complete matrix only in the appendix table. |
| 7 `fig_paired_bootstrap.pdf` | 18 | Paired MAE bootstrap; frozen bootstrap table | Sign convention is stated only in the caption and interval values are not printed. | Add direct interval labels and a visible zero/favor-direction annotation. |
| 8 `fig_event_flow.pdf` | 19 | Audit dispositions; event audit | Disposition counts are not linked to evidence tiers. | Replace with one hierarchical 563-anchor accounting diagram. |
| 9 `fig_evidence_tiers.pdf` | 19 | Evidence tiers; tier summary | Peer bars conceal that most inconclusive cases arise before or during common comparison. | Remove the separate figure; encode tier leaves in the hierarchical accounting diagram. |
| 10 `fig_placebos.pdf` | 20 | Time-placebo availability and probabilities; placebo summary | Nested 50-date and 100-date subsets appear as peer categories. | Show `228 -> 157 -> 128` nesting, unavailable cases, and the probability distribution separately. |
| 11 `fig_interval_coverage.pdf` | 21 | Held-out coverage; interval summary | The coverage axis begins at 0.5 and the figure omits interval-width context. | Use a full 0--100% coverage scale plus an aligned interval-width panel. |
| 12 `fig_screening_sensitivity.pdf` | 22 | Screening and tier sensitivity; two frozen summaries | Tier counts are not normalized; large page whitespace leaves strict/primary/lenient undefined. | Use a 100% stacked tier composition and a donor-radius point/line panel with definitions in the caption. |
| 13 `fig_external_evidence.pdf` | 23 | Same-site POC and document review; frozen summaries | Separate bars omit QA and 88502 paths and imply a flat evidence hierarchy. | Use a four-lane nested evidence ladder for POC, QA, documents, and the separate 88502 audit. |
| 14 `fig_case_studies.pdf` | 24 | Three deterministic examples; case manifest and frozen result tables | Long identifiers collide with headers; calendar axes, sparse diagnostics, and no case-level placebo distribution reduce readability. | Use relative-day panels, concise case/date headers, a transparent saved-placebo-summary diagnostic, interval/evidence row, and explicit abstention panel. |

## Cross-cutting findings

1. The baseline figure font is DejaVu Sans while report text is Latin Modern;
   labels below 8 pt appear in several dense panels.
2. The baseline figures are vector PDFs with embedded non-Type-3 fonts, but the
   source directory was globally ignored and only a subset of referenced
   generated figures was tracked. The revised report must track every referenced
   safe vector figure and its deterministic source.
3. The obsolete graph-based display name is inaccurate. The implementation is a
   pre-event reliability prior based on correlation and distance, with a
   reliability-prior penalty.
4. The implementation uses inclusive Pandas date labels: the calibration slice
   is `t0-180` through `t0-15`, while the effect pre-window is `t0-60` through
   `t0-1`. Thus 46 calendar dates overlap. There is no post-anchor leakage, but
   the pre-window is not independent of fitting and residual centering.
5. The 2023 date concentration must not be presented as an instrument, policy,
   agency, or administrative mechanism. The audit can report its association
   with named code-pair transitions and clustered dates only.

## Acceptance criteria for the revised figure set

The post-revision QA report must show that every legacy scientific figure is a
manifested vector PDF and every v0.5 scientific figure is a receipt-bound
raster PNG, each with existing hash-verified frozen or display-contract inputs.
All 563 anchors must reconcile in the legacy accounting figure; placebo
nesting, split isolation, interval nominal levels, and external-evidence
ladders must remain arithmetically correct; and no figure may contain a
placeholder, a causal-instrument assertion, a hidden truncated coverage axis,
or a claim unsupported by its sources.

## Stricter measured layout gate

The earlier 16-figure sign-off is superseded for the current visual acceptance
standard. The current source generates 17 figures after splitting the complete
representative cases from the abstention display. Before the revised PDF can be
signed off, every figure must have:

1. a text-measured node layout with at least 6-pt horizontal and 4-pt vertical
   internal padding;
2. at least 3 pt between independent important text boxes, no text beyond the
   figure canvas, and no legend over a data region;
3. normal labels at least 8.5 pt, node labels at least 9 pt, and panel titles
   at least 10 pt at final print width;
4. a grayscale contrast check; and
5. a 150-DPI and 300-DPI final-page crop record.

**Status: the historical v0.3.2-only visual sign-off is superseded.** The
current report has 17 legacy vector figures and five v0.5 receipt-bound raster
figures. The final source gate must generate a combined 22-figure,
150/300-DPI crop record and a new canonical PDF from a clean committed
worktree. This presentation work does not complete any human-only submission
item.
