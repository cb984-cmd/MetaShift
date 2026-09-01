# Figure QA report

## Scope

This report records the visual and machine-checkable QA protocol for the formal
MetaShift-Bench report. It binds every scientific graphic to
`v0.3.2-evidence-final`; it does not certify a human taxonomy review, authorship
statement, physical mechanism, or competition submission.

## Baseline finding

The prior 36-page PDF passed vector/font checks but failed this higher
presentation audit in several substantive ways: generic motivating curves,
crossing workflow arrows, non-hierarchical anchor/tier counts, peer-style
placebo nesting, truncated coverage display, sparse interval context, a
case-study header collision, and an unexplained 2023 chart in the main text.
These are recorded figure-by-figure in `FIGURE_AUDIT.md`.

## Required post-revision machine checks

| Check | Evidence |
| --- | --- |
| Every referenced PDF exists, is nonempty, and is in the asset manifest | `generated/figure_qa_validation.json` |
| Every figure has frozen or SHA-256-pinned display inputs | Asset manifest and figure verifier |
| All 563 primary anchors reconcile through audit disposition and evidence-tier leaves | Figure verifier accounting check |
| Placebo counts preserve `228 -> 157 -> 128` nesting and 71 unavailable cases | Figure verifier placebo check |
| Complete target-plus-donor input footprints remain split-disjoint | Frozen split audit and figure verifier |
| Coverage figure uses 95% conditional and 90% conformal nominal references with saved widths | Figure verifier interval check |
| No non-vector scientific figure, placeholder, Type 3 font, or unembedded font remains | Figure/font validators |
| Every final-PDF page is rendered and visually inspected | Build preflight plus manual page review |

## Status

**Post-revision machine verification is complete:** `verify_figures.py`
validated 16 referenced vector figures and 10 logical/source checks against the
frozen v0.3.2 inputs. A staged build rendered 42 pages with no overfull boxes;
the visual pass corrected and rechecked the event-accounting, representative-case,
and QA-ladder layouts. A clean-source final-mode build, full final page
inspection, and formal-report sign-off remain pending.
