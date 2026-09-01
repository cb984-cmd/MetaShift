# Major revision plan: MetaShift-Bench formal report

## Scope and immutable evidence boundary

This is a presentation, documentation, and frozen-result expansion pass for the
formal English report. The sole scientific evidence source remains:

| Item | Locked value |
| --- | --- |
| Evidence tag | `v0.3.2-evidence-final` |
| Evidence commit | `57d678ecabebff724d898abe626c9ef80538775b` |
| Evidence release | <https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final> |
| Synthetic result label | `stable_full_v2` |
| Frozen case-manifest SHA-256 | `065b1b65c231c5298fb4969a7b5669f3ae8850b9228d50afee7d98422575e099` |

No work in this revision may tune an estimator, threshold, donor rule, or
perturbation after the held-out evaluation; change the viewed test set; delete
unfavorable events; treat Method Code as physical-instrument ground truth; or
perform taxonomy stratification. The current taxonomy status remains
`human_blocked`.

## Starting point

The starting manuscript commit is `930c22c976c37c29a08eb4c89169045f47144dca`.
It contains a 19-page, hash-verified pre-submission draft and a 20-asset
deterministic generation pipeline. The revision expands the report rather than
replacing or weakening its existing no-superiority, no-causal-instrument, and
no-calibrated-real-interval boundaries.

## Current execution state

The earlier 36-page PDF and its 13-check formal-compliance record are a
superseded presentation baseline, not the current sign-off. The active
remediation replaces the prior visual gate with text-measured geometry and
splits the crowded combined representative-case figure into separate complete
comparison and abstention displays. It retains the data-derived, hash-pinned
figures; exact inclusive-window implementation and its 46-date
calibration/pre overlap; external-QA availability ladder; and appendix-only
2023 descriptive concentration analysis.

The current source generates 38 presentation assets and maps 39 quantitative
claims through 70 frozen evidence-asset references. Its source QA checks 17
figures for hashes, vector structure, full-event accounting, input-footprint
isolation, nested-placebo arithmetic, interval construction, external
availability counts, deterministic case reconstruction, descriptive
concentration arithmetic, and measured geometry. The geometry record requires
node padding, independent-text separation, canvas containment, readable final
print typography, legend/data separation, and grayscale contrast. Clean
report-source commit `2aad488726a04e1a1adda1e768b909b350686aad` completed the
strict final build: the canonical 44-page PDF has SHA-256
`08841e8ed3ed9e4a3a69ceddf62a42a385c0077e0a6cdf9d761c20a6ceb22d40`, zero
overfull boxes, 150/300-DPI rendering for all 44 pages, 34 focused figure
crops, an 18-PDF/125-font clean audit, and 15/15 formal-report checks.
Technical presentation work is complete.

No new data, analysis, tuning, taxonomy work, or evidence-release change is
permitted during this revision. The CI-safe public-document checker writes to
an ignored transient artifact by default, leaving the frozen release
`results/document_consistency.json` unchanged.

All contribution, identity, taxonomy, advisor, AI-use, signature, stamp,
plagiarism, integrity-declaration, and final-attestation items remain human
review required.

## Issue-to-change matrix

| ID | Revision requirement | Planned files | Completion check |
| --- | --- | --- | --- |
| R1 | Reorder the report into the required scientific narrative and appendices. | `main.tex`; new `sections/problem.tex`, `framework.tex`, `case_studies.tex`, `reproducibility.tex`, `appendix.tex` | Source validator confirms exact input order, required headings, separate references, appendices, and disclosures. |
| R2 | Expand the abstract and introduction with a non-causal motivating example, CS framing, six contributions, and balanced result preview. | `sections/frontmatter.tex`, `sections/introduction.tex` | Source/claim checks confirm frozen counts and prohibited claims remain absent. |
| R3 | Define targets, physical sites, POCs, anchors, donor sets, all windows, residuals, local effects, tiers, and abstention; state permitted/prohibited claims. | `sections/problem.tex`; generated claim-boundary table | Equations and terminology are checked against `metashift/counterfactual.py`, `metashift/evidence.py`, and frozen configuration. |
| R4 | Expand related work to authoritative sources covering comparability, homogenization, change points, counterfactuals, weak labels, uncertainty, and selective prediction. | `sections/related_work.tex`, `references.bib`; generated comparison table | Citation validator finds every citation defined, every bibliography entry used, and required source categories represented. |
| R5 | Document data provenance, canonical monitor construction, cleaning, donor deduplication, deterministic POC tie breaking, and separate 88101/88502 handling. | `sections/data.tex`; data/audit figures and tables | All numbers trace to frozen sources; no raw download is committed. |
| R6 | Make the audit framework technically complete: donor eligibility, Standard SC, nearest-neighbor DiD, MetaShift prior/CV, single-series baselines, effects, intervals, placebos, sensitivity, complexity, and implementation. | `sections/framework.tex`; generated algorithm blocks/tables | Formula fragments reproduce code inputs, constraints, windows, and early exits. |
| R7 | Expand the frozen experimental design: stable windows, component split, perturbations, seeds, labels, metrics, bootstrap, main/ablation alignment, real audit, and sensitivity protocol. | `sections/experiments.tex`; split and perturbation assets | Configuration values and metric definitions are sourced from frozen config/artifacts. |
| R8 | Restore complete RQ1 evidence for all frozen methods, marking unavailable metrics as N/A instead of inferring them. | generator; `generated/tables/table_all_methods.tex`; results and appendix | Generated table covers all listed methods and its caption explains metric availability. |
| R9 | Show perturbation-specific MAE, AUPRC, Macro-F1, and regional-FPR results without selecting favorable variants. | generator; perturbation tables/heatmaps; results and appendix | Each frozen local/regional family present in the saved metrics file is included; source hashes validate. |
| R10 | Make the evidence-grade rules reproducible, including mandatory/optional diagnostics, thresholds, failure reasons, and abstention logic. | generator; `table_evidence_tier_rules.tex`; `sections/framework.tex`, `results.tex` | Rule table matches `configs/evidence_tier_primary_v1.json` and `metashift/evidence.py`; tier totals reconcile to 563. |
| R11 | Add deterministic supported, not-supported, and inconclusive case studies; use raw curves only when their reconstruction input and selection rule are frozen and hash-recorded. | generator; case asset manifest/table/figure; `sections/case_studies.tex` | Case selection rule is deterministic, all diagnostic facts trace to frozen tables, and missing evidence is shown rather than imputed. |
| R12 | Add motivating, audit-pipeline, split, perturbation, interval, and abstention visuals; improve existing captions and styles. | generator; `generated/figures/*`; results/appendix captions | Vector assets use embedded non-Type-3 text, color-blind-safe palette, consistent colors, self-contained captions, and asset-manifest hashes. |
| R13 | Clarify all diagnostic interval terminology and report fixed undercoverage beside conformal conservatism. | `sections/problem.tex`, `results.tex`, `limitations.tex`, generated interval table/figure | No real-event interval is described as calibrated or statistically significant; frozen coverage values appear consistently. |
| R14 | Expand the discussion and reorganize threats under construct, internal, statistical, and external validity. | `sections/discussion.tex`, `sections/limitations.tex`; limitation table | Each limitation has risk, mitigation, residual consequence, and needed future evidence. |
| R15 | Place reproducibility material in its own section; preserve placeholders and explicitly record human-only work. | `sections/reproducibility.tex`, `acknowledgements.tex`, `HUMAN_COMPLETION_CHECKLIST.md` | No identity, contribution, advisor, compensation, AI-use, signature, or taxonomy fact is invented. |
| R16 | Add robust manuscript gates, clean-build record, visual review, self-review, completion report, PDF metadata, and final output copy. | paper scripts; `PAPER_SELF_REVIEW.md`; `REVISION_COMPLETION_REPORT.md`; build outputs | Clean build, all validators, rendered page review, font check, asset determinism check, and evidence-based score report pass. |

## Asset and claim contract

1. The paper generator must reject non-v0.3.2 evidence, mismatched source hashes,
   and non-`stable_full_v2` benchmark results.
2. Every changed quantitative claim receives one ledger row with source path,
   frozen version, columns, filters, calculation, output asset, and
   `verified_frozen_evidence` status.
3. Every generated figure and table is listed with a SHA-256 in
   `generated/asset_manifest.json`. Conceptual figures are explicitly labeled as
   schematics and do not support a numerical claim.
4. The clean paper build must be deterministic for generated assets and final
   PDF bytes. Timestamps belong in build records, not frozen source manifests.
5. Generated PDFs, tables, reports, and source code may be committed. Raw EPA
   archives, API responses, credentials, virtual environments, caches, and
   rendered PNG review pages must remain untracked.

## Completion gates

The revision is complete only if all applicable checks pass:

1. Required report order, problem definition, methods, algorithms, complete
   baseline display, perturbation display, tier rules, case-study policy, and
   limitation taxonomy are present.
2. All 563 anchors remain accounted for; no failure is hidden or reclassified.
3. The visible conclusion retains the negative MetaShift-superiority result and
   all interpretation boundaries.
4. New quantitative claims, tables, and figures are ledger-mapped to
   SHA-verified frozen sources.
5. Existing release evidence remains unchanged and no frozen result is
   regenerated or overwritten.
6. Unit tests, CI-safe public-document checks, paper-source validation,
   citation validation, claim-ledger validation, asset determinism validation,
   formal-report validation, font validation, clean PDF build, and visual-page
   review pass.
7. The final completion report identifies starting/final commits, evidence
   version, PDF path/hash/page count, validation outcomes, evidence-based
   self-review, remaining scientific limits, and human-only blockers.
