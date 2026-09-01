# v0.4.1 Frozen Result Provenance

## Purpose

This record preserves the exact bytes from the sole authorized
`v0.4.1-execution-freeze` execution. It does not rerun, tune, subset, or
reinterpret the benchmark. The machine-readable authority is
[`configs/v04_frozen_result_manifest.json`](../../configs/v04_frozen_result_manifest.json).

## Frozen input and output chain

| Item | Authority |
| --- | --- |
| Executed annotated tag | `v0.4.1-execution-freeze` |
| Executed commit | `b286221f13b5da8c18dc30226114400d071421d1` |
| Producing command | `python scripts\run_v04_identifiability_benchmark.py --execute` |
| Prior preserved, unrun tag | `v0.4.0-execution-freeze` at `9f4660a88beef829e6c3cac72e0d59134b929add` |
| Post-execution command | `python scripts\verify_v04_identifiability_results.py --require-results` |
| Post-execution check result | 14/14 passed |

The tracked manifest lists all eight preserved files, their exact byte sizes,
SHA-256 hashes, CSV row counts and schemas where applicable, evidence roles,
and the receipt/attempt chain. The five payload hashes remain linked to the
durable execution receipt. The result-verification artifact is separately
recorded because it is a post-execution deterministic replay check.

## Local verification

No experiment is executed by this command:

```powershell
python scripts\verify_v04_frozen_result_provenance.py
```

It fails if any declared byte hash, file size, CSV schema, row count, durable
receipt chain, result-verifier check count, local annotated tag, or peeled
`origin` tag differs from the tracked manifest.

## Archival mechanism

The repository's established release-asset location is the ignored
`evidence_bundle/` directory. After the tracked manifest and verification
script are committed, create the one non-overwriting content-addressed archive:

```powershell
python scripts\export_v04_frozen_evidence.py
```

It produces exactly these declared paths:

```text
evidence_bundle/MetaShift-v04-frozen-evidence-b286221f13b5.zip
evidence_bundle/MetaShift-v04-frozen-evidence-b286221f13b5-manifest.json
```

The archive contains only the eight frozen v0.4.1 files, the tracked
provenance manifest, and an exact source snapshot of
`v0.4.1-execution-freeze`. It scans output bytes and the source snapshot for
credential-like content, refuses an unclean worktree, and refuses to overwrite
an existing archive or sidecar.

Publishing a GitHub Release asset remains a human publication decision. Once
authorized, the exact prepared command is:

```powershell
gh release create v0.4.1-execution-freeze `
  --title "MetaShift v0.4.1 Frozen Synthetic Evidence" `
  --notes-file paper\upgrade\V04_FROZEN_RESULT_PROVENANCE.md `
  evidence_bundle\MetaShift-v04-frozen-evidence-b286221f13b5.zip `
  evidence_bundle\MetaShift-v04-frozen-evidence-b286221f13b5-manifest.json
```

## Interpretation boundary

The preserved outputs provide confirmatory evidence only for the frozen
synthetic construction. They do not establish causal mechanism attribution,
physical instrument truth, unrestricted AQS scope classification, or
algorithmic superiority. The taxonomy review remains human-only and is not
part of this archive.
