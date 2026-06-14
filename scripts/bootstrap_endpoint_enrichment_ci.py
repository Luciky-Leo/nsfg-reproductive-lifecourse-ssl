"""Bootstrap uncertainty for temporal-validation phenotype endpoint enrichment.

This script recomputes 2022-2023 weighted endpoint prevalence by phenotype and
adds bootstrap percentile intervals for prevalence ratios and risk differences.
The bootstrap resamples public-use clusters with replacement within strata
(`VEST`/`VECL`) and retains the public-use NSFG weight column in each resampled
record.
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
SEED = 20260604

ENDPOINTS = [
    "contraceptive_vulnerability",
    "fertility_service_or_loss_help",
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
    "impaired_fecundity_status",
]


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not mask.any():
        return float("nan")
    return float(np.sum(values[mask] * weights[mask]) / np.sum(weights[mask]))


def compute_point_estimates(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    phenotypes = sorted(df["phenotype"].dropna().astype(int).unique())
    weights = df[WEIGHT_COL].to_numpy(float)
    for endpoint in ENDPOINTS:
        y = df[endpoint].to_numpy(float)
        baseline = weighted_mean(y, weights)
        for phenotype in phenotypes:
            subset = df["phenotype"].to_numpy(int) == phenotype
            y_sub = y[subset]
            w_sub = weights[subset]
            prev = weighted_mean(y_sub, w_sub)
            rows.append(
                {
                    "endpoint": endpoint,
                    "phenotype": phenotype,
                    "n": int(subset.sum()),
                    "events": int(np.nansum(y_sub)),
                    "weighted_prevalence": prev,
                    "baseline_weighted_prevalence": baseline,
                    "prevalence_ratio": prev / baseline if baseline > 0 else np.nan,
                    "risk_difference": prev - baseline,
                }
            )
    return pd.DataFrame(rows)


def draw_stratified_cluster_sample(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for _, stratum in df.groupby(STRATA_COL, sort=False):
        clusters = stratum[CLUSTER_COL].dropna().unique()
        sampled_clusters = rng.choice(clusters, size=len(clusters), replace=True)
        for cluster in sampled_clusters:
            pieces.append(stratum[stratum[CLUSTER_COL].eq(cluster)])
    return pd.concat(pieces, ignore_index=True)


def bootstrap_intervals(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    phenotypes = sorted(df["phenotype"].dropna().astype(int).unique())
    n_strata = int(df[STRATA_COL].nunique())
    n_clusters = int(df[[STRATA_COL, CLUSTER_COL]].drop_duplicates().shape[0])
    records: dict[tuple[str, int], dict[str, list[float]]] = {
        (endpoint, phenotype): {"prevalence_ratio": [], "risk_difference": []}
        for endpoint in ENDPOINTS
        for phenotype in phenotypes
    }

    for _ in range(BOOTSTRAPS):
        sample = draw_stratified_cluster_sample(df, rng)
        weights = sample[WEIGHT_COL].to_numpy(float)
        ph = sample["phenotype"].to_numpy(int)
        for endpoint in ENDPOINTS:
            y = sample[endpoint].to_numpy(float)
            baseline = weighted_mean(y, weights)
            for phenotype in phenotypes:
                subset = ph == phenotype
                prev = weighted_mean(y[subset], weights[subset])
                if baseline > 0 and np.isfinite(prev):
                    records[(endpoint, phenotype)]["prevalence_ratio"].append(prev / baseline)
                    records[(endpoint, phenotype)]["risk_difference"].append(prev - baseline)

    rows: list[dict[str, object]] = []
    for endpoint in ENDPOINTS:
        for phenotype in phenotypes:
            pr = np.asarray(records[(endpoint, phenotype)]["prevalence_ratio"], dtype=float)
            rd = np.asarray(records[(endpoint, phenotype)]["risk_difference"], dtype=float)
            rows.append(
                {
                    "endpoint": endpoint,
                    "phenotype": phenotype,
                    "bootstrap_n": int(len(pr)),
                    "prevalence_ratio_ci_low": float(np.nanpercentile(pr, 2.5)),
                    "prevalence_ratio_ci_high": float(np.nanpercentile(pr, 97.5)),
                    "risk_difference_ci_low": float(np.nanpercentile(rd, 2.5)),
                    "risk_difference_ci_high": float(np.nanpercentile(rd, 97.5)),
                    "bootstrap_seed": SEED,
                    "bootstrap_method": "stratified cluster percentile bootstrap using VEST/VECL with public-use weights retained",
                    "bootstrap_strata": n_strata,
                    "bootstrap_clusters": n_clusters,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    labels = pd.read_csv(DATA / "nsfg_endpoint_labels.csv.gz")
    phenotypes = pd.read_csv(DATA / "phenotype_assignments.csv.gz")
    matrix = pd.read_csv(
        DATA / "nsfg_2022_2023_lifecourse_matrix.csv.gz",
        usecols=["CaseID", WEIGHT_COL, STRATA_COL, CLUSTER_COL],
    ).rename(columns={"CaseID": "caseid"})

    labels = labels[labels["cycle"].eq(TEST_CYCLE)].copy()
    phenotypes = phenotypes[phenotypes["cycle"].eq(TEST_CYCLE)].copy()
    df = labels.merge(phenotypes[["caseid", "cycle", "phenotype"]], on=["caseid", "cycle"], how="inner")
    df = df.merge(matrix, on="caseid", how="inner")
    df["phenotype"] = df["phenotype"].astype(int)

    design_summary = pd.DataFrame(
        [
            {
                "cycle": TEST_CYCLE,
                "analysis_rows": int(len(df)),
                "strata_variable": STRATA_COL,
                "cluster_variable": CLUSTER_COL,
                "weight_variable": WEIGHT_COL,
                "n_strata": int(df[STRATA_COL].nunique()),
                "n_strata_cluster_pairs": int(df[[STRATA_COL, CLUSTER_COL]].drop_duplicates().shape[0]),
                "bootstrap_replicates": BOOTSTRAPS,
                "bootstrap_seed": SEED,
                "bootstrap_method": "stratified cluster percentile bootstrap using VEST/VECL with public-use weights retained",
            }
        ]
    )

    point = compute_point_estimates(df)
    ci = bootstrap_intervals(df)
    merged = point.merge(ci, on=["endpoint", "phenotype"], how="left")

    ci_path = TABLES / "endpoint_enrichment_by_phenotype_test_bootstrap_ci.csv"
    merged.to_csv(ci_path, index=False)
    design_path = TABLES / "endpoint_enrichment_bootstrap_design_summary.csv"
    design_summary.to_csv(design_path, index=False)

    primary_path = TABLES / "endpoint_enrichment_by_phenotype_test.csv"
    primary = pd.read_csv(primary_path)
    previous_ci_cols = [
        "prevalence_ratio_ci_low",
        "prevalence_ratio_ci_high",
        "risk_difference_ci_low",
        "risk_difference_ci_high",
        "bootstrap_n",
        "bootstrap_seed",
        "bootstrap_method",
        "bootstrap_strata",
        "bootstrap_clusters",
    ]
    primary = primary.drop(columns=[col for col in previous_ci_cols if col in primary.columns])
    ci_cols = [
        "endpoint",
        "phenotype",
        "prevalence_ratio_ci_low",
        "prevalence_ratio_ci_high",
        "risk_difference_ci_low",
        "risk_difference_ci_high",
        "bootstrap_n",
        "bootstrap_seed",
        "bootstrap_method",
        "bootstrap_strata",
        "bootstrap_clusters",
    ]
    updated = primary.merge(ci[ci_cols], on=["endpoint", "phenotype"], how="left")
    updated.to_csv(primary_path, index=False)

    print(f"Rows: {len(merged)}")
    print(f"Wrote {ci_path}")
    print(f"Wrote {design_path}")
    print(f"Updated {primary_path}")


if __name__ == "__main__":
    main()
