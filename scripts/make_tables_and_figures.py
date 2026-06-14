"""Create manuscript-ready first-pass figures and source tables."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "processed" / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz"
ENDPOINTS = ROOT / "data" / "processed" / "nsfg_endpoint_labels.csv.gz"
ASSIGNMENTS = ROOT / "data" / "processed" / "phenotype_assignments.csv.gz"
PCA = ROOT / "data" / "processed" / "ssl_pca_coordinates.csv.gz"
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"
MANUSCRIPT_TABLES = ROOT / "manuscript" / "tables"

PALETTE = ["#3B6FB6", "#E6862E", "#4E9B50", "#8D6AB8"]


def weighted_mean(y: pd.Series, w: pd.Series) -> float:
    y = pd.to_numeric(y, errors="coerce")
    w = pd.to_numeric(w, errors="coerce")
    mask = y.notna() & w.notna()
    if mask.sum() == 0 or w[mask].sum() == 0:
        return np.nan
    return float((y[mask] * w[mask]).sum() / w[mask].sum())


def weighted_sd(y: pd.Series, w: pd.Series) -> float:
    y = pd.to_numeric(y, errors="coerce")
    w = pd.to_numeric(w, errors="coerce")
    mask = y.notna() & w.notna() & w.gt(0)
    if mask.sum() <= 1 or w[mask].sum() == 0:
        return np.nan
    mean = weighted_mean(y[mask], w[mask])
    var = ((w[mask] * (y[mask] - mean) ** 2).sum() / w[mask].sum())
    return float(np.sqrt(var))


def load_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(MATRIX)
    endpoints = pd.read_csv(ENDPOINTS)
    assignments = pd.read_csv(ASSIGNMENTS)
    pca = pd.read_csv(PCA)
    return df, endpoints, assignments, pca


def make_table1(df: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(endpoints, on=["caseid", "cycle"], how="left")
    split_map = {
        "2011_2013": "Training/pretraining",
        "2013_2015": "Training/pretraining",
        "2015_2017": "Training/pretraining",
        "2017_2019": "Development/model selection",
        "2022_2023": "Temporal validation",
    }
    merged["analysis_split"] = merged["cycle"].map(split_map)
    endpoint_cols = [c for c in endpoints.columns if c not in {"caseid", "cycle"}]
    rows = []
    for split, sub in merged.groupby("analysis_split", sort=False):
        row = {
            "analysis_split": split,
            "n_respondents": int(len(sub)),
            "weighted_mean_age": weighted_mean(sub["age_analysis"], sub["analysis_weight"]),
            "weighted_sd_age": weighted_sd(sub["age_analysis"], sub["analysis_weight"]),
            "weighted_mean_parity": weighted_mean(sub["parity"], sub["analysis_weight"]) if "parity" in sub else np.nan,
            "weighted_sd_parity": weighted_sd(sub["parity"], sub["analysis_weight"]) if "parity" in sub else np.nan,
            "weighted_pregnancy_record_prevalence": weighted_mean(sub["has_pregnancy_record"], sub["analysis_weight"]),
        }
        for endpoint in endpoint_cols:
            row[f"{endpoint}_weighted_prev"] = weighted_mean(sub[endpoint], sub["analysis_weight"])
        rows.append(row)
    return pd.DataFrame(rows)


def make_table2() -> pd.DataFrame:
    audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    endpoint_defs = pd.read_csv(TABLES / "endpoint_definitions.csv")
    rows = [
        {
            "domain_or_endpoint": "Primary SSL input features",
            "definition": "Endpoint-direct variables excluded; top nonconstant features selected by train-set completeness and variance.",
            "n_features": int(audit["used_in_primary_encoder"].sum()),
            "leakage_control": "Direct endpoint regex excluded before encoder fitting.",
        }
    ]
    for _, row in endpoint_defs.iterrows():
        rows.append(
            {
                "domain_or_endpoint": row["endpoint"],
                "definition": row["positive_definition"],
                "n_features": "Endpoint",
                "leakage_control": row["direct_feature_regex"],
            }
        )
    return pd.DataFrame(rows)


def make_table3() -> pd.DataFrame:
    profile = pd.read_csv(TABLES / "phenotype_profiles_test_weighted.csv")
    return profile.pivot(index="variable", columns="phenotype", values="weighted_mean").reset_index()


def make_table4() -> pd.DataFrame:
    enrich = pd.read_csv(TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    perf = pd.read_csv(TABLES / "supervised_validation_metrics.csv")
    top = enrich.sort_values(["endpoint", "prevalence_ratio"], ascending=[True, False]).groupby("endpoint").head(1)
    top = top.rename(
        columns={
            "phenotype": "top_phenotype",
            "n": "top_n",
            "events": "top_events",
            "weighted_prevalence": "top_weighted_prevalence",
            "prevalence_ratio": "top_prevalence_ratio",
            "risk_difference": "top_risk_difference",
        }
    )
    best_perf = perf.sort_values(["endpoint", "auprc"], ascending=[True, False]).groupby("endpoint").head(1)
    best_perf = best_perf.rename(columns={"feature_set": "best_feature_set"})
    return top.merge(best_perf, on="endpoint", how="left")


def save_tables(df: pd.DataFrame, endpoints: pd.DataFrame) -> None:
    MANUSCRIPT_TABLES.mkdir(parents=True, exist_ok=True)
    make_table1(df, endpoints).to_csv(MANUSCRIPT_TABLES / "table1_cohort_characteristics.csv", index=False)
    make_table2().to_csv(MANUSCRIPT_TABLES / "table2_variables_endpoints.csv", index=False)
    make_table3().to_csv(MANUSCRIPT_TABLES / "table3_phenotype_profiles.csv", index=False)
    make_table4().to_csv(MANUSCRIPT_TABLES / "table4_endpoint_enrichment_model_metrics.csv", index=False)


def figure1_workflow() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 6.0))
    ax.axis("off")
    boxes = [
        (0.05, 0.68, 0.21, 0.16, "2011-2017\nTraining / SSL pretraining\n16,176 respondents", PALETTE[0]),
        (0.34, 0.68, 0.21, 0.16, "2017-2019\nDevelopment / k selection\n5,409 respondents", PALETTE[1]),
        (0.63, 0.68, 0.21, 0.16, "2022-2023\nTemporal validation\n4,893 respondents", "#777777"),
        (0.05, 0.27, 0.20, 0.18, "Respondent and\npregnancy files\nlinked by CaseID", "#6C8EBF"),
        (0.31, 0.27, 0.21, 0.18, "Leakage-controlled\nlife-course matrix\n48 SSL input features", "#6C8EBF"),
        (0.58, 0.27, 0.21, 0.18, "Masked tabular SSL\nencoder, PCA, k-means\n3 phenotypes", "#6C8EBF"),
        (0.84, 0.27, 0.13, 0.18, "Endpoint\nenrichment\nmodels", "#6C8EBF"),
    ]
    for x, y, w, h, text, color in boxes:
        rect = FancyBboxPatch(
            (x, y),
            w,
            h,
            transform=ax.transAxes,
            boxstyle="round,pad=0.02,rounding_size=0.015",
            facecolor="white",
            edgecolor=color,
            linewidth=2,
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=10, color="#1f1f1f", transform=ax.transAxes)
    arrows = [
        ((0.26, 0.76), (0.34, 0.76)),
        ((0.55, 0.76), (0.63, 0.76)),
        ((0.16, 0.68), (0.16, 0.45)),
        ((0.25, 0.36), (0.31, 0.36)),
        ((0.52, 0.36), (0.58, 0.36)),
        ((0.79, 0.36), (0.84, 0.36)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, xycoords=ax.transAxes, arrowprops=dict(arrowstyle="->", color="#555555", lw=1.8))
    ax.text(0.05, 0.93, "NSFG reproductive life-course SSL study design", fontsize=15, weight="bold", transform=ax.transAxes)
    ax.text(0.05, 0.11, "Primary validation uses only 2022-2023 labels; endpoint-direct variables are excluded from the primary SSL encoder.", fontsize=9, color="#555555", transform=ax.transAxes)
    fig.savefig(FIGURES / "figure1_workflow.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "figure1_workflow.pdf", bbox_inches="tight")
    plt.close(fig)


def figure2_matrix(df: pd.DataFrame) -> None:
    summary = pd.read_csv(TABLES / "harmonized_matrix_summary.csv")
    audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    used = audit[audit["used_in_primary_encoder"]].sort_values("missing_train").head(48)
    mat = df.loc[df["cycle"].eq("2022_2023"), used["feature"].tolist()].apply(pd.to_numeric, errors="coerce").isna().astype(int)
    mat = mat.sample(n=min(900, len(mat)), random_state=1)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    sns.barplot(data=summary, x="cycle", y="respondents", ax=axes[0], color=PALETTE[0])
    axes[0].set_title("Temporal cohort split", fontsize=11)
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Respondents aged 15-44")
    sns.heatmap(mat.T, ax=axes[1], cmap=["#1f5aa6", "#f2f2f2"], cbar=False, xticklabels=False, yticklabels=False)
    axes[1].set_title("Missingness in selected SSL features, 2022-2023", fontsize=11)
    axes[1].set_xlabel("Respondents")
    axes[1].set_ylabel("Features")
    fig.tight_layout()
    fig.savefig(FIGURES / "figure2_matrix_missingness.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "figure2_matrix_missingness.pdf", bbox_inches="tight")
    plt.close(fig)


def figure3_embedding(assignments: pd.DataFrame, pca: pd.DataFrame) -> None:
    coords = pca.merge(assignments, on=["caseid", "cycle"])
    test = coords[coords["cycle"].eq("2022_2023")].copy()
    metrics = pd.read_csv(TABLES / "cluster_selection_metrics.csv")
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2))
    for pheno, sub in test.groupby("phenotype"):
        axes[0].scatter(sub["pc1"], sub["pc2"], s=7, alpha=0.65, color=PALETTE[int(pheno)], label=f"P{int(pheno)}")
    axes[0].set_title("Held-out 2022-2023 embeddings", fontsize=11)
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    axes[0].legend(frameon=False, fontsize=8)
    counts = test["phenotype"].value_counts().sort_index()
    axes[1].bar([f"P{i}" for i in counts.index], counts.values, color=[PALETTE[int(i)] for i in counts.index])
    axes[1].set_title("Phenotype size in temporal validation", fontsize=11)
    axes[1].set_ylabel("Respondents")
    axes[2].plot(metrics["k"], metrics["silhouette"], marker="o", label="Silhouette", color=PALETTE[0])
    axes[2].plot(metrics["k"], metrics["bootstrap_ari_mean"], marker="o", label="Bootstrap ARI", color=PALETTE[1])
    axes[2].set_title("Development-set k selection", fontsize=11)
    axes[2].set_xlabel("k")
    axes[2].set_ylim(0, 1.05)
    axes[2].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "figure3_embedding_phenotypes.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "figure3_embedding_phenotypes.pdf", bbox_inches="tight")
    plt.close(fig)


def figure4_profiles() -> None:
    profile = pd.read_csv(TABLES / "phenotype_profiles_test_weighted.csv")
    keep = [
        "age_analysis",
        "parity",
        "preg_n_records",
        "has_pregnancy_record",
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "unintended_mistimed_pregnancy_history",
        "adverse_pregnancy_history_proxy",
        "impaired_fecundity_status",
    ]
    mat = profile[profile["variable"].isin(keep)].pivot(index="variable", columns="phenotype", values="weighted_mean")
    row_labels = {
        "age_analysis": "Age, years",
        "parity": "Parity",
        "preg_n_records": "Pregnancy records",
        "has_pregnancy_record": "Any pregnancy record",
        "contraceptive_vulnerability": "Contraceptive vulnerability",
        "fertility_service_or_loss_help": "Fertility help",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy",
        "adverse_pregnancy_history_proxy": "LBW/stillbirth proxy",
        "impaired_fecundity_status": "Impaired fecundity",
    }
    mat = mat.rename(index=row_labels)
    z = mat.sub(mat.mean(axis=1), axis=0).div(mat.std(axis=1).replace(0, 1), axis=0)
    fig, ax = plt.subplots(figsize=(7.8, 5.2))
    sns.heatmap(z, cmap="vlag", center=0, annot=mat.round(2), fmt="", linewidths=0.5, ax=ax, cbar_kws={"label": "Row z-score"})
    ax.set_title("Survey-weighted phenotype profile, 2022-2023", fontsize=12)
    ax.set_xlabel("Phenotype")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIGURES / "figure4_phenotype_profiles.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "figure4_phenotype_profiles.pdf", bbox_inches="tight")
    plt.close(fig)


def figure5_enrichment() -> None:
    enrich = pd.read_csv(TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    perf = pd.read_csv(TABLES / "supervised_validation_metrics.csv")
    label_map = {
        "contraceptive_vulnerability": "Contraceptive\nvulnerability",
        "fertility_service_or_loss_help": "Fertility\nhelp",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted\npregnancy",
        "adverse_pregnancy_history_proxy": "LBW/stillbirth\nproxy",
        "impaired_fecundity_status": "Impaired\nfecundity",
    }
    enrich = enrich.copy()
    perf = perf.copy()
    enrich["endpoint_label"] = enrich["endpoint"].map(label_map)
    perf["endpoint_label"] = perf["endpoint"].map(label_map)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    sns.barplot(data=enrich, x="endpoint_label", y="prevalence_ratio", hue="phenotype", palette=PALETTE[:3], ax=axes[0])
    axes[0].axhline(1, color="#333333", lw=1)
    axes[0].set_title("Phenotype endpoint enrichment, 2022-2023", fontsize=11)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Weighted prevalence ratio")
    axes[0].tick_params(axis="x", rotation=0)
    axes[0].legend(title="Phenotype", frameon=False, fontsize=8)
    sns.barplot(data=perf, x="endpoint_label", y="auprc_enrichment", hue="feature_set", ax=axes[1])
    axes[1].axhline(1, color="#333333", lw=1)
    axes[1].set_title("Risk-enrichment model comparison", fontsize=11)
    axes[1].set_xlabel("")
    axes[1].set_ylabel("AUPRC / baseline prevalence")
    axes[1].tick_params(axis="x", rotation=0)
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "figure5_risk_enrichment.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "figure5_risk_enrichment.pdf", bbox_inches="tight")
    plt.close(fig)


def supplementary_figures() -> None:
    curve = pd.read_csv(TABLES / "ssl_training_curve.csv")
    audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(curve["epoch"], curve["masked_mse"], marker="o", color=PALETTE[0])
    axes[0].set_title("Masked reconstruction training", fontsize=11)
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Masked MSE")
    sns.histplot(audit, x="missing_train", hue="used_in_primary_encoder", bins=30, ax=axes[1], legend=False)
    axes[1].set_title("Feature missingness and SSL selection", fontsize=11)
    axes[1].set_xlabel("Training missingness")
    fig.tight_layout()
    fig.savefig(FIGURES / "figureS1_ssl_diagnostics.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES / "figureS1_ssl_diagnostics.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.0)
    FIGURES.mkdir(parents=True, exist_ok=True)
    df, endpoints, assignments, pca = load_all()
    save_tables(df, endpoints)
    figure1_workflow()
    figure2_matrix(df)
    figure3_embedding(assignments, pca)
    figure4_profiles()
    figure5_enrichment()
    supplementary_figures()
    print("Figures and tables written.")


if __name__ == "__main__":
    main()
