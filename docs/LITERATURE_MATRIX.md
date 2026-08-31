# MetaShift-Bench related-work matrix

**Verification note:** a dash means that the cited source was not verified to
demonstrate that feature; it is not proof that no such work exists. This matrix
supports conservative comparison language, not an absolute “first” claim.

| ID | Work | Problem / data / method | Validation | M | C | S | E | P | O | Distinction from MetaShift-Bench |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| L1 | Clements et al. (2017) | Low-cost air-monitor deployment, calibration, and standardization practice. | Workshop synthesis. | — | — | — | — | — | Article | Measurement-quality context, not AQS Method Code transition audit. |
| L2 | Barkjohn, Gantt, and Clements (2021) | U.S. PurpleAir PM2.5 correction against collocated FRM/FEM monitors. | Approximately 12,000 24-hour collocated observations. | — | — | — | — | — | Partial | Calibrates low-cost sensors; does not audit reported AQS method transitions. |
| L3 | Chu, Ali, and He (2020) | AirBox low-cost sensors, regulatory references, spatial calibration and mapping. | Reference-station RMSE/R2 evaluation. | — | Reference | — | — | — | Partial | Uses spatial references, not metadata-anchor counterfactual events. |
| L4 | Killick, Fearnhead, and Eckley (2012) | PELT multiple change-point detection. | Known-change simulations and public package. | — | — | Yes | — | — | Yes | Detection baseline only; no monitoring metadata or event ledger. |
| L5 | Reeves et al. (2007) | Climate change-point methods review. | Methodological review. | History context | — | Not verified | — | — | Not verified | Environmental discontinuity background, not PM2.5 audit. |
| L6 | Gagliardi and Andenna (2022) | Meteorologically normalized pollutant trends plus change-point testing. | Observational applied analysis. | — | — | — | — | — | Not verified | Studies environmental concentration changes, not reported method transitions. |
| L7 | Menne and Williams (2009) | Pairwise homogenization of U.S. temperature stations. | Known synthetic inhomogeneities and false-alarm comparison. | Station history | Pairwise reference | Yes | — | — | Public data | Strong analogue for reference series and metadata, but adjusts climate records rather than auditing AQS PM2.5. |
| L8 | Abadie, Diamond, and Hainmueller (2010) | Synthetic control comparative case study. | In-space placebo/falsification. | — | Yes | — | — | Yes | Not verified here | Provides counterfactual and placebo precedent; method metadata is not its event definition. |
| L9 | Callaway and Sant'Anna (2021) | Group-time difference-in-differences with staggered adoption. | Method simulations and `did` package. | — | Yes | Yes | — | Pretrend diagnostics | Yes | Formal causal assumptions are stronger than a reported Method Code transition supports. |
| L10 | U.S. EPA Method Code definition | Defines reported collection/analysis method for a time period. | Official documentation. | Available | — | — | — | — | Yes | Establishes reproducible metadata anchor; does not prove hardware or bias. |
| L11 | U.S. EPA AQS API v2 | Sample data, monitor metadata, and QA services. | Public API. | Available | — | — | — | — | Yes | Enables extraction but supplies no transition benchmark or counterfactual protocol. |
| L12 | U.S. EPA AirData file formats | Bulk AQS site, monitor, daily, and hourly files. | Official documentation. | Available | — | — | — | — | Yes | Public-data substrate; project defines the event universe and audit protocol. |
| L13 | AirNow About the Data | Near-real-time air-quality data and validation context. | Official documentation. | — | — | — | — | — | Yes | Shows why certified historical AQS data is preferable for this audit. |
| L14 | OpenAQ API documentation | Aggregated global observations with provider/source metadata. | Public API. | Metadata available | — | — | — | — | Yes | Provenance context, but not EPA AQS Method Code transition truth. |

**Feature key:** M = reported measurement-method metadata used analytically; C =
cross-site counterfactual/reference comparison; S = known-truth synthetic
perturbation; E = complete audit ledger for eligible reported transitions; P =
explicit placebo/falsification; O = public code/data/documentation.

## Citation-ready references

1. A. L. Clements et al., “Low-Cost Air Quality Monitoring Tools: From Research
   to Practice (A Workshop Summary),” *Sensors*, vol. 17, no. 11, Art. 2478,
   2017, doi: [10.3390/s17112478](https://doi.org/10.3390/s17112478).
2. K. K. Barkjohn, B. Gantt, and A. L. Clements, “Development and Application
   of a United States Wide Correction for PM2.5 Data Collected with the
   PurpleAir Sensor,” *Atmospheric Measurement Techniques*, vol. 14, pp.
   4617--4630, 2021, doi:
   [10.5194/amt-14-4617-2021](https://doi.org/10.5194/amt-14-4617-2021).
3. H.-J. Chu, M. Z. Ali, and Y.-C. He, “Spatial Calibration and PM2.5 Mapping
   of Low-Cost Air Quality Sensors,” *Scientific Reports*, vol. 10, Art.
   22079, 2020, doi:
   [10.1038/s41598-020-79064-w](https://doi.org/10.1038/s41598-020-79064-w).
4. R. Killick, P. Fearnhead, and I. A. Eckley, “Optimal Detection of
   Changepoints With a Linear Computational Cost,” *Journal of the American
   Statistical    Association*, vol. 107, no. 500, pp. 1590--1598, 2012, doi:
   [10.1080/01621459.2012.737745](https://doi.org/10.1080/01621459.2012.737745).
5. J. Reeves, J. Chen, X. L. Wang, R. Lund, and Q. Lu, “A Review and Comparison
   of Changepoint Detection Techniques for Climate Data,” *Journal of Applied
   Meteorology and Climatology*, vol. 46, no. 6, pp. 900--915, 2007, doi:
   [10.1175/JAM2493.1](https://doi.org/10.1175/JAM2493.1).
6. R. V. Gagliardi and C. Andenna, “Change Points Detection and Trend Analysis
   to Characterize Changes in Meteorologically Normalized Air Pollutant
   Concentrations,” *Atmosphere*, vol. 13, no. 1, Art. 64, 2022, doi:
   [10.3390/atmos13010064](https://doi.org/10.3390/atmos13010064).
7. M. J. Menne and C. N. Williams, Jr., “Homogenization of Temperature Series
   via Pairwise Comparisons,” *Journal of Climate*, vol. 22, no. 7, pp.
   1700--1717, 2009, doi:
   [10.1175/2008JCLI2263.1](https://doi.org/10.1175/2008JCLI2263.1).
8. A. Abadie, A. Diamond, and J. Hainmueller, “Synthetic Control Methods for
   Comparative Case Studies,” *Journal of the American Statistical
   Association*, vol. 105, no. 490, pp. 493--505, 2010, doi:
   [10.1198/jasa.2009.ap08746](https://doi.org/10.1198/jasa.2009.ap08746).
9. B. Callaway and P. H. C. Sant'Anna, “Difference-in-Differences With Multiple
   Time Periods,” *Journal of Econometrics*, vol. 225, no. 2, pp. 200--230,
   2021, doi:
   [10.1016/j.jeconom.2020.12.001](https://doi.org/10.1016/j.jeconom.2020.12.001).
10. U.S. EPA, “[Method Code](https://aqs.epa.gov/aqsweb/helpfiles/method_code.htm),”
    AQS Help File.
11. U.S. EPA, “[AQS API Version 2](https://aqs.epa.gov/aqsweb/documents/data_api.html).”
12. U.S. EPA, “[AirData Download Files](https://aqs.epa.gov/aqsweb/airdata/download_files.html)”
    and “[AirData File Formats](https://aqs.epa.gov/aqsweb/airdata/FileFormats.html).”
13. AirNow, “[About the Data](https://www.airnow.gov/about-the-data/).”
14. OpenAQ, “[API Documentation](https://docs.openaq.org/).”

## Conservative contribution language

> MetaShift-Bench integrates established ideas from monitoring-quality
> assurance, change-point detection, reference-series homogenization,
> synthetic-control falsification, and reproducible public-data auditing into a
> protocol for reported EPA AQS PM2.5 Method Code transitions. It evaluates
> whether observed patterns are consistent with measurement-system
> discontinuities; it does not treat reported code changes as causal
> interventions or definitive evidence of physical instrument change.
