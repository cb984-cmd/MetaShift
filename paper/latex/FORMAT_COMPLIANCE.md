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

## Final technical compliance checklist

- [x] The cover fields wrap cleanly without invented identities.
- [x] The abstract has no isolated frozen-evidence block or near-empty page.
- [x] All 16 scientific figures satisfy the machine-checkable portions of
  `FIGURE_STYLE_GUIDE.md`.
- [x] The complete perturbation matrix and 2023 concentration analysis appear
  only in the appendix.
- [x] Clean source commit `bd4164242638f723eb6f5aec72c822507e098030` builds
  the 41-page final PDF with SHA-256
  `efdc98810db8cf5937e6783ab683c44fb73857ec3438e9acacc205f39f8bbbcc` and zero
  overfull boxes.
- [x] All 41 final-PDF pages render to nontrivial review images.
- [x] Source, reference, claim-ledger, asset-determinism, figure-QA, font, and
  formal-report validators pass in final mode: 39 claims, 69 evidence-asset
  references, 36 deterministic assets, 16 figures, 33 citations/33
  bibliography entries, and 14/14 formal-report checks.
- [x] The font audit covers the final PDF and 16 vector figures: 17 PDFs, 120
  font records, zero Type 3 fonts, and zero unembedded fonts.
- [x] Citation links are restrained for print while remaining functional.
- [x] The human-only fields remain visibly incomplete until truthful human
  confirmation is supplied.

**Status: technical format validation complete; no competition-submission
completion is claimed.**
