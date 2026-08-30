# MetaShift

MetaShift audits whether a discontinuity in an air-quality monitoring series is
more consistent with a local measurement-regime change than with a regional
environmental change. It does not treat an AQS `Method Code` change as proof of
an instrument replacement or of a causal measurement bias. The code uses such
changes only as metadata-anchored candidate dates.

The preregistered study boundary, estimand, evaluation protocol, and claims to
avoid are in [`docs/study_protocol.md`](docs/study_protocol.md).

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
