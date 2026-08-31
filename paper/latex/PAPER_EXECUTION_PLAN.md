# MetaShift-Bench formal-report execution plan

## Scope and evidence lock

This report is a formal English research-report draft for the 2026 S.-T. Yau
High School Science Award, Computer Science category. Its scientific evidence
is locked to:

| Item | Frozen value |
| --- | --- |
| Evidence tag | `v0.3.2-evidence-final` |
| Evidence commit | `57d678ecabebff724d898abe626c9ef80538775b` |
| Evidence release | <https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final> |
| Frozen benchmark configuration | `configs/benchmark_release_v2.json` |
| Evidence summary | `configs/current_evidence_summary_v2.json` |
| Synthetic result label | `stable_full_v2` |

The report will not change a model, threshold, donor rule, selected event, or
experimental artifact. It will not execute taxonomy stratification. The
Method Code taxonomy remains pending independent student and teacher review and
will not support a stratified claim in this report.

## Scientific position

The contribution is **MetaShift-Bench**, a metadata-anchored, weakly labeled,
selective audit benchmark. A reported AQS Method Code transition is an event
anchor, not a physical-instrument log, ground-truth bias label, or causal
intervention. MetaShift is a tested metadata-informed weighting hypothesis;
the report will explicitly preserve the result that neither MetaShift variant
has a confidence-supported overall advantage over standard synthetic control.

## Work sequence

1. Reconcile source documentation against the frozen evidence summary and
   generated artifacts; label prior v0.1/v0.2 material as historical only.
2. Maintain `CLAIM_EVIDENCE_LEDGER.csv` before adding any quantitative prose.
3. Generate numeric LaTeX table fragments and vector figures only from frozen
   artifacts through tracked scripts.
4. Create the A4 LaTeX project in the official report order: cover page,
   title/author page, abstract, keywords, contents, main text, separate
   references, then acknowledgements and contribution disclosures.
5. Draft each section around RQ1--RQ5, with a direct answer, quantitative
   evidence, uncertainty, interpretation boundary, and limitation.
6. Compile, validate claims/citations/references, render every PDF page, and
   record a transparent self-review.
7. Preserve all human-only fields as `HUMAN COMPLETION REQUIRED`; do not claim
   a submission-ready status until students and supervising teacher complete
   the required review and attestations.

## Automated draft status

The automated writing stage produces `MetaShift_Bench_Yau_2026.pdf`, generated
tables and figures, a source-to-evidence claim ledger, citation validation, and
a rendered-page/format-compliance record. All of these outputs derive only from
the frozen v0.3.2 evidence contract and remain reproducible through the local
build commands.

This is a pre-submission draft, not a completed competition submission. The
human completion checklist remains authoritative for identity, student
understanding, contribution statements, advisor and compensation disclosure,
AI-use disclosure, Method Code taxonomy review, signatures, stamps, plagiarism
report, and final truthfulness attestation.

## Quantitative source contract

Numeric prose must be generated or checked against these sources:

| Result family | Canonical source |
| --- | --- |
| Dataset, anchor, and audit counts | `artifacts/data_gate/summary.json`, `artifacts/real_transition_88101_event_audit.csv` |
| Synthetic metrics and paired uncertainty | `artifacts/stable_synthetic_stable_full_v2_metrics.csv`, `artifacts/stable_synthetic_stable_full_v2_bootstrap.csv` |
| Leakage audit and stable-case split | `artifacts/stable_synthetic_case_manifest.json`, `artifacts/stable_synthetic_case_split_audit.json` |
| Real-event intervals and donor sensitivity | `artifacts/real_transition_88101_event_intervals.csv`, `artifacts/real_transition_88101_nested_selection_intervals.csv`, `artifacts/leave_one_donor_out_summary.csv` |
| Placebo diagnostics | `artifacts/time_placebo_summary.csv`, `artifacts/donor_as_treated_placebos.csv`, `artifacts/time_placebo_date_permutations.csv` |
| Evidence tiers and external evidence | `artifacts/real_transition_88101_evidence_tier_summary.json`, `artifacts/hourly_poc_validation_summary.csv`, `artifacts/external_document_review_summary.json` |
| Interval calibration | `artifacts/synthetic_interval_coverage_v2_summary.csv` |
| Integrity and reproducibility | `results/release_gate.json`, `results/manuscript_number_verification.json`, `results/reproducibility_comparison.json` |

The tracked summary is the CI-safe public statement of these values. The
release gate validates it locally against generated artifacts.

## Report boundaries

- Do not call the 34 supported audit candidates confirmed failures, confirmed
  measurement biases, or instrument replacements.
- Do not call real Method Code anchors ground truth.
- Do not describe real-event intervals as calibrated 95% confidence intervals.
- Do not state or imply that MetaShift is superior to standard synthetic
  control.
- Do not use the viewed 80-site evaluation set for model, threshold, gate, or
  taxonomy tuning.
- Do not invent author identity, school, advisor, contribution, AI-use,
  signature, or attestation information.

## Human completion boundary

The final PDF may contain visible placeholders for identity and official
declarations. The following items remain human-only: student and advisor
identity, contribution verification, Method Code taxonomy review, accurate
AI-use record, advisor relationship and compensation disclosure, signatures,
institutional stamps, plagiarism report, and final truthfulness attestation.
