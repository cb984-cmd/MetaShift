# MetaShift-Bench paper optimization plan

**Status:** active paper-strengthening extension; v0.2.0 remains an archived
baseline release.
**Principle:** the benchmark-and-audit claim remains primary; no new model
superiority claim will be introduced unless a separately preregistered,
independently evaluated result supports it.

## Review response tracker

| Priority | Review requirement | Decision | Evidence / next artifact |
| --- | --- | --- | --- |
| P0 | Align release, manuscript, code, CI, and results | Complete | [`v0.2.0-paper-evidence`](https://github.com/cb984-cmd/MetaShift/releases/tag/v0.2.0-paper-evidence) points to verified commit `a738f03` |
| P0 | Prevent stale hourly API-response reuse | Complete locally | The manifest is invalidated before refresh and accepts only response hashes read after atomic disk write; 9/11 current requests supplied paired evidence and 2 HTTP failures remain unavailable |
| P0 | Verify manuscript numbers automatically | Complete | Updated verifier covers input-footprint isolation and method-stable 45/60/90-day sensitivity; it passed in both full reconstructions |
| P0 | Unify main/ablation synthetic noise | Complete locally | 7,300 shared Standard SC rows align exactly under the corrected split |
| P1 | Add selection-aware nested bootstrap | Complete; integrated | 261 events, 1,000 repetitions, no event failures |
| P1 | Add 50--100 unique time placebos and BH q values | Complete; integrated | 149 events with at least 50 unique placebos; 41 pass q<=0.10 |
| P1 | Test evidence-tier thresholds | Complete; integrated | Strict/primary/lenient summaries; shared FDR screen is limiting |
| P1 | Expand independent stable test monitors and prevent same-site POC leakage | Complete | 66 calibration + 80 evaluation targets; no complete target-plus-donor physical input site crosses splits |
| P1 | Add one-way parameter sensitivity grid | Complete | 11 predeclared settings and 1/3/5 donor thresholds |
| P2 | Public document validation | Complete as a negative-result audit | 20 preselected events; 0 dated site-level confirmations located |
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
They must preserve the v0.2.0 result archive and cannot tune against its
already viewed 80-site synthetic evaluation split.

| Priority | Extension requirement | Status | Evidence / boundary |
| --- | --- | --- | --- |
| P0 | Freeze metadata-only Method Code taxonomy | In progress | `configs/method_transition_taxonomy_v1.csv` covers all 34 observed pairs and is validated without outcome data; student/teacher review remains required |
| P0 | Test synthetic uncertainty calibration | Complete with evidence shortfall | Conditional nominal-95% intervals cover only 62.47%--67.56% on evaluation; target-cluster nominal-90% conformal intervals cover 98.22%--99.56%. Neither is presented as a calibrated real-event confidence interval, and no post-evaluation tuning occurred |
| P0 | Test selection-aware interval coverage | Pending | The existing nested selection bootstrap still needs a separately frozen synthetic-coverage protocol; it must not tune against the viewed 80-site split |
| P0 | Analyze auditability representativeness | In progress | `configs/auditability_representativeness_v1.json` fixes feature definitions, an explicit urban/rural-data limitation, and a noncausal model restricted to anchors with at least one qualified donor |
| P1 | Stratify observations by frozen taxonomy | Blocked on human taxonomy review | Descriptive only; no equipment-change or causal label |
| P1 | Vary evidence-tier q thresholds | Pending | Strict/primary/lenient settings must vary raw p, q, and donor-stability cutoffs together |
| P1 | Enhance same-site overlap evidence | Pending | Use AQS paired POC overlap only as independent consistency context |
| P2 | New selective model or gate | Deferred | Requires a new blind 60-plus-target input-disjoint manifest; existing 66/80 split is ineligible |
