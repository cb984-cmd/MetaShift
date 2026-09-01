# Format compliance record

## Applicable report requirements

The formal report uses A4 paper, a title page, English title/abstract/keywords,
table of contents, scientific narrative, references on a separate section,
appendices, and an explicit human-only acknowledgement/contribution/disclosure
template. It uses source-generated tables and vector figures rather than copied
or screenshot content.

## Baseline build record

The prior canonical PDF was 36 A4 pages, had no recorded overfull boxes, and
passed its embedded-font audit. That baseline is not treated as visually final:
the post-build audit opened a new figure and methods revision, recorded in
`FIGURE_AUDIT.md`.

## Post-revision compliance checklist

- [x] The cover fields wrap cleanly without invented identities.
- [x] The abstract has no isolated frozen-evidence block or near-empty page.
- [x] All 16 scientific figures satisfy the machine-checkable portions of
  `FIGURE_STYLE_GUIDE.md`.
- [x] The complete perturbation matrix and 2023 concentration analysis appear
  only in the appendix.
- [ ] The report builds cleanly from committed source and all required final
  PDF pages are rendered for review.
- [x] Staged source, reference, claim-ledger, asset-determinism, and figure-QA
  validators pass; final-mode font validation remains pending.
- [x] Citation links are restrained for print while remaining functional.
- [x] The human-only fields remain visibly incomplete until truthful human
  confirmation is supplied.

**Status: revision in progress; no submission-format completion is claimed.**
