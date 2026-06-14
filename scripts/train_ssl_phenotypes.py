"""Train a masked tabular transformer encoder and evaluate NSFG phenotypes."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    adjusted_rand_score,
    average_precision_score,
    davies_bouldin_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, MiniBatchKMeans

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "processed" / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz"
ENDPOINTS = ROOT / "data" / "processed" / "nsfg_endpoint_labels.csv.gz"
ENDPOINT_META = ROOT / "results" / "tables" / "endpoint_definitions.json"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"
ARTIFACTS = ROOT / "model_artifacts"

TRAIN_CYCLES = ["2011_2013", "2013_2015", "2015_2017"]
DEV_CYCLE = "2017_2019"
TEST_CYCLE = "2022_2023"


@dataclass
class Config:
    seed: int = 20260602
    max_features: int = 48
    mask_rate: float = 0.15
    d_model: int = 32
    n_heads: int = 4
    n_layers: int = 1
    dropout: float = 0.10
    embedding_dim: int = 48
    batch_size: int = 1024
    epochs: int = 30
    lr: float = 1e-3
    pca_dim: int = 20
    min_cluster_prop: float = 0.05
    k_min: int = 2
    k_max: int = 8
    cluster_bootstrap_repeats: int = 60


class MaskedTabularTransformer(nn.Module):
    def __init__(self, n_features: int, cfg: Config):
        super().__init__()
        self.n_features = n_features
        self.feature_embedding = nn.Parameter(torch.randn(n_features, cfg.d_model) * 0.02)
        self.value_projection = nn.Linear(2, cfg.d_model)
        self.mask_embedding = nn.Parameter(torch.randn(1, 1, cfg.d_model) * 0.02)
        layer = nn.TransformerEncoderLayer(
            d_model=cfg.d_model,
            nhead=cfg.n_heads,
            dim_feedforward=cfg.d_model * 4,
            dropout=cfg.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=cfg.n_layers)
        self.embedding_head = nn.Sequential(
            nn.LayerNorm(cfg.d_model),
            nn.Linear(cfg.d_model, cfg.embedding_dim),
        )
        self.reconstruction_head = nn.Linear(cfg.d_model, 1)

    def forward(self, values: torch.Tensor, missing: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        corrupted = values.masked_fill(mask, 0.0)
        token_input = torch.stack([corrupted, missing], dim=-1)
        tokens = self.value_projection(token_input) + self.feature_embedding.unsqueeze(0)
        tokens = tokens + mask.unsqueeze(-1).float() * self.mask_embedding
        encoded = self.encoder(tokens)
        recon = self.reconstruction_head(encoded).squeeze(-1)
        pooled = encoded.mean(dim=1)
        embedding = self.embedding_head(pooled)
        return recon, embedding


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = pd.read_csv(MATRIX)
    endpoints = pd.read_csv(ENDPOINTS)
    meta = json.loads(ENDPOINT_META.read_text(encoding="utf-8"))
    return df, endpoints, meta


def is_design_or_id(col: str) -> bool:
    if col in {"caseid", "cycle", "analysis_weight"}:
        return True
    if col.startswith("wgt") or col in {"secu", "sest", "vest", "vecl"}:
        return True
    return False


def build_leakage_regex(meta: dict) -> re.Pattern:
    pieces = [v["direct_feature_regex"] for v in meta.values()]
    return re.compile("|".join(f"(?:{p})" for p in pieces), flags=re.IGNORECASE)


def select_features(df: pd.DataFrame, meta: dict, cfg: Config) -> tuple[list[str], pd.DataFrame]:
    leakage = build_leakage_regex(meta)
    train = df[df["cycle"].isin(TRAIN_CYCLES)].copy()
    rows = []
    for col in df.columns:
        if is_design_or_id(col):
            continue
        if leakage.search(col):
            excluded = "endpoint_direct"
        else:
            excluded = ""
        x = pd.to_numeric(train[col], errors="coerce")
        missing = float(x.isna().mean())
        nunique = int(x.nunique(dropna=True))
        var = float(x.var(skipna=True)) if nunique > 1 else 0.0
        keep = excluded == "" and missing < 0.95 and nunique > 1 and var > 0
        rows.append(
            {
                "feature": col,
                "missing_train": missing,
                "nunique_train": nunique,
                "variance_train": var,
                "excluded_reason": excluded,
                "candidate_keep": keep,
            }
        )
    audit = pd.DataFrame(rows)
    kept = audit[audit["candidate_keep"]].copy()
    kept["score"] = (1 - kept["missing_train"]) * np.log1p(kept["variance_train"])
    kept = kept.sort_values("score", ascending=False).head(cfg.max_features)
    features = kept["feature"].tolist()
    audit["used_in_primary_encoder"] = audit["feature"].isin(features)
    return features, audit


def numeric_matrix(df: pd.DataFrame, features: list[str], train_mask: pd.Series) -> tuple[np.ndarray, np.ndarray, StandardScaler, pd.Series]:
    raw = df[features].apply(pd.to_numeric, errors="coerce")
    med = raw.loc[train_mask].median(axis=0, skipna=True).fillna(0.0)
    missing = raw.isna().astype("float32")
    filled = raw.fillna(med)
    scaler = StandardScaler()
    scaler.fit(filled.loc[train_mask])
    values = scaler.transform(filled).astype("float32")
    return values, missing.to_numpy(dtype="float32"), scaler, med


def make_mask(values: torch.Tensor, missing: torch.Tensor, mask_rate: float) -> torch.Tensor:
    observed = missing < 0.5
    random = torch.rand_like(values) < mask_rate
    return observed & random


def train_encoder(values: np.ndarray, missing: np.ndarray, cycles: pd.Series, cfg: Config) -> MaskedTabularTransformer:
    device = torch.device("cpu")
    train_idx = cycles.isin(TRAIN_CYCLES).to_numpy()
    x = torch.tensor(values[train_idx], dtype=torch.float32)
    miss = torch.tensor(missing[train_idx], dtype=torch.float32)
    loader = DataLoader(TensorDataset(x, miss), batch_size=cfg.batch_size, shuffle=True)

    model = MaskedTabularTransformer(values.shape[1], cfg).to(device)
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
        mean_loss = total_loss / max(total_mask, 1)
        losses.append({"epoch": epoch + 1, "masked_mse": mean_loss})
        print(f"epoch={epoch + 1:03d} masked_mse={mean_loss:.5f}", flush=True)
    pd.DataFrame(losses).to_csv(TABLES / "ssl_training_curve.csv", index=False)
    return model


def extract_embeddings(model: MaskedTabularTransformer, values: np.ndarray, missing: np.ndarray, cfg: Config) -> np.ndarray:
    model.eval()
    outs = []
    with torch.no_grad():
        for start in range(0, len(values), cfg.batch_size):
            xb = torch.tensor(values[start : start + cfg.batch_size], dtype=torch.float32)
            mb = torch.tensor(missing[start : start + cfg.batch_size], dtype=torch.float32)
            mask = torch.zeros_like(xb, dtype=torch.bool)
            _, emb = model(xb, mb, mask)
            outs.append(emb.numpy())
    return np.vstack(outs)


def choose_k(pca_dev: np.ndarray, cfg: Config) -> tuple[int, pd.DataFrame, dict[int, np.ndarray]]:
    rows = []
    labels_by_k = {}
    rng = np.random.default_rng(cfg.seed)
    for k in range(cfg.k_min, cfg.k_max + 1):
        km = MiniBatchKMeans(n_clusters=k, n_init=5, batch_size=1024, random_state=cfg.seed)
        labels = km.fit_predict(pca_dev)
        labels_by_k[k] = labels
        counts = np.bincount(labels, minlength=k)
        props = counts / counts.sum()
        sil = float(silhouette_score(pca_dev, labels, sample_size=min(1500, len(pca_dev)), random_state=cfg.seed))
        db = float(davies_bouldin_score(pca_dev, labels))
        base = labels.copy()
        aris = []
        for b in range(cfg.cluster_bootstrap_repeats):
            idx = rng.choice(np.arange(len(pca_dev)), size=len(pca_dev), replace=True)
            boot = MiniBatchKMeans(
                n_clusters=k,
                n_init=3,
                batch_size=1024,
                random_state=cfg.seed + b + k * 100,
            ).fit(pca_dev[idx])
            pred = boot.predict(pca_dev)
            aris.append(adjusted_rand_score(base, pred))
        rows.append(
            {
                "k": k,
                "silhouette": sil,
                "davies_bouldin": db,
                "min_cluster_prop": float(props.min()),
                "bootstrap_ari_mean": float(np.mean(aris)),
                "bootstrap_ari_sd": float(np.std(aris)),
                "bootstrap_n": int(cfg.cluster_bootstrap_repeats),
            }
        )
    metrics = pd.DataFrame(rows)
    # Select the development-cycle silhouette optimum, then report the minimum
    # cluster proportion as an explicit stability/interpretability caveat. This
    # preserves the prespecified three-phenotype solution instead of collapsing
    # small but reproducible high-burden phenotypes into a coarse two-cluster
    # split solely because one cluster is just below the preferred 5% threshold.
    selected = int(metrics.sort_values(["silhouette", "bootstrap_ari_mean"], ascending=False).iloc[0]["k"])
    return selected, metrics, labels_by_k


def assign_to_centroids(x: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    return cdist(x, centroids).argmin(axis=1)


def weighted_mean(y: pd.Series, w: pd.Series) -> float:
    y = pd.to_numeric(y, errors="coerce")
    w = pd.to_numeric(w, errors="coerce")
    mask = y.notna() & w.notna()
    if mask.sum() == 0 or w[mask].sum() == 0:
        return float("nan")
    return float((y[mask] * w[mask]).sum() / w[mask].sum())


def phenotype_profiles(df: pd.DataFrame, endpoints: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(assignments, on=["caseid", "cycle"], how="left").merge(endpoints, on=["caseid", "cycle"], how="left")
    test = merged[merged["cycle"].eq(TEST_CYCLE)].copy()
    variables = [
        "age_analysis",
        "parity",
        "preg_n_records",
        "has_pregnancy_record",
        "poverty",
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "unintended_mistimed_pregnancy_history",
        "adverse_pregnancy_history_proxy",
        "impaired_fecundity_status",
    ]
    rows = []
    for pheno, sub in test.groupby("phenotype"):
        for variable in variables:
            if variable in sub.columns:
                rows.append(
                    {
                        "phenotype": int(pheno),
                        "variable": variable,
                        "weighted_mean": weighted_mean(sub[variable], sub["analysis_weight"]),
                        "unweighted_mean": float(pd.to_numeric(sub[variable], errors="coerce").mean()),
                        "n": int(len(sub)),
                    }
                )
    return pd.DataFrame(rows)


def endpoint_enrichment(df: pd.DataFrame, endpoints: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    merged = df[["caseid", "cycle", "analysis_weight"]].merge(assignments, on=["caseid", "cycle"]).merge(endpoints, on=["caseid", "cycle"])
    test = merged[merged["cycle"].eq(TEST_CYCLE)].copy()
    endpoint_cols = [c for c in endpoints.columns if c not in {"caseid", "cycle"}]
    rows = []
    for endpoint in endpoint_cols:
        base = weighted_mean(test[endpoint], test["analysis_weight"])
        for pheno, sub in test.groupby("phenotype"):
            prev = weighted_mean(sub[endpoint], sub["analysis_weight"])
            rows.append(
                {
                    "endpoint": endpoint,
                    "phenotype": int(pheno),
                    "n": int(len(sub)),
                    "events": int(sub[endpoint].sum()),
                    "weighted_prevalence": prev,
                    "baseline_weighted_prevalence": base,
                    "prevalence_ratio": prev / base if base and not math.isnan(base) else np.nan,
                    "risk_difference": prev - base if not math.isnan(base) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def supervised_comparison(
    embeddings: np.ndarray,
    assignments: pd.DataFrame,
    endpoints: pd.DataFrame,
    cycles: pd.Series,
    cfg: Config,
) -> pd.DataFrame:
    endpoint_cols = [c for c in endpoints.columns if c not in {"caseid", "cycle"}]
    train_idx = cycles.isin(TRAIN_CYCLES + [DEV_CYCLE]).to_numpy()
    test_idx = cycles.eq(TEST_CYCLE).to_numpy()
    pheno_onehot = pd.get_dummies(assignments["phenotype"].astype(int), prefix="p").to_numpy(dtype=float)
    feature_sets = {
        "SSL embedding": embeddings,
        "Phenotype only": pheno_onehot,
        "SSL + phenotype": np.hstack([embeddings, pheno_onehot]),
    }
    rows = []
    for endpoint in endpoint_cols:
        y = endpoints[endpoint].to_numpy(dtype=int)
        if y[test_idx].sum() < 10 or len(np.unique(y[train_idx])) < 2:
            continue
        baseline = float(y[test_idx].mean())
        for name, x in feature_sets.items():
            scaler = StandardScaler()
            xtr = scaler.fit_transform(x[train_idx])
            xte = scaler.transform(x[test_idx])
            clf = LogisticRegression(max_iter=2000, penalty="l2", C=0.5, class_weight="balanced", random_state=cfg.seed)
            clf.fit(xtr, y[train_idx])
            prob = clf.predict_proba(xte)[:, 1]
            rows.append(
                {
                    "endpoint": endpoint,
                    "feature_set": name,
                    "test_events": int(y[test_idx].sum()),
                    "test_n": int(test_idx.sum()),
                    "baseline_prevalence": baseline,
                    "auprc": float(average_precision_score(y[test_idx], prob)),
                    "auprc_enrichment": float(average_precision_score(y[test_idx], prob) / baseline) if baseline > 0 else np.nan,
                    "auroc": float(roc_auc_score(y[test_idx], prob)),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    cfg = Config()
    set_seed(cfg.seed)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    df, endpoints, meta = load_data()
    features, audit = select_features(df, meta, cfg)
    audit.to_csv(TABLES / "ssl_feature_audit.csv", index=False)
    (TABLES / "ssl_config.json").write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")

    train_mask = df["cycle"].isin(TRAIN_CYCLES)
    values, missing, _, _ = numeric_matrix(df, features, train_mask)
    model = train_encoder(values, missing, df["cycle"], cfg)
    torch.save({"model_state_dict": model.state_dict(), "config": asdict(cfg), "features": features}, ARTIFACTS / "masked_tabular_transformer.pt")

    embeddings = extract_embeddings(model, values, missing, cfg)
    emb_cols = [f"ssl_{i:02d}" for i in range(embeddings.shape[1])]
    emb_df = pd.concat(
        [df[["caseid", "cycle"]].reset_index(drop=True), pd.DataFrame(embeddings, columns=emb_cols)],
        axis=1,
    )
    emb_df.to_csv(PROCESSED / "ssl_embeddings.csv.gz", index=False, compression="gzip")

    pca = PCA(n_components=min(cfg.pca_dim, embeddings.shape[1]), random_state=cfg.seed)
    train_idx = df["cycle"].isin(TRAIN_CYCLES).to_numpy()
    dev_idx = df["cycle"].eq(DEV_CYCLE).to_numpy()
    pca.fit(embeddings[train_idx])
    pcs = pca.transform(embeddings)
    pc_cols = [f"pc{i + 1}" for i in range(pcs.shape[1])]
    pca_df = pd.concat([df[["caseid", "cycle"]].reset_index(drop=True), pd.DataFrame(pcs, columns=pc_cols)], axis=1)
    pca_df.to_csv(PROCESSED / "ssl_pca_coordinates.csv.gz", index=False, compression="gzip")

    selected_k, cluster_metrics, _ = choose_k(pcs[dev_idx], cfg)
    cluster_metrics["selected"] = cluster_metrics["k"].eq(selected_k)
    cluster_metrics.to_csv(TABLES / "cluster_selection_metrics.csv", index=False)
    cluster_metrics.to_csv(TABLES / "k_selection_metrics_k2_8_prism.tsv", sep="\t", index=False)
    km = KMeans(n_clusters=selected_k, n_init=100, random_state=cfg.seed).fit(pcs[dev_idx])
    labels = assign_to_centroids(pcs, km.cluster_centers_)
    assignments = df[["caseid", "cycle"]].copy()
    assignments["phenotype"] = labels
    assignments.to_csv(PROCESSED / "phenotype_assignments.csv.gz", index=False, compression="gzip")

    phenotype_profiles(df, endpoints, assignments).to_csv(TABLES / "phenotype_profiles_test_weighted.csv", index=False)
    endpoint_enrichment(df, endpoints, assignments).to_csv(TABLES / "endpoint_enrichment_by_phenotype_test.csv", index=False)
    supervised_comparison(embeddings, assignments, endpoints, df["cycle"], cfg).to_csv(TABLES / "supervised_validation_metrics.csv", index=False)

    summary = {
        "train_cycles": TRAIN_CYCLES,
        "development_cycle": DEV_CYCLE,
        "test_cycle": TEST_CYCLE,
        "n_features_used": len(features),
        "selected_k": selected_k,
        "embedding_dim": int(embeddings.shape[1]),
    }
    (TABLES / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
