"""Run reviewer-requested SSL encoder initialization sensitivity checks."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import torch
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from torch.utils.data import DataLoader, TensorDataset

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
    extract_embeddings,
    load_data,
    make_mask,
    numeric_matrix,
    set_seed,
    weighted_mean,
)


SENSITIVITY_SEEDS = [20260602, 20260612]
FIXED_K = 3


def train_local(values: np.ndarray, missing: np.ndarray, cycles: pd.Series, cfg: Config) -> tuple[MaskedTabularTransformer, float]:
    device = torch.device("cpu")
    train_idx = cycles.isin(TRAIN_CYCLES).to_numpy()
    x = torch.tensor(values[train_idx], dtype=torch.float32)
    miss = torch.tensor(missing[train_idx], dtype=torch.float32)
    generator = torch.Generator()
    generator.manual_seed(cfg.seed)
    loader = DataLoader(
        TensorDataset(x, miss),
        batch_size=cfg.batch_size,
        shuffle=True,
        generator=generator,
    )
    model = MaskedTabularTransformer(values.shape[1], cfg).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=1e-4)
    final_loss = math.nan
    for _epoch in range(cfg.epochs):
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
        final_loss = total_loss / max(total_mask, 1)
    return model, float(final_loss)


def masked_loss_snapshot(model: MaskedTabularTransformer, values: np.ndarray, missing: np.ndarray, cycles: pd.Series, cfg: Config) -> float:
    train_idx = cycles.isin(TRAIN_CYCLES).to_numpy()
    rng = torch.Generator()
    rng.manual_seed(cfg.seed + 1000)
    vals = values[train_idx]
    miss = missing[train_idx]
    total_loss = 0.0
    total_mask = 0
    with torch.no_grad():
        for start in range(0, len(vals), cfg.batch_size):
            xb = torch.tensor(vals[start : start + cfg.batch_size], dtype=torch.float32)
            mb = torch.tensor(miss[start : start + cfg.batch_size], dtype=torch.float32)
            observed = mb < 0.5
            mask = observed & (torch.rand(xb.shape, generator=rng) < cfg.mask_rate)
            recon, _ = model(xb, mb, mask)
            if mask.sum() == 0:
                continue
            total_loss += float(((recon[mask] - xb[mask]) ** 2).sum().item())
            total_mask += int(mask.sum())
    return total_loss / max(total_mask, 1)


def endpoint_max_pr(
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    labels: np.ndarray,
    endpoint: str,
    stratum_mask: pd.Series,
) -> float:
    tmp = df[["caseid", "cycle", "analysis_weight"]].copy()
    tmp["phenotype_seed"] = labels
    merged = tmp.merge(endpoints[["caseid", "cycle", endpoint]], on=["caseid", "cycle"], how="left")
    test = merged[df["cycle"].eq(TEST_CYCLE) & stratum_mask].copy()
    base = weighted_mean(test[endpoint], test["analysis_weight"])
    vals = []
    for _pheno, sub in test.groupby("phenotype_seed"):
        prev = weighted_mean(sub[endpoint], sub["analysis_weight"])
        if base and not math.isnan(base):
            vals.append(prev / base)
    return float(max(vals)) if vals else math.nan


def summarize_seed(
    seed: int,
    df: pd.DataFrame,
    endpoints: pd.DataFrame,
    values: np.ndarray,
    missing: np.ndarray,
    primary_labels: np.ndarray,
) -> dict[str, object]:
    cfg = Config(seed=seed)
    set_seed(seed)

    if seed == Config().seed and (PROCESSED / "ssl_embeddings.csv.gz").exists():
        emb_df = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
        embeddings = emb_df.filter(regex=r"^ssl_").to_numpy(dtype=float)
        final_loss = float(pd.read_csv(TABLES / "ssl_training_curve.csv")["masked_mse"].iloc[-1])
    elif (ARTIFACTS / f"masked_tabular_transformer_seed_{seed}.pt").exists():
        checkpoint = torch.load(ARTIFACTS / f"masked_tabular_transformer_seed_{seed}.pt", map_location="cpu", weights_only=False)
        model = MaskedTabularTransformer(values.shape[1], cfg)
        model.load_state_dict(checkpoint["model_state_dict"])
        embeddings = extract_embeddings(model, values, missing, cfg)
        final_loss = masked_loss_snapshot(model, values, missing, df["cycle"], cfg)
    else:
        model, final_loss = train_local(values, missing, df["cycle"], cfg)
        embeddings = extract_embeddings(model, values, missing, cfg)
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "config": cfg.__dict__,
                "note": "encoder seed sensitivity artifact, not primary model",
            },
            ARTIFACTS / f"masked_tabular_transformer_seed_{seed}.pt",
        )

    train_idx = df["cycle"].isin(TRAIN_CYCLES).to_numpy()
    dev_idx = df["cycle"].eq(DEV_CYCLE).to_numpy()
    test_idx = df["cycle"].eq(TEST_CYCLE).to_numpy()
    pca = PCA(n_components=min(cfg.pca_dim, embeddings.shape[1]), random_state=seed)
    pca.fit(embeddings[train_idx])
    pcs = pca.transform(embeddings)
    km = MiniBatchKMeans(n_clusters=FIXED_K, n_init=10, batch_size=1024, random_state=seed).fit(pcs[dev_idx])
    labels = assign_to_centroids(pcs, km.cluster_centers_)
    dev_labels = labels[dev_idx]
    test_props = np.bincount(labels[test_idx], minlength=FIXED_K) / max(test_idx.sum(), 1)
    ever_pregnant = pd.to_numeric(df["has_pregnancy_record"], errors="coerce").fillna(0).gt(0)
    return {
        "seed": seed,
        "epochs": cfg.epochs,
        "fixed_k": FIXED_K,
        "final_masked_mse": final_loss,
        "dev_silhouette": float(silhouette_score(pcs[dev_idx], dev_labels, sample_size=min(600, dev_idx.sum()), random_state=seed)),
        "dev_davies_bouldin": float(davies_bouldin_score(pcs[dev_idx], dev_labels)),
        "dev_min_cluster_prop": float(np.bincount(dev_labels, minlength=FIXED_K).min() / max(dev_idx.sum(), 1)),
        "test_min_cluster_prop": float(test_props.min()),
        "test_ari_vs_primary": float(adjusted_rand_score(primary_labels[test_idx], labels[test_idx])),
        "ever_pregnant_adverse_max_pr": endpoint_max_pr(
            df, endpoints, labels, "adverse_pregnancy_history_proxy", ever_pregnant
        ),
        "ever_pregnant_mistimed_max_pr": endpoint_max_pr(
            df, endpoints, labels, "unintended_mistimed_pregnancy_history", ever_pregnant
        ),
    }


def main() -> None:
    df, endpoints, _meta = load_data()
    audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    features = audit.loc[audit["used_in_primary_encoder"].astype(str).str.lower().eq("true"), "feature"].tolist()
    values, missing, _scaler, _med = numeric_matrix(df, features, df["cycle"].isin(TRAIN_CYCLES))
    primary = pd.read_csv(PROCESSED / "phenotype_assignments.csv.gz")
    primary_labels = primary["phenotype"].to_numpy(dtype=int)
    rows = []
    for seed in SENSITIVITY_SEEDS:
        print(f"running seed {seed}", flush=True)
        rows.append(summarize_seed(seed, df, endpoints, values, missing, primary_labels))
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "supplementary_encoder_seed_sensitivity.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
