# v0.5 Post-Execution Audit

## Authority and immutable evidence

This audit covers the sole authorized execution at commit
`14fd0fee4fb015e6c661299041e35ff704a27286`. The annotated freeze tag is
`v0.5.0-answerability-freeze`; its distinct annotated remote execution-claim
tag is `v0.5.0-answerability-execution-claim`. The durable attempt reached
`completed` at `2026-09-01T12:59:56.383733+00:00` with `failure_count: 0` and
binds the receipt SHA-256
`954fc9b56a8f526644320aa7b1b15ed76844e400e1394ffd8f733729996a87c9`.

`configs/v05_frozen_result_manifest.json` is the tracked authority for exact
file bytes, schemas, CSV row counts, receipt/attempt linkage, source hashes,
and local/remote annotated-tag objects. The ignored raw outputs were not
modified for this audit.

| Frozen output | Bytes | SHA-256 |
| --- | ---: | --- |
| `v05_scope_pair_results.csv` | 392,650,382 | `36649ebe9d1b91927a95766a5757a715cb53f657295fa3471ccf83303c225ede` |
| `v05_calibration_policy.json` | 901 | `3b98f04e4edb45955d7e9814522365174801ff35f35a90bde87e4b9f5c4107ba` |
| `v05_policy_metrics.csv` | 27,402 | `9996a3a51cb57cbbf53867b6a74a8d9e3c93ce760862c7d03761ef81ece3b6ea` |
| `v05_answerability_frontier.csv` | 27,119 | `76246d55b061d979a8df8852d66e228e1d951f0e3260f5c4a4fa89060cc91eaa` |
| `v05_certificate_validity.csv` | 4,499 | `a6f36119f4964f82c8f8c907126cf3d7b88ace627ff920d5a60a3196a672fcd7` |
| `v05_failure_mode_map.csv` | 401,049 | `69ba2d10d5281eec04cd77e1d2d8a7a52f7dbfcd51b5655a4f509e82f6b3bdc1` |
| `v05_component_bootstrap.csv` | 2,915 | `a05e1cdfdd0eca6683cecd302dffe92930cafbe8b11b738a821e090414518646` |
| `v05_execution_receipt.json` | 4,969 | `954fc9b56a8f526644320aa7b1b15ed76844e400e1394ffd8f733729996a87c9` |

## Accounting, q=0, and certificate boundaries

The receipt records all expected counts: 76,800 calibration and 230,400
evaluation pair rows (307,200 total), 614,400 scope-arm events, and 61,440
q=0 pair rows. It records unique pair IDs, target identity inside every pair
and target group, q=0 comparative-observation identity, and all 640 cells per
component as true. Its independent implementation-semantics cross-check passed
all 640 cells with maximum absolute difference
`1.6653345369377348e-16`, below `1e-12`.

q=0 is a negative-control impossibility stratum, not a success result. In the
evaluation split it contains 46,080 pair rows (92,160 scope-arm events). Both
forced target-only and forced comparative policies answered all 92,160 and had
0.5 conditional error. The certificate answered zero q=0 pair rows. The
calibration-0.20 confidence policy answered 51,672 q=0 events and also had
0.5 conditional error. Thus neither q=0 identity nor abstention may be
presented as a scope-recovery gain.

The certificate is explicitly synthetic-design-information-assisted. It
answered 89,997 of 230,400 evaluation pair rows (179,994 events; coverage
0.3906119792), with zero observed answered-event errors and zero observed
envelope violations. It abstained on 140,403 nonpositive-margin pair rows.
Its predeclared simulation-information oracle answered 92,155 pair rows, so
the reported efficiency is 0.9765829309. These finite synthetic observations
do not validate a deployable certificate, prove population risk is zero, or
provide a physical or real-AQS mechanism.

## Frozen evaluation outcomes

The unfavorable ordinary-channel outcomes are retained:

* At reporting \(\alpha=0.01\), \(0.05\), and \(0.10\), both target-only and
  ordinary comparative finite-policy frontiers had zero positive qualifying
  coverage. The respective 0.01/0.05/0.10 confidence policies always
  abstained.
* At \(\alpha=0.20\), target-only still had no positive qualifying coverage.
  The ordinary comparative frontier selected
  `confidence_selective@calibration_alpha=0.20`, with evaluation coverage
  0.6037456597 and conditional error 0.1952078676. Its component-cluster
  percentile bootstrap coverage interval was [0.6008630642, 0.6070075412]
  and error interval [0.1926023543, 0.1980570777].
* Forced policies are not calibrated risk guarantees: target-only forced had
  coverage 1.0 and conditional error 0.5; comparative forced had coverage 1.0
  and conditional error 0.2750954861.
* The separate synthetic-design-information certificate channel had coverage
  0.3906119792 and zero observed conditional error at every reporting alpha.
  It is not an ordinary comparative-policy frontier and must not be used for
  estimator-superiority, deployment, or external-validity claims.

Consequently, the held-out Scope Answerability Gain is 0 at
\(\alpha=0.01,0.05,0.10\) and 0.6037456597 at \(\alpha=0.20\). These are
descriptive finite-policy results for this frozen synthetic protocol only.

## Verifier status

| Check | Status | Audit treatment |
| --- | --- | --- |
| Pre-outcome protocol verifier required by the executor | Passed before output creation; the completed source-bound attempt and receipt are its durable execution evidence. | Does not establish post-execution semantics alone. |
| Post-execution result verifier `verify_v05_answerability_results.py` | Reported successful after the authorized execution. Its output is not a declared raw artifact, so no result-verifier report hash is asserted. | The successful completion is recorded without fabricating a missing report file. |
| Current `verify_v05_protocol_freeze.py --allow-existing-outputs` | Passed. | Read-only post-execution contract inspection. |
| Current `verify_v05_frozen_result_provenance.py` | Passed all seven checks. | Validates bytes, schemas/rows, receipt/attempt, tags, and frozen source binding without execution. |
| Current full result-verifier replay in this local environment | Failed closed at runtime provenance because installed NumPy is `2.4.6`, not receipt-pinned `2.5.2`; all other observed non-runtime checks and deterministic replay completed. | Not a frozen-result failure and not a rerun. A successful replay requires the receipt-pinned CPython 3.13 environment. |

No status above authorizes a second execution, altered raw output, outcome-driven
policy change, or broader claim than the frozen v0.5 protocol permits.
