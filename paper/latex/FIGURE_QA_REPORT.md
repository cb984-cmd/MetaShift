# Figure QA report

## Scope

This report records the visual and machine-checkable QA protocol for the
answerability-first manuscript. It distinguishes:

| Figure family | Count | Binding |
| --- | ---: | --- |
| Legacy v0.3.2 vector figures | 17 | Frozen evidence manifest and source figure verifier |
| v0.5 raster figures | 5 | Execution-receipt hash, figure manifest, and v0.5 asset verifier |
| Total final-PDF placements | 22 | Combined final-page crop validator |

No figure certifies taxonomy labels, real physical mechanisms, authorship, or a
competition submission.

## Required checks

| Check | Evidence |
| --- | --- |
| Legacy source figures exist, are vector, and preserve frozen accounting | `generated/figure_qa_validation.json` |
| v0.5 figures derive only from receipt-hashed frozen outputs | `generated/v05_answerability_asset_validation.json` |
| v0.5 asset generation is deterministic | `generated/v05_answerability_asset_determinism.json` |
| Source geometry records satisfy print-layout constraints | `generated/figure_layout_qa.json` and `generated/v05_figure_layout_qa.json` |
| Every final-PDF figure caption is located and cropped at 150 and 300 DPI | `generated/final_figure_placement_qa.json` |
| Final PDF and vector figures contain no Type 3 or unembedded font | `generated/font_audit.json` |

The source-layout gate requires 6-pt horizontal and 4-pt vertical node
padding, 3-pt separation between independent text boxes, no text/node
overflow, no legend/data collision, and grayscale luminance contrast of at
least 35. It rejects report-facing text below 8.5 pt, node text below 9 pt, or
titles below 10 pt at final print width.

## Status

The prior v0.3.2-only visual sign-off is superseded. The clean final-mode
build from `61186839aefa3b7780134cf7936c5424dd39b1e6` produced the 57-page
canonical PDF (SHA-256
`399334fee9a19954e4b37c6f5d84aa2efa048899a5816ab7fe061415f62797c5`). Its
combined validator located and rendered all 22 placements into all 44 required
150/300-DPI crops; source-layout, crop, and print-resolution checks passed.
The canonical font audit covered 18 PDFs and 127 font entries with no Type 3
or unembedded-font violation. A page-level review of all rendered pages and a
detailed 300-DPI review of the five v0.5 figure placements found no clipping,
collision, missing placement, or unreadable v0.5 label.
