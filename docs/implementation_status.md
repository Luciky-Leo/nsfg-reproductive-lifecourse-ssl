# Implementation Status

Last updated: 2026-06-02

## Completed

- Downloaded and parsed NSFG 2011-2019 fixed-width female respondent and pregnancy files using official Stata dictionaries.
- Downloaded and parsed NSFG 2022-2023 female respondent and pregnancy CSV files.
- Built a 15-44-year harmonized respondent-level matrix across 2011-2023.
- Constructed five leakage-audited reproductive-health endpoints.
- Trained a CPU-feasible masked tabular SSL encoder on 2011-2017 records.
- Selected phenotypes in 2017-2019 and applied fixed centroids to 2022-2023.
- Generated source-data tables, Figure 1-5, Figure S1, and Table 1-4.
- Drafted a manuscript skeleton, figure legends, and seed reference file.

## Current analytic outputs

- Harmonic matrix: `data/processed/nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz`
- Endpoint labels: `data/processed/nsfg_endpoint_labels.csv.gz`
- SSL embeddings: `data/processed/ssl_embeddings.csv.gz`
- Phenotype assignments: `data/processed/phenotype_assignments.csv.gz`
- Figures: `results/figures/`
- Manuscript tables: `manuscript/tables/`

## Key caveats

- The primary SSL encoder is deliberately CPU-feasible: 48 endpoint-excluded features, one Transformer layer, 48-dimensional embeddings, and five epochs.
- The article should say "masked tabular SSL encoder", not "foundation model".
- Endpoint definitions are public-use survey proxies and should not be framed as clinical diagnoses.
- Figure styling is first-pass manuscript style; it can be polished after the statistical story is accepted.
