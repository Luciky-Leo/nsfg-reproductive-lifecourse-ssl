"""Write an actionable final-submission preflight report.

The QA report says whether the package is internally consistent. The final gate
report says which gates remain open. This helper translates those machine
reports into the exact next commands needed to move from DRAFT to FINAL without
changing any gate state by itself.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_REVIEW = ROOT / "analysis_review"
QA_JSON = ANALYSIS_REVIEW / "submission_package_qa_20260604.json"
GATE_JSON = ANALYSIS_REVIEW / "final_gate_status_20260604.json"
OUT_JSON = ANALYSIS_REVIEW / "final_submission_preflight_20260604.json"
OUT_MD = ANALYSIS_REVIEW / "final_submission_preflight_20260604.md"


RECOMMENDED_PANEL_APPROVAL = "同意推荐组合"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_archive() -> Path | None:
    exports = ROOT / "manuscript" / "exports"
    archives = sorted(
        exports.glob("nsfg_reproductive_lifecourse_ssl_latex_package_*.zip"),
        key=lambda p: p.stat().st_mtime,
    )
    return archives[-1] if archives else None


def metadata_command() -> str:
    return (
        'python scripts\\apply_submission_metadata.py '
        '--corresponding-name "<FINAL CORRESPONDING AUTHOR>" '
        '--corresponding-email "<FINAL EMAIL>" '
        '--affiliation "<FINAL DEPARTMENT, INSTITUTION, CITY, COUNTRY>" '
        "--write"
    )


def panel_command() -> str:
    return (
        'python scripts\\record_persist_panel_selection.py '
        f'--options "{RECOMMENDED_PANEL_APPROVAL}" '
        '--write --approved-by "<APPROVER NAME>"'
    )


def figure5_replacement_command() -> str:
    return "python scripts\\replace_approved_figure5.py --write"


def integrated_input_command() -> str:
    return (
        'python scripts\\apply_final_submission_inputs.py '
        '--corresponding-name "<FINAL CORRESPONDING AUTHOR>" '
        '--corresponding-email "<FINAL EMAIL>" '
        '--affiliation "<FINAL DEPARTMENT, INSTITUTION, CITY, COUNTRY>" '
        f'--panel-options "{RECOMMENDED_PANEL_APPROVAL}" '
        '--approved-by "<APPROVER NAME>" '
        "--write"
    )


def build_preflight() -> dict:
    qa = read_json(QA_JSON)
    gate = read_json(GATE_JSON)
    counts = qa.get("counts", {})
    open_gates = gate.get("open_gates", [])
    archive = latest_archive()

    actions: list[dict[str, str]] = []
    open_gate_names = {row.get("gate", "") for row in open_gates}
    if {"submission_metadata", "persist_panel_selection"} & open_gate_names:
        actions.append(
            {
                "gate": "final_user_inputs",
                "why": "Apply the final author metadata, explicit PERSIST/PRISM panel approval, and guarded Figure 5 replacement in one step.",
                "command": integrated_input_command(),
            }
        )
    if "submission_metadata" in open_gate_names:
        actions.append(
            {
                "gate": "submission_metadata",
                "why": "Fallback command if applying metadata separately.",
                "command": metadata_command(),
            }
        )
    if "persist_panel_selection" in open_gate_names:
        actions.append(
            {
                "gate": "persist_panel_selection",
                "why": "Fallback command if recording panel choices separately.",
                "command": panel_command(),
            }
        )
        actions.append(
            {
                "gate": "figure5_asset_replacement",
                "why": "Fallback command if metadata and panel choices are applied separately; this replaces Figure 5 only after panel selection and candidate validation gates pass.",
                "command": figure5_replacement_command(),
            }
        )
    if any(row.get("status") == "draft" for row in open_gates):
        actions.append(
            {
                "gate": "latest_archive",
                "why": "The current archive is deliberately labelled DRAFT while warning gates remain.",
                "command": "python scripts\\final_closeout.py",
            }
        )

    final_ready = bool(gate.get("final_ready"))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": ROOT.name,
        "qa_counts": counts,
        "final_ready": final_ready,
        "latest_archive": archive.name if archive else None,
        "latest_archive_status": "FINAL" if archive and "_FINAL_" in archive.name else ("DRAFT" if archive and "_DRAFT_" in archive.name else "missing"),
        "open_gates": open_gates,
        "next_actions": actions,
        "recommended_panel_approval_reply": RECOMMENDED_PANEL_APPROVAL,
    }


def write_markdown(preflight: dict) -> None:
    lines = [
        "# Final Submission Preflight",
        "",
        f"Generated: {preflight['generated_at']}",
        "",
        f"Final ready: `{preflight['final_ready']}`",
        f"QA counts: `{preflight['qa_counts']}`",
        f"Latest archive: `{preflight.get('latest_archive') or 'none'}`",
        f"Archive status: `{preflight['latest_archive_status']}`",
        "",
        "## Open Gates",
        "",
    ]
    if preflight["open_gates"]:
        lines.extend(["| Gate | Status | Evidence | Required action |", "|---|---|---|---|"])
        for row in preflight["open_gates"]:
            lines.append(
                "| "
                + " | ".join(
                    str(row.get(key, "")).replace("|", "/").replace("\n", " ")
                    for key in ["gate", "status", "evidence", "required_action"]
                )
                + " |"
            )
    else:
        lines.append("No open gates detected.")

    lines.extend(["", "## Next Commands", ""])
    if preflight["next_actions"]:
        for idx, action in enumerate(preflight["next_actions"], start=1):
            lines.extend(
                [
                    f"{idx}. `{action['gate']}`",
                    "",
                    action["why"],
                    "",
                    "```powershell",
                    action["command"],
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "All gates appear closed. Run final closeout:",
                "",
                "```powershell",
                "python scripts\\final_closeout.py",
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## User Approval Shortcut",
            "",
            f"Recommended panel approval reply: `{preflight['recommended_panel_approval_reply']}`",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    preflight = build_preflight()
    OUT_JSON.write_text(json.dumps(preflight, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(preflight)
    print(json.dumps(preflight, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
