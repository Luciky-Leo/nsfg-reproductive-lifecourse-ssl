"""Prepare a PERSIST/PRISM Stage-2 render plan without finalizing panels.

This script converts the Stage-1 candidate table into an auditable render plan.
It does not render figures and does not create panel_final_selection files.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE1 = ROOT / "figure_redraw" / "panel_stage1_selection_20260602"
CANDIDATES = STAGE1 / "panel_template_candidates.tsv"
PLAN_TSV = STAGE1 / "persist_stage2_recommended_render_plan.tsv"
PLAN_MD = STAGE1 / "persist_stage2_recommended_render_plan.md"

RECOMMENDED_OPTIONS = [
    "F1-W1",
    "F2-A1",
    "F2-B1",
    "F2-C1",
    "F3-A1",
    "F3-B1",
    "F3-C1",
    "F4-A1",
    "F5-A1",
    "F5-B1",
    "FS1-A1",
    "FS1-B1",
]

MUST_FIX = {
    "F1-W": "Make the workflow look like a polished registry-analysis workflow, not a boxed draft flowchart; keep no A/B/C/D labels for single workflow.",
    "F2-A": "Keep cohort count labels readable and aligned; preserve cycle order.",
    "F2-B": "Use one y-axis unless a second metric is data-backed; avoid dual-axis decoration.",
    "F2-C": "Manage long feature names by wrapping, truncation with source labels, or domain grouping.",
    "F3-A": "Use real PC1/PC2 embedding coordinates only; do not add decorative loading/correlation insets unless computed.",
    "F3-B": "Show both phenotype counts and readable P0/P1/P2 labels; avoid radial decoration unless explicitly selected.",
    "F3-C": "Clarify that silhouette and bootstrap ARI are model-selection metrics; avoid implying test-set tuning.",
    "F4-A": "Remove unnecessary single-panel label if the final figure remains one panel; keep raw values and standardized color scale interpretable.",
    "F5-A": "Must show prevalence-ratio bootstrap CI intervals with no-enrichment reference line; point estimates alone are not acceptable.",
    "F5-B": "Avoid performance-improvement wording; label as secondary risk-enrichment summaries.",
    "FS1-A": "Show SSL training loss as method diagnostic only; avoid overclaiming model superiority.",
    "FS1-B": "Compare used versus unused feature missingness transparently; avoid artificial density smoothing if values stack.",
}

DATA_SOURCE_HINTS = {
    "F1-W": "results/tables/harmonized_matrix_summary.csv; manuscript/tables/table1_cohort_characteristics.csv",
    "F2-A": "manuscript/tables/table1_cohort_characteristics.csv",
    "F2-B": "results/tables/harmonized_cycle_linkage_summary.csv",
    "F2-C": "results/tables/ssl_feature_audit.csv",
    "F3-A": "results/tables/embedding_pca_test.csv or current embedding intermediate table from figure script",
    "F3-B": "results/tables/phenotype_profiles_test_weighted.csv and phenotype assignment outputs",
    "F3-C": "results/tables/cluster_selection_metrics.csv",
    "F4-A": "manuscript/tables/table3_phenotype_profiles.csv; results/tables/phenotype_profiles_test_weighted.csv",
    "F5-A": "results/tables/endpoint_enrichment_by_phenotype_test.csv with bootstrap CI columns",
    "F5-B": "results/tables/supervised_validation_metrics.csv; manuscript/tables/table4_endpoint_enrichment_model_metrics.csv",
    "FS1-A": "results/tables/ssl_training_curve.csv",
    "FS1-B": "results/tables/ssl_feature_audit.csv",
}


def read_candidates() -> list[dict[str, str]]:
    with CANDIDATES.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> None:
    rows = read_candidates()
    by_option = {row["Option"]: row for row in rows}
    selected = []
    missing = [option for option in RECOMMENDED_OPTIONS if option not in by_option]
    if missing:
        raise SystemExit(f"Recommended options missing from candidate table: {missing}")

    for option in RECOMMENDED_OPTIONS:
        row = by_option[option]
        panel = row["Panel"]
        selected.append(
            {
                "Option": option,
                "Panel": panel,
                "Figure": row["Figure"],
                "Recommended chart": row["Proposed chart"],
                "Template/capsule": row["PERSIST template/capsule"],
                "Candidate kind": row["Candidate kind"],
                "Runtime": row["Runtime"],
                "Data source hints": DATA_SOURCE_HINTS.get(panel, row["Required data"]),
                "Required data": row["Required data"],
                "Must-fix notes": MUST_FIX.get(panel, row["Risk / missing item"]),
                "Risk / missing item": row["Risk / missing item"],
                "Total score": row["Total score"],
                "Status": "recommended_not_final",
            }
        )

    PLAN_TSV.parent.mkdir(parents=True, exist_ok=True)
    with PLAN_TSV.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(selected[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(selected)

    lines = [
        "# PERSIST Stage-2 Recommended Render Plan",
        "",
        "Status: recommended only, not final. Do not render or replace manuscript figures until the user approves panel options and `panel_final_selection.tsv` is created.",
        "",
        "Recommended approval string:",
        "",
        "`" + ", ".join(RECOMMENDED_OPTIONS) + "`",
        "",
        "## Recommended Panels",
        "",
        "| Option | Figure | Panel | Template/capsule | Data source hints | Must-fix notes |",
        "|---|---|---|---|---|---|",
    ]
    for row in selected:
        lines.append(
            "| {Option} | {Figure} | {Panel} | {Template/capsule} | {Data source hints} | {Must-fix notes} |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    lines += [
        "",
        "## Gate",
        "",
        "Use `scripts/record_persist_panel_selection.py` only after explicit user approval. The recorder validates one option per panel and writes the final selection files.",
        "",
    ]
    PLAN_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {PLAN_TSV}")
    print(f"Wrote {PLAN_MD}")


if __name__ == "__main__":
    main()
