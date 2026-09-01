# v0.4 One-Time Execution Audit

**Status:** completed and structurally verified on 2026-09-01. This is an
auditable result record for the narrow synthetic-contract study. It is not a
manuscript, a release claim, a real AQS analysis, or evidence that MetaShift
outperforms another method.

## Immutable execution authority

| Item | Value |
| --- | --- |
| Execution tag | [`v0.4.1-execution-freeze`](https://github.com/cb984-cmd/MetaShift/tree/v0.4.1-execution-freeze) |
| Peeled execution commit | [`b286221f13b5da8c18dc30226114400d071421d1`](https://github.com/cb984-cmd/MetaShift/commit/b286221f13b5da8c18dc30226114400d071421d1) |
| CI run | [Tests #33475675409](https://github.com/cb984-cmd/MetaShift/actions/runs/33475675409) |
| CI jobs | `unit-tests` and `document-consistency`, both successful |
| Protocol SHA-256 | `3d42a641601966cbd418f487ef41c3ee12dad16e91493fcf078b60b564bf4244` |
| Execution manifest SHA-256 | `8716fb330eed7b876fdf0ca094badeda4762ba4343a070040d63fe34065e20b7` |
| Receipt SHA-256 | `623f7f1f1f3a41ceac834dac61cf5faf857d4e173a574ec4d4e2321e99a1bbac` |

The prior annotated `v0.4.0-execution-freeze` tag remains preserved but was
not executed. It was superseded before any output or attempt record because
the then-frozen source did not include the independent post-execution result
verifier.

## Executed accounting and evidence files

The following local generated files are intentionally ignored by Git. Their
hashes are recorded in the durable receipt and were rechecked by the frozen
post-execution verifier.

| File | SHA-256 |
| --- | --- |
| `v04_core_event_results.csv` | `775f3b148e936bcb59026e6982c18ae340f83df37dbe3512cdb4370808658462` |
| `v04_core_thresholds.json` | `189bebe6371e7f3e4223a42e2f2e7d57794f2bb5826ae7e60395658d4de2423c` |
| `v04_core_metrics.json` | `2dc66758fdd6a04adeecb4829481a9cbd379193b9018561ccceca9a681cb61ce` |
| `v04_core_bootstrap.json` | `21b95b35bccba6fa591204bcb4e93a4fb8e8e20705ea2fdae9a59c4ac9385460` |
| `v04_stress_results.csv` | `c93cfda1183584ba01d8fe82f09ef870acac45c2e59b3b5045de39859f6a763a` |
| `v04_execution_receipt.json` | `623f7f1f1f3a41ceac834dac61cf5faf857d4e173a574ec4d4e2321e99a1bbac` |
| `v04_result_verification.json` | `8ab8c71d9ce5b194058751269c804f2d066f64341dcf51ef3325df91ef56aa98` |

The run generated 720 calibration and 1,440 evaluation core events, with
480 evaluation events in each of N, L, and R; it generated 1,800 raw-scale
stress events. There were zero recorded failures.

## Frozen outcomes

| Quantity | Result |
| --- | ---: |
| Calibration detection threshold | 0.06084251849023525 |
| Calibration scope threshold | 0.08414974339041259 |
| Evaluation target identity rate | 1.000000 |
| Detection macro-F1 | 0.953125 |
| Detection macro-F1, 95% component bootstrap | 0.924833--0.975036 |
| Forced comparative L/R error | 0.000000 |
| Target-only L/R policy error | 0.500000 |
| Selective L/R error, q = 0/0.25/0.50/0.75 | 0 / 0 / 0 / 0 |
| Selective L/R coverage, q = 0/0.25/0.50/0.75 | 1.000000 / 0.767708 / 0.508333 / 0.243750 |
| Valid bootstrap repetitions for every reported metric | 1,000 |
| Satisfied raw-scale stress bounds | 1,800 / 1,800 |

The 0.5 target-only scope-policy error is the balanced local/regional
information-limit construction under the predeclared always-local tie rule.
The zero comparative error is a property of these generated panels and
predeclared score thresholds, not a statement about real monitoring data or
instrument conditions.

The complete threshold, denominator, calibration/evaluation, confusion, and
selective-abstention audit is in
[`V04_CORE_METRIC_AUDIT.md`](V04_CORE_METRIC_AUDIT.md) and
[`V04_CORE_CONFUSION_MATRICES.csv`](V04_CORE_CONFUSION_MATRICES.csv).
The raw-scale stress bounds and unavailable-metric boundary are separately
audited in [`V04_STRESS_SUITE_AUDIT.md`](V04_STRESS_SUITE_AUDIT.md) and
[`V04_ASSUMPTION_FAILURE_MATRIX.csv`](V04_ASSUMPTION_FAILURE_MATRIX.csv).

## Post-execution verification

`scripts/verify_v04_identifiability_results.py --require-results` passed
**14/14** checks. It required the local annotated tag and matching peeled
`origin` tag; loaded the protocol, manifest, and source authority from tagged
Git blobs; required the clean checkout to match every allowlisted source hash;
and replayed every deterministic core and stress outcome in memory. It then
verified all payload and receipt hashes, N/L/R and split accounting, component,
pair, case, seed, and schedule identities, calibration-only threshold
provenance, predictions, metrics, selective risk and coverage, bootstrap
interval validity, stress bounds, and the no-external-input boundary.

## Interpretation boundary and next state

This evidence supports only the stated synthetic construction: matched L/R
target observations are identical while comparative donor information can
support a separately evaluated scope decision. It does not establish causal
identification, physical-instrument truth, AQS generalization, external
monitoring validity, or superiority over standard synthetic control.

The audit does not authorize taxonomy stratification, real-anchor analysis, a
final manuscript, a final figure set, or external release publication.
Taxonomy-independent theory, metric, stress, novelty, crosswalk, and
preliminary manuscript/figure architecture work may proceed under their stated
gates. Taxonomy-dependent conclusions still require independent human review.
