"""Smoke test for the 2022-2023 NSFG public-use female files.

The goal is not to fit a model yet. This script verifies that the public CSVs
load correctly, checks respondent-pregnancy linkage, and inventories variables
that can support a reproductive life-course SSL phenotype study.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nsfg_2022_2023"
OUT = ROOT / "results" / "tables"
LOGS = ROOT / "logs"

FEM_RESP = RAW / "NSFG_2022_2023_FemRespPUFData.csv"
FEM_PREG = RAW / "NSFG_2022_2023_FemPregPUFData.csv"

THEME_PATTERNS = {
    "identity_design_weight": r"^(CaseID|WGT|VEST|VECL|SEST|SECU)|WEIGHT|STRAT|CLUST",
    "demographics_social": r"AGE|HISP|RACE|EDUC|SCHOOL|POVERTY|LABOR|METRO|RELIG|INS|INCOME",
    "partnership_marriage": r"MAR|COHAB|HUSB|PART|RELAT|ENGAG|WIFE|MANREL",
    "pregnancy_fertility_history": r"PREG|BIRTH|PARITY|NUMCHILD|KID|MENARCHE|FECUND|INFERT|TRY",
    "contraception_sexual": r"CONTRA|CONSTAT|METH|PILL|IUD|STER|SEX|RHADSEX|EVERSEX|CONT",
    "fertility_services_art": r"ADOPT|EMBRYO|DONOR|IVF|ART|FERT|CLINIC|TREAT|SERVICE",
    "pregnancy_intention_outcome": r"WANT|TIMING|TOOSOON|LATER|OUTCOME|GEST|BIRTHWGT|BORNALIV",
    "health_behavior": r"SMK|SMOK|BMI|WEIGHT|HEIGHT|DIAB|HYPERT|HEALTH|ALCOHOL|DRUG",
    "imputation_flags": r"_I$|IMPUT",
}

CANDIDATE_VARIABLES = [
    "CaseID",
    "WGT2022_2023",
    "VEST",
    "VECL",
    "AGE_R",
    "AGER",
    "HISP",
    "HISPANIC",
    "HISPRACE2",
    "WOMRASDU",
    "HIEDUC",
    "POVERTY",
    "MARSTAT",
    "FMARITAL",
    "RMARITAL",
    "EVERSEX",
    "RHADSEX",
    "CURRPREG",
    "LASTPREG",
    "PREGNUM",
    "PARITY",
    "NUMCHILD",
    "MENARCHE",
    "TRYLONG",
    "EVCONTAG",
    "EVWNTANO",
    "HRDEMBRYO",
    "EVERADOPT",
    "SEEKADPT",
    "OUTCOME",
    "BORNALIV",
    "RECNT5YRPRG",
    "KNEWPREG",
    "PRIORSMK",
    "POSTSMKS",
    "GETPRENA",
    "BGNPRENA",
    "GEST_LB",
    "GEST_OTHR",
    "GestImp",
    "BIRTHWGT",
    "WANTBOLD",
    "TIMINGOK",
    "NEWWANTR",
    "wantresp",
    "WANTPART",
]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype="string", low_memory=False)


def missing_rate(series: pd.Series) -> float:
    values = series.astype("string")
    empty = values.isna() | values.str.strip().isin(["", ".", "NA", "NaN"])
    return float(empty.mean())


def value_counts_compact(series: pd.Series, n: int = 8) -> str:
    vc = series.astype("string").fillna("<NA>").value_counts(dropna=False).head(n)
    return "; ".join(f"{idx}:{int(val)}" for idx, val in vc.items())


def inventory_variables(columns: list[str]) -> pd.DataFrame:
    rows = []
    for col in columns:
        themes = [
            theme
            for theme, pattern in THEME_PATTERNS.items()
            if re.search(pattern, col, flags=re.IGNORECASE)
        ]
        if themes:
            rows.append({"variable": col, "themes": "|".join(themes)})
    return pd.DataFrame(rows)


def screen_candidates(df: pd.DataFrame, table: str) -> pd.DataFrame:
    rows = []
    for col in CANDIDATE_VARIABLES:
        if col not in df.columns:
            continue
        rows.append(
            {
                "table": table,
                "variable": col,
                "n_nonmissing": int(df[col].notna().sum()),
                "missing_rate": round(missing_rate(df[col]), 4),
                "top_values": value_counts_compact(df[col]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    resp = read_csv(FEM_RESP)
    preg = read_csv(FEM_PREG)

    summary = pd.DataFrame(
        [
            {
                "table": "female_respondent",
                "path": str(FEM_RESP.relative_to(ROOT)),
                "rows": len(resp),
                "columns": resp.shape[1],
                "unique_caseid": resp["CaseID"].nunique() if "CaseID" in resp else None,
            },
            {
                "table": "female_pregnancy",
                "path": str(FEM_PREG.relative_to(ROOT)),
                "rows": len(preg),
                "columns": preg.shape[1],
                "unique_caseid": preg["CaseID"].nunique() if "CaseID" in preg else None,
            },
        ]
    )
    summary.to_csv(OUT / "nsfg_2022_2023_smoke_summary.csv", index=False)

    resp_cases = set(resp["CaseID"].dropna()) if "CaseID" in resp else set()
    preg_cases = set(preg["CaseID"].dropna()) if "CaseID" in preg else set()
    preg_per_resp = preg.groupby("CaseID", dropna=True).size() if "CaseID" in preg else pd.Series(dtype=int)
    linkage = pd.DataFrame(
        [
            {
                "metric": "pregnancy_records",
                "value": len(preg),
            },
            {
                "metric": "respondents_with_pregnancy_records",
                "value": len(preg_cases),
            },
            {
                "metric": "pregnancy_caseids_present_in_respondent_file",
                "value": len(preg_cases & resp_cases),
            },
            {
                "metric": "pregnancy_caseids_missing_from_respondent_file",
                "value": len(preg_cases - resp_cases),
            },
            {
                "metric": "median_pregnancy_records_per_pregnant_respondent",
                "value": float(preg_per_resp.median()) if not preg_per_resp.empty else None,
            },
            {
                "metric": "max_pregnancy_records_per_respondent",
                "value": int(preg_per_resp.max()) if not preg_per_resp.empty else None,
            },
        ]
    )
    linkage.to_csv(OUT / "pregnancy_linkage_summary.csv", index=False)

    inventory = pd.concat(
        [
            inventory_variables(list(resp.columns)).assign(table="female_respondent"),
            inventory_variables(list(preg.columns)).assign(table="female_pregnancy"),
        ],
        ignore_index=True,
    )
    inventory = inventory[["table", "variable", "themes"]]
    inventory.to_csv(OUT / "candidate_variable_inventory.csv", index=False)

    outcomes = pd.concat(
        [
            screen_candidates(resp, "female_respondent"),
            screen_candidates(preg, "female_pregnancy"),
        ],
        ignore_index=True,
    )
    outcomes.to_csv(OUT / "outcome_screening_2022_2023.csv", index=False)

    payload = {
        "female_respondent": {"rows": int(resp.shape[0]), "columns": int(resp.shape[1])},
        "female_pregnancy": {"rows": int(preg.shape[0]), "columns": int(preg.shape[1])},
        "candidate_inventory_rows": int(len(inventory)),
        "screened_candidate_variables": int(len(outcomes)),
        "source_files": {
            "female_respondent": str(FEM_RESP),
            "female_pregnancy": str(FEM_PREG),
        },
    }
    (LOGS / "nsfg_2022_2023_smoke_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
