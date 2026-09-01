# MetaShift-Bench paper optimization plan

**Status:** Integrity remediation complete. The current frozen evidence release
is [`v0.3.2-evidence-final`](https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final)
at `57d678ecabebff724d898abe626c9ef80538775b`; it passes 35/35 release-gate
checks, 12/12 document-consistency checks, and 57/57 manuscript-number checks.
v0.2.0 and v0.3.1 are retained only as superseded archival history.
**Principle:** the benchmark-and-audit claim remains primary; no new model
superiority claim will be introduced unless a separately preregistered,
independently evaluated result supports it.

## Review response tracker

| Priority | Review requirement | Decision | Evidence / next artifact |
| --- | --- | --- | --- |
| P0 | Align release, manuscript, code, CI, and results | Complete | `v0.3.2-evidence-final` points to verified frozen commit `57d678e`; source provenance is tracked in `configs/current_evidence_summary_v2.json` |
| P0 | Enforce physical-donor uniqueness | Complete | The rebuilt 88101 control inventory has zero duplicate physical donors; 238 anchors retain at least three distinct physical donors and the rebuilt stable set retains a 66/80 zero-overlap split. All dependent artifacts were rebuilt |
| P0 | Prevent stale hourly API-response reuse | Complete locally | The manifest is invalidated before refresh and accepts only response hashes read after atomic disk write; 9/11 current requests supplied paired evidence and 2 HTTP failures remain unavailable |
| P0 | Verify manuscript numbers automatically | Complete | The v0.3.2 verifier records 57 passing generated-number checks; the tracked summary provides a CI-safe source contract |
| P0 | Unify main/ablation synthetic noise | Complete locally | 7,300 shared Standard SC rows align exactly under the corrected split |
| P1 | Add selection-aware nested bootstrap | Complete; integrated | 227 events with v2 distinct donors, 1,000 scheduled repetitions, and one retained event failure (`33-009-0010`) |
| P1 | Add 50--100 unique time placebos and BH q values | Complete; integrated | 157 events with at least 50 unique placebos; 40 pass q<=0.10 (v2 distinct donors) |
| P1 | Test evidence-tier thresholds | Complete; integrated | Strict/primary/lenient summaries; shared FDR screen is limiting |
| P1 | Expand independent stable test monitors and prevent same-site POC leakage | Complete | 66 calibration + 80 evaluation targets; no complete target-plus-donor physical input site crosses splits |
| P1 | Add one-way parameter sensitivity grid | Complete | 11 predeclared settings and 1/3/5 donor thresholds |
| P2 | Public document validation | Complete as a negative-result audit | 20 preselected events; 0/20 dated site-specific confirmations located |
| P2 | Generate reproducible representative cases | Complete | Three supported, three not-supported, and three inconclusive cases |
| P2 | Expand related-work comparison | Complete | Verified four-area literature matrix and source-grounded comparison |
| P3 | Gated ensemble / variance detector | Deferred | Model-superiority route is closed; may appear only as a clearly separate appendix exploration |

## Current evidence boundaries

1. A reported Method Code change is an audit anchor, not an instrument-change
   ground truth.
2. Selection-aware intervals account for resampled time blocks, donor
   correlation eligibility, donor selection, and weight fitting within a fixed
   observed candidate pool. They do not account for all data-source or
   metadata uncertainty.
3. BH-adjusted time-placebo values are exploratory screening quantities, not
   causal p-values.
4. Public document searches that did not locate a dated site-level notice are
   explicitly recorded as unavailable evidence, not evidence of no change.

## Freeze criteria for the paper-evidence release

- [x] All manuscript numbers automatically match artifacts from the corrected,
  clean reconstruction.
- [x] Main and ablation shared rows align exactly in the corrected local rerun.
- [x] Stable benchmark uses disjoint complete target-plus-donor physical input
  footprints across calibration and evaluation partitions.
- [x] Selection-aware intervals, extended placebos, BH q values, and
  threshold sensitivity are included in the manuscript and evidence bundle.
- [x] External-document audit, case-study outputs, and related-work matrix are
  complete.
- [x] The evidence commit passes public CI and two locked-environment
  reconstructions.
- [x] A versioned public evidence release points exactly to the manuscript
  commit and excludes raw data, API responses, and credentials.

## Paper-strengthening extension

All additions below are governed by
[`configs/paper_extension_protocol_v1.json`](configs/paper_extension_protocol_v1.json).
They preserve the v0.2.0 result archive only as superseded history and cannot
tune against the already viewed 80-site synthetic evaluation split.

| Priority | Extension requirement | Status | Evidence / boundary |
| --- | --- | --- | --- |
| P0 | Freeze metadata-only Method Code taxonomy | Human-blocked | `configs/method_transition_taxonomy_v1.csv` and the exact 34-row [human-review packet](paper/upgrade/TAXONOMY_HUMAN_REVIEW_PACKET.md) contain no outcome data; every row remains pending independent student/teacher review before any stratification |
| P0 | Test fixed-weight synthetic uncertainty calibration | Complete as a negative result | v2 nominal-95% conditional coverage is 63.875%--67.281%; nominal-90% split-conformal coverage is 98.8125%--99.5625%. No post-evaluation adjustment is permitted |
| P0 | Test selection-aware interval coverage | Frozen infeasibility recorded | `configs/selection_aware_coverage_protocol_v2.json` was frozen before outcomes and records full donor-reselection coverage as infeasible within the deadline; real intervals are not claimed calibrated |
| P0 | Analyze auditability representativeness | Complete | v2 retains all 563 anchors: 228 complete comparisons, 325 donor-insufficient events, and 10 input-window failures |
| P1 | Stratify observations by frozen taxonomy | Blocked on human taxonomy review | Descriptive only; no equipment-change or causal label |
| P1 | Vary evidence-tier q thresholds | Complete | v2 strict/primary/lenient settings yield 0/34/55 supported candidates; labels remain exploratory |
| P1 | Enhance same-site overlap evidence | Complete with limitation | Eleven daily and nine hourly paired alternate-POC comparisons are retained; daily/hourly direction agreement is 8/9, and evidence is contextual only |
| P2 | New selective model or gate | Deferred | Requires a new blind 60-plus-target input-disjoint manifest; existing 66/80 split is ineligible |

## v0.5 scope-answerability reconstruction

The active reconstruction no longer seeks a MetaShift-versus-standard synthetic
control advantage. Its pre-outcome protocol measures synthetic scope
answerability under target-only and comparative information channels, while
holding the target observation fixed across local/shared paired states. The
new theory, literature limits, power analysis, protocol, claim ledger, and
execution checklist are in `paper/upgrade/V05_*`. Taxonomy review remains
blocked and is not an input to this scope-level work.
