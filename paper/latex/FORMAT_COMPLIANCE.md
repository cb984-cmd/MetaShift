# Format compliance record

## Applicable report requirements

The formal report uses A4 paper, a title page, English title/abstract/keywords,
table of contents, scientific narrative, references on a separate section,
appendices, and an explicit human-only acknowledgement/contribution/disclosure
template. It uses source-generated tables and vector figures rather than copied
or screenshot content.

## Superseded baseline build record

The prior canonical PDF was 36 A4 pages, had no recorded overfull boxes, and
passed its embedded-font audit. That baseline is not treated as visually final:
the post-build audit opened a new figure and methods revision, recorded in
`FIGURE_AUDIT.md`.

## Active stricter technical compliance checklist

- [x] The cover fields wrap cleanly without invented identities.
- [x] The abstract has no isolated frozen-evidence block or near-empty page.
- [x] All 17 scientific figures have source-measured padding, text spacing,
  canvas-boundary, typography, legend/data, and grayscale records in
  `generated/figure_layout_qa.json`.
- [x] The complete perturbation matrix and 2023 concentration analysis appear
  only in the appendix.
- [x] Source, reference, claim-ledger, asset-determinism, and figure-QA
  validators pass in source mode: 39 claims, 70 evidence-asset references, 38
  deterministic assets, 17 figures, and 33 citations/33 bibliography entries.
- [ ] A clean final build records its source commit, PDF checksum, page count,
  and zero-overfull-box result.
- [ ] Every final-PDF page and all 17 figure placements have 150-DPI and
  300-DPI rendered evidence, including 34 focused figure crops.
- [ ] Final-mode formal-report and font validation pass against that build.
- [x] Citation links are restrained for print while remaining functional.
- [x] The human-only fields remain visibly incomplete until truthful human
  confirmation is supplied.

**Status: source-level visual validation is passing; final-PDF visual
validation is in progress. No competition-submission completion is claimed.**

## Superseded 16-figure final-build snapshot

The prior 41-page, 16-figure sign-off from clean source commit
`bd4164242638f723eb6f5aec72c822507e098030` is retained as a historical record
only. It reported PDF SHA-256
`efdc98810db8cf5937e6783ab683c44fb73857ec3438e9acacc205f39f8bbbcc`, 36
deterministic assets, 69 evidence-asset references, 14/14 formal-report
checks, and zero Type 3 or unembedded fonts. Those values do not certify the
current 17-figure source revision.
