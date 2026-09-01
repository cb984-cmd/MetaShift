# v0.4 Identifiability Theory

**Status:** bounded formalization for the frozen synthetic construction. This
document proves a statement about a stipulated observable feature vector. It
does not prove causal attribution, physical-instrument truth, AQS external
validity, or superiority of any estimator.

## 1. Scope and notation

For the binary scope task, let \(Y\in\{L,R\}\) denote local and regional
scope, let \(\Pr(Y=L)=\pi\in(0,1)\), and write \(q=1-\pi\). Let

\[
P_L=\mathcal L(X\mid Y=L),\qquad P_R=\mathcal L(X\mid Y=R),
\]

where \(X\) is explicitly the target-only observable. Let
\(\mu=P_L+P_R\), with densities \(p_L=dP_L/d\mu\) and
\(p_R=dP_R/d\mu\). The scope classifier uses zero-one loss.

The theorem below says nothing about another observable vector such as donor
paths, metadata, intervention records, or a causal structural model. Those
may contain additional information. It also distinguishes scope attribution
from detecting that a target path changed at all.

## 2. Bayes-risk identity

### Theorem 1: binary scope Bayes risk

For every measurable target-only classifier \(g\),

\[
\inf_g\Pr(g(X)\ne Y)
=\int\min\{\pi p_L(x),q p_R(x)\}\,d\mu(x)
=\frac12\left(1-\int\left|\pi p_L(x)-q p_R(x)\right|\,d\mu(x)\right).
\]

**Proof.** Conditional on \(X=x\), predicting \(L\) incurs probability mass
\(q p_R(x)\), and predicting \(R\) incurs \(\pi p_L(x)\). Pointwise
minimization gives the first identity. For nonnegative \(a,b\),
\(\min(a,b)=(a+b-|a-b|)/2\). Integrating with
\(\int(\pi p_L+q p_R)d\mu=1\) gives the second. \(\square\)

If \(\pi=q=1/2\), define

\[
d_{\mathrm{TV}}(P_L,P_R)=\frac12\int|p_L-p_R|\,d\mu.
\]

Then the identity specializes to

\[
R^*=\frac12\{1-d_{\mathrm{TV}}(P_L,P_R)\}.
\]

For unequal priors, ordinary \(d_{\mathrm{TV}}(P_L,P_R)\) alone does not
determine risk; the prior-weighted integral in Theorem 1 is required.

## 3. Target-only non-identifiability after label-blind selection

### Theorem 2: selection cannot create target-only scope information

Suppose \(P_L=P_R=M\). Let \(S\in\{0,1\}\) denote acceptance and assume a
label-blind measurable selection kernel

\[
\Pr(S=1\mid X=x,Y=y)=s(x),\qquad 0\le s(x)\le1,
\]

with \(a=\int s\,dM>0\). This includes deterministic target-only selection
and randomized selection whose auxiliary randomness is conditionally
independent of \(Y\) given \(X\). Then

\[
\Pr(Y=L\mid S=1)=\pi
\]

and

\[
\mathcal L(X\mid Y=L,S=1)
=\mathcal L(X\mid Y=R,S=1)
=\frac{s\,dM}{a}.
\]

Consequently every label-blind accepted-set classifier has conditional error
at least \(\min\{\pi,q\}\), and a constant majority-label rule attains that
bound. At balanced priors, every such classifier has error exactly \(1/2\).

**Proof.** The selection condition yields
\(\Pr(Y=L,S=1)=\pi\int s\,dM=\pi a\) and
\(\Pr(S=1)=\pi a+qa=a\), proving the posterior-prior identity. For any
measurable set \(A\),

\[
\Pr(X\in A\mid Y=L,S=1)
=\frac{\int_A s\,dM}{a}
=\Pr(X\in A\mid Y=R,S=1).
\]

Apply Theorem 1 to the accepted conditional laws, which are equal. Auxiliary
randomness covered by the stated conditional-independence condition can be
absorbed into the selection/classifier kernel without changing this argument.
\(\square\)

The positive-coverage and label-blind conditions are essential. If selection
can depend on \(Y\), it can alter the accepted prior even when \(P_L=P_R\).

## 4. Correspondence to the v0.4.1 exact core

Let \(V\) contain a synthetic component, its donor availability realization,
and its pair-derived schedule. In the exact core, \(V\) is generated without
using the scope arm. For a matched pair,

\[
X^L=T(V)=X^R.
\]

Thus, drawing a pair and then a balanced scope label produces
\(P_L=P_R\) for the target-only \(X\), which is the stipulated construction
for Theorem 2. The frozen evaluation contains both matched rows rather than a
new random sample; the theorem explains its constructed sampling model and
does not infer an unrestricted population law.

Comparative observations add donor paths. On retained dates, with
availability-normalized weights

\[
\widetilde w_{jt}=\frac{w_j a_{jt}}{\sum_k w_k a_{kt}},
\qquad \sum_j\widetilde w_{jt}=1,
\]

the regional arm applies the same analysis-scale schedule \(h_t\) to target
and available donors:

\[
r'_t=(z_t+h_t)-\sum_j\widetilde w_{jt}(z_{jt}+h_t)-b=r_t.
\]

The local arm applies the same \(h_t\) to its target only. Therefore the
construction creates a target-only equivalence while retaining a comparative
signal. This is an algebraic property conditional on aligned dates, finite observed
target and donor values (with donors permitted explicit missingness), shared
availability, fixed weights, a zero pre-anchor schedule, a valid inverse
domain, and real arithmetic. The frozen runner derives and records the
pair-derived schedule before passing it to the generic pair builder; the
builder validates a recorded seed when supplied but does not itself claim that
an arbitrary caller-supplied schedule is protocol-generated. The code verifies
numerical residual agreement within \(10^{-12}\). It is not a universal theorem
that comparative data identify scope, nor does the observed zero comparative
error establish a real-world guarantee.

## 5. Stress-family boundary

The raw-scale stress suite supports only its declared clipping-aware
residual-leakage bounds. A raw shared additive or proportional perturbation
does not generally induce the same log-scale increment for target and donor
values. The frozen v0.3.2 variance records also use unequal fixed seeds, so
they do not support a frozen-record distributional-equivalence claim. The
formal scope results above rely instead on the separately frozen v0.4.1
analysis-scale construction.

## 6. Adversarial proof audit

| Candidate overclaim | Why it fails | Retained correction |
| --- | --- | --- |
| Ordinary TV gives the unequal-prior Bayes error. | Pairs with the same ordinary TV can have different risks under \(\pi\ne1/2\). | Use the prior-weighted integral in Theorem 1; use ordinary TV only at balanced priors. |
| Abstention alone improves scope accuracy under equal target laws. | A label-blind positive-coverage selector preserves both the class prior and equal accepted laws. | Theorem 2 gives the same Bayes floor on accepted cases. |
| Any selective procedure obeys Theorem 2. | A selector that uses \(Y\), directly or through label-dependent side information, can change the accepted prior. | Require the stated label-blind kernel and conditional independence. |
| Target equality proves comparative or causal identification. | Donor paths are a different observable vector; causal attribution additionally requires assumptions. | The result is target-only non-identifiability in a constructed synthetic task. |
| The zero forced-scope error proves comparative identification generally. | It was measured only on the pre-registered exact core with fixed construction and calibration. | Report it as an empirical constructed-core metric only. |
| Raw-scale common shocks exactly cancel under a clipped log transform. | The transform makes the increment value-dependent. | Retain only the documented leakage bounds. |

## 7. Sources

1. L. Devroye, L. Györfi, and G. Lugosi, *A Probabilistic Theory of Pattern
   Recognition*, Springer, 1996, Chapter 2.
   https://doi.org/10.1007/978-1-4612-0711-5
2. Y. Polyanskiy and Y. Wu, *MIT 6.441 Information Theory*, Chapter 10,
   Binary Hypothesis Testing, 2016.
   https://ocw.mit.edu/courses/6-441-information-theory-spring-2016/26fd180f40b6773bf19b659a4c5e8656_MIT6_441S16_chapter_10.pdf
3. A. B. Tsybakov, *Introduction to Nonparametric Estimation*, Springer,
   2009, Section 2.2. https://doi.org/10.1007/978-0-387-79052-7
4. C. K. Chow, "On Optimum Recognition Error and Reject Tradeoff," *IEEE
   Transactions on Information Theory*, 16(1), 41--46, 1970.
   https://doi.org/10.1109/TIT.1970.1054406
5. R. El-Yaniv and Y. Wiener, "On the Foundations of Noise-free Selective
   Classification," *JMLR*, 11, 1605--1641, 2010.
   https://jmlr.org/papers/v11/el-yaniv10a.html
6. V. Franc, D. Průša, and V. Voráček, "Optimal Strategies for Reject Option
   Classifiers," *JMLR*, 24, 2023.
   https://jmlr.org/papers/v24/21-0048.html
7. T. J. Rothenberg, "Identification in Parametric Models," *Econometrica*,
   39(3), 577--591, 1971. https://doi.org/10.2307/1913267
8. J. Peters, P. Bühlmann, and N. Meinshausen, "Causal inference by using
   invariant prediction: identification and confidence intervals," *JRSS B*,
   78(5), 947--1012, 2016. https://doi.org/10.1111/rssb.12167

The related change-detection and selective-classification literature establishes
component methods, not a claim that this benchmark formulation is the first
of its kind. See the bounded closest-work assessment in `NOVELTY_AUDIT.md`.
