#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/data/raw/nsfg_2011_2019"
mkdir -p "${OUT}/stata"

BASE="https://ftp.cdc.gov/pub/health_statistics/nchs/datasets/NSFG"
STATA="${BASE}/stata"

cycles=(2011_2013 2013_2015 2015_2017 2017_2019)

for cycle in "${cycles[@]}"; do
  curl -L -o "${OUT}/${cycle}_FemRespData.dat" "${BASE}/${cycle}_FemRespData.dat"
  curl -L -o "${OUT}/${cycle}_FemPregData.dat" "${BASE}/${cycle}_FemPregData.dat"
  curl -L -o "${OUT}/stata/${cycle}_FemRespSetup.dct" "${STATA}/${cycle}_FemRespSetup.dct"
  curl -L -o "${OUT}/stata/${cycle}_FemPregSetup.dct" "${STATA}/${cycle}_FemPregSetup.dct"
done

curl -L -o "${OUT}/2011_2019_FemaleWgtData.dat" "${BASE}/2011_2019_FemaleWgtData.dat"
curl -L -o "${OUT}/stata/2011_2019_FemaleWgtSetup.dct" "${STATA}/2011_2019_FemaleWgtSetup.dct"

cd "${OUT}"
sha256sum *.dat stata/*.dct > SHA256SUMS.txt
find . -maxdepth 2 -type f -printf '%P\t%s bytes\n' | sort
