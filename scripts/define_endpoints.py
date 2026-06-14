"""Define leakage-auditable reproductive-health endpoints for NSFG analyses."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "processed" / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"


ENDPOINTS = {
    "contraceptive_vulnerability": {
        "label": "Current contraceptive nonuse despite intercourse in the 3 months before interview",
        "positive_definition": "CONSTAT1 code 42; denominator is the NSFG analytic female respondent population, interpreted as a current vulnerability proxy rather than an incident pregnancy outcome",
        "direct_feature_regex": "constat|currmeth|meth",
        "interpretation": "A current contraceptive vulnerability proxy, not a pregnancy outcome.",
    },
    "fertility_service_or_loss_help": {
        "label": "Ever received medical help to become pregnant or to prevent miscarriage",
        "positive_definition": "HLPPRG code 1 or HLPMC code 1, indicating ever receiving medical help to become pregnant or to prevent miscarriage",
        "direct_feature_regex": "hlpprg|hlpmc|infert|fecund|infever|anyprghp|anymschp|ovul|insem|invitro|tubes|advice|endomet|fibroid",
        "interpretation": "A fertility-care and pregnancy-loss-care utilization endpoint.",
    },
    "unintended_mistimed_pregnancy_history": {
        "label": "Any pregnancy recorded as too soon, mistimed, or unwanted",
        "positive_definition": "Among respondents with pregnancy records, any NEWWANTR code 3/4/6, WANTRESP code 3/5, WANTPART code 3/5, TIMINGOK code 3, or WANTBOLD code 5",
        "direct_feature_regex": "preg_newwantr|preg_wantresp|preg_wantpart|preg_timingok|preg_wantbold",
        "interpretation": "A lifetime pregnancy-intention history proxy among respondents with pregnancy records.",
    },
    "adverse_pregnancy_history_proxy": {
        "label": "Any low-birthweight live birth or stillbirth history",
        "positive_definition": "Among respondents with pregnancy records, any public-use low-birthweight live birth indicator (LBW1 code 1) or stillbirth outcome (OUTCOME code 3)",
        "direct_feature_regex": "preg_lbw|preg_outcome|birthwgt|gest",
        "interpretation": "A public-use adverse pregnancy-history proxy, not a clinical diagnosis.",
    },
    "impaired_fecundity_status": {
        "label": "Fecundity limitation or infertility status",
        "positive_definition": "FECUND code 2-5 or INFERT code 1-2, using public-use NSFG fecundity or infertility recodes and excluding FECUND code 1 contraceptive sterilization",
        "direct_feature_regex": "fecund|infert|hlpprg|hlpmc|infever|anyprghp|anymschp",
        "interpretation": "A broad public-use fecundity-limitation or infertility proxy that excludes contraceptive sterilization and is not a clinical infertility diagnosis.",
    },
}


def num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def positive_count(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    out = pd.Series(0, index=df.index, dtype="int64")
    for col in cols:
        if col in df.columns:
            out = out + num(df, col).fillna(0).gt(0).astype("int64")
    return out


def define(df: pd.DataFrame) -> pd.DataFrame:
    endpoints = pd.DataFrame({"caseid": df["caseid"], "cycle": df["cycle"]})
    endpoints["contraceptive_vulnerability"] = num(df, "constat1").eq(42).astype("int64")

    endpoints["fertility_service_or_loss_help"] = (
        num(df, "hlpprg").eq(1) | num(df, "hlpmc").eq(1)
    ).astype("int64")

    unintended_cols = [
        "preg_newwantr_code_3_n",
        "preg_newwantr_code_4_n",
        "preg_newwantr_code_6_n",
        "preg_wantresp_code_3_n",
        "preg_wantresp_code_5_n",
        "preg_wantpart_code_3_n",
        "preg_wantpart_code_5_n",
        "preg_timingok_code_3_n",
        "preg_wantbold_code_5_n",
    ]
    endpoints["unintended_mistimed_pregnancy_history"] = positive_count(df, unintended_cols).gt(0).astype("int64")

    adverse_cols = ["preg_lbw1_code_1_n", "preg_outcome_code_3_n"]
    endpoints["adverse_pregnancy_history_proxy"] = positive_count(df, adverse_cols).gt(0).astype("int64")

    endpoints["impaired_fecundity_status"] = (
        num(df, "fecund").isin([2, 3, 4, 5]) | num(df, "infert").isin([1, 2])
    ).astype("int64")

    return endpoints


def weighted_prevalence(y: pd.Series, w: pd.Series) -> float:
    mask = y.notna() & w.notna()
    if mask.sum() == 0 or w[mask].sum() == 0:
        return float("nan")
    return float((y[mask].astype(float) * w[mask].astype(float)).sum() / w[mask].astype(float).sum())


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(MATRIX)
    endpoints = define(df)
    endpoints.to_csv(PROCESSED / "nsfg_endpoint_labels.csv.gz", index=False, compression="gzip")

    rows = []
    for name, meta in ENDPOINTS.items():
        for cycle, sub in endpoints.groupby("cycle"):
            idx = sub.index
            rows.append(
                {
                    "endpoint": name,
                    "cycle": cycle,
                    "n": int(len(sub)),
                    "events": int(sub[name].sum()),
                    "unweighted_prevalence": float(sub[name].mean()),
                    "weighted_prevalence": weighted_prevalence(sub[name], df.loc[idx, "analysis_weight"]),
                    **meta,
                }
            )
    pd.DataFrame(rows).to_csv(TABLES / "endpoint_prevalence_by_cycle.csv", index=False)
    pd.DataFrame(
        [{"endpoint": k, **v} for k, v in ENDPOINTS.items()]
    ).to_csv(TABLES / "endpoint_definitions.csv", index=False)
    (TABLES / "endpoint_definitions.json").write_text(json.dumps(ENDPOINTS, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows).query("cycle == '2022_2023'")[["endpoint", "n", "events", "unweighted_prevalence", "weighted_prevalence"]].to_string(index=False))


if __name__ == "__main__":
    main()
