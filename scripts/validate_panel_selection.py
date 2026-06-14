"""Validate the recorded final PERSIST/PRISM panel selection.

This validator protects the final figure gate from false positives. A final
selection is valid only if every required panel has exactly one approved option,
the option exists in the Stage-1 candidate table, and approval metadata is
present in the TSV written by ``record_persist_panel_selection.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE1 = ROOT / "figure_redraw" / "panel_stage1_selection_20260602"
CANDIDATES = STAGE1 / "panel_template_candidates.tsv"
FINAL_TSV = STAGE1 / "panel_final_selection.tsv"
FINAL_MD = STAGE1 / "panel_final_selection.md"

REQUIRED_PANELS = [
    "F1-W",
    "F2-A",
    "F2-B",
    "F2-C",
    "F3-A",
    "F3-B",
    "F3-C",
    "F4-A",
    "F5-A",
    "F5-B",
    "FS1-A",
    "FS1-B",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def validate() -> dict:
    issues: list[str] = []
    warnings: list[str] = []

    if not CANDIDATES.exists():
        return {
            "valid": False,
            "status": "fail",
            "issues": [f"Candidate table is missing: {CANDIDATES}"],
            "warnings": [],
        }
    if not FINAL_MD.exists() or not FINAL_TSV.exists():
        missing = [str(path) for path in [FINAL_MD, FINAL_TSV] if not path.exists()]
        return {
            "valid": False,
            "status": "warn",
            "issues": [f"Final selection file(s) missing: {', '.join(missing)}"],
            "warnings": ["Record explicit user-approved panel choices before final export."],
        }

    candidates = read_tsv(CANDIDATES)
    selected = read_tsv(FINAL_TSV)
    candidate_options = {row["Option"]: row for row in candidates}

    by_panel: dict[str, list[dict[str, str]]] = {}
    for row in selected:
        panel = row.get("Panel", "")
        by_panel.setdefault(panel, []).append(row)
        option = row.get("Option", "")
        if option not in candidate_options:
            issues.append(f"Unknown option in final selection: {option}")
        elif candidate_options[option].get("Panel") != panel:
            issues.append(f"Option {option} does not belong to panel {panel}")
        if not row.get("Approved by", "").strip():
            issues.append(f"Option {option} has no Approved by value")
        if not row.get("Approved at", "").strip():
            issues.append(f"Option {option} has no Approved at timestamp")

    missing_panels = [panel for panel in REQUIRED_PANELS if panel not in by_panel]
    extra_panels = [panel for panel in by_panel if panel not in REQUIRED_PANELS]
    duplicated_panels = {panel: rows for panel, rows in by_panel.items() if len(rows) != 1}
    if missing_panels:
        issues.append("Missing required panel choices: " + ", ".join(missing_panels))
    if extra_panels:
        issues.append("Unexpected panel choices: " + ", ".join(extra_panels))
    if duplicated_panels:
        issues.append(
            "Panels with non-one selection count: "
            + "; ".join(f"{panel}={len(rows)}" for panel, rows in duplicated_panels.items())
        )

    return {
        "valid": not issues,
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "selected_count": len(selected),
        "required_panel_count": len(REQUIRED_PANELS),
        "final_tsv": str(FINAL_TSV),
        "final_md": str(FINAL_MD),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    result = validate()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()

