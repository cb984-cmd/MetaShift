# MetaShift

> **Integrity remediation complete (2026-08-31):** The v0.2.0 release was
> superseded due to a geographic control inventory defect (multiple POCs per
> physical donor site counted as separate donors). All cross-site results have
> been rebuilt with physical-site-unique donors. The current v0.3.0 release
> passes all 26/26 release gate checks with machine-verified manuscript numbers.

MetaShift audits whether a discontinuity in an air-quality monitoring series is
more consistent with a local measurement-regime change than with a regional
environmental change. It does not treat an AQS `Method Code` change as proof of
an instrument replacement or of a causal measurement bias. The code uses such
changes only as metadata-anchored candidate dates.

The preregistered study boundary, estimand, evaluation protocol, and claims to
avoid are in [`docs/study_protocol.md`](docs/study_protocol.md).

## Current research decision

The project is proceeding on the **MetaShift-Bench** route. Two bounded model
iterations did not produce a confidence-supported, stable improvement over
standard synthetic control, so the repository does not claim estimator
superiority. [`MODEL_DECISION.md`](MODEL_DECISION.md) records the protected
test policy, the superseded early anchor-injection diagnostics, and the
evidence for this decision.

The replacement stable-regime benchmark uses 146 distinct physical monitoring
sites: 66 cases for score-threshold calibration and 80 disjoint evaluation
sites. The two splits have disjoint complete target-plus-donor physical input
footprints. Its pseudo-anchors lie at least 60 days from a target or selected
donor Method Code transition. Each local and matched regional perturbation
variant has 400 evaluation samples.

## Benchmark snapshot

At the frozen release configuration:

| Result | Value |
| --- | ---: |
| AQS 88101 eligible metadata anchors | 563 |
| Complete common-method observational comparisons | 228 |
| Explicit insufficient-donor exclusions | 325 |
| Stable synthetic evaluation samples per perturbation | 400 |
| Time-placebo-calibrated real anchors | 157 / 228 |
| Donor-as-treated placebo records | 866 |
| Independent 88502 anchors / complete comparisons | 34 / 3 |

In the stable synthetic evaluation, standard synthetic control achieved
macro-F1/AUPRC of **0.816 / 0.915**. Fixed-prior and pre-period
cross-validated MetaShift achieved **0.795 / 0.898** and **0.809 / 0.902**.
Cross-validated MetaShift's lower local-effect MAE point estimate was not
confidence-supported by paired event bootstrap, so the repository makes **no
algorithm-superiority claim**.

The `results\release_gate.json` checklist passes after two full builds in
independent Python environments produced identical hashes for all core
result artifacts. Figures are generated from saved CSV outputs only.

## Review remediation

The primary synthetic benchmark and reliability ablations now call the same
centralized seed function. Their 7,300 shared Standard synthetic-control
rows match exactly to an absolute tolerance of `1e-10`; the generated
alignment report is `artifacts\benchmark_ablation_alignment_stable_full_v2.json`.

The real-event audit now includes conditional 1,000-repetition moving-block
bootstrap intervals and leave-one-donor-out refits. These describe residual
uncertainty conditional on fixed pre-event donor weights; they do not turn
observational anchors into confirmed physical-instrument events.

An exploratory evidence synthesis combines the completed diagnostics without
changing the estimators: 34 of 563 anchors meet the FDR-screened
candidate-discontinuity rule, 122 are not supported by available evidence, and
407 are inconclusive. These are evidence tiers for audit and case selection,
not confirmed instrument failures or causal labels.

Use `requirements-lock.txt` for the frozen evidence environment. The public
CI workflow in `.github\workflows\tests.yml` installs it and runs unit tests.
The AI-use and contribution templates in `docs\` must be completed accurately
by students and the supervising teacher before any competition submission.

The remediated benchmark was reconstructed in a default environment and a
separate environment installed from `requirements-lock.txt`; all selected
core-result hashes matched. Public CI also passed on the remediation commit.

The corrected safe public evidence package is available from the
[v0.3.0-distinct-donors release](https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.0-distinct-donors).
The earlier v0.2.0 release is retained as an archived, superseded baseline
(its control inventory could count multiple POCs from one physical site as
separate donors). The v0.1.0 evidence release applies to the superseded
synthetic split. Neither superseded release should be cited for current results.

An evidence-backed English manuscript draft is at
[`paper/MANUSCRIPT_DRAFT.md`](paper/MANUSCRIPT_DRAFT.md). It is deliberately
marked as a draft: student identities, author contributions, teacher approval,
AI-use disclosure, and all submitted claims require human verification.

The targeted public-document review is intentionally conservative:
[`docs/EXTERNAL_DOCUMENT_REVIEW.md`](docs/EXTERNAL_DOCUMENT_REVIEW.md) records
20 preselected AQS metadata boundaries, but identifies **zero** dated,
site-specific public confirmations. It is context verification and a negative
external-validation result, not proof that no field change occurred.

## Data gate

The first reproducible gate scans EPA AQS daily PM2.5 archives:

```powershell
python scripts\scan_data_gate.py --download
```

It downloads `daily_88101_<year>.zip` for 2019--2025 when missing, writes
provenance hashes, identifies persistent method-code transitions, and finds
eligible geographic control monitors.

The canonical signal is `Arithmetic Mean` from `24-HR BLK AVG` records with at
least 75% observation coverage. `Excluded` event rows are deliberately removed:
they are alternative daily summaries for the same monitor-day, not independent
observations. The script fails rather than silently selecting a row if duplicate
monitor-days remain after this rule.

An eligible anchor requires a method-code change with a 60-day pre-window and
post-window, at least 45 observations in each, and no more than a seven-day gap
at the transition. A geographic control must be within 100 km, have at least
60 paired pre-transition observations, historical correlation of at least 0.60,
and no method-code transition in the anchor's plus/minus 60-day window.

The gate is passed only if the resulting inventory and controls meet the
predeclared thresholds. The subsequent study will evaluate attribution on
controlled local and regional perturbations, then report real metadata-anchor
cases separately as observational evidence.

## Benchmark commands

```powershell
python run_all.py --with-aqs-api
```

The one-command release reconstruction runs the commands below, then writes
`results\release_gate.json`.

```powershell
python scripts\build_stable_synthetic_cases.py
python scripts\run_stable_synthetic_benchmark.py --label stable_full_v2
python scripts\run_reliability_ablations.py --label stable_full_v2
python scripts\run_real_transition_audit.py --parameter-code 88101 --label 88101
python scripts\run_time_placebos.py
python scripts\run_additional_placebos.py
python scripts\analyze_external_validation.py
python scripts\scan_data_gate.py --parameter-code 88502 --output-dir artifacts\data_gate_88502 --download
python scripts\run_real_transition_audit.py --parameter-code 88502 --label 88502
python scripts\make_figures.py
python scripts\evaluate_release_gate.py
```

Generated data and results are intentionally ignored by Git. The source
scripts preserve raw-data provenance, the 563-event audit records exclusions,
and the final report will distinguish a metadata-associated discontinuity from
a confirmed instrument fault.

## Tonight's feasibility prototype

```powershell
python scripts\run_feasibility_prototype.py
```

This selects five predeclared Tier C candidates when available, runs
nearest-neighbor difference, a standard pre-period synthetic control, and the
initial reliability-weighted MetaShift estimator. It also injects a target-only
25% step at each anchor and evaluates recovery as the *increment* over the
unperturbed estimate. The output is an audit artifact, not a final performance
claim.

The same-site alternate-POC audit is run separately:

```powershell
python scripts\run_colocated_validation.py
```

It produces `artifacts\colocated_validation.csv`. These are Tier C *candidates*:
POC separates reported monitor streams but does not independently prove a
physical instrument identity or calibration truth.

With locally configured AQS API credentials, the QA-collocation download is:

```powershell
python scripts\download_qa_collocation.py
```

Raw API responses are stored under the ignored `data\raw\aqs_qa\` directory;
their credential-free request metadata and record counts are written to
`artifacts\qa_collocation_manifest.json`.

## Initial paired synthetic benchmark

```powershell
python scripts\run_synthetic_benchmark.py
```

This first benchmark selects 30 events with a long pre-transition regime and
at least three eligible donors. At each metadata date it injects matched
target-only additive and target-plus-donor regional shocks. It reports
per-event scores and a method-level summary. The paired shocks isolate an
estimator's response to the injected effect; they are not a substitute for the
final station-disjoint stable-window benchmark.
