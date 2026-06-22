Dear Editors,

We are pleased to submit the manuscript entitled "Self-supervised reproductive life-course phenotyping in the National Survey of Family Growth" for consideration as a Research and Applications article in JAMIA Open.

This study addresses a biomedical informatics problem in reproductive-health survey analysis: how to learn reproducible respondent-level representations from heterogeneous, sparse, skip-patterned survey records without defining the representation around a single endpoint. We harmonized National Survey of Family Growth female respondent and pregnancy files from 2011-2013 through 2022-2023, trained a leakage-controlled masked tabular self-supervised encoder on earlier cycles, selected interpretable phenotypes in a development cycle, and evaluated endpoint enrichment in a temporally held-out cycle.

The informatics contribution is a split-aware workflow for survey representation learning, phenotype discovery, endpoint-leakage auditing, raw-feature baseline comparison, and within-survey temporal stress testing. We explicitly do not frame the model as a clinical diagnostic tool, treatment-decision system, causal analysis, or large foundation model. The endpoint analyses are survey-level enrichment summaries and robustness checks, including ever-pregnant strata, age/parity baselines, adjusted enrichment models, leakage sensitivity, and raw input versus SSL embedding supervised comparisons.

We believe the manuscript fits JAMIA Open because it develops and transparently evaluates a reusable informatics workflow for public-use health survey data, with emphasis on reproducibility, leakage control, interpretable phenotyping, and cautious use of machine-learning outputs. The study may be useful for researchers building representation-learning workflows for survey, registry, and other structured population-health datasets where data are heterogeneous and endpoints can be indirectly encoded by upstream variables.

The manuscript is accompanied by source-data tables, figure assets, model metadata, and analysis scripts. Raw individual-level NSFG public-use records are not redistributed; scripts point to CDC/NCHS public-use data portals. The project repository is available at https://github.com/Luciky-Leo/nsfg-reproductive-lifecourse-ssl and the archived reproducibility package is available at https://doi.org/10.5281/zenodo.20692052.

All authors have approved the submitted version. The authors declare no competing interests, and no external funding was received for this study.

Sincerely,

Jiuqiong Yan and Rui Guan, on behalf of all authors

Department of Obstetrics and Gynecology, Changhai Hospital, Naval Medical University, Shanghai, China

Corresponding author emails: yanjiuqiong@163.com; cngreen785@163.com
