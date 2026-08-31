# MetaShift-Bench: A Metadata-Anchored Counterfactual Benchmark for Auditing Measurement-Method Transitions in Air-Quality Networks

> **Working draft (v0.3.0 distinct-donor rebuild).** All cross-site results
> verified against v2 artifacts (56/56 manuscript checks pass, 26/26 release
> gate checks pass). Replace all bracketed identity fields, verify every
> citation, and complete the AI-use and contribution records before submission.

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
reconstructs 563 persistent Method Code transitions. Of these, 228 have a
common comparison set with at least three geographic donors; 325 are retained
as insufficient-donor cases and 10 as input-window failures. A stable-regime
synthetic benchmark uses 146 distinct physical target sites, with 66 for
threshold calibration and 80 for independent evaluation. Each local and
matched regional perturbation variant has 400 evaluation samples. Standard
synthetic control obtains macro-F1/AUPRC of 0.816/0.915, while fixed-prior and
pre-period cross-validated MetaShift obtain 0.795/0.898 and 0.809/0.902.
Cross-validated MetaShift has a lower local-effect MAE point estimate
(0.09742 versus 0.09983), but its paired bootstrap difference against standard
synthetic control is -0.00240 (95% CI [-0.00772, 0.00347]). We therefore do
not claim algorithmic superiority. Instead, the contribution is a transparent
benchmark, complete event audit, graded observational evidence hierarchy, and
reproducible documentation of where cross-site attribution is supported,
unsupported, or inconclusive.

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

### 2.1 Monitoring comparability and homogenization

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

Low-cost sensor calibration work provides additional comparability context
[8--10]. Climate-record homogenization offers a closer methodological analogy:
pairwise reference series and station-history context can identify or adjust
inhomogeneities, but such work does not establish causal effects of reported
AQS Method Code changes [11].

### 2.2 Change-point and counterfactual methods

PELT provides an efficient offline multiple-change-point baseline [6], and
environmental studies have applied change-point testing to meteorologically
normalized pollutant trends [12]. These methods identify structure in a time
series but do not by themselves distinguish a station-local measurement
discontinuity from a shared regional change.

Synthetic control provides transparent donor-weighted counterfactuals and
placebo diagnostics [5]. Difference-in-differences methods formalize
counterfactual assumptions for treatment effects [13]. This study borrows
reference-series and placebo ideas as diagnostic tools, but does not claim that
a reported measurement metadata transition satisfies the causal assumptions of
a policy intervention.

### 2.3 Public data, metadata, and contribution boundary

EPA documents the Method Code field, AQS API, and AirData bulk files
[1, 7, 14, 15]. AirNow and OpenAQ provide additional public-data provenance
contexts, but are not substitutes for certified historical AQS records in this
audit [16, 17]. Table 1b summarizes the source-grounded design distinction.

Table 1b. Related-work contribution comparison.

| Design element | Source-supported antecedent | MetaShift-Bench scope |
| --- | --- | --- |
| Reported-method anchor | EPA exposes Method Code [14, 15]. | Uses reported AQS Method Code as a reproducible event anchor. |
| Network controls | Pairwise homogenization uses reference stations [11]. | Uses cross-site references as diagnostics, not causal identification. |
| Synthetic truth | PELT and homogenization use simulations [6, 11]. | Injects known effects only in stable target/donor windows. |
| Placebos | Synthetic control uses falsification [5]. | Uses time and donor-as-treated placebos. |
| Audit trail | Public AQS files and API [7, 15]. | Publishes source, eligibility, exclusion, and event-disposition records. |

We are not aware of a prior benchmark that jointly uses reported AQS
measurement-method transitions as reproducible metadata anchors, cross-site
diagnostic controls, stable-window synthetic perturbations, and complete
eligible-event accounting. This is a scoped literature statement rather than a
claim that this work is the first in any broader field.

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
| Anchors with at least three geographic donors | 238 |
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
  selection-aware residual interval excludes zero; at least 50 unique stable
  time placebos are available; raw placebo probability and BH-adjusted q value
  are each at most 0.10; and at least 90% of leave-one-donor-out refits retain
  the effect direction.
- **Not supported by available evidence:** all relevant diagnostics are
  available, but at least one fails.
- **Inconclusive:** no common comparative estimate, time placebo, or
  donor-sensitivity result is available.

These tiers are not causal or physical-instrument labels.

The primary interval is a 1,000-repetition selection-aware nested circular
block bootstrap. Each repetition jointly resamples time blocks in the
pre-transition calibration window, recomputes candidate donor correlation,
selects 3--5 donors from the fixed observed geographic/method-stability pool,
refits weights, and resamples pre/post windows. This design includes
correlation-threshold, donor-selection, and weight-fitting variation within the
observed pool, but does not include uncertainty in source metadata, station
geography, or candidate-pool construction. Fixed-weight conditional intervals
are reported as a secondary comparison.

## 5. Experimental design

### 5.1 Stable-regime synthetic benchmark

Early synthetic smoke experiments that injected effects at real Method Code
anchors were excluded from reported results because a real unknown
discontinuity could underlie the injection. The final benchmark instead chooses 146 pseudo-anchors at least 60 days away
from any target or selected donor Method Code transition. The 66 calibration
sites and 80 evaluation sites have disjoint complete target-plus-donor physical
input footprints, so a station cannot influence both threshold selection and
held-out evaluation.

The benchmark injects target-only additive steps, proportional steps, gradual
drifts, temporary steps, and variance increases, as well as matched
target-and-donor regional variants. Each perturbation variant has 400
evaluation samples. The primary outcomes are local-effect MAE, AUPRC, macro-F1,
and regional false-attribution rate. Thresholds are selected only on the
calibration partition. Main and ablation experiments use the same centralized
deterministic seed function; all 7,300 shared standard-synthetic-control rows
match exactly to tolerance \(10^{-10}\).

### 5.2 Real-anchor diagnostics

All 563 anchors are retained in the event audit. For complete comparisons, the
study reports pre-fit diagnostics, fixed-weight conditional intervals, and
1,000-repetition selection-aware nested circular moving-block intervals.
It also reports 50--100 unique stable post-transition time placebos,
Benjamini--Hochberg adjusted exploratory q values, donor-as-treated placebos,
200 date-resampling permutations, and leave-one-donor-out refits. The nested
intervals model selection within a fixed observed candidate pool but do not
include all source-metadata or candidate-pool uncertainty.

### 5.3 External evidence and sensitivity analysis

Eleven same-site alternate-POC candidates provide spatially controlled but
non-definitive evidence. QA collocation responses are analyzed only when the
target POC and adequate matched pre/post records are present. A targeted review
of 20 preselected public monitoring-document cases found no dated,
site-specific confirmation, so it is reported as a negative external-validation
result. EPA's T640/T640X Network Data Alignment documentation supplies general
method context but not a dated local site-change record [18]. Parameter 88502
is processed in a fully separate pipeline and is not
combined with 88101.

## 6. Results

### 6.1 Synthetic benchmark

Table 2. Aggregate independent synthetic-evaluation performance.

| Method | Local-effect MAE | AUPRC | Macro-F1 | Regional FPR |
| --- | ---: | ---: | ---: | ---: |
| Standard synthetic control | 0.09983 | 0.91476 | 0.81641 | 0.140 |
| MetaShift fixed-prior | 0.10344 | 0.89832 | 0.79515 | 0.150 |
| MetaShift cross-validated | 0.09742 | 0.90178 | 0.80916 | 0.135 |
| Nearest-neighbor DiD | 0.11150 | 0.88443 | 0.78852 | 0.075 |
| Bayesian mean shift | 0.24672 | 0.50116 | 0.49962 | 0.542 |
| Before-after median | 0.25330 | 0.50125 | 0.50024 | 0.505 |
| CUSUM | N/A | 0.50117 | 0.49720 | 0.581 |
| PELT | N/A | 0.50025 | 0.49976 | 0.522 |
| Rolling-MAD | N/A | 0.50112 | 0.49427 | 0.402 |

Cross-validated MetaShift has a lower point-estimate MAE than standard
synthetic control, but standard synthetic control has better attribution
ranking, macro-F1, and regional false-attribution rate. The paired
event-cluster bootstrap difference for fixed-prior MetaShift minus standard
synthetic control is 0.00361 (95% CI [-0.00401, 0.01163]); for
cross-validated MetaShift minus standard synthetic control is -0.00240
(95% CI [-0.00772, 0.00347]).
Both intervals include zero.

The results vary by perturbation. Cross-validated MetaShift has lower MAE than
standard synthetic control for additive, proportional, gradual-drift, and
temporary local shifts in this benchmark, while standard synthetic control has
stronger aggregate attribution metrics. All methods perform poorly on pure
variance changes. These results rule out a general algorithm-superiority claim.

Table 2b. Reliability-prior and ridge ablations on the same synthetic inputs.

| Variant | Local-effect MAE | Macro-F1 | Regional FPR |
| --- | ---: | ---: | ---: |
| Standard synthetic control | 0.09983 | 0.81641 | 0.140 |
| MetaShift full prior, ridge=0.1 | 0.10344 | 0.79515 | 0.150 |
| No graph-prior penalty | 0.10350 | 0.80167 | 0.133 |
| No distance term | 0.10370 | 0.80588 | 0.088 |
| No ridge penalty | 0.10289 | 0.80127 | 0.138 |
| Ridge=0.01 | 0.10304 | 0.80263 | 0.130 |
| Ridge=1.0 | 0.10500 | 0.80285 | 0.097 |
| Direct reliability weights | 0.10543 | 0.80574 | 0.105 |

No ablation restores a confidence-supported aggregate improvement over
standard synthetic control. The small effect-MAE differences among
reliability-prior variants demonstrate sensitivity to weight construction but
not a stable independent algorithm contribution.

### 6.2 Real transition audit

Table 3. Full 88101 audit status.

| Status | Anchors |
| --- | ---: |
| Complete common-method comparison | 228 |
| Fewer than three geographic donors | 325 |
| Estimator input-window failure | 10 |
| Total | 563 |

For the 228 complete comparisons, the median signed 60-day log residual effect
is -0.07093 for fixed-prior MetaShift, -0.06418 for standard synthetic
control, and -0.06894 for nearest-neighbor DiD. These are observational
estimates, not measured instrument-bias labels.

Fixed-weight conditional block-bootstrap intervals exclude zero for 159/228
MetaShift events, 145/228 standard synthetic-control events, and 134/228
nearest-neighbor events. Selection-aware nested intervals complete all 227
real comparison events with 1,000 repetitions each. Selection-aware intervals
exclude zero for 153/227 MetaShift events. The nested interval is modestly
wider on average than the fixed-weight interval because it reselects donors
and refits weights inside each bootstrap repetition.

Leave-one-donor-out refitting completes every removal for 227 events; 202/227
complete leave-one-donor-out events retain direction under every donor removal.
One donor removal is unavailable because it leaves an insufficient comparison
window and remains in the result table.

Evidence tiers contain 34 supported candidates, 122 not-supported events, and
407 inconclusive events. The 34 are candidates for detailed qualitative review,
not confirmed method-caused biases.

### 6.3 Placebos, POC/QA, and parameter sensitivity

Of 228 complete events, 157 complete events have at least 50 unique stable
post-transition time placebos. One hundred twenty of these have 100 unique
placebos. Seventy events have raw within-event placebo probability at most
0.10; 40 events pass exploratory Benjamini-Hochberg q<=0.10 screening. The
200-resampling global comparison gives an upper-tail probability of 0.00498
for the actual-anchor mean score against sampled stable post-transition dates.
The donor-as-treated analysis contains 1,050 records, with median standardized
score 0.46802.

Under strict (raw p<=0.05, donor-direction stability at least 95%), primary
(raw p<=0.10, stability at least 90%), and lenient (raw p<=0.20, stability at
least 80%) settings, the evidence-tier counts remain 34 supported, 122
not-supported, and 407 inconclusive because the shared BH q<=0.10 condition is
the limiting rule. These q values are exploratory screening quantities, not
causal p-values.

Eleven same-site alternate-POC candidates have paired pre/post data. However,
the retrieved QA collocation responses yield no case that simultaneously has
the target POC in a QA pair and at least three matched pre- and post-transition
records. A targeted review of 20 preselected official documentation cases also
found 0 dated, site-specific confirmations; all 20 only corroborate the
reported AQS metadata context or general method context. QA and document
evidence are thus explicitly limited supplements, not external causal truth.

For the same 11 POC candidates, narrow AQS API hourly windows provide nine
matched pre/post one-hour POC comparisons; eight of nine hourly difference
changes have the same sign as their daily counterpart. Qualifier fractions are
reported for target and reference POCs and are high for some records, so this
is consistency context rather than a validation label.

The independent 88502 pipeline has 34 eligible metadata anchors and 3 complete
common-method comparisons. It demonstrates separate-pipeline feasibility but is
too small for strong generalization claims.

### 6.4 Sensitivity and coverage

For the real-event effect audit, changing the symmetric pre/post window from
60 days to 45 or 90 days uses an additional method-regime stability check for
the target's intended pre/post segments and every fixed donor. The 45-day
window is complete for 224/228 events with 93.3% direction agreement to 60
days; the 90-day window is complete for 196/228 events with 93.9% agreement.
The corresponding fixed-prior MetaShift median log effects are -0.07552,
-0.07093, and -0.06908 for 45, 60, and 90 days. Three 45-day and 36 90-day
events are unavailable because the full window is not method-stable or does
not meet its specified observation requirement.

At the 60-day primary window, log-effect and raw-unit effect signs agree for
94.3% of MetaShift events, 92.3% of standard synthetic-control events, and
91.2% of nearest-neighbor events. Absolute log effects also have Spearman
correlations of 0.807, 0.833, and 0.848 with absolute raw effects,
respectively. This is reporting-scale concordance, not equivalence of causal
estimands.

On synthetic data with known effects, a pre-fit RMSE quality gate exposes a
risk-coverage tradeoff. For example, the standard synthetic-control gate
chosen at the 90th calibration percentile retains 75/80 evaluation sites and
has local-effect MAE 0.09274, versus 0.09983 at full 80-site coverage. Because
real physical-bias labels are absent, real-event gate coverage is reported as
evidence availability rather than selective classification accuracy.

The one-factor screening grid confirms that donor geography is the dominant
data-availability choice. With a minimum of three donors, the primary setting
has 238 eligible anchors; a 50 km radius has 102 and a 200 km radius has 426.
Across 70%, 75%, and 80% daily-coverage rules, the count is 243, 238, and 232;
across 45, 60, and 90-day stable-window rules, it is 252, 238, and 214. Gap,
correlation, and required-donor settings are reported in the public
sensitivity table rather than optimized post hoc.

Table 4. One-factor real-anchor screening sensitivity with at least three
geographic donors.

| Setting | Eligible anchors before donor threshold | Anchors with >=3 donors |
| --- | ---: | ---: |
| Primary: 75%, 60 days, 7-day gap, 100 km, rho>=0.60 | 563 | 238 |
| Coverage 70% | 563 | 243 |
| Coverage 80% | 563 | 232 |
| Stable window 45 days | 572 | 252 |
| Stable window 90 days | 543 | 214 |
| Transition gap 3 days | 512 | 212 |
| Transition gap 14 days | 589 | 254 |
| Donor radius 50 km | 563 | 102 |
| Donor radius 200 km | 563 | 426 |
| Correlation rho>=0.50 | 563 | 241 |
| Correlation rho>=0.70 | 563 | 230 |

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
4. Selection-aware bootstrap intervals include resampled correlation
   eligibility, donor selection, and weight fitting only within the observed
   candidate pool; they do not capture all source-metadata, geography, or model
   specification uncertainty.
5. Same-site POC and QA evidence are sparse and do not establish instrument
   ground truth in this corpus.
6. The daily data do not supply a validated real exceptional-event label for
   causal classification.
7. The 88502 sensitivity sample is small and cannot support broad generalization.
8. Results apply to the specified AQS PM2.5 data slice and are not evidence for
   all pollutants, networks, or years.
9. The external-document review found no dated, site-specific confirmation for
   its 20 selected records. Failure to locate a public notice is not evidence
   that no physical change occurred.

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

[8] A. L. Clements et al., “Low-Cost Air Quality Monitoring Tools: From Research
to Practice (A Workshop Summary),” *Sensors*, vol. 17, no. 11, Art. 2478, 2017,
doi: 10.3390/s17112478.

[9] K. K. Barkjohn, B. Gantt, and A. L. Clements, “Development and Application
of a United States Wide Correction for PM2.5 Data Collected with the PurpleAir
Sensor,” *Atmospheric Measurement Techniques*, vol. 14, pp. 4617--4630, 2021,
doi: 10.5194/amt-14-4617-2021.

[10] H.-J. Chu, M. Z. Ali, and Y.-C. He, “Spatial Calibration and PM2.5 Mapping
of Low-Cost Air Quality Sensors,” *Scientific Reports*, vol. 10, Art. 22079,
2020, doi: 10.1038/s41598-020-79064-w.

[11] M. J. Menne and C. N. Williams, Jr., “Homogenization of Temperature Series
via Pairwise Comparisons,” *Journal of Climate*, vol. 22, no. 7, pp. 1700--1717,
2009, doi: 10.1175/2008JCLI2263.1.

[12] R. V. Gagliardi and C. Andenna, “Change Points Detection and Trend Analysis
to Characterize Changes in Meteorologically Normalized Air Pollutant
Concentrations,” *Atmosphere*, vol. 13, no. 1, Art. 64, 2022, doi:
10.3390/atmos13010064.

[13] B. Callaway and P. H. C. Sant'Anna, “Difference-in-Differences With Multiple
Time Periods,” *Journal of Econometrics*, vol. 225, no. 2, pp. 200--230, 2021,
doi: 10.1016/j.jeconom.2020.12.001.

[14] U.S. Environmental Protection Agency, “Method Code,” *AQS Help File*.
[Online]. Available: https://aqs.epa.gov/aqsweb/helpfiles/method_code.htm.
[Accessed: 2026-08-30].

[15] U.S. Environmental Protection Agency, “AQS API Version 2,” [Online].
Available: https://aqs.epa.gov/aqsweb/documents/data_api.html. [Accessed:
2026-08-30].

[16] AirNow, “About the Data,” [Online]. Available:
https://www.airnow.gov/about-the-data/. [Accessed: 2026-08-30].

[17] OpenAQ, “API Documentation,” [Online]. Available:
https://docs.openaq.org/. [Accessed: 2026-08-30].

[18] U.S. Environmental Protection Agency, “Supplemental Information on the
EPA's Update of PM2.5 Data From T640/T640X PM Mass Monitors,” May 13, 2024.
[Online]. Available:
https://www.epa.gov/system/files/documents/2024-05/2_supplemental-info_t640-data-update_final-05-13-2024.pdf.

## Acknowledgements and contributions

### Topic origin

[Describe how the research topic was selected. State whether the topic was
suggested by an advisor, discovered through reading, or originated from student
curiosity. Be specific about the intellectual path from initial interest to
the research question.]

### Data acquisition

All data were downloaded programmatically from the U.S. EPA Air Quality System
(AQS) public data portal using the AQS Data API. No proprietary or restricted
data were used. API credentials are free and available to any registered user.
The data processing pipeline is fully documented in the public repository.

### Data analysis and computation

All statistical analysis, algorithm implementation, and computation were
performed using Python with the NumPy, pandas, SciPy, ruptures, and matplotlib
libraries. The complete source code is publicly available at
https://github.com/cb984-cmd/MetaShift. All reported results are reproducible
from the committed source code and frozen configuration files.

### Experimental design and execution

The study protocol, evaluation split, and analysis decisions were predeclared
in `docs/study_protocol.md` before examining evaluation results. The synthetic
benchmark uses physically disjoint calibration (66 sites) and evaluation
(80 sites) splits. No evaluation-set result was used to modify the method or
its parameters.

### Paper writing

[State who drafted each section. Note any AI-assisted drafting and the extent
of human review and revision. Reference `docs/AI_ASSISTANCE_RECORD_TEMPLATE.md`
for detailed AI usage disclosure.]

### Advisor relationship and role

[State each advisor's institutional affiliation, the nature of the advising
relationship (school teacher, university faculty, etc.), and what specific
guidance each advisor provided. State explicitly whether any paid tutoring or
commercial training is involved. Per competition rules, advisors from
for-profit companies or training institutions are not permitted.]

### Individual contributions

[For each team member, state their specific technical contributions:
which code they wrote, which experiments they ran, which analysis they
performed, which sections they drafted. Every team member must have a
substantive contribution; listing without contribution is prohibited.]

### Difficulties encountered

[Describe the main technical challenges encountered during the research and
how they were resolved. Include the physical-donor uniqueness defect discovered
during development and the complete rebuild that followed.]

### External help and AI assistance

This project used AI coding assistants (GitHub Copilot) for code generation,
debugging, data pipeline construction, and manuscript drafting assistance.
All AI-generated code and text were reviewed, verified, and modified by the
student author(s). The complete AI assistance record is maintained in
`docs/AI_ASSISTANCE_RECORD_TEMPLATE.md` and must be accurately completed
before submission. No AI tool independently designed the research question,
chose the methodology, or interpreted the results.

### Disclosure

[State whether this work has been submitted to or presented at any other
competition, conference, or publication venue. If yes, provide details.]
