# v0.5 Theory-to-Code Audit

**Status:** pre-outcome implementation audit. The table binds the limited
theory to executable semantics before an execution manifest exists.

| Contract | Formal condition | Implementation | Enforced by |
| --- | --- | --- | --- |
| Nested channels | \(O_T=X\), \(O_C=(X,D)\); no donor field enters target-only policy | `target_only_*` fields in `run_v05_answerability_frontier.py` are constant local predictions; comparative policies read only score/cutoff | `test_policy_application_cannot_fit_on_evaluation`; protocol forbidden-side-channel list |
| Matched target law | Local/shared target arrays are byte-identical | `rows_for_component` constructs one `target_raw`, hashes it once, and emits it for both arms | target-group digest accounting and `test_complete_miniature_grid_preserves_target_and_q0_identity` |
| q=0 impossibility control | \(\lambda_j=0\) leaves the entire comparative observation unchanged | q=0 branch copies local donor arrays/log paths before scoring | q=0 identity checks in runner, accounting, and result verifier |
| Availability normalization | \(\widetilde w_{jt}=w_ja_{jt}/\sum_kw_ka_{kt}\) | `normalized_availability_weights` mirrors `weighted_donor_series`; vectorized runner uses `_normalize_weights` | direct normalization test and 640-cell `semantic_crosscheck` against `anchor_residual_windows` |
| Exact analysis-scale gap | \(A^L-A^S=\overline{q_th_t}\) before raw field | `build_partial_scope_pair`, `effective_donor_participation`, and the signed mean score | `test_exact_partial_scope_identity_and_scores` |
| Raw-scale limit | no exact \((1-q)h\) claim after raw field | `_raw_additive_bound` and `raw_additive_mean_leakage_bound` report a separate bound | raw leakage unit test and semantics cross-check |
| Bounded envelope | \(B=2M+2(U_-+U_+)+B_{\rm raw}+C\) | `structural_error_bound` | exact-formula unit test; every generated row records both arm bounds |
| Structural separation | \(\kappa=G_{\min}-(B_L+B_S)>0\) | `structural_certificate` | asymmetric-bound threshold and nonpositive-margin abstention tests |
| Robust threshold | \(\tau=H-G_{\min}/2+(B_S-B_L)/2\) | `structural_certificate` | test rejects nominal midpoint in asymmetric-bound example |
| Calibration isolation | thresholds/cutoffs use calibration only | `calibration_policies` accepts only the calibration split; `apply_policies` receives frozen policy values | evaluation-split rejection and mock-based no-fit test |
| Finite empirical frontier | fixed policy set, no post-outcome retuning | `policy_metrics` reports all policies; at every reporting tolerance, `answerability_frontier` considers the forced policy plus all four calibration-targeted confidence policies and selects only a descriptive evaluation envelope | protocol verifier, cross-tolerance regression test, and frozen result replay |
| Dependence-aware uncertainty | resample whole components | `component_policy_metrics` and `component_bootstrap` operate on per-component counts | vectorized/reference bootstrap point-estimate equivalence test |
| One-time execution | a remote claim precedes any local output allocation | `acquire_remote_execution_claim` atomically pushes an annotated claim tag; `acquire_attempt` persists `claimed` before directory allocation | remote-claim and post-claim allocation-failure regression tests; receipt and result-verifier tag checks |

## Intentional non-equivalences

1. The v0.5 signed mean score is not `estimate_metadata_anchor`'s median
   `log_effect`. It is separately named and confined to the affine
   construction.
2. The synthetic structural certificate is not a real-data rule because its
   lower participation, signal, and error bounds are design information.
3. The finite-policy held-out frontier is not the population supremum
   \(\Gamma_{\mathcal I}\).
4. A source-bound deterministic replay validates generator implementation; it
   does not turn the stipulated generator into a real-world mechanism model.
