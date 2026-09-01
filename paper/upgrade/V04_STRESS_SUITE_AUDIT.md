# v0.4.1 Raw-Scale Stress-Suite Audit

**Status:** completed post-execution diagnostic audit. This document examines
only the preserved raw-scale stress output. It neither reruns the benchmark nor
converts the stress rows into classification, selective-risk, coverage, causal,
or external-validity evidence.

## Evidence boundary

The sole source is
`artifacts/v04_identifiability_core/v04_stress_results.csv`:

| Property | Value |
| --- | ---: |
| SHA-256 | `c93cfda1183584ba01d8fe82f09ef870acac45c2e59b3b5045de39859f6a763a` |
| Rows | 1,800 |
| Calibration rows | 600 |
| Evaluation rows | 1,200 |
| Families | 5 |
| Bound-satisfied rows | 1,800 / 1,800 |
| Bound failures | 0 |

Each row retains only `protocol_id`, `component_id`, `split`,
`stress_family`, `stress_seed`, `maximum_residual_leakage_bound`,
`absolute_median_effect_leakage`, and `bound_satisfied`.

The tracked
[`V04_ASSUMPTION_FAILURE_MATRIX.csv`](V04_ASSUMPTION_FAILURE_MATRIX.csv)
contains all ten family-by-split aggregates. The command below recomputes the
table from every frozen row and fails on a source hash, schema, count, bound,
or transcription mismatch:

```powershell
python scripts\verify_v04_stress_suite_audit.py
```

It is a read-only local audit and requires the ignored preserved output. It
does not invoke `run_v04_identifiability_benchmark.py`.

## Complete accounting and bound results

| Stress family | Calibration / evaluation rows | Max bound, calibration / evaluation | Max absolute median leakage, calibration / evaluation | Bound failures |
| --- | ---: | ---: | ---: | ---: |
| Raw additive step | 120 / 240 | 0.035456 / 0.036759 | 0.003335 / 0.003193 | 0 / 0 |
| Raw proportional step | 120 / 240 | 0.284073 / 0.357443 | 0.000259 / 0.000253 | 0 / 0 |
| Raw gradual drift | 120 / 240 | 0.028775 / 0.036759 | 0.003115 / 0.002727 | 0 / 0 |
| Raw temporary step | 120 / 240 | 0.035456 / 0.032106 | 0.002164 / 0.002442 | 0 / 0 |
| Raw variance increase | 120 / 240 | 1.893821 / 2.382951 | 0.000622 / 0.000758 | 0 / 0 |

The largest recorded per-case bound is 2.3829509992445113 and the largest
recorded absolute median-effect leakage is 0.0033346022811573395. Those
aggregates are descriptive only; pass/fail is checked separately on every one
of the 1,800 stored rows.

## Assumption map

| Family | Frozen perturbation | Retained bound | Exact-cancellation status |
| --- | --- | --- | --- |
| Raw additive step | Add 2.0 raw units after anchor | Sharp nonnegative additive bound | Outside exact core: raw-to-log increment is value-dependent |
| Raw proportional step | Multiply by 1.15 after anchor | Global proportional Lipschitz bound, \(a=0.15\) | Outside exact core: raw-to-log increment is value-dependent |
| Raw gradual drift | Capped 2.0-unit, 30-day raw ramp | Pointwise sharp nonnegative additive bound | Outside exact core: raw-to-log increment is value-dependent |
| Raw temporary step | 2.0 raw-unit change for 30 post-anchor days | Sharp nonnegative bound on affected dates | Outside exact core: raw-to-log increment is value-dependent |
| Raw variance increase | Common signed innovation scaled from pre-anchor MAD | Global signed clipping-aware one-Lipschitz bound | Outside exact core: no frozen L/R target-equivalence result |

These are the assumptions and bounds specified before execution in
`configs/v04_identifiability_protocol.json` and derived in
[`THEORY_SPECIFICATION.md`](THEORY_SPECIFICATION.md). A passing bound means
only that the stored residual-leakage diagnostic stayed within its declared
limit for that synthetic case.

## Metrics deliberately unavailable

The frozen stress CSV contains no local-versus-regional labels, target-only
scores, comparative scores, predictions, thresholds, confidence values,
abstention decisions, or bootstrap samples. Therefore it cannot support:

1. detection accuracy, precision, recall, or macro-F1;
2. forced or selective scope error;
3. answered-case risk or coverage;
4. a comparison with a baseline method; or
5. causal, instrument, AQS, or physical-realism attribution.

No post-execution classifier or risk diagnostic was fitted to fill these
fields. The exact-core task metrics remain separately bounded in
[`V04_CORE_METRIC_AUDIT.md`](V04_CORE_METRIC_AUDIT.md).

## Retained conclusion

All five pre-registered raw-scale stress families met their per-case
clipping-aware residual-leakage bounds. This validates only the stated
stress-diagnostic implementation on its synthetic inputs. It does not extend
the exact analysis-scale construction, repair the frozen v0.3.2
unequal-seed variance limitation, or establish a real monitoring-network
claim.
