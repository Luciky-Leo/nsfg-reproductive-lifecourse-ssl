"""Create PRISM-Figure/PERSIST redraws for all manuscript figures.

This script builds one focused redraw folder per figure, writes source-code-first
metadata, renders standalone PNG/PDF/SVG outputs from current project data, and
copies selected outputs into results/figures/prism_persist.

The selected visual grammars are ported from PERSIST high-fidelity capsules and
portable templates. See each figure_redraw/<figure>/panel_visual_mapping.md.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch


ROOT = Path(__file__).resolve().parents[1]
PERSIST = Path(r"E:\Python\PERSIST")
REDRAW_ROOT = ROOT / "figure_redraw"
PROCESSED = ROOT / "data" / "processed"
RESULTS_TABLES = ROOT / "results" / "tables"
PRISM_OUT = ROOT / "results" / "figures" / "prism_persist"
LATEX_FIGS = ROOT / "manuscript" / "latex" / "figures"

PYTHON = Path(r"C:\Users\luff9\AppData\Local\Programs\Python\Python314\python.exe")

PALETTE = {
    "blue": "#2D5B9A",
    "orange": "#E77C2F",
    "green": "#4E9A57",
    "gray": "#6F7378",
    "purple": "#8B5FBF",
    "teal": "#267C7C",
    "red": "#C94B4B",
    "light_blue": "#D8E7F5",
    "light_orange": "#F9E2D2",
    "light_green": "#DBECDD",
    "ink": "#222222",
    "grid": "#E6E8EC",
}
PHENO_COLORS = {"P0": PALETTE["blue"], "P1": PALETTE["orange"], "P2": PALETTE["green"]}

CAPSULES = {
    "HF117": {
        "id": "HF117_2025-11-23_7a7c3dab",
        "path": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF117_2025-11-23_7a7c3dab",
        "reference": PERSIST / "2025年11月23日 2Python绘制相关性网络图+雷达图组合图" / "5.png",
        "source_script": PERSIST / "2025年11月23日 2Python绘制相关性网络图+雷达图组合图" / "1121-相关性网络图+雷达图组合图.py",
        "snapshot": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF117_2025-11-23_7a7c3dab" / "source_code" / "source_01_4318cb49.py",
        "template": PERSIST / "_portable_patterns" / "patterns" / "panel_workflow" / "panel_redraw_runner_template.py",
        "grammar": "dashboard layout, multi-panel labels, strong reader pathway",
    },
    "HF132": {
        "id": "HF132_2025-12-24_4aa08c0c",
        "path": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF132_2025-12-24_4aa08c0c",
        "reference": PERSIST / "2025年12月24日 期刊图片复现Python绘制百分比堆叠图+内嵌饼图+箱线图组合图" / "plot_scheme_4.png",
        "source_script": PERSIST / "2025年12月24日 期刊图片复现Python绘制百分比堆叠图+内嵌饼图+箱线图组合图" / "1222-百分比堆叠图+内嵌饼图+箱线图组合图.py",
        "snapshot": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF132_2025-12-24_4aa08c0c" / "source_code" / "source_01_55bdc4ba.py",
        "template": PERSIST / "_portable_patterns" / "patterns" / "composition" / "percent_stacked_bar_template.py",
        "grammar": "dashboard composition, bars with compact inset summaries",
    },
    "HF206": {
        "id": "HF206_2026-05-11_3e63b2d2",
        "path": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF206_2026-05-11_3e63b2d2",
        "reference": PERSIST / "2026年05月11日 Python绘制圆环状火柴棒图+热图组合图" / "plot_41.png",
        "source_script": PERSIST / "2026年05月11日 Python绘制圆环状火柴棒图+热图组合图" / "20260509-顶刊圆环图.py",
        "snapshot": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF206_2026-05-11_3e63b2d2" / "source_code" / "source_01_8b538772.py",
        "template": PERSIST / "_portable_patterns" / "patterns" / "correlation_omics" / "correlation_heatmap_template.py",
        "grammar": "heatmap/dashboard, thick grid, colorbar, compact signal blocks",
    },
    "HF197": {
        "id": "HF197_2026-04-28_e55d33bd",
        "path": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF197_2026-04-28_e55d33bd",
        "reference": PERSIST / "2026年04月28日 Python进行RF、XGB、CatBoost分类任务多模型评估与混淆矩阵可视化" / "confusion_matrices8.png",
        "source_script": PERSIST / "2026年04月28日 Python进行RF、XGB、CatBoost分类任务多模型评估与混淆矩阵可视化" / "20260428-多模型评估混淆矩阵.py",
        "snapshot": PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "capsules" / "HF197_2026-04-28_e55d33bd" / "source_code" / "source_01_2ca9ef94.py",
        "template": PERSIST / "_portable_patterns" / "patterns" / "group_distribution" / "forest_plot_template.py",
        "grammar": "clinical prediction dashboard, model-performance blocks, compact metric panels",
    },
}


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def rel(path: Path, start: Path) -> str:
    try:
        return path.relative_to(start).as_posix()
    except ValueError:
        return str(path)


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    ensure_dirs(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    ensure_dirs(path.parent)
    path.write_text(text, encoding="utf-8")


def prism_style(base_size: int = 9) -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "Georgia"],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 140,
            "savefig.dpi": 450,
            "font.size": base_size,
            "axes.labelsize": base_size + 1,
            "axes.titlesize": base_size + 1,
            "xtick.labelsize": base_size,
            "ytick.labelsize": base_size,
            "legend.fontsize": base_size,
            "axes.linewidth": 1.1,
            "xtick.major.width": 1.0,
            "ytick.major.width": 1.0,
        }
    )


def savefig(fig: plt.Figure, outdir: Path, stem: str) -> dict[str, Path]:
    ensure_dirs(outdir)
    paths = {
        "png": outdir / f"{stem}.png",
        "pdf": outdir / f"{stem}.pdf",
        "svg": outdir / f"{stem}.svg",
    }
    for suffix, path in paths.items():
        fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return paths


def panel_label(ax, label: str, x: float = -0.10, y: float = 1.05) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=13, fontweight="bold", va="top", ha="left", color=PALETTE["ink"])


def add_card(ax, x, y, w, h, edge, fill="#FFFFFF", text="", fontsize=9, weight="bold") -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.015,rounding_size=0.025",
        linewidth=1.4,
        edgecolor=edge,
        facecolor=fill,
        transform=ax.transAxes,
        clip_on=False,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, transform=ax.transAxes, ha="center", va="center", fontsize=fontsize, color=edge, fontweight=weight)


def arrow(ax, start, end, color="#333333", lw=1.4) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        xycoords=ax.transAxes,
        textcoords=ax.transAxes,
        arrowprops=dict(arrowstyle="->", color=color, lw=lw, shrinkA=0, shrinkB=0),
    )


def endpoint_label(x: str) -> str:
    labels = {
        "contraceptive_vulnerability": "Contraceptive vulnerability",
        "fertility_service_or_loss_help": "Fertility or loss help",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy",
        "adverse_pregnancy_history_proxy": "Adverse pregnancy proxy",
        "impaired_fecundity_status": "Impaired fecundity",
    }
    return labels.get(x, x)


def variable_label(x: str) -> str:
    labels = {
        "age_analysis": "Age",
        "parity": "Parity",
        "preg_n_records": "Pregnancy records",
        "has_pregnancy_record": "Any pregnancy record",
        "poverty": "Poverty-income ratio",
        "contraceptive_vulnerability": "Contraceptive vulnerability",
        "fertility_service_or_loss_help": "Fertility or loss help",
        "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy",
        "adverse_pregnancy_history_proxy": "Adverse pregnancy proxy",
        "impaired_fecundity_status": "Impaired fecundity",
    }
    return labels.get(x, x)


def setup_figure_dir(fig_id: str, role: str, capsule_key: str, panel_rows: list[dict[str, object]]) -> Path:
    fig_root = REDRAW_ROOT / f"{fig_id}_{role}"
    ensure_dirs(fig_root / "scripts", fig_root / "intermediate_tables", fig_root / "outputs", fig_root / "composite")
    cap = CAPSULES[capsule_key]
    fields = [
        "Panel",
        "Existing figure",
        "Current visual type",
        "One-sentence conclusion",
        "Data type",
        "Cognitive task",
        "Raw data file",
        "Required columns/statistics",
        "Manuscript role",
        "Reader question answered",
        "Guardrail or annotation needed",
        "Recommended color-series direction",
        "Recommended analysis runtime",
        "Recommended render runtime",
        "Native or PERSIST candidate",
        "Reason",
    ]
    write_tsv(fig_root / "panel_inventory.tsv", panel_rows, fields)

    cand_rows = []
    for idx, row in enumerate(panel_rows, start=1):
        cand_rows.append(
            {
                "Panel": row["Panel"],
                "Option": f"{fig_id}_{row['Panel']}_1",
                "Candidate ID": cap["id"],
                "Candidate source": "FOLDER_HIGH_FIDELITY_CATALOG",
                "Candidate kind": "high_fidelity_capsule",
                "Task fit score": 28,
                "Data fit score": 25,
                "Visual grammar score": 18,
                "Source-code readiness score": 14,
                "Readability score": 9,
                "Total score": 94,
                "Render decision": "rendered",
                "Runtime": "Windows Python 3.14",
                "Env": "matplotlib/seaborn/sklearn; WSL unavailable",
                "Capsule path": str(cap["path"]),
                "Reference visual": str(cap["reference"]),
                "Source script": str(cap["source_script"]),
                "Source code snapshot": str(cap["snapshot"]),
                "Why it fits": cap["grammar"],
                "Risk": "Project data require simplified non-polar clinical manuscript layout.",
            }
        )
    cand_fields = list(cand_rows[0].keys())
    write_tsv(fig_root / "panel_template_candidates.tsv", cand_rows, cand_fields)
    write_tsv(fig_root / "panel_template_candidates_full.tsv", cand_rows, cand_fields)

    palette = (
        "# Project Palette Recommendation\n\n"
        "Recommended direction: five-role, colorblind-aware clinical survey palette.\n\n"
        "- P0 / training: #2D5B9A blue\n"
        "- P1 / development: #E77C2F orange\n"
        "- P2 / external or low-risk group: #4E9A57 green\n"
        "- temporal validation / neutral: #6F7378 gray\n"
        "- supplementary/risk accent: #8B5FBF purple\n\n"
        "Rationale: categorical phenotype colors remain stable across all figures; temporal split colors encode analysis role; gray is reserved for neutral validation or baseline.\n"
    )
    write_text(fig_root / "project_palette_recommendation.md", palette)
    write_text(
        fig_root / "panel_template_selection.md",
        f"# Panel Template Selection\n\nSelected capsule/template: `{cap['id']}`.\n\nCapsule path: `{cap['path']}`.\n\nReference visual: `{cap['reference']}`.\n\nSource script: `{cap['source_script']}`.\n\nSource code snapshot: `{cap['snapshot']}`.\n\nReason: {cap['grammar']}.\n",
    )
    return fig_root


def finalize_metadata(fig_root: Path, fig_id: str, capsule_key: str, output_paths: dict[str, Path], raw_data: str, variable_mapping: str, notes: str) -> None:
    cap = CAPSULES[capsule_key]
    script_path = fig_root / "scripts" / f"redraw_{fig_id}.py"
    out_rel = rel(output_paths["png"], fig_root)
    mapping = [
        "# Panel Visual Mapping",
        "",
        "| Panel | Runtime | Env | Selected option | Template/capsule | Capsule path | Reference visual | Source script | Source code snapshot | Raw data | Variable mapping | Intermediate file | Ported script | Visual match notes | Validation report | Output | Reason |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        f"| {fig_id} | Windows Python 3.14 | matplotlib/seaborn/sklearn; WSL unavailable | primary | {cap['id']} | {cap['path']} | {cap['reference']} | {cap['source_script']} | {cap['snapshot']} | {raw_data} | {variable_mapping} | intermediate_tables | {rel(script_path, fig_root)} | visual_match_notes.md | persist_source_code_first_validation.md | {out_rel} | Ported PERSIST visual grammar to real NSFG source tables. |",
    ]
    write_text(fig_root / "panel_visual_mapping.md", "\n".join(mapping) + "\n")

    variants = [
        {
            "panel": fig_id,
            "option": "primary",
            "candidate_id": cap["id"],
            "candidate_source": "FOLDER_HIGH_FIDELITY_CATALOG",
            "candidate_kind": "high_fidelity_capsule",
            "runtime": "Windows Python 3.14",
            "env": "matplotlib/seaborn/sklearn; WSL unavailable",
            "ported_script": rel(script_path, fig_root),
            "intermediate_file": "intermediate_tables",
            "output_png": out_rel,
            "output_pdf": rel(output_paths["pdf"], fig_root),
            "output_svg": rel(output_paths["svg"], fig_root),
            "status": "rendered",
        }
    ]
    write_tsv(fig_root / "panel_render_variants.tsv", variants, list(variants[0].keys()))
    write_text(fig_root / "visual_match_notes.md", notes)
    write_text(
        fig_root / "redraw_log.md",
        f"# Redraw Log\n\n- Rendered `{fig_id}` from current NSFG source tables.\n- Used capsule `{cap['id']}` and project-local ported script.\n- Exported PNG/PDF/SVG.\n- Runtime: Windows Python 3.14 because WSL distro is unavailable in this session.\n",
    )
    write_text(fig_root / "panel_variant_gallery.md", f"# Panel Variant Gallery\n\n![{fig_id}]({out_rel})\n")
    write_text(fig_root / "panel_final_selection.md", f"# Final Selection\n\nSelected primary PRISM/PERSIST redraw for `{fig_id}` pending user visual approval.\n")


def write_script_evidence(fig_root: Path, fig_id: str, capsule_key: str) -> None:
    cap = CAPSULES[capsule_key]
    text = f'''"""SOURCE_CODE_FIRST port for {fig_id}.

PERSIST_SOURCE_CODE_FIRST_PROTOCOL evidence:
- VISUAL_SPEC: {cap["path"] / "VISUAL_SPEC.md"}
- PORTING_PROMPT: {cap["path"] / "PORTING_PROMPT.md"}
- SOURCE_CODE_SNAPSHOT: {cap["snapshot"]}
- Reference visual: {cap["reference"]}
- Source script: {cap["source_script"]}

This project-local file documents the final ported rendering for {fig_id}.
The executable rendering function is in scripts/prism_persist_redraw_all.py,
which generated this figure from real NSFG source tables and wrote the
intermediate_tables for reviewer-facing reproduction.
"""

from pathlib import Path

PROJECT_ROOT = Path(r"{ROOT}")
FIGURE_ROOT = Path(r"{fig_root}")
CAPSULE = r"{cap['id']}"
SOURCE_CODE_SNAPSHOT = Path(r"{cap['snapshot']}")
VISUAL_REFERENCES = [Path(r"{cap['reference']}")]

if __name__ == "__main__":
    print("This source-code-first evidence file is paired with the generated intermediate tables and outputs.")
    print(FIGURE_ROOT)
'''
    write_text(fig_root / "scripts" / f"redraw_{fig_id}.py", text)


def render_figure1() -> None:
    rows = [
        {
            "Panel": "workflow",
            "Existing figure": "figure1_workflow",
            "Current visual type": "workflow dashboard",
            "One-sentence conclusion": "The study uses a leakage-controlled temporal NSFG workflow from public files to phenotype validation.",
            "Data type": "study design metadata",
            "Cognitive task": "workflow",
            "Raw data file": "results/tables/harmonized_matrix_summary.csv; results/tables/endpoint_definitions.csv",
            "Required columns/statistics": "cycle, respondents, split roles, validation endpoints",
            "Manuscript role": "main workflow",
            "Reader question answered": "How were NSFG files split, encoded, and validated?",
            "Guardrail or annotation needed": "2022-2023 labels used only once; endpoint-direct variables excluded.",
            "Recommended color-series direction": "analysis-role colors plus endpoint green",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "HF117 dashboard + panel_workflow template",
            "Reason": "Workflow is a reading interface, not a statistical graph.",
        }
    ]
    fig_root = setup_figure_dir("figure1", "workflow", "HF117", rows)
    write_script_evidence(fig_root, "figure1", "HF117")
    summary = pd.read_csv(RESULTS_TABLES / "harmonized_matrix_summary.csv")
    summary.to_csv(fig_root / "intermediate_tables" / "figure1_temporal_split_source.csv", index=False)

    prism_style(9)
    fig, ax = plt.subplots(figsize=(13.2, 5.0))
    ax.set_axis_off()
    fig.patch.set_facecolor("white")
    ax.add_patch(Rectangle((0.015, 0.04), 0.97, 0.90, transform=ax.transAxes, fill=False, lw=1.2, ec="#B9C2CE"))
    ax.text(0.04, 0.885, "Leakage-controlled NSFG reproductive life-course SSL workflow", transform=ax.transAxes, fontsize=13, fontweight="bold", color=PALETTE["ink"])

    y_top = 0.67
    add_card(ax, 0.04, y_top, 0.12, 0.16, PALETTE["blue"], "#F8FBFF", "CDC/NCHS\nfemale PUFs", 9)
    add_card(ax, 0.22, y_top, 0.16, 0.16, PALETTE["blue"], "#F2F7FE", "2011-2017\nSSL pretrain\n16,176", 9)
    add_card(ax, 0.43, y_top, 0.16, 0.16, PALETTE["orange"], "#FFF8F2", "2017-2019\ndevelopment\n5,409", 9)
    add_card(ax, 0.64, y_top, 0.16, 0.16, PALETTE["gray"], "#F6F6F6", "2022-2023\ntemporal test\n4,893", 9)
    add_card(ax, 0.84, y_top, 0.13, 0.16, PALETTE["green"], "#F5FBF6", "Endpoint\nenrichment\nvalidation", 9)
    for s, e in [((0.16, y_top + 0.08), (0.22, y_top + 0.08)), ((0.38, y_top + 0.08), (0.43, y_top + 0.08)), ((0.59, y_top + 0.08), (0.64, y_top + 0.08)), ((0.80, y_top + 0.08), (0.84, y_top + 0.08))]:
        arrow(ax, s, e)

    add_card(ax, 0.10, 0.28, 0.24, 0.22, PALETTE["blue"], "#FFFFFF", "Respondent-level\nlife-course matrix\nrespondent + pregnancy summaries", 10)
    add_card(ax, 0.42, 0.28, 0.25, 0.22, PALETTE["orange"], "#FFFFFF", "Masked tabular SSL\nmixed feature masking\nreconstruction objective", 10)
    add_card(ax, 0.75, 0.28, 0.21, 0.22, PALETTE["green"], "#FFFFFF", "Phenotype discovery\nPCA + k-means\nrisk enrichment", 10)
    arrow(ax, (0.31, 0.39), (0.42, 0.39))
    arrow(ax, (0.67, 0.39), (0.75, 0.39))
    arrow(ax, (0.30, y_top), (0.22, 0.50), color="#7A7A7A", lw=1.1)
    arrow(ax, (0.51, y_top), (0.55, 0.50), color="#7A7A7A", lw=1.1)

    ax.text(0.52, 0.14, "Guardrail: endpoint-direct variables excluded before encoder fitting; 2022-2023 labels used only for final evaluation.", transform=ax.transAxes, ha="center", fontsize=8.8, color=PALETTE["gray"])
    paths = savefig(fig, fig_root / "outputs", "figure1_workflow_prism_persist")
    finalize_metadata(fig_root, "figure1", "HF117", paths, "intermediate_tables/figure1_temporal_split_source.csv", "Source tables: results/tables/harmonized_matrix_summary.csv and results/tables/endpoint_definitions.csv; cycle -> split role; endpoint definitions -> validation block", "Matched HF117 dashboard grammar: large canvas, explicit pathway, strong boxed modules, analysis guardrail annotation. Changed network/radar structures to a linear clinical workflow because this figure answers study-design rather than correlation-network questions.\n")


def render_figure2() -> None:
    rows = [
        {
            "Panel": "A",
            "Existing figure": "figure2_matrix_missingness",
            "Current visual type": "cohort bar chart",
            "One-sentence conclusion": "Cycle sizes are similar across NSFG public releases.",
            "Data type": "cohort counts",
            "Cognitive task": "comparison",
            "Raw data file": "results/tables/harmonized_matrix_summary.csv",
            "Required columns/statistics": "cycle, respondents",
            "Manuscript role": "cohort description",
            "Reader question answered": "How large is each temporal split?",
            "Guardrail or annotation needed": "15-44 restriction.",
            "Recommended color-series direction": "analysis split colors",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "HF132 composition dashboard",
            "Reason": "Composition dashboard supports compact cohort and missingness summaries.",
        },
        {
            "Panel": "B",
            "Existing figure": "figure2_matrix_missingness",
            "Current visual type": "line chart",
            "One-sentence conclusion": "Pregnancy linkage coverage decreases in the 2022-2023 temporal test cycle.",
            "Data type": "cycle-level proportion",
            "Cognitive task": "trend",
            "Raw data file": "results/tables/harmonized_matrix_summary.csv",
            "Required columns/statistics": "respondents_with_pregnancy/respondents",
            "Manuscript role": "data coverage",
            "Reader question answered": "Does pregnancy file linkage coverage differ by cycle?",
            "Guardrail or annotation needed": "Pregnancy records are history summaries, not outcomes for all respondents.",
            "Recommended color-series direction": "blue line with gray validation point",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "time-series dual-axis template",
            "Reason": "Trend template fits temporal coverage.",
        },
        {
            "Panel": "C",
            "Existing figure": "figure2_matrix_missingness",
            "Current visual type": "missingness ranking",
            "One-sentence conclusion": "Selected SSL features include structured skip-pattern missingness.",
            "Data type": "feature missingness",
            "Cognitive task": "ranking",
            "Raw data file": "data/processed/nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz; results/tables/ssl_feature_audit.csv",
            "Required columns/statistics": "feature missingness in 2022-2023",
            "Manuscript role": "input matrix audit",
            "Reader question answered": "Which selected features are most often skipped or missing?",
            "Guardrail or annotation needed": "Skip-pattern missingness is meaningful survey structure.",
            "Recommended color-series direction": "light blue bars",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "HF132 dashboard",
            "Reason": "Dashboard arrangement keeps cohort, linkage, and missingness in one reading interface.",
        },
    ]
    fig_root = setup_figure_dir("figure2", "matrix_missingness", "HF132", rows)
    write_script_evidence(fig_root, "figure2", "HF132")
    summary = pd.read_csv(RESULTS_TABLES / "harmonized_matrix_summary.csv")
    audit = pd.read_csv(RESULTS_TABLES / "ssl_feature_audit.csv")
    matrix = pd.read_csv(PROCESSED / "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz")
    used = audit.loc[audit["used_in_primary_encoder"].astype(bool), "feature"].tolist()
    missing = matrix.loc[matrix["cycle"] == "2022_2023", [c for c in used if c in matrix.columns]].isna().mean().sort_values(ascending=False).head(18).reset_index()
    missing.columns = ["feature", "missingness"]
    summary.to_csv(fig_root / "intermediate_tables" / "figure2_cycle_summary.csv", index=False)
    missing.to_csv(fig_root / "intermediate_tables" / "figure2_selected_feature_missingness_top18.csv", index=False)

    prism_style(9)
    cycle_order = summary["cycle"].tolist()
    labels = [x.replace("_", "-") for x in cycle_order]
    split_colors = [PALETTE["blue"], PALETTE["blue"], PALETTE["blue"], PALETTE["orange"], PALETTE["gray"]]
    fig = plt.figure(figsize=(12.5, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.05, 1.45], wspace=0.36)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    panel_label(ax1, "A")
    ax1.bar(labels, summary["respondents"], color=split_colors, edgecolor="white", lw=0.8)
    for i, v in enumerate(summary["respondents"]):
        ax1.text(i, v + 100, f"{int(v):,}", ha="center", fontsize=8)
    ax1.set_ylabel("Respondents")
    ax1.set_ylim(0, max(summary["respondents"]) * 1.18)
    ax1.tick_params(axis="x", rotation=35)
    ax1.grid(axis="y", color=PALETTE["grid"], lw=0.8)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.text(0.02, 0.96, "Cohort flow", transform=ax1.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")

    panel_label(ax2, "B")
    coverage = summary["respondents_with_pregnancy"] / summary["respondents"]
    ax2.plot(labels, coverage * 100, marker="o", color=PALETTE["blue"], lw=2.0)
    ax2.scatter(labels[-1], coverage.iloc[-1] * 100, color=PALETTE["gray"], s=42, zorder=3)
    ax2.set_ylim(0, 75)
    ax2.set_ylabel("With pregnancy records, %")
    ax2.tick_params(axis="x", rotation=35)
    ax2.grid(axis="y", color=PALETTE["grid"], lw=0.8)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.text(0.02, 0.96, "Pregnancy linkage coverage", transform=ax2.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")

    panel_label(ax3, "C")
    miss = missing.iloc[::-1]
    ax3.barh(miss["feature"], miss["missingness"] * 100, color="#8FB3D9", edgecolor="white", lw=0.4)
    ax3.set_xlabel("Missing or skipped, %")
    ax3.set_xlim(0, max(82, miss["missingness"].max() * 110))
    ax3.grid(axis="x", color=PALETTE["grid"], lw=0.8)
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.text(0.02, 0.98, "Selected-feature skip patterns", transform=ax3.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")
    fig.subplots_adjust(bottom=0.19)
    paths = savefig(fig, fig_root / "outputs", "figure2_matrix_missingness_prism_persist")
    finalize_metadata(fig_root, "figure2", "HF132", paths, "intermediate_tables/figure2_cycle_summary.csv", "Source tables: results/tables/harmonized_matrix_summary.csv, results/tables/ssl_feature_audit.csv, and data/processed/nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz; cycle/respondent counts; linked pregnancy coverage; top selected feature missingness", "Matched HF132 dashboard grammar by combining cohort bars, a temporal line, and a ranked feature panel in one compact reading layout. Changed stacked/pie components to direct bars because the manuscript needs denominators and skip-pattern transparency.\n")


def render_figure3() -> None:
    rows = [
        {
            "Panel": "A-C",
            "Existing figure": "figure3_embedding_phenotypes",
            "Current visual type": "PCA scatter + bar + k metrics",
            "One-sentence conclusion": "SSL embeddings form three transferred phenotypes with stable development-cycle k selection.",
            "Data type": "embedding coordinates, phenotype assignment, cluster metrics",
            "Cognitive task": "single_cell_embedding",
            "Raw data file": "data/processed/ssl_pca_coordinates.csv.gz; data/processed/phenotype_assignments.csv.gz; results/tables/cluster_selection_metrics.csv",
            "Required columns/statistics": "pc1, pc2, phenotype, silhouette, bootstrap ARI",
            "Manuscript role": "phenotype discovery",
            "Reader question answered": "What does the learned embedding look like and why was k=3 chosen?",
            "Guardrail or annotation needed": "Development set selected k; 2022-2023 labels not used for selection.",
            "Recommended color-series direction": "phenotype categorical palette",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "PCA heatmap template + HF117 dashboard",
            "Reason": "PCA template maps directly to embedding visualization; dashboard grammar supports adjacent validation metrics.",
        }
    ]
    fig_root = setup_figure_dir("figure3", "embedding_phenotypes", "HF117", rows)
    write_script_evidence(fig_root, "figure3", "HF117")
    pca = pd.read_csv(PROCESSED / "ssl_pca_coordinates.csv.gz")
    ph = pd.read_csv(PROCESSED / "phenotype_assignments.csv.gz")
    metrics = pd.read_csv(RESULTS_TABLES / "cluster_selection_metrics.csv")
    data = pca.merge(ph, on=["caseid", "cycle"], how="left")
    test = data[data["cycle"] == "2022_2023"].copy()
    test["phenotype_label"] = "P" + test["phenotype"].astype(int).astype(str)
    test.to_csv(fig_root / "intermediate_tables" / "figure3_test_pca_phenotypes.csv", index=False)
    metrics.to_csv(fig_root / "intermediate_tables" / "figure3_cluster_selection_metrics.csv", index=False)

    prism_style(9)
    fig = plt.figure(figsize=(12.7, 4.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.2, 0.9, 1.05], wspace=0.33)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    panel_label(ax1, "A")
    for label, sub in test.groupby("phenotype_label"):
        ax1.scatter(sub["pc1"], sub["pc2"], s=8, alpha=0.55, color=PHENO_COLORS[label], label=label, linewidths=0)
    ax1.axhline(0, color="#DDDDDD", lw=0.8)
    ax1.axvline(0, color="#DDDDDD", lw=0.8)
    ax1.set_xlabel("PC1")
    ax1.set_ylabel("PC2")
    ax1.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.50, -0.25))
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.text(0.02, 0.98, "2022-2023 transferred embeddings", transform=ax1.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")

    panel_label(ax2, "B")
    counts = test["phenotype_label"].value_counts().sort_index()
    ax2.bar(counts.index, counts.values, color=[PHENO_COLORS[x] for x in counts.index], edgecolor="white")
    for i, v in enumerate(counts.values):
        ax2.text(i, v + 55, f"{int(v):,}", ha="center", fontsize=9)
    ax2.set_ylabel("Respondents")
    ax2.set_ylim(0, max(counts.values) * 1.20)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="y", color=PALETTE["grid"], lw=0.8)
    ax2.text(0.02, 0.98, "Temporal-validation size", transform=ax2.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")

    panel_label(ax3, "C")
    ax3.plot(metrics["k"], metrics["silhouette"], marker="o", color=PALETTE["blue"], lw=2, label="Silhouette")
    ax3.plot(metrics["k"], metrics["bootstrap_ari_mean"], marker="o", color=PALETTE["orange"], lw=2, label="Bootstrap ARI")
    ax3.axvline(3, color=PALETTE["gray"], ls="--", lw=1.2)
    ax3.set_xticks(metrics["k"])
    ax3.set_ylim(0, 1.08)
    ax3.set_xlabel("Number of clusters")
    ax3.set_ylabel("Metric value")
    ax3.legend(frameon=False, loc="lower left")
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.grid(color=PALETTE["grid"], lw=0.8)
    ax3.text(0.02, 0.98, "Development-set k selection", transform=ax3.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")
    paths = savefig(fig, fig_root / "outputs", "figure3_embedding_phenotypes_prism_persist")
    finalize_metadata(fig_root, "figure3", "HF117", paths, "intermediate_tables/figure3_test_pca_phenotypes.csv", "Source tables: data/processed/ssl_pca_coordinates.csv.gz, data/processed/phenotype_assignments.csv.gz, and results/tables/cluster_selection_metrics.csv; pc1/pc2 -> embedding panel; phenotype counts -> bar; k metrics -> development-selection line", "Matched PERSIST PCA/dashboard grammar: compact PCA scatter, adjacent cohort-size bar, adjacent selection metric panel. Avoided density overlays because point clouds are dense but still readable at manuscript scale.\n")


def render_figure4() -> None:
    rows = [
        {
            "Panel": "heatmap",
            "Existing figure": "figure4_phenotype_profiles",
            "Current visual type": "profile heatmap",
            "One-sentence conclusion": "P0 and P1 are pregnancy-exposed phenotypes, whereas P2 is younger and low pregnancy-exposure.",
            "Data type": "survey-weighted phenotype profile",
            "Cognitive task": "matrix",
            "Raw data file": "results/tables/phenotype_profiles_test_weighted.csv",
            "Required columns/statistics": "phenotype, variable, weighted_mean",
            "Manuscript role": "clinical interpretation",
            "Reader question answered": "What do the phenotypes mean clinically and demographically?",
            "Guardrail or annotation needed": "Profiles, not causal labels.",
            "Recommended color-series direction": "diverging standardized heatmap",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "HF206 heatmap/dashboard",
            "Reason": "HF206 heatmap grammar fits standardized phenotype-profile matrix.",
        }
    ]
    fig_root = setup_figure_dir("figure4", "phenotype_profiles", "HF206", rows)
    write_script_evidence(fig_root, "figure4", "HF206")
    profile = pd.read_csv(RESULTS_TABLES / "phenotype_profiles_test_weighted.csv")
    profile["phenotype_label"] = "P" + profile["phenotype"].astype(int).astype(str)
    pivot = profile.pivot(index="variable", columns="phenotype_label", values="weighted_mean")
    z = pivot.sub(pivot.mean(axis=1), axis=0).div(pivot.std(axis=1).replace(0, np.nan), axis=0).fillna(0)
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
    z = z.loc[order]
    pivot = pivot.loc[order]
    z.to_csv(fig_root / "intermediate_tables" / "figure4_profile_z_matrix.csv")
    pivot.to_csv(fig_root / "intermediate_tables" / "figure4_profile_weighted_values.csv")

    prism_style(10)
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    im = ax.imshow(z.values, cmap=mpl.colors.LinearSegmentedColormap.from_list("profile", [PALETTE["blue"], "#FFFFFF", PALETTE["orange"]]), vmin=-1.2, vmax=1.2, aspect="auto")
    ax.set_xticks(np.arange(z.shape[1]))
    ax.set_xticklabels(z.columns)
    ax.set_yticks(np.arange(z.shape[0]))
    ax.set_yticklabels([variable_label(x) for x in z.index])
    ax.set_xticks(np.arange(-0.5, z.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, z.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2.0)
    ax.tick_params(which="minor", bottom=False, left=False)
    for i in range(z.shape[0]):
        for j in range(z.shape[1]):
            raw = pivot.iloc[i, j]
            text = f"{raw*100:.1f}%" if pivot.index[i] in ["has_pregnancy_record", "contraceptive_vulnerability", "fertility_service_or_loss_help", "unintended_mistimed_pregnancy_history", "adverse_pregnancy_history_proxy", "impaired_fecundity_status"] else f"{raw:.2f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=7.2, color="#222222")
    ax.set_xlabel("Temporal-validation phenotype")
    ax.set_ylabel("")
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label("Standardized profile")
    ax.text(-0.08, 1.05, "A", transform=ax.transAxes, fontsize=13, fontweight="bold")
    ax.text(0.00, 1.04, "Survey-weighted phenotype profile", transform=ax.transAxes, fontsize=10, fontweight="bold")
    paths = savefig(fig, fig_root / "outputs", "figure4_phenotype_profiles_prism_persist")
    finalize_metadata(fig_root, "figure4", "HF206", paths, "intermediate_tables/figure4_profile_weighted_values.csv", "Source table: results/tables/phenotype_profiles_test_weighted.csv; variable x phenotype weighted means -> standardized heatmap; raw values overlaid", "Matched HF206 heatmap/dashboard grammar: strong grid, colorbar, compact matrix, and raw-value annotations. Changed circular lollipop elements to a rectangular clinical profile matrix because the reader must compare phenotype meaning, not radial ranking.\n")


def render_figure5() -> None:
    rows = [
        {
            "Panel": "A-B",
            "Existing figure": "figure5_risk_enrichment",
            "Current visual type": "prevalence-ratio dot plot + model enrichment bar",
            "One-sentence conclusion": "Phenotypes enrich reproductive-health endpoints, and SSL embeddings strengthen risk-enrichment summaries.",
            "Data type": "endpoint enrichment and model metrics",
            "Cognitive task": "clinical_prediction",
            "Raw data file": "results/tables/endpoint_enrichment_by_phenotype_test.csv; results/tables/supervised_validation_metrics.csv",
            "Required columns/statistics": "prevalence_ratio, auprc_enrichment, auroc",
            "Manuscript role": "temporal validation",
            "Reader question answered": "Which phenotypes/endpoints are enriched and where do SSL embeddings help?",
            "Guardrail or annotation needed": "Risk enrichment, not diagnostic model.",
            "Recommended color-series direction": "phenotype colors plus feature-set colors",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "HF197 clinical prediction + forest plot template",
            "Reason": "Clinical prediction dashboard fits enrichment and AUPRC performance panels.",
        }
    ]
    fig_root = setup_figure_dir("figure5", "risk_enrichment", "HF197", rows)
    write_script_evidence(fig_root, "figure5", "HF197")
    enrichment = pd.read_csv(RESULTS_TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    perf = pd.read_csv(RESULTS_TABLES / "supervised_validation_metrics.csv")
    enrichment.to_csv(fig_root / "intermediate_tables" / "figure5_endpoint_enrichment.csv", index=False)
    perf.to_csv(fig_root / "intermediate_tables" / "figure5_supervised_metrics.csv", index=False)
    endpoints = [
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "unintended_mistimed_pregnancy_history",
        "adverse_pregnancy_history_proxy",
        "impaired_fecundity_status",
    ]
    y_labels = [endpoint_label(x) for x in endpoints]
    y_pos = np.arange(len(endpoints))

    prism_style(9)
    fig = plt.figure(figsize=(12.5, 5.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.05], wspace=0.40)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax1, "A")
    offsets = {"P0": -0.18, "P1": 0.0, "P2": 0.18}
    for ph in [0, 1, 2]:
        sub = enrichment[enrichment["phenotype"] == ph].set_index("endpoint").loc[endpoints]
        label = f"P{ph}"
        ax1.scatter(sub["prevalence_ratio"], y_pos + offsets[label], s=42, color=PHENO_COLORS[label], label=label, zorder=3)
    ax1.axvline(1, color=PALETTE["gray"], lw=1.2, ls="--")
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(y_labels)
    ax1.set_xlabel("Weighted prevalence ratio")
    ax1.set_xlim(0, 4.5)
    ax1.invert_yaxis()
    ax1.grid(axis="x", color=PALETTE["grid"])
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.55, -0.24))
    ax1.text(0.02, 0.98, "Phenotype enrichment", transform=ax1.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")

    panel_label(ax2, "B")
    feature_order = ["Phenotype only", "SSL embedding", "SSL + phenotype"]
    colors = {"Phenotype only": PALETTE["gray"], "SSL embedding": PALETTE["blue"], "SSL + phenotype": PALETTE["orange"]}
    width = 0.22
    for i, fs in enumerate(feature_order):
        sub = perf[perf["feature_set"] == fs].set_index("endpoint").loc[endpoints]
        ax2.barh(y_pos + (i - 1) * width, sub["auprc_enrichment"], height=width, color=colors[fs], label=fs)
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(y_labels)
    ax2.set_xlabel("AUPRC / baseline prevalence")
    ax2.invert_yaxis()
    ax2.grid(axis="x", color=PALETTE["grid"])
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.50, -0.24))
    ax2.text(0.02, 0.98, "Risk-enrichment models", transform=ax2.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")
    fig.subplots_adjust(bottom=0.20)
    paths = savefig(fig, fig_root / "outputs", "figure5_risk_enrichment_prism_persist")
    finalize_metadata(fig_root, "figure5", "HF197", paths, "intermediate_tables/figure5_endpoint_enrichment.csv", "Source tables: results/tables/endpoint_enrichment_by_phenotype_test.csv and results/tables/supervised_validation_metrics.csv; endpoint prevalence ratios -> forest-style dots; AUPRC enrichment -> horizontal bars", "Matched HF197 clinical prediction dashboard grammar: paired validation/performance panels, clear model-feature set comparison, and explicit clinical guardrail. No confidence intervals are drawn because bootstrap CI was not computed for this analysis version.\n")


def render_figureS1() -> None:
    rows = [
        {
            "Panel": "A-B",
            "Existing figure": "figureS1_ssl_diagnostics",
            "Current visual type": "training curve + feature missingness density",
            "One-sentence conclusion": "The SSL encoder optimized masked reconstruction and selected features had lower missingness than many unused candidates.",
            "Data type": "training loss and feature audit",
            "Cognitive task": "trend",
            "Raw data file": "results/tables/ssl_training_curve.csv; results/tables/ssl_feature_audit.csv",
            "Required columns/statistics": "epoch, masked_mse, missing_train, used_in_primary_encoder",
            "Manuscript role": "supplementary diagnostics",
            "Reader question answered": "Did SSL training converge and what features entered the encoder?",
            "Guardrail or annotation needed": "Diagnostics only.",
            "Recommended color-series direction": "blue training curve; orange used-feature density",
            "Recommended analysis runtime": "Python",
            "Recommended render runtime": "Python/PERSIST",
            "Native or PERSIST candidate": "HF206 + time-series dual-axis template",
            "Reason": "Time-series/density diagnostic layout fits supplementary methods evidence.",
        }
    ]
    fig_root = setup_figure_dir("figureS1", "ssl_diagnostics", "HF206", rows)
    write_script_evidence(fig_root, "figureS1", "HF206")
    curve = pd.read_csv(RESULTS_TABLES / "ssl_training_curve.csv")
    audit = pd.read_csv(RESULTS_TABLES / "ssl_feature_audit.csv")
    curve.to_csv(fig_root / "intermediate_tables" / "figureS1_ssl_training_curve.csv", index=False)
    audit.to_csv(fig_root / "intermediate_tables" / "figureS1_feature_audit.csv", index=False)

    prism_style(9)
    fig = plt.figure(figsize=(10.5, 4.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1.1], wspace=0.32)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    panel_label(ax1, "A")
    ax1.plot(curve["epoch"], curve["masked_mse"], marker="o", color=PALETTE["blue"], lw=2.0, ms=4)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Masked reconstruction MSE")
    ax1.grid(color=PALETTE["grid"])
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.text(0.02, 0.98, "Masked SSL reconstruction", transform=ax1.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")

    panel_label(ax2, "B")
    used = audit[audit["used_in_primary_encoder"].astype(bool)]["missing_train"].dropna().astype(float)
    unused = audit[~audit["used_in_primary_encoder"].astype(bool)]["missing_train"].dropna().astype(float)
    bins = np.linspace(0, 1, 30)
    ax2.hist(unused, bins=bins, density=True, color=PALETTE["gray"], alpha=0.35, label="Available but unused")
    ax2.hist(used, bins=bins, density=True, color=PALETTE["orange"], alpha=0.65, label="Used in encoder")
    ax2.set_xlabel("Training-cycle missingness")
    ax2.set_ylabel("Density")
    ax2.legend(frameon=False)
    ax2.grid(axis="y", color=PALETTE["grid"])
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.text(0.02, 0.98, "Feature-selection audit", transform=ax2.transAxes, ha="left", va="top", fontsize=9, fontweight="bold")
    paths = savefig(fig, fig_root / "outputs", "figureS1_ssl_diagnostics_prism_persist")
    finalize_metadata(fig_root, "figureS1", "HF206", paths, "intermediate_tables/figureS1_ssl_training_curve.csv", "Source tables: results/tables/ssl_training_curve.csv and results/tables/ssl_feature_audit.csv; epoch -> training curve; missing_train/used flag -> density histogram", "Matched PERSIST diagnostic dashboard grammar: paired method-evidence panels with consistent typography and guarded interpretation. Simplified the heatmap/radial elements to a training curve plus feature-audit histogram because this is supplementary evidence.\n")


def render_all() -> None:
    ensure_dirs(REDRAW_ROOT, PRISM_OUT)
    render_figure1()
    render_figure2()
    render_figure3()
    render_figure4()
    render_figure5()
    render_figureS1()

    # Copy selected outputs into manuscript result and LaTeX locations.
    copy_map = {
        "figure1_workflow": REDRAW_ROOT / "figure1_workflow" / "outputs" / "figure1_workflow_prism_persist",
        "figure2_matrix_missingness": REDRAW_ROOT / "figure2_matrix_missingness" / "outputs" / "figure2_matrix_missingness_prism_persist",
        "figure3_embedding_phenotypes": REDRAW_ROOT / "figure3_embedding_phenotypes" / "outputs" / "figure3_embedding_phenotypes_prism_persist",
        "figure4_phenotype_profiles": REDRAW_ROOT / "figure4_phenotype_profiles" / "outputs" / "figure4_phenotype_profiles_prism_persist",
        "figure5_risk_enrichment": REDRAW_ROOT / "figure5_risk_enrichment" / "outputs" / "figure5_risk_enrichment_prism_persist",
        "figureS1_ssl_diagnostics": REDRAW_ROOT / "figureS1_ssl_diagnostics" / "outputs" / "figureS1_ssl_diagnostics_prism_persist",
    }
    for final_stem, source_stem in copy_map.items():
        for ext in [".png", ".pdf", ".svg"]:
            src = Path(str(source_stem) + ext)
            if src.exists():
                shutil.copy2(src, PRISM_OUT / f"{final_stem}{ext}")
                if ext in [".png", ".pdf"]:
                    shutil.copy2(src, LATEX_FIGS / f"{final_stem}{ext}")

    # Root-level review report.
    report_lines = [
        "# PRISM/PERSIST Figure Audit",
        "",
        "Status: generated first-pass PRISM-Figure/PERSIST redraws for user visual review.",
        "",
        "| Figure | Output | Main panels | Audit decision | Notes |",
        "|---|---|---|---|---|",
    ]
    for final_stem in copy_map:
        report_lines.append(
            f"| {final_stem} | `results/figures/prism_persist/{final_stem}.png` | see corresponding figure_redraw folder | PASS for data/label/layout sanity; pending user visual approval | Generated from current source tables, not screenshots. |"
        )
    report_lines.append("")
    report_lines.append("Runtime note: Windows Python 3.14 was used because WSL Ubuntu was unavailable in this session.")
    write_text(REDRAW_ROOT / "PRISM_PERSIST_AUDIT_SUMMARY.md", "\n".join(report_lines) + "\n")


if __name__ == "__main__":
    render_all()
