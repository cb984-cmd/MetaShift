# v0.4.1 Core Metric Audit

**Status:** completed post-execution transcription audit. This document reads
only the preserved v0.4.1 outputs and reports the pre-registered synthetic
tasks without retuning a threshold, fitting a model, or generating a new
outcome.

## Evidence inputs and reproduction boundary

| Input | SHA-256 | Role |
| --- | --- | --- |
| `v04_core_event_results.csv` | `775f3b148e936bcb59026e6982c18ae340f83df37dbe3512cdb4370808658462` | All 2,160 frozen event rows and predictions |
| `v04_core_thresholds.json` | `189bebe6371e7f3e4223a42e2f2e7d57794f2bb5826ae7e60395658d4de2423c` | Calibration-only thresholds and confidence cutoffs |
| `v04_core_metrics.json` | `2dc66758fdd6a04adeecb4829481a9cbd379193b9018561ccceca9a681cb61ce` | Frozen evaluation summary |
| `v04_core_bootstrap.json` | `21b95b35bccba6fa591204bcb4e93a4fb8e8e20705ea2fdae9a59c4ac9385460` | Pre-registered component bootstrap |

The tracked
[`V04_CORE_CONFUSION_MATRICES.csv`](V04_CORE_CONFUSION_MATRICES.csv) has all
72 cells, including zeros and abstentions. The non-writing command below
recomputes those cells from the frozen CSV and fails on any transcription
difference:

```powershell
python scripts\verify_v04_core_metric_audit.py
```

This local audit command requires the ignored frozen files. It is not a CI
task, does not call the one-time runner, and does not alter an artifact.

## Task definitions and denominators

| Task | Observable and rule | Calibration denominator | Evaluation denominator |
| --- | --- | ---: | ---: |
| Detection | Target-only score; binary `no_change` versus `change` (`local` or `regional`) | 720 N/L/R events | 1,440 N/L/R events |
| Forced comparative scope | Comparative scope score; predict `local` when score reaches the calibration threshold and `regional` otherwise | 480 L/R events | 960 L/R events |
| Target-only scope rule | Target-only L/R task; always predict `local` under the predeclared tie rule | 480 L/R events | 960 L/R events |
| Selective comparative scope | Forced comparative prediction, answered only when calibration-defined confidence reaches its fixed cutoff | 480 L/R events | 960 L/R events |

The core contains 120 calibration and 240 evaluation synthetic components. Each
component contributes two schedule families and three N/L/R records, yielding
720 calibration and 1,440 evaluation records. Scope denominators exclude N by
task definition; no rows are dropped for non-finite scores.

## Frozen calibration quantities

| Quantity | Value |
| --- | ---: |
| Detection threshold | 0.06084251849023525 |
| Comparative scope threshold | 0.08414974339041259 |
| Selective confidence cutoff, q=0.00 | 0 |
| Selective confidence cutoff, q=0.25 | 0.034194333688153056 |
| Selective confidence cutoff, q=0.50 | 0.05609923755323942 |
| Selective confidence cutoff, q=0.75 | 0.07714486495266792 |

All quantities above were selected from calibration data before evaluation
metrics were calculated. The calibration rows below are accounting context,
not held-out performance results.

| q | Local answered | Regional answered | Total answered | Abstained |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 | 240 | 240 | 480 | 0 |
| 0.25 | 120 | 240 | 360 | 120 |
| 0.50 | 4 | 236 | 240 | 240 |
| 0.75 | 0 | 120 | 120 | 360 |

## Evaluation metrics

| Evaluation quantity | Value |
| --- | ---: |
| Target identity rate on L/R rows | 1.000000 |
| Detection average precision | 0.9952239465343127 |
| Detection precision / recall / false-positive rate | 0.968750 / 0.968750 / 0.062500 |
| Detection macro-F1 | 0.953125 |
| Forced comparative scope error / macro-F1 | 0 / 1.000000 |
| Target-only always-local scope error | 0.500000 |

The target-only error is not a fitted-model failure result: it is the
predeclared always-local tie rule applied to the balanced, matched L/R
construction. The forced comparative result is empirical only for the frozen
synthetic core and its calibration-defined threshold.

### Detection confusion matrix

| True binary label | Predicted no change | Predicted change |
| --- | ---: | ---: |
| No change | 450 | 30 |
| Change (L or R) | 30 | 930 |

### Scope confusion matrices

| Forced comparative true scope | Predicted local | Predicted regional |
| --- | ---: | ---: |
| Local | 480 | 0 |
| Regional | 0 | 480 |

| Target-only true scope | Predicted local | Predicted regional |
| --- | ---: | ---: |
| Local | 480 | 0 |
| Regional | 480 | 0 |

### Selective comparative scope accounting

| q | Cutoff | Local answered | Regional answered | Total answered | Coverage | Abstained | Answered-case error |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 0 | 480 | 480 | 960 | 1.000000 | 0 | 0 |
| 0.25 | 0.034194333688153056 | 257 | 480 | 737 | 0.767708 | 223 | 0 |
| 0.50 | 0.05609923755323942 | 16 | 472 | 488 | 0.508333 | 472 | 0 |
| 0.75 | 0.07714486495266792 | 0 | 234 | 234 | 0.243750 | 726 | 0 |

At q=0.75, the answered subset happens to contain only regional rows in this
frozen construction. That imbalance is an observed consequence of the
calibration-defined confidence rule, not an additional selection or a
generalizable fairness statement.

## Component-bootstrap uncertainty

The pre-registered bootstrap resampled complete `component_id` records with
replacement for 1,000 repetitions (seed `20260901`). Every reported metric had
1,000 valid repetitions.

| Metric | Point | 95% percentile interval |
| --- | ---: | ---: |
| Target identity rate | 1.000000 | 1.000000--1.000000 |
| Detection macro-F1 | 0.953125 | 0.924833--0.975036 |
| Forced scope error | 0 | 0--0 |
| Target-only scope error | 0.500000 | 0.500000--0.500000 |
| Selective coverage, q=0.00 | 1.000000 | 1.000000--1.000000 |
| Selective coverage, q=0.25 | 0.767708 | 0.736432--0.800026 |
| Selective coverage, q=0.50 | 0.508333 | 0.496875--0.520833 |
| Selective coverage, q=0.75 | 0.243750 | 0.212500--0.277083 |
| Selective error, q=0.00 | 0 | 0--0 |
| Selective error, q=0.25 | 0 | 0--0 |
| Selective error, q=0.50 | 0 | 0--0 |
| Selective error, q=0.75 | 0 | 0--0 |

These intervals quantify component resampling variability within the stipulated
synthetic generator. They do not provide calibrated uncertainty for real AQS
events or establish comparative-model superiority.

## Boundaries retained by this audit

1. Detection, forced scope, target-only scope, and selective scope are
   different tasks with different denominators; they must not be combined.
2. The target-only theorem applies to the stipulated observable and
   label-blind selection conditions in
   [`IDENTIFIABILITY_THEORY.md`](IDENTIFIABILITY_THEORY.md), not to donor,
   metadata, intervention, or causal information.
3. No taxonomy label, candidate AQS outcome, real-event score, or v0.3.2
   outcome was read or used for this audit.
4. The raw-scale stress suite is reported separately; it has no frozen scope
   classification or risk/coverage metrics.
