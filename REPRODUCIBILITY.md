# Reproducibility

## Scope

This repository reconstructs the MetaShift-Bench data audit and synthetic
benchmark from public EPA AQS AirData files. Raw downloads, AQS API responses,
and generated results are excluded from Git because they are large, may be
updated by EPA, or require local credentials.

The frozen source configuration is
[`configs/benchmark_release_v1.json`](configs/benchmark_release_v1.json).
It defines the stable synthetic case split, effect-strength grid, estimator
settings, and bootstrap seed. It also records the stable-case manifest hash
expected for the current AirData snapshot.

## Environment

```powershell
python -m pip install -r requirements-lock.txt
```

`requirements-lock.txt` is the frozen evidence environment. The version-range
`requirements.txt` remains for development only. The project has been run with
Python 3.13; package versions are also recorded in the generated run manifest.

## Full reconstruction

Run from the repository root:

```powershell
python run_all.py --with-aqs-api
```

This command:

1. validates the unit tests twice;
2. scans the public 2019--2025 daily 88101 archive and records URL, file
   modification time, byte size, SHA256, CSV member, and row count;
3. constructs stable synthetic pseudo-anchor cases and runs the synthetic
   benchmark and reliability ablations;
4. runs the 563-anchor observational audit and its time, donor-as-treated,
   date-resampling, POC, QA-collocation, external-document, and case-study
   evidence analyses;
5. independently scans and audits parameter code 88502; and
6. writes `results/release_gate.json`, which lists every release requirement
   and whether the generated artifacts satisfy it, after generating all
   figures from saved result tables. A failed gate exits nonzero and prevents
   evidence-bundle export.

The pipeline also runs `scripts/verify_manuscript_numbers.py`, which compares
the manuscript's required numeric fragments with generated result artifacts and
fails if a displayed number is stale or inconsistent.

`--with-aqs-api` requires the local `AQS_API_EMAIL` and `AQS_API_KEY`
environment variables. They are read only at runtime, never printed or written
to repository files. Without API credentials, use `python run_all.py` to
rebuild the public-data core; the release gate will explicitly mark external
QA validation as incomplete.

## Generated outputs

All generated files live under ignored `data/`, `artifacts/`, or `results/`.
Important outputs include:

| Output | Purpose |
| --- | --- |
| `artifacts/data_gate/data_manifest.csv` | Public 88101 source provenance |
| `artifacts/stable_synthetic_case_manifest.json` | Stable synthetic case hash and split |
| `artifacts/stable_synthetic_case_split_audit.json` | Complete target-plus-donor physical-input split audit |
| `artifacts/stable_synthetic_stable_full_v1_metrics.csv` | Threshold-isolated synthetic metrics |
| `artifacts/reliability_ablation_stable_full_v1_metrics.csv` | Reliability-component ablation metrics |
| `artifacts/real_transition_88101_event_audit.csv` | All 563 anchors and explicit audit status |
| `artifacts/real_transition_88101_event_intervals.csv` | Conditional block-bootstrap event intervals |
| `artifacts/leave_one_donor_out_summary.csv` | Donor-removal sensitivity by event |
| `artifacts/time_placebo_summary.csv` | Per-event time-placebo calibration |
| `artifacts/external_validation_evidence.csv` | Same-site POC and QA evidence status |
| `artifacts/data_gate_88502/data_manifest.csv` | Independent 88502 source provenance |
| `results/release_gate.json` | Machine-readable release checklist |

The `MODEL_DECISION.md` file documents why the project does not claim
algorithmic superiority over standard synthetic control.

## Public evidence bundle

After the full reconstruction, create a safe evidence bundle for review:

```powershell
python scripts\export_evidence_bundle.py
```

The export requires a passing release gate for the current Git commit and a
clean source worktree. It contains summary results, hashes, manifests, figures,
configuration, and audit tables. It rejects raw AirData archives and AQS API
responses, and it does not include credentials.

## Complete public-safe archive

To package every safe local result, figure, process record, and a source
snapshot for a GitHub Release asset:

```powershell
python scripts\export_complete_public_archive.py
```

The generated archive remains ignored by Git. It includes every safe file under
`artifacts\`, `results\`, and `figures\`, plus the full source snapshot and Git
history. It explicitly excludes raw EPA archives, raw AQS API responses,
credentials, and virtual environments. Legacy development artifacts are
included only as historical diagnostics; final claims remain limited to the
passing release-gate evidence.

## Cross-environment consistency

After two independent full runs, capture and compare the deterministic core
result hashes:

```powershell
python scripts\verify_reproducibility.py capture --label environment_a
python scripts\verify_reproducibility.py capture --label environment_b
python scripts\verify_reproducibility.py compare `
  --first artifacts\reproducibility_hashes_environment_a.json `
  --second artifacts\reproducibility_hashes_environment_b.json
```

The comparison hashes core CSV and JSON result artifacts, including
event-level intervals, donor sensitivity, and main/ablation alignment. It
also includes real-event evidence tiers. It excludes files with run timestamps
or API request timestamps. Each capture records its exact Git commit. The
release gate accepts a cross-environment comparison only when both captures
and the release source are the same commit.
