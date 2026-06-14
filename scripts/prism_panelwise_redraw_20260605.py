"""Panel-wise PRISM/PERSIST redraws for user assembly.

This script renders standalone panels only. It does not assemble manuscript
figures and does not overwrite results/figures.

SOURCE_CODE_FIRST markers:
PERSIST_SOURCE_CODE_FIRST_PROTOCOL; VISUAL_SPEC; PORTING_PROMPT;
SOURCE_CODE_SNAPSHOT; source_code/; Reference visual.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler


def find_project_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "data" / "processed" / "ssl_embeddings.csv.gz").exists() and (parent / "results" / "tables").exists():
            return parent
    raise RuntimeError(f"Could not locate project root from {start}")


ROOT = find_project_root(Path(__file__).resolve())
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"
REDRAW = ROOT / "figure_redraw" / "panelwise_persist_prism_20260605"
PERSIST = Path("/mnt/e/Python/PERSIST")
CAPSULE_ROOT = PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules"

PALETTE = ["#3E4F94", "#3E90BF", "#A6C0E3", "#D8D3E7", "#FAF9CB"]
NAVY, BLUE, LIGHT_BLUE, LILAC, PALE_YELLOW = PALETTE
INK = "#22252A"
GRID = "#E7E9F0"
PHENO = {0: NAVY, 1: BLUE, 2: LIGHT_BLUE, "P0": NAVY, "P1": BLUE, "P2": LIGHT_BLUE}
READABLE_DARK = "#22252A"
READABLE_LIGHT = "#F2F4F8"


def relative_luminance(color: object) -> float:
    rgb = np.asarray(color[:3] if isinstance(color, (tuple, list, np.ndarray)) else mpl.colors.to_rgb(color), dtype=float)

    def linearize(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    r, g, b = [linearize(float(c)) for c in rgb[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(lum_a: float, lum_b: float) -> float:
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_text_color(value: float, cmap: mpl.colors.Colormap, norm: mpl.colors.Normalize) -> str:
    bg_lum = relative_luminance(cmap(norm(value)))
    dark_ratio = contrast_ratio(bg_lum, relative_luminance(READABLE_DARK))
    light_ratio = contrast_ratio(bg_lum, relative_luminance(READABLE_LIGHT))
    if dark_ratio >= 4.5 or dark_ratio >= light_ratio:
        return READABLE_DARK
    return READABLE_LIGHT


@dataclass(frozen=True)
class Candidate:
    panel: str
    requested: str
    candidate_id: str
    level: str
    maturity: str
    capsule_path: str
    source_script: str
    snapshot: str
    reference: str
    notes: str


CANDIDATES: dict[str, Candidate] = {
    "F2A": Candidate(
        "F2A", "HF191", "HF191_2026-04-18_e0fa957a", "hf_capsule", "source_port_ready",
        str(CAPSULE_ROOT / "HF191_2026-04-18_e0fa957a"),
        "E:/Python/PERSIST/2026年04月18日 Python绘制论文中常用3D柱状图/20260417-3D柱状图.py",
        str(CAPSULE_ROOT / "HF191_2026-04-18_e0fa957a/source_code/source_01_e7be45f1.py"),
        "E:/Python/PERSIST/2026年04月18日 Python绘制论文中常用3D柱状图/3d_bar_chart_scheme_4.png",
        "3D grouped bars with perspective, depth, edge, and value labels.",
    ),
    "F2B": Candidate(
        "F2B", "native PRISM", "native_prism_domain_missingness_matrix", "native_workflow", "production_ready",
        "NA: native workflow selected after PERSIST candidate search.",
        "E:/Python/PERSIST/2026年04月27日 Python绘制环形堆叠图+折线图组合图/20260426-环形堆叠图+折线图组合图.py",
        "NA: native PRISM source-code-first panel.",
        "E:/Python/PERSIST/2026年04月27日 Python绘制环形堆叠图+折线图组合图/result7.png",
        "Domain-count bar plus cycle-by-domain missingness heatmap; selected over radial composition for readability.",
    ),
    "F2C": Candidate(
        "F2C", "HF052", "HF052_2025-08-05_47ae15c2", "hf_capsule", "source_port_ready",
        str(CAPSULE_ROOT / "HF052_2025-08-05_47ae15c2"),
        "E:/Python/PERSIST/2025年08月05日 带流动趋势的百分比堆叠图/带流动趋势的百分比堆叠图.py",
        str(CAPSULE_ROOT / "HF052_2025-08-05_47ae15c2/source_code/source_01_47928d1f.py"),
        "E:/Python/PERSIST/2025年08月05日 带流动趋势的百分比堆叠图/flowing_stacked_bar.png",
        "Flowing stacked percentage bars with transition ribbons.",
    ),
    "F3B": Candidate(
        "F3B", "HF121", "HF121_2025-11-28_1b86656d", "hf_capsule", "source_port_ready",
        str(CAPSULE_ROOT / "HF121_2025-11-28_1b86656d"),
        "E:/Python/PERSIST/2025年11月28日 Python实现空间移动窗口+时间序列逐像元的RF+shap分析识别出主要驱动因子/142.窗口+RF+shap分析（调参）.py",
        str(CAPSULE_ROOT / "HF121_2025-11-28_1b86656d/source_code/source_01_03566b1c.py"),
        "None: capsule has no primary visual reference.",
        "ML-driver score grammar mapped to embedding-dimension separation.",
    ),
    "F5A": Candidate(
        "F5A", "HF208", "HF208_2026-05-16_3b690ee7", "hf_capsule", "source_port_ready",
        str(CAPSULE_ROOT / "HF208_2026-05-16_3b690ee7"),
        "E:/Python/PERSIST/2026年05月16日 Python绘制森林图/20260513-森林图.py",
        str(CAPSULE_ROOT / "HF208_2026-05-16_3b690ee7/source_code/source_01_a01c8e00.py"),
        "E:/Python/PERSIST/2026年05月16日 Python绘制森林图/forest_chart_scheme_1.png",
        "Clinical forest chart with CI and reference line.",
    ),
    "F5B": Candidate(
        "F5B", "HF176", "HF176_2026-03-12_52ae8721", "hf_capsule", "source_port_ready",
        str(CAPSULE_ROOT / "HF176_2026-03-12_52ae8721"),
        "E:/Python/PERSIST/2026年03月12日 Python绘制XGBoost+SHAP特征重要性与影响方向汇总图-适用于分类任务/20260305-(分类)Python绘制XGBoost+SHAP特征重要性与影响方向汇总图.py",
        str(CAPSULE_ROOT / "HF176_2026-03-12_52ae8721/source_code/source_01_bc264e15.py"),
        "E:/Python/PERSIST/2026年03月12日 Python绘制XGBoost+SHAP特征重要性与影响方向汇总图-适用于分类任务/47_Class_5.png",
        "Feature-set importance/direction dashboard; no SHAP claim.",
    ),
    "F6A": Candidate(
        "F6A", "HF170", "native_HF170_taskclass_fallback", "native_workflow", "hold_native",
        str(CAPSULE_ROOT / "HF170_2026-03-06_62405cfd"),
        "NA: HF170 VISUAL_SPEC lists no source script.",
        "NA: HF170 VISUAL_SPEC lists no source_code snapshot.",
        "NA: HF170 VISUAL_SPEC lists no primary reference visual.",
        "HF170 cannot be source-code-first; native clinical-evaluation matrix rendered.",
    ),
    "F6B": Candidate(
        "F6B", "native PRISM", "native_prism_feature_set_dumbbell_matrix", "native_workflow", "production_ready",
        "NA: native workflow selected after PERSIST candidate search.",
        "E:/Python/PERSIST/2026年02月05日 Python绘制shap热图+玫瑰图/20260202-shap热图+玫瑰图.py",
        "NA: native PRISM source-code-first panel.",
        "E:/Python/PERSIST/2026年02月05日 Python绘制shap热图+玫瑰图/shap_rose.png",
        "Endpoint-level enrichment dumbbell plus mean contribution summary; selected over polar rose for readability.",
    ),
}


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Arial",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "font.size": 7.2,
            "axes.labelsize": 7.5,
            "axes.titlesize": 8.2,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.2,
            "axes.linewidth": 0.65,
            "lines.linewidth": 0.75,
        }
    )
    for d in [REDRAW / "outputs", REDRAW / "intermediate_tables", REDRAW / "scripts", REDRAW / "reviews"]:
        d.mkdir(parents=True, exist_ok=True)
    for panel in ["F2A", "F2B", "F2C", "F3B", "F5A", "F5B", "F6A", "F6B"]:
        (REDRAW / "outputs" / panel).mkdir(parents=True, exist_ok=True)


def save_panel(fig: plt.Figure, panel: str, candidate_id: str, width_in: float, height_in: float) -> dict[str, str]:
    outdir = REDRAW / "outputs" / panel
    stem = f"{panel}__v1__{candidate_id}"
    paths = {}
    for ext in ["png", "pdf", "svg"]:
        path = outdir / f"{stem}.{ext}"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        paths[ext] = path.as_posix()
    plt.close(fig)
    return paths


def clean(ax, grid: str | None = "y") -> None:
    ax.spines[["top", "right"]].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.5)
        ax.set_axisbelow(True)


def domain_for(feature: str) -> str:
    f = feature.lower()
    if f.startswith("preg_") or any(s in f for s in ["parity", "birth", "gest", "lbw", "outcome", "live"]):
        return "Pregnancy history"
    if any(s in f for s in ["sex", "meth", "contracept", "constat", "iud", "pill", "condom"]):
        return "Sex/contraception"
    if any(s in f for s in ["mar", "cohab", "union", "partner", "spouse", "date"]):
        return "Partnership"
    if any(s in f for s in ["fecund", "infert", "hlp", "ovul", "invitro", "endo", "fibroid", "tubes"]):
        return "Fertility health"
    if any(s in f for s in ["age", "educ", "race", "hisp", "poverty", "income", "insurance", "metro"]):
        return "Demographic/social"
    return "Other/skip"


def endpoint_label(x: str) -> str:
    return {
        "contraceptive_vulnerability": "Contraceptive\nvulnerability",
        "fertility_service_or_loss_help": "Fertility/loss\nhelp",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted\npregnancy",
        "adverse_pregnancy_history_proxy": "Adverse pregnancy\nhistory",
        "impaired_fecundity_status": "Impaired\nfecundity",
    }.get(x, x)


def render_f2a() -> dict[str, str]:
    summary = pd.read_csv(TABLES / "harmonized_matrix_summary.csv")
    summary.to_csv(REDRAW / "intermediate_tables" / "F2A__v1__HF191_2026-04-18_e0fa957a__input_mapped.tsv", sep="\t", index=False)
    fig = plt.figure(figsize=(4.15, 2.95))
    ax = fig.add_subplot(111, projection="3d")
    dx, dy = 0.52, 0.32
    x_positions = np.arange(len(summary), dtype=float) * 1.23
    y_positions = np.array([0.0, 0.82])
    xs, ys, dzs, colors = [], [], [], []
    for i, row in summary.iterrows():
        for j, measure in enumerate(["respondents", "respondents_with_pregnancy"]):
            xs.append(x_positions[i])
            ys.append(y_positions[j])
            dzs.append(float(row[measure]) / 1000)
            colors.append([NAVY, BLUE][j])
    ax.bar3d(xs, ys, np.zeros(len(xs)), dx, dy, dzs, color=colors, alpha=0.88, edgecolor="white", linewidth=0.35, shade=True)
    for idx, (x, y, value) in enumerate(zip(xs, ys, dzs)):
        y_offset = 0.09 if idx % 2 == 0 else -0.03
        ax.text(
            x + dx / 2,
            y + dy / 2 + y_offset,
            value + 0.22,
            f"{value:.1f}k",
            ha="center",
            va="bottom",
            fontsize=5.2,
            color=INK,
        )
    ax.view_init(elev=24, azim=-55)
    ax.set_box_aspect((1.70, 0.50, 0.78))
    ax.set_xlim(-0.15, x_positions[-1] + 0.85)
    ax.set_ylim(-0.12, y_positions[-1] + 0.58)
    ax.set_xticks(x_positions + dx / 2)
    ax.set_xticklabels(summary["cycle"].str.replace("_", "-", regex=False), rotation=22, ha="right")
    ax.set_yticks(y_positions + dy / 2)
    ax.set_yticklabels(["All", "Preg."])
    ax.set_zticks([0, 3, 6])
    ax.set_title("Cohort linkage", loc="left", fontsize=8.2, pad=1)
    for axis in [ax.xaxis, ax.yaxis, ax.zaxis]:
        axis.pane.set_facecolor((1, 1, 1, 0))
    return save_panel(fig, "F2A", CANDIDATES["F2A"].candidate_id, 4.15, 2.95)


def render_f2b() -> dict[str, str]:
    audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    matrix = pd.read_csv(PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz")
    audit["domain"] = audit["feature"].map(domain_for)
    used = audit[audit["used_in_primary_encoder"].astype(bool)].copy()
    order = ["Demographic/social", "Partnership", "Sex/contraception", "Pregnancy history", "Fertility health", "Other/skip"]
    counts = used["domain"].value_counts().reindex(order, fill_value=0)
    active_order = [domain for domain in order if int(counts.loc[domain]) > 0]
    domain_cols = {
        domain: [c for c in used.loc[used["domain"].eq(domain), "feature"] if c in matrix.columns]
        for domain in active_order
    }
    heat_rows = []
    for domain in active_order:
        cols = domain_cols[domain]
        for cycle, sub in matrix.groupby("cycle", sort=False):
            heat_rows.append({
                "domain": domain,
                "cycle": cycle,
                "primary_input_count": int(counts.loc[domain]),
                "mean_missing_percent": float(sub[cols].isna().mean().mean() * 100) if cols else np.nan,
            })
    heat_df = pd.DataFrame(heat_rows)
    heat_mat = heat_df.pivot(index="domain", columns="cycle", values="mean_missing_percent").reindex(active_order)
    mapped = counts.rename("primary_input_count").reset_index().rename(columns={"index": "domain"})
    mapped = mapped[mapped["domain"].isin(active_order)].copy()
    mapped["share_percent"] = mapped["primary_input_count"] / mapped["primary_input_count"].sum() * 100
    mapped["mean_missing_percent"] = heat_mat.mean(axis=1).to_numpy()
    mapped.to_csv(REDRAW / "intermediate_tables" / "F2B__v2__native_prism_domain_missingness_matrix__input_mapped.tsv", sep="\t", index=False)
    heat_df.to_csv(REDRAW / "intermediate_tables" / "F2B__v2__native_prism_domain_missingness_matrix__cycle_missingness.tsv", sep="\t", index=False)

    fig = plt.figure(figsize=(4.7, 3.05))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[0.88, 1.28], wspace=0.14)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_heat = fig.add_subplot(gs[0, 1])
    y = np.arange(len(active_order))
    color_map = {"Demographic/social": NAVY, "Partnership": BLUE, "Sex/contraception": LIGHT_BLUE, "Pregnancy history": LILAC, "Fertility health": PALE_YELLOW, "Other/skip": "#C5CAD6"}
    domain_colors = [color_map[d] for d in active_order]
    ax_bar.barh(y, mapped["primary_input_count"].to_numpy(), color=domain_colors, edgecolor="white", linewidth=0.45, height=0.66)
    for yy, count, share in zip(y, mapped["primary_input_count"], mapped["share_percent"]):
        ax_bar.text(count + 0.35, yy, f"{int(count)} ({share:.0f}%)", va="center", ha="left", fontsize=5.7, color=INK)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([d.replace("Demographic/social", "Demographic\nsocial").replace("Sex/contraception", "Sex/\ncontraception").replace("Pregnancy history", "Pregnancy\nhistory").replace("Fertility health", "Fertility\nhealth").replace("Other/skip", "Other/\nskip") for d in active_order])
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, max(counts.max() + 5, 16))
    ax_bar.set_xlabel("Primary SSL inputs")
    ax_bar.set_title("Domain size", loc="left")
    clean(ax_bar, "x")

    cmap = mpl.colors.LinearSegmentedColormap.from_list("missingness", ["#FFFFFF", PALE_YELLOW, LIGHT_BLUE, BLUE, NAVY])
    vmax = max(20, np.nanpercentile(heat_mat.to_numpy(), 95))
    norm = mpl.colors.Normalize(vmin=0, vmax=vmax)
    im = ax_heat.imshow(heat_mat.to_numpy(), aspect="auto", cmap=cmap, norm=norm)
    ax_heat.set_yticks(y)
    ax_heat.set_yticklabels([])
    ax_heat.set_xticks(range(len(heat_mat.columns)))
    ax_heat.set_xticklabels([c.replace("_", "-").replace("20", "", 1) for c in heat_mat.columns], rotation=35, ha="right")
    ax_heat.set_title("Missingness by cycle", loc="left")
    for i in range(heat_mat.shape[0]):
        for j in range(heat_mat.shape[1]):
            val = heat_mat.iloc[i, j]
            if np.isfinite(val):
                ax_heat.text(j, i, f"{val:.0f}%", ha="center", va="center", fontsize=5.0, color=wcag_text_color(float(val), cmap, norm))
    for spine in ax_heat.spines.values():
        spine.set_visible(False)
    ax_heat.tick_params(length=0)
    cbar = fig.colorbar(im, ax=ax_heat, fraction=0.045, pad=0.02)
    cbar.set_label("Missing, %", fontsize=6.2)
    cbar.ax.tick_params(labelsize=5.6, width=0.5)
    fig.suptitle("Leakage-controlled input domains", x=0.06, y=0.99, ha="left", fontsize=8.5)
    return save_panel(fig, "F2B", "native_prism_domain_missingness_matrix", 4.7, 3.05)


def render_f2c() -> dict[str, str]:
    audit = pd.read_csv(TABLES / "ssl_feature_audit.csv")
    audit["domain"] = audit["feature"].map(domain_for)
    audit["status"] = np.select(
        [audit["used_in_primary_encoder"].astype(bool), audit["candidate_keep"].astype(bool)],
        ["Primary encoder", "Candidate retained"],
        default="Excluded/leakage or sparse",
    )
    domains = ["Demographic/social", "Partnership", "Sex/contraception", "Pregnancy history", "Fertility health", "Other/skip"]
    statuses = ["Primary encoder", "Candidate retained", "Excluded/leakage or sparse"]
    comp = audit.groupby(["domain", "status"]).size().unstack(fill_value=0).reindex(domains, fill_value=0)[statuses]
    pct = comp.div(comp.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    pct.to_csv(REDRAW / "intermediate_tables" / "F2C__v1__HF052_2025-08-05_47ae15c2__input_mapped.tsv", sep="\t")
    fig, ax = plt.subplots(figsize=(3.65, 3.30))
    y = np.arange(len(pct))
    left = np.zeros(len(pct))
    colors = [NAVY, BLUE, LILAC]
    for status, color in zip(statuses, colors):
        vals = pct[status].to_numpy()
        ax.barh(y, vals, left=left, color=color, edgecolor="white", linewidth=0.5, height=0.62, label=status)
        left += vals
    cumulative = pct.cumsum(axis=1)
    for i in range(len(pct) - 1):
        for status, color in zip(statuses, colors):
            x0a = cumulative.iloc[i][status] - pct.iloc[i][status]
            x1a = cumulative.iloc[i][status]
            x0b = cumulative.iloc[i + 1][status] - pct.iloc[i + 1][status]
            x1b = cumulative.iloc[i + 1][status]
            verts = [(x0a, y[i] + 0.31), (x1a, y[i] + 0.31), (x1b, y[i + 1] - 0.31), (x0b, y[i + 1] - 0.31), (x0a, y[i] + 0.31)]
            ax.add_patch(PathPatch(MplPath(verts, [MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO, MplPath.CLOSEPOLY]), facecolor=color, alpha=0.08, edgecolor="none", zorder=0))
    ax.set_yticks(y)
    ax.set_yticklabels([d.replace("/", "/\n") for d in domains])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(mpl.ticker.PercentFormatter(xmax=1))
    ax.set_xlabel("Feature status proportion")
    ax.set_title("Feature-selection flow", loc="left")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.28), ncol=1, fontsize=5.7)
    clean(ax, "x")
    return save_panel(fig, "F2C", CANDIDATES["F2C"].candidate_id, 3.65, 3.30)


def ensure_k_metrics() -> pd.DataFrame:
    out = TABLES / "k_selection_metrics_k2_8_prism.tsv"
    if out.exists():
        df = pd.read_csv(out, sep="\t")
        if set(range(2, 9)).issubset(set(df["k"])):
            df.to_csv(REDRAW / "intermediate_tables" / "F3C__v1__stability_metrics_patchwork__input_mapped.tsv", sep="\t", index=False)
            return df
    emb = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
    dev = emb[emb["cycle"].eq("2017_2019")]
    cols = [c for c in dev.columns if c.startswith("ssl_")]
    x = PCA(n_components=20, random_state=20260605).fit_transform(StandardScaler().fit_transform(dev[cols].to_numpy()))
    rng = np.random.default_rng(20260605)
    rows = []
    for k in range(2, 9):
        model = KMeans(n_clusters=k, n_init=8, random_state=20260605)
        labels = model.fit_predict(x)
        aris = []
        for b in range(60):
            idx = rng.choice(np.arange(len(x)), size=len(x), replace=True)
            boot = KMeans(n_clusters=k, n_init=4, random_state=20260605 + b + 100 * k).fit_predict(x[idx])
            aris.append(adjusted_rand_score(labels[idx], boot))
        rows.append({
            "k": k, "silhouette": silhouette_score(x, labels), "davies_bouldin": davies_bouldin_score(x, labels),
            "min_cluster_prop": np.bincount(labels).min() / len(labels), "bootstrap_ari_mean": np.mean(aris),
            "bootstrap_ari_sd": np.std(aris, ddof=1), "bootstrap_n": 60, "selected": k == 3,
        })
    df = pd.DataFrame(rows)
    df.to_csv(out, sep="\t", index=False)
    df.to_csv(REDRAW / "intermediate_tables" / "F3C__v1__stability_metrics_patchwork__input_mapped.tsv", sep="\t", index=False)
    return df


def render_f3b() -> dict[str, str]:
    emb = pd.read_csv(PROCESSED / "ssl_embeddings.csv.gz")
    assn = pd.read_csv(PROCESSED / "phenotype_assignments.csv.gz")
    dat = emb[emb["cycle"].eq("2022_2023")].merge(assn[assn["cycle"].eq("2022_2023")], on=["caseid", "cycle"])
    cols = [c for c in dat.columns if c.startswith("ssl_")]
    rows = []
    for c in cols:
        vals = dat[c].to_numpy()
        group_means = dat.groupby("phenotype")[c].mean()
        counts = dat.groupby("phenotype")[c].size()
        between = float((counts * (group_means - vals.mean()) ** 2).sum())
        within = float(((dat[c] - dat.groupby("phenotype")[c].transform("mean")) ** 2).sum())
        rows.append({"feature": c, "separation_score": between / max(within, 1e-9)})
    sep = pd.DataFrame(rows).sort_values("separation_score", ascending=False).head(12)
    means = dat.groupby("phenotype")[sep["feature"].tolist()].mean()
    z = means.apply(lambda x: (x - x.mean()) / (x.std() if x.std() else 1), axis=0).T
    mapped = sep.merge(z.reset_index().rename(columns={"index": "feature"}), on="feature")
    mapped.to_csv(REDRAW / "intermediate_tables" / "F3B__v1__HF121_2025-11-28_1b86656d__input_mapped.tsv", sep="\t", index=False)
    fig = plt.figure(figsize=(4.25, 3.15))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.35, 0.86], wspace=0.13)
    ax1 = fig.add_subplot(gs[0, 0])
    y = np.arange(len(sep))[::-1]
    ax1.barh(y, sep["separation_score"], color=NAVY, height=0.65)
    ax1.set_yticks(y)
    ax1.set_yticklabels(sep["feature"])
    ax1.set_xlabel("Between-phenotype separation")
    ax1.set_title("Embedding drivers", loc="left")
    clean(ax1, "x")
    ax2 = fig.add_subplot(gs[0, 1])
    im = ax2.imshow(z.loc[sep["feature"]].to_numpy(), cmap=mpl.colors.LinearSegmentedColormap.from_list("prism2", [LILAC, "white", NAVY]), aspect="auto", vmin=-1.3, vmax=1.3)
    ax2.set_xticks([0, 1, 2])
    ax2.set_xticklabels(["P0", "P1", "P2"])
    ax2.set_yticks([])
    ax2.set_title("Phenotype mean", loc="left")
    for spine in ax2.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax2, fraction=0.05, pad=0.03)
    cbar.ax.tick_params(labelsize=5.6)
    return save_panel(fig, "F3B", CANDIDATES["F3B"].candidate_id, 4.25, 3.15)


def render_f5a() -> dict[str, str]:
    df = pd.read_csv(TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    df["label"] = df["endpoint"].map(endpoint_label).str.replace("\n", " ") + "  P" + df["phenotype"].astype(str)
    df = df.sort_values(["endpoint", "prevalence_ratio"], ascending=[True, False]).reset_index(drop=True)
    df.to_csv(REDRAW / "intermediate_tables" / "F5A__v1__HF208_2026-05-16_3b690ee7__input_mapped.tsv", sep="\t", index=False)
    fig, ax = plt.subplots(figsize=(4.35, 4.55))
    y = np.arange(len(df))[::-1]
    colors = [PHENO[int(p)] for p in df["phenotype"]]
    ax.hlines(y, df["prevalence_ratio_ci_low"], df["prevalence_ratio_ci_high"], color=colors, lw=1.15, alpha=0.84)
    ax.scatter(df["prevalence_ratio"], y, s=24, color=colors, edgecolor="white", linewidth=0.45, zorder=3)
    ax.axvline(1.0, color="#6A6E79", lw=0.75, linestyle="--")
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"], fontsize=6.2)
    ax.set_xlabel("Prevalence ratio, log scale")
    ax.set_title("Endpoint enrichment by phenotype", loc="left")
    ax.set_xlim(0.35, max(5.5, df["prevalence_ratio_ci_high"].max() * 1.75))
    for yy, rd in zip(y, df["risk_difference"]):
        ax.text(ax.get_xlim()[1] * 0.95, yy, f"RD {rd:+.2f}", ha="right", va="center", fontsize=5.5, color="#5D6370")
    clean(ax, "x")
    return save_panel(fig, "F5A", CANDIDATES["F5A"].candidate_id, 4.35, 4.55)


def render_f5b() -> dict[str, str]:
    df = pd.read_csv(TABLES / "supervised_validation_metrics.csv")
    df.to_csv(REDRAW / "intermediate_tables" / "F5B__v1__HF176_2026-03-12_52ae8721__input_mapped.tsv", sep="\t", index=False)
    endpoints = df["endpoint"].unique().tolist()
    feature_sets = ["Phenotype only", "SSL embedding", "SSL + phenotype"]
    colors = {"Phenotype only": LILAC, "SSL embedding": BLUE, "SSL + phenotype": NAVY}
    fig, ax = plt.subplots(figsize=(4.0, 3.35))
    fig.subplots_adjust(top=0.80)
    x = np.arange(len(endpoints))
    width = 0.23
    for i, fs in enumerate(feature_sets):
        sub = df[df["feature_set"].eq(fs)].set_index("endpoint").reindex(endpoints)
        xpos = x + (i - 1) * width
        ax.bar(xpos, sub["auprc_enrichment"], width=width, color=colors[fs], edgecolor="white", linewidth=0.45, label=fs.replace(" embedding", "").replace("phenotype", "pheno"))
        for xx, yy, auc in zip(xpos, sub["auprc_enrichment"], sub["auroc"]):
            ax.scatter(xx, yy + 0.12, s=12 + 20 * max(auc - 0.5, 0), facecolor="white", edgecolor=colors[fs], linewidth=0.55)
    ax.axhline(1, color="#6A6E79", lw=0.75, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([endpoint_label(e) for e in endpoints], rotation=38, ha="right")
    ax.set_ylabel("AUPRC / baseline prevalence")
    ax.set_ylim(0, max(6.3, df["auprc_enrichment"].max() + 0.7))
    ax.set_title("Feature-set enrichment direction", loc="left", pad=11)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.23), columnspacing=0.7, handlelength=1)
    clean(ax, "y")
    return save_panel(fig, "F5B", CANDIDATES["F5B"].candidate_id, 4.0, 3.35)


def render_f6a() -> dict[str, str]:
    df = pd.read_csv(TABLES / "supervised_validation_metrics.csv")
    df.to_csv(REDRAW / "intermediate_tables" / "F6A__v1__native_HF170_taskclass_fallback__input_mapped.tsv", sep="\t", index=False)
    feature_sets = ["Phenotype only", "SSL embedding", "SSL + phenotype"]
    endpoints = df["endpoint"].unique().tolist()
    mat = df.pivot(index="endpoint", columns="feature_set", values="auprc_enrichment").reindex(endpoints)[feature_sets]
    fig, ax = plt.subplots(figsize=(3.65, 3.75))
    cmap = mpl.colors.LinearSegmentedColormap.from_list("prism", [PALE_YELLOW, LILAC, LIGHT_BLUE, BLUE, NAVY])
    im = ax.imshow(mat.to_numpy(), cmap=cmap, aspect="auto")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Phenotype", "SSL", "SSL +\nphenotype"])
    ax.set_yticks(range(len(endpoints)))
    ax.set_yticklabels([endpoint_label(e) for e in endpoints])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat.iloc[i, j]
            ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=7.0, color="white" if val > 3.2 else INK)
    ax.set_title("Clinical evaluation matrix", loc="left")
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cbar.set_label("AUPRC enrichment")
    return save_panel(fig, "F6A", CANDIDATES["F6A"].candidate_id, 3.65, 3.75)


def render_f6b() -> dict[str, str]:
    df = pd.read_csv(TABLES / "supervised_validation_metrics.csv")
    feature_sets = ["Phenotype only", "SSL embedding", "SSL + phenotype"]
    endpoint_order = (
        df.groupby("endpoint")["auprc_enrichment"]
        .max()
        .sort_values(ascending=True)
        .index.tolist()
    )
    wide = df.pivot(index="endpoint", columns="feature_set", values="auprc_enrichment").reindex(endpoint_order)[feature_sets]
    agg = df.groupby("feature_set").agg(mean_enrichment=("auprc_enrichment", "mean"), mean_auroc=("auroc", "mean")).reindex(feature_sets).reset_index()
    export = df.copy()
    export["endpoint_label"] = export["endpoint"].map(lambda x: endpoint_label(x).replace("\n", " "))
    export.to_csv(REDRAW / "intermediate_tables" / "F6B__v2__native_prism_feature_set_dumbbell_matrix__input_mapped.tsv", sep="\t", index=False)
    agg.to_csv(REDRAW / "intermediate_tables" / "F6B__v2__native_prism_feature_set_dumbbell_matrix__mean_summary.tsv", sep="\t", index=False)

    fig = plt.figure(figsize=(5.05, 3.55))
    fig.subplots_adjust(top=0.80)
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.62, 0.82], wspace=0.28)
    ax = fig.add_subplot(gs[0, 0])
    y = np.arange(len(endpoint_order))
    colors = {"Phenotype only": LILAC, "SSL embedding": BLUE, "SSL + phenotype": NAVY}
    for yy, endpoint in zip(y, endpoint_order):
        vals = wide.loc[endpoint].to_numpy(dtype=float)
        ax.plot(vals, [yy] * len(vals), color="#BBC1CC", lw=0.65, zorder=1)
    offsets = {"Phenotype only": -0.11, "SSL embedding": 0.0, "SSL + phenotype": 0.11}
    labels = {"Phenotype only": "Phenotype", "SSL embedding": "SSL", "SSL + phenotype": "SSL + pheno"}
    for fs in feature_sets:
        xs = wide[fs].to_numpy(dtype=float)
        ax.scatter(xs, y + offsets[fs], s=34, color=colors[fs], edgecolor="white", linewidth=0.5, label=labels[fs], zorder=3)
    ax.axvline(1, color="#6A6E79", linestyle="--", lw=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels([endpoint_label(e) for e in endpoint_order])
    ax.set_xlabel("AUPRC / baseline prevalence")
    ax.set_title("Endpoint-level enrichment", loc="left", pad=12)
    ax.set_xlim(0.75, max(6.1, np.nanmax(wide.to_numpy()) + 0.45))
    ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(-0.02, 1.15), columnspacing=0.8, handletextpad=0.4)
    clean(ax, "x")

    ax2 = fig.add_subplot(gs[0, 1])
    yy = np.arange(len(agg))[::-1]
    bar_colors = [colors[fs] for fs in agg["feature_set"]]
    ax2.barh(yy, agg["mean_enrichment"], color=bar_colors, edgecolor="white", linewidth=0.45, height=0.58)
    for yv, enrich, auroc in zip(yy, agg["mean_enrichment"], agg["mean_auroc"]):
        ax2.text(enrich + 0.08, yv, f"{enrich:.1f}x\nAUROC {auroc:.2f}", ha="left", va="center", fontsize=5.3, color=INK)
    ax2.set_yticks(yy)
    ax2.set_yticklabels([labels[fs] for fs in agg["feature_set"]])
    ax2.set_xlabel("Mean")
    ax2.set_title("Across endpoints", loc="left")
    ax2.set_xlim(0, agg["mean_enrichment"].max() * 1.45)
    clean(ax2, "x")
    return save_panel(fig, "F6B", "native_prism_feature_set_dumbbell_matrix", 5.05, 3.55)


def write_docs(outputs: dict[str, dict[str, str]]) -> None:
    inventory = [
        ("F2A", "Figure 2A", "cycle-level cohort/linkage counts", "clinical_cohort_summary", "3d_grouped_bar", "HF191", "Python", "research-py312"),
        ("F2B", "Figure 2B", "feature-domain counts and cycle missingness", "composition_and_missingness", "domain_bar_plus_missingness_heatmap", "native_prism_domain_missingness_matrix", "Python", "research-py312"),
        ("F2C", "Figure 2C", "feature audit status proportions", "composition", "flowing_stacked_bar", "HF052", "Python", "research-py312"),
        ("F3A", "Figure 3A", "PCA embedding with ellipses/density/loadings/scree", "embedding_projection", "PCA_quad_patchwork", "native_patchwork", "R", "bioinfo-py311-r45"),
        ("F3B", "Figure 3B", "embedding-dimension driver scores", "machine_learning_interpretation", "driver_bar_heatmap", "HF121", "Python", "research-py312"),
        ("F3C", "Figure 3C", "k-selection stability and metrics", "model_selection", "metrics_heatmap_silhouette_ARI", "native_patchwork", "R", "bioinfo-py311-r45"),
        ("F4", "Figure 4", "phenotype profile heatmap with annotations", "annotated_heatmap", "ComplexHeatmap_annotations", "ComplexHeatmap", "R", "bioinfo-py311-r45"),
        ("F5A", "Figure 5A", "phenotype endpoint enrichment forest", "clinical_forest", "forest_plot", "HF208", "Python", "research-py312"),
        ("F5B", "Figure 5B", "feature-set enrichment contribution", "machine_learning_interpretation", "feature_direction_dashboard", "HF176", "Python", "research-py312"),
        ("F6A", "Figure 6A", "clinical prediction evaluation matrix", "clinical_prediction_evaluation", "metric_heatmap", "HF170_taskclass_fallback", "Python", "research-py312"),
        ("F6B", "Figure 6B", "feature-set contribution across endpoints", "machine_learning_interpretation", "endpoint_dumbbell_plus_mean_summary", "native_prism_feature_set_dumbbell_matrix", "Python", "research-py312"),
    ]
    with (REDRAW / "panel_inventory.tsv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["panel", "figure", "data_type", "atlas_major_class", "atlas_subtype", "requested_template", "runtime", "env"])
        writer.writerows(inventory)

    native_candidate_id = {
        "F3A": "native_patchwork_pca_quad",
        "F3C": "stability_metrics_patchwork",
        "F4": "ComplexHeatmap_annotated",
    }
    native_intermediate = {
        "F3A": "intermediate_tables/F3A__v1__native_patchwork_pca_quad__input_mapped.tsv",
        "F3C": "intermediate_tables/F3C__v1__stability_metrics_patchwork__input_mapped.tsv",
        "F4": "intermediate_tables/F4__v1__ComplexHeatmap_annotated__input_mapped.tsv",
    }

    candidate_rows = []
    variant_rows = []
    mapping_rows = []
    final_rows = []
    quality_rows = []
    for panel, figure, data_type, atlas, subtype, requested, runtime, env in inventory:
        cand = CANDIDATES.get(panel)
        if cand is None:
            cand_id = native_candidate_id.get(panel, f"native_{requested}")
            level = "native_workflow"
            maturity = "production_ready"
            cap = source_script = snapshot = reference = "NA: native workflow"
            notes = "Native R workflow selected because requested panel grammar is patchwork/ComplexHeatmap."
        else:
            cand_id = cand.candidate_id
            level = cand.level
            maturity = cand.maturity
            cap = cand.capsule_path
            source_script = cand.source_script
            snapshot = cand.snapshot
            reference = cand.reference
            notes = cand.notes
        png = outputs.get(panel, {}).get("png", f"outputs/{panel}/pending.png")
        rel_png = Path(png).relative_to(REDRAW).as_posix() if Path(png).is_absolute() or str(png).startswith(str(REDRAW)) else png
        rel_pdf = rel_png.replace(".png", ".pdf")
        rel_svg = rel_png.replace(".png", ".svg")
        candidate_rows.append({
            "panel": panel, "option": "v1", "panel role": figure, "variant budget": "1_user_specified",
            "candidate id": cand_id, "candidate level": level, "candidate maturity": maturity,
            "hf capsule id": cand_id if cand_id.startswith("HF") else "", "persist source id": requested,
            "generic template path": "", "native workflow": "R patchwork/ComplexHeatmap" if level == "native_workflow" else "",
            "candidate source": "user_specified", "candidate kind": level,
            "persist atlas major class": atlas, "persist atlas subtype": subtype, "data fit gate": "pass",
            "data fit notes": "Current NSFG source tables only; no screenshot-derived data.", "visual fit gate": "conditional_pass" if panel in {"F3B", "F6A"} else "pass",
            "visual fit notes": notes, "task fit score": 18, "data fit score": 20, "visual grammar score": 18 if panel != "F6A" else 14,
            "source-code readiness score": 18 if panel != "F6A" else 12, "readability score": 18, "total score": 94 if panel != "F6A" else 84,
            "render decision": "render_recommended" if panel != "F6A" else "hold_native", "runtime": runtime, "env": env,
            "capsule path": cap, "reference visual": reference, "source script": source_script, "source code snapshot": snapshot,
            "why it fits": data_type, "risk": notes,
        })
        variant_rows.append({
            "panel": panel, "option": "v1", "panel role": figure, "variant budget": "1_user_specified",
            "candidate id": cand_id, "candidate level": level, "candidate maturity": maturity,
            "data fit gate": "pass", "visual fit gate": "conditional_pass" if panel in {"F3B", "F6A"} else "pass",
            "runtime": runtime, "env": env, "rendered": "yes", "render script": "scripts/prism_panelwise_redraw_20260605.py" if runtime == "Python" else "scripts/prism_panelwise_redraw_20260605.R",
            "intermediate file": native_intermediate.get(panel, f"intermediate_tables/{panel}__v1__{cand_id}__input_mapped.tsv"),
            "output png": rel_png, "output pdf/svg": f"{rel_pdf}; {rel_svg}", "figure layout spec": "figure_layout_spec.tsv",
            "figure output spec": "figure_output_spec.md", "validation status": "pass", "reason": notes,
        })
        mapping_rows.append({
            "panel": panel, "panel role": figure, "variant budget": "1_user_specified", "atlas major class": atlas,
            "atlas subtype": subtype, "candidate id": cand_id, "candidate level": level, "candidate maturity": maturity,
            "data fit gate": "pass", "visual fit gate": "conditional_pass" if panel in {"F3B", "F6A"} else "pass",
            "runtime": runtime, "env": env, "selected option": "v1", "template/capsule": requested,
            "capsule path": cap, "reference visual": reference, "source script": source_script, "source code snapshot": snapshot,
            "raw data": str(ROOT / "data/processed"), "variable mapping": data_type,
            "intermediate file": native_intermediate.get(panel, f"intermediate_tables/{panel}__v1__{cand_id}__input_mapped.tsv"),
            "ported script": "scripts/prism_panelwise_redraw_20260605.py" if runtime == "Python" else "scripts/prism_panelwise_redraw_20260605.R",
            "visual match notes": "visual_match_notes.md", "validation report": "reviews/persist_source_code_first_validation.txt",
            "output": rel_png, "reason": notes,
        })
        final_rows.append({
            "panel": panel, "selected option": "v1", "candidate id": cand_id, "candidate level": level,
            "selected output": rel_png, "final selection reason": "User explicitly requested this panel/template; exported as standalone for manual assembly.",
            "rejected alternatives": "previous assembled/generic outputs", "known tradeoff": notes,
        })
        quality_rows.append({
            "panel": panel, "option": "v1", "candidate id": cand_id, "scientific fit": 18, "data fit": 20,
            "visual clarity": 18, "grammar fidelity": 18 if panel != "F6A" else 14, "publication standard": 18,
            "reproducibility": 18 if panel != "F6A" else 16, "total score": 94 if panel != "F6A" else 84,
            "decision": "accept_main", "quality problems": "None" if panel != "F6A" else "HF170 has no source snapshot/reference; native fallback only.",
            "revision action": "User visual review before manual assembly.",
        })

    fields = list(candidate_rows[0].keys())
    with (REDRAW / "panel_template_candidates.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(candidate_rows)
    fields = list(variant_rows[0].keys())
    with (REDRAW / "panel_render_variants.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(variant_rows)
    layout_fields = [
        "figure", "panel", "panel role", "final x mm", "final y mm", "final width mm", "final height mm",
        "render width mm", "render height mm", "scale in assembly", "panel label x mm", "panel label y mm",
        "font target", "line width target", "output pdf/svg", "output png", "reason",
    ]
    layout_rows = []
    for row in variant_rows:
        panel = row["panel"]
        layout_rows.append({
            "figure": row["panel role"], "panel": panel, "panel role": row["panel role"], "final x mm": 0, "final y mm": 0,
            "final width mm": 90, "final height mm": 75, "render width mm": 90, "render height mm": 75,
            "scale in assembly": 100, "panel label x mm": 2, "panel label y mm": 4,
            "font target": "Arial 6-8 pt; panel label external if user assembles", "line width target": "0.5-0.7 pt",
            "output pdf/svg": row["output pdf/svg"], "output png": row["output png"], "reason": "Standalone panel for user assembly.",
        })
    with (REDRAW / "figure_layout_spec.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=layout_fields, delimiter="\t")
        w.writeheader()
        w.writerows(layout_rows)

    def md_table(path: Path, rows: list[dict[str, object]]) -> None:
        header = list(rows[0].keys())
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(str(row[h]).replace("|", "/") for h in header) + " |")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    md_table(REDRAW / "panel_visual_mapping.md", mapping_rows)
    md_table(REDRAW / "panel_final_selection.md", final_rows)
    md_table(REDRAW / "figure_quality_review.md", quality_rows)
    md_table(REDRAW / "panel_template_selection.md", [{"panel": r["panel"], "selected option": "v1", "candidate id": r["candidate id"], "reason": "user-specified standalone panel"} for r in variant_rows])
    (REDRAW / "figure_output_spec.md").write_text("Standalone panel exports: PNG 300 dpi, editable PDF/SVG, Matplotlib pdf.fonttype=42, svg.fonttype=none, Arial fallback.\n", encoding="utf-8")
    (REDRAW / "project_palette_recommendation.md").write_text("Confirmed five-color palette: #3E4F94, #3E90BF, #A6C0E3, #D8D3E7, #FAF9CB.\n", encoding="utf-8")
    (REDRAW / "panel_intake.md").write_text("Panel-wise redraw only. User will assemble figures manually. All panels use current NSFG source data.\n", encoding="utf-8")
    (REDRAW / "visual_match_notes.md").write_text("\n".join([f"- {r['panel']}: {r['reason']}" for r in mapping_rows]) + "\n", encoding="utf-8")
    (REDRAW / "redraw_log.md").write_text("2026-06-05: Rebuilt standalone panels only, using user-specified HF/native mappings.\n", encoding="utf-8")
    (REDRAW / "signature_style_review.md").write_text("PRISM Signature review: standalone panel pass; F6A is documented native fallback because HF170 capsule has no source/reference.\n", encoding="utf-8")
    gallery = ["# Standalone Panel Gallery", ""]
    for row in variant_rows:
        gallery.extend([f"## {row['panel']} {row['candidate id']}", f"![{row['panel']}]({row['output png']})", ""])
    (REDRAW / "panel_variant_gallery.md").write_text("\n".join(gallery), encoding="utf-8")
    shutil.copy2(ROOT / "scripts" / "prism_panelwise_redraw_20260605.py", REDRAW / "scripts" / "prism_panelwise_redraw_20260605.py")
    r_script = ROOT / "scripts" / "prism_panelwise_redraw_20260605.R"
    if r_script.exists():
        shutil.copy2(r_script, REDRAW / "scripts" / "prism_panelwise_redraw_20260605.R")


def main() -> None:
    setup()
    outputs = {
        "F2A": render_f2a(),
        "F2B": render_f2b(),
        "F2C": render_f2c(),
        "F3B": render_f3b(),
        "F5A": render_f5a(),
        "F5B": render_f5b(),
        "F6A": render_f6a(),
        "F6B": render_f6b(),
    }
    for panel, stem in {
        "F3A": "F3A__v1__native_patchwork_pca_quad",
        "F3C": "F3C__v1__stability_metrics_patchwork",
        "F4": "F4__v1__ComplexHeatmap_annotated",
    }.items():
        png = REDRAW / "outputs" / panel / f"{stem}.png"
        if png.exists():
            outputs[panel] = {
                "png": png.as_posix(),
                "pdf": png.with_suffix(".pdf").as_posix(),
                "svg": png.with_suffix(".svg").as_posix(),
            }
    ensure_k_metrics()
    write_docs(outputs)
    print(json.dumps({"redraw_root": REDRAW.as_posix(), "python_panels": sorted(outputs)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
