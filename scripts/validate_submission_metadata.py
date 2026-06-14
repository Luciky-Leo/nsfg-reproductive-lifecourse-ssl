"""Validate final submission author and affiliation metadata.

The LaTeX builder reads ``config/submission_metadata.json`` when it exists.
This validator is intentionally strict about placeholder text so a final package
cannot accidentally retain draft author or affiliation fields.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "config" / "submission_metadata.json"
TEMPLATE = ROOT / "config" / "submission_metadata.template.json"

PLACEHOLDER_PATTERNS = [
    "to be completed",
    "Corresponding author name",
    "corresponding.author@example.com",
    "Department, Institution, City, Country",
    "example.com",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path: Path = METADATA) -> dict:
    issues: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        return {
            "valid": False,
            "status": "warn",
            "metadata_path": str(path),
            "template_path": str(TEMPLATE),
            "issues": [f"Metadata file is missing: {path}"],
            "warnings": ["Create it from config/submission_metadata.template.json before final export."],
        }
    try:
        metadata = load_json(path)
    except json.JSONDecodeError as exc:
        return {
            "valid": False,
            "status": "fail",
            "metadata_path": str(path),
            "issues": [f"Invalid JSON: {exc}"],
            "warnings": [],
        }

    authors = metadata.get("authors", [])
    affiliations = metadata.get("affiliations", {})
    if not isinstance(authors, list) or not authors:
        issues.append("authors must be a non-empty list")
    if not isinstance(affiliations, dict) or not affiliations:
        issues.append("affiliations must be a non-empty object")

    corresponding_count = 0
    for idx, author in enumerate(authors, start=1):
        prefix = f"authors[{idx}]"
        if not isinstance(author, dict):
            issues.append(f"{prefix} must be an object")
            continue
        name = str(author.get("name", "")).strip()
        email = str(author.get("email", "")).strip()
        affiliation = str(author.get("affiliation", "")).strip()
        if not name:
            issues.append(f"{prefix}.name is missing")
        if any(pattern.lower() in name.lower() for pattern in PLACEHOLDER_PATTERNS):
            issues.append(f"{prefix}.name contains placeholder text")
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            issues.append(f"{prefix}.email is not a valid email address")
        if any(pattern.lower() in email.lower() for pattern in PLACEHOLDER_PATTERNS):
            issues.append(f"{prefix}.email contains placeholder text")
        if not affiliation:
            issues.append(f"{prefix}.affiliation is missing")
        elif affiliation not in affiliations:
            issues.append(f"{prefix}.affiliation references unknown affiliation id {affiliation!r}")
        if bool(author.get("corresponding", False)):
            corresponding_count += 1
            if not email:
                issues.append(f"{prefix} is marked corresponding but has no email")

    if corresponding_count < 1:
        issues.append("at least one corresponding author is required")
    elif corresponding_count > 1:
        warnings.append(f"{corresponding_count} corresponding authors are listed; co-corresponding authors are allowed")

    for key, value in affiliations.items():
        text = str(value).strip()
        if not text:
            issues.append(f"affiliations[{key!r}] is empty")
        if any(pattern.lower() in text.lower() for pattern in PLACEHOLDER_PATTERNS):
            issues.append(f"affiliations[{key!r}] contains placeholder text")

    return {
        "valid": not issues,
        "status": "pass" if not issues else "warn",
        "metadata_path": str(path),
        "issues": issues,
        "warnings": warnings,
        "author_count": len(authors) if isinstance(authors, list) else 0,
        "corresponding_count": corresponding_count,
        "affiliation_count": len(affiliations) if isinstance(affiliations, dict) else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(METADATA), help="Metadata JSON path to validate.")
    args = parser.parse_args()
    result = validate(Path(args.path))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
