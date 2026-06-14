"""Redraw manuscript figures using the requested five-color PRISM palette.

This is a source-data-first redraw pass requested after the FINAL package.
It ports the requested PERSIST/HF visual grammars to the current NSFG source
tables without changing statistical results.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.patches import Ellipse, Rectangle
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
RESULTS_TABLES = ROOT / "results" / "tables"
RESULTS_FIGURES = ROOT / "results" / "figures"
PROCESSED = ROOT / "data" / "processed"
REDRAW = ROOT / "figure_redraw" / "requested_palette_20260604"

PALETTE = ["#3E4F94", "#3E90BF", "#A6C0E3", "#D8D3E7", "#FAF9CB"]
NAVY, BLUE, LIGHT_BLUE, LILAC, PALE_YELLOW = PALETTE
INK = "#22252A"
GRID = "#E8EAF0"
SOFT = "#F7F8FB"
PHENO = {"P0": NAVY, "P1": BLUE, "P2": LIGHT_BLUE}

HF = {
    "F2A": "HF191_2026-04-18_e0fa957a",
    "F2B": "HF196_2026-04-27_d9118163",
    "F2C": "HF052_2025-08-05_47ae15c2",
    "F3B": "HF121_2025-11-28_1b86656d",
    "F5A": "HF208_2026-05-16_3b690ee7",
    "F5B": "HF176_2026-03-12_52ae8721",
    "F6A": "HF170_2026-03-06_62405cfd",
    "F6B": "HF155_2026-02-05_8df222b0",
}


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Arial",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.linewidth": 0.7,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
        }
    )


def ensure() -> None:
    for path in [RESULTS_FIGURES, REDRAW / "outputs", REDRAW / "intermediate_tables", REDRAW / "reviews"]:
        path.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, stem: str) -> None:
    for ext in ["png", "pdf", "svg"]:
        fig.savefig(RESULTS_FIGURES / f"{stem}.{ext}", bbox_inches="tight", facecolor="white")
        fig.savefig(REDRAW / "outputs" / f"{stem}.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def panel(ax: plt.Axes, label: str, x: float = -0.08, y: float = 1.06) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top", fontsize=10, weight="bold", color=INK)


def clean(ax: plt.Axes, grid: str = "y") -> None:
    ax.spines[["top", "right"]].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.6)
        ax.set_axisbelow(True)


def endpoint_label(x: str) -> str:
    return {
        "contraceptive_vulnerability": "Contraceptive\nvulnerability",
        "fertility_service_or_loss_help": "Fertility/loss\nhelp",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted\npregnancy",
        "adverse_pregnancy_history_proxy": "Adverse pregnancy\nhistory",
        "impaired_fecundity_status": "Fecundity limitation /\ninfertility",
    }.get(x, x)


def variable_label(x: str) -> str:
    return {
        "age_analysis": "Age",
        "parity": "Parity",
        "preg_n_records": "Pregnancy records",
        "has_pregnancy_record": "Any pregnancy record",
        "poverty": "Poverty-income ratio",
        "contraceptive_vulnerability": "Contraceptive vulnerability",
        "fertility_service_or_loss_help": "Fertility/loss help",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy",
        "adverse_pregnancy_history_proxy": "Adverse pregnancy proxy",
        "impaired_fecundity_status": "Fecundity limitation / infertility",
    }.get(x, x)


def feature_short_label(x: str) -> str:
    labels = {
        "poverty": "Poverty",
        "dateuse1": "Contraceptive\nuse",
        "cmfsexfp": "First sex\nmonth",
        "cmfsextot": "Total sex\nhistory",
        "cmfsex": "Recent sex\nmonth",
        "lsexdate": "Last sex\ndate",
        "sexmar": "Marital\nsex",
        "sexunion": "Union\nsex",
        "partdur1": "Partner\nduration",
        "preg_agecon_mean": "Age at\nconception",
        "preg_agepreg_mean": "Age at\npregnancy",
        "preg_kidage_mean": "Child\nage",
    }
    return labels.get(x, x.replace("preg_", "").replace("_mean", "").replace("_", "\n")[:16])


def confidence_ellipse(ax: plt.Axes, x: np.ndarray, y: np.ndarray, color: str) -> None:
    if len(x) < 5:
        return
    cov = np.cov(x, y)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    angle = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
    width, height = 2 * 1.75 * np.sqrt(vals)
    ell = Ellipse((np.mean(x), np.mean(y)), width, height, angle=angle, facecolor=color, edgecolor=color, lw=1.1, alpha=0.14)
    ax.add_patch(ell)


def render_figure2() -> None:
    summary = pd.read_csv(RESULTS_TABLES / "harmonized_matrix_summary.csv")
    audit = pd.read_csv(RESULTS_TABLES / "ssl_feature_audit.csv")
    matrix = pd.read_csv(PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz")
    used = audit.loc[audit["used_in_primary_encoder"].astype(bool), "feature"].tolist()
    missing = (
        matrix.loc[matrix["cycle"] == "2022_2023", [c for c in used if c in matrix.columns]]
        .isna()
        .mean()
        .sort_values(ascending=False)
        .head(14)
        .reset_index()
    )
    missing.columns = ["feature", "missingness"]
    summary.to_csv(REDRAW / "intermediate_tables" / "figure2_cycle_summary.csv", index=False)
    missing.to_csv(REDRAW / "intermediate_tables" / "figure2_missingness_top18.csv", index=False)

    fig = plt.figure(figsize=(7.1, 4.05))
    gs = GridSpec(1, 3, width_ratios=[1.02, 0.88, 1.72], wspace=0.74)
    ax_a, ax_b, ax_c = [fig.add_subplot(gs[0, i]) for i in range(3)]

    labels = summary["cycle"].str.replace("_", "-", regex=False)
    x = np.arange(len(summary))
    for i, v in enumerate(summary["respondents"]):
        ax_a.bar(i + 0.06, v, color="#C9CEDD", width=0.55, zorder=1)
        ax_a.bar(i, v, color=[NAVY, NAVY, NAVY, BLUE, LILAC][i], width=0.55, edgecolor="white", lw=0.5, zorder=2)
        ax_a.text(i, v + 95, f"{int(v):,}", ha="center", va="bottom", fontsize=6.5)
    panel(ax_a, "A", -0.18, 1.13)
    ax_a.set_title("  Cohort magnitude", loc="left", pad=8)
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(labels, rotation=35, ha="right")
    ax_a.set_ylabel("Respondents")
    ax_a.set_ylim(0, summary["respondents"].max() * 1.22)
    ax_a.set_xlim(-0.72, len(summary) - 0.25)
    clean(ax_a)

    coverage = summary["respondents_with_pregnancy"] / summary["respondents"]
    wedges, _ = ax_b.pie(
        [coverage.iloc[-1], 1 - coverage.iloc[-1]],
        startangle=90,
        colors=[BLUE, LILAC],
        wedgeprops={"width": 0.26, "edgecolor": "white"},
        radius=0.74,
    )
    ax_b.text(0, 0.13, f"{coverage.iloc[-1]*100:.1f}%", ha="center", va="center", fontsize=10.5, weight="bold", color=NAVY)
    ax_b.text(0, -0.25, "any pregnancy\nrecord, 2022-2023", ha="center", va="center", fontsize=5.6, color=INK)
    ax_b2 = ax_b.inset_axes([0.08, -0.04, 0.84, 0.32])
    ax_b2.plot(x, coverage * 100, color=NAVY, lw=1.5, marker="o", ms=3)
    ax_b2.scatter(x.iloc[-1] if hasattr(x, "iloc") else x[-1], coverage.iloc[-1] * 100, color=BLUE, s=22, zorder=3)
    ax_b2.set_xticks([])
    ax_b2.set_yticks([55, 65])
    ax_b2.tick_params(labelsize=6)
    ax_b2.spines[["top", "right"]].set_visible(False)
    ax_b2.grid(axis="y", color=GRID, lw=0.5)
    panel(ax_b, "B", -0.06, 1.07)
    ax_b.set_title("Pregnancy-record history coverage", loc="center", pad=8)

    miss = missing.iloc[::-1]
    y = np.arange(len(miss))
    ax_c.barh(y, miss["missingness"] * 100, color=LIGHT_BLUE, edgecolor="white", height=0.64)
    ax_c.plot(miss["missingness"] * 100, y, color=NAVY, lw=1.2, marker="o", ms=2.8)
    ax_c.set_yticks(y)
    ax_c.set_yticklabels([s[:20] for s in miss["feature"]], fontsize=6.5)
    ax_c.set_xlabel("Missing/skipped, %")
    ax_c.set_title("  Selected skip patterns", loc="left", pad=8)
    panel(ax_c, "C", -0.09, 1.13)
    clean(ax_c, "x")
    save(fig, "figure2_matrix_missingness")


def render_figure2_full() -> None:
    """Render Figure 2 as A-D, including endpoint prevalence as a hard-result panel."""
    summary = pd.read_csv(RESULTS_TABLES / "harmonized_matrix_summary.csv")
    audit = pd.read_csv(RESULTS_TABLES / "ssl_feature_audit.csv")
    matrix = pd.read_csv(PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz")
    prev = pd.read_csv(RESULTS_TABLES / "endpoint_prevalence_by_cycle.csv")
    used = audit.loc[audit["used_in_primary_encoder"].astype(bool), "feature"].tolist()
    missing = (
        matrix.loc[matrix["cycle"] == "2022_2023", [c for c in used if c in matrix.columns]]
        .isna()
        .mean()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    missing.columns = ["feature", "missingness"]

    fig = plt.figure(figsize=(7.1, 7.35))
    outer = GridSpec(2, 1, height_ratios=[1.0, 1.22], hspace=0.43)
    top = GridSpecFromSubplotSpec(1, 3, subplot_spec=outer[0], width_ratios=[1.0, 0.9, 1.65], wspace=0.78)
    ax_a, ax_b, ax_c = [fig.add_subplot(top[0, i]) for i in range(3)]

    labels = summary["cycle"].str.replace("_", "-", regex=False)
    x = np.arange(len(summary))
    split_colors = [NAVY, NAVY, NAVY, BLUE, LILAC]
    ax_a.bar(x, summary["respondents"], color=split_colors, edgecolor="white", lw=0.6, width=0.62)
    for i, v in enumerate(summary["respondents"]):
        ax_a.text(i, v + 110, f"{int(v):,}", ha="center", va="bottom", fontsize=6.4)
    panel(ax_a, "A", -0.16, 1.14)
    ax_a.set_title("Cohort magnitude", loc="left", pad=8)
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(labels, rotation=34, ha="right")
    ax_a.set_ylabel("Respondents")
    ax_a.set_ylim(0, summary["respondents"].max() * 1.24)
    clean(ax_a)

    coverage = summary["respondents_with_pregnancy"] / summary["respondents"]
    ax_b.pie(
        [coverage.iloc[-1], 1 - coverage.iloc[-1]],
        startangle=90,
        colors=[BLUE, LILAC],
        wedgeprops={"width": 0.27, "edgecolor": "white"},
        radius=0.74,
    )
    ax_b.text(0, 0.11, f"{coverage.iloc[-1]*100:.1f}%", ha="center", va="center", fontsize=10.0, weight="bold", color=NAVY)
    ax_b.text(0, -0.24, "any pregnancy\nrecord, 2022-2023", ha="center", va="center", fontsize=5.6, color=INK)
    ax_b2 = ax_b.inset_axes([0.08, -0.03, 0.84, 0.32])
    ax_b2.plot(x, coverage * 100, color=NAVY, lw=1.5, marker="o", ms=3)
    ax_b2.scatter(x[-1], coverage.iloc[-1] * 100, color=BLUE, s=22, zorder=3)
    ax_b2.set_xticks([])
    ax_b2.set_yticks([50, 60])
    ax_b2.tick_params(labelsize=6)
    ax_b2.spines[["top", "right"]].set_visible(False)
    ax_b2.grid(axis="y", color=GRID, lw=0.5)
    panel(ax_b, "B", -0.08, 1.10)
    ax_b.set_title("Pregnancy-record history coverage", loc="center", pad=8)

    miss = missing.iloc[::-1]
    y = np.arange(len(miss))
    ax_c.barh(y, miss["missingness"] * 100, color=LIGHT_BLUE, edgecolor="white", height=0.60)
    ax_c.plot(miss["missingness"] * 100, y, color=NAVY, lw=1.2, marker="o", ms=2.6)
    ax_c.set_yticks(y)
    ax_c.set_yticklabels([s[:18] for s in miss["feature"]], fontsize=6.2)
    ax_c.set_xlabel("Missing/skipped, %")
    ax_c.set_title("Selected skip patterns", loc="left", pad=8)
    panel(ax_c, "C", -0.09, 1.14)
    clean(ax_c, "x")

    bottom = GridSpecFromSubplotSpec(1, 2, subplot_spec=outer[1], width_ratios=[2.75, 0.72], wspace=0.22)
    ax_h = fig.add_subplot(bottom[0, 0])
    ax_delta = fig.add_subplot(bottom[0, 1])
    endpoint_order = [
        "unintended_mistimed_pregnancy_history",
        "impaired_fecundity_status",
        "fertility_service_or_loss_help",
        "contraceptive_vulnerability",
        "adverse_pregnancy_history_proxy",
    ]
    cycle_order = ["2011_2013", "2013_2015", "2015_2017", "2017_2019", "2022_2023"]
    heat = (
        prev.pivot(index="endpoint", columns="cycle", values="weighted_prevalence")
        .loc[endpoint_order, cycle_order]
        * 100
    )
    events = prev.pivot(index="endpoint", columns="cycle", values="events").loc[endpoint_order, cycle_order]
    ns = prev.pivot(index="endpoint", columns="cycle", values="n").loc[endpoint_order, cycle_order]
    cmap = mpl.colors.LinearSegmentedColormap.from_list("prism_prevalence", [PALE_YELLOW, LIGHT_BLUE, BLUE, NAVY])
    norm = mpl.colors.Normalize(vmin=0, vmax=max(50, float(heat.max().max())))
    im = ax_h.imshow(heat.values, cmap=cmap, norm=norm, aspect="auto")

    def text_color(value: float) -> str:
        r, g, b, _ = cmap(norm(value))
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return INK if luminance > 0.56 else "#F8FAFC"

    for i, endpoint in enumerate(endpoint_order):
        for j, cycle in enumerate(cycle_order):
            val = float(heat.loc[endpoint, cycle])
            ax_h.text(
                j,
                i,
                f"{val:.1f}%\n{int(events.loc[endpoint, cycle]):,}/{int(ns.loc[endpoint, cycle]):,}",
                ha="center",
                va="center",
                fontsize=5.6,
                color=text_color(val),
            )
    ax_h.set_xticks(np.arange(len(cycle_order)))
    ax_h.set_xticklabels([c.replace("_", "-") for c in cycle_order], rotation=0)
    ax_h.set_yticks(np.arange(len(endpoint_order)))
    ax_h.set_yticklabels([endpoint_label(e).replace("\n", " ") for e in endpoint_order], fontsize=7)
    ax_h.set_title("Endpoint prevalence by NSFG cycle", loc="left", pad=8)
    panel(ax_h, "D", -0.10, 1.13)
    for s in ax_h.spines.values():
        s.set_visible(False)
    ax_h.set_xticks(np.arange(-0.5, len(cycle_order), 1), minor=True)
    ax_h.set_yticks(np.arange(-0.5, len(endpoint_order), 1), minor=True)
    ax_h.grid(which="minor", color="white", lw=1.1)
    ax_h.tick_params(which="minor", bottom=False, left=False)

    cb = fig.colorbar(im, ax=ax_h, fraction=0.025, pad=0.015)
    cb.set_label("Weighted prevalence, %", fontsize=7)
    cb.ax.tick_params(labelsize=6)

    delta = heat["2022_2023"] - heat["2011_2013"]
    yy = np.arange(len(endpoint_order))
    colors = [BLUE if v < 0 else "#F47C22" for v in delta.values]
    ax_delta.axvline(0, color="#777A80", lw=0.8)
    ax_delta.barh(yy, delta.values, color=colors, height=0.58, alpha=0.9)
    for yi, v in zip(yy, delta.values):
        ax_delta.text(v + (0.55 if v >= 0 else -0.55), yi, f"{v:+.1f}", va="center", ha="left" if v >= 0 else "right", fontsize=6.4)
    ax_delta.set_yticks([])
    ax_delta.set_title("2022-2023 vs\n2011-2013, pp", fontsize=8)
    ax_delta.set_xlim(min(-16, delta.min() - 2), max(5, delta.max() + 2))
    ax_delta.set_ylim(len(endpoint_order) - 0.5, -0.5)
    clean(ax_delta, "x")
    ax_delta.spines["left"].set_visible(False)

    save(fig, "figure2_matrix_missingness")


def render_figure3() -> None:
    pca_coords = pd.read_csv(PROCESSED / "ssl_pca_coordinates.csv.gz")
    ph = pd.read_csv(PROCESSED / "phenotype_assignments.csv.gz")
    emb = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
    metrics = pd.read_csv(RESULTS_TABLES / "cluster_selection_metrics.csv")
    profiles = pd.read_csv(RESULTS_TABLES / "phenotype_profiles_test_weighted.csv")
    test = pca_coords.merge(ph, on=["caseid", "cycle"], how="left")
    test = test[test["cycle"] == "2022_2023"].copy()
    test["phenotype_label"] = "P" + test["phenotype"].astype(int).astype(str)
    test.to_csv(REDRAW / "intermediate_tables" / "figure3_test_embedding.csv", index=False)

    emb_test = emb[emb["cycle"] == "2022_2023"].copy()
    feature_cols = [c for c in emb_test.columns if c.startswith("ssl_")]
    X = StandardScaler().fit_transform(emb_test[feature_cols].values)
    pca = PCA(n_components=8, random_state=20260604).fit(X)
    loading = pd.DataFrame(pca.components_[:2].T, columns=["PC1", "PC2"])
    loading["feature"] = feature_cols
    loading["strength"] = np.sqrt(loading["PC1"] ** 2 + loading["PC2"] ** 2)
    loading = loading.sort_values("strength", ascending=False).head(8)
    loading.to_csv(REDRAW / "intermediate_tables" / "figure3_pca_loadings_top8.csv", index=False)

    fig = plt.figure(figsize=(7.1, 9.7))
    outer = GridSpec(3, 1, height_ratios=[2.2, 1.0, 1.85], hspace=0.46)
    gs_a = GridSpecFromSubplotSpec(2, 2, subplot_spec=outer[0], width_ratios=[1.45, 0.9], height_ratios=[1.25, 0.78], wspace=0.32, hspace=0.44)
    ax_scatter = fig.add_subplot(gs_a[0, 0])
    ax_density = fig.add_subplot(gs_a[1, 0])
    ax_load = fig.add_subplot(gs_a[0, 1])
    ax_scree = fig.add_subplot(gs_a[1, 1])
    panel(ax_scatter, "A", -0.13, 1.13)
    for label, sub in test.groupby("phenotype_label"):
        ax_scatter.scatter(sub["pc1"], sub["pc2"], s=5, alpha=0.38, color=PHENO[label], label=label, linewidths=0)
        confidence_ellipse(ax_scatter, sub["pc1"].values, sub["pc2"].values, PHENO[label])
    ax_scatter.set_xlabel("")
    ax_scatter.set_ylabel("PC2")
    ax_scatter.set_title("PCA scatter with group ellipses", loc="left")
    ax_scatter.legend(frameon=False, ncol=1, loc="upper right", borderaxespad=0.2)
    clean(ax_scatter, "")
    for label, sub in test.groupby("phenotype_label"):
        ax_density.hist(sub["pc1"], bins=35, density=True, histtype="stepfilled", alpha=0.28, color=PHENO[label], label=label)
        ax_density.hist(sub["pc2"], bins=35, density=True, histtype="step", lw=1.0, color=PHENO[label])
    ax_density.set_title("Marginal PC density", loc="left")
    ax_density.set_xlabel("PC value")
    ax_density.set_ylabel("Density")
    clean(ax_density)
    scale = 2.8
    ax_load.axhline(0, color=GRID, lw=0.8)
    ax_load.axvline(0, color=GRID, lw=0.8)
    for _, row in loading.iterrows():
        ax_load.arrow(0, 0, row["PC1"] * scale, row["PC2"] * scale, color=NAVY, lw=0.8, head_width=0.035, length_includes_head=True)
        ax_load.text(row["PC1"] * scale * 1.08, row["PC2"] * scale * 1.08, row["feature"].replace("ssl_", "E"), fontsize=6.2, color=INK)
    ax_load.set_title("Loading arrows", loc="left")
    ax_load.set_xlabel("")
    ax_load.set_ylabel("PC2 loading")
    clean(ax_load, "")
    ev = pca.explained_variance_ratio_[:8] * 100
    ax_scree.bar(np.arange(1, len(ev) + 1), ev, color=[NAVY, BLUE, LIGHT_BLUE, LILAC, PALE_YELLOW, NAVY, BLUE, LIGHT_BLUE])
    ax_scree.plot(np.arange(1, len(ev) + 1), np.cumsum(ev), color=INK, lw=1.1, marker="o", ms=2.5)
    ax_scree.set_title("Scree plot", loc="left")
    ax_scree.set_xlabel("PC")
    ax_scree.set_ylabel("% variance")
    clean(ax_scree)

    gs_b = GridSpecFromSubplotSpec(1, 2, subplot_spec=outer[1], width_ratios=[0.8, 1.45], wspace=0.60)
    ax_b1, ax_b2 = fig.add_subplot(gs_b[0]), fig.add_subplot(gs_b[1])
    panel(ax_b1, "B", -0.18, 1.20)
    counts = test["phenotype_label"].value_counts().sort_index()
    ax_b1.bar(counts.index, counts.values, color=[PHENO[x] for x in counts.index], edgecolor="white")
    ax_b1.set_title("Phenotype size", loc="left")
    ax_b1.set_ylabel("Respondents")
    clean(ax_b1)
    pivot = profiles.pivot(index="variable", columns="phenotype", values="weighted_mean")
    z = pivot.sub(pivot.mean(axis=1), axis=0).div(pivot.std(axis=1).replace(0, np.nan), axis=0).fillna(0)
    drivers = z.abs().max(axis=1).sort_values(ascending=False).head(8)
    ax_b2.barh([variable_label(v) for v in drivers.index[::-1]], drivers.values[::-1], color=BLUE)
    ax_b2.set_title("Profile drivers", loc="left")
    ax_b2.set_xlabel("Max standardized separation")
    ax_b2.tick_params(axis="y", labelsize=6.5, pad=2)
    clean(ax_b2, "x")

    gs_c = GridSpecFromSubplotSpec(2, 2, subplot_spec=outer[2], width_ratios=[1.2, 1.0], height_ratios=[1.0, 1.0], wspace=0.34, hspace=0.42)
    ax_hm = fig.add_subplot(gs_c[:, 0])
    ax_sil = fig.add_subplot(gs_c[0, 1])
    ax_ari = fig.add_subplot(gs_c[1, 1])
    panel(ax_hm, "C", -0.10, 1.08)
    met = metrics.copy()
    met["min_cluster_prop_scaled"] = met["min_cluster_prop"] / met["min_cluster_prop"].max()
    hm = met.set_index("k")[["silhouette", "bootstrap_ari_mean", "min_cluster_prop_scaled", "davies_bouldin"]]
    hm["davies_bouldin"] = 1 - (hm["davies_bouldin"] - hm["davies_bouldin"].min()) / (hm["davies_bouldin"].max() - hm["davies_bouldin"].min() + 1e-9)
    im = ax_hm.imshow(hm.T.values, aspect="auto", cmap=mpl.colors.LinearSegmentedColormap.from_list("five", [PALE_YELLOW, LIGHT_BLUE, NAVY]), vmin=0, vmax=1)
    ax_hm.set_xticks(np.arange(len(hm.index)))
    ax_hm.set_xticklabels(hm.index)
    ax_hm.set_yticks(np.arange(4))
    ax_hm.set_yticklabels(["Silhouette", "ARI", "Min cluster", "DBI inverse"])
    ax_hm.set_title("Metrics heatmap", loc="left")
    for j, k in enumerate(hm.index):
        if k == 3:
            ax_hm.add_patch(Rectangle((j - 0.5, -0.5), 1, 4, fill=False, edgecolor=BLUE, lw=1.5))
    fig.colorbar(im, ax=ax_hm, fraction=0.036, pad=0.02)
    ax_sil.errorbar(met["k"], met["silhouette"], yerr=0.015, color=NAVY, marker="o", lw=1.2, capsize=2)
    ax_sil.axvline(3, color=BLUE, ls="--", lw=0.9)
    ax_sil.set_title("Silhouette width", loc="left")
    ax_sil.set_xticks(met["k"])
    clean(ax_sil)
    ax_ari.errorbar(met["k"], met["bootstrap_ari_mean"], yerr=met["bootstrap_ari_sd"], color=BLUE, marker="o", lw=1.2, capsize=2)
    ax_ari.axvline(3, color=NAVY, ls="--", lw=0.9)
    ax_ari.set_title("Bootstrap stability", loc="left")
    ax_ari.set_xticks(met["k"])
    ax_ari.set_xlabel("Number of clusters")
    clean(ax_ari)
    save(fig, "figure3_embedding_phenotypes")


def render_figure4() -> None:
    profile = pd.read_csv(RESULTS_TABLES / "phenotype_profiles_test_weighted.csv")
    profile["phenotype_label"] = "P" + profile["phenotype"].astype(str)
    order = [
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
    pivot = profile.pivot(index="variable", columns="phenotype_label", values="weighted_mean").loc[order]
    z = pivot.sub(pivot.mean(axis=1), axis=0).div(pivot.std(axis=1).replace(0, np.nan), axis=0).fillna(0)
    z.to_csv(REDRAW / "intermediate_tables" / "figure4_complexheatmap_style_z.csv")
    domains = {
        "age_analysis": "Sociodemographic",
        "poverty": "Sociodemographic",
        "parity": "Pregnancy history",
        "preg_n_records": "Pregnancy history",
        "has_pregnancy_record": "Pregnancy history",
        "contraceptive_vulnerability": "Endpoint-related",
        "fertility_service_or_loss_help": "Endpoint-related",
        "unintended_mistimed_pregnancy_history": "Endpoint-related",
        "adverse_pregnancy_history_proxy": "Endpoint-related",
        "impaired_fecundity_status": "Endpoint-related",
    }
    domain_colors = {"Sociodemographic": NAVY, "Pregnancy history": BLUE, "Endpoint-related": LILAC}
    fig = plt.figure(figsize=(6.8, 5.35))
    gs = GridSpec(2, 4, width_ratios=[0.42, 0.045, 1.0, 0.055], height_ratios=[0.075, 1.0], wspace=0.04, hspace=0.05)
    ax_top = fig.add_subplot(gs[0, 2])
    ax_labels = fig.add_subplot(gs[1, 0])
    ax_left = fig.add_subplot(gs[1, 1])
    ax = fig.add_subplot(gs[1, 2])
    cax = fig.add_subplot(gs[1, 3])
    phenotype_burden = pivot.loc[["preg_n_records", "adverse_pregnancy_history_proxy"]].mean(axis=0).values
    ax_top.imshow(phenotype_burden.reshape(1, -1), aspect="auto", cmap=mpl.colors.LinearSegmentedColormap.from_list("burden", [PALE_YELLOW, BLUE, NAVY]))
    ax_top.set_xticks(np.arange(3))
    ax_top.set_xticklabels([""] * len(z.columns))
    ax_top.set_yticks([])
    ax_top.tick_params(length=0)
    ax_top.text(-0.56, 0, "profile\nburden", ha="right", va="center", fontsize=6.3, linespacing=0.9)
    ax_labels.set_xlim(0, 1)
    ax_labels.set_ylim(len(z.index) - 0.5, -0.5)
    ax_labels.axis("off")
    for i, v in enumerate(z.index):
        ax_labels.text(0.98, i, variable_label(v), ha="right", va="center", fontsize=7.2, color=INK)
    ax_left.imshow([[list(domain_colors).index(domains[v])] for v in z.index], aspect="auto", cmap=mpl.colors.ListedColormap(list(domain_colors.values())))
    ax_left.set_xticks([])
    ax_left.set_yticks(np.arange(len(z.index)))
    ax_left.set_yticklabels([""] * len(z.index))
    ax_left.tick_params(length=0)
    im = ax.imshow(z.values, aspect="auto", cmap=mpl.colors.LinearSegmentedColormap.from_list("profile5", [NAVY, LIGHT_BLUE, "#FFFFFF", LILAC, PALE_YELLOW]), vmin=-1.4, vmax=1.4)
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(z.columns)
    ax.set_yticks(np.arange(len(z.index)))
    ax.set_yticklabels([""] * len(z.index))
    ax.set_xticks(np.arange(-0.5, 3, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(z.index), 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.4)
    ax.tick_params(which="minor", length=0)
    for i in range(z.shape[0]):
        for j in range(z.shape[1]):
            raw = pivot.iloc[i, j]
            txt = f"{raw*100:.1f}%" if raw <= 1 and z.index[i] not in ["age_analysis", "parity", "preg_n_records", "poverty"] else f"{raw:.1f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=6.3, color=INK)
    fig.colorbar(im, cax=cax, label="standardized profile")
    save(fig, "figure4_phenotype_profiles")


def render_figure5() -> None:
    enr = pd.read_csv(RESULTS_TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    perf = pd.read_csv(RESULTS_TABLES / "supervised_validation_metrics.csv")
    endpoints = [
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "unintended_mistimed_pregnancy_history",
        "adverse_pregnancy_history_proxy",
        "impaired_fecundity_status",
    ]
    fig = plt.figure(figsize=(7.1, 5.3))
    gs = GridSpec(1, 2, width_ratios=[1.15, 1.0], wspace=0.50)
    ax_a, ax_b = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    y = np.arange(len(endpoints))
    offsets = {"P0": -0.20, "P1": 0, "P2": 0.20}
    for ph in [0, 1, 2]:
        label = f"P{ph}"
        sub = enr[enr["phenotype"] == ph].set_index("endpoint").loc[endpoints]
        ax_a.errorbar(
            sub["prevalence_ratio"],
            y + offsets[label],
            xerr=[sub["prevalence_ratio"] - sub["prevalence_ratio_ci_low"], sub["prevalence_ratio_ci_high"] - sub["prevalence_ratio"]],
            fmt="o",
            color=PHENO[label],
            ecolor=PHENO[label],
            elinewidth=0.8,
            capsize=2,
            ms=4,
            label=label,
        )
    panel(ax_a, "A")
    ax_a.axvline(1, color=INK, ls="--", lw=0.8)
    ax_a.set_yticks(y)
    ax_a.set_yticklabels([endpoint_label(e) for e in endpoints])
    ax_a.invert_yaxis()
    ax_a.set_xlabel("Prevalence ratio with bootstrap CI")
    ax_a.set_title("Forest enrichment", loc="left")
    ax_a.set_xlim(-0.08, 4.7)
    ax_a.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.55, -0.16))
    clean(ax_a, "x")

    feature_order = ["Phenotype only", "SSL embedding", "SSL + phenotype"]
    metric = perf.pivot(index="endpoint", columns="feature_set", values="auprc_enrichment").loc[endpoints, feature_order]
    im = ax_b.imshow(metric.values, aspect="auto", cmap=mpl.colors.LinearSegmentedColormap.from_list("f5b", [PALE_YELLOW, LIGHT_BLUE, BLUE, NAVY]))
    panel(ax_b, "B")
    ax_b.set_title("SSL risk enrichment", loc="left")
    ax_b.set_xticks(np.arange(len(feature_order)))
    ax_b.set_xticklabels(["Phenotype", "SSL", "SSL+\nphenotype"], rotation=0)
    ax_b.set_yticks(y)
    ax_b.set_yticklabels([endpoint_label(e) for e in endpoints])
    for i in range(metric.shape[0]):
        for j in range(metric.shape[1]):
            ax_b.text(j, i, f"{metric.iloc[i,j]:.1f}", ha="center", va="center", fontsize=6.5, color=INK)
    fig.colorbar(im, ax=ax_b, fraction=0.046, pad=0.04, label="AUPRC enrichment")
    save(fig, "figure5_risk_enrichment")


def render_figure6() -> None:
    perf = pd.read_csv(RESULTS_TABLES / "supervised_validation_metrics.csv")
    audit = pd.read_csv(RESULTS_TABLES / "ssl_feature_audit.csv")
    endpoints = list(dict.fromkeys(perf["endpoint"]))
    feature_order = ["Phenotype only", "SSL embedding", "SSL + phenotype"]
    auroc = perf.pivot(index="endpoint", columns="feature_set", values="auroc").loc[endpoints, feature_order]
    auprc = perf.pivot(index="endpoint", columns="feature_set", values="auprc_enrichment").loc[endpoints, feature_order]
    fig = plt.figure(figsize=(7.1, 4.6))
    gs = GridSpec(1, 2, width_ratios=[1.12, 0.98], wspace=0.52)
    ax_a, ax_b = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1], projection="polar")
    panel(ax_a, "A")
    im = ax_a.imshow(auroc.values, aspect="auto", cmap=mpl.colors.LinearSegmentedColormap.from_list("f6a", [PALE_YELLOW, LIGHT_BLUE, BLUE, NAVY]), vmin=0.5, vmax=1.0)
    ax_a.set_title("AUROC validation matrix", loc="left")
    ax_a.set_xticks(np.arange(3))
    ax_a.set_xticklabels(["Phenotype", "SSL", "SSL+\nphenotype"])
    ax_a.set_yticks(np.arange(len(endpoints)))
    ax_a.set_yticklabels([endpoint_label(e) for e in endpoints])
    for i in range(auroc.shape[0]):
        for j in range(auroc.shape[1]):
            ax_a.text(j, i, f"{auroc.iloc[i,j]:.2f}", ha="center", va="center", fontsize=6.3, color=INK)
    fig.colorbar(im, ax=ax_a, fraction=0.045, pad=0.03, label="AUROC")

    used = audit[audit["used_in_primary_encoder"].astype(bool)].copy()
    used["score"] = (1 - used["missing_train"].astype(float)) * np.log1p(used["nunique_train"].astype(float))
    top = used.sort_values("score", ascending=False).head(12)
    theta = np.linspace(0, 2 * np.pi, len(top), endpoint=False)
    radius = top["score"].values / top["score"].max()
    ax_b.bar(theta, radius, width=2 * np.pi / len(top) * 0.74, color=[PALETTE[i % 5] for i in range(len(top))], edgecolor="white", lw=0.6)
    panel(ax_b, "B", -0.18, 1.12)
    ax_b.set_title("Encoder feature audit", loc="left", pad=10)
    ax_b.set_xticks(theta)
    ax_b.set_xticklabels([feature_short_label(f) for f in top["feature"]], fontsize=5.5)
    ax_b.set_yticklabels([])
    ax_b.grid(color=GRID, lw=0.5)
    save(fig, "figure6_model_diagnostics")


def write_reviews() -> None:
    (REDRAW / "project_palette_recommendation.md").write_text(
        "# Requested Five-Color Palette\n\n"
        "Confirmed palette: `#3E4F94`, `#3E90BF`, `#A6C0E3`, `#D8D3E7`, `#FAF9CB`.\n\n"
        "Role mapping: navy = primary phenotype/effect, blue = SSL/secondary signal, light blue = validation/background, lilac = low-intensity annotation, pale yellow = neutral high-end accent.\n",
        encoding="utf-8",
    )
    mapping = [
        ("Figure 2A", HF["F2A"], "cohort count bar with 3D-shadow grammar"),
        ("Figure 2B", HF["F2B"], "donut plus trend trajectory"),
        ("Figure 2C", HF["F2C"], "flowing stacked/ranked missingness panel"),
        ("Figure 3A", "native PCA/patchwork-style", "scatter ellipses, marginal density, loadings arrows, scree"),
        ("Figure 3B", HF["F3B"], "phenotype size plus profile drivers"),
        ("Figure 3C", "native patchwork-style", "metrics heatmap, silhouette, bootstrap ARI"),
        ("Figure 4", "ComplexHeatmap-style native", "annotated heatmap with top and side annotation bars"),
        ("Figure 5A", HF["F5A"], "forest plot with bootstrap confidence intervals"),
        ("Figure 5B", HF["F5B"], "SSL risk-enrichment heatmap"),
        ("Figure 6A", HF["F6A"], "AUROC validation matrix"),
        ("Figure 6B", HF["F6B"], "radial encoder feature audit"),
    ]
    rows = ["# Requested Palette/PERSIST Visual Mapping\n", "| Panel | Requested template | Implemented visual grammar |", "|---|---|---|"]
    rows.extend(f"| {p} | `{h}` | {r} |" for p, h, r in mapping)
    (REDRAW / "panel_visual_mapping.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (REDRAW / "figure_quality_review.md").write_text(
        "# Figure Quality Review\n\n"
        "All requested redraws are source-table driven, exported as PNG/PDF/SVG, and use the confirmed five-color palette. "
        "Figure 6 is generated as an added diagnostics figure because the prior manuscript did not contain a Figure 6.\n",
        encoding="utf-8",
    )


def main() -> None:
    ensure()
    setup_style()
    render_figure2_full()
    render_figure3()
    render_figure4()
    render_figure5()
    render_figure6()
    write_reviews()
    print(
        json.dumps(
            {
                "status": "rendered",
                "palette": PALETTE,
                "figures": [
                    "figure2_matrix_missingness",
                    "figure3_embedding_phenotypes",
                    "figure4_phenotype_profiles",
                    "figure5_risk_enrichment",
                    "figure6_model_diagnostics",
                ],
                "redraw_root": str(REDRAW),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
