"""Apply final user inputs for submission metadata and panel approval.

This is an orchestrator around the existing gatekeeper scripts. By default it
performs a dry run only. Use ``--write`` only after the corresponding author,
affiliation, and PERSIST/PRISM panel approval have been explicitly provided by
the user.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PREFLIGHT_MD = ROOT / "analysis_review" / "final_submission_preflight_20260604.md"
QA_JSON = ROOT / "analysis_review" / "submission_package_qa_20260604.json"


def run(cmd: list[str], env: dict[str, str]) -> None:
    print(f"+ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(ROOT), env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def read_qa_counts() -> dict:
    if not QA_JSON.exists():
        return {}
    return json.loads(QA_JSON.read_text(encoding="utf-8")).get("counts", {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corresponding-name", required=True, help="Final corresponding author name.")
    parser.add_argument("--corresponding-email", required=True, help="Final corresponding author email.")
    parser.add_argument(
        "--affiliation",
        required=True,
        help="Final affiliation string for affiliation id 1.",
    )
    parser.add_argument(
        "--panel-options",
        default="同意推荐组合",
        help="Panel option IDs or recommended-set alias. Default: 同意推荐组合.",
    )
    parser.add_argument("--approved-by", required=True, help="Name/label of the panel-choice approver.")
    parser.add_argument(
        "--approval-note",
        default="",
        help="Optional panel approval note copied into the final selection files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write metadata and panel final-selection files. Omit for dry run.",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    metadata_cmd = [
        sys.executable,
        str(SCRIPTS / "apply_submission_metadata.py"),
        "--corresponding-name",
        args.corresponding_name,
        "--corresponding-email",
        args.corresponding_email,
        "--affiliation",
        args.affiliation,
    ]
    panel_cmd = [
        sys.executable,
        str(SCRIPTS / "record_persist_panel_selection.py"),
        "--options",
        args.panel_options,
        "--approved-by",
        args.approved_by,
    ]
    if args.approval_note:
        panel_cmd.extend(["--approval-note", args.approval_note])
    if args.write:
        metadata_cmd.append("--write")
        panel_cmd.append("--write")

    run(metadata_cmd, env=env)
    run(panel_cmd, env=env)
    replacement_cmd = [sys.executable, str(SCRIPTS / "replace_approved_figure5.py")]
    if args.write:
        replacement_cmd.append("--write")
    run(replacement_cmd, env=env)
    run([sys.executable, str(SCRIPTS / "qa_submission_package.py")], env=env)
    run([sys.executable, str(SCRIPTS / "write_final_gate_status.py")], env=env)
    run([sys.executable, str(SCRIPTS / "final_submission_preflight.py")], env=env)

    result = {
        "mode": "write" if args.write else "dry_run",
        "qa_counts": read_qa_counts(),
        "preflight": str(PREFLIGHT_MD),
        "note": (
            "Inputs were written. Review refreshed QA/gate/preflight before final closeout."
            if args.write
            else "Dry run only. No final metadata or panel-selection files were written."
        ),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
