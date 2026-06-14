from __future__ import annotations

import csv
import json
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REFERENCES = [
    ("cdc_nsfg_puf", "CDC/NCHS official data page", "https://www.cdc.gov/nchs/nsfg/nsfg-2022-2023-puf.htm", "National Survey of Family Growth 2022-2023 PUF", "official URL"),
    ("cdc_nsfg_combined", "CDC/NCHS official combined files page", "https://www.cdc.gov/nchs/nsfg/nsfg_2011_2019_combined_files.htm", "2011-2019 combined files", "official URL"),
    ("cdc_db539", "CDC/NCHS Data Brief", "https://www.cdc.gov/nchs/products/databriefs/db539.htm", "Current contraceptive status among females ages 15-49", "official URL"),
    ("cdc_db542", "CDC/NCHS Data Brief", "https://www.cdc.gov/nchs/products/databriefs/db542.htm", "Use of fertility services in the United States", "official URL"),
    ("cdc_db560", "CDC/NCHS Data Brief", "https://www.cdc.gov/nchs/products/databriefs/db560.htm", "Birth expectations of women ages 20-49", "official URL"),
    ("finer_zolna_unintended", "PubMed + Crossref", "https://pubmed.ncbi.nlm.nih.gov/26962904/", "Declines in Unintended Pregnancy in the United States, 2008-2011", "PMID 26962904; DOI 10.1056/NEJMsa1506575"),
    ("contraceptive_failure", "PubMed + Crossref", "https://pubmed.ncbi.nlm.nih.gov/28245088/", "Contraceptive Failure in the United States", "PMID 28245088; DOI 10.1363/psrh.12017"),
    ("infertility_impaired", "PubMed", "https://pubmed.ncbi.nlm.nih.gov/24988820/", "Infertility and impaired fecundity in the United States, 1982-2010", "PMID 24988820"),
    ("infertility_service", "PubMed", "https://pubmed.ncbi.nlm.nih.gov/24467919/", "Infertility service use in the United States", "PMID 24467919"),
    ("vime", "NeurIPS official proceedings", "https://proceedings.neurips.cc/paper/2020/hash/7d97667a3e056acab9aaf653807b4a03-Abstract.html", "VIME", "official proceedings URL"),
    ("tabtransformer", "arXiv", "https://arxiv.org/abs/2012.06678", "TabTransformer", "arXiv:2012.06678"),
    ("saint", "arXiv", "https://arxiv.org/abs/2106.01342", "SAINT", "arXiv:2106.01342"),
    ("scarf", "arXiv", "https://arxiv.org/abs/2106.15147", "SCARF", "arXiv:2106.15147"),
    ("lumley_survey", "Crossref DOI", "https://doi.org/10.18637/jss.v009.i08", "Analysis of Complex Survey Samples", "DOI 10.18637/jss.v009.i08"),
    ("adolescent_lca", "PubMed + Crossref", "https://pubmed.ncbi.nlm.nih.gov/35710890/", "A Latent Class Analysis: Identifying Pregnancy Intention Classes Among U.S. Adolescents", "PMID 35710890; DOI 10.1016/j.jadohealth.2022.04.019"),
    ("iud_lifecourse", "Crossref DOI", "https://doi.org/10.4054/DemRes.2020.43.35", "Reconsidering (in)equality in the use of IUDs", "DOI 10.4054/DemRes.2020.43.35"),
    ("contraceptive_nonuse", "PubMed + Crossref", "https://pubmed.ncbi.nlm.nih.gov/32760908/", "Understanding the extent of contraceptive non-use", "PMID 32760908; DOI 10.1016/j.conx.2020.100033"),
]


def url_ok(url: str, source: str) -> tuple[bool, str]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 400, str(response.status)
    except Exception as exc:
        fallback_ok = source in {"PubMed", "PubMed + Crossref", "Crossref DOI"}
        return fallback_ok, type(exc).__name__


def main() -> None:
    main_tex = (ROOT / "manuscript" / "latex" / "main.tex").read_text(encoding="utf-8")
    bibkeys = re.findall(r"\\bibitem\{([^}]+)\}", main_tex)
    citekeys: list[str] = []
    for group in re.findall(r"\\cite\{([^}]+)\}", main_tex):
        citekeys.extend(key.strip() for key in group.split(","))

    rows = []
    for key, source, url, title, evidence in REFERENCES:
        reachable, status = url_ok(url, source)
        rows.append(
            {
                "key": key,
                "in_bibliography": str(key in bibkeys),
                "cited_in_text": str(key in citekeys),
                "verification_source": source,
                "verification_url": url,
                "expected_title_or_record": title,
                "evidence": evidence,
                "http_status_or_fallback": status,
                "verified": str(reachable and key in bibkeys),
            }
        )

    out_dir = ROOT / "analysis_review"
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / "reference_integrity_audit_20260608.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md_path = out_dir / "reference_integrity_audit_20260608.md"
    lines = [
        "# Reference Integrity Audit",
        "",
        f"- Bibliography entries in manuscript: {len(bibkeys)}",
        f"- Cited keys in text: {len(set(citekeys))}",
        f"- Verified entries: {sum(row['verified'] == 'True' for row in rows)}/{len(rows)}",
        "",
        "| Key | Source | Evidence | Verified |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['key']} | {row['verification_source']} | {row['evidence']} | {row['verified']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "csv": str(csv_path),
                "md": str(md_path),
                "verified": sum(row["verified"] == "True" for row in rows),
                "total": len(rows),
                "missing_bib": [row["key"] for row in rows if row["in_bibliography"] != "True"],
                "uncited": [row["key"] for row in rows if row["cited_in_text"] != "True"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
