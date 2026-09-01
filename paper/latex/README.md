# Formal LaTeX report

This A4 project turns only frozen `v0.3.2-evidence-final` evidence into the
formal research-report draft. It never runs analysis, model tuning, taxonomy
stratification, or raw-data download.

```powershell
python scripts\generate_paper_assets.py --write
python scripts\verify_claim_ledger.py --require-assets
python scripts\verify_paper_source.py
python scripts\verify_references.py
python scripts\verify_paper_asset_determinism.py
python scripts\build_paper.py
python scripts\verify_formal_report.py
```

`generated/` contains reproducible tables, 17 vector figures, evidence macros,
and manifests. `generated/figure_layout_qa.json` records measured node padding,
text separation, canvas boundaries, final print width, typography, and
grayscale checks. `build/`, `rendered_pages/`, and the 150/300-DPI
`qa_page_crops/` are local compilation outputs. The final PDF is copied to
`MetaShift_Bench_Yau_2026.pdf` only after a successful build.

The current strict final build is from clean report-source commit
`2aad488726a04e1a1adda1e768b909b350686aad`: 44 pages, 1,048,269 bytes, and
SHA-256 `08841e8ed3ed9e4a3a69ceddf62a42a385c0077e0a6cdf9d761c20a6ceb22d40`.
It has zero overfull boxes, 11/11 source figure checks for 17 figures, 38
deterministic assets, all 44 pages rendered at 150 and 300 DPI, 34 focused
figure crops, an 18-PDF/125-font audit with no Type 3 or unembedded fonts, and
15/15 formal-report checks. See `generated/build_report.json` and
`generated/formal_report_compliance.json`.

Do not replace `HUMAN COMPLETION REQUIRED` identity, contribution, advisor,
AI-use, or attestation fields with invented content. The Method Code taxonomy
remains human-blocked; this report includes no taxonomy-stratified analysis.
Use `HUMAN_COMPLETION_CHECKLIST.md` only for independently verified student and
teacher review, disclosures, signatures, and final submission materials.
