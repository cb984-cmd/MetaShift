# v0.4 Theory Specification: Scope, Equivalence, and Residual Bounds

**Status:** Draft implementation contract for Gate A. It specifies a
constructed synthetic benchmark; it does not identify physical causes of real
monitoring events or modify `v0.3.2-evidence-final`.

## 1. Information and scope

For one synthetic case, let \(Y\in\{N,L,R\}\) denote no change, a
target-local change, and a matched target-plus-donor change. A target-only
procedure receives \(X\), the target path. A comparative procedure also
receives the donor paths \(D_1,\ldots,D_J\), fixed pre-anchor weights, and
availability indicators. The scope task is deliberately separate from change
detection: a target-only procedure may detect a change while lacking
information to determine whether it is local or shared.

No proposition in this document treats a Method Code change, a detected
residual, or a synthetic label as evidence of an instrument replacement,
physical failure, causal bias, or recovered true pollution concentration.

## 2. Exact target-only proposition

### Proposition 1: matched deterministic input identity

For any deterministic frozen v0.3.2 family listed as pathwise-identical in
[`PERTURBATION_EQUIVALENCE_MATRIX.csv`](PERTURBATION_EQUIVALENCE_MATRIX.csv),
the local and regional constructions satisfy

\[
X^L=X^R.
\]

Thus, for any deterministic target-only statistic \(S\),

\[
S(X^L)=S(X^R).
\]

This follows directly from the generator branches: they apply the same
deterministic target transformation and differ only in whether the same
transformation is also applied to donors. It applies to additive,
proportional, gradual, and temporary shapes. It does **not** apply to the
frozen variance pair, whose arm-specific fixed seeds generate different stored
target arrays.

If a matched-pair experiment assigns \(L\) and \(R\) with equal prior
probability and an answer/abstain rule depends only on \(X\), the conditional
class probabilities remain equal after any positive-coverage target-only
selection. Under zero-one scope loss, every accepted target-only decision then
has conditional risk \(1/2\). This elementary statement is a
benchmark-design consequence of equal input distributions; it is not a claim
that all real single-station audits must abstain.

### Distributional extension: contract, not frozen evidence

If a new experiment defines an arm-invariant random schedule \(H\), with the
same conditioning variables, parameter values, preprocessing, and target map
in both arms, then

\[
X^L=g(B,H)=X^R
\]

pathwise when the same realization is shared, and therefore also
\(X^L\overset{d}=X^R\). If independent arm-invariant draws are used instead,
only equality in distribution follows, and an integrable deterministic
statistic has equal expectations. Frozen v0.3.2 variance records do not meet
this contract because they condition on distinct fixed seeds.

The general testing interpretation is standard: identical conditional
class-conditional laws contain no scope information beyond the priors. This
is recorded as an elementary implementation contract rather than a novel
statistical theorem; see Le Cam, *Asymptotic Methods in Statistical Decision
Theory* (1986), Springer, DOI
[`10.1007/978-1-4612-4946-7`](https://doi.org/10.1007/978-1-4612-4946-7),
for the statistical-experiment framework.

## 3. Exact cancellation in the new analysis-scale core

Let

\[
z_t=f(y_t)=\log(1+\max(y_t,0)).
\]

On a retained date, let \(a_{jt}\in\{0,1\}\) indicate donor availability and
let the availability-normalized weights be

\[
\widetilde w_{jt} =
\frac{w_j a_{jt}}{\sum_k w_k a_{kt}},
\qquad \sum_j\widetilde w_{jt}=1.
\]

The implementation retains only dates with a positive denominator and enough
available donors. Its donor composite is

\[
q_t=\sum_j\widetilde w_{jt}z_{jt},
\]

and the primary residual is \(r_t=z_t-q_t-b\), where \(b\) is a
pre-anchor calibration offset.

### Proposition 2: transformed-scale shared-shock invariance

For a schedule \(h_t\) that is zero before the anchor and satisfies the
inverse-domain condition \(z_t+h_t\ge0\) for every observed affected target
and donor value, define the regional arm by

\[
z'_t=z_t+h_t,\qquad z'_{jt}=z_{jt}+h_t.
\]

Then, over the real numbers,

\[
r'_t=(z_t+h_t)-\sum_j\widetilde w_{jt}(z_{jt}+h_t)-b=r_t.
\]

The local arm receives the identical shifted target \(z'_t\) but leaves its
donors unchanged. Therefore the local and regional target arrays are exactly
the same, while the local comparative residual receives the schedule \(h_t\)
relative to the invariant regional residual. The implementation realizes the
transformed paths through
\(y'=\exp(z+h)-1\), validates the domain, requires a zero pre-anchor schedule,
uses one `pair_id`-derived schedule seed without an arm label, and records a
canonical schedule SHA-256. Because this raw inverse/re-transform path uses
IEEE floating-point arithmetic, code-level verification is numerical
invariance within \(10^{-12}\), not bitwise equality. The algebraic
proposition itself remains exact over real arithmetic.

This proposition does not apply to raw-scale v0.3.2 perturbations. It is a
mathematical identifiability diagnostic, not a physical model of every PM2.5
monitoring transition.

## 4. Clipping-aware approximate raw-scale bounds

The implemented transform clips raw values before the logarithm. For a raw
additive change \(h\), define

\[
g_h(y)=f(y+h)-f(y).
\]

For every finite raw \(y\) and any finite signed \(h\), \(g_h\) is globally
one-Lipschitz under the implementation's clipping rule. When \(h\ge0\) and
all compared raw values are nonnegative and lower-bounded by \(m\ge0\), its
differentiable branch has

\[
g'_h(y)=-\frac{h}{(1+y+h)(1+y)},\qquad
L_h=\frac{h}{(1+m+h)(1+m)}.
\]

The sharper expression must not be used when a negative raw input reaches the
clipping boundary; the globally valid constant is then one.

For a nonnegative proportional change \(a\), define

\[
g_a(y)=f((1+a)y)-f(y).
\]

On the nonnegative branch,

\[
g'_a(y)=\frac{a}{(1+(1+a)y)(1+y)}.
\]

Including the clipping branch, \(g_a\) is globally \(a\)-Lipschitz for
\(a\ge0\).

For either increment function \(g\), a shared regional raw perturbation on a
retained date contributes

\[
\delta_t=g(y_t)-\sum_j\widetilde w_{jt}g(y_{jt}),
\]

so

\[
|\delta_t|
\le \sum_j\widetilde w_{jt}|g(y_t)-g(y_{jt})|
\le L\sum_j\widetilde w_{jt}|y_t-y_{jt}|.
\]

The result holds pointwise for time-varying positive drift or temporary
increments. A shared signed raw variance innovation can use the globally
one-Lipschitz clipping-aware constant for its regional-arm residual
contribution; that bound does not make its frozen local/regional target arrays
equivalent.

If the schedule is zero in the pre window, and
\(|\delta_t|\le B\) at every retained post date, the empirical median is
sup-norm stable:

\[
\left|\operatorname{med}(r_t+\delta_t)-\operatorname{med}(r_t)\right|\le B.
\]

This follows because every order statistic, and the even-sample average of
the two central order statistics, lies between the corresponding baseline
order statistic plus or minus \(B\). It transfers the pointwise bound to the
implemented median pre/post effect. It is an applicability bound, not causal
identification.

## 5. Theorem-to-code contract

The exact core is implemented only in
`metashift/identifiability.py`; `metashift/synthetic.py` remains the frozen
raw-scale v0.3.2 generator. The tests enforce:

1. exact target identity in the four valid frozen deterministic pairs;
2. no frozen distributional claim for the unequal-seed variance record;
3. a schedule seed determined only by `pair_id`, not by scope arm;
4. algebraic residual invariance and numerical invariance within \(10^{-12}\)
   for the transformed-scale regional pair with availability-normalized
   missing donors;
5. rejection of pre-anchor or invalid inverse-domain schedules;
6. numerical clipping-aware additive and proportional bounds; and
7. median stability under a bounded residual perturbation.

See `tests/test_v04_theory_scope.py` and
`tests/test_v04_identifiability_core.py`.
