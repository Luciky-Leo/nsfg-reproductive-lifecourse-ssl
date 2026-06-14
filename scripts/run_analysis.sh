#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAMBA="/mnt/e/WSL/micromamba/bin/micromamba"
ENV="research-py312"

cd "${ROOT}"

bash scripts/download_nsfg_2022_2023.sh
bash scripts/download_nsfg_2011_2019.sh
"${MAMBA}" run -n "${ENV}" python scripts/build_harmonized_lifecourse_matrix.py
"${MAMBA}" run -n "${ENV}" python scripts/define_endpoints.py
"${MAMBA}" run -n "${ENV}" python scripts/train_ssl_phenotypes.py
"${MAMBA}" run -n "${ENV}" python scripts/cluster_validate_ssl.py
"${MAMBA}" run -n "${ENV}" python scripts/make_tables_and_figures.py
