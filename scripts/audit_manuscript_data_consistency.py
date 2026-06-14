"""Audit manuscript text against current NSFG analysis artifacts.

This script checks high-risk consistency points that are easy to miss during
late manuscript and figure revisions: cohort counts, encoder dimensions,
cluster metrics, endpoint enrichment intervals, and Figure 5 interval-display
readiness. It is intentionally read-only.
"""

from __future__ import annotations

import csv
import gzip
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_TABLES = ROOT / "results" / "tables"
PROCESSED = ROOT / "data" / "processed"
MANUSCRIPT = ROOT / "manuscript"
LATEX = MANUSCRIPT / "latex"
ANALYSIS_REVIEW = ROOT / "analysis_review"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def count_gzip_csv_prefixed_columns(path: Path, prefix: str) -> int:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    return sum(col.startswith(prefix) for col in header)


def fnum(value: object, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}"


def pr_ci_sentence(row: dict[str, str]) -> str:
    return (
        f"{fnum(row['prevalence_ratio'], 2)}; "
        f"95\\% CI {fnum(row['prevalence_ratio_ci_low'], 2)}--{fnum(row['prevalence_ratio_ci_high'], 2)}"
    )


def table4_pr_ci(row: dict[str, str]) -> str:
    return (
        f"{fnum(row['top_prevalence_ratio'], 2)} "
        f"({fnum(row['prevalence_ratio_ci_low'], 2)}--{fnum(row['prevalence_ratio_ci_high'], 2)})"
    )


def check(checks: list[dict], area: str, status: str, detail: str, evidence: str) -> None:
    checks.append(
        {
            "area": area,
            "status": status,
            "detail": detail,
            "evidence": evidence,
        }
    )


def status_counts(checks: list[dict]) -> dict[str, int]:
    return {
        "pass": sum(row["status"] == "pass" for row in checks),
        "warn": sum(row["status"] == "warn" for row in checks),
        "fail": sum(row["status"] == "fail" for row in checks),
    }


def main() -> None:
    main_tex = (LATEX / "main.tex").read_text(encoding="utf-8")
    table4_tex = (LATEX / "tables" / "table4.tex").read_text(encoding="utf-8")
    draft_md = (MANUSCRIPT / "main_draft.md").read_text(encoding="utf-8")
    table1 = read_csv(MANUSCRIPT / "tables" / "table1_cohort_characteristics.csv")
    table4 = read_csv(MANUSCRIPT / "tables" / "table4_endpoint_enrichment_model_metrics.csv")
    matrix_summary = read_csv(RESULT_TABLES / "harmonized_matrix_summary.csv")
    feature_audit = read_csv(RESULT_TABLES / "ssl_feature_audit.csv")
    cluster = read_csv(RESULT_TABLES / "cluster_selection_metrics.csv")
    enrichment = read_csv(RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    analysis_summary = read_json(RESULT_TABLES / "analysis_summary.json")
    ssl_config = read_json(RESULT_TABLES / "ssl_config.json")

    checks: list[dict] = []

    n_total = sum(int(float(row["n_respondents"])) for row in table1)
    n_train = int(float(next(row for row in table1 if row["analysis_split"] == "Training/pretraining")["n_respondents"]))
    n_dev = int(float(next(row for row in table1 if row["analysis_split"] == "Development/model selection")["n_respondents"]))
    n_test = int(float(next(row for row in table1 if row["analysis_split"] == "Temporal validation")["n_respondents"]))
    n_matrix_features = int(float(matrix_summary[0]["features"]))
    n_encoder_features = sum(
        row.get("used_in_primary_encoder", "").strip().lower() == "true" for row in feature_audit
    )
    embedding_dim_actual = count_gzip_csv_prefixed_columns(PROCESSED / "ssl_embeddings.csv.gz", "ssl_")

    expected_counts = [
        f"{n_total:,} respondents",
        f"{n_matrix_features} cross-cycle columns",
        f"{n_train:,}, {n_dev:,}, and {n_test:,} respondents",
    ]
    missing_counts = [text for text in expected_counts if text not in main_tex]
    check(
        checks,
        "cohort_counts",
        "fail" if missing_counts else "pass",
        "Manuscript cohort and matrix counts match source tables.",
        "missing: " + "; ".join(missing_counts) if missing_counts else "; ".join(expected_counts),
    )

    config_embedding_dim = int(ssl_config["embedding_dim"])
    summary_embedding_dim = int(analysis_summary["embedding_dim"])
    summary_features = int(analysis_summary["n_features_used"])
    encoder_phrase = (
        f"primary encoder used {n_encoder_features} endpoint-excluded features "
        f"and generated {embedding_dim_actual}-dimensional respondent embeddings"
    )
    dim_status = "pass"
    dim_notes = []
    if summary_features != n_encoder_features:
        dim_status = "fail"
        dim_notes.append(f"analysis_summary n_features_used={summary_features}, audit={n_encoder_features}")
    if summary_embedding_dim != embedding_dim_actual:
        dim_status = "fail"
        dim_notes.append(f"analysis_summary embedding_dim={summary_embedding_dim}, actual={embedding_dim_actual}")
    if config_embedding_dim != embedding_dim_actual:
        dim_status = "fail"
        dim_notes.append(f"ssl_config embedding_dim={config_embedding_dim}, actual={embedding_dim_actual}")
    if encoder_phrase not in main_tex:
        dim_status = "fail"
        dim_notes.append("main.tex missing encoder phrase")
    check(
        checks,
        "encoder_artifacts",
        dim_status,
        "Encoder feature count and embedding dimension are internally consistent.",
        "; ".join(dim_notes) if dim_notes else encoder_phrase,
    )

    selected = next(row for row in cluster if row["selected"].lower() == "true")
    cluster_expected = [
        f"silhouette {float(selected['silhouette']):.3f}",
        f"Davies--Bouldin {float(selected['davies_bouldin']):.3f}",
        f"bootstrap adjusted Rand index {float(selected['bootstrap_ari_mean']):.3f}",
        f"{float(selected['min_cluster_prop']) * 100:.1f}\\% of respondents",
    ]
    missing_cluster = [text for text in cluster_expected if text not in main_tex]
    check(
        checks,
        "cluster_metrics",
        "fail" if missing_cluster else "pass",
        "Selected-k metrics in manuscript match cluster_selection_metrics.csv.",
        "missing: " + "; ".join(missing_cluster) if missing_cluster else "; ".join(cluster_expected),
    )

    missing_ci: list[str] = []
    for row in table4:
        endpoint = row["endpoint"]
        expected = table4_pr_ci(row)
        if expected not in table4_tex:
            missing_ci.append(f"{endpoint}: {expected}")
    for row in table4:
        if row["endpoint"] not in {
            "adverse_pregnancy_history_proxy",
            "unintended_mistimed_pregnancy_history",
        }:
            continue
        point = f"{fnum(row['top_prevalence_ratio'], 2)}"
        interval = f"95\\% CI {fnum(row['prevalence_ratio_ci_low'], 2)}--{fnum(row['prevalence_ratio_ci_high'], 2)}"
        if point not in main_tex or interval not in main_tex:
            missing_ci.append(f"main text: PR {point}; {interval}")
    check(
        checks,
        "endpoint_intervals",
        "fail" if missing_ci else "pass",
        "Endpoint PR and bootstrap CI strings in manuscript match Table 4 row-level source data.",
        "missing: " + "; ".join(missing_ci) if missing_ci else f"{len(table4)} endpoint intervals checked",
    )

    old_figure5 = LATEX / "figures" / "figure5_risk_enrichment.png"
    endpoint_source = RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv"
    fig5a_candidate = (
        ROOT
        / "figure_redraw"
        / "preapproval_fig5a_ci_candidate_20260604"
        / "outputs"
        / "F5-A"
        / "F5-A__F5-A1__portable_forest_plot.png"
    )
    if old_figure5.exists() and old_figure5.stat().st_mtime < endpoint_source.stat().st_mtime:
        status = "warn"
        detail = "Current manuscript Figure 5 asset predates bootstrap-CI source data."
    else:
        status = "pass"
        detail = "Current manuscript Figure 5 asset is not older than endpoint-CI source data."
    evidence = (
        f"figure5={datetime.fromtimestamp(old_figure5.stat().st_mtime).isoformat(timespec='seconds')}; "
        f"endpoint_table={datetime.fromtimestamp(endpoint_source.stat().st_mtime).isoformat(timespec='seconds')}; "
        f"candidate_exists={fig5a_candidate.exists()}"
    )
    check(checks, "figure5_asset", status, detail, evidence)

    stale_hits = []
    for phrase in ["32-dimensional", "silhouette 0.573", "minimum cluster proportion 13.0%"]:
        if phrase in draft_md:
            stale_hits.append(phrase)
    if "Superseded draft note" not in draft_md:
        stale_hits.append("missing superseded draft note")
    check(
        checks,
        "superseded_draft",
        "fail" if stale_hits else "pass",
        "Superseded Markdown draft is clearly marked and no longer carries stale core metrics.",
        "stale hits: " + "; ".join(stale_hits) if stale_hits else "main_draft.md marked superseded",
    )

    generated_at = datetime.now().isoformat(timespec="seconds")
    counts = status_counts(checks)
    report = {
        "generated_at": generated_at,
        "project": ROOT.name,
        "counts": counts,
        "checks": checks,
    }
    ANALYSIS_REVIEW.mkdir(parents=True, exist_ok=True)
    json_path = ANALYSIS_REVIEW / "manuscript_data_consistency_audit_20260604.json"
    md_path = ANALYSIS_REVIEW / "manuscript_data_consistency_audit_20260604.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Manuscript Data Consistency Audit",
        "",
        f"Generated: {generated_at}",
        "",
        f"Counts: {counts['pass']} pass, {counts['warn']} warn, {counts['fail']} fail.",
        "",
        "| Area | Status | Detail | Evidence |",
        "|---|---|---|---|",
    ]
    for row in checks:
        evidence_md = row["evidence"].replace("|", "\\|")
        detail_md = row["detail"].replace("|", "\\|")
        lines.append(f"| {row['area']} | {row['status'].upper()} | {detail_md} | {evidence_md} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
