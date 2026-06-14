# Data Sources

## Primary public-use data

National Survey of Family Growth (NSFG), 2022-2023 public-use release.

Official page:
https://www.cdc.gov/nchs/nsfg/nsfg-2022-2023-puf.htm

Downloaded for the smoke test:

| File | Purpose |
|---|---|
| `NSFG-2022-2023-FemRespPUFData.zip` | Female respondent public-use CSV archive |
| `NSFG-2022-2023-FemPregPUFData.zip` | Female pregnancy public-use CSV archive |
| `2022-2023-NSFG-FileIndex-FemRespPUF.pdf` | Female respondent variable index |
| `2022-2023-NSFG-FileIndex-FemPregPUF.pdf` | Female pregnancy variable index |
| `2022-2023-NSFG-FemRespPUFCodebook.pdf` | Female respondent codebook |
| `2022-2023-NSFG-FemPregPUFCodebook.pdf` | Female pregnancy codebook |
| `NSFG-2022-2023-UsersGuide-revJuly2025.pdf` | User guide and survey documentation |

Raw public-use files are kept under `data/raw/nsfg_2022_2023/` and are excluded
from git. The download script is `scripts/download_nsfg_2022_2023.sh`.

## Planned extension

For the full manuscript, harmonize the 2011-2013, 2013-2015, 2015-2017,
2017-2019, and 2022-2023 NSFG female respondent and female pregnancy files.
The CDC page for 2011-2019 combined use explains how to combine NSFG releases
from 2011-2019:

https://www.cdc.gov/nchs/nsfg/nsfg_2011_2019_combined_files.htm

## Data-use boundary

Only public-use NSFG files will be used. Restricted contextual or geography
variables are not needed for the rapid second-paper version.
