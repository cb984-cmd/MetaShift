# v0.5 Frozen Result Provenance

The sole authorized v0.5 execution completed at
`14fd0fee4fb015e6c661299041e35ff704a27286`.  Its immutable source authority is
the annotated `v0.5.0-answerability-freeze` tag; the separately annotated remote
one-time claim is `v0.5.0-answerability-execution-claim`.

`configs/v05_frozen_result_manifest.json` seals the ignored result bundle and
attempt record by exact byte count, SHA-256, CSV schema, and row count.  It also
pins receipt/attempt linkage, both annotated tag objects and peeled remote refs,
and every Git-blob hash in the execution input allowlist.

Run `python scripts\verify_v05_frozen_result_provenance.py` for a read-only
byte/provenance audit. Add `--verify-results` in the receipt-pinned CPython 3.13
environment to also run the existing read-only full deterministic replay
verifier; it intentionally fails closed on a different installed runtime.
Neither command invokes the executor.

After committing the tracked provenance files, run
`python scripts\export_v05_frozen_evidence.py` from a clean worktree. It writes
the declared ignored archive and sidecar only when neither already exists, binds
the archive to a `git archive` snapshot of the freeze tag, and only removes its
own lock or temporary files on failure. It never overwrites outputs or reruns.

This is protocol-restricted synthetic evidence, not evidence of estimator
superiority, real-AQS scope attribution, causal or physical mechanisms, external
validity, or deployment readiness.
