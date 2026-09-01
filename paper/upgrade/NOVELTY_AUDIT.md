# Phase 1: Closest-Work and Novelty Audit

**Status:** Gate 1 decision: PASS.
**Scope:** A focused adversarial comparison of the closest primary works and
official measurement-data documentation. This audit does not claim an
originality score, a new experimental result, or a completed theorem.

## Candidate contribution after the audit

The only candidate novelty claim that survives this review is deliberately
narrow:

> We formulate a monitoring-network auditing setting in which weak metadata
> anchors identify where to inspect but do not determine what occurred. The
> scientific question is whether specified cross-site evidence makes an event
> answerable under explicit assumptions; when it does, the system reports a
> predeclared answered-case risk/coverage evaluation on synthetic truth, and
> when it does not, the system returns an explicit abstention with a recorded
> reason.

This is not a claim of priority. It is a joint, setting-specific problem
formulation that remains **pending Gate A**: Phase 2 must show that
observational equivalence, residual separation, selective risk, and
truth-regime boundaries are mathematically correct and match the eventual
implementation.

The detailed field-by-field evidence is in
[`CLOSEST_WORK_MATRIX.csv`](CLOSEST_WORK_MATRIX.csv); the search process is in
[`LITERATURE_SEARCH_LOG.md`](LITERATURE_SEARCH_LOG.md).

## Direct adversarial comparison

| Closest work | What it already establishes | What remains outside its stated scope |
| --- | --- | --- |
| Menne and Williams (2009), [MW09](https://doi.org/10.1175/2008JCLI2263.1) | Pairwise network differences, station-history metadata, simulated inhomogeneities, and station-attributed artificial shifts. | A weak-anchor answerability criterion, complete event accounting, answered-case risk/coverage, and explicit abstention. |
| Williams, Menne, and Thorne (2012), [WMT12](https://doi.org/10.1029/2011JD016761) | Realistic benchmark analogs that separate known synthetic truth from uncertain real observations. | Per-event weak-anchor identifiability and an abstaining auditing protocol. |
| Barigozzi, Cho, and Fryzlewicz (2018), [BCF18](https://doi.org/10.1016/j.jeconom.2018.05.003) | A formal common-versus-idiosyncratic change-point framework under an approximate factor model. | Metadata-anchored measurement transitions, physical-site constraints, event-universe accounting, and selective audit decisions. |
| Taiebat and Sassani (2017), [TS17](https://doi.org/10.1139/tcsme-2017-0033) | Conditional sensor-versus-system distinguishability using known physical relations and redundant sensors. | Weak anchors in a public historical monitoring network without those causal/physical relationships, plus risk/coverage and abstention. |
| Geifman and El-Yaniv (2017), [GE17](https://arxiv.org/abs/1705.08500) | Explicit selective classification with a risk target and reject option on labeled benchmarks. | Network-event identifiability, weak operational metadata, and a complete historical event universe. |
| Jin and Ren (2025), [JR25](https://doi.org/10.1093/jrsssb/qkaf016) | Selection-conditional coverage under specified permutation-invariance assumptions. | Local-versus-shared monitoring-network attribution and a weak-anchor abstention protocol. |

The remaining included sources place additional limits on the claim:

- [A21](https://www.aeaweb.org/articles?id=10.1257/jel.20191450) establishes
  that synthetic-control feasibility, pre-fit diagnostics, and placebos are
  existing methodology.
- [EYW10](https://www.jmlr.org/papers/v11/el-yaniv10a.html) establishes that
  risk-coverage trade-offs and reject options are not new.
- [CGAD24](https://jmlr.org/papers/v25/23-0253.html) establishes that weak
  supervision requires a carefully restricted validity target when strong
  labels are unavailable.
- [AR24](https://openreview.net/forum?id=33XGfHLtZg) establishes that
  conformal risk control is not a novel generic uncertainty contribution.
- [VW20](https://arxiv.org/abs/2003.06222) establishes that benchmark design
  under uncertain real ground truth is an existing concern.
- [EPA-AQS](https://aqs.epa.gov/aqsweb/documents/about_aqs_data.html)
  establishes that AQS supplies measurements, metadata, and QA context, but
  not a complete historical physical-fault label ledger.

## Claim boundaries required by the literature

The reconstructed project must not claim:

1. that common-versus-idiosyncratic change-point analysis is new;
2. that pairwise network comparison, metadata use, synthetic benchmarking,
   synthetic control, risk-coverage, weak-supervision validity, or
   selection-conditional coverage is new;
3. that AQS Method Code transitions prove a physical replacement, fault, or
   causal bias;
4. that weak metadata anchors are gold labels;
5. that real anchors support classification accuracy or selective-risk claims;
6. that an abstention is meaningful unless it is an explicit policy with
   reported coverage and machine-readable reasons; or
7. that an identifiability statement holds outside its formal assumptions.

TS17 is the sharpest limiting comparison: it demonstrates that conditional
identifiability-style claims depend on concrete assumptions. Accordingly,
Phase 2 must distinguish a benchmark-level observational statement from
physical causal attribution in real monitoring events.

## Gate 1 rationale

Gate 1 passes because:

- the matrix directly compares six strongest closest works and six additional
  constraining sources;
- every matrix row has a canonical primary or official URL and a stated
  verification status;
- the proposed contribution is narrower than combining a list of existing
  methods; and
- the remaining gap is framed as a testable joint task, not a universal
  novelty assertion.

Gate 1 does not establish the task's technical validity. The novelty framing is
pending Gate A, and must be narrowed or rejected if Phase 2 finds an invalid
proposition, an implementation mismatch, or a closer work that resolves the
same joint problem.
