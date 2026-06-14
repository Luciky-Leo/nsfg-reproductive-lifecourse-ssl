"""Stage-1 PERSIST panel candidate selection.

This does not redraw figures. It creates per-panel candidate inventories so the
user can choose the capsule/template and visualization method before rendering.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


ROOT = Path(r"E:\Reserch\NSFG_Reproductive_LifeCourse_SSL_20260601")
PERSIST = Path(r"E:\Python\PERSIST")
OUT = ROOT / "figure_redraw" / "panel_stage1_selection_20260602"
HF_CATALOG = PERSIST / "_portable_patterns" / "high_fidelity_by_folder" / "FOLDER_HIGH_FIDELITY_CATALOG.csv"
PERSIST_INDEX = PERSIST / "_index" / "PERSIST_plot_code_index.csv"


def ensure(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_catalogs() -> tuple[pd.DataFrame, pd.DataFrame]:
    hf = pd.read_csv(HF_CATALOG)
    idx = pd.read_csv(PERSIST_INDEX)
    return hf, idx


def hf_meta(hf: pd.DataFrame, prefix: str) -> dict[str, str]:
    row = hf[hf["capsule_id"].astype(str).str.startswith(prefix)].head(1)
    if row.empty:
        return {}
    item = row.iloc[0].to_dict()
    return {
        "id": str(item.get("capsule_id", "")),
        "kind": "high_fidelity_capsule",
        "path": str(item.get("capsule_folder", "")),
        "reference": "" if pd.isna(item.get("primary_reference", "")) else str(item.get("primary_reference", "")),
        "source": "" if pd.isna(item.get("primary_script", "")) else str(item.get("primary_script", "")),
        "title": str(item.get("title", "")),
        "feature_keys": str(item.get("feature_keys", "")),
        "visual_score": str(item.get("visual_score", "")),
    }


def persist_meta(idx: pd.DataFrame, pid: str, path_hint: str) -> dict[str, str]:
    if pid.startswith("portable:"):
        return {
            "id": pid,
            "kind": "portable_template",
            "source_surface": "PERSIST portable pattern path",
            "path": str(PERSIST / path_hint),
            "reference": "",
            "source": str(PERSIST / path_hint),
            "title": pid.replace("portable:", ""),
            "feature_keys": "",
            "visual_score": "",
        }
    row = idx[idx["id"].astype(str).eq(pid)].head(1)
    if row.empty:
        return {
            "id": pid,
            "kind": "portable_template",
            "source_surface": "PERSIST index fallback",
            "path": str(PERSIST / path_hint),
            "reference": "",
            "source": str(PERSIST / path_hint),
            "title": path_hint,
            "feature_keys": "",
            "visual_score": "",
        }
    item = row.iloc[0].to_dict()
    rel = str(item.get("relative_path", path_hint))
    return {
        "id": pid,
        "kind": "portable_template",
        "source_surface": "PERSIST indexed code",
        "path": str(PERSIST / rel),
        "reference": "",
        "source": str(PERSIST / rel),
        "title": str(item.get("item_title", "")),
        "feature_keys": str(item.get("technique_tags", "")),
        "visual_score": "",
    }


def score(task: int, data: int, visual: int, code: int, read: int) -> dict[str, int]:
    return {
        "Task fit score": task,
        "Data fit score": data,
        "Visual grammar score": visual,
        "Source-code readiness score": code,
        "Readability score": read,
        "Total score": task + data + visual + code + read,
    }


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure(path.parent)
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ensure(OUT)
    hf, idx = read_catalogs()

    panels = [
        {
            "Panel": "F1-W",
            "Figure": "Figure 1",
            "Current type": "workflow",
            "One-sentence conclusion": "Public-use NSFG files are split temporally for leakage-controlled SSL pretraining, development, and validation.",
            "Data task": "study workflow and guardrail communication",
            "Data source status": "available",
            "Source data": "results/tables/harmonized_matrix_summary.csv; results/tables/endpoint_definitions.csv",
        },
        {
            "Panel": "F2-A",
            "Figure": "Figure 2A",
            "Current type": "cycle count bar chart",
            "One-sentence conclusion": "Eligible female respondent counts are comparable across harmonized NSFG cycles.",
            "Data task": "group count comparison",
            "Data source status": "available",
            "Source data": "results/tables/harmonized_matrix_summary.csv",
        },
        {
            "Panel": "F2-B",
            "Figure": "Figure 2B",
            "Current type": "cycle coverage line chart",
            "One-sentence conclusion": "Pregnancy-record linkage coverage varies by cycle and is lower in 2022-2023.",
            "Data task": "temporal trend",
            "Data source status": "available",
            "Source data": "results/tables/harmonized_matrix_summary.csv",
        },
        {
            "Panel": "F2-C",
            "Figure": "Figure 2C",
            "Current type": "selected-feature missingness ranking",
            "One-sentence conclusion": "Selected SSL inputs retain structured NSFG skip-pattern missingness.",
            "Data task": "ranked missingness or skip-pattern distribution",
            "Data source status": "available",
            "Source data": "results/tables/ssl_feature_audit.csv; data/processed/nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz",
        },
        {
            "Panel": "F3-A",
            "Figure": "Figure 3A",
            "Current type": "PCA embedding scatter",
            "One-sentence conclusion": "Transferred 2022-2023 SSL embeddings separate into reproductive life-course phenotypes.",
            "Data task": "low-dimensional embedding",
            "Data source status": "available",
            "Source data": "data/processed/ssl_pca_coordinates.csv.gz; data/processed/phenotype_assignments.csv.gz",
        },
        {
            "Panel": "F3-B",
            "Figure": "Figure 3B",
            "Current type": "phenotype size bar chart",
            "One-sentence conclusion": "The temporal-validation phenotypes have unequal but interpretable sizes.",
            "Data task": "cluster composition",
            "Data source status": "available",
            "Source data": "data/processed/phenotype_assignments.csv.gz",
        },
        {
            "Panel": "F3-C",
            "Figure": "Figure 3C",
            "Current type": "k-selection metric line chart",
            "One-sentence conclusion": "Development-cycle k=3 balances silhouette and bootstrap stability.",
            "Data task": "model-selection metric trend",
            "Data source status": "available",
            "Source data": "results/tables/cluster_selection_metrics.csv",
        },
        {
            "Panel": "F4-A",
            "Figure": "Figure 4A",
            "Current type": "phenotype profile heatmap",
            "One-sentence conclusion": "Phenotypes differ across age, parity, pregnancy history, socioeconomic, and reproductive-health profiles.",
            "Data task": "profile matrix comparison",
            "Data source status": "available",
            "Source data": "results/tables/phenotype_profiles_test_weighted.csv",
        },
        {
            "Panel": "F5-A",
            "Figure": "Figure 5A",
            "Current type": "prevalence-ratio dot/forest plot",
            "One-sentence conclusion": "Specific phenotypes enrich distinct reproductive-health endpoints in temporal validation.",
            "Data task": "effect-size comparison",
            "Data source status": "available; CI columns not currently present",
            "Source data": "results/tables/endpoint_enrichment_by_phenotype_test.csv",
        },
        {
            "Panel": "F5-B",
            "Figure": "Figure 5B",
            "Current type": "AUPRC enrichment grouped bars",
            "One-sentence conclusion": "SSL embeddings summarize risk-enrichment information beyond phenotype labels for selected endpoints.",
            "Data task": "model metric comparison",
            "Data source status": "available",
            "Source data": "results/tables/supervised_validation_metrics.csv",
        },
        {
            "Panel": "FS1-A",
            "Figure": "Figure S1A",
            "Current type": "SSL training curve",
            "One-sentence conclusion": "Masked reconstruction loss declines during training.",
            "Data task": "training trajectory",
            "Data source status": "available",
            "Source data": "results/tables/ssl_training_curve.csv",
        },
        {
            "Panel": "FS1-B",
            "Figure": "Figure S1B",
            "Current type": "feature missingness distribution",
            "One-sentence conclusion": "Used encoder features have a different missingness distribution than available but unused candidates.",
            "Data task": "distribution comparison",
            "Data source status": "available",
            "Source data": "results/tables/ssl_feature_audit.csv",
        },
    ]

    # candidate tuple:
    # option, panel, source_id, method, why, required_data, risk, decision, score tuple
    candidate_specs = [
        ("F1-W1", "F1-W", "HF132", "single integrated workflow with segmented boxes and small inset glyphs", "Composition-dashboard grammar can make the study design look like a polished registry-analytics workflow rather than a plain flowchart.", "cycle split counts; endpoint guardrail statements", "May look busy if too many icon/inset elements are retained.", "render_recommended", (28, 25, 20, 14, 9)),
        ("F1-W2", "F1-W", "HF117", "network/dashboard workflow with optional radial summary inset", "Strong high-fidelity dashboard style; useful if you want Figure 1 to look more AI-method oriented.", "cycle split counts; life-course matrix modules; SSL encoder modules", "Network/radar grammar can overstate correlation/network analysis if not simplified.", "render_optional", (24, 23, 20, 14, 8)),
        ("F1-W3", "F1-W", "portable:panel_workflow", "clean panel-workflow template", "Most conservative and accurate for workflow, but less high-fidelity than HF capsules.", "study stages and guardrails", "May look less visually distinctive.", "hold_native", (27, 25, 15, 15, 9)),
        ("F2-A1", "F2-A", "HF132", "cycle count bars inside composition dashboard style", "Good for polished cohort-flow/count bars with consistent figure-level layout.", "cycle and respondent count", "Not as minimal as a pure journal bar plot.", "render_recommended", (27, 25, 18, 14, 9)),
        ("F2-A2", "F2-A", "portable:percent_stacked_bar", "compact bar or percent-stack style count panel", "Easy to port and readable for cycle count comparison.", "cycle and respondent count", "Template is composition-oriented, not specifically count-oriented.", "render_optional", (23, 24, 14, 15, 9)),
        ("F2-A3", "F2-A", "HF009", "radial grouped bar / circular count panel", "High visual impact for cycle-level counts.", "cycle and respondent count", "Risk of looking decorative and less BMC-style.", "render_optional", (18, 20, 18, 13, 6)),
        ("F2-B1", "F2-B", "HF012", "dual-axis/time-series trend panel", "Best match for linkage coverage over NSFG cycles, with high-fidelity trend styling.", "cycle and pregnancy-linkage coverage", "Dual-axis elements should be suppressed if only one y metric is shown.", "render_recommended", (29, 25, 18, 14, 9)),
        ("F2-B2", "F2-B", "portable:time_series_dual_axis", "portable time-series line template", "Most faithful data mapping for a trend panel.", "cycle and coverage proportion", "Less high-fidelity than HF012.", "render_optional", (27, 25, 14, 15, 9)),
        ("F2-B3", "F2-B", "HF132", "dashboard trend inset", "Keeps F2A/B/C visually unified under a composition-dashboard figure.", "cycle and coverage proportion", "Trend panel may be visually subordinate if too compressed.", "render_optional", (23, 24, 17, 14, 8)),
        ("F2-C1", "F2-C", "HF206", "ranked missingness heatmap/block panel", "Good for selected-feature missingness as a matrix-like audit with high-fidelity heatmap grammar.", "feature missingness and used-feature flags", "Circular elements should be removed unless they encode a real statistic.", "render_recommended", (28, 25, 20, 14, 8)),
        ("F2-C2", "F2-C", "HF013", "correlation/heatmap-style missingness matrix", "Good if we convert top missing features into a compact feature-domain heatmap.", "feature missingness by cycle or domain", "Needs cycle-by-feature matrix; otherwise becomes a simple heatmap skin.", "render_optional", (24, 22, 18, 14, 8)),
        ("F2-C3", "F2-C", "portable:ridge_density", "ridge density of selected-feature missingness", "Good if you prefer distributional missingness rather than top-feature bars.", "missingness values for used and unused features", "It changes the reader question from ranking to distribution.", "render_optional", (20, 23, 15, 15, 8)),
        ("F3-A1", "F3-A", "HF103", "PCA scatter with companion loading/correlation inset style", "Direct high-fidelity match for PCA embedding visualization.", "pc1, pc2, phenotype labels", "If we add loading/correlation insets, they must be real and explained.", "render_recommended", (30, 25, 20, 14, 9)),
        ("F3-A2", "F3-A", "portable:pca_heatmap", "portable PCA plus heatmap template", "Best source-code-first mapping for a clean PCA panel.", "sample-by-feature matrix or pc coordinates", "Less distinctive than HF103.", "render_optional", (28, 25, 15, 15, 9)),
        ("F3-A3", "F3-A", "HF117", "dashboard embedding with phenotype inset", "Useful if Figure 3 should look like an AI phenotype-discovery dashboard.", "pc coordinates, phenotype labels, phenotype summaries", "Network/radar features must not imply unsupported network analysis.", "render_optional", (24, 23, 19, 14, 8)),
        ("F3-B1", "F3-B", "HF132", "phenotype composition/count dashboard bar", "Good match for phenotype sizes and can use inset labels without crowding.", "phenotype counts", "May be too styled for a simple count panel.", "render_recommended", (27, 25, 18, 14, 9)),
        ("F3-B2", "F3-B", "portable:percent_stacked_bar", "percent stacked or compact composition bar", "Best if you want the panel to emphasize cluster proportions rather than absolute counts.", "phenotype counts or proportions", "Absolute counts need annotation.", "render_optional", (25, 25, 15, 15, 8)),
        ("F3-B3", "F3-B", "HF009", "radial phenotype-size bar", "High-impact compact representation for three phenotype sizes.", "phenotype counts", "Decorative risk; not first choice for BMC style.", "render_optional", (19, 22, 18, 13, 6)),
        ("F3-C1", "F3-C", "HF012", "k-selection dual-metric trend", "Best high-fidelity match for silhouette and ARI across candidate k.", "k, silhouette, bootstrap ARI", "Dual-axis should be avoided if both metrics are already 0-1.", "render_recommended", (29, 25, 18, 14, 9)),
        ("F3-C2", "F3-C", "portable:time_series_dual_axis", "portable line/trend template", "Clean and direct for k-selection metrics.", "k and metric values", "Less visual richness.", "render_optional", (28, 25, 14, 15, 9)),
        ("F3-C3", "F3-C", "HF132", "dashboard mini line panel", "Keeps Figure 3 visually integrated if F3B also uses HF132.", "k and metric values", "Could under-emphasize model-selection guardrails.", "render_optional", (23, 24, 17, 14, 8)),
        ("F4-A1", "F4-A", "HF206", "high-fidelity heatmap/block matrix with optional side summaries", "Best high-fidelity match for phenotype-profile heatmap.", "phenotype by variable weighted profile matrix", "Circular add-ons must be justified or omitted.", "render_recommended", (30, 25, 20, 14, 9)),
        ("F4-A2", "F4-A", "HF013", "Pearson/Spearman-style rectangular heatmap", "Cleaner heatmap grammar; good if we want less decorative clinical profile presentation.", "phenotype by variable matrix", "Correlation title/legend language must be changed to profile deviations.", "render_optional", (27, 25, 18, 14, 9)),
        ("F4-A3", "F4-A", "HF103", "PCA + heatmap phenotype profile dashboard", "Useful if Figure 4 should link profile heatmap with latent-space separation.", "profile matrix plus phenotype coordinates", "Adds another data layer; may duplicate Figure 3.", "render_optional", (23, 22, 20, 14, 8)),
        ("F4-A4", "F4-A", "portable:correlation_heatmap", "portable correlation/heatmap template", "Most conservative rectangular heatmap option.", "profile matrix", "Less high-fidelity than HF options.", "hold_native", (25, 25, 14, 15, 9)),
        ("F5-A1", "F5-A", "portable:forest_plot", "forest plot of prevalence ratios with bootstrap intervals", "Best statistical grammar for effect sizes and no-enrichment reference line.", "endpoint, phenotype, prevalence ratio, bootstrap CI", "Requires careful interval rendering for small P0 to avoid overcrowding.", "render_recommended", (30, 25, 16, 15, 9)),
        ("F5-A2", "F5-A", "HF197", "clinical prediction dashboard effect-size block", "Good if Figure 5 should look like a clinical model-performance panel set.", "prevalence ratios by endpoint and phenotype", "Confusion-matrix parts must be removed; otherwise mismatched.", "render_optional", (24, 23, 19, 14, 8)),
        ("F5-A3", "F5-A", "HF206", "lollipop/heatmap endpoint-enrichment matrix", "Good if we convert phenotype-by-endpoint PR values into a compact matrix/lollipop hybrid.", "endpoint by phenotype PR matrix", "Changes forest-plot reading to matrix reading.", "render_optional", (24, 24, 20, 14, 8)),
        ("F5-B1", "F5-B", "HF197", "clinical performance dashboard grouped metric panel", "Best high-fidelity match for AUPRC enrichment and supervised-model comparison.", "endpoint, feature set, AUPRC enrichment", "Must avoid overclaiming diagnostic model performance.", "render_recommended", (29, 25, 20, 14, 9)),
        ("F5-B2", "F5-B", "portable:feature_importance_with_correlation", "feature-importance/model-contribution style bar with correlation inset", "Useful if reframed as incremental information from SSL feature sets.", "model metrics plus optional endpoint correlation matrix", "Would require extra correlation/increment table to avoid decorative inset.", "render_optional", (22, 21, 17, 15, 8)),
        ("F5-B3", "F5-B", "HF092", "SHAP/bar/beeswarm-style contribution dashboard", "Strong AI-method visual language if we add real feature contribution or embedding-importance data.", "AUPRC enrichment; optional feature contribution values", "Not suitable unless real contribution data are available.", "hold_native", (18, 16, 20, 14, 6)),
        ("FS1-A1", "FS1-A", "HF012", "training-loss trend using dual-axis style stripped to one metric", "Best high-fidelity trend style for SSL convergence.", "epoch and masked reconstruction MSE", "Dual-axis styling should be simplified to one y-axis.", "render_recommended", (29, 25, 18, 14, 9)),
        ("FS1-A2", "FS1-A", "portable:time_series_dual_axis", "portable time-series training curve", "Most direct and conservative method-diagnostic curve.", "epoch and MSE", "Less high-fidelity.", "render_optional", (28, 25, 14, 15, 9)),
        ("FS1-A3", "FS1-A", "HF206", "diagnostic dashboard with loss curve plus compact heatmap inset", "Useful if S1 becomes a method-diagnostics dashboard.", "epoch/MSE plus feature audit metrics", "May overcomplicate a supplementary panel.", "render_optional", (22, 21, 19, 14, 8)),
        ("FS1-B1", "FS1-B", "portable:ridge_density", "ridge density for used versus unused feature missingness", "Best match for comparing two missingness distributions.", "missing_train and used_in_primary_encoder", "Needs careful bandwidth/binning to avoid artificial patterns.", "render_recommended", (29, 25, 16, 15, 9)),
        ("FS1-B2", "FS1-B", "portable:box_violin_dot", "box/violin/dot distribution panel", "More transparent for distribution comparison than histogram overlay.", "missing_train and used flag", "Can look sparse if many values stack at 0 or 1.", "render_optional", (27, 25, 15, 15, 9)),
        ("FS1-B3", "FS1-B", "HF001", "raincloud-style distribution panel", "High-fidelity distribution style with strong journal typography.", "missingness values by feature-use group", "Original capsule is not exactly missingness-specific; requires careful port.", "render_optional", (24, 25, 18, 14, 8)),
    ]

    template_paths = {
        "portable:panel_workflow": r"_portable_patterns\patterns\panel_workflow\panel_redraw_runner_template.py",
        "portable:percent_stacked_bar": r"_portable_patterns\patterns\composition\percent_stacked_bar_template.py",
        "portable:time_series_dual_axis": r"_portable_patterns\patterns\time_spatial\time_series_dual_axis_template.py",
        "portable:ridge_density": r"_portable_patterns\patterns\group_distribution\ridge_density_template.py",
        "portable:pca_heatmap": r"_portable_patterns\patterns\correlation_omics\pca_heatmap_template.py",
        "portable:correlation_heatmap": r"_portable_patterns\patterns\correlation_omics\correlation_heatmap_template.py",
        "portable:forest_plot": r"_portable_patterns\patterns\group_distribution\forest_plot_template.py",
        "portable:feature_importance_with_correlation": r"_portable_patterns\patterns\model_explainability\feature_importance_with_correlation_template.py",
        "portable:box_violin_dot": r"_portable_patterns\patterns\group_distribution\box_violin_dot_template.py",
    }

    panel_by_id = {row["Panel"]: row for row in panels}
    candidates: list[dict[str, object]] = []
    for option, panel, source_id, method, why, required, risk, decision, scores in candidate_specs:
        if source_id.startswith("HF"):
            meta = hf_meta(hf, source_id)
        else:
            meta = persist_meta(idx, source_id, template_paths[source_id])
        scoring = score(*scores)
        candidates.append(
            {
                "Option": option,
                "Panel": panel,
                "Figure": panel_by_id[panel]["Figure"],
                "Proposed chart": method,
                "PERSIST template/capsule": meta.get("id", source_id),
                "Candidate kind": meta.get("kind", ""),
                "Source surface": meta.get("source_surface", "PERSIST high-fidelity capsule catalog"),
                "Candidate title": meta.get("title", ""),
                "Capsule or template path": meta.get("path", ""),
                "Reference visual": meta.get("reference", ""),
                "Source script/snapshot": meta.get("source", ""),
                "Runtime": "Python preferred; R only if survey-specific CI is added",
                "Why it fits": why,
                "Required data": required,
                "Risk / missing item": risk,
                "Render decision": decision,
                **scoring,
            }
        )

    write_tsv(OUT / "panel_inventory.tsv", panels)
    write_tsv(OUT / "panel_template_candidates.tsv", candidates)

    # Reviewer-facing markdown shortlist.
    lines: list[str] = []
    lines.append("# PERSIST Stage-1 Panel Candidate Shortlist")
    lines.append("")
    lines.append("Status: candidate selection only. No panel is finalized and no new final figure should be assembled before user approval.")
    lines.append("")
    lines.append("Identifier rule: `HF...` entries come from the PERSIST high-fidelity capsule catalog; `portable:...` entries are explicit reusable pattern paths and are not PERSIST indexed-code IDs.")
    lines.append("")
    lines.append("## Panel Inventory")
    lines.append("")
    lines.append("| Panel | Current type | One-sentence conclusion | Data task | Data source status |")
    lines.append("|---|---|---|---|---|")
    for row in panels:
        lines.append(f"| {row['Panel']} | {row['Current type']} | {row['One-sentence conclusion']} | {row['Data task']} | {row['Data source status']} |")
    lines.append("")
    lines.append("## Candidate Options")
    lines.append("")
    for panel in [row["Panel"] for row in panels]:
        pinfo = panel_by_id[panel]
        lines.append(f"### {panel} ({pinfo['Figure']})")
        lines.append("")
        lines.append("| Option | Proposed chart | Capsule/template ID | Decision | Score | Main risk |")
        lines.append("|---|---|---|---|---:|---|")
        for row in [r for r in candidates if r["Panel"] == panel]:
            lines.append(
                f"| {row['Option']} | {row['Proposed chart']} | {row['PERSIST template/capsule']} | {row['Render decision']} | {row['Total score']} | {row['Risk / missing item']} |"
            )
        lines.append("")
    lines.append("## Approval Syntax")
    lines.append("")
    lines.append("Reply with option IDs such as `F1-W1, F2-A1, F2-B1, ...`, or say `render all recommended options` to render only rows marked `render_recommended`.")
    lines.append("")
    (OUT / "panel_candidate_shortlist.md").write_text("\n".join(lines), encoding="utf-8")

    # Reference gallery with local image paths where available.
    glines: list[str] = ["# Candidate Reference Visual Gallery", "", "Only candidates with an existing reference image are shown."]
    for row in candidates:
        ref = str(row["Reference visual"])
        if ref and ref.lower() != "nan" and Path(ref).exists():
            glines.append("")
            glines.append(f"## {row['Option']} | {row['PERSIST template/capsule']}")
            glines.append("")
            glines.append(f"![{row['Option']}]({ref})")
            glines.append("")
            glines.append(f"- Proposed chart: {row['Proposed chart']}")
            glines.append(f"- Risk: {row['Risk / missing item']}")
    (OUT / "panel_candidate_reference_gallery.md").write_text("\n".join(glines), encoding="utf-8")

    print(f"Wrote {OUT}")
    print(f"Panels: {len(panels)}")
    print(f"Candidates: {len(candidates)}")


if __name__ == "__main__":
    main()
