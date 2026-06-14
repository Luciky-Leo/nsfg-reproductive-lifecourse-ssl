"""Run the guarded final-submission closeout sequence.

This script coordinates the build steps that otherwise need to be run manually:

1. regenerate the LaTeX source package;
2. compile ``main.tex`` to ``main.pdf`` and
   ``supplementary_information.tex`` to ``supplementary_information.pdf``;
3. run manuscript-data consistency audit;
4. validate Figure 5 final-size candidate evidence;
5. run submission QA;
6. export a guarded Overleaf archive.

It refuses to create a FINAL archive while actionable QA warnings remain. A
pre-export warning about a stale prior Overleaf archive is ignored because the
new export is the step that resolves it. Use ``--allow-warnings`` only when an
explicitly labelled DRAFT archive is desired.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
LATEX = ROOT / "manuscript" / "latex"
QA_JSON = ROOT / "analysis_review" / "submission_package_qa_20260604.json"
PREFLIGHT_MD = ROOT / "analysis_review" / "final_submission_preflight_20260604.md"


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"+ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(cwd), env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def bundled_tectonic() -> Path | None:
    home = Path.home()
    candidates = [
        home
        / ".codex"
        / "plugins"
        / "cache"
        / "openai-bundled"
        / "latex"
        / "0.2.2"
        / "bin"
        / "tectonic.exe",
        Path("/mnt/c/Users/luff9/.codex/plugins/cache/openai-bundled/latex/0.2.2/bin/tectonic.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    path_hit = shutil.which("tectonic")
    return Path(path_hit) if path_hit else None


def subprocess_path(path: Path, executable: Path) -> str:
    """Return a path argument suitable for the executable being called.

    When a Windows .exe is invoked through WSL, absolute /mnt/e paths need to be
    converted to Windows drive paths for the Windows process.
    """
    if os.name == "posix" and executable.suffix.lower() == ".exe":
        try:
            return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
        except Exception:
            return str(path)
    return str(path)


def compile_pdf(tex_name: str) -> None:
    tectonic = bundled_tectonic()
    if not tectonic:
        raise SystemExit(f"No Tectonic executable found. Compile {tex_name} manually before final export.")
    cmd = [
        str(tectonic),
        "-X",
        "compile",
        "--outdir",
        subprocess_path(LATEX, tectonic),
        "--outfmt",
        "pdf",
        "--print",
        "--keep-logs",
        "--untrusted",
        tex_name,
    ]
    run(cmd, cwd=LATEX)


def read_qa() -> dict:
    if not QA_JSON.exists():
        raise SystemExit(f"QA JSON missing after QA run: {QA_JSON}")
    return json.loads(QA_JSON.read_text(encoding="utf-8"))


def scoped_counts(qa: dict, *, exclude_area: str | None = None) -> dict[str, int]:
    checks = qa.get("checks", [])
    if exclude_area is not None:
        checks = [check for check in checks if check.get("area") != exclude_area]
    return {
        "pass": sum(1 for check in checks if check.get("status") == "pass"),
        "warn": sum(1 for check in checks if check.get("status") == "warn"),
        "fail": sum(1 for check in checks if check.get("status") == "fail"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow a labelled DRAFT archive when QA warnings remain.",
    )
    parser.add_argument(
        "--no-source-data",
        action="store_true",
        help="Pass through to export_overleaf_package.py to omit source_data CSV files.",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    run([sys.executable, str(SCRIPTS / "build_latex_submission_package.py")], env=env)
    compile_pdf("main.tex")
    compile_pdf("supplementary_information.tex")
    run([sys.executable, str(SCRIPTS / "audit_manuscript_data_consistency.py")], env=env)
    run([sys.executable, str(SCRIPTS / "validate_figure5_finalsize_candidate.py")], env=env)
    run([sys.executable, str(SCRIPTS / "qa_submission_package.py")], env=env)
    run([sys.executable, str(SCRIPTS / "write_final_gate_status.py")], env=env)
    run([sys.executable, str(SCRIPTS / "final_submission_preflight.py")], env=env)
    run([sys.executable, str(SCRIPTS / "write_final_gap_report.py")], env=env)
    qa = read_qa()
    counts = scoped_counts(qa, exclude_area="overleaf_export")
    fail_count = int(counts.get("fail", 0))
    warn_count = int(counts.get("warn", 0))
    if fail_count:
        raise SystemExit(f"QA has {fail_count} failure(s); refusing archive export.")
    if warn_count and not args.allow_warnings:
        raise SystemExit(
            f"QA has {warn_count} warning(s); refusing FINAL export. "
            "Use --allow-warnings only for a DRAFT archive."
        )

    export_cmd = [sys.executable, str(SCRIPTS / "export_overleaf_package.py")]
    if warn_count or args.allow_warnings:
        export_cmd.append("--allow-warnings")
    if args.no_source_data:
        export_cmd.append("--no-source-data")
    run(export_cmd, env=env)
    run([sys.executable, str(SCRIPTS / "qa_submission_package.py")], env=env)
    run([sys.executable, str(SCRIPTS / "write_final_gate_status.py")], env=env)
    run([sys.executable, str(SCRIPTS / "final_submission_preflight.py")], env=env)
    run([sys.executable, str(SCRIPTS / "write_final_gap_report.py")], env=env)
    final_qa = read_qa()
    final_counts = final_qa.get("counts", {})
    final_fail_count = int(final_counts.get("fail", 0))
    final_warn_count = int(final_counts.get("warn", 0))
    if final_fail_count:
        raise SystemExit(f"Post-export QA has {final_fail_count} failure(s).")
    if final_warn_count and not args.allow_warnings:
        raise SystemExit(
            f"Post-export QA has {final_warn_count} warning(s); refusing FINAL closeout."
        )
    print(
        json.dumps(
            {
                "closeout": "complete",
                "qa_counts": final_counts,
                "preflight": str(PREFLIGHT_MD),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
