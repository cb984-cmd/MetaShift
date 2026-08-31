# MetaShift study protocol

## Working title

**MetaShift: a metadata-anchored benchmark and audit protocol for PM2.5
measurement-regime discontinuities**

The title is intentionally narrower than “instrument-change bias attribution.”
An AQS `Method Code` identifies a reported method, not necessarily a physical
instrument replacement, calibration fault, or causal source of a value change.
AQS also defines a monitor by site, parameter, and POC; POC is not a universal
physical-instrument identifier.

## Research question

When an AQS PM2.5 series has a documented Method Code transition, is its
target-minus-control residual near that date unusually large and persistent
relative to placebo dates and placebo target stations?

The project estimates evidence *consistent with* a station-specific
measurement-regime discontinuity. It does not infer the true physical cause or
automatically correct historical concentrations. MetaShift is evaluated as one
interpretable counterfactual estimator, not presumed or claimed to dominate
standard synthetic control.

## Data and analytical unit

The initial corpus is EPA AQS `daily_88101_<year>.zip` for 2019--2025. The
analytical unit is a daily series keyed by:

`State Code`, `County Code`, `Site Num`, and `POC`.

The primary signal is `Arithmetic Mean` from PM2.5 local-condition records with
`Sample Duration = 24-HR BLK AVG`, at least 75% observation coverage, a
nonempty Method Code, and an `Event Type` other than `Excluded`. The latter is
essential: the daily archive contains alternative `Included` and `Excluded`
summaries for the same monitor-day, so treating both as observations would
duplicate and distort the series.

The daily archive does not contain a Qualifier column. Qualifier-based checks
therefore require a later hourly-data audit and are not used as an initial
label or assumed to be available in this phase.

## Frozen anchor and control rules

An eligible metadata anchor is a change in Method Code with:

1. At least 60 calendar days before and after the transition;
2. At least 45 retained observations in each adjacent method run; and
3. At most a seven-day gap between the adjacent runs.

Geographic donors must be a different physical site, within 100 km, stable in
the anchor's plus/minus 60-day window, have at least 60 paired pre-transition
days, and have pre-transition log-PM2.5 correlation of at least 0.60. The
counterfactual uses the highest-ranked three to five donors. A same-site,
different-POC series is never a geographic donor; it is reserved for an
external consistency check.

The national data gate produced 563 eligible anchors, 394 with at least one
geographic donor, 271 with at least three, and 11 with a same-site alternate
POC donor. These values are data-availability evidence, not counts of confirmed
measurement biases.

Transitions explicitly enabling “Network Data Alignment” will be analyzed as a
configuration-change stratum. They will not be merged without distinction with
transitions whose method descriptions indicate different analyzer families.

## Comparative estimators

For target series `i`, anchor date `tau`, and donors `j`, transform a
concentration `y` to:

`z = log(1 + max(y, 0))`.

Fit nothing using post-anchor data. Assign eligible donor weights:

`w_ij proportional to rho_ij^2 exp(-d_ij / 50 km)`,

where `rho_ij` is pre-transition correlation and `d_ij` is distance. On each
date, normalize weights over available donors. Compute a calibrated residual:

`r_it = z_it - sum_j(w_ij z_jt) - median_pre[z_it - sum_j(w_ij z_jt)]`.

The primary effect is the difference between median residuals in the 60-day
post- and pre-anchor windows. The standardized MetaShift score divides this
effect by the robust MAD scale of a 180-to-15-day pre-anchor calibration
residual. Raw-unit residual differences are reported as a secondary
interpretation aid. All conclusions compare it with nearest-neighbor
difference-in-differences, standard synthetic control, and single-station
change-point baselines.

## Evaluation

Real Method Code anchors have no ground-truth label for physical bias. Thus,
event F1, localization error, and effect MAE are measured only in controlled
perturbation experiments:

1. Select stable target-donor windows with no nearby method transition.
2. Inject target-only additive, proportional, and gradual-drift changes.
3. Inject matched target-and-donor changes representing regional environmental
   shifts.
4. Compare MetaShift with CUSUM, PELT, and a rolling robust-z baseline under
   identical windows and tuning rules.
5. Report AUPRC/F1 for local-versus-shared change, detection localization
   error, and effect MAE by perturbation type and magnitude.

For real anchors, report the residual effect, both fixed-weight conditional and
selection-aware uncertainty intervals,
pre-transition fit, donor composition, missingness, pseudo-date placebo
distribution, donor-as-treated placebo distribution, and leave-one-donor-out
sensitivity. A real event is classified only as supported, unsupported, or
inconclusive as a candidate method-associated discontinuity.

The exploratory evidence-synthesis rule labels a candidate as
`supported_candidate_discontinuity` only when its pre-event quality gate
passes, its selection-aware residual interval excludes zero, its stable
post-transition time-placebo probability is at most 0.10, and its
leave-one-donor-out effect direction remains stable. Missing comparative,
placebo, or donor-sensitivity evidence yields `inconclusive`; failed available
diagnostics yield `not_supported`. These tiers organize evidence and case
selection; they do not identify a physical causal mechanism.

The selection-aware interval jointly block-resamples target and candidate-donor
observations in the pre-event calibration window, recomputes donor correlation
eligibility, selects up to five donors, refits reliability-constrained weights,
and then block-resamples pre/post comparison windows. It conditions on the
observed geographic, method-stability, and availability candidate pool; it does
not model uncertainty in source metadata, station geography, or that initial
candidate-pool construction.

The primary daily AQS files do not supply a validated real-world
exceptional-event label suitable for causal attribution, and the retrieved QA
collocation responses do not provide adequate matched pre/post validation for
the candidate target POCs. Therefore, this study does not claim an
exceptional-event-specific real-label accuracy result. Environmental negative
controls are instead the matched regional synthetic perturbations, stable
post-transition time placebos, and donor-as-treated placebos. QA and qualifier
availability are reported as graded evidence limitations.

## Paper-strengthening extension protocol

The v0.2.0 evidence release remains an archived, reproducible benchmark
baseline. The following extension is frozen before its new outcome analyses;
it does not reopen the closed claim that MetaShift is superior to standard
synthetic control.

The extension adds a Method Code transition taxonomy based only on the old and
new AQS Method Codes, their reported Method Names, and predeclared official
source links. `configs/method_transition_taxonomy_v1.csv` must cover every
observed transition pair exactly. It may not use real-event effects, evidence
tiers, synthetic evaluation outcomes, or post-transition rankings to assign
classes. The initial machine-readable table is explicitly pending independent
student and teacher review; it is not a human-verified equipment-history
record.

Stratified real-event results will be descriptive distributions of residual
diagnostics by frozen class. They cannot establish a physical instrument
replacement or causal measurement bias. Groups with fewer than 20 complete
comparisons will be reported descriptively only. Predeclared between-class
tests use bootstrap median-difference intervals and appropriately
Benjamini--Hochberg-adjusted exploratory comparisons.

The existing 80 stable-synthetic evaluation targets have already been viewed.
They may not select or tune any new model, threshold, gate, taxonomy rule, or
selective-decision mechanism. Any new learned model or gate requires a new
blind stable-synthetic manifest with at least 60 targets and completely
disjoint target-plus-donor physical input footprints from both the existing
66 calibration and 80 evaluation target sets.

The frozen fixed-weight interval coverage study completed 23,360
effect-identifiable synthetic instances. Its nominal-95% conditional
moving-block intervals covered only 62.47%--67.56% of held-out truths across
the four cross-site methods. Target-cluster split-conformal nominal-90%
intervals covered 98.22%--99.56% and were therefore substantially
conservative. These results are retained as a negative calibration finding:
fixed-weight intervals may be reported only as conditional resampling
diagnostics, not as coverage-calibrated real-event confidence intervals. No
bootstrap block length, conformal score, threshold, or model parameter may be
changed using this 80-site evaluation result.

## Claims and limitations

The final report must not claim that Method Code proves hardware replacement,
that POC tracks a physical instrument, that nearby stations automatically form
a causal control group, or that a residual break proves measurement bias.
Wildfire, meteorology, local emissions, siting changes, network-wide
operational changes, data screening, and schedule changes remain potential
confounders.

Core references for these boundaries are EPA's AQS file-format documentation,
POC definition, method-code table, and continuous-monitor comparability
guidance; the design also cites the PELT and synthetic-control method papers.
