# Open-source figure and diagram tool review

## Decision

The report will use the existing, pinned **Matplotlib 3.11.1** batch pipeline
to create deterministic vector PDFs. It requires no new package or system
renderer, already supports PDF output with embedded TrueType fonts, and is
sufficient for the report's statistical graphics and deliberately simple
workflow diagrams. The report will not add a dependency merely for visual
novelty.

This review was completed before the figure redesign. Tool facts and project
links were checked on 2026-08-31.

| Tool | License and implementation | Vector / LaTeX path | Accessibility and maintenance evidence | Decision |
| --- | --- | --- | --- | --- |
| [Matplotlib](https://github.com/matplotlib/matplotlib) | Permissive Matplotlib license; Python | Native PDF/SVG/PS backends; optional LaTeX text | Ships `tableau-colorblind10`; 3.11.1 includes PDF/font fixes and is compatible with the locked environment. | **Selected.** |
| [SciencePlots](https://github.com/garrettj403/SciencePlots) | MIT; Python style sheets for Matplotlib | Inherits Matplotlib output; styles can require LaTeX | Provides bright/colorblind cycles; active 2.2.2 release. | Not added: a local style contract is simpler and avoids an extra package. |
| [Seaborn](https://github.com/mwaskom/seaborn) | BSD-3-Clause; Python statistical layer | Inherits Matplotlib PDF/SVG behavior | Has a colorblind palette and recommends redundant encodings. | Not added: it offers no needed capability beyond the current Matplotlib stack. |
| [Altair](https://github.com/vega/altair) | BSD-3-Clause; Python/Vega-Lite | Static PDF/SVG requires `vl-convert-python` | Declarative specifications and SVG accessibility options. | Not added: the conversion layer is unnecessary for a static LaTeX report. |
| [Graphviz](https://gitlab.com/graphviz/graphviz) | EPL-2.0; C/C++ with DOT language | Native PDF/SVG through `dot -Tpdf` | Text DOT sources support reproducible directed layouts; current active upstream is GitLab. | Conditional only: no complex auto-layout graph remains after the workflow redraw. |
| [TikZ/PGF](https://github.com/pgf-tikz/pgf) | GPL-2.0 or LPPL-1.3c; TeX | Native TeX/PDF output | Strong typesetting integration and active releases. | Viable but not selected: inline TeX diagrams add build complexity without a clear gain here. |
| [PGFPlots](https://github.com/pgf-tikz/pgfplots) | GPL-3.0-or-later; TeX | Native TeX plots and external PDFs | Includes ColorBrewer/Paul Tol libraries. | Not added: slower TeX plotting and licensing/build complexity are unnecessary. |

## Implementation safeguards

1. All generated figures use Matplotlib's non-GUI `Agg` backend and
   `savefig(..., format="pdf")`.
2. The shared style fixes type sizes, colors, marker shapes, line styles, and
   PDF font type. Plot text is not rendered by an external web service or a
   generative model.
3. Every scientific figure records its input paths in
   `generated/asset_manifest.json`; display-only inputs carry a separate
   SHA-256-pinned configuration.
4. The figure verifier rejects missing, stale, non-vector, unmanifested, or
   unprovenanced graphics. It also checks the accounting and nesting invariants
   that a visual review alone could miss.
5. No downloaded figure, screenshot, copied diagram, gradient, shadow, icon,
   3D effect, or rasterized scientific chart is used.
