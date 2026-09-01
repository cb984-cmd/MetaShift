# Formal LaTeX report

This A4 report presents MetaShift-Bench as a target-fixed benchmark for
selective scope answerability. It preserves three evidence roles:

| Evidence release | Permitted role |
| --- | --- |
| `v0.3.2-evidence-final` | Real-data deployment and abstention evidence |
| v0.4 | Historical endpoint and raw-leakage sanity checks |
| `v0.5-answerability-frontier` | Frozen synthetic scope-answerability boundary evidence |

The v0.5 raw outputs are immutable. Presentation scripts only read
receipt-hashed outputs; they never execute, tune, replace, or reinterpret the
frozen experiment. Use the receipt-pinned interpreter, not an unpinned
`python`, for all v0.5 provenance-dependent commands:

```powershell
$py = 'C:\Users\marco\.copilot\session-state\863d8d39-4e41-4fe4-9ac9-3b3055a632d1\files\metashift-repro-venv\Scripts\python.exe'
& $py scripts\generate_paper_assets.py --write
& $py scripts\verify_claim_ledger.py --require-assets
& $py scripts\generate_v05_answerability_assets.py --write
& $py scripts\verify_v05_answerability_assets.py
& $py scripts\verify_v05_answerability_asset_determinism.py
& $py scripts\verify_v05_claim_ledger.py --require-assets
& $py scripts\verify_paper_source.py
& $py scripts\verify_references.py
& $py scripts\verify_paper_asset_determinism.py
```

The canonical `MetaShift_Bench_Yau_2026.pdf` is published only by a clean
final-mode build. Its source commit, page count, byte size, SHA-256 hash, and
compliance results are recorded in `generated/build_report.json` and
`generated/clean_build_record.json`. Future report-source edits require another
clean final-mode build; do not cite a superseded PDF record.

`generated/` holds 38 legacy presentation assets and 11 receipt-bound v0.5
assets, including 17 legacy vector figures and five v0.5 raster figures.
`generated/figure_layout_qa.json` and
`generated/v05_figure_layout_qa.json` record source-layout checks; `build/`,
`rendered_pages/`, and `qa_page_crops/` are local build outputs.

Do not replace `HUMAN COMPLETION REQUIRED` identity, contribution, adviser,
AI-use, or attestation fields with invented content. The Method Code taxonomy
remains human-blocked and only affects mechanism-level claims; it does not
validate or invalidate the v0.5 synthetic scope result.
