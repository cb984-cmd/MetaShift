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

## Stricter measured-layout requirements

The active gate is stricter than the historical sign-off below. It measures
final source-rendered positions and requires 6-pt horizontal and 4-pt vertical
node padding, 3-pt minimum separation between independent text boxes, no text
or node overflow, no legend over a data axes, and grayscale luminance contrast
of at least 35. It rejects report-facing text below 8.5 pt, node text below 9
pt, or titles below 10 pt at the measured final print width. The current source
set contains 17 figures because the former combined case-study display is now
separate complete-comparison and abstention figures.

## Status

**The prior 16-figure technical sign-off is superseded.** The current
source-level preflight passes 11 checks for 17 vector figures and records the
measured layout in `generated/figure_layout_qa.json`. Final-PDF placement
checks, 150/300-DPI crop generation, and rendered-page inspection are pending a
clean final build. The historical PDF statistics above are no longer a sign-off
for this source revision. This remains a presentation and reproducibility
review only; student and teacher completion of the human-only disclosures is
still required.
