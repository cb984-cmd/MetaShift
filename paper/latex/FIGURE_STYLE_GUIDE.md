# Figure style guide

## Purpose and scope

This guide governs every generated scientific figure in the formal report. It
applies to the paper-local presentation layer only and does not change frozen
v0.3.2 science. The requirements are checked by
`scripts/verify_figures.py` and by final rendered-page review.

## Typography and geometry

| Element | Standard |
| --- | --- |
| Body / plot family | DejaVu Serif with serif math, visually compatible with the report's Latin Modern text |
| Minimum final tick/legend/annotation size | 8 pt |
| Axis-label and legend size | 8.5 pt or larger |
| Panel title size | 9.5 pt or larger |
| Figure title size | 10.5 pt or larger |
| Output | Vector PDF, `pdf.fonttype = 42`, no Type 3 or unembedded fonts |
| Main-text width | One-column `\linewidth`; no raster enlargement or manual screen capture |
| Dense detail | Put complete matrices/tables in the appendix instead of reducing labels below the minimum size |

## Stable encodings

| Concept | Color | Redundant encoding |
| --- | --- | --- |
| Standard SC | `#4C566A` | Circle marker / solid reference line |
| MetaShift fixed | `#3B82F6` | Triangle marker / solid line |
| MetaShift CV | `#7C3AED` | Diamond marker / dashed line |
| Nearest-neighbor DiD | `#0F766E` | Square marker / dash-dot line |
| Supported candidate | `#2563EB` | Filled blue segment plus explicit label |
| Not supported | `#B45309` | Hatched amber segment plus explicit label |
| Inconclusive | `#64748B` | Gray segment plus explicit label |
| Failure / no overlap | `#B91C1C` | Dashed barrier or crossed label, never color alone |

Black target traces, gray donor composites, dashed reference lines, direct
labels, and marker shapes are used where they improve grayscale reproduction.
Legends never rely on hue as the only distinction.

## Statistical and logical conventions

1. Every axis has a label and unit/scale where applicable. Directional metrics
   identify whether high or low is favorable.
2. Coverage displays use a full 0--100% scale. A localized difference plot may
   use a centered zero line only when the reference and favor direction are
   printed directly on the figure.
3. Intervals use point-plus-line notation with numerical endpoints or a
   self-contained companion table; interval width is not presented as a benefit
   without its coverage context.
4. Nested cohorts are drawn as flows, containment, or explicitly branched
   counts, never as misleading peer bars.
5. Target, donor composite, residual, placebo, and interval panels use days
   relative to the anchor when an event is shown. Shading and anchor lines use
   the same pre/post convention across figures.
6. Schematics carry a visible `schematic` or `illustrative component` label.
   Data-derived figures name a frozen artifact or checksum-pinned display
   contract in their caption and manifest.
7. A Method Code transition is always a metadata anchor. No title, legend,
   caption, or annotation may call it a verified instrument replacement,
   failure, calibration error, physical bias, or corrected concentration.

## Review protocol

The generator produces only source-derived vector figures. Automated QA then
checks the manifest, evidence version, accounting totals, interval nominal
levels, nested-placebo arithmetic, split isolation, source hashes, PDF
structure, and placeholder vocabulary. A human visual pass reviews every
rendered final-PDF page at normal scale and dense tables/figures enlarged.
