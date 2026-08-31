# MetaShift: A Metadata-Anchored Benchmark and Audit Protocol for PM2.5 Measurement-Regime Discontinuities in Regulatory Networks

> **Draft for author verification, not a submission-ready report.** Replace all
> bracketed identity fields, verify every citation and number against the
> published evidence release, and complete the AI-use and contribution records
> before submission.

**Student author(s):** [Name(s)]  
**School, province/state, country:** [Fill in]  
**Supervising teacher(s) and affiliation(s):** [Fill in]  
**Date:** [Fill in]

## Abstract

Regulatory air-quality time series can change because of environmental
conditions, but they can also change when a monitoring network reports a
different measurement method. Conventional single-series change-point methods
can identify a numerical break but cannot determine whether the break is
station-specific relative to the regional monitoring network. We present
MetaShift-Bench, a reproducible audit protocol for documented Method Code
transitions in the United States Environmental Protection Agency (EPA) Air
Quality System (AQS). We treat a Method Code transition as a metadata anchor,
not as proof of instrument replacement or bias. For each eligible target
monitor, the protocol constructs a pre-transition, geographically constrained
counterfactual from correlated donor monitors; estimates a local residual
discontinuity; and reports quality, uncertainty, placebo, and donor-sensitivity
diagnostics.

From 2019--2025 daily AQS parameter 88101 PM2.5 records, the pipeline
reconstructs 563 persistent Method Code transitions. Of these, 261 have a
common comparison set with at least three geographic donors; 292 are retained
as insufficient-donor cases and 10 as input-window failures. A stable-regime
synthetic benchmark uses 80 distinct target monitors, with 40 for threshold
calibration and 40 for independent evaluation. Each local and matched regional
perturbation family has 200 evaluation samples. Standard synthetic control
obtains macro-F1/AUPRC of 0.829/0.906, while fixed-prior and pre-period
cross-validated MetaShift obtain 0.798/0.884 and 0.794/0.885. Although
MetaShift has lower local-effect MAE point estimates, paired bootstrap
intervals for its MAE advantage over standard synthetic control include zero.
We therefore do not claim algorithmic superiority. Instead, the contribution is
a transparent benchmark, complete event audit, graded observational evidence
hierarchy, and reproducible documentation of where cross-site attribution is
supported, unsupported, or inconclusive.

**Keywords:** Air-quality monitoring; measurement-method transition;
counterfactual estimation; change-point attribution; data quality; PM2.5.

## 1. Introduction

Air-quality data are used for public communication, compliance analysis,
scientific trend studies, and health research. A discontinuity in a station's
reported PM2.5 time series can reflect a real environmental change, such as
regional transport or meteorology, but it can also be associated with a change
in the reported measurement method. These explanations have different
implications for downstream use of the time series.

Existing change-point procedures are useful for detecting numerical shifts, but
a single time series does not supply a counterfactual answer to the question:
what would this station plausibly have measured if its reported method had not
changed? Nearby, historically correlated stations offer a partial reference for
regional conditions, subject to explicit assumptions and failure modes.

This report makes four contributions:

1. It reconstructs a metadata-anchored AQS Method Code transition inventory
   with explicit eligibility, exclusion, and donor rules.
2. It compares cross-site counterfactual estimators with single-station
   change-point baselines on stable-regime synthetic perturbations.
3. It provides a layered evidence protocol combining controlled synthetic
   truth, a full real-transition audit, time and donor placebos, same-site POC
   evidence, QA-collocation availability, uncertainty intervals, and
   donor-removal sensitivity.
4. It publishes a reproducible codebase, source manifests, locked environment,
   CI checks, and a public evidence release.

The study does **not** claim that a Method Code transition proves a physical
instrument replacement, a calibration error, or a causal measurement bias. It
also does not claim that MetaShift is universally superior to standard
synthetic control.

## 2. Background and related work

EPA AQS defines a monitor by site, pollutant parameter, and Parameter
Occurrence Code (POC); POC is not a universal physical-instrument identifier
[1, 2]. The AQS daily data files include reported Method Code and Method Name,
which make it possible to pre-specify candidate dates rather than scan all
dates without metadata [1].

PM2.5 method comparability is an empirical question. EPA maintains continuous
monitor comparability material [3], and collocated FRM/FEM analyses demonstrate
that measurement configurations can differ under real monitoring conditions
[4]. These sources motivate auditing measurement-regime metadata, but they do
not supply causal labels for every historical AQS transition.

This work uses synthetic control as a transparent counterfactual baseline [5]
and PELT as an offline change-point baseline [6]. It differs from forecasting,
imputation, generic anomaly detection, and low-cost sensor calibration: the
event dates are defined by reported method metadata, and the central objective
is an auditable comparison between station-local residual behavior and regional
shared behavior.

## 3. Data and event construction

### 3.1 Primary data

The primary corpus contains the 2019--2025 EPA AirData daily archives for AQS
parameter 88101, PM2.5 Local Conditions [1, 7]. The canonical daily signal is
`Arithmetic Mean` for `24-HR BLK AVG` records. The pipeline retains records
with observation percent at least 75, nonempty Method Code, and Event Type
other than `Excluded`. Administrative `Excluded` rows are not treated as
independent observations because they can be alternate summaries for the same
monitor-day.

Table 1. Primary 88101 data construction.

| Quantity | Count |
| --- | ---: |
| Canonical daily records | 2,424,793 |
| Monitor time series | 1,689 |
| Persistent Method Code anchors | 563 |
| Anchors with at least one geographic donor | 394 |
| Anchors with at least three geographic donors | 271 |
| Same-site alternate-POC candidates | 11 |

Each archive's URL, local modification time, byte size, SHA256, CSV member, and
row count are recorded in `artifacts/data_gate/data_manifest.csv`.

### 3.2 Anchor and donor eligibility

An anchor is a Method Code change with at least 60 calendar days before and
after the transition, at least 45 retained observations in each adjacent method
run, and a gap of at most seven days. A geographic donor must be at a different
site, within 100 km, stable in the target anchor's plus/minus 60-day window,
have at least 60 paired pre-transition observations, and have pre-transition
log-PM2.5 correlation at least 0.60. Same-site POCs are reserved for external
consistency evidence rather than used as primary geographic donors.

## 4. Methods

### 4.1 Counterfactual residual

For target series \(i\), date \(t\), and donor set \(N_i\), let

\[
z_{i,t}=\log(1+\max(y_{i,t},0)).
\]

MetaShift uses nonnegative donor weights summing to one. The reliability prior
uses pre-transition correlation and distance:

\[
R_{ij}\propto \max(\rho_{ij},0)^2\exp(-d_{ij}/50\text{ km}).
\]

Weights are fit only on the 180-to-15-day pre-anchor interval with a
nonnegative sum-to-one counterfactual objective and optional ridge and
reliability-prior penalties. The residual is calibrated by the pre-anchor
median:

\[
r_{i,t}=z_{i,t}-\sum_{j\in N_i}w_{ij}z_{j,t}
-\operatorname{median}_{s\in T_{\mathrm{cal}}}
\left(z_{i,s}-\sum_{j\in N_i}w_{ij}z_{j,s}\right).
\]

The primary event effect is the 60-day post-anchor median residual minus the
60-day pre-anchor median residual. Raw-unit effects are reported separately as
an interpretation aid.

### 4.2 Comparative methods

The benchmark includes before-after median, Bayesian mean shift, CUSUM,
rolling-MAD, PELT, nearest-neighbor difference-in-differences, standard
synthetic control, fixed-prior MetaShift, and a pre-period
cross-validated MetaShift variant.

### 4.3 Evidence tiers for real anchors

Real anchors have no physical-bias ground truth. We therefore use the following
observational evidence synthesis only for audit and case selection:

- **Supported candidate discontinuity:** pre-event quality gate passes; the
  conditional residual interval excludes zero; time-placebo probability is at
  most 0.10; and leave-one-donor-out direction is stable.
- **Not supported by available evidence:** all relevant diagnostics are
  available, but at least one fails.
- **Inconclusive:** no common comparative estimate, time placebo, or
  donor-sensitivity result is available.

These tiers are not causal or physical-instrument labels.

## 5. Experimental design

### 5.1 Stable-regime synthetic benchmark

Early synthetic smoke experiments that injected effects at real Method Code
anchors were excluded from reported results because a real unknown
discontinuity could underlie the injection. The final benchmark instead chooses
80 pseudo-anchors at least 60 days away from any target or selected donor
Method Code transition. Forty cases calibrate decision thresholds; forty
disjoint target monitors evaluate them.

The benchmark injects target-only additive steps, proportional steps, gradual
drifts, temporary steps, and variance increases, as well as matched
target-and-donor regional variants. Each perturbation variant has 200
evaluation samples. The primary outcomes are local-effect MAE, AUPRC, macro-F1,
and regional false-attribution rate. Thresholds are selected only on the
calibration partition. Main and ablation experiments use the same centralized
deterministic seed function; all 4,000 shared standard-synthetic-control rows
match exactly to tolerance \(10^{-10}\).

### 5.2 Real-anchor diagnostics

All 563 anchors are retained in the event audit. For complete comparisons, the
study reports pre-fit diagnostics, 1,000-repetition circular moving-block
bootstrap intervals conditional on fixed pre-event weights, post-transition
time placebos, donor-as-treated placebos, 200 date-resampling permutations,
and leave-one-donor-out refits. The bootstrap intervals do not include
uncertainty from donor selection or model specification.

### 5.3 External evidence and sensitivity analysis

Eleven same-site alternate-POC candidates provide spatially controlled but
non-definitive evidence. QA collocation responses are analyzed only when the
target POC and adequate matched pre/post records are present. Parameter 88502
is processed in a fully separate pipeline and is not combined with 88101.

## 6. Results

### 6.1 Synthetic benchmark

Table 2. Aggregate independent synthetic-evaluation performance.

| Method | Local-effect MAE | AUPRC | Macro-F1 | Regional FPR |
| --- | ---: | ---: | ---: | ---: |
| Standard synthetic control | 0.11687 | 0.90559 | 0.82854 | 0.026 |
| MetaShift fixed-prior | 0.10950 | 0.88418 | 0.79825 | 0.094 |
| MetaShift cross-validated | 0.10779 | 0.88486 | 0.79416 | 0.141 |
| Nearest-neighbor DiD | 0.12644 | 0.87082 | 0.77779 | 0.109 |
| Bayesian mean shift | 0.22414 | 0.50254 | 0.49782 | 0.483 |
| Before-after median | 0.24075 | 0.50253 | 0.49741 | 0.455 |
| CUSUM | N/A | 0.50235 | 0.49072 | 0.635 |
| PELT | N/A | 0.50234 | 0.49812 | 0.529 |
| Rolling-MAD | N/A | 0.50237 | 0.50252 | 0.528 |

MetaShift has lower point-estimate MAE than standard synthetic control, but
standard synthetic control has better attribution ranking, macro-F1, and
regional false-attribution rate. The paired event-cluster bootstrap difference
for fixed-prior MetaShift minus standard synthetic control is -0.00737
(95% CI [-0.01845, 0.00346]); for cross-validated MetaShift it is -0.00908
(95% CI [-0.01983, 0.00193]). Both intervals include zero.

The results vary by perturbation. MetaShift's effect MAE is lower for
additive, proportional, gradual-drift, and temporary shifts, but standard
synthetic control has stronger attribution metrics in most aggregate
comparisons. All methods perform poorly on pure variance changes. These
results rule out a general algorithm-superiority claim.

### 6.2 Real transition audit

Table 3. Full 88101 audit status.

| Status | Anchors |
| --- | ---: |
| Complete common-method comparison | 261 |
| Fewer than three geographic donors | 292 |
| Estimator input-window failure | 10 |
| Total | 563 |

For the 261 complete comparisons, the median signed 60-day log residual effect
is -0.07093 for fixed-prior MetaShift, -0.06418 for standard synthetic
control, and -0.06894 for nearest-neighbor DiD. These are observational
estimates, not measured instrument-bias labels.

Conditional block-bootstrap intervals exclude zero for 182/261 MetaShift
events, 166/261 standard synthetic-control events, and 154/261
nearest-neighbor events. Leave-one-donor-out refitting completes every removal
for 260 events; 238/260 of those retain the full-estimate direction after every
single donor removal. One donor removal is unavailable because it leaves an
insufficient comparison window and remains in the result table.

The evidence synthesis assigns 54 anchors to supported candidate
discontinuities, 113 to not-supported-by-available-evidence, and 396 to
inconclusive. The 54 are candidates for detailed qualitative review, not
confirmed method-caused biases.

### 6.3 Placebos, POC/QA, and parameter sensitivity

Of 261 complete events, 167 have ten stable post-transition time placebos.
Among them, 61 have a within-event placebo probability at most 0.10. The
200-resampling global comparison gives an upper-tail probability of 0.00498
for the actual-anchor mean score against sampled stable post-transition dates.
The donor-as-treated analysis contains 1,050 records, with median standardized
score 0.46802.

Eleven same-site alternate-POC candidates have paired pre/post data. However,
the retrieved QA collocation responses yield no case that simultaneously has
the target POC in a QA pair and at least three matched pre- and post-transition
records. QA evidence is thus an explicitly limited supplement.

The independent 88502 pipeline has 34 eligible metadata anchors, but only
three complete common-method comparisons. It demonstrates separate-pipeline
feasibility but is too small for strong generalization claims.

## 7. Discussion

The benchmark demonstrates that metadata anchors and geographic
counterfactuals make it possible to organize a large audit without equating
every numerical discontinuity with a device fault. The full audit also reveals
an important practical limitation: more than half of eligible transitions do
not have enough qualified geographic donors under the pre-specified rules.
Abstaining in these cases is more reliable than forcing a binary conclusion.

The synthetic results indicate a tradeoff. Reliability constraints can reduce
point-estimate effect error in some perturbation families, but standard
synthetic control has stronger aggregate local-versus-regional attribution
performance. This negative result is meaningful because it identifies where
additional constraints do not yet justify a general method claim.

## 8. Limitations and threats to validity

1. Method Code describes a reported measurement method, not necessarily
   physical hardware, calibration, siting, processing, or maintenance history.
2. A local residual change can arise from local emissions, meteorology,
   land-use changes, smoke, or unobserved operational factors.
3. Geographic donors are selected using observed historical agreement and may
   not remain valid after a transition.
4. Conditional block-bootstrap intervals do not capture all uncertainty from
   donor selection and model specification.
5. Same-site POC and QA evidence are sparse and do not establish instrument
   ground truth in this corpus.
6. The daily data do not supply a validated real exceptional-event label for
   causal classification.
7. The 88502 sensitivity sample is small and cannot support broad generalization.
8. Results apply to the specified AQS PM2.5 data slice and are not evidence for
   all pollutants, networks, or years.

## 9. Conclusion

MetaShift-Bench provides a reproducible way to audit reported PM2.5 measurement
method transitions using metadata anchors, cross-site counterfactuals,
synthetic truth, real-event diagnostics, and explicit abstention. The evidence
supports a benchmark-and-audit contribution, not a claim that MetaShift
outperforms standard synthetic control. The most responsible use of the
results is to flag candidate station-specific discontinuities for further
review, while preserving inconclusive and unsupported cases.

## References

[1] U.S. Environmental Protection Agency, “AirData File Formats,” [Online].
Available: https://aqs.epa.gov/aqsweb/airdata/FileFormats.html. [Accessed:
2026-08-30].

[2] U.S. Environmental Protection Agency, “Parameter Occurrence Code (POC),”
[Online]. Available:
https://aqs.epa.gov/aqsweb/documents/codingmanual/html/fromdatabase/POC.html.
[Accessed: 2026-08-30].

[3] U.S. Environmental Protection Agency, “PM2.5 Continuous Monitor
Comparability Assessments,” [Online]. Available:
https://www.epa.gov/outdoor-air-quality-data/pm25-continuous-monitor-comparability-assessments.
[Accessed: 2026-08-30].

[4] S. Khan, J. Emerson, and G. Mentz, “Evaluation of Fine Particulate Matter
(PM2.5) Concentrations Measured by Collocated Federal Reference Method and
Federal Equivalent Method Monitors in the U.S.,” *Atmosphere*, vol. 15, no. 8,
2024, doi: 10.3390/atmos15080978.

[5] A. Abadie, A. Diamond, and J. Hainmueller, “Synthetic Control Methods for
Comparative Case Studies: Estimating the Effect of California's Tobacco Control
Program,” *Journal of the American Statistical Association*, vol. 105, no. 490,
pp. 493--505, 2010, doi: 10.1198/jasa.2009.ap08746.

[6] R. Killick, P. Fearnhead, and I. A. Eckley, “Optimal Detection of
Changepoints With a Linear Computational Cost,” *Journal of the American
Statistical Association*, vol. 107, no. 500, pp. 1590--1598, 2012, doi:
10.1080/01621459.2012.737745.

[7] U.S. Environmental Protection Agency, “Obtaining AQS Data,” [Online].
Available: https://www.epa.gov/aqs/obtaining-aqs-data. [Accessed: 2026-08-30].

## Acknowledgements and contributions

Complete `docs/AUTHOR_CONTRIBUTION_TEMPLATE.md` with verified student,
teacher, and external contributions. Complete
`docs/AI_ASSISTANCE_RECORD_TEMPLATE.md` accurately before submission. Do not
represent tool-generated work as independently performed by a student.
