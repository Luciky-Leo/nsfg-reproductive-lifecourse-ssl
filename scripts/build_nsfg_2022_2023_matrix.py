"""Build a respondent-level 2022-2023 NSFG reproductive life-course matrix."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nsfg_2022_2023"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"

FEM_RESP = RAW / "NSFG_2022_2023_FemRespPUFData.csv"
FEM_PREG = RAW / "NSFG_2022_2023_FemPregPUFData.csv"

ID_AND_DESIGN = ["CaseID", "WGT2022_2023", "VEST", "VECL"]

RESPONDENT_BLOCKS = {
    "demographics_social": r"AGE|HISP|RACE|EDUC|SCHOOL|POVERTY|LABOR|METRO|RELIG|INS",
    "partnership_marriage": r"MAR|COHAB|HUSB|PART|RELAT|ENGAG|MANREL",
    "reproductive_timing": r"MENARCHE|PREG|BIRTH|PARITY|NUMCHILD|KID",
    "contraception_sexual": r"CONTRA|CONSTAT|METH|PILL|IUD|STER|SEX|RHADSEX|EVERSEX|CONT",
    "fertility_services_art": r"ADOPT|EMBRYO|DONOR|IVF|ART|FERT|CLINIC|TREAT|SERVICE",
    "health_behavior": r"SMK|SMOK|BMI|WEIGHT|HEIGHT|DIAB|HYPERT|HEALTH",
}

PREG_CATEGORICAL = [
    "OUTCOME",
    "BORNALIV",
    "RECNT5YRPRG",
    "EVUSEINT",
    "STOPDUSE",
    "WANTBOLD",
    "TIMINGOK",
    "NEWWANTR",
    "wantresp",
    "WANTPART",
    "PRIORSMK",
    "POSTSMKS",
    "GETPRENA",
    "BGNPRENA",
    "GEST_LB",
    "GEST_OTHR",
    "GestImp",
    "BIRTHWGT",
]

PREG_NUMERIC = ["PREGORDR", "agepreg", "agecon", "KIDAGE", "BFEEDWKS"]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype="string", low_memory=False)


def missing_rate(series: pd.Series) -> float:
    values = series.astype("string")
    missing = values.isna() | values.str.strip().isin(["", ".", "NA", "NaN"])
    return float(missing.mean())


def assign_block(column: str) -> str | None:
    for block, pattern in RESPONDENT_BLOCKS.items():
        if re.search(pattern, column, flags=re.IGNORECASE):
            return block
    return None


def select_respondent_features(resp: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    rows = []
    selected = []
    for col in resp.columns:
        if col in ID_AND_DESIGN:
            selected.append(col)
            rows.append(
                {
                    "variable": col,
                    "source": "female_respondent",
                    "block": "id_design",
                    "missing_rate": round(missing_rate(resp[col]), 4),
                }
            )
            continue
        block = assign_block(col)
        if block is None:
            continue
        miss = missing_rate(resp[col])
        if miss >= 0.995:
            continue
        selected.append(col)
        rows.append(
            {
                "variable": col,
                "source": "female_respondent",
                "block": block,
                "missing_rate": round(miss, 4),
            }
        )
    return selected, pd.DataFrame(rows)


def aggregate_pregnancy(preg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = preg[["CaseID"]].drop_duplicates().copy()
    counts = preg.groupby("CaseID", dropna=True).size().rename("preg_n_records").reset_index()
    base = base.merge(counts, on="CaseID", how="left")

    feature_rows = [
        {
            "variable": "preg_n_records",
            "source": "female_pregnancy_aggregate",
            "block": "pregnancy_record_count",
            "missing_rate": 0.0,
        }
    ]

    for col in PREG_CATEGORICAL:
        if col not in preg.columns:
            continue
        series = preg[["CaseID", col]].dropna()
        for code in sorted(series[col].dropna().unique(), key=lambda x: str(x))[:20]:
            name = f"preg_{col}_code_{code}_n"
            tmp = (
                series.assign(_hit=series[col].eq(code).astype(int))
                .groupby("CaseID")["_hit"]
                .sum()
                .rename(name)
                .reset_index()
            )
            base = base.merge(tmp, on="CaseID", how="left")
            base[name] = base[name].fillna(0).astype("int64")
            feature_rows.append(
                {
                    "variable": name,
                    "source": "female_pregnancy_aggregate",
                    "block": f"pregnancy_{col}",
                    "missing_rate": 0.0,
                }
            )

    for col in PREG_NUMERIC:
        if col not in preg.columns:
            continue
        numeric = pd.to_numeric(preg[col], errors="coerce")
        tmp = (
            preg.assign(_value=numeric)
            .groupby("CaseID")["_value"]
            .agg(["min", "max", "mean"])
            .reset_index()
        )
        tmp = tmp.rename(
            columns={
                "min": f"preg_{col}_min",
                "max": f"preg_{col}_max",
                "mean": f"preg_{col}_mean",
            }
        )
        base = base.merge(tmp, on="CaseID", how="left")
        for suffix in ["min", "max", "mean"]:
            name = f"preg_{col}_{suffix}"
            feature_rows.append(
                {
                    "variable": name,
                    "source": "female_pregnancy_aggregate",
                    "block": f"pregnancy_{col}",
                    "missing_rate": round(missing_rate(base[name]), 4),
                }
            )

    return base, pd.DataFrame(feature_rows)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    resp = read_csv(FEM_RESP)
    preg = read_csv(FEM_PREG)

    resp_cols, resp_inventory = select_respondent_features(resp)
    preg_agg, preg_inventory = aggregate_pregnancy(preg)

    matrix = resp[resp_cols].merge(preg_agg, on="CaseID", how="left")
    matrix["has_pregnancy_record"] = matrix["preg_n_records"].notna().astype("int8")
    matrix["preg_n_records"] = matrix["preg_n_records"].fillna(0).astype("int64")

    matrix_path = PROCESSED / "nsfg_2022_2023_lifecourse_matrix.csv.gz"
    matrix.to_csv(matrix_path, index=False, compression="gzip")

    inventory = pd.concat([resp_inventory, preg_inventory], ignore_index=True)
    inventory = pd.concat(
        [
            inventory,
            pd.DataFrame(
                [
                    {
                        "variable": "has_pregnancy_record",
                        "source": "derived",
                        "block": "pregnancy_record_count",
                        "missing_rate": 0.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    inventory.to_csv(TABLES / "nsfg_2022_2023_lifecourse_feature_inventory.csv", index=False)

    summary = pd.DataFrame(
        [
            {"metric": "respondents", "value": int(matrix.shape[0])},
            {"metric": "features_including_caseid_and_design", "value": int(matrix.shape[1])},
            {"metric": "respondent_source_features", "value": int(len(resp_cols))},
            {"metric": "pregnancy_aggregate_features", "value": int(preg_agg.shape[1] - 1)},
            {
                "metric": "respondents_with_pregnancy_records",
                "value": int(matrix["has_pregnancy_record"].sum()),
            },
        ]
    )
    summary.to_csv(TABLES / "nsfg_2022_2023_lifecourse_matrix_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"matrix={matrix_path}")


if __name__ == "__main__":
    main()
