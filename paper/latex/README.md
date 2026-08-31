# Formal LaTeX report

This A4 project turns only frozen `v0.3.2-evidence-final` evidence into the
formal research-report draft. It never runs analysis, model tuning, taxonomy
stratification, or raw-data download.

```powershell
python scripts\generate_paper_assets.py --write
python scripts\verify_claim_ledger.py --require-assets
python scripts\verify_paper_source.py
python scripts\verify_references.py
python scripts\build_paper.py
python scripts\verify_formal_report.py
```

`generated/` contains reproducible tables, vector figures, evidence macros,
and manifests. `build/` and `rendered_pages/` are local compilation outputs.
The final PDF is copied to `MetaShift_Bench_Yau_2026.pdf` only after a
successful build.

Do not replace `HUMAN COMPLETION REQUIRED` identity, contribution, advisor,
AI-use, or attestation fields with invented content. The Method Code taxonomy
remains human-blocked; this report includes no taxonomy-stratified analysis.
Use `HUMAN_COMPLETION_CHECKLIST.md` only for independently verified student and
teacher review, disclosures, signatures, and final submission materials.
