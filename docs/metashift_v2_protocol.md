# MetaShift v2: bounded redesign protocol

**Status:** active development protocol, dated 2026-08-30.

## Motivation

The v1 time-based paired synthetic evaluation was inspected and did not show a
reliable advantage over standard synthetic control. It remains an archived
baseline result and **must not** be reused to select v2 components or
hyperparameters.

V2 tests whether a bounded, mechanism-driven extension can add value above the
counterfactual itself:

1. quality gates that allow abstention on an unreliable target-donor fit;
2. explicit residual models for level, proportional, drift, and variance
   changes at a metadata anchor; and
3. target-series time placebos that calibrate an event's unusualness.

The audit benchmark remains the publishable foundation if V2 does not meet its
predeclared criteria.

## Split discipline

The final V2 target-event evaluation set is **state-disjoint**:

- **Final test target states:** Illinois (`17`) and Massachusetts (`25`).
- **Development target states:** every other state.
- **Model-selection labels:** controlled perturbations on development targets
  only. Real Method Code events remain observational and have no physical-bias
  labels.

The data gate has counted these test states but has not used them in any model
performance result. Their event-level scores, selected methods, or metrics must
not be inspected until V2 structure, configuration, and pass/fail rule are
committed.

Controls may cross state boundaries because they are contemporaneous input data,
but no target event from the final-test states may appear in training,
validation, threshold selection, or case selection.

## V2 pipeline

1. **Quality gate.** Require at least three geographic donors, a minimum
   pre-event paired-day count, pre-event residual scale below a development-set
   threshold, effective donor count above a threshold, and no dominant donor
   above a threshold. Events failing any condition output `insufficient_evidence`.
2. **Robust counterfactual.** Fit nonnegative, sum-to-one donor weights only on
   the 180-to-15-day pre-anchor window, with a reliability prior built from
   correlation, distance, and coverage. Estimate a calibration residual using a
   robust median.
3. **Residual shape models.** On the post-anchor residual, estimate candidate
   evidence for an immediate level shift, proportional residual shift, linear
   drift, and variance change. Use development perturbations only to set
   selection and score-calibration rules.
4. **Placebo calibration.** Apply the identical pipeline at eligible
   non-transition pseudo-dates in the same target series. The empirical
   placebo tail probability is:

   `p = (1 + count(placebo_score >= observed_score)) / (1 + number_of_placebos)`.
5. **Decision.** Return the strongest supported shape only when the quality gate
   passes, its placebo p-value is at or below the development-selected cutoff,
   and the residual shape is persistent. Otherwise return
   `insufficient_evidence`.

## Evaluation and one-shot rule

Development evaluates v1, standard synthetic control, and v2 on local and
regional controlled perturbations. It reports effect MAE, local-versus-regional
AUPRC, regional false-attribution rate, coverage, and selective error by
coverage.

V2 advances to the final state-disjoint test only if, on development data:

1. it improves at least two of effect MAE, regional false-attribution rate, and
   selective local-versus-regional discrimination compared with standard
   synthetic control;
2. the gain is not driven by one target state or a single transition family;
3. at least one V2 component loses the gain when ablated; and
4. abstention and exclusion rates are fully reported.

Otherwise, stop V2 optimization and retain only the benchmark-and-audit
contribution. Once the final test runs, it is never used for further tuning.
