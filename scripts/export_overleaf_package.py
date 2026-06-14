"""Export an Overleaf-ready LaTeX archive with QA guardrails.

The exporter is conservative:
- it refuses to create a final package if QA has warnings or failures;
- it can create an explicitly labelled draft archive with --allow-warnings;
- it excludes build artifacts and raw-data directories.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEX = ROOT / "manuscript" / "latex"
QA_JSON = ROOT / "analysis_review" / "submission_package_qa_20260604.json"
EXPORTS = ROOT / "manuscript" / "exports"

REQUIRED_LATEX_FILES = [
    "main.tex",
    "main.pdf",
    "supplementary_information.tex",
    "supplementary_information.pdf",
    "README_OVERLEAF.md",
    "submission_package_manifest.json",
]

EXCLUDED_SUFFIXES = {
    ".aux",
    ".log",
    ".out",
    ".xdv",
    ".synctex.gz",
    ".zip",
}

EXCLUDED_PARTS = {
    "build",
    "__pycache__",
}


def read_qa() -> dict:
    if not QA_JSON.exists():
        raise SystemExit(f"QA JSON not found: {QA_JSON}")
    return json.loads(QA_JSON.read_text(encoding="utf-8"))


def archive_scope_checks(qa: dict) -> list[dict]:
    """Return checks that should be embedded in an archive manifest.

    The archive cannot be expected to satisfy checks about a prior archive before
    the new archive exists, so overleaf_export self-checks are deliberately kept
    out of the manifest's synchronized QA scope.
    """

    return [
        check
        for check in qa.get("checks", [])
        if check.get("area") != "overleaf_export"
    ]


def count_statuses(checks: list[dict]) -> dict[str, int]:
    return {
        "pass": sum(1 for check in checks if check.get("status") == "pass"),
        "warn": sum(1 for check in checks if check.get("status") == "warn"),
        "fail": sum(1 for check in checks if check.get("status") == "fail"),
    }


def assert_required_files() -> None:
    missing = [name for name in REQUIRED_LATEX_FILES if not (LATEX / name).exists()]
    if missing:
        raise SystemExit(f"Required LaTeX package files are missing: {', '.join(missing)}")
    for subdir in ["figures", "tables", "source_data"]:
        if not (LATEX / subdir).is_dir():
            raise SystemExit(f"Required LaTeX package directory is missing: {subdir}")


def archive_members(include_source_data: bool) -> list[Path]:
    members: list[Path] = []
    for path in sorted(LATEX.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(LATEX)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if not include_source_data and rel.parts and rel.parts[0] == "source_data":
            continue
        members.append(path)
    return members


def package_name(status: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"nsfg_reproductive_lifecourse_ssl_latex_package_{status}_{timestamp}.zip"


def make_archive(status: str, include_source_data: bool, qa: dict) -> Path:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    archive_path = EXPORTS / package_name(status)
    members = archive_members(include_source_data=include_source_data)
    if not any(path.relative_to(LATEX).as_posix() == "main.tex" for path in members):
        raise SystemExit("main.tex would not be included in the archive; refusing export.")

    manifest_checks = archive_scope_checks(qa)
    manifest_counts = count_statuses(manifest_checks)
    archive_manifest = {
        "project": ROOT.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "qa_counts": manifest_counts,
        "qa_counts_raw": qa.get("counts", {}),
        "qa_scope": "non_overleaf_export_checks",
        "include_source_data": include_source_data,
        "latex_root": str(LATEX),
        "member_count": len(members) + 1,
        "members": [path.relative_to(LATEX).as_posix() for path in members] + ["OVERLEAF_ARCHIVE_MANIFEST.json"],
        "warnings": [
            check
            for check in manifest_checks
            if check.get("status") == "warn"
        ],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in members:
            zf.write(path, path.relative_to(LATEX).as_posix())
        zf.writestr("OVERLEAF_ARCHIVE_MANIFEST.json", json.dumps(archive_manifest, indent=2))

    sidecar = archive_path.with_suffix(".manifest.json")
    sidecar.write_text(json.dumps(archive_manifest, indent=2), encoding="utf-8")
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Create an explicitly labelled DRAFT archive even when QA warnings remain.",
    )
    parser.add_argument(
        "--no-source-data",
        action="store_true",
        help="Exclude source_data CSV files from the archive. Default includes them.",
    )
    args = parser.parse_args()

    assert_required_files()
    qa = read_qa()
    counts = count_statuses(archive_scope_checks(qa))
    raw_counts = qa.get("counts", {})
    fail_count = int(counts.get("fail", 0))
    warn_count = int(counts.get("warn", 0))
    if fail_count:
        raise SystemExit(f"QA has {fail_count} failure(s); refusing export.")
    if warn_count and not args.allow_warnings:
        raise SystemExit(
            f"QA has {warn_count} warning(s). Use --allow-warnings only for a DRAFT archive."
        )
    status = "DRAFT" if warn_count else "FINAL"
    archive_path = make_archive(
        status=status,
        include_source_data=not args.no_source_data,
        qa=qa,
    )
    print(json.dumps({
        "archive": str(archive_path),
        "status": status,
        "qa_counts": counts,
        "qa_counts_raw": raw_counts,
        "qa_scope": "non_overleaf_export_checks",
        "include_source_data": not args.no_source_data,
        "size_bytes": archive_path.stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()
