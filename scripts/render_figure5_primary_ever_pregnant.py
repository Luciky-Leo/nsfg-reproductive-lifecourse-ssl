"""Render Figure 5 after elevating ever-pregnant pregnancy-history estimates.

Panel A uses the primary interpretive analysis set for each endpoint:
pregnancy-history endpoints use the ever-pregnant stratum, while other
endpoints use the full analytic cohort. Panel B keeps the secondary supervised
AUPRC enrichment summaries.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "tables"
OUT_RESULTS = ROOT / "results" / "figures"
OUT_LATEX = ROOT / "manuscript" / "latex" / "figures"
SOURCE_DATA = ROOT / "manuscript" / "latex" / "source_data"

PALETTE = ["#3E4F94", "#3E90BF", "#A6C0E3", "#D8D3E7", "#FAF9CB"]
NAVY, BLUE, LIGHT_BLUE, LILAC, PALE_YELLOW = PALETTE
INK = "#22252A"
GRID = "#E7E9F0"
PHENO_COLORS = {0: NAVY, 1: BLUE, 2: LIGHT_BLUE}
FEATURE_COLORS = {
    "Phenotype only": LILAC,
    "SSL embedding": BLUE,
    "SSL + phenotype": NAVY,
}

ENDPOINT_ORDER = [
    "contraceptive_vulnerability",
    "fertility_service_or_loss_help",
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
    "impaired_fecundity_status",
]

ENDPOINT_LABELS = {
    "contraceptive_vulnerability": "Contraceptive\nat-risk status",
    "fertility_service_or_loss_help": "Fertility / loss\ncare",
    "unintended_mistimed_pregnancy_history": "Mistimed or unwanted\npregnancy history",
    "adverse_pregnancy_history_proxy": "Adverse pregnancy\nhistory proxy",
    "impaired_fecundity_status": "Fecundity limitation /\ninfertility",
}

PREG_HISTORY_ENDPOINTS = {
    "unintended_mistimed_pregnancy_history",
    "adverse_pregnancy_history_proxy",
}


def clean_axis(ax: plt.Axes, axis: str = "both") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="both", labelsize=7, width=0.7)
    if axis in {"both", "x"}:
        ax.grid(axis="x", color=GRID, linewidth=0.7)
    if axis in {"both", "y"}:
        ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.12, 1.06, label, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom")


def load_primary_panel_a() -> pd.DataFrame:
    full = pd.read_csv(RESULTS / "endpoint_enrichment_by_phenotype_test.csv")
    ever = pd.read_csv(RESULTS / "supplementary_ever_pregnant_endpoint_enrichment.csv")
    full["analysis_set"] = "Full cohort"
    ever["analysis_set"] = "Ever-pregnant"
    parts = []
    for endpoint in ENDPOINT_ORDER:
        if endpoint in PREG_HISTORY_ENDPOINTS:
            parts.append(ever[ever["endpoint"].eq(endpoint)].copy())
        else:
            parts.append(full[full["endpoint"].eq(endpoint)].copy())
    panel = pd.concat(parts, ignore_index=True)
    panel["phenotype"] = panel["phenotype"].astype(int)
    panel["endpoint_order"] = panel["endpoint"].map({e: i for i, e in enumerate(ENDPOINT_ORDER)})
    panel = panel.sort_values(["endpoint_order", "phenotype"]).reset_index(drop=True)
    panel.to_csv(SOURCE_DATA / "figure5_primary_endpoint_enrichment_display.csv", index=False)
    return panel


def render() -> None:
    OUT_RESULTS.mkdir(parents=True, exist_ok=True)
    OUT_LATEX.mkdir(parents=True, exist_ok=True)
    SOURCE_DATA.mkdir(parents=True, exist_ok=True)

    panel_a = load_primary_panel_a()
    supervised = pd.read_csv(RESULTS / "supervised_validation_metrics.csv")

    fig = plt.figure(figsize=(10.2, 3.9), dpi=300)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], wspace=0.34)

    ax = fig.add_subplot(gs[0, 0])
    endpoint_y = {
        endpoint: (len(ENDPOINT_ORDER) - 1 - endpoint_i) * 1.35
        for endpoint_i, endpoint in enumerate(ENDPOINT_ORDER)
    }
    phenotype_offset = {0: 0.28, 1: 0.0, 2: -0.28}
    panel_a = panel_a.copy()
    panel_a["y"] = [
        endpoint_y[row["endpoint"]] + phenotype_offset[int(row["phenotype"])]
        for _, row in panel_a.iterrows()
    ]
    for _, row in panel_a.iterrows():
        color = PHENO_COLORS[int(row["phenotype"])]
        label = f"P{int(row['phenotype'])}" if row["endpoint"] == ENDPOINT_ORDER[0] else None
        line = ax.hlines(
            row["y"],
            float(row["prevalence_ratio_ci_low"]),
            float(row["prevalence_ratio_ci_high"]),
            color=color,
            linewidth=1.25,
            alpha=0.82,
        )
        ax.scatter(
            float(row["prevalence_ratio"]),
            row["y"],
            s=28,
            color=color,
            edgecolor="white",
            linewidth=0.45,
            zorder=3,
            label=label,
        )
    ax.axvline(1.0, color="#6A6E79", linewidth=0.8, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlim(0.18, 6.0)
    ax.set_xlabel("Prevalence ratio, log scale", fontsize=8)
    ax.set_yticks([endpoint_y[e] for e in ENDPOINT_ORDER])
    ax.set_yticklabels([ENDPOINT_LABELS[e] for e in ENDPOINT_ORDER], fontsize=7)
    ax.set_ylim(min(endpoint_y.values()) - 0.75, max(endpoint_y.values()) + 0.75)
    ax.set_title("Endpoint enrichment by phenotype", loc="left", fontsize=9, pad=4)
    clean_axis(ax, "x")
    panel_label(ax, "A")
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0.0, 1.02), fontsize=6.5, handletextpad=0.3, columnspacing=0.8)
    ax.text(
        0.99,
        -0.22,
        "Pregnancy-history endpoints use the ever-pregnant stratum; others use the full cohort.",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=6.2,
        color="#565A64",
    )

    ax2 = fig.add_subplot(gs[0, 1])
    mat = (
        supervised.pivot(index="endpoint", columns="feature_set", values="auprc_enrichment")
        .reindex(ENDPOINT_ORDER)
        [["Phenotype only", "SSL embedding", "SSL + phenotype"]]
    )
    im = ax2.imshow(
        mat.to_numpy(),
        aspect="auto",
        cmap=plt.matplotlib.colors.LinearSegmentedColormap.from_list(
            "prism_enrich", [PALE_YELLOW, LILAC, LIGHT_BLUE, BLUE, NAVY]
        ),
        vmin=1,
        vmax=max(5.8, float(np.nanmax(mat.to_numpy()))),
    )
    ax2.set_xticks(np.arange(mat.shape[1]))
    ax2.set_xticklabels(["Phenotype", "SSL", "SSL +\nphenotype"], fontsize=7)
    ax2.set_yticks(np.arange(mat.shape[0]))
    ax2.set_yticklabels([ENDPOINT_LABELS[e] for e in mat.index], fontsize=6.8)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            value = float(mat.iloc[i, j])
            color = "white" if value >= 3.2 else INK
            ax2.text(j, i, f"{value:.1f}x", ha="center", va="center", fontsize=7, color=color, fontweight="bold")
    ax2.set_title("AUPRC enrichment over baseline", loc="left", fontsize=9, pad=4)
    panel_label(ax2, "B")
    for spine in ax2.spines.values():
        spine.set_linewidth(0.8)
    cbar = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.035)
    cbar.set_label("AUPRC / prevalence", fontsize=7)
    cbar.ax.tick_params(labelsize=6.5, width=0.6)

    fig.subplots_adjust(left=0.17, right=0.95, bottom=0.22, top=0.88)
    for outdir in [OUT_RESULTS, OUT_LATEX]:
        for ext in ["pdf", "png", "svg"]:
            fig.savefig(outdir / f"figure5_risk_enrichment.{ext}", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    render()
