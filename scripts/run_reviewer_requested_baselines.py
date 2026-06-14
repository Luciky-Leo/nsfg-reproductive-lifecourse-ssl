"""Reviewer-requested trivial and raw-feature baselines.

These analyses address the strongest simulated-reviewer concern: the SSL
profiles may simply restate age, parity, and pregnancy exposure. The outputs
are intentionally conservative and are used to calibrate claims rather than to
retrofit a stronger story.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from train_ssl_phenotypes import (
    DEV_CYCLE,
    PROCESSED,
    TABLES,
    TEST_CYCLE,
    TRAIN_CYCLES,
    Config,
    numeric_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = [
    "contraceptive_vulnerability",
    "fertility_service_or_loss_help",
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
    "impaired_fecundity_status",
]
PREGNANCY_HISTORY_ENDPOINTS = {
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
}


def weighted_mean(values: pd.Series | np.ndarray, weights: pd.Series | np.ndarray) -> float:
    y = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    w = pd.to_numeric(pd.Series(weights), errors="coerce").to_numpy(float)
    mask = np.isfinite(y) & np.isfinite(w) & (w > 0)
    if not mask.any():
        return float("nan")
    return float(np.sum(y[mask] * w[mask]) / np.sum(w[mask]))


def load_core() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    df = pd.read_csv(PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz")
    endpoints = pd.read_csv(PROCESSED / "nsfg_endpoint_labels.csv.gz")
    assignments = pd.read_csv(PROCESSED / "phenotype_assignments.csv.gz")
    embeddings = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
    feature_audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    features = feature_audit.loc[
        feature_audit["used_in_primary_encoder"].astype(bool),
        "feature",
    ].tolist()
    return df, endpoints, assignments, embeddings, features


def test_frame(df: pd.DataFrame, endpoints: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "caseid",
        "cycle",
        "analysis_weight",
        "age_analysis",
        "parity",
        "has_pregnancy_record",
    ]
    frame = (
        df.loc[df["cycle"].eq(TEST_CYCLE), [c for c in keep if c in df.columns]]
        .merge(endpoints.loc[endpoints["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
        .merge(assignments.loc[assignments["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
    )
    frame["age_group"] = pd.cut(
        pd.to_numeric(frame["age_analysis"], errors="coerce"),
        bins=[14, 24, 34, 44],
        labels=["15-24", "25-34", "35-44"],
        include_lowest=True,
    ).astype("string")
    parity = pd.to_numeric(frame["parity"], errors="coerce")
    frame["parity_group"] = np.select(
        [parity.eq(0), parity.between(1, 2, inclusive="both"), parity.ge(3)],
        ["0", "1-2", "3+"],
        default="missing",
    )
    ever = pd.to_numeric(frame["has_pregnancy_record"], errors="coerce").fillna(0).astype(int)
    frame["ever_pregnant_group"] = np.where(ever.eq(1), "ever pregnant", "no pregnancy record")
    frame["age_parity_group"] = frame["age_group"].fillna("missing") + " / parity " + frame["parity_group"].astype(str)
    frame["age_ever_pregnant_group"] = (
        frame["age_group"].fillna("missing") + " / " + frame["ever_pregnant_group"].astype(str)
    )
    frame["phenotype_group"] = "P" + pd.to_numeric(frame["phenotype"], errors="coerce").astype("Int64").astype(str)
    return frame


def group_enrichment(frame: pd.DataFrame, group_col: str, label: str, analysis_set: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for endpoint in ENDPOINTS:
        if analysis_set == "ever-pregnant stratum" and endpoint not in PREGNANCY_HISTORY_ENDPOINTS:
            continue
        subframe = frame
        if analysis_set == "ever-pregnant stratum":
            subframe = frame[pd.to_numeric(frame["has_pregnancy_record"], errors="coerce").eq(1)].copy()
        base = weighted_mean(subframe[endpoint], subframe["analysis_weight"])
        for group, sub in subframe.groupby(group_col, dropna=False, sort=True):
            prev = weighted_mean(sub[endpoint], sub["analysis_weight"])
            rows.append(
                {
                    "analysis_set": analysis_set,
                    "method": label,
                    "endpoint": endpoint,
                    "group": str(group),
                    "n": int(len(sub)),
                    "events": int(pd.to_numeric(sub[endpoint], errors="coerce").fillna(0).sum()),
                    "weighted_prevalence": prev,
                    "baseline_weighted_prevalence": base,
                    "prevalence_ratio": prev / base if base and np.isfinite(base) else np.nan,
                    "risk_difference": prev - base if np.isfinite(base) else np.nan,
                    "group_share": float(len(sub) / len(subframe)) if len(subframe) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def summarize_group_baselines(stats: pd.DataFrame, min_n: int = 50) -> pd.DataFrame:
    rows = []
    eligible = stats[stats["n"].ge(min_n)].copy()
    for (analysis_set, endpoint, method), sub in eligible.groupby(["analysis_set", "endpoint", "method"], sort=False):
        top = sub.sort_values(["prevalence_ratio", "n"], ascending=[False, False]).iloc[0]
        rows.append(
            {
                "analysis_set": analysis_set,
                "endpoint": endpoint,
                "method": method,
                "top_group": top["group"],
                "top_n": int(top["n"]),
                "top_events": int(top["events"]),
                "top_weighted_prevalence": float(top["weighted_prevalence"]),
                "baseline_weighted_prevalence": float(top["baseline_weighted_prevalence"]),
                "top_prevalence_ratio": float(top["prevalence_ratio"]),
                "top_risk_difference": float(top["risk_difference"]),
                "top_group_share": float(top["group_share"]),
                "min_n_rule": int(min_n),
            }
        )
    return pd.DataFrame(rows)


def minimal_feature_matrix(df: pd.DataFrame) -> np.ndarray:
    out = pd.DataFrame(
        {
            "age_analysis": pd.to_numeric(df["age_analysis"], errors="coerce"),
            "parity": pd.to_numeric(df["parity"], errors="coerce").clip(lower=0, upper=6),
            "has_pregnancy_record": pd.to_numeric(df["has_pregnancy_record"], errors="coerce").fillna(0),
        }
    )
    return out.fillna(out.loc[df["cycle"].isin(TRAIN_CYCLES), :].median()).to_numpy(float)


def supervised_raw_feature_comparison(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    assignments: pd.DataFrame,
    embeddings: pd.DataFrame,
    features: list[str],
) -> pd.DataFrame:
    cfg = Config()
    values, _, _, _ = numeric_matrix(df, features, df["cycle"].isin(TRAIN_CYCLES))
    emb_cols = [c for c in embeddings.columns if c.startswith("ssl_")]
    ssl = embeddings[emb_cols].to_numpy(float)
    pheno = pd.get_dummies(assignments["phenotype"].astype(int), prefix="P").to_numpy(float)
    minimal = minimal_feature_matrix(df)
    feature_sets = {
        "Age + parity + ever-pregnant": minimal,
        "Raw 48 encoder inputs": values,
        "SSL embedding": ssl,
        "Raw 48 + SSL": np.hstack([values, ssl]),
        "Phenotype only": pheno,
        "SSL + phenotype": np.hstack([ssl, pheno]),
    }
    cycles = df["cycle"]
    rows: list[dict[str, object]] = []

    for analysis_set in ["full analytic cohort", "ever-pregnant stratum"]:
        base_train = cycles.isin(TRAIN_CYCLES + [DEV_CYCLE]).to_numpy()
        base_test = cycles.eq(TEST_CYCLE).to_numpy()
        if analysis_set == "ever-pregnant stratum":
            ever = pd.to_numeric(df["has_pregnancy_record"], errors="coerce").fillna(0).eq(1).to_numpy()
            base_train = base_train & ever
            base_test = base_test & ever

        for endpoint in ENDPOINTS:
            if analysis_set == "ever-pregnant stratum" and endpoint not in PREGNANCY_HISTORY_ENDPOINTS:
                continue
            y = endpoints[endpoint].to_numpy(dtype=int)
            if y[base_test].sum() < 10 or len(np.unique(y[base_train])) < 2:
                continue
            baseline = float(y[base_test].mean())
            for name, x in feature_sets.items():
                try:
                    scaler = StandardScaler()
                    xtr = scaler.fit_transform(x[base_train])
                    xte = scaler.transform(x[base_test])
                    clf = LogisticRegression(
                        max_iter=3000,
                        penalty="l2",
                        C=0.5,
                        class_weight="balanced",
                        random_state=cfg.seed,
                    )
                    clf.fit(xtr, y[base_train])
                    prob = clf.predict_proba(xte)[:, 1]
                    auprc = float(average_precision_score(y[base_test], prob))
                    auroc = float(roc_auc_score(y[base_test], prob))
                except Exception:
                    auprc = float("nan")
                    auroc = float("nan")
                rows.append(
                    {
                        "analysis_set": analysis_set,
                        "endpoint": endpoint,
                        "feature_set": name,
                        "train_events": int(y[base_train].sum()),
                        "train_n": int(base_train.sum()),
                        "test_events": int(y[base_test].sum()),
                        "test_n": int(base_test.sum()),
                        "baseline_prevalence": baseline,
                        "auprc": auprc,
                        "auprc_enrichment": auprc / baseline if baseline > 0 and np.isfinite(auprc) else np.nan,
                        "auroc": auroc,
                    }
                )
    out = pd.DataFrame(rows)
    out["delta_auprc_vs_minimal"] = np.nan
    out["delta_auprc_vs_raw48"] = np.nan
    for (analysis_set, endpoint), sub in out.groupby(["analysis_set", "endpoint"]):
        minimal_ap = sub.loc[sub["feature_set"].eq("Age + parity + ever-pregnant"), "auprc"]
        raw_ap = sub.loc[sub["feature_set"].eq("Raw 48 encoder inputs"), "auprc"]
        minimal_value = float(minimal_ap.iloc[0]) if len(minimal_ap) else math.nan
        raw_value = float(raw_ap.iloc[0]) if len(raw_ap) else math.nan
        idx = (out["analysis_set"].eq(analysis_set)) & (out["endpoint"].eq(endpoint))
        out.loc[idx, "delta_auprc_vs_minimal"] = out.loc[idx, "auprc"] - minimal_value
        out.loc[idx, "delta_auprc_vs_raw48"] = out.loc[idx, "auprc"] - raw_value
    return out


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    df, endpoints, assignments, embeddings, features = load_core()
    frame = test_frame(df, endpoints, assignments)

    pieces = [
        group_enrichment(frame, "phenotype_group", "SSL phenotype", "full analytic cohort"),
        group_enrichment(frame, "age_parity_group", "Age x parity strata", "full analytic cohort"),
        group_enrichment(frame, "age_ever_pregnant_group", "Age x ever-pregnant strata", "full analytic cohort"),
        group_enrichment(frame, "phenotype_group", "SSL phenotype", "ever-pregnant stratum"),
        group_enrichment(frame, "age_parity_group", "Age x parity strata", "ever-pregnant stratum"),
    ]
    group_stats = pd.concat(pieces, ignore_index=True)
    group_stats.to_csv(TABLES / "supplementary_trivial_stratification_baseline.csv", index=False)
    summary = summarize_group_baselines(group_stats)
    summary.to_csv(TABLES / "supplementary_trivial_baseline_summary.csv", index=False)

    supervised = supervised_raw_feature_comparison(df, endpoints, assignments, embeddings, features)
    supervised.to_csv(TABLES / "supplementary_supervised_raw_feature_comparison.csv", index=False)

    print("Wrote reviewer-requested baselines:")
    print(summary.to_string(index=False))
    print(supervised.to_string(index=False))


if __name__ == "__main__":
    main()
