"""Record user-approved PERSIST/PRISM panel choices.

This script is a gatekeeper. It writes final selection files only when the user
has explicitly approved a complete set of panel options.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
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

RECOMMENDED_ALIASES = {
    "recommended",
    "render all recommended options",
    "agree recommended",
    "agree with recommended",
    "同意推荐组合",
    "推荐组合",
}


def read_candidates() -> list[dict[str, str]]:
    with CANDIDATES.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_options(text: str) -> list[str]:
    if text.strip().lower() in RECOMMENDED_ALIASES:
        return RECOMMENDED_OPTIONS
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]


def validate_options(options: list[str], candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    by_option = {row["Option"]: row for row in candidates}
    unknown = [option for option in options if option not in by_option]
    if unknown:
        raise SystemExit(f"Unknown option(s): {', '.join(unknown)}")
    selected = [by_option[option] for option in options]
    by_panel: dict[str, list[str]] = {}
    for row in selected:
        by_panel.setdefault(row["Panel"], []).append(row["Option"])
    missing = [panel for panel in REQUIRED_PANELS if panel not in by_panel]
    duplicated = {panel: opts for panel, opts in by_panel.items() if len(opts) > 1}
    extra = [panel for panel in by_panel if panel not in REQUIRED_PANELS]
    if missing:
        raise SystemExit(f"Missing panel choices: {', '.join(missing)}")
    if duplicated:
        details = "; ".join(f"{panel}: {', '.join(opts)}" for panel, opts in duplicated.items())
        raise SystemExit(f"More than one option selected for panel(s): {details}")
    if extra:
        raise SystemExit(f"Unexpected panel choices: {', '.join(extra)}")
    return sorted(selected, key=lambda row: REQUIRED_PANELS.index(row["Panel"]))


def write_selection(selected: list[dict[str, str]], approved_by: str, approval_note: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with FINAL_TSV.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "Panel",
            "Figure",
            "Option",
            "Proposed chart",
            "PERSIST template/capsule",
            "Candidate kind",
            "Runtime",
            "Required data",
            "Risk / missing item",
            "Render decision",
            "Total score",
            "Approved by",
            "Approved at",
            "Approval note",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in selected:
            out = {field: row.get(field, "") for field in fieldnames}
            out["Approved by"] = approved_by
            out["Approved at"] = timestamp
            out["Approval note"] = approval_note
            writer.writerow(out)

    lines = [
        "# PERSIST/PRISM Panel Final Selection",
        "",
        f"Approved by: {approved_by}",
        f"Approved at: {timestamp}",
        f"Approval note: {approval_note or 'not provided'}",
        "",
        "These selections authorize Stage-2 rendering of variants from real project data. They do not by themselves authorize replacing manuscript figure assets before standalone outputs pass validation and user final-variant review.",
        "",
        "| Panel | Figure | Option | Chart | Template/capsule | Runtime |",
        "|---|---|---|---|---|---|",
    ]
    for row in selected:
        lines.append(
            "| {Panel} | {Figure} | {Option} | {Proposed chart} | {PERSIST template/capsule} | {Runtime} |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    lines.append("")
    FINAL_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--options",
        required=True,
        help="Comma-separated option IDs, or 'recommended'. Example: F1-W1,F2-A1,...",
    )
    parser.add_argument("--approved-by", default="", help="Name/label of approving user. Required with --write.")
    parser.add_argument("--approval-note", default="", help="Optional note copied into final selection files.")
    parser.add_argument("--write", action="store_true", help="Write final selection files. Omit for validation-only dry run.")
    args = parser.parse_args()

    selected = validate_options(parse_options(args.options), read_candidates())
    print("Validated panel choices:")
    for row in selected:
        print(f"- {row['Panel']}: {row['Option']} | {row['PERSIST template/capsule']}")
    if args.write:
        if not args.approved_by.strip():
            raise SystemExit("--approved-by is required when --write is used.")
        write_selection(selected, args.approved_by.strip(), args.approval_note.strip())
        print(f"Wrote {FINAL_TSV}")
        print(f"Wrote {FINAL_MD}")
    else:
        print("Dry run only. No final selection files were written.")


if __name__ == "__main__":
    main()
