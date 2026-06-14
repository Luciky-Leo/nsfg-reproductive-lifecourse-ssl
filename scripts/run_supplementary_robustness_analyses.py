"""Run supplementary robustness analyses for the NSFG SSL phenotype study.

The analyses here are deliberately positioned as sensitivity and robustness
checks. They do not change the primary leakage-controlled temporal validation
analysis, but they add evidence that phenotype enrichment is not solely driven
by age range, simple clustering baselines, direct endpoint leakage, or a single
demographic stratum.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import torch
from scipy.special import expit, logsumexp
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

from build_harmonized_lifecourse_matrix import (
    aggregate_pregnancy,
    age_numeric,
    cycle_analysis_weight,
    read_preg_2223,
    read_resp_2223,
    selected_respondent_columns,
)
from define_endpoints import define as define_endpoints
from train_ssl_phenotypes import (
    ARTIFACTS,
    DEV_CYCLE,
    PROCESSED,
    TABLES,
    TEST_CYCLE,
    TRAIN_CYCLES,
    Config,
    MaskedTabularTransformer,
    assign_to_centroids,
    build_leakage_regex,
    extract_embeddings,
    is_design_or_id,
    numeric_matrix,
    select_features,
    set_seed,
)


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "results" / "figures"
BOOTSTRAPS = 300
STABILITY_BOOTSTRAPS = 60
SEED = 20260607
ENDPOINTS = [
    "contraceptive_vulnerability",
    "fertility_service_or_loss_help",
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
    "impaired_fecundity_status",
]
PALETTE = ["#3E4F94", "#3E90BF", "#A6C0E3", "#D8D3E7", "#FAF9CB"]


def weighted_mean(values: pd.Series | np.ndarray, weights: pd.Series | np.ndarray) -> float:
    y = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    w = pd.to_numeric(pd.Series(weights), errors="coerce").to_numpy(float)
    mask = np.isfinite(y) & np.isfinite(w) & (w > 0)
    if not mask.any():
        return float("nan")
    return float(np.sum(y[mask] * w[mask]) / np.sum(w[mask]))


def ensure_dirs() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)


def load_primary_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    df = pd.read_csv(PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz")
    endpoints = pd.read_csv(PROCESSED / "nsfg_endpoint_labels.csv.gz")
    assignments = pd.read_csv(PROCESSED / "phenotype_assignments.csv.gz")
    embeddings = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
    feature_audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    endpoint_meta = json.loads((TABLES / "endpoint_definitions.json").read_text(encoding="utf-8"))
    return df, endpoints, assignments, embeddings, feature_audit, endpoint_meta


def test_analysis_frame(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    assignments: pd.DataFrame,
) -> pd.DataFrame:
    covars = [
        "caseid",
        "cycle",
        "analysis_weight",
        "age_analysis",
        "hisprace2",
        "hispanic",
        "hieduc",
        "poverty",
        "curr_ins",
        "parity",
    ]
    use_cols = [c for c in covars if c in df.columns]
    out = (
        df.loc[df["cycle"].eq(TEST_CYCLE), use_cols]
        .merge(endpoints.loc[endpoints["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
        .merge(assignments.loc[assignments["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
    )
    design = pd.read_csv(
        PROCESSED / "nsfg_2022_2023_lifecourse_matrix.csv.gz",
        usecols=["CaseID", "WGT2022_2023", "VEST", "VECL"],
    ).rename(columns={"CaseID": "caseid"})
    out = out.merge(design, on="caseid", how="left")
    out["analysis_weight"] = pd.to_numeric(out.get("analysis_weight", out["WGT2022_2023"]), errors="coerce")
    out["phenotype"] = pd.to_numeric(out["phenotype"], errors="coerce").astype("Int64")
    return out


def endpoint_enrichment_table(
    frame: pd.DataFrame,
    label: str,
    weight_col: str = "analysis_weight",
    phenotype_col: str = "phenotype",
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    phenotypes = sorted(pd.to_numeric(frame[phenotype_col], errors="coerce").dropna().astype(int).unique())
    for endpoint in ENDPOINTS:
        base = weighted_mean(frame[endpoint], frame[weight_col])
        for phenotype in phenotypes:
            sub = frame[pd.to_numeric(frame[phenotype_col], errors="coerce").eq(phenotype)]
            prev = weighted_mean(sub[endpoint], sub[weight_col])
            rows.append(
                {
                    "analysis": label,
                    "endpoint": endpoint,
                    "phenotype": int(phenotype),
                    "n": int(len(sub)),
                    "events": int(pd.to_numeric(sub[endpoint], errors="coerce").fillna(0).sum()),
                    "weighted_prevalence": prev,
                    "baseline_weighted_prevalence": base,
                    "prevalence_ratio": prev / base if base and np.isfinite(base) else np.nan,
                    "risk_difference": prev - base if np.isfinite(base) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def build_full_2022_harmonized_matrix() -> pd.DataFrame:
    resp = read_resp_2223()
    preg = read_preg_2223()
    preg_agg = aggregate_pregnancy(preg)
    resp = resp[selected_respondent_columns(resp)].copy()
    matrix = resp.merge(preg_agg, on="caseid", how="left")
    matrix["has_pregnancy_record"] = matrix["preg_n_records"].notna().astype("int8")
    matrix["preg_n_records"] = matrix["preg_n_records"].fillna(0).astype("int64")
    matrix["cycle"] = TEST_CYCLE
    matrix["age_analysis"] = age_numeric(matrix)
    matrix["analysis_weight"] = cycle_analysis_weight(matrix, TEST_CYCLE)
    matrix = matrix[matrix["age_analysis"].between(15, 49, inclusive="both")].copy()
    matrix = matrix.astype(object).where(matrix.notna(), np.nan)
    return matrix.reset_index(drop=True)


def load_trained_encoder_assignment(
    df: pd.DataFrame,
    full_2022: pd.DataFrame,
    embeddings_df: pd.DataFrame,
    assignments: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    artifact = torch.load(ARTIFACTS / "masked_tabular_transformer.pt", map_location="cpu", weights_only=False)
    cfg = Config(**artifact["config"])
    features = list(artifact["features"])
    train_mask = df["cycle"].isin(TRAIN_CYCLES)
    _, _, scaler, med = numeric_matrix(df, features, train_mask)

    aligned = full_2022.copy()
    for feature in features:
        if feature not in aligned.columns:
            aligned[feature] = np.nan
    raw = aligned[features].apply(pd.to_numeric, errors="coerce")
    missing = raw.isna().astype("float32").to_numpy(dtype="float32")
    values = scaler.transform(raw.fillna(med)).astype("float32")

    model = MaskedTabularTransformer(len(features), cfg)
    model.load_state_dict(artifact["model_state_dict"])
    full_embeddings = extract_embeddings(model, values, missing, cfg)

    emb_cols = [c for c in embeddings_df.columns if c.startswith("ssl_")]
    primary_embeddings = embeddings_df[emb_cols].to_numpy(dtype=float)
    train_idx = df["cycle"].isin(TRAIN_CYCLES).to_numpy()
    dev_idx = df["cycle"].eq(DEV_CYCLE).to_numpy()
    pca = PCA(n_components=min(cfg.pca_dim, primary_embeddings.shape[1]), random_state=cfg.seed)
    pca.fit(primary_embeddings[train_idx])
    pcs = pca.transform(primary_embeddings)
    selected_k = int(pd.read_json(TABLES / "analysis_summary.json", typ="series")["selected_k"])
    km = KMeans(n_clusters=selected_k, n_init=100, random_state=cfg.seed).fit(pcs[dev_idx])
    full_pcs = pca.transform(full_embeddings)
    full_labels = assign_to_centroids(full_pcs, km.cluster_centers_)

    full_assignments = full_2022[["caseid", "cycle", "age_analysis"]].copy()
    full_assignments["phenotype"] = full_labels.astype(int)

    existing_test = assignments.loc[assignments["cycle"].eq(TEST_CYCLE), ["caseid", "phenotype"]].copy()
    existing_test["caseid"] = existing_test["caseid"].astype(str)
    reassigned = full_assignments.loc[full_assignments["age_analysis"].le(44), ["caseid", "phenotype"]].copy()
    reassigned["caseid"] = reassigned["caseid"].astype(str)
    qc = reassigned.merge(
        existing_test,
        on="caseid",
        suffixes=("_reassigned", "_primary"),
    )
    ari = adjusted_rand_score(qc["phenotype_primary"], qc["phenotype_reassigned"]) if len(qc) else np.nan
    label_map: dict[int, int] = {}
    if len(qc):
        tab = pd.crosstab(qc["phenotype_reassigned"], qc["phenotype_primary"])
        for reassigned_label, counts in tab.iterrows():
            label_map[int(reassigned_label)] = int(counts.idxmax())
    if label_map:
        full_assignments["phenotype_unaligned"] = full_assignments["phenotype"].astype(int)
        full_assignments["phenotype"] = full_assignments["phenotype_unaligned"].map(label_map).fillna(
            full_assignments["phenotype_unaligned"]
        ).astype(int)
        aligned_qc = full_assignments.loc[
            full_assignments["age_analysis"].le(44), ["caseid", "phenotype"]
        ].copy()
        aligned_qc["caseid"] = aligned_qc["caseid"].astype(str)
        aligned_qc = aligned_qc.merge(existing_test, on="caseid", suffixes=("_aligned", "_primary"))
        exact_agreement = float(
            pd.to_numeric(aligned_qc["phenotype_aligned"], errors="coerce").eq(
                pd.to_numeric(aligned_qc["phenotype_primary"], errors="coerce")
            ).mean()
        )
    else:
        exact_agreement = float("nan")
    qc_table = pd.DataFrame(
        [
            {
                "analysis": "full_2022_embedding_reassignment",
                "n_primary_15_44_matched": int(len(qc)),
                "adjusted_rand_index_vs_primary_assignment": float(ari),
                "exact_label_agreement_after_alignment": exact_agreement,
                "phenotype_label_map_reassigned_to_primary": ";".join(
                    f"{k}->{v}" for k, v in sorted(label_map.items())
                ),
                "note": "Model weights were loaded from the primary endpoint-excluded encoder; scaler, PCA, and development centroids were reconstructed from primary train/development data. Full-age labels were aligned to the primary 15-44 phenotype labels by majority overlap before enrichment summaries.",
            }
        ]
    )
    return full_assignments, qc_table


def run_age_range_sensitivity(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    assignments: pd.DataFrame,
    embeddings_df: pd.DataFrame,
) -> pd.DataFrame:
    full_2022 = build_full_2022_harmonized_matrix()
    full_endpoints = define_endpoints(full_2022)
    full_assignments, qc = load_trained_encoder_assignment(df, full_2022, embeddings_df, assignments)
    full_assignments.to_csv(
        PROCESSED / "supplementary_2022_2023_full_age_phenotype_assignments.csv.gz",
        index=False,
        compression="gzip",
    )
    qc.to_csv(TABLES / "supplementary_age_range_assignment_qc.csv", index=False)

    merged = (
        full_2022[["caseid", "cycle", "age_analysis", "analysis_weight"]]
        .merge(full_endpoints, on=["caseid", "cycle"], how="inner")
        .merge(full_assignments[["caseid", "cycle", "phenotype"]], on=["caseid", "cycle"], how="inner")
    )
    age_frames = []
    for age_label, upper in [("15-44", 44), ("15-49", 49)]:
        sub = merged[merged["age_analysis"].between(15, upper, inclusive="both")].copy()
        age_frames.append(endpoint_enrichment_table(sub, f"2022-2023 age {age_label}"))
    out = pd.concat(age_frames, ignore_index=True)
    out.to_csv(TABLES / "supplementary_age_range_endpoint_enrichment.csv", index=False)
    return out


def draw_stratified_cluster_sample(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for _, stratum in df.groupby("VEST", sort=False):
        clusters = stratum["VECL"].dropna().unique()
        if len(clusters) == 0:
            continue
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        for cluster in sampled:
            pieces.append(stratum[stratum["VECL"].eq(cluster)])
    if not pieces:
        return df.sample(frac=1.0, replace=True, random_state=int(rng.integers(1, 10_000_000)))
    return pd.concat(pieces, ignore_index=True)


def build_covariate_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    cov = pd.DataFrame(index=frame.index)
    cov["intercept"] = 1.0
    cov["age_analysis"] = pd.to_numeric(frame["age_analysis"], errors="coerce")
    cov["poverty"] = pd.to_numeric(frame["poverty"], errors="coerce")
    cov["parity"] = pd.to_numeric(frame["parity"], errors="coerce").clip(lower=0, upper=6)
    for col in ["hisprace2", "hieduc", "curr_ins"]:
        if col in frame.columns:
            cats = frame[col].astype("string").fillna("missing")
            dummies = pd.get_dummies(cats, prefix=col, drop_first=True, dtype=float)
            cov = pd.concat([cov, dummies], axis=1)
    cov = cov.apply(pd.to_numeric, errors="coerce")
    med = cov.median(axis=0, skipna=True).fillna(0.0)
    cov = cov.fillna(med)
    nonconstant = [c for c in cov.columns if c == "intercept" or cov[c].nunique(dropna=True) > 1]
    return cov[nonconstant].astype(float)


def fit_weighted_or(
    frame: pd.DataFrame,
    covariates: pd.DataFrame,
    endpoint: str,
    phenotype: int,
) -> float:
    y = pd.to_numeric(frame[endpoint], errors="coerce").fillna(0).to_numpy(dtype=float)
    if y.sum() < 5 or y.sum() == len(y):
        return float("nan")
    x = covariates.copy()
    x["phenotype_indicator"] = pd.to_numeric(frame["phenotype"], errors="coerce").eq(phenotype).astype(float).to_numpy()
    if x["phenotype_indicator"].sum() == 0 or x["phenotype_indicator"].sum() == len(x):
        return float("nan")
    w = pd.to_numeric(frame["analysis_weight"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
    try:
        model = sm.GLM(y, x, family=sm.families.Binomial(), freq_weights=w)
        result = model.fit(maxiter=100, disp=0)
        coef = float(result.params["phenotype_indicator"])
        return float(math.exp(np.clip(coef, -20, 20)))
    except Exception:
        return float("nan")


def run_adjusted_endpoint_models(frame: pd.DataFrame) -> pd.DataFrame:
    base_cov = build_covariate_matrix(frame)
    phenotypes = sorted(frame["phenotype"].dropna().astype(int).unique())
    rng = np.random.default_rng(SEED)
    rows: list[dict[str, object]] = []
    boot_records: dict[tuple[str, int], list[float]] = {(endpoint, p): [] for endpoint in ENDPOINTS for p in phenotypes}

    for endpoint in ENDPOINTS:
        for phenotype in phenotypes:
            point = fit_weighted_or(frame, base_cov, endpoint, phenotype)
            rows.append({"endpoint": endpoint, "phenotype": phenotype, "adjusted_odds_ratio": point})

    for _ in range(BOOTSTRAPS):
        boot = draw_stratified_cluster_sample(frame, rng)
        boot_cov = build_covariate_matrix(boot).reindex(columns=base_cov.columns, fill_value=0.0)
        for endpoint in ENDPOINTS:
            for phenotype in phenotypes:
                value = fit_weighted_or(boot, boot_cov, endpoint, phenotype)
                if np.isfinite(value):
                    boot_records[(endpoint, phenotype)].append(value)

    ci_rows = []
    for endpoint in ENDPOINTS:
        for phenotype in phenotypes:
            vals = np.asarray(boot_records[(endpoint, phenotype)], dtype=float)
            ci_rows.append(
                {
                    "endpoint": endpoint,
                    "phenotype": phenotype,
                    "bootstrap_n": int(len(vals)),
                    "adjusted_or_ci_low": float(np.nanpercentile(vals, 2.5)) if len(vals) else np.nan,
                    "adjusted_or_ci_high": float(np.nanpercentile(vals, 97.5)) if len(vals) else np.nan,
                    "model": "survey-weighted one-vs-rest logistic enrichment model",
                    "adjustment_covariates": "age, race/ethnicity, education, poverty, insurance, parity",
                    "bootstrap_method": "stratified cluster percentile bootstrap using VEST/VECL",
                }
            )
    out = pd.DataFrame(rows).merge(pd.DataFrame(ci_rows), on=["endpoint", "phenotype"], how="left")
    out.to_csv(TABLES / "supplementary_adjusted_endpoint_enrichment.csv", index=False)
    return out


def preprocess_primary_feature_matrix(
    df: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, np.ndarray, StandardScaler, pd.Series]:
    train_mask = df["cycle"].isin(TRAIN_CYCLES)
    return numeric_matrix(df, features, train_mask)


def fit_pca_kmeans_assignments(
    representation: np.ndarray,
    cycles: pd.Series,
    k: int,
    seed: int,
) -> np.ndarray:
    train_idx = cycles.isin(TRAIN_CYCLES).to_numpy()
    dev_idx = cycles.eq(DEV_CYCLE).to_numpy()
    pca = PCA(n_components=min(20, representation.shape[1]), random_state=seed)
    pca.fit(representation[train_idx])
    pcs = pca.transform(representation)
    km = KMeans(n_clusters=k, n_init=100, random_state=seed).fit(pcs[dev_idx])
    return assign_to_centroids(pcs, km.cluster_centers_)


def stability_ari_for_representation(
    representation: np.ndarray,
    dev_idx: np.ndarray,
    k: int,
    seed: int,
) -> tuple[float, float]:
    dev = representation[dev_idx]
    pca = PCA(n_components=min(20, dev.shape[1]), random_state=seed)
    pcs = pca.fit_transform(dev)
    base = MiniBatchKMeans(n_clusters=k, n_init=10, batch_size=1024, random_state=seed).fit_predict(pcs)
    rng = np.random.default_rng(seed)
    aris = []
    for b in range(STABILITY_BOOTSTRAPS):
        idx = rng.choice(np.arange(len(pcs)), size=len(pcs), replace=True)
        model = MiniBatchKMeans(
            n_clusters=k,
            n_init=5,
            batch_size=1024,
            random_state=seed + b + 1000,
        ).fit(pcs[idx])
        aris.append(adjusted_rand_score(base, model.predict(pcs)))
    return float(np.mean(aris)), float(np.std(aris))


def one_hot_svd_representation(df: pd.DataFrame, features: list[str], n_components: int = 20) -> np.ndarray:
    train = df["cycle"].isin(TRAIN_CYCLES)
    pieces = []
    for feature in features:
        x = pd.to_numeric(df[feature], errors="coerce")
        q = x.loc[train].quantile([0.25, 0.5, 0.75]).dropna().unique()
        if len(q) >= 2:
            bins = [-np.inf, *sorted(q), np.inf]
            cat = pd.cut(x, bins=bins, labels=False, include_lowest=True).astype("float")
        else:
            med = x.loc[train].median()
            cat = x.gt(med).astype("float")
        cat = cat.astype("Int64").astype("string").fillna("missing")
        pieces.append(pd.get_dummies(cat, prefix=feature, dtype=float))
    one_hot = pd.concat(pieces, axis=1)
    svd = TruncatedSVD(n_components=min(n_components, max(2, one_hot.shape[1] - 1)), random_state=SEED)
    svd.fit(one_hot.loc[train])
    return svd.transform(one_hot)


def binary_matrix_for_lca(df: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, list[str]]:
    train = df["cycle"].isin(TRAIN_CYCLES)
    bins = []
    names = []
    for feature in features:
        x = pd.to_numeric(df[feature], errors="coerce")
        if x.loc[train].nunique(dropna=True) <= 1:
            continue
        med = x.loc[train].median(skipna=True)
        if not np.isfinite(med):
            continue
        bins.append(x.gt(med).fillna(False).astype(int).to_numpy())
        names.append(feature)
    if not bins:
        raise RuntimeError("No usable selected variables for LCA-style baseline.")
    return np.vstack(bins).T.astype(float), names


def fit_bernoulli_lca(x_dev: np.ndarray, k: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n, p = x_dev.shape
    init = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(x_dev)
    pi = np.bincount(init, minlength=k).astype(float) + 1.0
    pi = pi / pi.sum()
    theta = np.zeros((k, p), dtype=float)
    for j in range(k):
        sub = x_dev[init == j]
        theta[j] = (sub.sum(axis=0) + 1.0) / (len(sub) + 2.0) if len(sub) else rng.uniform(0.25, 0.75, p)
    theta = np.clip(theta, 1e-4, 1 - 1e-4)
    for _ in range(250):
        logp = np.log(pi)[None, :] + x_dev @ np.log(theta).T + (1 - x_dev) @ np.log(1 - theta).T
        resp = np.exp(logp - logsumexp(logp, axis=1, keepdims=True))
        nk = resp.sum(axis=0) + 1e-9
        pi_new = nk / n
        theta_new = (resp.T @ x_dev + 1.0) / (nk[:, None] + 2.0)
        theta_new = np.clip(theta_new, 1e-4, 1 - 1e-4)
        if np.max(np.abs(theta_new - theta)) < 1e-5:
            pi, theta = pi_new, theta_new
            break
        pi, theta = pi_new, theta_new
    return pi, theta


def predict_bernoulli_lca(x: np.ndarray, pi: np.ndarray, theta: np.ndarray) -> np.ndarray:
    logp = np.log(pi)[None, :] + x @ np.log(theta).T + (1 - x) @ np.log(1 - theta).T
    return np.argmax(logp, axis=1)


def method_summary_from_assignments(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    labels: np.ndarray,
    method: str,
    stability_mean: float,
    stability_sd: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    method_assign = df[["caseid", "cycle"]].copy()
    method_assign["method_phenotype"] = labels.astype(int)
    test = (
        df.loc[df["cycle"].eq(TEST_CYCLE), ["caseid", "cycle", "analysis_weight"]]
        .merge(endpoints.loc[endpoints["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
        .merge(method_assign.loc[method_assign["cycle"].eq(TEST_CYCLE)], on=["caseid", "cycle"], how="inner")
    )
    enrich = endpoint_enrichment_table(test.rename(columns={"method_phenotype": "phenotype"}), method)
    enrich["method"] = method
    counts = test["method_phenotype"].value_counts(normalize=True).sort_index()
    summary_rows = []
    for endpoint, sub in enrich.groupby("endpoint"):
        summary_rows.append(
            {
                "method": method,
                "endpoint": endpoint,
                "test_n": int(len(test)),
                "n_clusters": int(test["method_phenotype"].nunique()),
                "min_cluster_proportion": float(counts.min()),
                "bootstrap_ari_mean": stability_mean,
                "bootstrap_ari_sd": stability_sd,
                "max_prevalence_ratio": float(sub["prevalence_ratio"].max()),
                "max_abs_risk_difference": float(sub["risk_difference"].abs().max()),
            }
        )
    return pd.DataFrame(summary_rows), enrich


def run_baseline_method_comparison(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    assignments: pd.DataFrame,
    embeddings_df: pd.DataFrame,
    feature_audit: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = Config()
    selected_k = int(pd.read_json(TABLES / "analysis_summary.json", typ="series")["selected_k"])
    features = feature_audit.loc[feature_audit["used_in_primary_encoder"].astype(bool), "feature"].tolist()
    dev_idx = df["cycle"].eq(DEV_CYCLE).to_numpy()
    methods_summary = []
    methods_enrich = []

    emb_cols = [c for c in embeddings_df.columns if c.startswith("ssl_")]
    ssl_rep = embeddings_df[emb_cols].to_numpy(dtype=float)
    ssl_stab = stability_ari_for_representation(ssl_rep, dev_idx, selected_k, cfg.seed)
    ssl_labels = assignments["phenotype"].to_numpy(dtype=int)
    summary, enrich = method_summary_from_assignments(df, endpoints, ssl_labels, "SSL embedding + k-means", *ssl_stab)
    methods_summary.append(summary)
    methods_enrich.append(enrich)

    values, _, _, _ = preprocess_primary_feature_matrix(df, features)
    raw_labels = fit_pca_kmeans_assignments(values, df["cycle"], selected_k, cfg.seed + 11)
    raw_stab = stability_ari_for_representation(values, dev_idx, selected_k, cfg.seed + 11)
    summary, enrich = method_summary_from_assignments(df, endpoints, raw_labels, "Raw matrix PCA + k-means", *raw_stab)
    methods_summary.append(summary)
    methods_enrich.append(enrich)

    svd_rep = one_hot_svd_representation(df, features[: min(24, len(features))])
    svd_labels = fit_pca_kmeans_assignments(svd_rep, df["cycle"], selected_k, cfg.seed + 22)
    svd_stab = stability_ari_for_representation(svd_rep, dev_idx, selected_k, cfg.seed + 22)
    summary, enrich = method_summary_from_assignments(df, endpoints, svd_labels, "MCA-style one-hot SVD + k-means", *svd_stab)
    methods_summary.append(summary)
    methods_enrich.append(enrich)

    xbin, lca_features = binary_matrix_for_lca(df, features[: min(16, len(features))])
    pi, theta = fit_bernoulli_lca(xbin[dev_idx], selected_k, cfg.seed + 33)
    lca_labels = predict_bernoulli_lca(xbin, pi, theta)
    lca_stab = stability_ari_for_representation(xbin, dev_idx, selected_k, cfg.seed + 33)
    summary, enrich = method_summary_from_assignments(df, endpoints, lca_labels, "Selected-variable Bernoulli LCA", *lca_stab)
    methods_summary.append(summary)
    methods_enrich.append(enrich)

    summary_out = pd.concat(methods_summary, ignore_index=True)
    enrich_out = pd.concat(methods_enrich, ignore_index=True)
    summary_out.to_csv(TABLES / "supplementary_baseline_phenotype_method_comparison.csv", index=False)
    enrich_out.to_csv(TABLES / "supplementary_baseline_endpoint_enrichment.csv", index=False)
    pd.DataFrame({"lca_input_feature": lca_features}).to_csv(TABLES / "supplementary_lca_input_features.csv", index=False)
    return summary_out, enrich_out


def select_full_domain_features(df: pd.DataFrame, meta: dict, cfg: Config) -> tuple[list[str], pd.DataFrame]:
    leakage = build_leakage_regex(meta)
    train = df[df["cycle"].isin(TRAIN_CYCLES)].copy()
    rows = []
    for col in df.columns:
        if is_design_or_id(col):
            continue
        x = pd.to_numeric(train[col], errors="coerce")
        missing = float(x.isna().mean())
        nunique = int(x.nunique(dropna=True))
        var = float(x.var(skipna=True)) if nunique > 1 else 0.0
        keep = missing < 0.95 and nunique > 1 and var > 0
        rows.append(
            {
                "feature": col,
                "missing_train": missing,
                "nunique_train": nunique,
                "variance_train": var,
                "endpoint_direct_feature": bool(leakage.search(col)),
                "candidate_keep": keep,
            }
        )
    audit = pd.DataFrame(rows)
    kept = audit[audit["candidate_keep"]].copy()
    kept["score"] = (1 - kept["missing_train"]) * np.log1p(kept["variance_train"])
    kept = kept.sort_values("score", ascending=False).head(cfg.max_features)
    features = kept["feature"].tolist()
    audit["used_in_full_domain_encoder"] = audit["feature"].isin(features)
    return features, audit


def make_mask(values: torch.Tensor, missing: torch.Tensor, mask_rate: float) -> torch.Tensor:
    observed = missing < 0.5
    random = torch.rand_like(values) < mask_rate
    return observed & random


def train_encoder_for_sensitivity(
    values: np.ndarray,
    missing: np.ndarray,
    cycles: pd.Series,
    cfg: Config,
    curve_path: Path,
) -> MaskedTabularTransformer:
    train_idx = cycles.isin(TRAIN_CYCLES).to_numpy()
    x = torch.tensor(values[train_idx], dtype=torch.float32)
    miss = torch.tensor(missing[train_idx], dtype=torch.float32)
    loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(x, miss), batch_size=cfg.batch_size, shuffle=True)
    model = MaskedTabularTransformer(values.shape[1], cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=1e-4)
    losses = []
    for epoch in range(cfg.epochs):
        model.train()
        total_loss = 0.0
        total_mask = 0
        for xb, mb in loader:
            mask = make_mask(xb, mb, cfg.mask_rate)
            if mask.sum() == 0:
                continue
            recon, _ = model(xb, mb, mask)
            loss = ((recon[mask] - xb[mask]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += float(loss.item()) * int(mask.sum())
            total_mask += int(mask.sum())
        losses.append({"epoch": epoch + 1, "masked_mse": total_loss / max(total_mask, 1)})
    pd.DataFrame(losses).to_csv(curve_path, index=False)
    return model


def run_leakage_sensitivity(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    assignments: pd.DataFrame,
    endpoint_meta: dict,
) -> pd.DataFrame:
    cfg = Config()
    set_seed(cfg.seed + 404)
    primary_enrich = endpoint_enrichment_table(
        test_analysis_frame(df, endpoints, assignments),
        "endpoint-excluded encoder",
    )
    primary_enrich["encoder"] = "endpoint-excluded"

    features, audit = select_full_domain_features(df, endpoint_meta, cfg)
    audit.to_csv(TABLES / "supplementary_full_domain_ssl_feature_audit.csv", index=False)
    values, missing, _, _ = numeric_matrix(df, features, df["cycle"].isin(TRAIN_CYCLES))
    model = train_encoder_for_sensitivity(
        values,
        missing,
        df["cycle"],
        cfg,
        TABLES / "supplementary_full_domain_ssl_training_curve.csv",
    )
    embeddings = extract_embeddings(model, values, missing, cfg)
    labels = fit_pca_kmeans_assignments(embeddings, df["cycle"], int(pd.read_json(TABLES / "analysis_summary.json", typ="series")["selected_k"]), cfg.seed + 404)
    full_assign = df[["caseid", "cycle"]].copy()
    full_assign["phenotype"] = labels.astype(int)
    full_assign.to_csv(PROCESSED / "supplementary_full_domain_phenotype_assignments.csv.gz", index=False, compression="gzip")
    full_enrich = endpoint_enrichment_table(
        test_analysis_frame(df, endpoints, full_assign),
        "full-domain encoder",
    )
    full_enrich["encoder"] = "full-domain"
    out = pd.concat([primary_enrich, full_enrich], ignore_index=True)
    out.to_csv(TABLES / "supplementary_leakage_sensitivity.csv", index=False)
    return out


def subgroup_values(frame: pd.DataFrame) -> dict[str, pd.Series]:
    age = pd.cut(
        pd.to_numeric(frame["age_analysis"], errors="coerce"),
        bins=[14, 24, 34, 44],
        labels=["15-24", "25-34", "35-44"],
        include_lowest=True,
    ).astype("string")
    poverty = pd.cut(
        pd.to_numeric(frame["poverty"], errors="coerce"),
        bins=[-np.inf, 99, 199, np.inf],
        labels=["<100% FPL", "100-199% FPL", ">=200% FPL"],
    ).astype("string")
    parity_num = pd.to_numeric(frame["parity"], errors="coerce")
    parity = pd.Series(np.select([parity_num.eq(0), parity_num.between(1, 2), parity_num.ge(3)], ["0", "1-2", ">=3"], default="missing"), index=frame.index)
    out = {
        "age_group": age,
        "race_ethnicity": frame["hisprace2"].astype("string") if "hisprace2" in frame.columns else frame["hispanic"].astype("string"),
        "poverty_group": poverty,
        "insurance": frame["curr_ins"].astype("string"),
        "parity_group": parity.astype("string"),
    }
    return out


def run_subgroup_robustness(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    prevalence_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, object]] = []
    for subgroup_name, groups in subgroup_values(frame).items():
        tmp = frame.copy()
        tmp["subgroup"] = groups.fillna("missing")
        for subgroup_value, sub in tmp.groupby("subgroup", dropna=False):
            if len(sub) < 50:
                continue
            for phenotype, ph_sub in sub.groupby("phenotype"):
                prevalence_rows.append(
                    {
                        "subgroup_type": subgroup_name,
                        "subgroup": str(subgroup_value),
                        "phenotype": int(phenotype),
                        "n": int(len(ph_sub)),
                        "weighted_phenotype_prevalence": weighted_mean(
                            sub["phenotype"].eq(phenotype).astype(int),
                            sub["analysis_weight"],
                        ),
                    }
                )
            enrichment = endpoint_enrichment_table(sub, f"{subgroup_name}: {subgroup_value}")
            enrichment["subgroup_type"] = subgroup_name
            enrichment["subgroup"] = str(subgroup_value)
            enrichment_rows.extend(enrichment.to_dict("records"))
    prevalence = pd.DataFrame(prevalence_rows)
    enrichment = pd.DataFrame(enrichment_rows)
    prevalence.to_csv(TABLES / "supplementary_subgroup_phenotype_prevalence.csv", index=False)
    enrichment.to_csv(TABLES / "supplementary_subgroup_endpoint_enrichment.csv", index=False)
    return prevalence, enrichment


def plot_age_and_adjusted(age_sens: pd.DataFrame, adjusted: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.55), constrained_layout=True)
    ax = axes[0]
    ax.text(-0.18, 1.06, "A", transform=ax.transAxes, ha="left", va="top", fontsize=10, fontweight="bold")
    top_1544 = (
        age_sens[age_sens["analysis"].str.contains("15-44")]
        .sort_values("prevalence_ratio", ascending=False)
        .groupby("endpoint", as_index=False)
        .first()[["endpoint", "phenotype"]]
    )
    plot_rows = age_sens.merge(top_1544, on=["endpoint", "phenotype"], how="inner")
    pivot = plot_rows.pivot_table(index="endpoint", columns="analysis", values="prevalence_ratio", aggfunc="first")
    y = np.arange(len(pivot))
    for i, endpoint in enumerate(pivot.index):
        vals = pivot.loc[endpoint].dropna()
        if len(vals) == 2:
            ax.plot(vals.to_numpy(), [i, i], color="#A6C0E3", lw=2)
        for j, (label, value) in enumerate(vals.items()):
            color = "#3E4F94" if "15-44" in label else "#3E90BF"
            ax.scatter(value, i, s=42, color=color, zorder=3, label=label if i == 0 else None)
    ax.axvline(1, color="#999999", lw=0.8, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels([e.replace("_", "\n") for e in pivot.index], fontsize=8)
    ax.set_xlabel("Highest phenotype prevalence ratio")
    ax.set_title("Age-range sensitivity")
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.54, -0.16), ncol=1)

    ax = axes[1]
    ax.text(-0.18, 1.06, "B", transform=ax.transAxes, ha="left", va="top", fontsize=10, fontweight="bold")
    adj_plot = adjusted.copy()
    adj_plot["endpoint_label"] = adj_plot["endpoint"].str.replace("_", "\n")
    adj_plot = adj_plot.sort_values(["endpoint", "phenotype"])
    y = np.arange(len(adj_plot))
    ax.errorbar(
        adj_plot["adjusted_odds_ratio"],
        y,
        xerr=[
            adj_plot["adjusted_odds_ratio"] - adj_plot["adjusted_or_ci_low"],
            adj_plot["adjusted_or_ci_high"] - adj_plot["adjusted_odds_ratio"],
        ],
        fmt="o",
        color="#3E4F94",
        ecolor="#A6C0E3",
        elinewidth=1.1,
        capsize=2,
        markersize=3.5,
    )
    ax.axvline(1, color="#999999", lw=0.8, ls="--")
    labels = [f"{e.replace('_', ' ')} | P{p}" for e, p in zip(adj_plot["endpoint"], adj_plot["phenotype"])]
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.8)
    ax.set_xscale("log")
    ax.set_xlabel("Adjusted odds ratio")
    ax.set_title("Covariate-adjusted enrichment")
    for axis in axes:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    for ext in ["png", "pdf"]:
        fig.savefig(FIGURES / f"supplementary_robustness_age_adjusted.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_method_and_leakage(method_summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), constrained_layout=True)
    ax = axes[0]
    ax.text(-0.16, 1.06, "A", transform=ax.transAxes, ha="left", va="top", fontsize=10, fontweight="bold")
    plot = method_summary.groupby("method", as_index=False).agg(
        max_pr=("max_prevalence_ratio", "mean"),
        ari=("bootstrap_ari_mean", "mean"),
        min_cluster=("min_cluster_proportion", "mean"),
    )
    x = np.arange(len(plot))
    ax.bar(x - 0.22, plot["max_pr"], width=0.22, color="#3E4F94", label="Mean max PR")
    ax.bar(x, plot["ari"], width=0.22, color="#3E90BF", label="ARI")
    ax.bar(x + 0.22, plot["min_cluster"], width=0.22, color="#A6C0E3", label="Min cluster")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["method"], rotation=30, ha="right", fontsize=7)
    ax.set_title("Phenotyping baseline comparison")
    ax.set_ylabel("Metric value")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    ax.text(-0.16, 1.06, "B", transform=ax.transAxes, ha="left", va="top", fontsize=10, fontweight="bold")
    leak = leakage.groupby(["encoder", "endpoint"], as_index=False)["prevalence_ratio"].max()
    order = ENDPOINTS
    width = 0.36
    for i, enc in enumerate(["endpoint-excluded", "full-domain"]):
        vals = leak[leak["encoder"].eq(enc)].set_index("endpoint").reindex(order)["prevalence_ratio"]
        ax.bar(np.arange(len(order)) + (i - 0.5) * width, vals, width=width, color=PALETTE[i], label=enc)
    ax.axhline(1, color="#999999", lw=0.8, ls="--")
    ax.set_xticks(np.arange(len(order)))
    ax.set_xticklabels([e.replace("_", "\n") for e in order], fontsize=7)
    ax.set_title("Endpoint-excluded vs full-domain encoder")
    ax.set_ylabel("Maximum phenotype PR")
    ax.legend(frameon=False, fontsize=8)
    for axis in axes:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    for ext in ["png", "pdf"]:
        fig.savefig(FIGURES / f"supplementary_method_leakage_sensitivity.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_subgroup_heatmap(subgroup_enrichment: pd.DataFrame) -> None:
    # Compact display: use the mean maximum PR across endpoints per subgroup.
    if subgroup_enrichment.empty:
        return
    compact = (
        subgroup_enrichment.groupby(["subgroup_type", "subgroup", "endpoint"], as_index=False)["prevalence_ratio"]
        .max()
        .groupby(["subgroup_type", "subgroup"], as_index=False)["prevalence_ratio"]
        .mean()
    )
    compact["label"] = compact["subgroup_type"] + ": " + compact["subgroup"].astype(str)
    compact = compact.sort_values("prevalence_ratio", ascending=False).head(25)
    fig, ax = plt.subplots(figsize=(6.8, 5.4), constrained_layout=True)
    ax.barh(np.arange(len(compact)), compact["prevalence_ratio"], color="#3E90BF")
    ax.axvline(1, color="#999999", lw=0.8, ls="--")
    ax.set_yticks(np.arange(len(compact)))
    ax.set_yticklabels(compact["label"], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Mean maximum endpoint PR")
    ax.set_title("Subgroup robustness summary")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for ext in ["png", "pdf"]:
        fig.savefig(FIGURES / f"supplementary_subgroup_robustness.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    set_seed(SEED)
    df, endpoints, assignments, embeddings, feature_audit, endpoint_meta = load_primary_inputs()
    frame = test_analysis_frame(df, endpoints, assignments)

    print("Running age-range sensitivity...")
    age_sens = run_age_range_sensitivity(df, endpoints, assignments, embeddings)

    print("Running adjusted endpoint enrichment models...")
    adjusted = run_adjusted_endpoint_models(frame)

    print("Running baseline phenotype method comparison...")
    method_summary, _ = run_baseline_method_comparison(df, endpoints, assignments, embeddings, feature_audit)

    print("Running leakage sensitivity...")
    leakage = run_leakage_sensitivity(df, endpoints, assignments, endpoint_meta)

    print("Running subgroup robustness...")
    _, subgroup_enrichment = run_subgroup_robustness(frame)

    print("Rendering supplementary robustness figures...")
    plot_age_and_adjusted(age_sens, adjusted)
    plot_method_and_leakage(method_summary, leakage)
    plot_subgroup_heatmap(subgroup_enrichment)

    manifest = pd.DataFrame(
        [
            {
                "output": "supplementary_age_range_endpoint_enrichment.csv",
                "purpose": "Compares 2022-2023 phenotype endpoint enrichment in 15-44 versus 15-49 respondents.",
            },
            {
                "output": "supplementary_adjusted_endpoint_enrichment.csv",
                "purpose": "Survey-weighted, cluster-bootstrap logistic enrichment models adjusted for age, race/ethnicity, education, poverty, insurance, and parity.",
            },
            {
                "output": "supplementary_baseline_phenotype_method_comparison.csv",
                "purpose": "Compares SSL phenotypes against raw PCA, MCA-style SVD, and selected-variable Bernoulli LCA baselines.",
            },
            {
                "output": "supplementary_leakage_sensitivity.csv",
                "purpose": "Compares primary endpoint-excluded encoder enrichment against full-domain encoder sensitivity.",
            },
            {
                "output": "supplementary_subgroup_endpoint_enrichment.csv",
                "purpose": "Checks phenotype endpoint enrichment across age, race/ethnicity, poverty, insurance, and parity strata.",
            },
        ]
    )
    manifest.to_csv(TABLES / "supplementary_robustness_manifest.csv", index=False)
    print("Done.")


if __name__ == "__main__":
    main()
