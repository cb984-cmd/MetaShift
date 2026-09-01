# v0.5 Power and Feasibility Analysis

**Status:** pre-outcome planning calculation. This document uses the frozen
protocol dimensions only; it does not inspect a prospective evaluation result.

## Component count

The evaluation split contains 360 independent synthetic components. Every
component contributes every one of the 640 grid cells and both matched scope
arms. Component identity is therefore the resampling and planning unit; neither
rows, dates, arms, nor grid cells are treated as independent observations.

The full protocol produces:

| Split | Components | Matched pairs | Scope-arm events |
| --- | ---: | ---: | ---: |
| Calibration | 120 | 76,800 | 153,600 |
| Evaluation | 360 | 230,400 | 460,800 |

The 360-component design supports stable plotting of a continuous
coverage/error boundary in every cell while retaining a component-disjoint
calibration partition. It is not designed as a hypothesis test of estimator
superiority.

## Planning reference for zero errors

If there were one independent binary error opportunity per fully answered
component and zero errors, the one-sided exact-binomial 95% reference bound
would be

\[
1-0.05^{1/360}=0.00829.
\]

That calculation is only a planning reference. The actual reports aggregate
two correlated scope arms and many correlated grid cells per component; they
therefore use a 1,000-repetition component-cluster percentile bootstrap rather
than pretending that 460,800 rows are independent. Selective policies can also
have substantially fewer answered components.

Accordingly, the \(\alpha=0.01\) frontier point is a predeclared descriptive
operating tolerance. It must not be interpreted as a general 1% population
risk certification, even if a particular frozen cell observes zero errors.

## Feasibility checks fixed before execution

The chosen dimensions permit:

1. a complete 640-cell grid for every component instead of outcome-selected
   subregions;
2. an exact target-fixed pair for every local/shared comparison;
3. q=0 and q=1 endpoints plus three partial-scope conditions;
4. independent component calibration and evaluation;
5. bounded innovations so deterministic envelope assumptions can be tested;
6. availability-normalized donor mixtures with at least three donors on every
   date; and
7. a bounded raw-scale field that exercises nonlinear transform leakage without
   being misrepresented as an exact analysis-scale intervention.

The main computational risk is the roughly 307,200 matched pairs. The runner
must generate panels in memory and use vectorized score construction, while
checking representative results against
`metashift.counterfactual.anchor_residual_windows`. Any performance shortcut
that changes this residual semantics fails the protocol.
