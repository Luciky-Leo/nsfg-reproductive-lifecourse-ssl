"""Ever-pregnant stratum enrichment analysis for pregnancy-history endpoints.

This directly addresses the reviewer concern that pregnancy-history endpoint
enrichment can be mechanically driven by a phenotype axis separating respondents
with and without pregnancy records. The analysis restricts the 2022-2023
temporal-validation cohort to respondents with at least one linked pregnancy
record and reports phenotype enrichment inside that stratum.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"
TEST_CYCLE = "2022_2023"
WEIGHT_COL = "WGT2022_2023"
STRATA_COL = "VEST"
CLUSTER_COL = "VECL"
BOOTSTRAPS = 2000
SEED = 20260607

PREGNANCY_HISTORY_ENDPOINTS = [
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
]


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not mask.any():
        return float("nan")
    return float(np.sum(values[mask] * weights[mask]) / np.sum(weights[mask]))


def compute(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    phenotypes = sorted(df["phenotype"].dropna().astype(int).unique())
    weights = df[WEIGHT_COL].to_numpy(float)
    for endpoint in PREGNANCY_HISTORY_ENDPOINTS:
        y = df[endpoint].to_numpy(float)
        baseline = weighted_mean(y, weights)
        for phenotype in phenotypes:
            hit = df["phenotype"].to_numpy(int) == phenotype
            prev = weighted_mean(y[hit], weights[hit])
            rows.append(
                {
                    "endpoint": endpoint,
                    "phenotype": int(phenotype),
                    "n": int(hit.sum()),
                    "events": int(np.nansum(y[hit])),
                    "weighted_prevalence": prev,
                    "baseline_weighted_prevalence": baseline,
                    "prevalence_ratio": prev / baseline if baseline > 0 else np.nan,
                    "risk_difference": prev - baseline if np.isfinite(baseline) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def draw_stratified_cluster_sample(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for _, stratum in df.groupby(STRATA_COL, sort=False):
        clusters = stratum[CLUSTER_COL].dropna().unique()
        if len(clusters) == 0:
            continue
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        for cluster in sampled:
            pieces.append(stratum[stratum[CLUSTER_COL].eq(cluster)])
    if not pieces:
        return df.sample(frac=1.0, replace=True, random_state=int(rng.integers(1, 10_000_000)))
    return pd.concat(pieces, ignore_index=True)


def bootstrap_ci(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    phenotypes = sorted(df["phenotype"].dropna().astype(int).unique())
    records = {
        (endpoint, phenotype): {"prevalence_ratio": [], "risk_difference": []}
        for endpoint in PREGNANCY_HISTORY_ENDPOINTS
        for phenotype in phenotypes
    }
    for _ in range(BOOTSTRAPS):
        sample = draw_stratified_cluster_sample(df, rng)
        weights = sample[WEIGHT_COL].to_numpy(float)
        ph = sample["phenotype"].to_numpy(int)
        for endpoint in PREGNANCY_HISTORY_ENDPOINTS:
            y = sample[endpoint].to_numpy(float)
            baseline = weighted_mean(y, weights)
            for phenotype in phenotypes:
                hit = ph == phenotype
                prev = weighted_mean(y[hit], weights[hit])
                if baseline > 0 and np.isfinite(prev):
                    records[(endpoint, phenotype)]["prevalence_ratio"].append(prev / baseline)
                    records[(endpoint, phenotype)]["risk_difference"].append(prev - baseline)
    rows = []
    for endpoint in PREGNANCY_HISTORY_ENDPOINTS:
        for phenotype in phenotypes:
            pr = np.asarray(records[(endpoint, phenotype)]["prevalence_ratio"], dtype=float)
            rd = np.asarray(records[(endpoint, phenotype)]["risk_difference"], dtype=float)
            rows.append(
                {
                    "endpoint": endpoint,
                    "phenotype": int(phenotype),
                    "bootstrap_n": int(len(pr)),
                    "prevalence_ratio_ci_low": float(np.nanpercentile(pr, 2.5)) if len(pr) else np.nan,
                    "prevalence_ratio_ci_high": float(np.nanpercentile(pr, 97.5)) if len(pr) else np.nan,
                    "risk_difference_ci_low": float(np.nanpercentile(rd, 2.5)) if len(rd) else np.nan,
                    "risk_difference_ci_high": float(np.nanpercentile(rd, 97.5)) if len(rd) else np.nan,
                    "bootstrap_method": "ever-pregnant stratum; stratified cluster percentile bootstrap using VEST/VECL",
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(
        DATA / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz",
        usecols=["caseid", "cycle", "has_pregnancy_record"],
    )
    endpoints = pd.read_csv(DATA / "nsfg_endpoint_labels.csv.gz")
    assignments = pd.read_csv(DATA / "phenotype_assignments.csv.gz")
    design = pd.read_csv(
        DATA / "nsfg_2022_2023_lifecourse_matrix.csv.gz",
        usecols=["CaseID", WEIGHT_COL, STRATA_COL, CLUSTER_COL],
    ).rename(columns={"CaseID": "caseid"})
    merged = (
        df[df["cycle"].eq(TEST_CYCLE)]
        .merge(endpoints[endpoints["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
        .merge(assignments[assignments["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
        .merge(design, on="caseid", how="inner")
    )
    stratum = merged[pd.to_numeric(merged["has_pregnancy_record"], errors="coerce").eq(1)].copy()
    point = compute(stratum)
    ci = bootstrap_ci(stratum)
    out = point.merge(ci, on=["endpoint", "phenotype"], how="left")
    out.insert(0, "analysis", "2022-2023 ever-pregnant stratum")
    out.to_csv(TABLES / "supplementary_ever_pregnant_endpoint_enrichment.csv", index=False)
    summary = pd.DataFrame(
        [
            {
                "analysis": "2022-2023 ever-pregnant stratum",
                "n": int(len(stratum)),
                "phenotypes_included": ",".join(map(str, sorted(stratum["phenotype"].astype(int).unique()))),
                "strata": int(stratum[STRATA_COL].nunique()),
                "stratum_cluster_pairs": int(stratum[[STRATA_COL, CLUSTER_COL]].drop_duplicates().shape[0]),
                "bootstrap_replicates": BOOTSTRAPS,
            }
        ]
    )
    summary.to_csv(TABLES / "supplementary_ever_pregnant_design_summary.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
