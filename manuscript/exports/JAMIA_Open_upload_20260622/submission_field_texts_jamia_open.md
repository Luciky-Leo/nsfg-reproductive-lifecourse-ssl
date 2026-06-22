# JAMIA Open Submission Field Texts

These entries are matched to the JAMIA Open resubmission version of the manuscript.

## Title

Self-supervised reproductive life-course phenotyping in the National Survey of Family Growth

## Abstract

Objective: To develop and evaluate a split-aware self-supervised representation-learning workflow for summarizing heterogeneous reproductive life-course survey records into interpretable respondent phenotypes.

Materials and Methods: We harmonized National Survey of Family Growth (NSFG) female respondent and female pregnancy files from 2011-2013, 2013-2015, 2015-2017, 2017-2019, and 2022-2023. The primary analysis included females aged 15-44 years. Pregnancy files were aggregated to respondent-level histories and linked by CaseID. A leakage-controlled masked tabular self-supervised learning (SSL) encoder was trained on 2011-2017 records, phenotype selection was performed in 2017-2019, and 2022-2023 was reserved for within-NSFG temporal validation rather than validation in a separate health-system dataset. Endpoint-enrichment intervals used a stratified cluster bootstrap based on public-use VEST/VECL design variables.

Results: The harmonized matrix included 26,478 respondents and 598 cross-cycle columns before feature selection. The primary encoder used 48 endpoint-excluded features and generated 48-dimensional respondent embeddings. Development-cycle clustering selected three phenotypes. In 2022-2023, P0 represented younger low-pregnancy-exposure respondents, P1 represented the main pregnancy-exposed phenotype, and P2 was a small high-burden pregnancy-history phenotype. Within respondents with at least one pregnancy record, P2 showed the highest enrichment for adverse pregnancy-history proxy and mistimed or unwanted pregnancy history. SSL embeddings had higher AUPRC than raw 48 encoder inputs in 5/5 full-cohort endpoints and 2/2 ever-pregnant pregnancy-history endpoints.

Discussion: The workflow provides an informatics framework for representation learning, phenotype discovery, leakage auditing, and temporal stress testing in complex reproductive-health survey data. Pregnancy-history enrichment required interpretation against age/parity and ever-pregnant baselines.

Conclusion: Masked tabular SSL can summarize NSFG respondent and pregnancy records into interpretable reproductive life-course profiles and reproducible endpoint-enrichment summaries. The study supports survey representation learning and phenotype discovery, not clinical diagnosis, individual treatment guidance, or causal inference.

## Lay Summary

Large reproductive-health surveys contain information about contraception, pregnancy histories, fertility care, relationships, insurance, and socioeconomic conditions, but these domains are often analyzed one at a time. We developed a self-supervised learning workflow that summarizes many survey variables into respondent-level representations and then groups respondents into interpretable reproductive life-course profiles. The workflow was trained on earlier National Survey of Family Growth cycles and evaluated in the 2022-2023 cycle. The learned profiles highlighted groups with different reproductive histories and different concentrations of survey-defined endpoints such as contraceptive vulnerability, fertility-service or pregnancy-loss help, mistimed or unwanted pregnancy history, and adverse pregnancy-history proxies. The study is intended as a reproducible informatics approach for population-level survey phenotyping and hypothesis generation. It should not be used as a clinical diagnosis, individual risk calculator, treatment recommendation tool, or causal analysis.

## Data Availability

The raw data analyzed in this study are publicly available from CDC/NCHS NSFG public-use data portals, including the 2022-2023 public-use files and 2011-2019 public-use releases. Raw individual-level public-use records are not redistributed. Processed source-data tables used for figures and manuscript tables are included in the source_data directory and archived with the reproducibility package at Zenodo: https://doi.org/10.5281/zenodo.20793239. Public-use data access URLs and parsing notes are documented in the project README and processing scripts.

## Code Availability

Analysis scripts, split definitions, source-data tables, model metadata, and figure assets are available at GitHub (https://github.com/Luciky-Leo/nsfg-reproductive-lifecourse-ssl) and Zenodo (https://doi.org/10.5281/zenodo.20793239). Raw NSFG individual-level public-use records are not redistributed; the scripts point to CDC/NCHS public-use data portals and document the processing workflow. Project code is released under the MIT License, and citation metadata are provided in CITATION.cff.

## Ethics Approval And Consent To Participate

This study used de-identified public-use NSFG data released by CDC/NCHS. No new human-subject data were collected, and the analysis involved no direct participant contact or identifiable private information; therefore, separate informed consent and institutional review board approval were not required for this secondary public-use analysis.

## Competing Interests

The authors declare no competing interests.

## Funding

No external funding was received for this study.

## Author Order And Contributions

Feifan Lu, Fengshang Yan, and Qianqian Yang contributed equally to this work. Feifan Lu contributed to study conceptualization, public-data curation, formal analysis, figure and table generation, and manuscript drafting. Fengshang Yan and Qianqian Yang contributed to data verification, result interpretation, manuscript review, and revision. Jiuqiong Yan contributed to clinical interpretation, supervision, manuscript review, and revision. Rui Guan supervised the study, provided senior oversight, reviewed and edited the manuscript, and approved the final version. All authors read and approved the final manuscript.

## AI-Assisted Technology Disclosure

The authors used AI-assisted tools for language editing, formatting support, code-drafting support, and internal consistency checks during manuscript preparation. All analyses, interpretations, final text, figures, and submitted materials were reviewed and approved by the authors, who take full responsibility for the content.

## Manuscript Scope Statement

This manuscript is a biomedical informatics study of survey representation learning and phenotype enrichment. It is not designed as a clinical diagnostic model, bedside prediction tool, causal analysis, hospital EHR study, registry validation study, or large foundation model. The 2022-2023 analysis is a within-NSFG temporal validation of survey endpoint enrichment.
