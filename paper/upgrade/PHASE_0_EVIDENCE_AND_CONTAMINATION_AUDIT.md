# Phase 0: Evidence and Contamination Audit

**Status:** Gate 0 decision: PASS for theory and novelty work only.
**Audit date:** 2026-09-01
**Scope:** This is a metadata-only audit. It did not open candidate signal
arrays, candidate post-window observations, scores, fitted weights, or outcome
metrics. It does not select a v0.4 evaluation set.
The phase read no candidate post-window observations.

## Decision

`v0.3.2-evidence-final` remains immutable. The proposed
`v0.4.0-identifiability-audit` is a separate research version, not a relabeling
or reinterpretation of v0.3.2. Phase 0 establishes that there are potential
physical-site-disjoint sources for a future protocol and records the
contamination boundary. It does **not** establish that any candidate is
eligible, representative, or genuinely blind.
Candidate availability is not eligibility or blindness.

The Gate 0 pass authorizes the closest-work audit and theory specification. It
does not authorize data retrieval, stable-window screening, new synthetic
evaluation, threshold selection, or manuscript rewriting.

## Immutable v0.3.2 evidence inventory

| Item | Location | SHA-256 or immutable identifier |
| --- | --- | --- |
| Evidence release | `v0.3.2-evidence-final` | commit `57d678ecabebff724d898abe626c9ef80538775b` |
| Public release | `https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final` | release gate 35/35 |
| Tracked evidence authority | `configs/current_evidence_summary_v2.json` | `7a4c7219af77cb80c7c3aa5a2175a1ffa29f6ac826f8ec95305185d66f05bc55` |
| Frozen benchmark configuration | `configs/benchmark_release_v2.json` | `510fca2c90f858e7a40af9c27962a0af02305e837a4edfb55fa90ddabb6e6f64` |
| Stable case and donor manifest | `artifacts/stable_synthetic_case_manifest.json` | `77b695d3e8e7a230512fd4b697b93d3ce0f920116fb15286ea20cce5d9e123e7` |
| Stable split audit | `artifacts/stable_synthetic_case_split_audit.json` | `56671b8d44ed2581d7be3a181178551bece2daecdf6357a9d91fceb0806956d5` |
| Stable case-and-donor binding | `configs/benchmark_release_v2.json` | `065b1b65c231c5298fb4969a7b5669f3ae8850b9228d50afee7d98422575e099` |
| Complete public-safe archive | `evidence_bundle/MetaShift-Bench-evidence-57d678ecabeb.zip` | `4cc5293ad3dc5725c49d8804ed3782b434df2b408e4143f99fc9176c322163bf` |
| Archive file manifest | `evidence_bundle/MetaShift-Bench-evidence-57d678ecabeb-manifest.json` | `76a4de7748e31b2c7c5f08b76cf1fdb1d609ec997842bf336d7d0506bfb383b9` |

`artifacts/`, `results/`, and `evidence_bundle/` are intentionally ignored by
Git because they contain generated results or release assets. Their authoritative
paths, byte counts, and hashes are indexed in the tracked
`configs/current_evidence_summary_v2.json`. Clean CI must validate that tracked
authority file and must not require a local generated artifact.

## Previously viewed and therefore non-blind material

| Material | Established status | v0.4 use boundary |
| --- | --- | --- |
| Stable synthetic benchmark | 146 physical target sites: 66 calibration and 80 evaluation | The complete 294-site target-plus-donor input footprint is previously used. It cannot be presented as a new v0.4 blind evaluation source. |
| Existing synthetic results | `stable_full_v2` and all derivatives | May be cited only as frozen retrospective v0.3.2 evidence; not for v0.4 tuning or post hoc threshold selection. |
| Real 88101 metadata anchors | All 563 anchors were audited | May remain a complete retrospective event universe, not a labeled accuracy or selective-risk test. |
| 88502 sensitivity | 34 anchors and 3 complete comparisons | Previously analyzed; it is not an independent monitoring network or a clean blind test. |
| V2 state-disjoint target manifest | 67 Illinois/Massachusetts target IDs; `outcome_accessed: false` | A legacy v2 selection artifact. Do not treat it as a v0.4 blind set without a new full-footprint and access-provenance review. |
| 2023--2025 held-out event outputs | Existing output artifact | Contaminated for any new model, selector, or threshold decision. |

The stable-synthetic split itself is valid for the frozen version: it has zero
cross-split input overlap, with 154 calibration and 140 evaluation physical
input sites. That validity does not make its observed outcomes fresh for v0.4.

## Metadata-only candidate availability

`scripts/audit_v04_candidate_components.py` constructs connected components
using only the 238 anchors with at least three distinct physical donors, their
physical target/donor identifiers, and the previously used stable-benchmark
input identifiers. It does not load `data/raw/`, time-series values, date-window
completeness, or performance outputs.

The local audit reproduces:

| Quantity | Value |
| --- | ---: |
| Eligible anchors in the metadata graph | 238 |
| Connected target-plus-donor components | 25 |
| Prior stable-benchmark input footprint | 294 physical sites |
| Components disjoint from that footprint | six components |
| Eligible anchors in those components | nine eligible anchors |
| Physical sites in those components | 35 physical sites |

These six components are a feasibility signal only. Metadata-level separation
does not imply a complete pre/post window, enough donors at a chosen
pseudo-anchor, representative sampling, or unobserved outcomes. In particular,
running the existing stable-case builder would load candidate series and is
prohibited until a pre-outcome v0.4 protocol has been committed.

## Potential validation sources

1. **Unused 88101 input components:** Six metadata-only components are
   physically disjoint from the v0.3.2 stable benchmark. They are the first
   candidate source for a pre-registered protocol, subject to an explicit
   provenance and eligibility check.
2. **Forward-time 88101 data:** A future period can be specified before data
   acquisition, using only metadata and pre-window information. No 2026
   post-window observations were downloaded or queried in this phase. Future
   availability must be checked only after the protocol is frozen.
3. **Independent network:** No independent monitoring-network source is
   currently documented. Same-site alternate POC, QA-collocation, and public
   document records are AQS-contextual evidence, not an independent network.

## Safe actions and leakage prohibitions

Safe before Gate A:

- Verify frozen hashes and release identities.
- Analyze primary literature and formalize theory.
- Recompute physical-site graph membership from metadata identifiers only.
- Write a prospective protocol without outcome-derived thresholds.

Prohibited before a committed pre-outcome protocol:

- Read candidate post-window observations, residuals, scores, effect estimates,
  or synthetic metrics.
- Run stability, pre-fit, donor-selection, or window-completeness routines on
  candidate data when their result could influence case inclusion.
- Reuse the viewed 80-case evaluation partition or its target-plus-donor
  footprint as new blind evidence.
- Tune a model, gate, threshold, loss, donor weighting rule, or perturbation
  grid from any prior held-out output.
- Treat a Method Code transition, a residual, or a real evidence tier as a
  physical fault, instrument replacement, or causal bias label.

## Reproducible checks

CI-safe, tracked-only check:

```powershell
python -m unittest tests.test_v04_phase0_audit -v
python scripts/verify_v04_phase0_audit.py
```

Local evidence check, requiring ignored generated artifacts but still not
reading candidate outcomes:

```powershell
python scripts/audit_v04_candidate_components.py
python scripts/verify_v04_phase0_audit.py --verify-local-artifacts
```

## Gate 0 rationale

Gate 0 passes because the v0.3.2 identity and hashes are explicitly protected,
all known viewed partitions are separated from possible v0.4 sources, and the
candidate graph audit is metadata-only. Its limits are explicit: no valid v0.4
evaluation manifest exists yet, and neither the six components nor any
forward-time source may be called blind until Phase 3 freezes and records the
full source, eligibility, physical-footprint, and outcome-access procedure.
