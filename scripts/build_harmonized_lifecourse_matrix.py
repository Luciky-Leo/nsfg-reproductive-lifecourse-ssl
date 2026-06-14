"""Build a harmonized NSFG respondent-level life-course matrix across cycles."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from parse_stata_dct import parse_dct, read_fwf_with_dct


ROOT = Path(__file__).resolve().parents[1]
RAW_1119 = ROOT / "data" / "raw" / "nsfg_2011_2019"
RAW_2223 = ROOT / "data" / "raw" / "nsfg_2022_2023"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"

CYCLES_1119 = ["2011_2013", "2013_2015", "2015_2017", "2017_2019"]
CYCLE_2223 = "2022_2023"

RESPONDENT_PATTERNS = {
    "demographics_social": r"age|hisp|race|educ|school|poverty|labor|metro|relig|insur|curr_ins|hieduc|wgt|vest|vecl",
    "partnership_marriage": r"mar|cohab|husb|part|relat|engag|manrel|fmarit|rmarit",
    "reproductive_timing": r"menarche|preg|birth|parity|numchild|kid|lbpreg|compreg",
    "contraception_sexual": r"constat|meth|pill|iud|ster|sex|rhadsex|eversex|cont|use",
    "fertility_repro_health": r"infert|fecund|hlpprg|hlpmc|anyprghp|anymschp|infever|insem|invitro|ovul|tubes|advice|endo|fibroid|pid|pcos|gestdiab|genwarts|herpes|chlam|gonorr|hiv",
    "health_behavior": r"smk|smok|bmi|weight|height|diab|hypert|health",
}

PREG_CATEGORICAL = [
    "outcome",
    "pregend1",
    "pregend2",
    "bornaliv",
    "recnt5yrprg",
    "evuseint",
    "stopduse",
    "wantbold",
    "timingok",
    "newwantr",
    "wantresp",
    "wantpart",
    "priorsmk",
    "postsmks",
    "getprena",
    "bgnprena",
    "gest_lb",
    "gest_othr",
    "gestimp",
    "birthwgt",
    "lbw1",
]

PREG_NUMERIC = ["pregordr", "agepreg", "agecon", "kidage", "bfeedwks"]

ID_WEIGHT_COLS = [
    "caseid",
    "age_r",
    "ager",
    "wgt2011_2013",
    "wgt2013_2015",
    "wgt2015_2017",
    "wgt2017_2019",
    "wgt2022_2023",
    "wgt2022_2023",
    "wgt2011_2019",
    "vest",
    "vecl",
    "secu",
    "sest",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    return df


def read_resp_1119(cycle: str) -> pd.DataFrame:
    dat = RAW_1119 / f"{cycle}_FemRespData.dat"
    dct = RAW_1119 / "stata" / f"{cycle}_FemRespSetup.dct"
    return read_fwf_with_dct(dat, dct)


def read_preg_1119(cycle: str) -> pd.DataFrame:
    dat = RAW_1119 / f"{cycle}_FemPregData.dat"
    dct = RAW_1119 / "stata" / f"{cycle}_FemPregSetup.dct"
    return read_fwf_with_dct(dat, dct)


def read_resp_2223() -> pd.DataFrame:
    df = pd.read_csv(RAW_2223 / "NSFG_2022_2023_FemRespPUFData.csv", dtype="string", low_memory=False)
    return normalize_columns(df)


def read_preg_2223() -> pd.DataFrame:
    df = pd.read_csv(RAW_2223 / "NSFG_2022_2023_FemPregPUFData.csv", dtype="string", low_memory=False)
    return normalize_columns(df)


def selected_respondent_columns(df: pd.DataFrame) -> list[str]:
    keep = []
    for col in df.columns:
        if col in ID_WEIGHT_COLS:
            keep.append(col)
            continue
        for pattern in RESPONDENT_PATTERNS.values():
            if re.search(pattern, col, flags=re.IGNORECASE):
                keep.append(col)
                break
    return sorted(set(keep), key=keep.index)


def aggregate_pregnancy(preg: pd.DataFrame) -> pd.DataFrame:
    preg = normalize_columns(preg)
    if "caseid" not in preg.columns:
        raise ValueError("Pregnancy file lacks caseid")
    if "birthwgt" in preg.columns and "lbw1" not in preg.columns:
        birthwgt = preg["birthwgt"].astype("string").str.strip()
        preg["lbw1"] = birthwgt.map({"2": "1", "1": "2", "8": "8", "9": "9"})
    base = preg[["caseid"]].drop_duplicates().copy()
    counts = preg.groupby("caseid").size().rename("preg_n_records").reset_index()
    base = base.merge(counts, on="caseid", how="left")

    for col in PREG_CATEGORICAL:
        if col not in preg.columns:
            continue
        values = preg[col].dropna().astype(str).str.strip()
        values = sorted([v for v in values.unique() if v and v.lower() != "nan"], key=str)[:12]
        for value in values:
            safe = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
            name = f"preg_{col}_code_{safe}_n"
            hit = preg[["caseid", col]].copy()
            hit[name] = hit[col].astype("string").str.strip().eq(str(value)).fillna(False).astype(int)
            agg = hit.groupby("caseid")[name].sum().reset_index()
            base = base.merge(agg, on="caseid", how="left")
            base[name] = base[name].fillna(0).astype("int64")

    for col in PREG_NUMERIC:
        if col not in preg.columns:
            continue
        tmp = preg[["caseid", col]].copy()
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        agg = tmp.groupby("caseid")[col].agg(["min", "max", "mean"]).reset_index()
        agg = agg.rename(columns={s: f"preg_{col}_{s}" for s in ["min", "max", "mean"]})
        base = base.merge(agg, on="caseid", how="left")
    return base


def age_numeric(df: pd.DataFrame) -> pd.Series:
    for col in ["age_r", "ager"]:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def cycle_analysis_weight(df: pd.DataFrame, cycle: str) -> pd.Series:
    exact = f"wgt{cycle}"
    exact = exact.replace("_", "_")
    candidates = [
        exact,
        f"wgt{cycle.replace('_', '_')}",
        f"wgt{cycle.replace('_', '')}",
        "wgt2022_2023",
        "wgt2017_2019",
        "wgt2015_2017",
        "wgt2013_2015",
        "wgt2011_2013",
    ]
    for col in candidates:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce")
    weight_cols = [c for c in df.columns if c.startswith("wgt")]
    if weight_cols:
        return pd.to_numeric(df[weight_cols[0]], errors="coerce")
    return pd.Series(1.0, index=df.index)


def load_weight_2011_2019() -> pd.DataFrame | None:
    dat = RAW_1119 / "2011_2019_FemaleWgtData.dat"
    dct = RAW_1119 / "stata" / "2011_2019_FemaleWgtSetup.dct"
    if not dat.exists() or not dct.exists():
        return None
    return read_fwf_with_dct(dat, dct)


def build_cycle(cycle: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if cycle == CYCLE_2223:
        resp = read_resp_2223()
        preg = read_preg_2223()
    else:
        resp = read_resp_1119(cycle)
        preg = read_preg_1119(cycle)
    resp = normalize_columns(resp)
    preg_agg = aggregate_pregnancy(preg)
    resp = resp[selected_respondent_columns(resp)].copy()
    matrix = resp.merge(preg_agg, on="caseid", how="left")
    matrix["has_pregnancy_record"] = matrix["preg_n_records"].notna().astype("int8")
    matrix["preg_n_records"] = matrix["preg_n_records"].fillna(0).astype("int64")
    matrix["cycle"] = cycle
    matrix["age_analysis"] = age_numeric(matrix)
    matrix["analysis_weight"] = cycle_analysis_weight(matrix, cycle)
    matrix = matrix[matrix["age_analysis"].between(15, 44, inclusive="both")].copy()
    linkage = pd.DataFrame(
        [
            {
                "cycle": cycle,
                "respondents_15_44": int(matrix.shape[0]),
                "columns_raw_cycle_matrix": int(matrix.shape[1]),
                "pregnancy_caseids": int(preg["caseid"].nunique()),
                "respondents_with_pregnancy_records_15_44": int(matrix["has_pregnancy_record"].sum()),
            }
        ]
    )
    return matrix, linkage


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    matrices = []
    linkages = []
    for cycle in CYCLES_1119 + [CYCLE_2223]:
        matrix, linkage = build_cycle(cycle)
        matrices.append(matrix)
        linkages.append(linkage)

    common = sorted(set.intersection(*(set(m.columns) for m in matrices)))
    required = ["caseid", "cycle", "age_analysis", "analysis_weight", "has_pregnancy_record", "preg_n_records"]
    for col in required:
        if col not in common:
            common.append(col)
    common = [c for c in common if c in set.intersection(*(set(m.columns) for m in matrices))]
    full = pd.concat([m[common].copy() for m in matrices], ignore_index=True)

    weights = load_weight_2011_2019()
    if weights is not None and "caseid" in weights.columns:
        weights = weights.drop_duplicates("caseid")
        full = full.merge(weights, on="caseid", how="left", suffixes=("", "_combined"))

    out_path = PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz"
    full.to_csv(out_path, index=False, compression="gzip")

    pd.concat(linkages, ignore_index=True).to_csv(TABLES / "harmonized_cycle_linkage_summary.csv", index=False)
    pd.DataFrame({"variable": full.columns}).to_csv(TABLES / "harmonized_feature_list.csv", index=False)
    summary = (
        full.groupby("cycle", dropna=False)
        .agg(respondents=("caseid", "count"), respondents_with_pregnancy=("has_pregnancy_record", "sum"))
        .reset_index()
    )
    summary["features"] = full.shape[1]
    summary.to_csv(TABLES / "harmonized_matrix_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"matrix={out_path}")


if __name__ == "__main__":
    main()
