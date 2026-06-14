"""Write the current final-submission gap report for the NSFG SSL manuscript."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_REVIEW = ROOT / "analysis_review"
QA_JSON = ANALYSIS_REVIEW / "submission_package_qa_20260604.json"
PREFLIGHT_JSON = ANALYSIS_REVIEW / "final_submission_preflight_20260604.json"
CONSISTENCY_JSON = ANALYSIS_REVIEW / "manuscript_data_consistency_audit_20260604.json"
FIGURE5_VALIDATION_JSON = ANALYSIS_REVIEW / "figure5_finalsize_candidate_validation_20260604.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    qa = read_json(QA_JSON)
    preflight = read_json(PREFLIGHT_JSON)
    consistency = read_json(CONSISTENCY_JSON)
    figure5_validation = read_json(FIGURE5_VALIDATION_JSON) if FIGURE5_VALIDATION_JSON.exists() else {}

    figure5a = ROOT / "figure_redraw" / "preapproval_fig5a_ci_candidate_20260604" / "outputs" / "F5-A" / "F5-A__F5-A1__portable_forest_plot.png"
    figure5b = ROOT / "figure_redraw" / "preapproval_fig5b_risk_enrichment_candidate_20260604" / "outputs" / "F5-B" / "F5-B__F5-B1__risk_enrichment_dashboard.png"
    figure5_preview = ROOT / "figure_redraw" / "preapproval_figure5_ab_preview_20260604" / "outputs" / "figure5_AB_preapproval_preview.png"
    figure5_finalsize = ROOT / "figure_redraw" / "preapproval_figure5_finalsize_candidate_20260604" / "outputs" / "figure5_finalsize_preapproval_candidate.png"
    figure5_replacer = ROOT / "scripts" / "replace_approved_figure5.py"

    pending_items = [
        {
            "item": gate.get("gate", ""),
            "status": gate.get("status", ""),
            "why_it_matters": "This gate must close before the archive can be treated as final.",
            "evidence": gate.get("evidence", ""),
            "next_action": gate.get("required_action", ""),
        }
        for gate in preflight.get("open_gates", [])
    ]

    reviewer_risks = [
        {
            "risk": "within-NSFG temporal validation only",
            "severity": "manageable",
            "mitigation": "Manuscript states temporal validation rather than external registry validation and lists this as a limitation.",
        },
        {
            "risk": "small high-burden P2 phenotype",
            "severity": "moderate",
            "mitigation": "Cluster size caveat and bootstrap intervals are included; claims are limited to survey-level enrichment.",
        },
        {
            "risk": "indirect endpoint leakage",
            "severity": "manageable",
            "mitigation": "Direct endpoint-defining variables are excluded; indirect leakage is acknowledged as a limitation.",
        },
    ]

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": ROOT.name,
        "qa_counts": qa.get("counts", {}),
        "consistency_counts": consistency.get("counts", {}),
        "figure5_validation_counts": figure5_validation.get("counts", {}),
        "final_ready": preflight.get("final_ready", False),
        "latest_archive": preflight.get("latest_archive", ""),
        "latest_archive_status": preflight.get("latest_archive_status", ""),
        "pending_items": pending_items,
        "reviewer_risks": reviewer_risks,
        "candidate_assets": {
            "figure5a_png": rel(figure5a),
            "figure5b_png": rel(figure5b),
            "figure5_ab_preview_png": rel(figure5_preview),
            "figure5_finalsize_png": rel(figure5_finalsize),
            "figure5_finalsize_validation": rel(FIGURE5_VALIDATION_JSON) if FIGURE5_VALIDATION_JSON.exists() else "",
            "figure5_replacer": rel(figure5_replacer) if figure5_replacer.exists() else "",
        },
        "recommended_panel_approval_reply": preflight.get("recommended_panel_approval_reply", "同意推荐组合"),
    }

    json_path = ANALYSIS_REVIEW / "final_gap_report_20260604.json"
    md_path = ANALYSIS_REVIEW / "final_gap_report_20260604.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Final Submission Gap Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"QA: {report['qa_counts'].get('pass', 0)} pass, {report['qa_counts'].get('warn', 0)} warn, {report['qa_counts'].get('fail', 0)} fail.",
        f"Consistency audit: {report['consistency_counts'].get('pass', 0)} pass, {report['consistency_counts'].get('warn', 0)} warn, {report['consistency_counts'].get('fail', 0)} fail.",
        f"Figure 5 final-size validation: {report['figure5_validation_counts'].get('pass', 0)} pass, {report['figure5_validation_counts'].get('warn', 0)} warn, {report['figure5_validation_counts'].get('fail', 0)} fail.",
        f"Final ready: `{report['final_ready']}`.",
        f"Latest archive: `{report['latest_archive']}` ({report['latest_archive_status']}).",
        "",
        "## Pending Items",
        "",
    ]
    if pending_items:
        lines += [
            "| Item | Status | Why it matters | Evidence | Next action |",
            "|---|---|---|---|---|",
        ]
        for row in pending_items:
            lines.append(
                f"| {row['item']} | {row['status']} | {row['why_it_matters']} | {row['evidence']} | {row['next_action']} |"
            )
    else:
        lines.append("No open final-submission gates remain.")
    lines += [
        "",
        "## Reviewer Risks Still Worth Disclosing",
        "",
        "| Risk | Severity | Mitigation |",
        "|---|---|---|",
    ]
    for row in reviewer_risks:
        lines.append(f"| {row['risk']} | {row['severity']} | {row['mitigation']} |")
    lines += [
        "",
        "## Figure 5 Approval Assets",
        "",
        f"- Figure 5A candidate: `{report['candidate_assets']['figure5a_png']}`",
        f"- Figure 5B candidate: `{report['candidate_assets']['figure5b_png']}`",
        f"- A+B preview: `{report['candidate_assets']['figure5_ab_preview_png']}`",
        f"- Final-size A+B candidate: `{report['candidate_assets']['figure5_finalsize_png']}`",
        f"- Final-size validation report: `{report['candidate_assets']['figure5_finalsize_validation']}`",
        f"- Guarded replacement script: `{report['candidate_assets']['figure5_replacer']}`",
        "",
        f"Recommended panel approval reply: `{report['recommended_panel_approval_reply']}`",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
