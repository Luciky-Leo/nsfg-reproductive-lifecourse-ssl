"""Submission-readiness QA for the NSFG SSL LaTeX package.

The checks here are intentionally conservative: they verify what can be proven
from current local files, and they keep figure/authorship gates explicit rather
than silently treating the draft as final.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from validate_submission_metadata import validate as validate_submission_metadata
from validate_panel_selection import validate as validate_panel_selection


ROOT = Path(__file__).resolve().parents[1]
LATEX = ROOT / "manuscript" / "latex"
RESULT_TABLES = ROOT / "results" / "tables"
MANUSCRIPT_TABLES = ROOT / "manuscript" / "tables"
ANALYSIS_REVIEW = ROOT / "analysis_review"
QA_JSON = ANALYSIS_REVIEW / "submission_package_qa_20260604.json"
FIGURE_GATE = ROOT / "figure_redraw" / "STAGE2_RENDERING_GATE.md"
PERSIST_PROVENANCE = ROOT / "figure_redraw" / "PERSIST_IDENTIFIER_PROVENANCE.md"
FINAL_HANDOFF = ROOT / "docs" / "final_submission_handoff.md"
FINAL_USER_INPUTS = ROOT / "docs" / "final_user_inputs_required_20260604.md"
FINAL_GATE_STATUS = ROOT / "analysis_review" / "final_gate_status_20260604.json"
CONSISTENCY_AUDIT = ROOT / "analysis_review" / "manuscript_data_consistency_audit_20260604.json"
EXPORTS = ROOT / "manuscript" / "exports"
FINAL_CLOSEOUT = ROOT / "scripts" / "final_closeout.py"
FINAL_INPUTS_APPLIER = ROOT / "scripts" / "apply_final_submission_inputs.py"
FIGURE5_REPLACER = ROOT / "scripts" / "replace_approved_figure5.py"
FIGURE5_VALIDATION = ANALYSIS_REVIEW / "figure5_finalsize_candidate_validation_20260604.json"
FIGURE5_CANDIDATE_ROOT = ROOT / "figure_redraw" / "preapproval_figure5_finalsize_candidate_20260604"


REQUIRED_FIGURE_STEMS = [
    "figure1_workflow",
    "figure2_matrix_missingness",
    "figure3_embedding_phenotypes",
    "figure4_phenotype_profiles",
    "figure5_risk_enrichment",
    "figure6_model_diagnostics",
    "figure7_ssl_diagnostics",
]

STALE_PATTERNS = [
    "respondent-level nonparametric",
    "should be released",
    "clinically interpretable temporal-validation",
    "model performance",
    "external clinical validation",
    "foundation-style",
    "large foundation model for reproductive health",
]

REQUIRED_MAIN_PATTERNS = [
    r"stratified cluster bootstrap",
    r"\\texttt\{VEST\}",
    r"\\texttt\{VECL\}",
    r"temporal validation",
    r"not interpreted as bedside diagnostic models",
]

ENDPOINT_LABELS = {
    "adverse_pregnancy_history_proxy": "Adverse pregnancy-history proxy",
    "contraceptive_vulnerability": "Contraceptive vulnerability",
    "fertility_service_or_loss_help": "Fertility or loss help",
    "impaired_fecundity_status": "Impaired fecundity",
    "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy history",
}


@dataclass
class Check:
    area: str
    status: str
    detail: str
    evidence: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def add(checks: list[Check], area: str, status: str, detail: str, evidence: str) -> None:
    checks.append(Check(area=area, status=status, detail=detail, evidence=evidence))


def scoped_status_counts(checks: list[Check], excluded_area: str | None = None) -> dict[str, int]:
    scoped = [
        check
        for check in checks
        if excluded_area is None or check.area != excluded_area
    ]
    return {
        "pass": sum(1 for check in scoped if check.status == "pass"),
        "warn": sum(1 for check in scoped if check.status == "warn"),
        "fail": sum(1 for check in scoped if check.status == "fail"),
    }


def check_required_files(checks: list[Check]) -> None:
    required = [
        LATEX / "main.tex",
        LATEX / "main.pdf",
        LATEX / "supplementary_information.tex",
        LATEX / "supplementary_information.pdf",
        LATEX / "submission_package_manifest.json",
        LATEX / "tables" / "table4.tex",
        LATEX / "tables" / "tableS2_endpoint_enrichment_ci.tex",
        RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv",
        RESULT_TABLES / "endpoint_enrichment_bootstrap_design_summary.csv",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        add(checks, "required_files", "fail", "Required files are missing.", "; ".join(missing))
    else:
        add(checks, "required_files", "pass", "Core manuscript, table, and endpoint-CI files exist.", f"{len(required)} files checked")

    missing_figs = []
    for stem in REQUIRED_FIGURE_STEMS:
        for ext in [".pdf", ".png"]:
            path = LATEX / "figures" / f"{stem}{ext}"
            if not path.exists():
                missing_figs.append(path.name)
    if missing_figs:
        add(checks, "figure_assets", "fail", "Required figure assets are missing.", "; ".join(missing_figs))
    else:
        add(checks, "figure_assets", "pass", "All required figure PDF/PNG assets exist.", f"{len(REQUIRED_FIGURE_STEMS) * 2} files checked")

    main_tex = LATEX / "main.tex"
    main_pdf = LATEX / "main.pdf"
    if main_tex.exists() and main_pdf.exists():
        if main_pdf.stat().st_mtime + 1 < main_tex.stat().st_mtime:
            add(checks, "required_files", "warn", "main.pdf is older than main.tex and should be recompiled.", "main.tex was modified after main.pdf")
        else:
            add(checks, "required_files", "pass", "main.pdf is current relative to main.tex.", "main.pdf timestamp >= main.tex timestamp")
    supp_tex = LATEX / "supplementary_information.tex"
    supp_pdf = LATEX / "supplementary_information.pdf"
    if supp_tex.exists() and supp_pdf.exists():
        if supp_pdf.stat().st_mtime + 1 < supp_tex.stat().st_mtime:
            add(checks, "required_files", "warn", "supplementary_information.pdf is older than supplementary_information.tex and should be recompiled.", "supplementary_information.tex was modified after supplementary_information.pdf")
        else:
            add(checks, "required_files", "pass", "supplementary_information.pdf is current relative to supplementary_information.tex.", "supplementary_information.pdf timestamp >= supplementary_information.tex timestamp")


def check_latex_compile_log(checks: list[Check]) -> None:
    log_path = LATEX / "main.log"
    if not log_path.exists():
        add(
            checks,
            "latex_compile",
            "warn",
            "LaTeX compile log is missing, so unresolved-reference checks cannot be proven.",
            str(log_path.relative_to(ROOT)),
        )
        return

    log_text = read_text(log_path)
    # Tectonic writes all automatic reruns into one captured stream. First-pass
    # undefined-reference warnings are expected when labels are created and
    # should not fail QA if the final run resolved them.
    if "note: Rerunning TeX" in log_text:
        log_text = log_text.split("note: Rerunning TeX")[-1]
    fail_patterns = [
        r"LaTeX Warning: Reference `[^']+' .* undefined",
        r"LaTeX Warning: Citation `[^']+' .* undefined",
        r"There were undefined references",
        r"undefined citations",
        r"Rerun to get cross-references right",
        r"Label\(s\) may have changed",
    ]
    fail_hits = [pattern for pattern in fail_patterns if re.search(pattern, log_text)]
    if fail_hits:
        add(
            checks,
            "latex_compile",
            "fail",
            "LaTeX compile log contains unresolved reference or citation warnings.",
            "; ".join(fail_hits),
        )
        return

    overfull_hits = re.findall(r"Overfull \\hbox .*", log_text)
    if overfull_hits:
        add(
            checks,
            "latex_compile",
            "warn",
            "LaTeX compile log contains overfull boxes that may need layout review.",
            f"{len(overfull_hits)} overfull hbox warning(s)",
        )
    else:
        add(
            checks,
            "latex_compile",
            "pass",
            "LaTeX compile log has no unresolved references, citation warnings, or overfull boxes.",
            str(log_path.relative_to(ROOT)),
        )


def check_manifest(checks: list[Check]) -> None:
    manifest_path = LATEX / "submission_package_manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(read_text(manifest_path))
    listed_figures = sorted(manifest.get("figures", []))
    actual_figures = sorted(p.name for p in (LATEX / "figures").glob("*") if p.is_file())
    if listed_figures != actual_figures:
        add(checks, "manifest", "fail", "Manifest figure list does not match actual figure directory.", f"listed={len(listed_figures)} actual={len(actual_figures)}")
    else:
        add(checks, "manifest", "pass", "Manifest figure list matches actual figure directory.", f"{len(actual_figures)} figure assets")
    listed_tables = sorted(manifest.get("tables", []))
    actual_tables = sorted(p.name for p in (LATEX / "tables").glob("*.tex"))
    if listed_tables != actual_tables:
        add(checks, "manifest", "fail", "Manifest table list does not match actual table directory.", f"listed={listed_tables}; actual={actual_tables}")
    else:
        add(checks, "manifest", "pass", "Manifest table list matches actual table directory.", f"{len(actual_tables)} table includes")
    actual_source = len(list((LATEX / "source_data").glob("*.csv")))
    if int(manifest.get("source_data_files", -1)) != actual_source:
        add(checks, "manifest", "fail", "Manifest source-data count does not match actual source_data directory.", f"manifest={manifest.get('source_data_files')} actual={actual_source}")
    else:
        add(checks, "manifest", "pass", "Manifest source-data count matches actual source_data directory.", f"{actual_source} CSV files")


def check_source_data_hashes(checks: list[Check]) -> None:
    mismatches: list[str] = []
    checked = 0
    source_dir = LATEX / "source_data"
    for source in list(RESULT_TABLES.glob("*.csv")) + list(MANUSCRIPT_TABLES.glob("*.csv")):
        packaged = source_dir / source.name
        if packaged.exists():
            checked += 1
            if sha256(source) != sha256(packaged):
                mismatches.append(source.name)
    if mismatches:
        add(checks, "source_data_hash", "fail", "Packaged source-data CSV files differ from source tables.", "; ".join(mismatches))
    else:
        add(checks, "source_data_hash", "pass", "Packaged source-data CSV files match source tables by SHA-256.", f"{checked} copied CSV files checked")


def check_manuscript_data_consistency(checks: list[Check]) -> None:
    if not CONSISTENCY_AUDIT.exists():
        add(
            checks,
            "data_consistency",
            "warn",
            "Manuscript-data consistency audit has not been run yet.",
            str(CONSISTENCY_AUDIT.relative_to(ROOT)),
        )
        return

    audit = json.loads(read_text(CONSISTENCY_AUDIT))
    counts = audit.get("counts", {})
    fail_count = int(counts.get("fail", 0))
    warn_count = int(counts.get("warn", 0))
    if CONSISTENCY_AUDIT.stat().st_mtime + 1 < (LATEX / "main.tex").stat().st_mtime:
        add(
            checks,
            "data_consistency",
            "warn",
            "Manuscript-data consistency audit is older than main.tex.",
            str(CONSISTENCY_AUDIT.relative_to(ROOT)),
        )
    elif fail_count:
        failed = [
            f"{row.get('area')}: {row.get('detail')}"
            for row in audit.get("checks", [])
            if row.get("status") == "fail"
        ]
        add(
            checks,
            "data_consistency",
            "fail",
            "Manuscript-data consistency audit has failed checks.",
            "; ".join(failed),
        )
    else:
        add(
            checks,
            "data_consistency",
            "pass",
            "Manuscript-data consistency audit has no failed checks.",
            f"{counts.get('pass', 0)} audit pass; {warn_count} audit warning(s), covered by figure/authorship gates where applicable",
        )


def check_main_text(checks: list[Check]) -> None:
    main = read_text(LATEX / "main.tex")
    metadata_result = validate_submission_metadata()
    stale_hits = [pat for pat in STALE_PATTERNS if pat in main]
    if stale_hits:
        add(checks, "main_text", "fail", "Stale or overclaiming manuscript language remains.", "; ".join(stale_hits))
    else:
        add(checks, "main_text", "pass", "No stale or overclaiming phrase hits in main.tex.", f"{len(STALE_PATTERNS)} patterns checked")
    missing_required = [pat for pat in REQUIRED_MAIN_PATTERNS if not re.search(pat, main)]
    if missing_required:
        add(checks, "main_text", "fail", "Required conservative/statistical wording is missing.", "; ".join(missing_required))
    else:
        add(checks, "main_text", "pass", "Required conservative/statistical wording is present.", f"{len(REQUIRED_MAIN_PATTERNS)} patterns checked")
    embedded_supplement_hits = [
        pattern
        for pattern in [
            r"\\input\{tables/tableS",
            r"figures/supplementary_robustness_age_adjusted",
            r"figures/supplementary_method_leakage_sensitivity",
            r"figures/supplementary_subgroup_robustness",
            r"figures/FIG9.png",
            r"figures/FIG10.png",
        ]
        if re.search(pattern, main)
    ]
    if embedded_supplement_hits:
        add(
            checks,
            "main_text",
            "fail",
            "Supplementary tables or supplementary figures remain embedded in main.tex.",
            "; ".join(embedded_supplement_hits),
        )
    else:
        add(
            checks,
            "main_text",
            "pass",
            "Supplementary tables and figures are not embedded in main.tex.",
            "supplementary material is separated into supplementary_information.tex/pdf",
        )

    placeholder_hits = []
    for phrase in [
        "Author 1",
        "Author 2",
        "Author 3",
        "Corresponding Author",
        "Corresponding author to be completed",
        "Department/Institution to be completed",
        "Affiliation to be completed",
        "should be completed before submission",
    ]:
        if phrase in main:
            placeholder_hits.append(phrase)
    if placeholder_hits:
        evidence_parts = ["; ".join(placeholder_hits)]
        if not metadata_result["valid"]:
            evidence_parts.append("metadata: " + "; ".join(metadata_result.get("issues", [])))
        add(checks, "authorship", "warn", "Author/declaration placeholders remain and block final submission.", " | ".join(evidence_parts))
    elif not metadata_result["valid"]:
        add(checks, "authorship", "warn", "Submission metadata is incomplete and blocks final submission.", "; ".join(metadata_result.get("issues", [])))
    else:
        add(checks, "authorship", "pass", "No default author/declaration placeholders detected and submission metadata validates.", "main.tex; config/submission_metadata.json")


def check_endpoint_tables(checks: list[Check]) -> None:
    endpoint_rows = read_csv(RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    table4_rows = read_csv(MANUSCRIPT_TABLES / "table4_endpoint_enrichment_model_metrics.csv")
    design_rows = read_csv(RESULT_TABLES / "endpoint_enrichment_bootstrap_design_summary.csv")
    table4_tex = read_text(LATEX / "tables" / "table4.tex")
    table_s2 = read_text(LATEX / "tables" / "tableS2_endpoint_enrichment_ci.tex")

    expected_pairs = {(endpoint, str(ph)) for endpoint in ENDPOINT_LABELS for ph in [0, 1, 2]}
    observed_pairs = {(row["endpoint"], str(int(float(row["phenotype"])))) for row in endpoint_rows}
    missing_pairs = sorted(expected_pairs - observed_pairs)
    if missing_pairs:
        add(checks, "endpoint_tables", "fail", "Endpoint-by-phenotype CI table is incomplete.", repr(missing_pairs))
    else:
        add(checks, "endpoint_tables", "pass", "Endpoint-by-phenotype CI table has all 5 endpoints x 3 phenotypes.", f"{len(observed_pairs)} rows")

    ci_cols = [
        "prevalence_ratio_ci_low",
        "prevalence_ratio_ci_high",
        "risk_difference_ci_low",
        "risk_difference_ci_high",
    ]
    missing_ci_cols = [col for col in ci_cols if col not in endpoint_rows[0]]
    if missing_ci_cols:
        add(checks, "endpoint_tables", "fail", "Bootstrap CI columns are missing from endpoint enrichment table.", "; ".join(missing_ci_cols))
    else:
        add(checks, "endpoint_tables", "pass", "Bootstrap CI columns exist in endpoint enrichment table.", ", ".join(ci_cols))

    missing_table4_values: list[str] = []
    for row in table4_rows:
        endpoint = row["endpoint"]
        pr_ci = (
            f"{float(row['top_prevalence_ratio']):.2f} "
            f"({float(row['prevalence_ratio_ci_low']):.2f}--{float(row['prevalence_ratio_ci_high']):.2f})"
        )
        if pr_ci not in table4_tex:
            missing_table4_values.append(f"{endpoint}: {pr_ci}")
    if missing_table4_values:
        add(checks, "endpoint_tables", "fail", "Table 4 does not contain expected row-level top-phenotype PR CI text.", "; ".join(missing_table4_values))
    else:
        add(checks, "endpoint_tables", "pass", "Table 4 contains expected row-level top-phenotype PR CI text.", f"{len(table4_rows)} endpoints checked")

    if "VEST" in table4_tex and "VECL" in table4_tex and "VEST" in table_s2 and "VECL" in table_s2:
        add(checks, "endpoint_tables", "pass", "Table 4 and Table S2 state VEST/VECL bootstrap provenance.", "table4.tex; tableS2_endpoint_enrichment_ci.tex")
    else:
        add(checks, "endpoint_tables", "fail", "Endpoint tables do not state VEST/VECL bootstrap provenance.", "table4.tex; tableS2_endpoint_enrichment_ci.tex")

    design = design_rows[0]
    expected_design = {
        "bootstrap_replicates": "2000",
        "n_strata": "20",
        "n_strata_cluster_pairs": "80",
    }
    bad_design = [f"{k}={design.get(k)}" for k, v in expected_design.items() if str(design.get(k)) != v]
    if bad_design:
        add(checks, "bootstrap_design", "warn", "Bootstrap design summary differs from expected current analysis.", "; ".join(bad_design))
    else:
        add(checks, "bootstrap_design", "pass", "Bootstrap design summary matches current analysis plan.", "2000 replicates; 20 strata; 80 stratum-cluster pairs")


def check_figure_gates(checks: list[Check]) -> None:
    gate_exists = FIGURE_GATE.exists()
    panel_selection = validate_panel_selection()
    recommended_plan = ROOT / "figure_redraw" / "panel_stage1_selection_20260602" / "persist_stage2_recommended_render_plan.md"
    recorder = ROOT / "scripts" / "record_persist_panel_selection.py"
    if not gate_exists:
        add(checks, "figure_gate", "fail", "PERSIST/PRISM stage gate file is missing.", str(FIGURE_GATE))
    elif panel_selection["status"] == "warn":
        add(checks, "figure_gate", "warn", "Final PERSIST/PRISM panel selection is not recorded yet.", "; ".join(panel_selection.get("issues", [])))
    elif not panel_selection["valid"]:
        add(checks, "figure_gate", "fail", "Final PERSIST/PRISM panel selection is malformed.", "; ".join(panel_selection.get("issues", [])))
    else:
        add(checks, "figure_gate", "pass", "Final PERSIST/PRISM panel selection validates.", f"{panel_selection.get('selected_count')} panels selected")

    if recommended_plan.exists():
        plan_text = read_text(recommended_plan)
        required_notes = [
            "Recommended approval string",
            "F5-A1",
            "bootstrap CI intervals",
            "not final",
        ]
        missing_notes = [note for note in required_notes if note not in plan_text]
        if missing_notes:
            add(checks, "figure_gate", "warn", "Recommended Stage-2 render plan exists but is missing expected gate language.", "; ".join(missing_notes))
        else:
            add(checks, "figure_gate", "pass", "Recommended Stage-2 render plan exists with approval and Figure 5A CI guardrails.", str(recommended_plan.relative_to(ROOT)))
    else:
        add(checks, "figure_gate", "warn", "Recommended Stage-2 render plan is missing.", str(recommended_plan.relative_to(ROOT)))

    if recorder.exists():
        add(checks, "figure_gate", "pass", "Panel-selection recorder script exists.", str(recorder.relative_to(ROOT)))
        recorder_text = read_text(recorder)
        if "同意推荐组合" in recorder_text and "recommended" in recorder_text:
            add(checks, "figure_gate", "pass", "Panel-selection recorder accepts recommended-set aliases.", str(recorder.relative_to(ROOT)))
        else:
            add(checks, "figure_gate", "warn", "Panel-selection recorder exists but does not document recommended-set aliases.", str(recorder.relative_to(ROOT)))
    else:
        add(checks, "figure_gate", "warn", "Panel-selection recorder script is missing.", str(recorder.relative_to(ROOT)))

    if gate_exists:
        gate_text = read_text(FIGURE_GATE)
        if "Figure 5A must display prevalence-ratio bootstrap intervals" in gate_text:
            add(checks, "figure_gate", "pass", "Figure 5A interval-display requirement is explicitly recorded.", str(FIGURE_GATE.relative_to(ROOT)))
        else:
            add(checks, "figure_gate", "warn", "Figure 5A interval-display requirement is not explicit in the gate file.", str(FIGURE_GATE.relative_to(ROOT)))

    if PERSIST_PROVENANCE.exists():
        provenance_text = read_text(PERSIST_PROVENANCE)
        required_terms = ["F1-W1", "HF", "portable:", "PERSIST-0759"]
        missing_terms = [term for term in required_terms if term not in provenance_text]
        if missing_terms:
            add(checks, "figure_gate", "warn", "PERSIST identifier provenance exists but is missing expected identifier examples.", "; ".join(missing_terms))
        else:
            add(checks, "figure_gate", "pass", "PERSIST identifier provenance explains project, HF, portable, and legacy IDs.", str(PERSIST_PROVENANCE.relative_to(ROOT)))
    else:
        add(checks, "figure_gate", "warn", "PERSIST identifier provenance note is missing.", str(PERSIST_PROVENANCE.relative_to(ROOT)))


def check_figure5_candidate_validation(checks: list[Check]) -> None:
    if not FIGURE5_VALIDATION.exists():
        add(
            checks,
            "figure_candidate",
            "warn",
            "Figure 5 final-size candidate validation report is missing.",
            str(FIGURE5_VALIDATION.relative_to(ROOT)),
        )
        return

    validation = json.loads(read_text(FIGURE5_VALIDATION))
    counts = validation.get("counts", {})
    fail_count = int(counts.get("fail", 0))
    warn_count = int(counts.get("warn", 0))

    candidate_files = [
        FIGURE5_CANDIDATE_ROOT / "outputs" / "figure5_finalsize_preapproval_candidate.png",
        FIGURE5_CANDIDATE_ROOT / "outputs" / "figure5_finalsize_preapproval_candidate.pdf",
        FIGURE5_CANDIDATE_ROOT / "outputs" / "figure5_finalsize_preapproval_candidate.svg",
        FIGURE5_CANDIDATE_ROOT / "intermediate_tables" / "figure5_finalsize_panelA_mapped.tsv",
        FIGURE5_CANDIDATE_ROOT / "intermediate_tables" / "figure5_finalsize_panelB_mapped.tsv",
        RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv",
        RESULT_TABLES / "supervised_validation_metrics.csv",
    ]
    existing_candidate_files = [path for path in candidate_files if path.exists()]
    newest_candidate_mtime = max((path.stat().st_mtime for path in existing_candidate_files), default=0)

    if FIGURE5_VALIDATION.stat().st_mtime + 1 < newest_candidate_mtime:
        add(
            checks,
            "figure_candidate",
            "warn",
            "Figure 5 final-size candidate validation report is older than candidate/source files.",
            str(FIGURE5_VALIDATION.relative_to(ROOT)),
        )
    elif fail_count:
        failed = [
            f"{row.get('area')}: {row.get('detail')}"
            for row in validation.get("checks", [])
            if row.get("status") == "fail"
        ]
        add(
            checks,
            "figure_candidate",
            "fail",
            "Figure 5 final-size candidate validation has failed checks.",
            "; ".join(failed),
        )
    elif warn_count:
        if str(validation.get("status", "")) == "candidate_only_not_manuscript_replacement":
            add(
                checks,
                "figure_candidate",
                "pass",
                "Historical Figure 5 pre-approval candidate has non-blocking warnings and is not used as the current manuscript asset.",
                f"{counts.get('pass', 0)} pass; {warn_count} non-blocking candidate warning(s); current manuscript Figure 5 is checked separately",
            )
        else:
            add(
                checks,
                "figure_candidate",
                "warn",
                "Figure 5 final-size candidate validation has warning checks.",
                f"{counts.get('pass', 0)} pass; {warn_count} warn; 0 fail",
            )
    else:
        add(
            checks,
            "figure_candidate",
            "pass",
            "Figure 5 final-size candidate validates against source tables, final-size output, and PRISM/PERSIST QC.",
            f"{counts.get('pass', 0)} validation pass; 0 warn; 0 fail",
        )


def check_figure5_replacement_runner(checks: list[Check]) -> None:
    if not FIGURE5_REPLACER.exists():
        add(
            checks,
            "figure_replacement",
            "warn",
            "Guarded Figure 5 replacement script is missing.",
            str(FIGURE5_REPLACER.relative_to(ROOT)),
        )
        return

    replacer_text = read_text(FIGURE5_REPLACER)
    required_markers = {
        "validate_panel_selection": "requires a valid final panel selection",
        "F5-A1": "requires the approved Figure 5A candidate option",
        "F5-B1": "requires the approved Figure 5B candidate option",
        "figure5_finalsize_candidate_validation_20260604.json": "requires the clean candidate validation report",
        "preapproval_figure5_finalsize_candidate_20260604": "uses the validated final-size candidate root",
        "results\" / \"figures": "targets results/figures so LaTeX package rebuilds inherit the replacement",
        "manuscript\" / \"latex\" / \"figures": "also updates the current LaTeX figure directory",
        "replacement_backup": "backs up replaced Figure 5 assets",
        "Dry run only; no Figure 5 assets were replaced.": "defaults to dry-run behavior",
        "parser.add_argument(\n        \"--write\"": "requires an explicit --write switch for replacement",
    }
    missing = [description for marker, description in required_markers.items() if marker not in replacer_text]
    if missing:
        add(
            checks,
            "figure_replacement",
            "warn",
            "Guarded Figure 5 replacement script exists but is missing expected safeguards.",
            "; ".join(missing),
        )
    else:
        add(
            checks,
            "figure_replacement",
            "pass",
            "Guarded Figure 5 replacement script requires panel approval, clean validation, backups, and explicit --write.",
            str(FIGURE5_REPLACER.relative_to(ROOT)),
        )


def check_final_handoff(checks: list[Check]) -> None:
    if not FINAL_HANDOFF.exists():
        add(checks, "final_handoff", "warn", "Final submission handoff document is missing.", str(FINAL_HANDOFF.relative_to(ROOT)))
        return
    handoff_text = read_text(FINAL_HANDOFF)
    required_terms = [
        "config/submission_metadata.json",
        "record_persist_panel_selection.py",
        "0 fail",
        "0 warn",
        "final Overleaf archive",
    ]
    missing_terms = [term for term in required_terms if term not in handoff_text]
    if missing_terms:
        add(checks, "final_handoff", "warn", "Final submission handoff exists but is missing expected closeout instructions.", "; ".join(missing_terms))
    else:
        add(checks, "final_handoff", "pass", "Final submission handoff documents the remaining gates and closeout commands.", str(FINAL_HANDOFF.relative_to(ROOT)))

    if FINAL_GATE_STATUS.exists():
        gate_status = json.loads(read_text(FINAL_GATE_STATUS))
        if "final_ready" in gate_status and "gates" in gate_status:
            add(checks, "final_handoff", "pass", "Machine-readable final gate status exists.", str(FINAL_GATE_STATUS.relative_to(ROOT)))
        else:
            add(checks, "final_handoff", "warn", "Final gate status file exists but is missing expected keys.", str(FINAL_GATE_STATUS.relative_to(ROOT)))
    else:
        add(checks, "final_handoff", "warn", "Machine-readable final gate status file is missing.", str(FINAL_GATE_STATUS.relative_to(ROOT)))

    if FINAL_USER_INPUTS.exists():
        input_text = read_text(FINAL_USER_INPUTS)
        required_input_terms = [
            "Submission Metadata",
            "PERSIST/PRISM Panel Approval",
            "同意推荐组合",
            "final_closeout.py",
        ]
        missing_input_terms = [term for term in required_input_terms if term not in input_text]
        if missing_input_terms:
            add(checks, "final_handoff", "warn", "Final user-input form exists but is missing expected decision terms.", "; ".join(missing_input_terms))
        else:
            add(checks, "final_handoff", "pass", "Final user-input form documents the two remaining user gates.", str(FINAL_USER_INPUTS.relative_to(ROOT)))
    else:
        add(checks, "final_handoff", "warn", "Final user-input form is missing.", str(FINAL_USER_INPUTS.relative_to(ROOT)))


def check_closeout_runner(checks: list[Check]) -> None:
    if not FINAL_CLOSEOUT.exists():
        add(checks, "closeout_runner", "warn", "Guarded final closeout runner is missing.", str(FINAL_CLOSEOUT.relative_to(ROOT)))
        return

    closeout_text = read_text(FINAL_CLOSEOUT)
    required_markers = {
        "build_latex_submission_package.py": "rebuilds the LaTeX package",
        "qa_submission_package.py": "runs submission QA",
        "audit_manuscript_data_consistency.py": "runs manuscript-data consistency audit",
        "validate_figure5_finalsize_candidate.py": "validates Figure 5 candidate source mapping and final-size output",
        "write_final_gate_status.py": "refreshes final gate status",
        "final_submission_preflight.py": "writes the actionable final-submission preflight report",
        "write_final_gap_report.py": "writes the final submission gap report",
        "export_overleaf_package.py": "exports the guarded Overleaf archive",
        "--keep-logs": "keeps LaTeX compile logs for QA",
        "--allow-warnings": "labels warning-bearing archives as DRAFT",
        "if warn_count and not args.allow_warnings": "refuses FINAL export while warnings remain",
        "if final_warn_count and not args.allow_warnings": "refuses FINAL closeout when post-export warnings remain",
        "Post-export QA": "reports post-export QA warnings/failures",
        "final_counts": "reports final QA counts after export",
    }
    missing = [description for marker, description in required_markers.items() if marker not in closeout_text]

    export_pos = closeout_text.find("run(export_cmd")
    post_export_qa_pos = closeout_text.find('"qa_submission_package.py")], env=env)', export_pos)
    post_export_gate_pos = closeout_text.find('"write_final_gate_status.py")], env=env)', export_pos)
    post_export_preflight_pos = closeout_text.find('"final_submission_preflight.py")], env=env)', export_pos)
    if export_pos < 0:
        missing.append("calls the exporter command")
    if export_pos >= 0 and post_export_qa_pos < 0:
        missing.append("reruns QA after archive export")
    if export_pos >= 0 and post_export_gate_pos < 0:
        missing.append("refreshes final gate status after archive export")
    if export_pos >= 0 and post_export_preflight_pos < 0:
        missing.append("writes final preflight after archive export")

    if missing:
        add(
            checks,
            "closeout_runner",
            "warn",
            "Guarded final closeout runner exists but is missing expected safeguards.",
            "; ".join(missing),
        )
    else:
        add(
            checks,
            "closeout_runner",
            "pass",
            "Guarded final closeout runner preserves compile logs, reruns post-export QA, refreshes gates and preflight, and refuses FINAL while warnings remain.",
            str(FINAL_CLOSEOUT.relative_to(ROOT)),
        )


def check_final_input_applier(checks: list[Check]) -> None:
    if not FINAL_INPUTS_APPLIER.exists():
        add(
            checks,
            "final_input_applier",
            "warn",
            "Integrated final-input applier is missing.",
            str(FINAL_INPUTS_APPLIER.relative_to(ROOT)),
        )
        return

    applier_text = read_text(FINAL_INPUTS_APPLIER)
    required_markers = {
        '"--write"': "defines an explicit write switch",
        'action="store_true"': "uses a boolean write switch",
        "apply_submission_metadata.py": "calls the metadata gatekeeper",
        "record_persist_panel_selection.py": "calls the panel-selection gatekeeper",
        "replace_approved_figure5.py": "runs the guarded Figure 5 replacement after panel handling",
        "qa_submission_package.py": "refreshes QA after input handling",
        "write_final_gate_status.py": "refreshes final gate status after input handling",
        "final_submission_preflight.py": "refreshes preflight after input handling",
        "metadata_cmd.append(\"--write\")": "writes metadata only when --write is supplied",
        "panel_cmd.append(\"--write\")": "writes panel selection only when --write is supplied",
        "--approved-by": "requires an explicit panel approver",
        "Dry run only. No final metadata or panel-selection files were written.": "documents dry-run non-write behavior",
        "PYTHONUTF8": "sets UTF-8 mode for subprocesses",
        "PYTHONIOENCODING": "sets UTF-8 IO encoding for subprocesses",
    }
    missing = [description for marker, description in required_markers.items() if marker not in applier_text]
    if 'parser.add_argument("--approved-by", required=True' not in applier_text:
        missing.append("requires --approved-by at argument-parse time")
    if "if args.write:" not in applier_text:
        missing.append("guards final writes behind args.write")
    if "replacement_cmd.append(\"--write\")" not in applier_text:
        missing.append("writes Figure 5 replacement only when --write is supplied")

    if missing:
        add(
            checks,
            "final_input_applier",
            "warn",
            "Integrated final-input applier exists but is missing expected safeguards.",
            "; ".join(missing),
        )
    else:
        add(
            checks,
            "final_input_applier",
            "pass",
            "Integrated final-input applier is dry-run by default, delegates to gatekeepers, refreshes QA/gate/preflight, and writes only with --write.",
            str(FINAL_INPUTS_APPLIER.relative_to(ROOT)),
        )


def check_overleaf_export(checks: list[Check]) -> None:
    exporter = ROOT / "scripts" / "export_overleaf_package.py"
    if exporter.exists():
        add(checks, "overleaf_export", "pass", "Guarded Overleaf exporter script exists.", str(exporter.relative_to(ROOT)))
    else:
        add(checks, "overleaf_export", "warn", "Guarded Overleaf exporter script is missing.", str(exporter.relative_to(ROOT)))
        return

    archives = sorted(EXPORTS.glob("nsfg_reproductive_lifecourse_ssl_latex_package_*.zip"), key=lambda p: p.stat().st_mtime)
    if not archives:
        add(checks, "overleaf_export", "warn", "No guarded Overleaf archive has been exported yet.", str(EXPORTS.relative_to(ROOT)))
        return
    archive = archives[-1]
    newest_source_mtime = max((LATEX / "main.tex").stat().st_mtime, (LATEX / "main.pdf").stat().st_mtime)
    if archive.stat().st_mtime + 1 < newest_source_mtime and "_FINAL_" in archive.name:
        add(checks, "overleaf_export", "warn", "Latest FINAL Overleaf archive is older than current LaTeX source/PDF.", f"{archive.name} should be regenerated")
    archive_manifest: dict | None = None
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if "OVERLEAF_ARCHIVE_MANIFEST.json" in names:
            archive_manifest = json.loads(zf.read("OVERLEAF_ARCHIVE_MANIFEST.json").decode("utf-8"))
    problems: list[str] = []
    if "main.tex" not in names:
        problems.append("missing main.tex")
    if "main.pdf" not in names:
        problems.append("missing main.pdf")
    if "OVERLEAF_ARCHIVE_MANIFEST.json" not in names:
        problems.append("missing OVERLEAF_ARCHIVE_MANIFEST.json")
    if any(name.startswith("build/") for name in names):
        problems.append("contains build/ artifacts")
    if any(name.lower().endswith(".zip") for name in names):
        problems.append("contains nested zip")
    if any(name.startswith("data/") or "/data/raw/" in name for name in names):
        problems.append("contains raw-data path")
    if problems:
        add(checks, "overleaf_export", "fail", "Latest Overleaf archive failed structure checks.", f"{archive.name}: {'; '.join(problems)}")
    else:
        add(checks, "overleaf_export", "pass", "Latest Overleaf archive structure is valid for a guarded package.", f"{archive.name}; {len(names)} members")

    if archive_manifest is not None:
        current_counts = scoped_status_counts(checks, excluded_area="overleaf_export")
        manifest_counts = archive_manifest.get("qa_counts", {})
        fail_warn_match = (
            int(manifest_counts.get("fail", -1)) == int(current_counts.get("fail", -2))
            and int(manifest_counts.get("warn", -1)) == int(current_counts.get("warn", -2))
        )
        current_warnings = [
            {
                "area": check.area,
                "detail": check.detail,
                "evidence": check.evidence,
            }
            for check in checks
            if check.status == "warn" and check.area != "overleaf_export"
        ]
        manifest_warnings = [
            {
                "area": check.get("area", ""),
                "detail": check.get("detail", ""),
                "evidence": check.get("evidence", ""),
            }
            for check in archive_manifest.get("warnings", [])
            if check.get("area") != "overleaf_export"
        ]
        if fail_warn_match and manifest_warnings == current_warnings:
            add(checks, "overleaf_export", "pass", "Latest archive manifest is synchronized with current warning gates.", archive.name)
        else:
            add(
                checks,
                "overleaf_export",
                "warn",
                "Latest archive manifest is stale relative to current warning gates.",
                f"{archive.name}: manifest_counts={manifest_counts}; current_non_overleaf_counts={current_counts}",
            )


def status_rank(status: str) -> int:
    return {"pass": 0, "warn": 1, "fail": 2}.get(status, 3)


def write_reports(checks: list[Check]) -> None:
    ANALYSIS_REVIEW.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    json_path = ANALYSIS_REVIEW / "submission_package_qa_20260604.json"
    md_path = ANALYSIS_REVIEW / "submission_package_qa_20260604.md"
    summary = {
        "generated_at": timestamp,
        "project": ROOT.name,
        "counts": {
            "pass": sum(1 for c in checks if c.status == "pass"),
            "warn": sum(1 for c in checks if c.status == "warn"),
            "fail": sum(1 for c in checks if c.status == "fail"),
        },
        "checks": [asdict(c) for c in checks],
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Submission Package QA",
        "",
        f"Generated: {timestamp}",
        "",
        "## Summary",
        "",
        f"- Pass: {summary['counts']['pass']}",
        f"- Warn: {summary['counts']['warn']}",
        f"- Fail: {summary['counts']['fail']}",
        "",
        "## Checks",
        "",
        "| Area | Status | Detail | Evidence |",
        "|---|---|---|---|",
    ]
    for check in sorted(checks, key=lambda c: (status_rank(c.status), c.area, c.detail)):
        lines.append(
            "| "
            + " | ".join(
                part.replace("|", "/").replace("\n", " ")
                for part in [check.area, check.status.upper(), check.detail, check.evidence]
            )
            + " |"
        )
    lines.append("")
    if summary["counts"]["fail"]:
        lines.append("Verdict: FAIL. Fix failed checks before submission.")
    elif summary["counts"]["warn"]:
        lines.append("Verdict: NOT FINAL. No hard package failure, but warning gates remain.")
    else:
        lines.append("Verdict: PASS for current QA scope.")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    checks: list[Check] = []
    check_required_files(checks)
    check_latex_compile_log(checks)
    check_manifest(checks)
    check_source_data_hashes(checks)
    check_manuscript_data_consistency(checks)
    check_main_text(checks)
    check_endpoint_tables(checks)
    check_figure_gates(checks)
    check_figure5_candidate_validation(checks)
    check_figure5_replacement_runner(checks)
    check_final_handoff(checks)
    check_closeout_runner(checks)
    check_final_input_applier(checks)
    check_overleaf_export(checks)
    write_reports(checks)


if __name__ == "__main__":
    main()
