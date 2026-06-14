"""Run clustering and endpoint validation from saved SSL embeddings."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.cluster import MiniBatchKMeans

from train_ssl_phenotypes import (
    DEV_CYCLE,
    TEST_CYCLE,
    TRAIN_CYCLES,
    Config,
    TABLES,
    PROCESSED,
    MATRIX,
    ENDPOINTS,
    assign_to_centroids,
    choose_k,
    endpoint_enrichment,
    phenotype_profiles,
    supervised_comparison,
)


def main() -> None:
    cfg = Config()
    df = pd.read_csv(MATRIX)
    endpoints = pd.read_csv(ENDPOINTS)
    emb_df = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
    pca_df = pd.read_csv(PROCESSED / "ssl_pca_coordinates.csv.gz")
    feature_audit_path = TABLES / "ssl_feature_audit.csv"
    emb_cols = [c for c in emb_df.columns if c.startswith("ssl_")]
    pc_cols = [c for c in pca_df.columns if c.startswith("pc")]
    n_features_used = None
    if feature_audit_path.exists():
        feature_audit = pd.read_csv(feature_audit_path)
        if "used_in_primary_encoder" in feature_audit.columns:
            n_features_used = int(feature_audit["used_in_primary_encoder"].astype(str).str.lower().eq("true").sum())
    embeddings = emb_df[emb_cols].to_numpy()
    pcs = pca_df[pc_cols].to_numpy()
    dev_idx = df["cycle"].eq(DEV_CYCLE).to_numpy()

    selected_k, cluster_metrics, _ = choose_k(pcs[dev_idx], cfg)
    cluster_metrics["selected"] = cluster_metrics["k"].eq(selected_k)
    cluster_metrics.to_csv(TABLES / "cluster_selection_metrics.csv", index=False)
    cluster_metrics.to_csv(TABLES / "k_selection_metrics_k2_8_prism.tsv", sep="\t", index=False)
    km = MiniBatchKMeans(n_clusters=selected_k, n_init=10, batch_size=1024, random_state=cfg.seed).fit(pcs[dev_idx])
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
        "n_features_used": n_features_used,
        "selected_k": int(selected_k),
        "embedding_dim": int(embeddings.shape[1]),
        "pca_dim": int(len(pc_cols)),
    }
    (TABLES / "analysis_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
