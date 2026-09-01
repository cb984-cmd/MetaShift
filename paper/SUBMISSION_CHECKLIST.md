# MetaShift-Bench Submission Checklist (丘成桐中学科学奖 2026)

**Deadline: September 15, 2026 24:00 (Beijing time)**

## Technical readiness (automated — complete)

- [x] v0.3.2 release gate 35/35 pass
- [x] v0.3.2 public-document consistency machine-verified (12/12)
- [x] v0.3.2 manuscript numbers machine-verified (57/57)
- [x] v0.3.2 two-environment hash reproducibility confirmed
- [x] 166 unit tests pass
- [x] All v0.3.2 distinct-donor artifacts rebuilt
- [x] Frozen release tag `v0.3.2-evidence-final` points to `57d678ecabebff724d898abe626c9ef80538775b`
- [x] Evidence release published at https://github.com/cb984-cmd/MetaShift/releases/tag/v0.3.2-evidence-final
- [x] GitHub repo public at https://github.com/cb984-cmd/MetaShift
- [x] Source code, configs, and documentation committed
- [x] `.gitignore` excludes raw data, credentials, and generated artifacts
- [x] v0.5 one-time scope-answerability execution frozen at
  `14fd0fee4fb015e6c661299041e35ff704a27286`, receipt SHA-256
  `954fc9b56a8f526644320aa7b1b15ed76844e400e1394ffd8f733729996a87c9`
- [x] Final A4 report built from clean source commit
  `61186839aefa3b7780134cf7936c5424dd39b1e6`: 57 pages, 1,569,094 bytes,
  SHA-256 `399334fee9a19954e4b37c6f5d84aa2efa048899a5816ab7fe061415f62797c5`
- [x] Final report checks pass: 18 formal gates, 22 figure placements, 44
  150/300-DPI crops, zero overfull boxes, and no Type 3 or unembedded fonts

## Required materials (human action needed)

### 1. Online registration
- [ ] Register team at https://www.yau-awards.com/apply
- [ ] Fill in all student and school information
- [ ] Select Computer Science (计算机) category

### 2. Research report (PDF)
- [ ] Complete visible human-only placeholders in the authoritative
  `paper\latex\` source, not the historical `paper/MANUSCRIPT_DRAFT.md`
- [ ] Add student names, school, province/state, country
- [ ] Add supervising teacher names and affiliations
- [ ] Commit the completed source and run a new clean final-mode LaTeX build;
  do not submit the technical template PDF with human-completion placeholders
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
- [ ] Experimental logs: preserve both the v0.3.2 release gate and v0.5
  receipt/manifest for reviewer access, subject to team authorization
- [ ] Figures: 17 legacy vector and 5 receipt-bound v0.5 raster figures in
  the authoritative report
- [ ] Do not publish or attach the local v0.5 evidence archive without a
  verified team decision and applicable competition approval

## Pre-submission verification

- [ ] Students independently read and understand every section
- [ ] Students can answer questions about methods, data, limitations
- [ ] Students can explain the detection/scope/mechanism distinction and the
  limits of the v0.5 synthetic scope result
- [ ] All legacy and v0.5 report numbers match their respective claim-ledger
  and frozen-result validation records
- [ ] No credentials, API keys, or raw data in submitted materials
- [ ] Disclosure of any other competitions or submissions
