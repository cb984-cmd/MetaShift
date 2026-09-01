# v0.4 Blind-Set Power and Feasibility Audit

**Status:** Gate A feasibility input. This is a metadata-only design audit; it
does not inspect candidate signal values, stable windows, post-window effects,
residuals, fitted weights, scores, or classifications.

## Candidate sources

| Candidate source | Metadata-only count | Physical leakage status | Intended scope | Decision |
| --- | ---: | --- | --- | --- |
| Disjoint parameter-88101 components | 6 non-overlapping components, 9 anchors, 8 target physical sites, 35 physical sites | Zero overlap with the frozen 294-site v0.3.2 target-plus-donor footprint; outcome independence is not established | Potential descriptive realism-stress layer, with all uncertainty clustered by connected component | Not selected for confirmatory inference |
| New independently generated analysis-scale core | To be fixed before generation | Independent of every v0.3.2 physical site and outcome | Exact theorem-to-code validation and synthetic selective risk/coverage | Selected for the pre-outcome protocol |
| 2026 forward parameter-88101 data | No source catalog or full-footprint manifest yet | Not established | None | Not selected |
| v0.3.2 stable benchmark and 88502 sensitivity | Previously viewed | Contaminated for a new v0.4 evaluation | Frozen retrospective context only | Rejected |

The disjoint 88101 count comes only from anchor, donor, and physical-site
relationships: six connected components, nine anchor rows, eight distinct
target sites, and 35 total physical sites. A target site may have more than
one anchor row, so nine anchors are not nine independent target units.

## Independent-unit and precision analysis

The largest non-overlapping physical-input unit for the 88101 candidate is its
connected component. Repeated anchors or pseudo-anchors within a component
share target/donor information and cannot be treated as independent
external-validation observations. Physical-footprint separation removes direct
input reuse, but it does not prove component outcome independence: components
may still share regional shocks or collection processes. The candidate has six
non-overlapping components, not six empirically established independent
clusters.

Under the explicitly optimistic planning model of independent, approximately
normal component-level paired differences and a two-sided \(\alpha=0.05\)
paired t-test with five degrees of freedom, the standardized minimum detectable
difference at 80% power is **1.434544782040** standard deviations. This is too
large for a credible general comparative-performance claim.

Conditional on six nonzero component differences, an exact two-sided
component-level sign test can reject at 0.05 only if all six signs agree: its
smallest p-value is **0.03125**. Exact-zero ties must be discarded and the
effective component count reported; with fewer than six nonzero components,
this two-sided sign test cannot reject at 0.05. Even if an alternative makes
the favorable nonzero sign probability 0.80 independently at each component,
its two-sided rejection probability is only **0.262208**. This is optimistic
planning arithmetic, not a measured outcome or a claim that component
differences are normal or independent in the future study.

## Decision

The theorem-aligned, independently generated analysis-scale core is the only
selected pre-outcome source for a confirmatory *synthetic-contract* claim. It
can establish that the code implements the declared information and residual
properties; it cannot establish external physical validity in a monitoring
network.

The six isolated AQS components are retained only as a possible separately
protocolized realism-stress layer. They can support complete accounting and
component-clustered descriptive results, but they do not have enough
independent clusters for a broad confirmatory performance or information-gain
claim. No candidate post-window outcome has been accessed while making this
decision.

## Reproducible metadata-only check

```powershell
python scripts/audit_v04_blind_feasibility.py
```

The output is an ignored local audit artifact. It may be regenerated from the
same ignored metadata inventories, but it is not required by clean CI.
