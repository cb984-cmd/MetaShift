# v0.5 Scope Answerability Literature Audit

**Status:** focused primary-source audit completed before v0.5 outcomes. This
is not a systematic review and absence from it is not evidence of priority.

## Scope and search boundary

The audit asks whether prior work already combines a target-fixed
local/partial/shared construction, channel-specific selective scope
answerability, a comparative answerability gain, and a donor-participation
structural abstention condition. It separately audits established ingredients
that the project must not claim as new.

Publisher pages that block automated access are recorded as metadata-only
verification rather than supplemented with unverified detail.

The compact field-by-field comparison is retained in
[`V05_CLOSEST_WORK_MATRIX.csv`](V05_CLOSEST_WORK_MATRIX.csv).

| Area | Primary or official source | Verified contribution | Required v0.5 boundary |
| --- | --- | --- | --- |
| Comparison of experiments | D. Blackwell, "Comparison of Experiments" (1951), *Second Berkeley Symposium*, 93--102. [DOI](https://doi.org/10.1525/9780520411586-009); D. Blackwell, "Equivalent Comparisons of Experiments" (1953), *Annals of Mathematical Statistics* 24(2):265--272. [DOI](https://doi.org/10.1214/aoms/1177729032) | The 1951 DOI record verifies title, author, venue, and pages; the 1953 primary landing page was access-blocked during this audit. These works establish decision-theoretic comparison and garbling concepts. | Channel monotonicity is an application of established theory, not a new information-ordering result. |
| Selective risk--coverage | R. El-Yaniv and Y. Wiener, "On the Foundations of Noise-free Selective Classification" (2010), *JMLR* 11:1605--1641. [Official page](https://www.jmlr.org/papers/v11/el-yaniv10a.html) | Official JMLR abstract explicitly names the risk--coverage trade-off and studies its optimal or near-optimal achievement. | Do not present maximizing coverage under an error constraint as new. |
| Bounded-improvement rejection | V. Franc, D. Průša, and V. Voráček, "Optimal Strategies for Reject Option Classifiers" (2023), *JMLR* 24:1--49. [Official page](https://jmlr.org/papers/v24/21-0048.html) | Official JMLR abstract states that bounded improvement seeks guaranteed selective risk and maximal coverage. | \(\Gamma\) is closest to this established objective; v0.5 only specializes it to a scope benchmark and contrasting channels. |
| Confidence-selected prediction | Y. Geifman and R. El-Yaniv, "Selective Classification for Deep Neural Networks" (2017), *NeurIPS*. [Proceedings PDF](https://papers.nips.cc/paper_files/paper/2017/file/4a8423d5e91fda00bb7e46540e2b0cf-Paper.pdf) | Proceedings metadata identifies selective classification, desired risk, rejection, and held-out image benchmarks. | A confidence cutoff is not v0.5's innovation and cannot be called calibrated without the paper's assumptions. |
| Classical and learned rejection | C. K. Chow, "On Optimum Recognition Error and Reject Tradeoff" (1970), *IEEE TIT* 16(1):41--46. [DOI](https://doi.org/10.1109/TIT.1970.1054406); P. Bartlett and M. Wegkamp, "Classification with a Reject Option using a Hinge Loss" (2008), *JMLR* 9:1823--1840. [Official page](https://www.jmlr.org/papers/v9/bartlett08a.html) | The Bartlett--Wegkamp official abstract verifies a reject-cost classification framework and risk consistency. The Chow publisher page was access-limited. | Abstention itself and reject-option learning are established. |
| Hierarchical selective classification | S. Goren, I. Galil, and R. El-Yaniv, "Hierarchical Selective Classification" (2024), *NeurIPS*. [arXiv:2405.11533](https://arxiv.org/abs/2405.11533) | The arXiv record describes hierarchical risk and coverage, hierarchical risk--coverage curves, and less-specific predictions under uncertainty. | v0.5 has no label hierarchy and does not claim a hierarchical abstention contribution. |
| Conditional inference limits | R. Barber, E. Candès, A. Ramdas, and R. Tibshirani, "The limits of distribution-free conditional predictive inference" (2021), *Information and Inference* 10(2):455--482. [DOI](https://doi.org/10.1093/imaiai/iaaa017); A. Angelopoulos et al., "Conformal Risk Control" (2024), *ICLR*. [OpenReview](https://openreview.net/forum?id=33XGfHLtZg) | Both publisher pages were access-limited in this audit; citations and bounded applicability were cross-checked against their canonical records. | A frozen calibration procedure does not imply a distribution-free conditional scope-risk guarantee. |
| Common and idiosyncratic changes | M. Barigozzi, H. Cho, and P. Fryzlewicz, "Simultaneous multiple change-point and factor analysis for high-dimensional time series" (2018), *Journal of Econometrics* 206(1):187--225. [DOI](https://doi.org/10.1016/j.jeconom.2018.05.003); J. Bai, R. Lumsdaine, and J. Stock, "Testing for and Dating Common Breaks in Multivariate Time Series" (1998), *Review of Economic Studies* 65(3):395--432. [DOI](https://doi.org/10.1111/1467-937X.00049) | BCF's accessible author record verifies its common/idiosyncratic factor change-point focus. Some publisher pages were access-limited. | Common-versus-idiosyncratic change detection and multivariate break gains are not novel here. |
| Weak supervision | M. Cauchois, S. Gupta, A. Ali, and J. Duchi, "Predictive Inference with Weak Supervision" (2024), *JMLR* 25:1--45. [Official page](https://jmlr.org/papers/v25/23-0253.html); A. Ratner et al., "Data Programming" (2016), *NeurIPS*. [Proceedings record](https://papers.nips.cc/paper/6523-data-programming-creating-large-training-sets-quickly) | The JMLR abstract verifies specialized predictive-validity targets under partial/weak labels. | Injected synthetic scope labels are generator-defined gold truth, not weak labels. Method Code metadata remains a weak anchor, not a mechanism label. |
| Synthetic control | A. Abadie, "Using Synthetic Controls" (2021), *Journal of Economic Literature* 59(2):391--425. [Official AEA page](https://www.aeaweb.org/articles?id=10.1257/jel.20191450) | Official abstract and citation verify synthetic-control feasibility, data requirements, applicability, and failure conditions. | Donor weighting, pre-fit feasibility, and placebo logic are established and cannot substantiate mechanism claims. |
| Pairwise monitoring homogenization | M. Menne and C. Williams, "Homogenization of Temperature Series via Pairwise Comparisons" (2009), *Journal of Climate* 22(7):1700--1717. [DOI](https://doi.org/10.1175/2008JCLI2263.1); C. Williams, M. Menne, and P. Thorne, "Benchmarking the Performance of Pairwise Homogenization" (2012), *JGR Atmospheres* 117:D05116. [DOI](https://doi.org/10.1029/2011JD016761) | The Menne--Williams Crossref record includes the primary abstract describing pairwise station differences, documented shifts, station history, and simulation. | Network reference comparisons and realistic injected-truth benchmarking are established. |
| Residual signatures and diagnosis | E. Chow and A. Willsky, "Analytical Redundancy and the Design of Robust Failure Detection Systems" (1984), *IEEE TAC* 29(7):603--614. [DOI](https://doi.org/10.1109/TAC.1984.1103593); M. Krysander and E. Frisk, "Sensor Placement for Fault Diagnosis" (2008), *IEEE TSMC-A* 38(6):1398--1410. [DOI](https://doi.org/10.1109/TSMCA.2008.2003968) | Crossref verifies the Krysander--Frisk title, venue, authors, pages, and DOI; IEEE pages were access-limited. These works require structural or physical fault models. | Do not claim residual signatures, fault distinguishability, sensor observability, or physical sensor isolation. |
| Sensor-versus-system distinction | M. Taiebat and F. Sassani, "Distinguishing Sensor Faults from System Faults by Utilizing Minimum Sensor Redundancy" (2017), *Transactions of the Canadian Society for Mechanical Engineering* 41(3):469--487. [DOI](https://doi.org/10.1139/tcsme-2017-0033) | The canonical publisher page was access-limited; prior repository audit verified bibliographic metadata and its physical-relation premise. | v0.5 lacks the known physical relations required for sensor/system fault conclusions. |

## Bounded novelty statement

> MetaShift-Bench instantiates an information-constrained selective scope
> auditing benchmark under explicitly separated target-only and comparative
> channels. Its prospective empirical contribution is a target-fixed,
> donor-participation continuum that measures a predeclared
> channel-specific answerability envelope. Under stated synthetic
> analysis-scale and bounded-error assumptions, it additionally studies a
> structural sufficient condition for abstention.

This focused audit did not identify a source that states the complete joint
construction. That is not proof that none exists. The project must not claim
to be first, generic risk--coverage theory, a new common/idiosyncratic
change-point method, new fault isolation, or real monitoring-network
mechanism identification.
