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
python -m pip install -r requirements.txt
```

The project has been run with Python 3.13. The package versions installed in a
new environment are recorded in the generated run manifest.

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
   date-resampling, POC, and QA-collocation evidence analyses;
5. independently scans and audits parameter code 88502; and
6. writes `results/release_gate.json`, which lists every release requirement
   and whether the generated artifacts satisfy it, after generating all
   figures from saved result tables.

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
| `artifacts/stable_synthetic_stable_full_v1_metrics.csv` | Threshold-isolated synthetic metrics |
| `artifacts/reliability_ablation_stable_full_v1_metrics.csv` | Reliability-component ablation metrics |
| `artifacts/real_transition_88101_event_audit.csv` | All 563 anchors and explicit audit status |
| `artifacts/time_placebo_summary.csv` | Per-event time-placebo calibration |
| `artifacts/external_validation_evidence.csv` | Same-site POC and QA evidence status |
| `artifacts/data_gate_88502/data_manifest.csv` | Independent 88502 source provenance |
| `results/release_gate.json` | Machine-readable release checklist |

The `MODEL_DECISION.md` file documents why the project does not claim
algorithmic superiority over standard synthetic control.

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

The comparison intentionally hashes core CSV artifacts rather than files with
run timestamps or API request timestamps.
