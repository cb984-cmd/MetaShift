# Reproducibility

## Scope

This repository reconstructs the MetaShift-Bench data audit and synthetic
benchmark from public EPA AQS AirData files. Raw downloads, AQS API responses,
and generated results are excluded from Git because they are large, may be
updated by EPA, or require local credentials.

## Evidence roles and freeze boundaries

| Evidence package | Permitted role | Status |
| --- | --- | --- |
| `v0.3.2-evidence-final` | Real-data deployment, missingness, and abstention context | Immutable historical release |
| v0.4 | Exact endpoint and raw-scale leakage sanity checks | Immutable historical release |
| `v0.5-answerability-frontier` | Synthetic scope-answerability boundary evidence | One-time immutable execution |

The v0.5 experiment is not a reconstruction target. Its sole execution is
bound to commit `14fd0fee4fb015e6c661299041e35ff704a27286`, tags
`v0.5.0-answerability-freeze` and
`v0.5.0-answerability-execution-claim`, and receipt SHA-256
`954fc9b56a8f526644320aa7b1b15ed76844e400e1394ffd8f733729996a87c9`.
Do not run `scripts\run_v05_answerability_frontier.py --execute`, replace its
outputs, or tune a policy from its held-out evaluation data.

The frozen v0.3.2 reconstruction configuration is
[`configs/benchmark_release_v2.json`](configs/benchmark_release_v2.json).
It defines the stable synthetic case split, effect-strength grid, estimator
settings, and bootstrap seed. It also records the stable-case manifest hash
expected for the current AirData snapshot.

The CI-safe v0.3.2 public evidence contract is
[`configs/current_evidence_summary_v2.json`](configs/current_evidence_summary_v2.json).
It records the frozen tag and commit, headline values, provenance boundary, and
SHA-256 hashes for each local artifact source. Rebuild or verify it locally
after a full evidence reconstruction:

```powershell
python scripts\build_current_evidence_summary.py --check
```

## Environment

```powershell
python -m pip install -r requirements-lock.txt
```

`requirements-lock.txt` is the frozen evidence environment. The version-range
`requirements.txt` remains for development only. The project has been run with
Python 3.13; package versions are also recorded in the generated run manifest.

## Full reconstruction

### v0.3.2 real-data reconstruction

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

### v0.5 frozen-result verification

Use an interpreter matching the runtime recorded in
`artifacts\v05_answerability_frontier\v05_execution_receipt.json`. The
provenance verifier fails closed if the runtime differs. It only reads frozen
outputs and Git objects:

```powershell
$py = '<receipt-pinned Python interpreter>'
& $py scripts\verify_v05_frozen_result_provenance.py --verify-results
```

The verifier checks the execution receipt, source and result hashes, one-time
attempt chain, frozen tags, schemas, full deterministic result recomputation,
and the absence of an unauthorized rerun. It is intentionally distinct from
the v0.3.2 reconstruction pipeline.

## Generated outputs

All generated files live under ignored `data/`, `artifacts/`, or `results/`.
Important outputs include:

| Output | Purpose |
| --- | --- |
| `artifacts/data_gate/data_manifest.csv` | Public 88101 source provenance |
| `artifacts/stable_synthetic_case_manifest.json` | Stable synthetic case hash and split |
| `artifacts/stable_synthetic_case_split_audit.json` | Complete target-plus-donor physical-input split audit |
| `artifacts/stable_synthetic_stable_full_v2_metrics.csv` | Threshold-isolated synthetic metrics |
| `artifacts/reliability_ablation_stable_full_v2_metrics.csv` | Reliability-component ablation metrics |
| `artifacts/real_transition_88101_event_audit.csv` | All 563 anchors and explicit audit status |
| `artifacts/real_transition_88101_event_intervals.csv` | Conditional block-bootstrap event intervals |
| `artifacts/leave_one_donor_out_summary.csv` | Donor-removal sensitivity by event |
| `artifacts/time_placebo_summary.csv` | Per-event time-placebo calibration |
| `artifacts/external_validation_evidence.csv` | Same-site POC and QA evidence status |
| `artifacts/data_gate_88502/data_manifest.csv` | Independent 88502 source provenance |
| `results/release_gate.json` | Machine-readable release checklist |
| `artifacts/v05_answerability_frontier/v05_execution_receipt.json` | One-time v0.5 receipt and result root |
| `artifacts/v05_answerability_frontier/v05_answerability_frontier.csv` | Frozen finite-policy answerability envelope |
| `artifacts/v05_answerability_frontier/v05_certificate_validity.csv` | Frozen structural-certificate diagnostics |
| `configs/v05_frozen_result_manifest.json` | v0.5 result hash, schema, source, and tag binding |

The `MODEL_DECISION.md` file documents why the project does not claim
algorithmic superiority over standard synthetic control.

## v0.3.2 public evidence bundle

After the full reconstruction, verify the frozen summary and create a safe
evidence bundle for review:

```powershell
python scripts\build_current_evidence_summary.py --check
python scripts\export_evidence_bundle.py
```

The export requires a passing release gate for the current Git commit and a
clean source worktree. It contains summary results, hashes, manifests, figures,
configuration, and audit tables. It rejects raw AirData archives and AQS API
responses, and it does not include credentials.

## Local v0.5 frozen-evidence archive

After all tracked work is committed and the worktree is clean, make a local
content-addressed archive without rerunning v0.5:

```powershell
$py = '<receipt-pinned Python interpreter>'
& $py scripts\export_v05_frozen_evidence.py
```

The archive and sidecar manifest are ignored under `evidence_bundle\`. The
exporter reads only existing evidence and Git objects, excludes credentials and
raw AQS data, and does not publish an archive. Any release or submission
sharing decision remains human-owned.

## Formal report reproduction

The authoritative report source is `paper\latex\`, not the historical
`paper\MANUSCRIPT_DRAFT.md`. The clean final-mode build from source commit
`61186839aefa3b7780134cf7936c5424dd39b1e6` produced the current 57-page
canonical PDF, 1,569,094 bytes, SHA-256
`399334fee9a19954e4b37c6f5d84aa2efa048899a5816ab7fe061415f62797c5`.
It passed all 18 formal-report checks, including receipt-bound v0.5
verification, 22 figure placements with 44 150/300-DPI crops, and a font
audit.

Future report-source edits require a clean-worktree final build:

```powershell
$py = '<receipt-pinned Python interpreter>'
Push-Location paper\latex
& $py scripts\build_paper.py
Pop-Location
```

This technical build does not fill identity, contribution, advisor,
compensation, AI-use, taxonomy, signature, stamp, plagiarism, or final
truthfulness requirements. See
`paper\latex\HUMAN_COMPLETION_CHECKLIST.md`.

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
included only as historical diagnostics; v0.3.2 real-data claims remain
limited to the passing release-gate evidence.

The verified v0.3.2 complete and compact archives, their SHA-256 manifests, the
35/35 release gate, the 12/12 document-consistency report, and the 57/57
manuscript-number report are attached to the public
[v0.3.2-evidence-final release](https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final)
at `57d678ecabebff724d898abe626c9ef80538775b`. The v0.1, v0.2, v0.3.0, and
v0.3.1 releases are superseded and must not be cited for v0.3.2 real-data
results.
The v0.5 evidence is separately receipt-bound and must be cited only within
its synthetic scope-answerability boundary.

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
