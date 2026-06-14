"""Write a machine-readable final submission gate status report.

This report is a compact handoff artifact. It answers one question: can the
current project state be exported as a final submission package, and if not,
which concrete gates remain open?
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from validate_submission_metadata import validate as validate_submission_metadata
from validate_panel_selection import validate as validate_panel_selection


ROOT = Path(__file__).resolve().parents[1]
QA_JSON = ROOT / "analysis_review" / "submission_package_qa_20260604.json"
OUT_JSON = ROOT / "analysis_review" / "final_gate_status_20260604.json"
OUT_MD = ROOT / "analysis_review" / "final_gate_status_20260604.md"
EXPORTS = ROOT / "manuscript" / "exports"


def read_qa() -> dict:
    if not QA_JSON.exists():
        return {"counts": {"pass": 0, "warn": 0, "fail": 1}, "checks": []}
    return json.loads(QA_JSON.read_text(encoding="utf-8"))


def latest_archive() -> Path | None:
    archives = sorted(EXPORTS.glob("nsfg_reproductive_lifecourse_ssl_latex_package_*.zip"), key=lambda p: p.stat().st_mtime)
    return archives[-1] if archives else None


def build_status() -> dict:
    qa = read_qa()
    metadata = validate_submission_metadata()
    panel_selection = validate_panel_selection()
    archive = latest_archive()
    gates = []

    gates.append(
        {
            "gate": "qa_failures",
            "status": "closed" if int(qa.get("counts", {}).get("fail", 0)) == 0 else "open",
            "evidence": f"fail={qa.get('counts', {}).get('fail', 0)}",
            "required_action": "Fix failed QA checks." if int(qa.get("counts", {}).get("fail", 0)) else "",
        }
    )
    gates.append(
        {
            "gate": "submission_metadata",
            "status": "closed" if metadata.get("valid") else "open",
            "evidence": "; ".join(metadata.get("issues", [])) or "config/submission_metadata.json validates",
            "required_action": "Create and validate config/submission_metadata.json." if not metadata.get("valid") else "",
        }
    )
    gates.append(
        {
            "gate": "persist_panel_selection",
            "status": "closed" if panel_selection.get("valid") else "open",
            "evidence": "; ".join(panel_selection.get("issues", [])) or "panel selection validates",
            "required_action": "Record explicit user-approved PERSIST/PRISM panel choices." if not panel_selection.get("valid") else "",
        }
    )
    gates.append(
        {
            "gate": "latest_archive",
            "status": "draft" if archive and "_DRAFT_" in archive.name else ("final" if archive and "_FINAL_" in archive.name else "missing"),
            "evidence": archive.name if archive else "No Overleaf archive found",
            "required_action": "Run scripts/final_closeout.py after all gates close." if not (archive and "_FINAL_" in archive.name) else "",
        }
    )

    open_gates = [gate for gate in gates if gate["status"] in {"open", "missing", "draft"}]
    final_ready = (
        int(qa.get("counts", {}).get("fail", 0)) == 0
        and int(qa.get("counts", {}).get("warn", 0)) == 0
        and metadata.get("valid")
        and panel_selection.get("valid")
        and archive is not None
        and "_FINAL_" in archive.name
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": ROOT.name,
        "final_ready": final_ready,
        "qa_counts": qa.get("counts", {}),
        "gates": gates,
        "open_gate_count": len(open_gates),
        "open_gates": open_gates,
    }


def write_markdown(status: dict) -> None:
    lines = [
        "# Final Gate Status",
        "",
        f"Generated: {status['generated_at']}",
        "",
        f"Final ready: `{status['final_ready']}`",
        "",
        f"QA counts: `{status['qa_counts']}`",
        "",
        "| Gate | Status | Evidence | Required action |",
        "|---|---|---|---|",
    ]
    for gate in status["gates"]:
        lines.append(
            "| "
            + " | ".join(
                str(gate.get(key, "")).replace("|", "/").replace("\n", " ")
                for key in ["gate", "status", "evidence", "required_action"]
            )
            + " |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    status = build_status()
    OUT_JSON.write_text(json.dumps(status, indent=2), encoding="utf-8")
    write_markdown(status)
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
