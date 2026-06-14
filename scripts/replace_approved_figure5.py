"""Replace manuscript Figure 5 with the validated final-size candidate.

This script is guarded by two conditions:

1. the final PERSIST/PRISM panel selection must validate; and
2. Figure 5 panels must be approved as F5-A1 and F5-B1, the options used by the
   validated final-size candidate.

By default it performs a dry run and writes only a replacement-status report.
Use ``--write`` only after explicit user panel approval has been recorded.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from validate_panel_selection import validate as validate_panel_selection


ROOT = Path(__file__).resolve().parents[1]
STAGE1 = ROOT / "figure_redraw" / "panel_stage1_selection_20260602"
FINAL_TSV = STAGE1 / "panel_final_selection.tsv"
VALIDATION_JSON = ROOT / "analysis_review" / "figure5_finalsize_candidate_validation_20260604.json"
CANDIDATE_OUTPUTS = ROOT / "figure_redraw" / "preapproval_figure5_finalsize_candidate_20260604" / "outputs"
RESULT_FIGURES = ROOT / "results" / "figures"
LATEX_FIGURES = ROOT / "manuscript" / "latex" / "figures"
BACKUP_DIR = ROOT / "figure_redraw" / "preapproval_figure5_finalsize_candidate_20260604" / "replacement_backup"
REPORT_JSON = ROOT / "analysis_review" / "figure5_replacement_status_20260604.json"
REPORT_MD = ROOT / "analysis_review" / "figure5_replacement_status_20260604.md"


@dataclass
class ReplacementCheck:
    area: str
    status: str
    detail: str
    evidence: str


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def add(checks: list[ReplacementCheck], area: str, status: str, detail: str, evidence: str) -> None:
    checks.append(ReplacementCheck(area, status, detail, evidence))


def expected_sources() -> dict[str, Path]:
    return {
        "figure5_risk_enrichment.png": CANDIDATE_OUTPUTS / "figure5_finalsize_preapproval_candidate.png",
        "figure5_risk_enrichment.pdf": CANDIDATE_OUTPUTS / "figure5_finalsize_preapproval_candidate.pdf",
        "figure5_risk_enrichment.svg": CANDIDATE_OUTPUTS / "figure5_finalsize_preapproval_candidate.svg",
    }


def approved_figure5_options() -> dict[str, str]:
    if not FINAL_TSV.exists():
        return {}
    rows = read_tsv(FINAL_TSV)
    return {row.get("Panel", ""): row.get("Option", "") for row in rows if row.get("Panel", "") in {"F5-A", "F5-B"}}


def verify_prerequisites(checks: list[ReplacementCheck]) -> bool:
    ok = True
    panel_result = validate_panel_selection()
    if not panel_result.get("valid"):
        status = panel_result.get("status", "fail")
        add(
            checks,
            "panel_selection",
            "warn" if status == "warn" else "fail",
            "Final panel selection is not ready for Figure 5 replacement.",
            "; ".join(panel_result.get("issues", [])),
        )
        return False
    add(
        checks,
        "panel_selection",
        "pass",
        "Final panel selection validates.",
        f"{panel_result.get('selected_count')} panels selected",
    )

    selected = approved_figure5_options()
    expected = {"F5-A": "F5-A1", "F5-B": "F5-B1"}
    if selected != expected:
        ok = False
        add(
            checks,
            "figure5_options",
            "fail",
            "Approved Figure 5 options do not match this final-size candidate.",
            f"selected={selected}; expected={expected}",
        )
    else:
        add(
            checks,
            "figure5_options",
            "pass",
            "Approved Figure 5 options match the validated final-size candidate.",
            "F5-A1 and F5-B1",
        )

    if not VALIDATION_JSON.exists():
        ok = False
        add(
            checks,
            "candidate_validation",
            "fail",
            "Figure 5 final-size validation report is missing.",
            str(VALIDATION_JSON.relative_to(ROOT)),
        )
    else:
        validation = read_json(VALIDATION_JSON)
        counts = validation.get("counts", {})
        if int(counts.get("fail", 0)) or int(counts.get("warn", 0)):
            ok = False
            add(
                checks,
                "candidate_validation",
                "fail",
                "Figure 5 final-size validation report is not clean.",
                repr(counts),
            )
        else:
            add(
                checks,
                "candidate_validation",
                "pass",
                "Figure 5 final-size validation report is clean.",
                f"{counts.get('pass', 0)} pass; 0 warn; 0 fail",
            )

    missing_sources = [
        str(source.relative_to(ROOT))
        for source in expected_sources().values()
        if not source.exists()
    ]
    if missing_sources:
        ok = False
        add(checks, "candidate_outputs", "fail", "Figure 5 candidate output files are missing.", "; ".join(missing_sources))
    else:
        add(checks, "candidate_outputs", "pass", "Figure 5 candidate PNG/PDF/SVG outputs exist.", "3 files")

    return ok


def copy_with_backup() -> list[str]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_FIGURES.mkdir(parents=True, exist_ok=True)
    LATEX_FIGURES.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for target_name, source in expected_sources().items():
        for target_dir in [RESULT_FIGURES, LATEX_FIGURES]:
            target = target_dir / target_name
            if target.exists():
                backup = BACKUP_DIR / f"{target.stem}_{target_dir.name}_{timestamp}{target.suffix}"
                shutil.copy2(target, backup)
            shutil.copy2(source, target)
            copied.append(str(target.relative_to(ROOT)))
    return copied


def write_report(mode: str, checks: list[ReplacementCheck], copied: list[str]) -> dict:
    counts = {
        "pass": sum(1 for check in checks if check.status == "pass"),
        "warn": sum(1 for check in checks if check.status == "warn"),
        "fail": sum(1 for check in checks if check.status == "fail"),
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": ROOT.name,
        "mode": mode,
        "status": "replaced" if copied else "not_replaced",
        "counts": counts,
        "copied": copied,
        "checks": [asdict(check) for check in checks],
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Figure 5 Replacement Status",
        "",
        f"Generated: {report['generated_at']}",
        f"Mode: `{mode}`",
        f"Status: `{report['status']}`",
        "",
        "## Checks",
        "",
        "| Area | Status | Detail | Evidence |",
        "|---|---|---|---|",
    ]
    for check in checks:
        lines.append(
            "| "
            + " | ".join(
                value.replace("|", "/").replace("\n", " ")
                for value in [check.area, check.status.upper(), check.detail, check.evidence]
            )
            + " |"
        )
    if copied:
        lines += ["", "## Copied Files", ""]
        lines.extend(f"- `{path}`" for path in copied)
    lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Replace results/figures and manuscript/latex/figures Figure 5 assets after approval.",
    )
    args = parser.parse_args()

    checks: list[ReplacementCheck] = []
    ready = verify_prerequisites(checks)
    copied: list[str] = []
    if args.write:
        if not ready:
            report = write_report("write_failed", checks, copied)
            print(json.dumps(report, indent=2))
            raise SystemExit(1)
        copied = copy_with_backup()
        add(
            checks,
            "replacement",
            "pass",
            "Figure 5 candidate assets replaced the manuscript Figure 5 outputs.",
            f"{len(copied)} files copied with backups",
        )
        report = write_report("write", checks, copied)
    else:
        add(
            checks,
            "replacement",
            "pass" if ready else "warn",
            "Dry run only; no Figure 5 assets were replaced.",
            "Use --write after approval gates are closed.",
        )
        report = write_report("dry_run", checks, copied)
    print(json.dumps(report, indent=2))
    if args.write and report["counts"]["fail"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
