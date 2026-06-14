"""Create ``config/submission_metadata.json`` from command-line inputs.

This helper avoids hand-editing JSON for the final author gate. It keeps the
known first three authors from the template, marks one author as corresponding
or appends a new corresponding author, writes the final affiliation, and then
validates the result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_submission_metadata import validate


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "config" / "submission_metadata.template.json"
OUTPUT = ROOT / "config" / "submission_metadata.json"

PLACEHOLDER_NAMES = {
    "corresponding author name",
}


def load_template() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def build_metadata(corresponding_name: str, corresponding_email: str, affiliation: str) -> dict:
    template = load_template()
    authors = []
    for author in template.get("authors", []):
        name = str(author.get("name", "")).strip()
        email = str(author.get("email", "")).strip()
        if normalize(name) in PLACEHOLDER_NAMES or email.endswith("@example.com"):
            continue
        authors.append(
            {
                "name": name,
                "email": email,
                "affiliation": str(author.get("affiliation", "1")).strip() or "1",
            }
        )

    target = normalize(corresponding_name)
    matched = False
    for author in authors:
        author.pop("corresponding", None)
        if normalize(author["name"]) == target:
            author["email"] = corresponding_email.strip()
            author["corresponding"] = True
            matched = True

    if not matched:
        authors.append(
            {
                "name": corresponding_name.strip(),
                "email": corresponding_email.strip(),
                "affiliation": "1",
                "corresponding": True,
            }
        )

    return {
        "authors": authors,
        "affiliations": {
            "1": affiliation.strip(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corresponding-name", required=True, help="Final corresponding author name.")
    parser.add_argument("--corresponding-email", required=True, help="Final corresponding author email.")
    parser.add_argument("--affiliation", required=True, help="Final affiliation string for affiliation id 1.")
    parser.add_argument("--write", action="store_true", help="Write config/submission_metadata.json. Omit for dry run.")
    args = parser.parse_args()

    metadata = build_metadata(
        corresponding_name=args.corresponding_name,
        corresponding_email=args.corresponding_email,
        affiliation=args.affiliation,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    if args.write:
        OUTPUT.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = validate(OUTPUT)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(0 if result["valid"] else 1)
    print("Dry run only. Add --write to create config/submission_metadata.json.")


if __name__ == "__main__":
    main()

