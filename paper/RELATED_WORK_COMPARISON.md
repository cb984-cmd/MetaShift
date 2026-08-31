# Related-work contribution comparison

| Design element | Source-supported antecedent | MetaShift-Bench statement |
| --- | --- | --- |
| Reported-method anchor | EPA exposes and defines Method Code. | Uses reported AQS Method Code as a reproducible event anchor. |
| Network reference controls | Pairwise climate homogenization uses reference series. | Adapts multi-site references as diagnostic controls, not causal identification. |
| Stable-window perturbations | PELT and climate homogenization evaluate known synthetic changes. | Injects known perturbations only in stable observed target/donor windows. |
| Placebos | Synthetic control uses in-space falsification. | Uses time and donor-as-treated placebo diagnostics. |
| Public audit trail | AQS bulk files and API support reproducible data access. | Records source snapshot, eligibility, exclusion, and event disposition. |
| Non-causal interpretation | Difference-in-differences requires explicit identification assumptions. | Uses observational evidence tiers rather than causal treatment labels. |

**Safe novelty wording:** “We are not aware of a prior benchmark that jointly
uses reported AQS measurement-method transitions as reproducible metadata
anchors, cross-site diagnostic controls, stable-window synthetic perturbations,
and complete eligible-event accounting.” This is a scoped literature statement,
not a claim of being first.
