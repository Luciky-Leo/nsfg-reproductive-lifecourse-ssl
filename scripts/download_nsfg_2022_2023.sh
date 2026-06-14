#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/data/raw/nsfg_2022_2023"
mkdir -p "${OUT}"

cd "${OUT}"

curl -L -o NSFG-2022-2023-FemRespPUFData.zip \
  https://ftp.cdc.gov/pub/Health_Statistics/NCHS/NSFG/NSFG-2022-2023-FemRespPUFData.zip
curl -L -o NSFG-2022-2023-FemPregPUFData.zip \
  https://ftp.cdc.gov/pub/Health_Statistics/NCHS/NSFG/NSFG-2022-2023-FemPregPUFData.zip

curl -L -o 2022-2023-NSFG-FileIndex-FemRespPUF.pdf \
  https://www.cdc.gov/nchs/data/nsfg/fileindex/2022-2023-NSFG-FileIndex-FemRespPUF.pdf
curl -L -o 2022-2023-NSFG-FileIndex-FemPregPUF.pdf \
  https://www.cdc.gov/nchs/data/nsfg/fileindex/2022-2023-NSFG-FileIndex-FemPregPUF.pdf
curl -L -o 2022-2023-NSFG-FemRespPUFCodebook.pdf \
  https://www.cdc.gov/nchs/data/nsfg/codebooks/2022-2023-NSFG-FemRespPUFCodebook.pdf
curl -L -o 2022-2023-NSFG-FemPregPUFCodebook.pdf \
  https://www.cdc.gov/nchs/data/nsfg/codebooks/2022-2023-NSFG-FemPregPUFCodebook.pdf
curl -L -o NSFG-2022-2023-UsersGuide-revJuly2025.pdf \
  https://www.cdc.gov/nchs/data/nsfg/guidefaqs/NSFG-2022-2023-UsersGuide-revJuly2025.pdf

unzip -o -q NSFG-2022-2023-FemRespPUFData.zip
unzip -o -q NSFG-2022-2023-FemPregPUFData.zip

sha256sum * > SHA256SUMS.txt
find . -maxdepth 1 -type f -printf '%f\t%s bytes\n' | sort
