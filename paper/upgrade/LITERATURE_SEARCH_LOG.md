# Phase 1 Literature Search Log

**Search date:** 2026-09-01

**Scope:** Closest-work and novelty audit for the proposed
`v0.4.0-identifiability-audit`. No local experimental data, candidate
post-window observations, or frozen result artifacts were inspected for this
search.

## Search method

Primary papers and official documentation were preferred over secondary
summaries. Bibliographic metadata and scope were checked using publisher pages,
DOI/Crossref records, official proceedings, official JMLR pages, author or
university repositories when publisher access was unavailable, NOAA/NCEI, and
EPA. This is a focused closest-work audit, not a systematic review.

| Query | Source channels | Purpose and disposition |
| --- | --- | --- |
| `Menne Williams pairwise homogenization algorithm climate paper 2009 DOI` | Crossref, AMS/NOAA | Included MW09. |
| `Williams Menne Thorne benchmarking pairwise homogenization algorithm PHA climate paper DOI` | DOI record, university repository | Included WMT12. A Crossref fetch was rate-limited; title, authors, venue, and DOI were retained only from the canonical scholarly record. |
| `Barigozzi Cho Fryzlewicz common idiosyncratic change points paper DOI` | Crossref, university record | Included BCF18. |
| `Taiebat sensor system fault diagnosis redundancy paper DOI` | Publisher DOI, author and university records | Included TS17; canonical DOI verified as `10.1139/tcsme-2017-0033`. |
| `Abadie synthetic control feasibility pre fit placebo paper DOI` | AEA | Included A21. |
| `El-Yaniv Wiener risk coverage selective classification 2010` | JMLR | Included EYW10. |
| `Geifman El-Yaniv selective classification deep neural networks` | NeurIPS/arXiv | Included GE17. |
| `Predictive Inference with Weak Supervision Cauchois Gupta Ali Duchi` | JMLR | Included CGAD24. |
| `conformal prediction selection conditional coverage focal Jin Ren` | DOI record, arXiv | Included JR25. |
| `Conformal Risk Control Angelopoulos Bates Fisch Lei Schuster` | ICLR/OpenReview metadata | Included AR24. |
| `benchmark design real ground truth unavailable change point detection` | arXiv, Alan Turing Institute | Included VW20. |
| `site:epa.gov AQS monitor metadata comparability siting method equivalency` | EPA AQS and regulatory documentation | Included EPA-AQS context. |
| `Le Cam asymptotic methods observational equivalence identical distributions hypothesis testing DOI` | Crossref and Springer DOI record | Included LC86 as a limiting decision-theoretic reference. It supports only the general statistical-experiment vocabulary; the benchmark propositions are proved directly and are not claimed as new theory. |

## Inclusion criteria

- A primary paper or official documentation source.
- Direct relevance to at least one of: network change attribution,
  measurement/sensor versus system distinction, counterfactual comparison, weak
  supervision, selective risk/coverage/rejection, selection-conditional
  uncertainty, air-monitor metadata/comparability, or benchmarking with
  incomplete real ground truth.
- Enough accessible methodological detail to identify inputs, assumptions, and
  evaluation target.

## Exclusion criteria

- Secondary summaries where a primary or official source was accessible.
- Generic anomaly-detection work without a direct conceptual link to the
  proposed task.
- Sources that assert applicability without a method or assumption statement.
- Unverified bibliographic or DOI assertions.

## Access and interpretation limits

Some publisher pages apply automated-access controls, and one Crossref query
was rate-limited. Those limitations are recorded above rather than silently
filled from search snippets. The comparison matrix uses bounded claims tied to
the verified source record. Absence from this focused search is not evidence
that no other related work exists.
