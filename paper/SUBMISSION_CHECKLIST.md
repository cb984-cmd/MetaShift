# MetaShift-Bench Submission Checklist (丘成桐中学科学奖 2026)

**Deadline: September 15, 2026 24:00 (Beijing time)**

## Technical readiness (autonomous — complete)

- [x] Release gate 26/26 pass
- [x] Manuscript numbers machine-verified (56/56)
- [x] Two-environment hash reproducibility confirmed
- [x] 59 unit tests pass
- [x] All v2 distinct-donor artifacts rebuilt
- [x] Release tag `v0.3.0-distinct-donors` pushed
- [x] GitHub repo public at https://github.com/cb984-cmd/MetaShift
- [x] Source code, configs, and documentation committed
- [x] `.gitignore` excludes raw data, credentials, and generated artifacts

## Required materials (human action needed)

### 1. Online registration
- [ ] Register team at https://www.yau-awards.com/apply
- [ ] Fill in all student and school information
- [ ] Select Computer Science (计算机) category

### 2. Research report (PDF)
- [ ] Replace all `[Fill in]` placeholders in `paper/MANUSCRIPT_DRAFT.md`
- [ ] Add student names, school, province/state, country
- [ ] Add supervising teacher names and affiliations
- [ ] Convert to PDF with proper formatting
- [ ] Cover page with required fields
- [ ] Verify all tables render correctly in PDF

### 3. Academic integrity declaration (学术诚信声明)
- [ ] Download from https://www.yau-awards.com/index/reldown?id=2
- [ ] All students sign
- [ ] All supervising teachers sign
- [ ] School or academic affairs office stamp
- [ ] If external advisor: their institution's stamp

### 4. Advisor information form (指导老师信息表)
- [ ] Download from https://www.yau-awards.com/index/reldown?id=3
- [ ] Each advisor fills in separately
- [ ] Advisor signature and institutional stamp

### 5. Plagiarism check report (查重报告)
- [ ] Run final PDF through CNKI or PaperPass
- [ ] Ensure duplication rate ≤ 10%
- [ ] Save report as PDF

### 6. AI assistance and contribution records
- [ ] Complete `docs/AI_ASSISTANCE_RECORD_TEMPLATE.md` honestly
- [ ] Complete `docs/AUTHOR_CONTRIBUTION_TEMPLATE.md` with specific entries
- [ ] Complete the Acknowledgements section in the manuscript
- [ ] Each student can independently explain all methods and results

### 7. Supplementary evidence (recommended)
- [ ] Source code: link to https://github.com/cb984-cmd/MetaShift
- [ ] Demo: consider a short video showing pipeline execution
- [ ] Experimental logs: `results/release_gate.json` as evidence
- [ ] Figures: all 16 generated figures in `figures/`

## Pre-submission verification

- [ ] Students independently read and understand every section
- [ ] Students can answer questions about methods, data, limitations
- [ ] All numbers match the latest `results/manuscript_number_verification.json`
- [ ] No credentials, API keys, or raw data in submitted materials
- [ ] Disclosure of any other competitions or submissions
