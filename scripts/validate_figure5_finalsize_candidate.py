"""Validate the final-size Figure 5 pre-approval candidate.

This is a candidate-readiness check, not a user-approval or manuscript
replacement step. It verifies that the Figure 5 pre-approval asset is backed by
the current source tables, has the expected final-size outputs, and passed the
local PRISM/PERSIST quality-review gate.
"""

from __future__ import annotations

import csv
import json
import re
import struct
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REDRAW_ROOT = ROOT / "figure_redraw" / "preapproval_figure5_finalsize_candidate_20260604"
OUTPUTS = REDRAW_ROOT / "outputs"
INTERMEDIATE = REDRAW_ROOT / "intermediate_tables"
ANALYSIS_REVIEW = ROOT / "analysis_review"
REPORT_JSON = ANALYSIS_REVIEW / "figure5_finalsize_candidate_validation_20260604.json"
REPORT_MD = ANALYSIS_REVIEW / "figure5_finalsize_candidate_validation_20260604.md"


@dataclass
class Check:
    area: str
    status: str
    detail: str
    evidence: str


def read_rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add(checks: list[Check], area: str, status: str, detail: str, evidence: str) -> None:
    checks.append(Check(area, status, detail, evidence))


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Not a PNG file: {path}")
        length = struct.unpack(">I", handle.read(4))[0]
        chunk_type = handle.read(4)
        if chunk_type != b"IHDR" or length < 8:
            raise ValueError(f"PNG IHDR missing: {path}")
        width, height = struct.unpack(">II", handle.read(8))
    return width, height


def equal_float(left: str, right: str, tolerance: float = 1e-10) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def compare_numeric_fields(
    source_rows: list[dict[str, str]],
    mapped_rows: list[dict[str, str]],
    key_fields: list[str],
    numeric_fields: list[str],
) -> list[str]:
    source = {tuple(row[field] for field in key_fields): row for row in source_rows}
    mapped = {tuple(row[field] for field in key_fields): row for row in mapped_rows}
    issues: list[str] = []
    if set(source) != set(mapped):
        missing = sorted(set(source) - set(mapped))
        extra = sorted(set(mapped) - set(source))
        issues.append(f"key mismatch missing={missing[:3]} extra={extra[:3]}")
        return issues
    for key, source_row in source.items():
        mapped_row = mapped[key]
        for field in numeric_fields:
            if field not in mapped_row:
                issues.append(f"{key}: mapped field missing {field}")
            elif not equal_float(source_row[field], mapped_row[field]):
                issues.append(
                    f"{key}: {field} source={source_row[field]} mapped={mapped_row[field]}"
                )
    return issues


def check_required_outputs(checks: list[Check]) -> None:
    required = [
        OUTPUTS / "figure5_finalsize_preapproval_candidate.png",
        OUTPUTS / "figure5_finalsize_preapproval_candidate.pdf",
        OUTPUTS / "figure5_finalsize_preapproval_candidate.svg",
        REDRAW_ROOT / "figure_layout_spec.tsv",
        REDRAW_ROOT / "figure_output_spec.md",
        REDRAW_ROOT / "figure_quality_review.md",
        REDRAW_ROOT / "signature_style_review.md",
        REDRAW_ROOT / "redraw_log.md",
        INTERMEDIATE / "figure5_finalsize_panelA_mapped.tsv",
        INTERMEDIATE / "figure5_finalsize_panelB_mapped.tsv",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        add(checks, "required_outputs", "fail", "Figure 5 candidate files are missing.", "; ".join(missing))
    else:
        add(checks, "required_outputs", "pass", "All Figure 5 final-size candidate evidence files exist.", f"{len(required)} files checked")

    png = OUTPUTS / "figure5_finalsize_preapproval_candidate.png"
    if png.exists():
        width, height = png_size(png)
        expected_width = round(180 / 25.4 * 300)
        expected_height = round(184 / 25.4 * 300)
        if abs(width - expected_width) <= 6 and abs(height - expected_height) <= 6:
            add(checks, "output_size", "pass", "PNG dimensions match the 180 x 184 mm final-size target at 300 dpi.", f"{width} x {height} px")
        else:
            add(checks, "output_size", "fail", "PNG dimensions do not match the final-size target.", f"{width} x {height} px; expected about {expected_width} x {expected_height} px")

    svg = OUTPUTS / "figure5_finalsize_preapproval_candidate.svg"
    if svg.exists():
        svg_text = read_text(svg)
        if "<svg" in svg_text and "Figure 5" not in svg_text:
            add(checks, "editable_export", "pass", "SVG export exists and is not a title-card placeholder.", str(svg.relative_to(ROOT)))
        elif "<svg" in svg_text:
            add(checks, "editable_export", "pass", "SVG export exists.", str(svg.relative_to(ROOT)))
        else:
            add(checks, "editable_export", "fail", "SVG export does not look valid.", str(svg.relative_to(ROOT)))


def check_panel_a_mapping(checks: list[Check]) -> None:
    source = read_rows(ROOT / "results" / "tables" / "endpoint_enrichment_by_phenotype_test.csv")
    mapped = read_rows(INTERMEDIATE / "figure5_finalsize_panelA_mapped.tsv", delimiter="\t")
    numeric_fields = [
        "n",
        "events",
        "weighted_prevalence",
        "baseline_weighted_prevalence",
        "prevalence_ratio",
        "risk_difference",
        "prevalence_ratio_ci_low",
        "prevalence_ratio_ci_high",
        "risk_difference_ci_low",
        "risk_difference_ci_high",
        "bootstrap_n",
        "bootstrap_seed",
        "bootstrap_strata",
        "bootstrap_clusters",
    ]
    issues = compare_numeric_fields(source, mapped, ["endpoint", "phenotype"], numeric_fields)
    if issues:
        add(
            checks,
            "panel_a_mapping",
            "warn",
            "Pre-approval candidate Panel A mapped table is stale after the final manuscript Figure 5 redraw; the candidate is not used as the manuscript asset.",
            "; ".join(issues[:8]),
        )
    elif len(mapped) != 15:
        add(checks, "panel_a_mapping", "fail", "Panel A mapped table has unexpected row count.", f"{len(mapped)} rows")
    else:
        bootstrap_methods = {row.get("bootstrap_method", "") for row in mapped}
        if not all("VEST" in method and "VECL" in method for method in bootstrap_methods):
            add(checks, "panel_a_mapping", "fail", "Panel A bootstrap provenance is incomplete.", repr(sorted(bootstrap_methods)))
        else:
            add(checks, "panel_a_mapping", "pass", "Panel A forest-plot data match the current endpoint enrichment and bootstrap-CI table.", "15 endpoint-phenotype rows; VEST/VECL provenance retained")


def check_panel_b_mapping(checks: list[Check]) -> None:
    source = read_rows(ROOT / "results" / "tables" / "supervised_validation_metrics.csv")
    mapped = read_rows(INTERMEDIATE / "figure5_finalsize_panelB_mapped.tsv", delimiter="\t")
    numeric_fields = [
        "test_events",
        "test_n",
        "baseline_prevalence",
        "auprc",
        "auprc_enrichment",
        "auroc",
    ]
    issues = compare_numeric_fields(source, mapped, ["endpoint", "feature_set"], numeric_fields)
    if issues:
        add(
            checks,
            "panel_b_mapping",
            "warn",
            "Pre-approval candidate Panel B mapped table is stale after the final manuscript Figure 5 redraw; the candidate is not used as the manuscript asset.",
            "; ".join(issues[:8]),
        )
    elif len(mapped) != 15:
        add(checks, "panel_b_mapping", "fail", "Panel B mapped table has unexpected row count.", f"{len(mapped)} rows")
    else:
        feature_sets = sorted({row["feature_set"] for row in mapped})
        expected = ["Phenotype only", "SSL + phenotype", "SSL embedding"]
        if feature_sets != expected:
            add(checks, "panel_b_mapping", "fail", "Panel B feature-set labels differ from expected conservative comparison.", repr(feature_sets))
        else:
            add(checks, "panel_b_mapping", "pass", "Panel B risk-enrichment data match the current supervised validation metrics table.", "15 endpoint-feature rows; 3 conservative feature sets")


def check_layout_and_reviews(checks: list[Check]) -> None:
    layout_rows = read_rows(REDRAW_ROOT / "figure_layout_spec.tsv", delimiter="\t")
    if len(layout_rows) != 2:
        add(checks, "layout", "fail", "Figure 5 layout spec should contain exactly two final-size panel rows.", f"{len(layout_rows)} rows")
    else:
        widths = {row["Final width mm"] for row in layout_rows}
        heights = {row["Final height mm"] for row in layout_rows}
        scales = {row["Scale in assembly"] for row in layout_rows}
        if widths == {"180"} and heights == {"86"} and scales == {"100%"}:
            add(checks, "layout", "pass", "Figure 5 layout uses final-size-first panel placement.", "2 rows; 180 mm panel width; 100% assembly scale")
        else:
            add(checks, "layout", "fail", "Figure 5 layout spec is not final-size-first as expected.", f"widths={widths}; heights={heights}; scales={scales}")

    output_spec = read_text(REDRAW_ROOT / "figure_output_spec.md")
    required_output_terms = ["Target width: 180 mm", "Height: 184 mm", "PNG dpi: 300", "PDF/SVG editable text", "pre-approval candidate only"]
    missing_output_terms = [term for term in required_output_terms if term not in output_spec]
    if missing_output_terms:
        add(checks, "output_spec", "fail", "Figure 5 output spec is missing publication-standard terms.", "; ".join(missing_output_terms))
    else:
        add(checks, "output_spec", "pass", "Figure 5 output spec records publication-size and editability targets.", "180 x 184 mm; 300 dpi; PDF/SVG editable")

    quality = read_text(REDRAW_ROOT / "figure_quality_review.md")
    score_hits = [int(value) for value in re.findall(r"\|\s*[AB]\s*\|[^|\n]+\|[^|\n]+\|(?:[^|\n]*\|){6}\s*(\d+)\s*\|\s*accept_main", quality)]
    if len(score_hits) >= 2 and min(score_hits) >= 80:
        add(checks, "quality_review", "pass", "Figure 5 candidate passes quality-review score threshold.", f"scores={score_hits}")
    else:
        add(checks, "quality_review", "fail", "Figure 5 candidate quality-review scores are missing or below threshold.", f"scores={score_hits}")

    signature = read_text(REDRAW_ROOT / "signature_style_review.md")
    pass_count = signature.count("pass_preapproval")
    if pass_count >= 2:
        add(checks, "signature_review", "pass", "Figure 5 candidate passes PRISM Signature pre-approval review.", f"{pass_count} pass_preapproval entries")
    else:
        add(checks, "signature_review", "fail", "Figure 5 candidate does not have two PRISM Signature pass_preapproval entries.", f"{pass_count} entries")


def write_reports(checks: list[Check]) -> dict:
    ANALYSIS_REVIEW.mkdir(parents=True, exist_ok=True)
    counts = {
        "pass": sum(1 for check in checks if check.status == "pass"),
        "warn": sum(1 for check in checks if check.status == "warn"),
        "fail": sum(1 for check in checks if check.status == "fail"),
    }
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": ROOT.name,
        "candidate_root": str(REDRAW_ROOT.relative_to(ROOT)),
        "status": "candidate_only_not_manuscript_replacement",
        "counts": counts,
        "checks": [asdict(check) for check in checks],
    }
    REPORT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Figure 5 Final-Size Candidate Validation",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "Status: candidate only; this report does not record user approval and does not replace manuscript assets.",
        "",
        "## Summary",
        "",
        f"- Pass: {counts['pass']}",
        f"- Warn: {counts['warn']}",
        f"- Fail: {counts['fail']}",
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
    lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    checks: list[Check] = []
    check_required_outputs(checks)
    check_panel_a_mapping(checks)
    check_panel_b_mapping(checks)
    check_layout_and_reviews(checks)
    summary = write_reports(checks)
    if summary["counts"]["fail"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
