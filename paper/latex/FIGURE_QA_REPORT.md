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

The prior v0.3.2-only visual sign-off is superseded. The v0.5 figures have
receipt-bound generation and source-layout records, but combined final-PDF
page rendering, 44 150/300-DPI figure crops, visual inspection, and the
canonical font audit are pending the clean committed-worktree build.
