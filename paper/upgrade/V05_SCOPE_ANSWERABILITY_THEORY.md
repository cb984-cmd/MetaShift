# v0.5 Scope Answerability Theory

**Status:** pre-outcome theory gate. The exact statements in this document
concern a stipulated synthetic observation experiment. They do not establish
physical mechanism, instrument history, causal measurement bias, real-AQS
scope attribution, or estimator superiority.

## 1. Three distinct questions

For a change candidate, this work distinguishes:

| Question | Required information | Permitted v0.5 claim |
| --- | --- | --- |
| Detection | A target path | Whether the constructed target path changed |
| Scope | A target path and a declared comparative channel | Synthetic local-versus-shared scope answerability |
| Mechanism | Metadata, QA, maintenance, and independent human review | No v0.5 mechanism claim |

The Method Code taxonomy remains blocked by human review and affects only the
third question. It is not an input to this synthetic scope study.

## 2. Observation channels and answerability

Let \(Y\in\{L,S\}\) be a binary synthetic scope label, with a stipulated joint
law \(\mathsf P\). The channels are

\[
O_T=X,\qquad O_C=(X,D),\qquad O_E=(X,D,E),
\]

where \(X\) is the declared target-only path, \(D\) contains only donor paths,
fixed weights, and availability indicators, and \(E\) denotes optional external
evidence. A policy \(\phi=(g,s)\) maps an allowed channel and independent
auxiliary randomness to a predicted scope \(g\) and answer indicator
\(s\in\{0,1\}\). The policy must have positive coverage when its conditional
risk is evaluated.

The population **Scope Answerability Frontier** is

\[
\Gamma_{\mathcal I}(\alpha)=
\sup_{\substack{\phi\ \mathcal I\text{-measurable}\\
                \Pr_{\mathsf P}(s_\phi=1)>0\\
                \Pr_{\mathsf P}(g_\phi(O)\ne Y\mid s_\phi=1)\le\alpha}}
\Pr_{\mathsf P}(s_\phi=1).
\]

If no positive-coverage policy satisfies the constraint, the frontier is
defined as zero. This is the inverse form of an established selective
risk--coverage objective, not a newly invented generic criterion.

For two nested channels evaluated under the same law, label space, loss, and
policy class, define the **Scope Answerability Gain**

\[
\operatorname{SAG}_{\mathcal I\to\mathcal J}(\alpha)
=\Gamma_{\mathcal J}(\alpha)-\Gamma_{\mathcal I}(\alpha).
\]

The name is specific to this benchmark. Its nonnegativity under information
refinement is a direct application of the established comparison-of-experiments
principle.

### Proposition 1: target-only impossibility

Suppose \(\Pr(Y=L)=\Pr(Y=S)=1/2\) and

\[
\mathcal L(X\mid Y=L)=\mathcal L(X\mid Y=S).
\]

If every prediction and selection decision uses only \(X\) and auxiliary
randomness conditionally independent of \(Y\) given \(X\), then every
positive-coverage target-only policy has conditional scope error \(1/2\).
Consequently,

\[
\Gamma_T(\alpha)=0\quad\text{for }\alpha<1/2.
\]

**Proof.** Target-only selection preserves the balanced prior and equal
class-conditional accepted laws. Conditional on an accepted \(X\), either
prediction has probability \(1/2\) of error. This is the balanced special case
of the Bayes-risk argument in
[`IDENTIFIABILITY_THEORY.md`](IDENTIFIABILITY_THEORY.md). \(\square\)

The conclusion does not apply to unequal priors, pair identifiers, row order,
scope-generation metadata, donor availability summaries, or any other
label-dependent side channel.

### Proposition 2: information-refinement monotonicity

If every \(O_T\)-measurable policy can be implemented using \(O_C\) by
discarding \(D\), then

\[
\Gamma_C(\alpha)\geq\Gamma_T(\alpha).
\]

The same argument gives \(\Gamma_E(\alpha)\geq\Gamma_C(\alpha)\) when \(E\)
augments rather than changes the experiment. This is a policy-set inclusion
argument equivalent to a Blackwell refinement in this nested-channel setting.
It does not imply that a finite-sample fitted comparative rule improves, nor
that the inequality is strict.

## 3. Partial-scope exact analysis-scale construction

The exact v0.5 core uses the same residual definition as the project
counterfactual implementation. On a retained date, let \(a_{jt}\) be donor
availability, \(w_j\ge0\) fixed pre-anchor weights, and

\[
\widetilde w_{jt}=\frac{w_ja_{jt}}{\sum_k w_ka_{kt}},
\qquad \sum_j\widetilde w_{jt}=1.
\]

Let \(z=f(y)=\log(1+\max(y,0))\), let \(b\) be a fixed pre-anchor offset, and
write

\[
r_t=z_t-\sum_j\widetilde w_{jt}z_{jt}-b.
\]

For an analysis-scale target schedule \(h_t\) and donor participation values
\(\lambda_{jt}\in[0,1]\), construct a local arm and a comparison arm:

\[
z^L_t=z_t+h_t,\quad z^L_{jt}=z_{jt},
\]

\[
z^S_t=z_t+h_t,\quad z^S_{jt}=z_{jt}+\lambda_{jt}h_t.
\]

The target paths are therefore exactly identical between the two arms. Define

\[
q_t=\sum_j\widetilde w_{jt}\lambda_{jt}.
\]

### Proposition 3: partial-scope residual identity

With arm-invariant availability, retained dates, weights, preprocessing, and
pre-anchor offset,

\[
r^L_t-r_t=h_t,\qquad
r^S_t-r_t=(1-q_t)h_t.
\]

Thus the exact pointwise comparative separation is \(q_th_t\). This is an
algebraic identity, not a general empirical identifiability result.

For the v0.5 theorem score, use the signed mean residual effect over fixed
retained pre and post windows:

\[
A=\frac{1}{|W_{\rm post}|}\sum_{t\in W_{\rm post}}r_t
 -\frac{1}{|W_{\rm pre}|}\sum_{t\in W_{\rm pre}}r_t.
\]

The mean is selected only because it is affine in the stated residual
increments. It does not replace the median score used by v0.4 or claim
greater robustness. If \(h_t=H>0\) on every scored post date, then

\[
A^L-A^0=H,\qquad
A^S-A^0=H-\overline{q_tH},
\]

and the exact score-center gap is

\[
G=A^L-A^S=\overline{q_tH}.
\]

For a variable schedule, the correct gap is
\(\overline{q_th_t}\), not \(\bar q\,\bar h\).

## 4. Structural Answerability Certificate

The certificate is deliberately a **synthetic design-information-assisted**
diagnostic. It receives declared bounds and the generated participation design;
it is not a deployable real-network certificate when \(h_t\),
\(\lambda_{jt}\), or the error bounds are unavailable.

Let the local and partially shared scores obey

\[
|A^L-H|\le B_L,\qquad
|A^S-(H-G)|\le B_S.
\]

For the exact v0.5 core, \(B_L\) and \(B_S\) are conservative deterministic
envelopes derived from bounded noise, donor mismatch, a known raw-field
leakage bound, and known donor contamination. Let \(q_t\ge q_{\min}\) and
\(h_t\ge H_{\min}>0\) on every scored retained date. Then

\[
G\ge G_{\min}=q_{\min}H_{\min}.
\]

Define the structural margin

\[
\kappa=G_{\min}-(B_L+B_S).
\]

### Proposition 4: interval-separation certificate

If \(\kappa>0\), the score intervals are disjoint. In particular, every
threshold in

\[
\left(H-G_{\min}+B_S,\ H-B_L\right)
\]

correctly separates the two arms under the stated bounds. The implementation
uses the deterministic robust threshold

\[
\tau_{\rm cert}
=H-\frac{G_{\min}}{2}+\frac{B_S-B_L}{2}.
\]

It answers only if \(\kappa>0\), predicting local when
\(A>\tau_{\rm cert}\) and shared otherwise.

**Proof.** The upper partial-score bound is at most
\(H-G_{\min}+B_S\), while the lower local-score bound is
\(H-B_L\). Their strict ordering is exactly \(\kappa>0\); their midpoint is
\(\tau_{\rm cert}\). \(\square\)

The superficially similar rule that uses the nominal midpoint
\(H-G_{\min}/2\) is rejected: interval separation alone does not put that
midpoint between asymmetric error intervals. It would require the stronger
condition \(G_{\min}>2\max(B_L,B_S)\).

### Error-envelope contract

For the bounded synthetic generator, let \(M\) bound absolute donor mismatch,
and let \(U_-\) and \(U_+\) bound target and donor idiosyncratic noise in the
pre and post score windows. The pre-anchor offset cancels from the signed
mean score, yielding the conservative base envelope

\[
B_{\rm base}=2M+2(U_-+U_+).
\]

For a shared raw additive post-field \(c\), with
\(g_c(y)=f(y+c)-f(y)\), the per-arm leakage contribution is bounded by

\[
B_{{\rm raw},a}=
\frac1{|W_{\rm post}|}\sum_t
L_{c,t}\sum_j\widetilde w_{jt}|y_{t,a}-y_{jt,a}|,
\]

where \(L_{c,t}\) is the valid nonnegative-domain additive-increment
Lipschitz constant at that date. A post-only donor contamination of magnitude
at most \(C\) on any normalized donor mixture has contribution at most
\(B_{\rm contam}=C\). The implementation therefore uses

\[
B_a=B_{\rm base}+B_{{\rm raw},a}+B_{\rm contam},
\quad a\in\{L,S\}.
\]

This triangle-inequality envelope is intentionally conservative. A violation
of its assumptions, including nonfinite values, altered retained dates,
unbounded noise, or an unmodeled transformation, invalidates the certificate
for that case and requires abstention.

## 5. Raw-scale boundary

The partial-scope identity is exact only for the analysis-scale construction.
For a raw-scale intervention, the transformed residual increment is generally

\[
[f(\psi(y_t,c_t))-f(y_t)]-
\sum_j\widetilde w_{jt}
[f(\psi(y_{jt},\lambda_{jt}c_t))-f(y_{jt})],
\]

not \((1-q_t)h_t\). The v0.5 raw-field factor is therefore an explicitly
bounded stress factor inside the envelope above. It is not an exact
partial-scope theorem or a claim of physical realism.

## 6. Frozen empirical estimands

The execution does not estimate the unrestricted population supremum
\(\Gamma_{\mathcal I}\). Before evaluation, it freezes a finite policy set
\(\mathcal P\), all calibration rules, and all aggregation rules. On the
held-out synthetic components it reports only

\[
\widehat\Gamma_{\mathcal I}^{\mathcal P}(\alpha)
=\max_{\substack{\phi\in\mathcal P\\
                  \widehat R_\phi\le\alpha}}
\widehat C_\phi,
\]

with zero if no positive-coverage predeclared policy qualifies. This is a
frozen-generator empirical envelope, not a population optimum, a
distribution-free conditional-risk guarantee, or a post-evaluation policy
choice. Every candidate policy is reported even when it is not on the
envelope. The frozen \(\mathcal P\) includes all four separately
calibration-selected confidence policies at every reported \(\alpha\), not
only the confidence policy whose calibration target has the same numeric
value.

## 7. Claim classification

| Statement | Status |
| --- | --- |
| Bayes-risk limits, reject options, risk--coverage optimization, and information refinement | Established theory |
| Propositions 1--2 applied to the stipulated nested synthetic channels | Established theory specialized to this construction |
| Proposition 3 and the bounded score decomposition | Newly derived construction-specific algebra |
| Proposition 4 under the declared envelopes | Newly derived synthetic sufficient condition |
| Frozen v0.5 frontiers, gains, error, coverage, and certificate behavior | Empirical observations only after execution |
| Scope accuracy, mechanism, or causal inference on AQS records | Explicit nonclaim |

## 8. Adversarial audit

| Rejected shortcut | Failure | Retained correction |
| --- | --- | --- |
| Use \(\bar q\bar h\) for time-varying schedules | Availability can correlate with participation or schedule magnitude. | Use \(\overline{q_th_t}\), and use \(q_{\min}H_{\min}\) only as a lower bound. |
| Use a nominal midpoint after \(\kappa>0\) | Asymmetric error bounds can put a local score below that midpoint. | Use the interval-safe threshold \(\tau_{\rm cert}\). |
| Derive a deterministic certificate from Gaussian noise | Gaussian paths are unbounded. | Use bounded innovations and an explicit envelope. |
| Treat \(q=0\) as an ordinary comparative success case | Both target and donor observations are identical across arms. | Report it separately as a negative-control impossibility stratum. |
| Treat a calibration cutoff as a conditional-risk guarantee | Calibration selection alone gives no such general guarantee. | Report observed held-out conditional error and component-cluster uncertainty only. |
| Treat certificate inputs as normally observed operational covariates | Participation, injected signal, and bounds are simulation design information. | Label the certificate oracle-assisted and synthetic-only. |
