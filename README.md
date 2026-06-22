# NSFG Reproductive Life-Course SSL

Reproducibility materials for the manuscript:

**Self-supervised reproductive life-course phenotyping in the National Survey of Family Growth**

This repository contains analysis scripts, manuscript source files, final figures, source-data tables, model/configuration metadata, and reproducibility notes for the NSFG reproductive life-course self-supervised phenotyping study prepared for JAMIA Open resubmission.

## Data availability

The raw NSFG public-use files are available from CDC/NCHS public-use data portals. Raw individual-level public-use records are not redistributed in this repository. Scripts and documentation point to the official data portals and describe the processing workflow. Derived source-data tables used for manuscript figures and tables are included for transparency.

## Reproducibility contents

- `scripts/`: data parsing, harmonization, endpoint definition, SSL phenotyping, robustness analyses, figure/table generation, and submission QA scripts.
- `manuscript/latex/`: LaTeX source, main manuscript PDF, supplementary information PDF, tables, figures, and source-data tables.
- `results/tables/`: analysis output tables used to populate figures, tables, and supplementary materials.
- `results/figures/`: exported figure assets.
- `environment.yml`: conda/micromamba environment specification used for the analysis.
- `LICENSE`: MIT license.
- `CITATION.cff`: citation metadata.

## Runtime

The project was run under WSL Ubuntu with micromamba environment `research-py312`.

Example environment command used on the analysis workstation:

```powershell
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_JAMIA_Open_resubmission_20260620 && /mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python scripts/qa_submission_package.py"
```

## Raw data policy

Do not add `data/raw/`, `data/processed/`, `data/interim/`, or other individual-level NSFG files to this repository. These folders are intentionally excluded from public release.
