# Final Submission Handoff

Updated: 2026-06-09

Current status: rebuilt post-review LaTeX package. The manuscript has been revised after strict reviewer audit to emphasize public-use NSFG survey phenotyping, within-NSFG temporal validation, endpoint-enrichment interpretation, and cautious pregnancy-history analyses.

Target journal: **Reproductive Health**. Submission materials should keep the reproductive-health and public-use survey phenotype story first, with masked tabular SSL described as the enabling method.

## Implemented Reviewer Fixes

- Pregnancy-history endpoint enrichment is now primarily presented in the ever-pregnant stratum.
- Full-cohort pregnancy-history estimates are retained only as supporting exposure-structured summaries.
- Table 4 includes an `Analysis set` column and uses row-level bootstrap CIs.
- The 0.914 versus 0.953 bootstrap ARI difference is explicitly explained as primary PCA-projected phenotype selection versus direct SSL-embedding baseline clustering.
- Code availability now states that a public GitHub repository and Zenodo archive will be deposited and cited before publication.
- Figure 1 is included as the current PDF workflow asset rather than the older PNG-only build reference.
- SSL wording is constrained to a compact masked-reconstruction public-survey encoder, not a large foundation model or full implementation of all cited tabular SSL variants.

## Current Build Commands

Run from PowerShell:

```powershell
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_20260601 && /mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python scripts/build_latex_submission_package.py"
powershell -ExecutionPolicy Bypass -File E:\Reserch\_env\scripts\compile_latex.ps1 -ProjectPath E:\Reserch\NSFG_Reproductive_LifeCourse_SSL_20260601\manuscript\latex -MainTex main.tex
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_20260601 && /mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python scripts/audit_manuscript_data_consistency.py"
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_20260601 && /mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python scripts/qa_submission_package.py"
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_20260601 && /mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python scripts/export_overleaf_package.py --allow-warnings"
```

## Key Files

- Manuscript root: `manuscript/latex`
- Main manuscript: `manuscript/latex/main.tex`
- Compiled PDF: `manuscript/latex/main.pdf`
- Submission field text: `manuscript/latex/submission_field_texts.md`
- Source data: `manuscript/latex/source_data`
- Figures: `manuscript/latex/figures`
- Tables: `manuscript/latex/tables`
- QA report: `analysis_review/submission_package_qa_20260604.md`
- Consistency audit: `analysis_review/manuscript_data_consistency_audit_20260604.md`
- Reviewer-response note: `analysis_review/claude_review_response_20260609.md`

## Human Submission Items

- Confirm author order, corresponding-author details, and contribution statement in `config/submission_metadata.json`.
- If panel approval needs to be re-recorded, use `scripts/record_persist_panel_selection.py` and then rebuild the package.
- Create or update the public GitHub repository and Zenodo archive before publication, then replace the generic Code availability sentence with the final URL/DOI when available.
- Confirm Reproductive Health's required upload format for supplementary figures and tables.
- Paste the Data availability, Code availability, Ethics, Competing interests, Funding, and Author contribution fields from `manuscript/latex/submission_field_texts.md` into the submission system if separate fields are required.

## Final Export Criterion

The final Overleaf archive should be created only after QA reports `0 fail` and `0 warn`. Warning-bearing exports should remain explicitly labelled as draft archives.

## Claim Boundary

The final manuscript should remain framed as public-use survey representation learning, phenotype discovery, and endpoint enrichment. It should not claim clinical diagnosis, individual treatment guidance, causality, independent external validation, EHR/registry validation, or a large foundation model.
