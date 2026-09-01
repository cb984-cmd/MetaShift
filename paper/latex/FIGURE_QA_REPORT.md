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

**Technical sign-off is complete:** a final-mode build from clean source commit
`bd4164242638f723eb6f5aec72c822507e098030` produced
`MetaShift_Bench_Yau_2026.pdf` with SHA-256
`efdc98810db8cf5937e6783ab683c44fb73857ec3438e9acacc205f39f8bbbcc`,
1,050,437 bytes, 41 rendered pages, and zero overfull-box warnings.
`verify_figures.py` passed all 10 checks for 16 vector figures;
`verify_formal_report.py` passed 14/14 checks; and `pdffonts` found zero Type 3
or unembedded fonts across the final PDF and 16 figure PDFs (17 PDFs and 120
font records total).

The rendered-page preflight produced 41 nontrivial page images. The technical
visual review corrected the donor-construction label collision and a nearly
empty trailing page, then rechecked the final donor, accounting, interval,
external-evidence, representative-case, appendix, reference, and disclosure
pages. This is a presentation and reproducibility sign-off only; student and
teacher completion of the human-only disclosures remains required.
