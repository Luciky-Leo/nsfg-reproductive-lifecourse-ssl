"""Build an Overleaf-ready LaTeX manuscript package from current NSFG outputs."""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_TABLES = ROOT / "results" / "tables"
RESULT_FIGURES = ROOT / "results" / "figures"
FINAL_USER_FIGURES = ROOT / "figure_redraw" / "fig" / "NEW"
CONFIG = ROOT / "config"
SUBMISSION_METADATA = CONFIG / "submission_metadata.json"
MANUSCRIPT_TABLES = ROOT / "manuscript" / "tables"
LATEX = ROOT / "manuscript" / "latex"
LATEX_TABLES = LATEX / "tables"
LATEX_FIGURES = LATEX / "figures"
SOURCE_DATA = LATEX / "source_data"
SPRINGER_TEMPLATE = ROOT.parent / "Temp" / "_tmp_springer_nature_template"
SPRINGER_TEMPLATE_FILES = [
    "sn-jnl.cls",
    "sn-basic.bst",
    "sn-vancouver-num.bst",
    "sn-mathphys-num.bst",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def latex_escape(value: object) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def fnum(value: object, digits: int = 2) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return latex_escape(value)
    if math.isnan(x):
        return ""
    return f"{x:.{digits}f}"


def pct(value: object, digits: int = 1) -> str:
    try:
        x = float(value) * 100
    except (TypeError, ValueError):
        return latex_escape(value)
    if math.isnan(x):
        return ""
    return f"{x:.{digits}f}"


def comma_int(value: object) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return latex_escape(value)


def rp(width: str) -> str:
    """Ragged-right paragraph column for compact manuscript tables."""
    return rf">{{\raggedright\arraybackslash}}p{{{width}}}"


def analysis_short(value: str) -> str:
    lower_value = value.lower()
    if lower_value.startswith("ever"):
        return "Ever-pregnant"
    if lower_value.startswith("full"):
        return "Full cohort"
    return value


def subgroup_value_label(subgroup_type: str, subgroup_value: str) -> str:
    """Reader-facing labels for public-use subgroup recodes."""
    value = str(subgroup_value)
    if subgroup_type == "race_ethnicity":
        return {
            "1": "Hispanic",
            "2": "Non-Hispanic White",
            "3": "Non-Hispanic Black",
            "4": "Non-Hispanic Other/multiple",
        }.get(value, value)
    if subgroup_type == "insurance":
        return {
            "1": "Private/Medi-Gap",
            "2": "Medicaid/CHIP/state plan",
            "3": "Medicare/military/other gov.",
            "4": "Single-service/IHS/uninsured",
        }.get(value, value)
    if subgroup_type == "parity_group":
        return f"Parity {value}"
    return value


def pr_ci_text(row: dict[str, str]) -> str:
    point_key = "prevalence_ratio" if "prevalence_ratio" in row else "top_prevalence_ratio"
    return (
        f"{fnum(row[point_key], 2)} "
        f"({fnum(row['prevalence_ratio_ci_low'], 2)}--{fnum(row['prevalence_ratio_ci_high'], 2)})"
    )


def pr_ci_sentence(row: dict[str, str]) -> str:
    point_key = "prevalence_ratio" if "prevalence_ratio" in row else "top_prevalence_ratio"
    return (
        f"{fnum(row[point_key], 2)}; "
        f"95\\% CI {fnum(row['prevalence_ratio_ci_low'], 2)}--{fnum(row['prevalence_ratio_ci_high'], 2)}"
    )


def rd_ci_text(row: dict[str, str]) -> str:
    point = float(row["risk_difference"]) * 100
    low = float(row["risk_difference_ci_low"]) * 100
    high = float(row["risk_difference_ci_high"]) * 100
    return f"{point:.1f} ({low:.1f} to {high:.1f})"


ENDPOINT_LABELS = {
    "contraceptive_vulnerability": "Contraceptive vulnerability",
    "fertility_service_or_loss_help": "Fertility or loss help",
    "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy history",
    "adverse_pregnancy_history_proxy": "Adverse pregnancy-history proxy",
    "impaired_fecundity_status": "Fecundity limitation/infertility",
}

COMPACT_ENDPOINT_LABELS = {
    "contraceptive_vulnerability": "Contraceptive vuln.",
    "fertility_service_or_loss_help": "Fertility/loss help",
    "unintended_mistimed_pregnancy_history": "Mistimed/unwtd.",
    "adverse_pregnancy_history_proxy": "Adverse proxy",
    "impaired_fecundity_status": "Fecundity limit./infert.",
}

VARIABLE_LABELS = {
    "age_analysis": "Age, years",
    "parity": "Parity",
    "preg_n_records": "Pregnancy records",
    "has_pregnancy_record": "Any pregnancy record, %",
    "poverty": "Poverty-income ratio",
    "contraceptive_vulnerability": "Contraceptive vulnerability, %",
    "fertility_service_or_loss_help": "Fertility or loss help, %",
    "unintended_mistimed_pregnancy_history": "Mistimed/unwanted pregnancy, %",
    "adverse_pregnancy_history_proxy": "Adverse pregnancy-history proxy, %",
    "impaired_fecundity_status": "Fecundity limitation/infertility, %",
}


def mean_sd_text(mean_value: object, sd_value: object, digits: int = 1) -> str:
    return f"{fnum(mean_value, digits)} ({fnum(sd_value, digits)})"


def phenotype_value(row: dict[str, str], phenotype: int) -> str:
    """Read phenotype columns stored either as P0/P1/P2 or 0/1/2."""
    return row.get(f"P{phenotype}", row.get(str(phenotype), ""))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def supplementary_table_layout(text: str) -> str:
    """Keep supplementary tables in sequence and full text width.

    The same table fragments are not embedded in the main manuscript. In the
    separate supplementary PDF, [H] prevents S1/S2 from floating above the
    supplement title, and \textwidth gives all tables a consistent body width.
    """
    text = text.replace(r"\begin{table}[tbp]", r"\begin{table}[H]")
    text = re.sub(
        r"\\begin\{tabular\*\}\{0\.\d+\\textwidth\}",
        lambda _match: r"\begin{tabular*}{\textwidth}",
        text,
    )
    return text


DEFAULT_SUBMISSION_METADATA = {
    "authors": [
        {"name": "Fengshang Yan", "email": "342082145@qq.com", "affiliation": "1"},
        {"name": "Qianqian Yang", "email": "yangqianqian8733@163.com", "affiliation": "1"},
        {"name": "Mingtang Wang", "email": "1099529466@qq.com", "affiliation": "1"},
        {"name": "Corresponding author to be completed", "email": "", "affiliation": "1"},
    ],
    "affiliations": {
        "1": "Affiliation to be completed before submission",
    },
}


def load_submission_metadata() -> dict:
    if SUBMISSION_METADATA.exists():
        return json.loads(SUBMISSION_METADATA.read_text(encoding="utf-8"))
    return DEFAULT_SUBMISSION_METADATA


def split_author_name(name: str) -> tuple[str, str]:
    parts = [part for part in name.strip().split() if part]
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return name.strip(), ""


def springer_affiliation_tex(affil_id: str, affiliation: str, first: bool = False) -> str:
    macro = r"\affil*" if first else r"\affil"
    normalized = " ".join(affiliation.split())
    if (
        "Department of Obstetrics and Gynecology" in normalized
        and "Changhai Hospital" in normalized
        and "Naval Medical University" in normalized
    ):
        return (
            rf"{macro}[{latex_escape(affil_id)}]"
            r"{\orgdiv{Department of Obstetrics and Gynecology}, "
            r"\orgname{Changhai Hospital, Naval Medical University}, "
            r"\orgaddress{\postcode{200433}, \city{Shanghai}, \country{China}}"
            r"}"
        )
    return rf"{macro}[{latex_escape(affil_id)}]{{\orgname{{{latex_escape(affiliation)}}}}}"


def author_affiliation_tex() -> str:
    metadata = load_submission_metadata()
    lines: list[str] = []
    for author in metadata.get("authors", []):
        raw_name = str(author.get("name", "")).strip()
        if not raw_name:
            continue
        fnm, sur = split_author_name(raw_name)
        email = author.get("email", "")
        corresponding = bool(author.get("corresponding", False))
        affil_id = str(author.get("affiliation", "1")).strip() or "1"
        macro = r"\author*" if corresponding else r"\author"
        name_tex = rf"\fnm{{{latex_escape(fnm)}}}"
        if sur:
            name_tex += rf" \sur{{{latex_escape(sur)}}}"
        lines.append(rf"{macro}[{latex_escape(affil_id)}]{{{name_tex}}}")
        if email:
            lines.append(rf"\email{{{latex_escape(email)}}}")
        if bool(author.get("equal_contribution", False)):
            lines.append(r"\equalcont{These authors contributed equally to this work.}")

    affiliations = metadata.get("affiliations", {})
    for idx, (affil_id, affiliation) in enumerate(sorted(affiliations.items(), key=lambda item: item[0])):
        lines.append(springer_affiliation_tex(str(affil_id), str(affiliation), first=(idx == 0)))
    return "\n".join(lines)


def author_contributions_tex() -> str:
    metadata = load_submission_metadata()
    statement = str(metadata.get("contribution_statement", "")).strip()
    if statement:
        return latex_escape(statement)

    authors = [
        str(author.get("name", "")).strip()
        for author in metadata.get("authors", [])
        if str(author.get("name", "")).strip()
    ]
    corresponding = [
        str(author.get("name", "")).strip()
        for author in metadata.get("authors", [])
        if str(author.get("name", "")).strip() and bool(author.get("corresponding", False))
    ]
    corresponding_set = set(corresponding)
    non_corresponding = [name for name in authors if name not in corresponding_set]

    if non_corresponding and corresponding:
        first_part = (
            f"{', '.join(non_corresponding)} contributed to study conceptualization, "
            "public-data curation, formal analysis, figure and table generation, "
            "and manuscript drafting."
        )
        second_part = (
            f"{', '.join(corresponding)} supervised the study, reviewed and edited "
            "the manuscript, and approved the final version."
        )
        return latex_escape(f"{first_part} {second_part}")
    if authors:
        return latex_escape(
            f"{', '.join(authors)} contributed to study conceptualization, public-data "
            "curation, formal analysis, figure and table generation, manuscript drafting, "
            "and final manuscript review."
        )
    return "Author contributions should be completed before submission."


def table1_tex() -> str:
    rows = read_csv(MANUSCRIPT_TABLES / "table1_cohort_characteristics.csv")
    row_by_split = {row["analysis_split"]: row for row in rows}
    split_columns = [
        ("Training/pretraining", "Training/pretraining"),
        ("Development/model selection", "Development"),
        ("Temporal validation", "Temporal validation"),
    ]
    display_rows = [
        ("Respondents, n", lambda r: comma_int(r["n_respondents"])),
        ("Age, years, mean (SD)", lambda r: mean_sd_text(r["weighted_mean_age"], r.get("weighted_sd_age", ""), 1)),
        ("Parity, mean (SD)", lambda r: mean_sd_text(r["weighted_mean_parity"], r.get("weighted_sd_parity", ""), 2)),
        ("Any pregnancy record, %", lambda r: pct(r["weighted_pregnancy_record_prevalence"], 1)),
        ("Contraceptive vulnerability, %", lambda r: pct(r["contraceptive_vulnerability_weighted_prev"], 1)),
        ("Fertility/loss help, %", lambda r: pct(r["fertility_service_or_loss_help_weighted_prev"], 1)),
        ("Mistimed/unwanted pregnancy history, %", lambda r: pct(r["unintended_mistimed_pregnancy_history_weighted_prev"], 1)),
        ("Adverse pregnancy-history proxy, %", lambda r: pct(r["adverse_pregnancy_history_proxy_weighted_prev"], 1)),
        ("Fecundity limitation/infertility, %", lambda r: pct(r["impaired_fecundity_status_weighted_prev"], 1)),
    ]
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Cohort characteristics by temporal analysis split. Weighted estimates use public-use NSFG analysis weights; model training did not use survey weights as input features. Values for age and parity are weighted mean (SD). Endpoint percentages use the full analytic respondent denominator and therefore represent survey-level endpoint proxies rather than pregnancy-record-only rates.}",
        r"\label{tab:cohort}",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.34\textwidth") + r"rrr@{}}",
        r"\toprule",
        r"Characteristic & Training/pretraining & Development & Temporal validation \\",
        r"\midrule",
    ]
    for label, formatter in display_rows:
        values = [formatter(row_by_split[key]) for key, _ in split_columns]
        lines.append(f"{latex_escape(label)} & {' & '.join(values)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def table2_tex() -> str:
    rows = read_csv(MANUSCRIPT_TABLES / "table2_variables_endpoints.csv")
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Input feature set and validation endpoint definitions. Direct endpoint-defining variables were excluded from the primary encoder input before SSL fitting. The fecundity-limitation endpoint excludes contraceptive sterilization from the FECUND recode.}",
        r"\label{tab:endpoints}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.20\textwidth") + rp(r"0.42\textwidth") + r"c" + rp(r"0.22\textwidth") + r"@{}}",
        r"\toprule",
        r"Domain or endpoint & Operational definition & Role & Leakage-control rule \\",
        r"\midrule",
    ]
    for row in rows:
        name = ENDPOINT_LABELS.get(row["domain_or_endpoint"], row["domain_or_endpoint"])
        name = name.replace("Mistimed/unwanted", "Mistimed or unwanted")
        name = name.replace("Fecundity limitation/infertility", "Fecundity limitation or infertility")
        role = row["n_features"]
        if role == "Endpoint":
            role = "Endpt."
        leakage_rule = row["leakage_control"]
        if len(leakage_rule) > 55 or "|" in leakage_rule:
            leakage_rule = "Direct endpoint-variable regex excluded; full regex retained in source-data table."
        lines.append(
            f"{latex_escape(name)} & {latex_escape(row['definition'])} & {latex_escape(role)} & {latex_escape(leakage_rule)} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def table3_tex() -> str:
    rows = read_csv(MANUSCRIPT_TABLES / "table3_phenotype_profiles.csv")
    percent_vars = {
        "has_pregnancy_record",
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "unintended_mistimed_pregnancy_history",
        "adverse_pregnancy_history_proxy",
        "impaired_fecundity_status",
    }
    order = [
        "age_analysis",
        "parity",
        "preg_n_records",
        "has_pregnancy_record",
        "poverty",
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "unintended_mistimed_pregnancy_history",
        "adverse_pregnancy_history_proxy",
        "impaired_fecundity_status",
    ]
    by_var = {row["variable"]: row for row in rows}
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Survey-weighted temporal-validation phenotype profiles in 2022--2023. Phenotype labels were assigned from development-cycle centroids and named descriptively from profile characteristics, not from outcome status alone.}",
        r"\label{tab:phenotype_profiles}",
        r"\small",
        r"\setlength{\tabcolsep}{6pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}>{\raggedright\arraybackslash}p{0.56\textwidth}rrr@{}}",
        r"\toprule",
        r"Profile characteristic & P0 & P1 & P2 \\",
        r"\midrule",
    ]
    for var in order:
        row = by_var[var]
        vals = []
        for ph in [0, 1, 2]:
            val = phenotype_value(row, ph)
            vals.append(pct(val, 1) if var in percent_vars else fnum(val, 2))
        lines.append(f"{latex_escape(VARIABLE_LABELS[var])} & {' & '.join(vals)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def table4_tex() -> str:
    rows = read_csv(MANUSCRIPT_TABLES / "table4_endpoint_enrichment_model_metrics.csv")
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Temporal-validation endpoint enrichment by transferred SSL phenotype. The highest-enrichment phenotype is shown for each endpoint, with event counts. Pregnancy-history endpoints use the ever-pregnant stratum as the primary interpretive display to reduce mechanical enrichment from pregnancy exposure; other endpoints use the full analytic cohort. Prevalence-ratio intervals are stratified cluster bootstrap percentile intervals using public-use \texttt{VEST}/\texttt{VECL} design variables with respondent weights retained. Secondary supervised raw-feature and SSL comparisons are reported in Supplementary Table 10.}",
        r"\label{tab:enrichment}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.20\textwidth") + r"lcrcc@{}}",
        r"\toprule",
        r"Endpoint & Analysis & Top phenotype & Events/N & Top \% & PR (95\% CI) \\",
        r"\midrule",
    ]
    for row in rows:
        top_phenotype = int(float(row["top_phenotype"]))
        analysis_set = row.get("analysis_set", "Full analytic cohort")
        analysis_set = "Ever-preg." if analysis_set.startswith("Ever") else "Full cohort"
        lines.append(
            " & ".join(
                [
                    latex_escape(COMPACT_ENDPOINT_LABELS.get(row["endpoint"], row["endpoint"])),
                    latex_escape(analysis_set),
                    f"P{top_phenotype}",
                    f"{comma_int(row['top_events'])}/{comma_int(row['top_n'])}",
                    pct(row["top_weighted_prevalence"], 1),
                    pr_ci_text(row),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_endpoint_ci_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    endpoint_order = [
        "adverse_pregnancy_history_proxy",
        "contraceptive_vulnerability",
        "fertility_service_or_loss_help",
        "impaired_fecundity_status",
        "unintended_mistimed_pregnancy_history",
    ]
    rows = sorted(rows, key=lambda r: (endpoint_order.index(r["endpoint"]), int(float(r["phenotype"]))))
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Full temporal-validation phenotype-by-endpoint enrichment with bootstrap intervals. Intervals are stratified cluster percentile bootstrap intervals using public-use \texttt{VEST}/\texttt{VECL} design variables with respondent weights retained.}",
        r"\label{tab:endpoint_enrichment_ci}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.19\textwidth") + r"crr" + rp(r"0.20\textwidth") + rp(r"0.21\textwidth") + r"@{}}",
        r"\toprule",
        r"Endpoint & Phenotype & Events & Prev., \% & PR (95\% CI) & RD, \% (95\% CI) \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    latex_escape(COMPACT_ENDPOINT_LABELS.get(row["endpoint"], row["endpoint"])),
                    f"P{int(float(row['phenotype']))}",
                    comma_int(row["events"]),
                    pct(row["weighted_prevalence"], 1),
                    pr_ci_text(row),
                    rd_ci_text(row),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_table_tex() -> str:
    metrics = read_csv(RESULT_TABLES / "cluster_selection_metrics.csv")
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Development-cycle cluster selection metrics across k=2--8.}",
        r"\label{tab:cluster_selection}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular*}{0.86\textwidth}{@{\extracolsep{\fill}}rrrrrrr@{}}",
        r"\toprule",
        r"k & Silhouette & DBI & Min. cluster, \% & Boot. ARI & Boot. n & Selected \\",
        r"\midrule",
    ]
    for row in metrics:
        bootstrap_n = row.get("bootstrap_n", "")
        lines.append(
            " & ".join(
                [
                    comma_int(row["k"]),
                    fnum(row["silhouette"], 3),
                    fnum(row["davies_bouldin"], 3),
                    pct(row["min_cluster_prop"], 1),
                    fnum(row["bootstrap_ari_mean"], 3),
                    latex_escape(bootstrap_n),
                    latex_escape(row["selected"]),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_age_sensitivity_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_age_range_endpoint_enrichment.csv")
    by_key = {(row["analysis"], row["endpoint"], int(float(row["phenotype"]))): row for row in rows}
    primary_rows = [row for row in rows if "15-44" in row["analysis"]]
    selected_rows = []
    for endpoint in ENDPOINT_LABELS:
        sub = [row for row in primary_rows if row["endpoint"] == endpoint]
        if not sub:
            continue
        top = max(sub, key=lambda r: float(r["prevalence_ratio"]))
        phenotype = int(float(top["phenotype"]))
        expanded = by_key.get(("2022-2023 age 15-49", endpoint, phenotype))
        selected_rows.append((endpoint, phenotype, top, expanded))
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Age-range sensitivity analysis in the 2022--2023 temporal-validation cycle. The phenotype with the highest 15--44 prevalence ratio for each endpoint is shown, then re-evaluated after including females aged 45--49 years. Phenotype assignment used the primary endpoint-excluded encoder without refitting; full-age assignment labels were aligned to the primary P0/P1/P2 labels by majority overlap in the original 15--44 subset, and reassignment agreement was checked only as a technical reproducibility control.}",
        r"\label{tab:age_sensitivity}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.25\textwidth") + r"crrrr" + rp(r"0.14\textwidth") + r"@{}}",
        r"\toprule",
        r"Endpoint & Phenotype & 15--44 N & 15--44 PR & 15--49 N & 15--49 PR & Direction \\",
        r"\midrule",
    ]
    for endpoint, phenotype, row44, row49 in selected_rows:
        direction = "Same direction" if row49 and float(row49["prevalence_ratio"]) > 1 else "Attenuated/no enrichment"
        lines.append(
            " & ".join(
                [
                    latex_escape(ENDPOINT_LABELS.get(endpoint, endpoint)),
                    f"P{phenotype}",
                    comma_int(row44["n"]),
                    fnum(row44["prevalence_ratio"], 2),
                    comma_int(row49["n"]) if row49 else "",
                    fnum(row49["prevalence_ratio"], 2) if row49 else "",
                    latex_escape(direction),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_adjusted_enrichment_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_adjusted_endpoint_enrichment.csv")
    rows = sorted(rows, key=lambda r: (r["endpoint"], int(float(r["phenotype"]))))
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Covariate-adjusted phenotype endpoint enrichment in 2022--2023. Models are survey-weighted one-vs-rest logistic enrichment models adjusted for age, race/ethnicity, education, poverty, insurance, and parity. Confidence intervals are stratified cluster percentile bootstrap intervals using public-use \texttt{VEST}/\texttt{VECL}. These models are descriptive robustness checks and are not causal models.}",
        r"\label{tab:adjusted_enrichment}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular*}{0.96\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.36\textwidth") + r"crrc@{}}",
        r"\toprule",
        r"Endpoint & Phenotype & Adjusted OR & 95\% CI & Bootstrap n \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    latex_escape(ENDPOINT_LABELS.get(row["endpoint"], row["endpoint"])),
                    f"P{int(float(row['phenotype']))}",
                    fnum(row["adjusted_odds_ratio"], 2),
                    f"{fnum(row['adjusted_or_ci_low'], 2)}--{fnum(row['adjusted_or_ci_high'], 2)}",
                    comma_int(row["bootstrap_n"]),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_method_comparison_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_baseline_phenotype_method_comparison.csv")
    by_method: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_method.setdefault(row["method"], []).append(row)
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Baseline phenotyping method comparison in the 2022--2023 temporal-validation cycle. Mean maximum prevalence ratio is averaged across prespecified endpoints. Minimum cluster proportion and bootstrap ARI are development/test stability summaries; a high prevalence ratio from a very small cluster should not be interpreted as a stronger method.}",
        r"\label{tab:baseline_methods}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.32\textwidth") + r"rrrr@{}}",
        r"\toprule",
        r"Method & Mean max PR & Boot. ARI & Min. cluster, \% & Endpoints \\",
        r"\midrule",
    ]
    for method in sorted(by_method):
        vals = by_method[method]
        mean_pr = sum(float(row["max_prevalence_ratio"]) for row in vals) / len(vals)
        mean_ari = sum(float(row["bootstrap_ari_mean"]) for row in vals) / len(vals)
        min_cluster = sum(float(row["min_cluster_proportion"]) for row in vals) / len(vals)
        lines.append(
            " & ".join(
                [
                    latex_escape(method),
                    fnum(mean_pr, 2),
                    fnum(mean_ari, 3),
                    pct(min_cluster, 1),
                    comma_int(len(vals)),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_leakage_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_leakage_sensitivity.csv")
    grouped: dict[tuple[str, str], float] = {}
    for row in rows:
        key = (row["endpoint"], row["encoder"])
        grouped[key] = max(grouped.get(key, float("-inf")), float(row["prevalence_ratio"]))
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Endpoint-excluded versus full-domain encoder sensitivity. Values show the maximum phenotype prevalence ratio for each endpoint in 2022--2023. The primary endpoint-excluded encoder retained endpoint-enrichment patterns despite direct endpoint-variable exclusion.}",
        r"\label{tab:leakage_sensitivity}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular*}{0.90\textwidth}{@{\extracolsep{\fill}}lrr@{}}",
        r"\toprule",
        r"Endpoint & Endpoint-excluded & Full-domain \\",
        r"\midrule",
    ]
    for endpoint in ENDPOINT_LABELS:
        lines.append(
            " & ".join(
                [
                    latex_escape(ENDPOINT_LABELS.get(endpoint, endpoint)),
                    fnum(grouped.get((endpoint, "endpoint-excluded"), float("nan")), 2),
                    fnum(grouped.get((endpoint, "full-domain"), float("nan")), 2),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_subgroup_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_subgroup_endpoint_enrichment.csv")
    subgroup_type_labels = {
        "age_group": "Age",
        "insurance": "Insurance",
        "parity_group": "Parity",
        "poverty_group": "Poverty",
        "race_ethnicity": "Race/ethnicity",
    }
    eligible = [
        row
        for row in rows
        if int(float(row["n"])) >= 50 and float(row["baseline_weighted_prevalence"]) > 0
    ]
    top = sorted(eligible, key=lambda r: float(r["prevalence_ratio"]), reverse=True)[:12]
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Subgroup robustness summary. The table lists the highest subgroup-level phenotype endpoint enrichments with at least 50 respondents in the phenotype-subgroup cell. Full subgroup results are provided in source-data tables.}",
        r"\label{tab:subgroup_robustness}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.25\textwidth") + rp(r"0.26\textwidth") + r"crrr@{}}",
        r"\toprule",
        r"Subgroup & Endpoint & Phenotype & N & Events & PR \\",
        r"\midrule",
    ]
    for row in top:
        subgroup_type = row["subgroup_type"]
        subgroup_label = subgroup_type_labels.get(subgroup_type, subgroup_type.replace("_", " "))
        subgroup_value = subgroup_value_label(subgroup_type, row["subgroup"])
        lines.append(
            " & ".join(
                [
                    latex_escape(f"{subgroup_label}: {subgroup_value}"),
                    latex_escape(COMPACT_ENDPOINT_LABELS.get(row["endpoint"], row["endpoint"])),
                    f"P{int(float(row['phenotype']))}",
                    comma_int(row["n"]),
                    comma_int(row["events"]),
                    fnum(row["prevalence_ratio"], 2),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_ever_pregnant_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_ever_pregnant_endpoint_enrichment.csv")
    rows = sorted(rows, key=lambda r: (r["endpoint"], int(float(r["phenotype"]))))
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Ever-pregnant stratum analysis for pregnancy-history endpoints in the 2022--2023 temporal-validation cycle. This analysis restricts to respondents with at least one pregnancy record in the public-use pregnancy file to reduce mechanical enrichment from pregnancy exposure itself. Intervals are stratified cluster bootstrap percentile intervals using public-use \texttt{VEST}/\texttt{VECL}.}",
        r"\label{tab:ever_pregnant}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.20\textwidth") + r"crr" + rp(r"0.20\textwidth") + rp(r"0.21\textwidth") + r"@{}}",
        r"\toprule",
        r"Endpoint & Phenotype & Events/N & Prev., \% & PR (95\% CI) & RD, \% (95\% CI) \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    latex_escape(COMPACT_ENDPOINT_LABELS.get(row["endpoint"], row["endpoint"])),
                    f"P{int(float(row['phenotype']))}",
                    f"{comma_int(row['events'])}/{comma_int(row['n'])}",
                    pct(row["weighted_prevalence"], 1),
                    pr_ci_text(row),
                    rd_ci_text(row),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_trivial_baseline_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_trivial_baseline_summary.csv")
    endpoint_order = list(ENDPOINT_LABELS)
    analyses = sorted({row["analysis_set"] for row in rows}, key=lambda x: (0 if x.startswith("full") else 1, x))

    def get_row(analysis: str, endpoint: str, method: str) -> dict[str, str] | None:
        for row in rows:
            if row["analysis_set"] == analysis and row["endpoint"] == endpoint and row["method"] == method:
                return row
        return None

    def pr_group(row: dict[str, str] | None) -> str:
        if row is None:
            return "--"
        return f"{fnum(row['top_prevalence_ratio'], 2)} ({latex_escape(row['top_group'])})"

    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Reviewer-requested simple stratification baselines for phenotype endpoint enrichment. Age-by-parity and age-by-ever-pregnant strata were compared with the SSL phenotype to test whether endpoint enrichment was largely recoverable from simple reproductive-exposure strata. These are descriptive enrichment summaries, not causal adjustments.}",
        r"\label{tab:trivial_baseline}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.11\textwidth") + rp(r"0.20\textwidth") + rp(r"0.15\textwidth") + rp(r"0.24\textwidth") + rp(r"0.22\textwidth") + r"@{}}",
        r"\toprule",
        r"Analysis & Endpoint & SSL phenotype & Age x parity & Age x ever-pregnant \\",
        r"\midrule",
    ]
    for analysis in analyses:
        endpoints = sorted(
            {row["endpoint"] for row in rows if row["analysis_set"] == analysis},
            key=lambda e: endpoint_order.index(e) if e in endpoint_order else 99,
        )
        for endpoint in endpoints:
            ssl = get_row(analysis, endpoint, "SSL phenotype")
            age_parity = get_row(analysis, endpoint, "Age x parity strata")
            age_ever = get_row(analysis, endpoint, "Age x ever-pregnant strata")
            lines.append(
                " & ".join(
                    [
                        latex_escape(analysis_short(analysis)),
                        latex_escape(COMPACT_ENDPOINT_LABELS.get(endpoint, endpoint)),
                        pr_group(ssl),
                        pr_group(age_parity),
                        pr_group(age_ever),
                    ]
                )
                + r" \\"
            )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_raw_feature_comparison_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_supervised_raw_feature_comparison.csv")
    feature_order = [
        "Age + parity + ever-pregnant",
        "Raw 48 encoder inputs",
        "SSL embedding",
        "Raw 48 + SSL",
        "Phenotype only",
        "SSL + phenotype",
    ]
    feature_headers = {
        "Age + parity + ever-pregnant": "Age/parity",
        "Raw 48 encoder inputs": "Raw 48",
        "SSL embedding": "SSL",
        "Raw 48 + SSL": "Raw+SSL",
        "Phenotype only": "Pheno.",
        "SSL + phenotype": "SSL+ph.",
    }
    rows = [row for row in rows if row["feature_set"] in set(feature_order)]
    endpoint_order = list(ENDPOINT_LABELS)
    grouped: dict[tuple[str, str], dict[str, dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["analysis_set"], row["endpoint"]), {})[row["feature_set"]] = row

    def row_sort_key(item: tuple[tuple[str, str], dict[str, dict[str, str]]]) -> tuple[int, int]:
        (analysis, endpoint), _ = item
        analysis_rank = 0 if analysis.startswith("ever") else 1
        endpoint_rank = endpoint_order.index(endpoint) if endpoint in endpoint_order else 99
        return (analysis_rank, endpoint_rank)

    def metric_value(row: dict[str, str] | None, metric: str, digits: int = 3) -> str:
        if row is None:
            return "--"
        return fnum(row[metric], digits)

    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{Reviewer-requested supervised comparison of simple reproductive-exposure variables, raw primary encoder inputs, SSL embeddings, and combined feature sets. Models were L2-regularized logistic models trained on 2011--2019 and evaluated once in 2022--2023. The upper matrix reports AUPRC, the lower matrix reports AUROC. These unweighted discrimination summaries test representation utility and are not clinical prediction models. Full AUPRC-enrichment and delta values are provided in the source-data tables.}",
        r"\label{tab:raw_feature_supervised}",
        r"\tiny",
        r"\setlength{\tabcolsep}{1.5pt}",
        r"\textit{AUPRC matrix.}\\[-2pt]",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.10\textwidth") + rp(r"0.15\textwidth") + r"rrrcccccc@{}}",
        r"\toprule",
        "Analysis & Endpoint & Train ev. & Test ev. & Base, \\% & "
        + " & ".join(latex_escape(feature_headers[feature]) for feature in feature_order)
        + r" \\",
        r"\midrule",
    ]
    sorted_groups = sorted(grouped.items(), key=row_sort_key)
    for (analysis, endpoint), by_feature in sorted_groups:
        anchor = by_feature.get("Age + parity + ever-pregnant") or next(iter(by_feature.values()))
        lines.append(
            " & ".join(
                [
                    latex_escape(analysis_short(analysis)),
                    latex_escape(COMPACT_ENDPOINT_LABELS.get(endpoint, endpoint)),
                    comma_int(anchor["train_events"]),
                    comma_int(anchor["test_events"]),
                    pct(anchor["baseline_prevalence"], 1),
                    *[metric_value(by_feature.get(feature), "auprc", 3) for feature in feature_order],
                ]
            )
            + r" \\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular*}",
        r"\vspace{0.45em}",
        r"\textit{AUROC matrix.}\\[-2pt]",
        r"\begin{tabular*}{0.92\textwidth}{@{\extracolsep{\fill}}" + rp(r"0.14\textwidth") + rp(r"0.18\textwidth") + r"cccccc@{}}",
        r"\toprule",
        "Analysis & Endpoint & "
        + " & ".join(latex_escape(feature_headers[feature]) for feature in feature_order)
        + r" \\",
        r"\midrule",
    ]
    for (analysis, endpoint), by_feature in sorted_groups:
        lines.append(
            " & ".join(
                [
                    latex_escape(analysis_short(analysis)),
                    latex_escape(COMPACT_ENDPOINT_LABELS.get(endpoint, endpoint)),
                    *[metric_value(by_feature.get(feature), "auroc", 2) for feature in feature_order],
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def supplementary_seed_sensitivity_table_tex() -> str:
    rows = read_csv(RESULT_TABLES / "supplementary_encoder_seed_sensitivity.csv")
    lines = [
        r"\begin{table}[tbp]",
        r"\centering",
        r"\caption{SSL encoder initialization sensitivity. The primary development-selected k=3 solution was held fixed and a complete 30-epoch alternative initialization was compared with the primary seed. This analysis tests whether the learned representation and transferred phenotype assignment are sensitive to encoder initialization; it is not a repeated full model-selection study.}",
        r"\label{tab:seed_sensitivity}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}rrrrrrrr@{}}",
        r"\toprule",
        r"Seed & Epochs & k & Masked MSE & Silhouette & DBI & Test ARI & Adverse PR \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    comma_int(row["seed"]),
                    comma_int(row["epochs"]),
                    comma_int(row["fixed_k"]),
                    fnum(row["final_masked_mse"], 3),
                    fnum(row["dev_silhouette"], 3),
                    fnum(row["dev_davies_bouldin"], 2),
                    fnum(row["test_ari_vs_primary"], 2),
                    fnum(row["ever_pregnant_adverse_max_pr"], 2),
                ]
            )
            + r" \\"
        )
    lines += [r"\bottomrule", r"\end{tabular*}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def copy_assets() -> None:
    LATEX.mkdir(parents=True, exist_ok=True)
    LATEX_TABLES.mkdir(parents=True, exist_ok=True)
    LATEX_FIGURES.mkdir(parents=True, exist_ok=True)
    SOURCE_DATA.mkdir(parents=True, exist_ok=True)
    for template_file in SPRINGER_TEMPLATE_FILES:
        src = SPRINGER_TEMPLATE / template_file
        if not src.exists():
            raise FileNotFoundError(f"Springer Nature template file not found: {src}")
        shutil.copy2(src, LATEX / template_file)
    for stem in [
        "figure1_workflow",
        "figure2_matrix_missingness",
        "figure3_embedding_phenotypes",
        "figure4_phenotype_profiles",
        "figure5_risk_enrichment",
        "figure6_model_diagnostics",
        "figure7_ssl_diagnostics",
        "supplementary_robustness_age_adjusted",
        "supplementary_method_leakage_sensitivity",
        "supplementary_subgroup_robustness",
    ]:
        for ext in [".pdf", ".png"]:
            src = RESULT_FIGURES / f"{stem}{ext}"
            if src.exists():
                shutil.copy2(src, LATEX_FIGURES / src.name)
    user_figure_sources = {
        "FIG1.png": "FIG1_editable_vector.png",
        "FIG2.png": "FIG2.png",
        "FIG3.png": "FIG3.png",
        "FIG4.png": "FIG4.png",
        "FIG5.png": "FIG5.png",
        "FIG9.png": "FIG9.png",
        "FIG10.png": "FIG10.png",
    }
    for output_name, source_name in user_figure_sources.items():
        src = FINAL_USER_FIGURES / source_name
        if not src.exists():
            raise FileNotFoundError(f"Final user-approved figure not found: {src}")
        shutil.copy2(src, LATEX_FIGURES / output_name)
    for src in sorted((ROOT / "manuscript" / "tables").glob("*.csv")) + sorted(RESULT_TABLES.glob("*.csv")):
        shutil.copy2(src, SOURCE_DATA / src.name)


def build_main_tex() -> str:
    table1 = read_csv(MANUSCRIPT_TABLES / "table1_cohort_characteristics.csv")
    table4 = read_csv(MANUSCRIPT_TABLES / "table4_endpoint_enrichment_model_metrics.csv")
    matrix_summary = read_csv(RESULT_TABLES / "harmonized_matrix_summary.csv")
    feature_audit = read_csv(RESULT_TABLES / "ssl_feature_audit.csv")
    cluster = read_csv(RESULT_TABLES / "cluster_selection_metrics.csv")
    p0 = read_csv(MANUSCRIPT_TABLES / "table3_phenotype_profiles.csv")
    analysis_summary = json.loads((RESULT_TABLES / "analysis_summary.json").read_text(encoding="utf-8"))
    ssl_config = json.loads((RESULT_TABLES / "ssl_config.json").read_text(encoding="utf-8"))
    row_by_var = {row["variable"]: row for row in p0}
    selected = next(row for row in cluster if row["selected"].lower() == "true")
    top_by_endpoint = {row["endpoint"]: row for row in table4}
    ci_rows = read_csv(RESULT_TABLES / "endpoint_enrichment_by_phenotype_test.csv")
    ci_by_key = {(row["endpoint"], int(float(row["phenotype"]))): row for row in ci_rows}
    top_ci = {endpoint: row for endpoint, row in top_by_endpoint.items()}
    n_total = sum(int(float(row["n_respondents"])) for row in table1)
    n_train = int(float(next(row for row in table1 if row["analysis_split"] == "Training/pretraining")["n_respondents"]))
    n_dev = int(float(next(row for row in table1 if row["analysis_split"] == "Development/model selection")["n_respondents"]))
    n_test = int(float(next(row for row in table1 if row["analysis_split"] == "Temporal validation")["n_respondents"]))
    n_matrix_features = int(float(matrix_summary[0]["features"]))
    n_encoder_features = sum(
        row.get("used_in_primary_encoder", "").strip().lower() == "true" for row in feature_audit
    )
    embedding_dim = int(analysis_summary["embedding_dim"])
    ssl_epochs = int(ssl_config.get("epochs", 30))
    ssl_mask_rate = float(ssl_config.get("mask_rate", 0.15))
    ssl_d_model = int(ssl_config.get("d_model", 32))
    ssl_n_heads = int(ssl_config.get("n_heads", 4))
    ssl_n_layers = int(ssl_config.get("n_layers", 1))
    ssl_dropout = float(ssl_config.get("dropout", 0.10))
    ssl_batch_size = int(ssl_config.get("batch_size", 1024))
    ssl_lr = float(ssl_config.get("lr", 0.001))
    ssl_seed = int(ssl_config.get("seed", 20260602))
    k_min = int(ssl_config.get("k_min", 2))
    k_max = int(ssl_config.get("k_max", 8))
    cluster_bootstrap_repeats = int(ssl_config.get("cluster_bootstrap_repeats", 60))
    p0_age = float(phenotype_value(row_by_var["age_analysis"], 0))
    p0_parity = float(phenotype_value(row_by_var["parity"], 0))
    p0_preg = float(phenotype_value(row_by_var["has_pregnancy_record"], 0)) * 100
    p1_age = float(phenotype_value(row_by_var["age_analysis"], 1))
    p1_parity = float(phenotype_value(row_by_var["parity"], 1))
    p1_preg = float(phenotype_value(row_by_var["has_pregnancy_record"], 1)) * 100
    p1_contra = float(phenotype_value(row_by_var["contraceptive_vulnerability"], 1)) * 100
    p2_age = float(phenotype_value(row_by_var["age_analysis"], 2))
    p2_parity = float(phenotype_value(row_by_var["parity"], 2))
    p2_preg = float(phenotype_value(row_by_var["has_pregnancy_record"], 2)) * 100
    p2_adverse = float(phenotype_value(row_by_var["adverse_pregnancy_history_proxy"], 2)) * 100
    p2_mistimed = float(phenotype_value(row_by_var["unintended_mistimed_pregnancy_history"], 2)) * 100
    p2_fecund = float(phenotype_value(row_by_var["impaired_fecundity_status"], 2)) * 100
    pr_adverse = float(top_by_endpoint["adverse_pregnancy_history_proxy"]["top_prevalence_ratio"])
    pr_mistimed = float(top_by_endpoint["unintended_mistimed_pregnancy_history"]["top_prevalence_ratio"])
    pr_fert = float(top_by_endpoint["fertility_service_or_loss_help"]["top_prevalence_ratio"])
    pr_imp = float(top_by_endpoint["impaired_fecundity_status"]["top_prevalence_ratio"])
    pr_contra = float(top_by_endpoint["contraceptive_vulnerability"]["top_prevalence_ratio"])
    pr_adverse_ci = pr_ci_text(top_ci["adverse_pregnancy_history_proxy"])
    pr_mistimed_ci = pr_ci_text(top_ci["unintended_mistimed_pregnancy_history"])
    pr_fert_ci = pr_ci_text(top_ci["fertility_service_or_loss_help"])
    pr_imp_ci = pr_ci_text(top_ci["impaired_fecundity_status"])
    pr_contra_ci = pr_ci_text(top_ci["contraceptive_vulnerability"])
    pr_adverse_abs = pr_ci_sentence(top_ci["adverse_pregnancy_history_proxy"])
    pr_mistimed_abs = pr_ci_sentence(top_ci["unintended_mistimed_pregnancy_history"])
    pr_fert_abs = pr_ci_sentence(top_ci["fertility_service_or_loss_help"])
    pr_imp_abs = pr_ci_sentence(top_ci["impaired_fecundity_status"])
    pr_contra_abs = pr_ci_sentence(top_ci["contraceptive_vulnerability"])
    full_adverse_p2 = ci_by_key[("adverse_pregnancy_history_proxy", 2)]
    full_mistimed_p2 = ci_by_key[("unintended_mistimed_pregnancy_history", 2)]
    pr_adverse_full_abs = pr_ci_sentence(full_adverse_p2)
    pr_mistimed_full_abs = pr_ci_sentence(full_mistimed_p2)
    age_sensitivity = read_csv(RESULT_TABLES / "supplementary_age_range_endpoint_enrichment.csv")
    age_qc = read_csv(RESULT_TABLES / "supplementary_age_range_assignment_qc.csv")[0]
    adjusted_rows = read_csv(RESULT_TABLES / "supplementary_adjusted_endpoint_enrichment.csv")
    method_rows = read_csv(RESULT_TABLES / "supplementary_baseline_phenotype_method_comparison.csv")
    leakage_rows = read_csv(RESULT_TABLES / "supplementary_leakage_sensitivity.csv")
    trivial_rows = read_csv(RESULT_TABLES / "supplementary_trivial_baseline_summary.csv")
    raw_feature_rows = read_csv(RESULT_TABLES / "supplementary_supervised_raw_feature_comparison.csv")
    seed_sensitivity_rows = read_csv(RESULT_TABLES / "supplementary_encoder_seed_sensitivity.csv")

    def age_top_pr(endpoint: str, analysis_label: str) -> tuple[int, float]:
        primary = [row for row in age_sensitivity if row["endpoint"] == endpoint and "15-44" in row["analysis"]]
        top = max(primary, key=lambda r: float(r["prevalence_ratio"]))
        phenotype = int(float(top["phenotype"]))
        selected_rows = [
            row
            for row in age_sensitivity
            if row["endpoint"] == endpoint
            and int(float(row["phenotype"])) == phenotype
            and analysis_label in row["analysis"]
        ]
        row = selected_rows[0]
        return phenotype, float(row["prevalence_ratio"])

    def adjusted_row(endpoint: str, phenotype: int) -> dict[str, str]:
        return next(
            row
            for row in adjusted_rows
            if row["endpoint"] == endpoint and int(float(row["phenotype"])) == phenotype
        )

    def method_metric(method: str, column: str) -> float:
        rows = [row for row in method_rows if row["method"] == method]
        return sum(float(row[column]) for row in rows) / len(rows)

    def leakage_max(endpoint: str, encoder: str) -> float:
        vals = [
            float(row["prevalence_ratio"])
            for row in leakage_rows
            if row["endpoint"] == endpoint and row["encoder"] == encoder
        ]
        return max(vals) if vals else float("nan")

    def trivial_row(analysis_set: str, endpoint: str, method: str) -> dict[str, str]:
        return next(
            row
            for row in trivial_rows
            if row["analysis_set"] == analysis_set and row["endpoint"] == endpoint and row["method"] == method
        )

    def raw_metric(analysis_set: str, endpoint: str, feature_set: str, column: str) -> float:
        row = next(
            row
            for row in raw_feature_rows
            if row["analysis_set"] == analysis_set
            and row["endpoint"] == endpoint
            and row["feature_set"] == feature_set
        )
        return float(row[column])

    def count_ssl_above_raw(analysis_set: str) -> tuple[int, int]:
        endpoints = sorted({row["endpoint"] for row in raw_feature_rows if row["analysis_set"] == analysis_set})
        total = 0
        better = 0
        for endpoint in endpoints:
            try:
                raw = raw_metric(analysis_set, endpoint, "Raw 48 encoder inputs", "auprc")
                ssl = raw_metric(analysis_set, endpoint, "SSL embedding", "auprc")
            except StopIteration:
                continue
            total += 1
            better += int(ssl > raw)
        return better, total

    _, age_adverse_44 = age_top_pr("adverse_pregnancy_history_proxy", "15-44")
    _, age_adverse_49 = age_top_pr("adverse_pregnancy_history_proxy", "15-49")
    _, age_mistimed_44 = age_top_pr("unintended_mistimed_pregnancy_history", "15-44")
    _, age_mistimed_49 = age_top_pr("unintended_mistimed_pregnancy_history", "15-49")
    age_assignment_ari = float(age_qc["adjusted_rand_index_vs_primary_assignment"])
    adj_adverse_p2 = adjusted_row("adverse_pregnancy_history_proxy", 2)
    adj_contra_p1 = adjusted_row("contraceptive_vulnerability", 1)
    adj_fert_p1 = adjusted_row("fertility_service_or_loss_help", 1)
    adj_mistimed_p1 = adjusted_row("unintended_mistimed_pregnancy_history", 1)
    adj_fecund_p2 = adjusted_row("impaired_fecundity_status", 2)
    ssl_method_ari = method_metric("SSL embedding + k-means", "bootstrap_ari_mean")
    ssl_method_min_cluster = method_metric("SSL embedding + k-means", "min_cluster_proportion")
    raw_method_min_cluster = method_metric("Raw matrix PCA + k-means", "min_cluster_proportion")
    lca_method_ari = method_metric("Selected-variable Bernoulli LCA", "bootstrap_ari_mean")
    leak_adverse_primary = leakage_max("adverse_pregnancy_history_proxy", "endpoint-excluded")
    leak_adverse_full = leakage_max("adverse_pregnancy_history_proxy", "full-domain")
    ever_rows = read_csv(RESULT_TABLES / "supplementary_ever_pregnant_endpoint_enrichment.csv")
    ever_by_key = {(row["endpoint"], int(float(row["phenotype"]))): row for row in ever_rows}
    ever_adverse_p2 = ever_by_key[("adverse_pregnancy_history_proxy", 2)]
    ever_mistimed_p2 = ever_by_key[("unintended_mistimed_pregnancy_history", 2)]
    trivial_adverse_ageparity = trivial_row(
        "ever-pregnant stratum", "adverse_pregnancy_history_proxy", "Age x parity strata"
    )
    trivial_mistimed_ageparity = trivial_row(
        "ever-pregnant stratum", "unintended_mistimed_pregnancy_history", "Age x parity strata"
    )
    trivial_adverse_full_ageparity = trivial_row(
        "full analytic cohort", "adverse_pregnancy_history_proxy", "Age x parity strata"
    )
    ssl_better_full, ssl_total_full = count_ssl_above_raw("full analytic cohort")
    ssl_better_ever, ssl_total_ever = count_ssl_above_raw("ever-pregnant stratum")
    raw48_contra_auprc = raw_metric("full analytic cohort", "contraceptive_vulnerability", "Raw 48 encoder inputs", "auprc")
    ssl_contra_auprc = raw_metric("full analytic cohort", "contraceptive_vulnerability", "SSL embedding", "auprc")
    raw48_adverse_ever_auprc = raw_metric("ever-pregnant stratum", "adverse_pregnancy_history_proxy", "Raw 48 encoder inputs", "auprc")
    ssl_adverse_ever_auprc = raw_metric("ever-pregnant stratum", "adverse_pregnancy_history_proxy", "SSL embedding", "auprc")
    seed_primary = next(row for row in seed_sensitivity_rows if int(float(row["seed"])) == ssl_seed)
    seed_alt = next(row for row in seed_sensitivity_rows if int(float(row["seed"])) != ssl_seed)
    bootstrap_design = read_csv(RESULT_TABLES / "endpoint_enrichment_bootstrap_design_summary.csv")[0]
    n_boot_strata = int(float(bootstrap_design["n_strata"]))
    n_boot_pairs = int(float(bootstrap_design["n_strata_cluster_pairs"]))
    authors_tex = author_affiliation_tex()
    author_contributions = author_contributions_tex()

    return rf"""\documentclass[referee,pdflatex,sn-basic,Numbered]{{sn-jnl}}
\usepackage{{graphicx}}
\usepackage{{amsmath}}
\usepackage{{booktabs}}
\usepackage{{array}}
\makeatletter
\newenvironment{{landscape}}{{%
\clearpage
\begingroup
\pdfpagewidth=297mm
\pdfpageheight=210mm
\setlength{{\textwidth}}{{267mm}}
\setlength{{\textheight}}{{180mm}}
\setlength{{\columnwidth}}{{\textwidth}}
\setlength{{\linewidth}}{{\textwidth}}
\hsize=\textwidth
\vsize=\textheight
\@colroom=\textheight
}}{{%
\clearpage
\endgroup
\pdfpagewidth=210mm
\pdfpageheight=297mm
}}
\makeatother
\raggedbottom
\emergencystretch=2em

\begin{{document}}

\title[Reproductive life-course phenotyping in the NSFG]{{Reproductive life-course phenotyping in the National Survey of Family Growth: a self-supervised temporal survey study}}
{authors_tex}

\abstract{{
\textbf{{Background:}} Reproductive health across adolescence and adulthood is shaped by pregnancy history, contraceptive behavior, partnership context, fertility care, fecundity limitation or infertility, insurance, and socioeconomic conditions. Public National Survey of Family Growth (NSFG) analyses often focus on single domains, leaving multivariable reproductive life-course heterogeneity less directly characterized.

\textbf{{Methods:}} We harmonized public-use NSFG female respondent and female pregnancy files from 2011--2013, 2013--2015, 2015--2017, 2017--2019, and 2022--2023. The primary analysis included females aged 15--44 years. Female pregnancy files were aggregated to respondent-level histories and linked by CaseID. A leakage-controlled masked tabular self-supervised learning (SSL) encoder was trained for {ssl_epochs} epochs on 2011--2017 records, phenotype selection was performed in 2017--2019, and 2022--2023 was reserved for within-NSFG temporal validation rather than validation in a separate health-system dataset. Endpoint-enrichment intervals used a stratified cluster bootstrap based on public-use \texttt{{VEST}}/\texttt{{VECL}} design variables.

\textbf{{Results:}} The harmonized matrix included {n_total:,} respondents and {n_matrix_features} cross-cycle columns before feature selection. The training/pretraining, development, and temporal-validation splits included {n_train:,}, {n_dev:,}, and {n_test:,} respondents, respectively. The primary encoder used {n_encoder_features} endpoint-excluded features and generated {embedding_dim}-dimensional respondent embeddings. Development-cycle clustering selected three phenotypes (silhouette {float(selected['silhouette']):.3f}; Davies--Bouldin {float(selected['davies_bouldin']):.3f}; bootstrap adjusted Rand index {float(selected['bootstrap_ari_mean']):.3f}). In 2022--2023, P0 represented younger low-pregnancy-exposure respondents, P1 represented the main pregnancy-exposed phenotype, and P2 was a small high-burden pregnancy-history phenotype. Within respondents with at least one pregnancy record in the public-use pregnancy file, P2 showed the highest enrichment for adverse pregnancy-history proxy (prevalence ratio [PR] {pr_adverse_abs}; {int(float(top_by_endpoint['adverse_pregnancy_history_proxy']['top_events']))}/{int(float(top_by_endpoint['adverse_pregnancy_history_proxy']['top_n']))} events) and mistimed or unwanted pregnancy history (PR {pr_mistimed_abs}; {int(float(top_by_endpoint['unintended_mistimed_pregnancy_history']['top_events']))}/{int(float(top_by_endpoint['unintended_mistimed_pregnancy_history']['top_n']))} events). Full-cohort estimates were larger (adverse proxy PR {pr_adverse_full_abs}; mistimed/unwanted PR {pr_mistimed_full_abs}), and age-by-parity strata also enriched adverse pregnancy-history proxy in the ever-pregnant stratum (PR {fnum(trivial_adverse_ageparity['top_prevalence_ratio'], 2)}), confirming partial mechanical enrichment from pregnancy exposure. In reviewer-requested supervised comparisons, SSL embeddings had higher AUPRC than raw 48 encoder inputs in {ssl_better_full}/{ssl_total_full} full-cohort endpoints and {ssl_better_ever}/{ssl_total_ever} ever-pregnant pregnancy-history endpoints. Adjusted models supported P2 enrichment for adverse pregnancy-history proxy (adjusted OR {fnum(adj_adverse_p2['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_adverse_p2['adjusted_or_ci_low'], 2)}--{fnum(adj_adverse_p2['adjusted_or_ci_high'], 2)}) and P1 enrichment for contraceptive vulnerability (adjusted OR {fnum(adj_contra_p1['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_contra_p1['adjusted_or_ci_low'], 2)}--{fnum(adj_contra_p1['adjusted_or_ci_high'], 2)}), whereas fecundity limitation/infertility in P2 was not robust after adjustment.

\textbf{{Conclusions:}} A public-use survey phenotyping workflow using masked tabular SSL can summarize NSFG respondent and pregnancy files into interpretable reproductive life-course profiles. The results support representation learning, phenotype discovery, and endpoint enrichment as reproducible tools for population reproductive-health surveys, while showing that pregnancy-history enrichment must be interpreted against simple age/parity and ever-pregnant baselines. The study does not establish clinical diagnosis, individual treatment guidance, or causal mechanisms.
}}

\keywords{{National Survey of Family Growth, reproductive health, self-supervised learning, life-course phenotyping, contraception, fertility}}

\maketitle

\section{{Introduction}}

Reproductive health is rarely determined by a single exposure. Contraceptive use, pregnancy timing, pregnancy outcomes, partnership history, fertility services, fecundity limitation or infertility, health insurance, and socioeconomic conditions can co-occur across the reproductive life course. National studies have separately characterized unintended pregnancy, contraceptive failure or non-use, infertility, and fertility-service use using NSFG and related reproductive-health surveillance data \cite{{finer_zolna_unintended,contraceptive_failure,infertility_impaired,infertility_service,contraceptive_nonuse}}. Analyses that isolate one domain are valuable for surveillance, but they may understate heterogeneity among respondents whose reproductive histories and social conditions jointly shape reproductive-health needs.

The National Survey of Family Growth (NSFG) is a nationally representative United States survey that gathers information on fertility, contraception, pregnancy and births, marriage and cohabitation, infertility, and reproductive health. The public-use female respondent and female pregnancy files can be joined by CaseID, enabling respondent-level summaries of pregnancy histories while preserving a reproducible public-data workflow \cite{{cdc_nsfg_puf,cdc_nsfg_combined}}. Recent NCHS reports using the 2022--2023 NSFG have described current contraceptive status, fertility-service use, and birth expectations \cite{{cdc_db539,cdc_db542,cdc_db560}}. These reports provide essential national estimates, but they are not designed to learn multivariable reproductive life-course phenotypes across respondent and pregnancy records.

Self-supervised learning for tabular data offers a practical approach for learning representations from sparse, heterogeneous survey variables without using a single supervised label during representation training. Prior tabular SSL and transformer methods, including VIME, TabTransformer, SAINT, and SCARF, support the use of masking, contextual feature embeddings, and corruption-based pretraining for tabular representation learning \cite{{vime,tabtransformer,saint,scarf}}. Drawing on these ideas, we implemented a compact masked-reconstruction encoder for the public-use NSFG setting with explicit temporal splitting and endpoint leakage control; contrastive, row-attention, and large-scale foundation-model variants were not implemented.

This study aimed to construct a respondent-level reproductive life-course matrix from public NSFG files, train a masked tabular SSL encoder using earlier cycles, identify interpretable reproductive phenotypes in a development cycle, and evaluate phenotype-associated enrichment of prespecified reproductive-health endpoints in the temporally held-out 2022--2023 release.

\section{{Methods}}

\subsection{{Data sources and study population}}

We used public-use NSFG female respondent and female pregnancy files from 2011--2013, 2013--2015, 2015--2017, 2017--2019, and 2022--2023. Fixed-width 2011--2019 files were parsed with official CDC Stata dictionaries. The 2022--2023 public-use CSV files and user guide were obtained from the CDC/NCHS NSFG public-use data page. The primary analysis was restricted to females aged 15--44 years to preserve comparability between 2011--2019 and 2022--2023 public-use releases. The 2022--2023 NSFG release used a redesigned continuous, multimode protocol with an online component; therefore, the held-out cycle should be interpreted as a within-NSFG temporal and survey-mode stress test rather than a pure calendar-time validation. Cohort characteristics by temporal split are shown in Table 1.

\input{{tables/table1.tex}}

\subsection{{Temporal split and leakage control}}

The 2011--2013, 2013--2015, and 2015--2017 cycles were used for SSL pretraining. The 2017--2019 cycle was used for phenotype model selection and development-cycle diagnostics. The 2022--2023 cycle was reserved for within-NSFG temporal validation, and its endpoint labels were used only for final evaluation. This design evaluates temporal transport within a public-use survey series, not validation in a separate health-system cohort or registry. Survey weights were retained for descriptive prevalence and phenotype profiles, but were not used as model inputs because the encoder was intended to learn a reusable respondent-level representation from harmonized public-use variables rather than estimate design-weighted national parameters during optimization. For the primary encoder, variables directly defining the validation endpoints were excluded before feature selection to reduce endpoint leakage. Figure 1 summarizes the temporal split, leakage-controlled matrix construction, masked tabular SSL encoder, phenotype discovery, and validation workflow.

\begin{{figure}}[htbp]
\centering
\includegraphics[width=\textwidth]{{figures/FIG1.png}}
\caption{{Study design and leakage-controlled analysis workflow. Public-use NSFG female respondent and female pregnancy files were harmonized across cycles. Earlier cycles were used for masked SSL pretraining, 2017--2019 for phenotype selection, and 2022--2023 for within-NSFG temporal and survey-mode stress testing. Endpoint-direct variables were excluded from the primary encoder input.}}
\label{{fig:workflow}}
\end{{figure}}

\subsection{{Respondent-level life-course matrix}}

Female pregnancy records were aggregated to respondent level using pregnancy counts, live-birth and pregnancy-outcome counts, pregnancy-intention summaries, low-birthweight or stillbirth proxies, and prenatal-care or smoking indicators where public-use variables were available. These summaries were joined to female respondent variables by CaseID. Candidate input domains included demographics and social factors, partnership and marriage, reproductive timing, sexual and contraceptive history, pregnancy-history summaries, fertility and reproductive-health indicators, insurance and poverty, and missingness or skip-pattern indicators. Table 2 lists the primary input domains, endpoint definitions, and leakage-control rules used before SSL fitting.

\input{{tables/table2.tex}}

\subsection{{Masked tabular SSL encoder}}

The primary model used a masked tabular SSL encoder implemented for numeric-coded public-use survey variables. Feature values were median-imputed and standardized using training-cycle parameters, and missingness indicators were supplied as token inputs. During training, {ssl_mask_rate * 100:.0f}\% of observed values were masked and the model minimized masked reconstruction mean squared error. The compact encoder used {ssl_n_layers} transformer encoder layer, hidden dimension {ssl_d_model}, {ssl_n_heads} attention heads, dropout {ssl_dropout:.2f}, batch size {ssl_batch_size}, AdamW optimization with learning rate {ssl_lr:g}, and {ssl_epochs} training epochs. The final analysis artifacts used {n_encoder_features} endpoint-excluded input features and {embedding_dim}-dimensional respondent embeddings. This model was designed as a compact public-survey representation learner, not as a large foundation model.

All preprocessing and representation steps were fitted within their designated temporal splits. Training-cycle records were used to estimate imputation medians, standardization parameters, feature-completeness and variance screens, SSL encoder parameters, and principal-component loadings. Development-cycle embeddings were used to select k and fix k-means centroids. The 2022--2023 endpoint labels were not used for feature screening, imputation, scaling, PCA fitting, centroid fitting, SSL model selection, or phenotype naming. Endpoint-defining variable patterns and the primary encoder feature-audit file are provided in Table 2 and the source-data directory.

\subsection{{Phenotype discovery and validation}}

Respondent embeddings were projected to principal components fitted on training-cycle embeddings. The number of phenotypes was selected in 2017--2019 by comparing k={k_min}--{k_max} using silhouette score, Davies--Bouldin index, minimum cluster proportion, and {cluster_bootstrap_repeats} bootstrap adjusted Rand index (ARI) resamples. Development-cycle centroids were then fixed, and 2022--2023 respondents were assigned to the nearest centroid. Phenotype descriptions were based on survey-weighted profile characteristics, not on outcome enrichment alone.

Five validation endpoints were prespecified: contraceptive vulnerability, fertility-service or pregnancy-loss help, mistimed or unwanted pregnancy history, adverse pregnancy-history proxy, and fecundity limitation/infertility. The contraceptive-vulnerability endpoint was defined from the NSFG current contraceptive-status recode and interpreted as a current contraceptive at-risk status proxy within the analytic respondent population rather than an incident pregnancy outcome. The fecundity endpoint used \texttt{{FECUND}} codes for noncontraceptive surgical sterility, nonsurgical sterility, subfecundity, or long interval plus \texttt{{INFERT}} codes indicating infertility, and excluded contraceptive sterilization. Pregnancy-history endpoints used respondent-level pregnancy-file summaries and were interpreted as self-reported survey-history proxies rather than clinically adjudicated pregnancy outcomes. Because pregnancy exposure itself can mechanically affect pregnancy-history endpoint rates, the ever-pregnant stratum restricted to respondents with at least one pregnancy record in the public-use pregnancy file was used as the primary interpretive enrichment analysis for the two pregnancy-history endpoints; full-cohort estimates were retained as supporting exposure-structured summaries. Endpoint enrichment was summarized using survey-weighted one-vs-rest prevalence ratios and risk differences, following complex-survey analysis principles for descriptive population summaries \cite{{lumley_survey}}. In these one-vs-rest contrasts, each phenotype is compared with its complement, so estimates for the majority phenotype can be pulled toward the null by construction. AUPRC enrichment was defined as AUPRC divided by the endpoint baseline prevalence. Uncertainty intervals for endpoint enrichment were estimated with a stratified cluster percentile bootstrap using public-use \texttt{{VEST}} strata and \texttt{{VECL}} cluster variables, retaining the public-use respondent weights in each resample; the 2022--2023 primary bootstrap used {n_boot_strata} strata, {n_boot_pairs} stratum-cluster pairs, and 2000 resamples. Intervals were treated as descriptive because no multiplicity adjustment was applied across endpoints, phenotypes, and robustness families.

Secondary supervised endpoint-enrichment models compared simple reproductive-exposure variables (age, parity, and ever-pregnant status), raw primary encoder inputs, SSL embeddings, raw inputs plus SSL embeddings, phenotype-only inputs, and SSL-plus-phenotype inputs using L2-regularized logistic regression. Raw-feature and simple-exposure baselines were included because neural-network representations do not automatically outperform strong non-deep or direct tabular baselines \cite{{tabular_tree}}. Models were trained on 2011--2019 records, features were standardized within the training data, class weights were balanced, and 2022--2023 labels were used only for final evaluation. AUPRC, AUPRC enrichment over baseline prevalence, and AUROC were reported as unweighted model-performance summaries, whereas phenotype prevalence profiles and endpoint-enrichment estimates used survey weights. These supervised summaries were used to assess representation utility against raw-feature and trivial reproductive-exposure baselines; they were not interpreted as bedside diagnostic models, individual prognostic models, treatment-decision tools, or calibrated absolute-risk tools.

\subsection{{Robustness and sensitivity analyses}}

Seven robustness analyses were added after the primary workflow was fixed. First, because the 2022--2023 NSFG release includes females aged 15--49 years whereas earlier public-use cycles were restricted to ages 15--44 years, we transferred the trained endpoint-excluded encoder to the full 2022--2023 age range and compared endpoint enrichment in ages 15--44 versus 15--49 years without refitting the encoder, PCA, or development-cycle centroids. Second, we fitted survey-weighted one-vs-rest logistic enrichment models for each endpoint and phenotype, adjusting for age, race/ethnicity, education, poverty, insurance, and parity; confidence intervals used a stratified cluster bootstrap with \texttt{{VEST}}/\texttt{{VECL}}. These adjusted models were descriptive enrichment checks rather than causal models. Third, we compared SSL phenotyping with raw matrix PCA plus k-means, MCA-style one-hot SVD plus k-means, and selected-variable Bernoulli latent class analysis, interpreting stability and cluster degeneracy alongside endpoint enrichment. Fourth, we trained a full-domain SSL sensitivity encoder that did not exclude endpoint-direct variables and compared enrichment with the primary endpoint-excluded encoder. Fifth, subgroup robustness was summarized across age group, race/ethnicity, poverty, insurance, and parity strata. Sixth, we constructed simple age-by-parity and age-by-ever-pregnant strata to test whether pregnancy-history endpoint enrichment was recoverable from trivial reproductive-exposure groupings. Seventh, we performed a fixed-k encoder initialization sensitivity analysis by comparing the primary seed with one complete 30-epoch alternative seed while keeping the development-selected k=3 structure; this was treated as a sensitivity check rather than a repeated model-selection experiment.

Reporting was guided by STROBE for observational studies and by TRIPOD+AI items where they were relevant to transparent reporting of machine-learning model development and evaluation \cite{{strobe,tripod_ai}}. The present study is not a clinical prediction-model development study, so TRIPOD+AI was used as a reporting and transparency reference rather than as a claim that the workflow produces a deployable clinical prediction model.

\section{{Results}}

\subsection{{Cohort and harmonized matrix}}

The harmonized analysis included {n_total:,} respondents across five public-use cycles. Table 1 summarizes cohort characteristics by temporal split. The temporal-validation cohort included {n_test:,} respondents from 2022--2023. Female pregnancy records were joined to respondent records by CaseID, and Figure 2A reports the share of respondents with at least one pregnancy record rather than a file-linkage success or failure rate. The word ``linkage'' in the display refers to pregnancy-record history coverage after CaseID-based file joining, not to failed linkage among eligible respondent records. The harmonized matrix contained {n_matrix_features} columns before primary feature selection. Figure 2 shows cohort magnitude, pregnancy-record history coverage, input domains, missingness, feature-selection flow, and endpoint prevalence.

\begin{{figure}}[htbp]
\centering
\includegraphics[width=\textwidth]{{figures/FIG2.png}}
\caption{{Harmonized cohort structure, leakage-controlled inputs, feature selection, and endpoint prevalence. (A) Female respondent counts and pregnancy-record history coverage, defined as the number and percentage of respondents with at least one record in the public-use pregnancy file after CaseID-based joining; this is not a pregnancy-file linkage-failure rate. (B) Primary SSL input-domain counts and skip-pattern missingness by cycle. (C) Feature-selection flow separating primary encoder inputs, retained candidate features, and excluded or sparse variables. (D) Weighted endpoint prevalence across cycles with temporal-test change relative to 2011--2013.}}
\label{{fig:matrix}}
\end{{figure}}

\subsection{{SSL phenotype discovery}}

The embedding, phenotype sizes, profile drivers, and k-selection evidence are shown in Figure 3; the numerical cluster-selection metrics are given in Supplementary Table 1, and the SSL training diagnostics are shown in Supplementary Figure S5. The masked reconstruction loss declined across {ssl_epochs} SSL training epochs, supporting optimization of the compact encoder while remaining a training diagnostic rather than an outcome-validation metric. In the development cycle, k=3 had the highest silhouette score ({float(selected['silhouette']):.3f}) and high bootstrap ARI ({float(selected['bootstrap_ari_mean']):.3f}) among candidate cluster counts. The k=3 solution was retained over the more balanced k=2 alternative because it isolated an interpretable high-burden pregnancy-history profile while preserving high bootstrap stability. The smallest development-cycle cluster comprised {float(selected['min_cluster_prop']) * 100:.1f}\% of respondents, below the preferred 5\% threshold; therefore, k=3 was treated as a development-selected, bootstrap-stable, small-cluster solution rather than evidence of a universal reproductive taxonomy.

\begin{{figure}}[htbp]
\centering
\includegraphics[width=0.95\textwidth]{{figures/FIG3.png}}
\caption{{SSL embedding and phenotype discovery. (A) PCA visualization of 2022--2023 SSL embeddings colored by transferred phenotype, with phenotype ellipses, marginal PC density, leading embedding loadings, and a scree summary. (B) Phenotype size and leading profile drivers. (C) Development-cycle k-selection evidence, including the multi-metric heatmap, silhouette width, and bootstrap adjusted Rand index across candidate cluster numbers.}}
\label{{fig:phenotypes}}
\end{{figure}}

\subsection{{Temporal-validation phenotype profiles}}

The survey-weighted phenotype profile patterns are displayed in Figure 4. Table 3 provides the corresponding weighted profile estimates.

In 2022--2023, P0 represented younger low-pregnancy-exposure respondents, with weighted mean age {p0_age:.1f} years, parity {p0_parity:.2f}, and {p0_preg:.1f}\% having at least one pregnancy record. P1 represented the main pregnancy-exposed phenotype, with weighted mean age {p1_age:.1f} years, parity {p1_parity:.2f}, {p1_preg:.1f}\% having at least one pregnancy record, and the highest contraceptive vulnerability prevalence ({p1_contra:.1f}\%). P2 was a small high-burden pregnancy-history phenotype, with weighted mean age {p2_age:.1f} years, parity {p2_parity:.2f}, {p2_preg:.1f}\% having at least one pregnancy record, adverse pregnancy-history proxy prevalence {p2_adverse:.1f}\%, mistimed or unwanted pregnancy-history prevalence {p2_mistimed:.1f}\%, and fecundity limitation/infertility prevalence {p2_fecund:.1f}\%.

\input{{tables/table3.tex}}

\begin{{figure}}[htbp]
\centering
\includegraphics[width=0.92\textwidth]{{figures/FIG4.png}}
\caption{{Survey-weighted phenotype profiles in 2022--2023. Heatmap cells show standardized deviations across phenotypes for selected reproductive life-course descriptors and endpoint-related characteristics; cell labels show weighted raw means or prevalences. The top annotation bar summarizes a relative profile-burden score derived from pregnancy-record count and adverse pregnancy-history proxy; the left annotation bar groups rows into sociodemographic, pregnancy-history, and endpoint-related descriptor families.}}
\label{{fig:profiles}}
\end{{figure}}

\subsection{{Endpoint enrichment and secondary supervised validation}}

Bootstrap source estimates for endpoint enrichment and uncertainty intervals are provided in Supplementary Table 2. Pregnancy-history endpoint enrichment was interpreted primarily within respondents with at least one pregnancy record in the public-use pregnancy file, because full-cohort contrasts are partly driven by the low-pregnancy-exposure P0 phenotype. In this ever-pregnant stratum, P2 was enriched for adverse pregnancy-history proxy (48/229 events; PR {fnum(ever_adverse_p2['prevalence_ratio'], 2)}, 95\% CI {fnum(ever_adverse_p2['prevalence_ratio_ci_low'], 2)}--{fnum(ever_adverse_p2['prevalence_ratio_ci_high'], 2)}) and mistimed or unwanted pregnancy history (181/229 events; PR {fnum(ever_mistimed_p2['prevalence_ratio'], 2)}, 95\% CI {fnum(ever_mistimed_p2['prevalence_ratio_ci_low'], 2)}--{fnum(ever_mistimed_p2['prevalence_ratio_ci_high'], 2)}). Full-cohort estimates were larger for the same endpoints (adverse pregnancy-history proxy PR {pr_adverse_full_abs}; mistimed or unwanted pregnancy history PR {pr_mistimed_full_abs}), consistent with mechanical enrichment from pregnancy exposure and therefore treated as supporting rather than primary evidence.

For endpoints not structurally restricted to pregnancy records, full-cohort enrichment was summarized in the 2022--2023 analytic cohort. P2 was enriched for fertility-service or pregnancy-loss help (44/242 events; PR {pr_fert_abs}) and fecundity limitation/infertility (94/242 events; PR {pr_imp_abs}). P1 showed the highest enrichment for contraceptive vulnerability, interpreted here as a current contraceptive at-risk status proxy (238/2224 events; PR {pr_contra_abs}), consistent with its larger pregnancy-exposed profile and higher current contraceptive vulnerability prevalence.

Secondary supervised summaries showed that SSL embeddings carried endpoint-enrichment information beyond raw-feature and simple reproductive-exposure baselines in this temporal split. SSL embeddings had higher AUPRC than the raw 48 primary encoder inputs for {ssl_better_full}/{ssl_total_full} full-cohort endpoints and {ssl_better_ever}/{ssl_total_ever} ever-pregnant pregnancy-history endpoints. For example, contraceptive-vulnerability AUPRC increased from {fnum(raw48_contra_auprc, 3)} with raw 48 inputs to {fnum(ssl_contra_auprc, 3)} with SSL embeddings, and ever-pregnant adverse pregnancy-history proxy AUPRC increased from {fnum(raw48_adverse_ever_auprc, 3)} to {fnum(ssl_adverse_ever_auprc, 3)}. Because indirect survey proxies can still exist after direct endpoint-variable exclusion, these supervised differences were interpreted as representation-utility evidence within the temporal split rather than proof of leakage-free clinical prediction. Adding phenotype labels to SSL embeddings did not consistently improve AUPRC, so phenotype labels were interpreted as compressed profile summaries rather than necessary supervised predictors. AUPRC enrichment values are ratios of AUPRC to baseline endpoint prevalence; they summarize endpoint-ranking enrichment rather than clinical diagnostic performance. Figure 5 and Table 4 summarize phenotype endpoint enrichment. Supplementary Figure S4 summarizes secondary model diagnostics, including AUROC validation and feature-set AUPRC comparison, and Supplementary Table 10 provides the full raw-feature versus SSL AUPRC/AUROC comparison. These results support the utility of learned survey representations for endpoint enrichment in this split, but they should not be interpreted as clinical diagnostic accuracy or universal superiority over all supervised modeling strategies.

\input{{tables/table4.tex}}

\begin{{figure}}[htbp]
\centering
\includegraphics[width=\textwidth]{{figures/FIG5.png}}
\caption{{Endpoint enrichment and secondary supervised endpoint-enrichment summaries. (A) Full analytic-cohort survey-weighted prevalence ratios by phenotype in the 2022--2023 within-NSFG temporal-validation cohort with stratified cluster bootstrap confidence intervals; pregnancy-history endpoints are interpreted primarily using the ever-pregnant estimates in Table 4 and Supplementary Table 8. The dashed vertical line indicates no enrichment. (B) AUPRC enrichment over baseline prevalence for phenotype-only, SSL-embedding, and SSL-plus-phenotype summaries.}}
\label{{fig:enrichment}}
\end{{figure}}

\subsection{{Robustness and sensitivity analyses}}

Age-range sensitivity analyses preserved the main enrichment direction after including 45--49-year-old respondents from the 2022--2023 public-use release. Reassignment quality for the 15--44 subset was checked only as a technical reproducibility control (ARI {age_assignment_ari:.2f}) and was not treated as independent robustness evidence. The highest phenotype PR for adverse pregnancy-history proxy attenuated from {age_adverse_44:.2f} in ages 15--44 to {age_adverse_49:.2f} in ages 15--49, and the highest PR for mistimed or unwanted pregnancy history changed from {age_mistimed_44:.2f} to {age_mistimed_49:.2f}; all prespecified endpoints retained the same enrichment direction in the expanded age range. Because 45--49-year-old respondents were assigned by a model developed in ages 15--44, this analysis was interpreted as a sensitivity stress test rather than a fully validated expanded-age model. Supplementary Table 3 and Supplementary Figure S1 report the age-range sensitivity analysis.

The adjusted enrichment models are reported in Supplementary Table 4. Covariate-adjusted enrichment models showed that some, but not all, unadjusted phenotype enrichments persisted after accounting for age, race/ethnicity, education, poverty, insurance, and parity. P2 remained enriched for adverse pregnancy-history proxy after adjustment (adjusted OR {fnum(adj_adverse_p2['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_adverse_p2['adjusted_or_ci_low'], 2)}--{fnum(adj_adverse_p2['adjusted_or_ci_high'], 2)}). P1 remained enriched for contraceptive vulnerability (adjusted OR {fnum(adj_contra_p1['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_contra_p1['adjusted_or_ci_low'], 2)}--{fnum(adj_contra_p1['adjusted_or_ci_high'], 2)}), fertility-service or pregnancy-loss help (adjusted OR {fnum(adj_fert_p1['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_fert_p1['adjusted_or_ci_low'], 2)}--{fnum(adj_fert_p1['adjusted_or_ci_high'], 2)}), and mistimed or unwanted pregnancy history (adjusted OR {fnum(adj_mistimed_p1['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_mistimed_p1['adjusted_or_ci_low'], 2)}--{fnum(adj_mistimed_p1['adjusted_or_ci_high'], 2)}). The large P1 adjusted OR for mistimed or unwanted pregnancy history and the near-null or protective estimates for P0 should be read as exposure-structure signals from pregnancy-record definability, not as independent phenotype effects. By contrast, the unadjusted P2 fecundity limitation/infertility enrichment was not robust after adjustment (adjusted OR {fnum(adj_fecund_p2['adjusted_odds_ratio'], 2)}, 95\% CI {fnum(adj_fecund_p2['adjusted_or_ci_low'], 2)}--{fnum(adj_fecund_p2['adjusted_or_ci_high'], 2)}). These adjusted models reconcile the unadjusted PRs with covariate-conditioned descriptive associations and do not imply causal phenotype effects.

Baseline-method, leakage, subgroup, ever-pregnant, simple-strata, raw-feature supervised, and seed-sensitivity outputs are reported in Supplementary Table 5 through Supplementary Table 11; the corresponding method-sensitivity and subgroup displays are reported in Supplementary Figures S2 and S3. Specifically, leakage sensitivity is reported in Supplementary Table 6, subgroup robustness in Supplementary Table 7, the ever-pregnant stratum in Supplementary Table 8, and simple age/parity baselines in Supplementary Table 9. Baseline method comparisons supported the stability, rather than universal enrichment superiority, of the SSL phenotype representation. SSL embedding plus k-means had development bootstrap ARI {ssl_method_ari:.3f} and a minimum temporal-validation cluster proportion of {ssl_method_min_cluster * 100:.1f}\%. This supplementary baseline clusters the SSL embedding directly; the primary phenotype-selection workflow first projects embeddings to principal components and therefore has the development bootstrap ARI reported in Figure 3 and Supplementary Table 1. Raw matrix PCA plus k-means produced a much smaller minimum cluster proportion ({raw_method_min_cluster * 100:.1f}\%), indicating that some high enrichment values from raw PCA reflected unstable tiny clusters. Selected-variable Bernoulli LCA had development bootstrap ARI {lca_method_ari:.3f} but lower average endpoint-enrichment summaries than SSL. In leakage sensitivity, the full-domain encoder did not uniformly exceed the endpoint-excluded encoder; for adverse pregnancy-history proxy, the maximum PR was {leak_adverse_primary:.2f} for the primary endpoint-excluded encoder versus {leak_adverse_full:.2f} for the full-domain encoder.

The reviewer-requested simple stratification baseline confirmed that pregnancy-history endpoint enrichment was partly recoverable from age and pregnancy exposure alone. In the ever-pregnant stratum, the top age-by-parity group had PR {fnum(trivial_adverse_ageparity['top_prevalence_ratio'], 2)} for adverse pregnancy-history proxy, compared with P2 PR {fnum(ever_adverse_p2['prevalence_ratio'], 2)}; for mistimed or unwanted pregnancy history, the corresponding PRs were {fnum(trivial_mistimed_ageparity['top_prevalence_ratio'], 2)} and {fnum(ever_mistimed_p2['prevalence_ratio'], 2)}. Full-cohort age-by-parity enrichment for adverse pregnancy-history proxy was also high (PR {fnum(trivial_adverse_full_ageparity['top_prevalence_ratio'], 2)}), reinforcing that full-cohort pregnancy-history results should not be read as independent phenotype effects. Fixed-k encoder initialization sensitivity showed that an alternative 30-epoch seed had lower agreement with the primary temporal-validation assignment (ARI {fnum(seed_alt['test_ari_vs_primary'], 2)}) but retained ever-pregnant adverse pregnancy-history enrichment above null (maximum PR {fnum(seed_alt['ever_pregnant_adverse_max_pr'], 2)}). Subgroup summaries showed enrichment patterns across demographic and reproductive-history strata, but extreme subgroup values were treated as unstable when they arose from small event counts.

\section{{Discussion}}

This temporal survey analysis shows that masked tabular SSL can summarize NSFG female respondent and pregnancy files into interpretable reproductive life-course profiles. The main contribution is not a new single-endpoint risk score or clinical prediction model, but a reproducible workflow for learning survey-based respondent representations, translating them into profile-based phenotypes, and auditing whether endpoint enrichment survives simple exposure-structure baselines. This framing is intended for population reproductive-health surveillance and public-health hypothesis generation, not for clinical triage or individual counseling.

The three-phenotype solution separated a younger low-pregnancy-exposure group, a main pregnancy-exposed group, and a small higher-burden pregnancy-history group. This structure is consistent with the descriptive reproductive-health logic that survey-measured reproductive needs emerge from combinations of age, pregnancy history, partnership and contraceptive context, fertility services, and fecundity status rather than from any single endpoint variable. The phenotype interpretation remained profile-based, avoiding naming clusters solely by their validation endpoints.

For reproductive-health surveillance, the practical use case is cohort-level stratification rather than individual risk prediction. Public-health analysts could use similar profiles to monitor whether contraceptive vulnerability, fertility-service needs, fecundity limitation, or adverse pregnancy-history proxies concentrate within stable life-course strata across survey cycles, demographic groups, or policy-relevant access categories. The profiles can also help prioritize descriptive subgroup audits and generate hypotheses for more detailed clinical or registry studies. They should not be used to assign individual diagnoses, guide bedside management, or replace domain-specific NSFG surveillance reports.

The strongest full-cohort unadjusted enrichment occurred for pregnancy-history endpoints in the small P2 phenotype. Because pregnancy-record availability, parity, and pregnancy-history summaries are themselves part of the life-course structure, these findings can be partly exposure-driven. The reviewer-requested age-by-parity and age-by-ever-pregnant baselines confirmed this concern: simple strata reproduced a substantial portion of pregnancy-history enrichment, especially in the full analytic cohort. For this reason, the ever-pregnant stratum was used as the primary interpretive analysis for pregnancy-history endpoints: it reduced mechanical enrichment from pregnancy exposure and showed that adverse pregnancy-history enrichment persisted but attenuated. Adjusted models further showed that some unadjusted signals, especially fecundity limitation/infertility in P2, were not robust after age, sociodemographic, insurance, and parity adjustment. These patterns support descriptive phenotype enrichment rather than causal inference or independent clinical prediction.

The raw-feature supervised comparison provides a complementary view of representation utility. SSL embeddings outperformed the raw 48 primary inputs in the prespecified L2-logistic AUPRC summaries in this temporal split, including the ever-pregnant pregnancy-history analyses. However, the supervised gains should be interpreted cautiously because the models were not calibrated clinical risk tools, the endpoints are public-use survey constructs, and the embedding did not make phenotype labels consistently additive. The practical value of the SSL layer is therefore compression, harmonized cross-domain representation, and sensitivity-audited endpoint enrichment rather than a claim that deep learning is necessary for every NSFG endpoint.

The study differs from prior NSFG reports and analyses that focus on specific domains such as contraceptive status, fertility services, birth expectations, adolescent pregnancy intention classes, IUD use across life stages, or contraceptive non-use \cite{{cdc_db539,cdc_db542,cdc_db560,adolescent_lca,iud_lifecourse,contraceptive_nonuse}}. Those analyses remain essential for domain-specific surveillance and policy; our analysis adds a multivariable representation-learning layer that can summarize cross-domain reproductive life-course heterogeneity in public-use survey data.

Several limitations are important. First, NSFG public-use data are self-reported and do not contain hospital-verified clinical outcomes. Endpoint definitions therefore rely on public-use survey recodes and should be interpreted as reproductive-health proxies. Second, validation was temporal within the NSFG public-use survey series rather than external validation in an independent survey, hospital EHR, or registry. The 2022--2023 release also used a redesigned continuous, multimode protocol with an online component, so differences between 2017--2019 and 2022--2023 may reflect both temporal change and survey-mode or instrument change. Third, the higher-burden P2 phenotype was small in the development and temporal-validation cohorts; this supports interpretability but limits precision, especially for subgroup estimates with few events. Fourth, endpoint leakage was reduced by direct-variable exclusion and was examined with a full-domain sensitivity encoder, but public-use survey variables are correlated, and pregnancy counts, parity, and pregnancy-history summaries can serve as indirect proxies for pregnancy-history endpoints. The ever-pregnant stratum and simple-strata baselines address but do not eliminate this concern. Fifth, adjusted enrichment and subgroup analyses reduce concern that phenotypes merely restate age or parity gradients, but they remain descriptive robustness checks and do not identify causal mechanisms. Sixth, the SSL objective and cluster-selection procedure did not optimize a design-based survey likelihood; survey design variables and weights were used for descriptive profiles and enrichment intervals rather than for representation learning itself. Seventh, fixed-k seed sensitivity suggested that transferred phenotype assignments were moderately initialization-sensitive, even though endpoint enrichment direction persisted for adverse pregnancy-history proxy; therefore, the exact cluster boundaries require independent replication. Finally, the compact encoder was designed for reproducible CPU-feasible public-data analysis and should not be framed as a large foundation model.

\section{{Conclusions}}

A leakage-controlled masked tabular SSL workflow identified interpretable reproductive life-course profiles in public-use NSFG data and demonstrated descriptive within-NSFG endpoint enrichment for multiple reproductive-health survey endpoints. Reviewer-requested simple-strata and raw-feature comparisons showed both the value and limits of the representation: SSL embeddings improved secondary AUPRC summaries relative to raw 48 inputs in this split, but pregnancy-history phenotype enrichment remained partly recoverable from age and pregnancy-exposure strata. The approach provides a reproducible framework for population-level reproductive-health phenotyping, while future work should pursue independent survey or registry replication, survey-design-aware uncertainty intervals, broader seed-sensitivity testing, and cautious applied interpretation.

\backmatter

\section*{{Declarations}}

\bmhead{{Availability of data and materials}}

The raw data analyzed in this study are publicly available from CDC/NCHS NSFG public-use data portals, including the 2022--2023 public-use files and 2011--2019 public-use releases. Raw individual-level public-use records are not redistributed in this manuscript package. Processed source-data tables used for figures and manuscript tables are included in the \texttt{{source\_data}} directory. Public-use data access URLs and parsing notes are documented in the project README and processing scripts.

\bmhead{{Code availability}}

Analysis scripts, split definitions, source-data tables, model metadata, and figure assets are included in the submitted reproducibility package. Raw NSFG individual-level public-use records are not redistributed; the scripts point to CDC/NCHS public-use data portals and document the processing workflow. Project code is released under the MIT License, and citation metadata are provided in \texttt{{CITATION.cff}}. The submitted package includes the feature-audit files needed to identify primary encoder inputs, candidate retained variables, excluded sparse variables, and endpoint-direct exclusion rules.

\bmhead{{Ethics approval and consent to participate}}

This study used de-identified public-use NSFG data released by CDC/NCHS. No new human-subject data were collected, and the analysis involved no direct participant contact or identifiable private information; therefore, separate informed consent and institutional review board approval were not required for this secondary public-use analysis.

\bmhead{{Consent for publication}}

Not applicable.

\bmhead{{Competing interests}}

The authors declare no competing interests.

\bmhead{{Funding}}

No external funding was received for this study.

\bmhead{{Authors' contributions}}

{author_contributions}

\bmhead{{Supplementary information}}
Supplementary tables and figures are provided in the separate file \texttt{{supplementary\_information.pdf}}.

\begin{{thebibliography}}{{99}}
\bibitem{{finer_zolna_unintended}} Finer LB, Zolna MR. Declines in unintended pregnancy in the United States, 2008--2011. N Engl J Med. 2016;374(9):843--852. doi:10.1056/NEJMsa1506575.
\bibitem{{contraceptive_failure}} Sundaram A, Vaughan B, Kost K, Bankole A, Finer L, Singh S, Trussell J. Contraceptive failure in the United States: estimates from the 2006--2010 National Survey of Family Growth. Perspect Sex Reprod Health. 2017;49(1):7--16. doi:10.1363/psrh.12017.
\bibitem{{infertility_impaired}} Chandra A, Copen CE, Stephen EH. Infertility and impaired fecundity in the United States, 1982--2010: data from the National Survey of Family Growth. Natl Health Stat Report. 2013;(67):1--18.
\bibitem{{infertility_service}} Chandra A, Copen CE, Stephen EH. Infertility service use in the United States: data from the National Survey of Family Growth, 1982--2010. Natl Health Stat Report. 2014;(73):1--21.
\bibitem{{contraceptive_nonuse}} Frederiksen BN, Ahrens K. Understanding the extent of contraceptive non-use among women at risk of unintended pregnancy, National Survey of Family Growth 2011--2017. Contraception: X. 2020;2:100033. doi:10.1016/j.conx.2020.100033.
\bibitem{{cdc_nsfg_puf}} National Center for Health Statistics. National Survey of Family Growth: 2022--2023 public-use data files, codebooks, and documentation. https://www.cdc.gov/nchs/nsfg/nsfg-2022-2023-puf.htm.
\bibitem{{cdc_nsfg_combined}} National Center for Health Statistics. 2011--2019 combined files: selected data and documentation. \url{{https://www.cdc.gov/nchs/nsfg/nsfg_2011_2019_combined_files.htm}}.
\bibitem{{cdc_db539}} National Center for Health Statistics. Current contraceptive status among females ages 15--49: United States, 2022--2023. NCHS Data Brief No. 539. 2025. https://www.cdc.gov/nchs/products/databriefs/db539.htm.
\bibitem{{cdc_db542}} National Center for Health Statistics. Use of fertility services in the United States, 2022--2023. NCHS Data Brief No. 542. 2025. https://www.cdc.gov/nchs/products/databriefs/db542.htm.
\bibitem{{cdc_db560}} Martinez GM. Birth expectations of women ages 20--49: United States, 2022--2023. NCHS Data Brief No. 560. 2026. https://www.cdc.gov/nchs/products/databriefs/db560.htm.
\bibitem{{vime}} Yoon J, Zhang Y, Jordon J, van der Schaar M. VIME: extending the success of self- and semi-supervised learning to tabular domain. Advances in Neural Information Processing Systems. 2020;33:11033--11043.
\bibitem{{tabtransformer}} Huang X, Khetan A, Cvitkovic M, Karnin Z. TabTransformer: tabular data modeling using contextual embeddings. arXiv:2012.06678. 2020. https://arxiv.org/abs/2012.06678.
\bibitem{{saint}} Somepalli G, Goldblum M, Schwarzschild A, Bruss CB, Goldstein T. SAINT: improved neural networks for tabular data via row attention and contrastive pre-training. arXiv:2106.01342. 2021. https://arxiv.org/abs/2106.01342.
\bibitem{{scarf}} Bahri D, Jiang H, Tay Y, Metzler D. SCARF: self-supervised contrastive learning using random feature corruption. arXiv:2106.15147. 2021. https://arxiv.org/abs/2106.15147.
\bibitem{{tabular_tree}} Grinsztajn L, Oyallon E, Varoquaux G. Why do tree-based models still outperform deep learning on tabular data? Advances in Neural Information Processing Systems. 2022;35:507--520.
\bibitem{{lumley_survey}} Lumley T. Analysis of complex survey samples. J Stat Softw. 2004;9(8):1--19. doi:10.18637/jss.v009.i08.
\bibitem{{strobe}} von Elm E, Altman DG, Egger M, Pocock SJ, Gotzsche PC, Vandenbroucke JP; STROBE Initiative. The Strengthening the Reporting of Observational Studies in Epidemiology (STROBE) Statement: guidelines for reporting observational studies. PLoS Med. 2007;4(10):e296. doi:10.1371/journal.pmed.0040296.
\bibitem{{tripod_ai}} Collins GS, Moons KGM, Dhiman P, Riley RD, Beam AL, Van Calster B, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. doi:10.1136/bmj-2023-078378.
\bibitem{{adolescent_lca}} Offiong A, Powell TW, Dangerfield DT, Gemmill A, Marcell AV. A latent class analysis: identifying pregnancy intention classes among U.S. adolescents. J Adolesc Health. 2022;71(4):466--473. doi:10.1016/j.jadohealth.2022.04.019.
\bibitem{{iud_lifecourse}} Kramer RD, Higgins JA, Godecker AL, Ehrenthal DB. Reconsidering (in)equality in the use of IUDs in the United States: a closer look across the reproductive life course. Demographic Research. 2020;43:1049--1066. doi:10.4054/DemRes.2020.43.35.
\end{{thebibliography}}

\end{{document}}
"""


def build_supplementary_tex() -> str:
    return r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{array}
\usepackage{hyperref}
\usepackage{caption}
\usepackage{float}
\raggedbottom
\emergencystretch=2em
\renewcommand{\tablename}{Supplementary Table}
\renewcommand{\figurename}{Supplementary Figure}
\renewcommand{\thetable}{S\arabic{table}}
\renewcommand{\thefigure}{S\arabic{figure}}
\renewcommand{\theHtable}{S\arabic{table}}
\renewcommand{\theHfigure}{S\arabic{figure}}

\begin{document}

\begin{center}
{\Large\bfseries Supplementary information}\\[0.75em]
{\large Reproductive life-course phenotyping in the National Survey of Family Growth: a self-supervised temporal survey study}\\[0.75em]
Feifan Lu, Fengshang Yan, Qianqian Yang, Jiuqiong Yan, Rui Guan
\end{center}

\section*{Supplementary tables}

Supplementary Table S1 through Supplementary Table S11 provide numerical source summaries for cluster selection, endpoint enrichment intervals, age-range sensitivity, covariate adjustment, baseline methods, leakage sensitivity, subgroup robustness, the ever-pregnant stratum, simple age/parity baselines, raw-feature versus SSL supervised comparisons, and encoder seed sensitivity.

\input{tables/tableS1_cluster_selection.tex}

\input{tables/tableS2_endpoint_enrichment_ci.tex}

\input{tables/tableS3_age_sensitivity.tex}

\input{tables/tableS4_adjusted_enrichment.tex}

\input{tables/tableS5_baseline_methods.tex}

\input{tables/tableS6_leakage_sensitivity.tex}

\input{tables/tableS7_subgroup_robustness.tex}

\input{tables/tableS8_ever_pregnant.tex}

\input{tables/tableS9_trivial_baseline.tex}

\input{tables/tableS10_raw_feature_supervised.tex}

\input{tables/tableS11_seed_sensitivity.tex}

\clearpage

\section*{Supplementary figures}

Supplementary Figures S1--S3 provide robustness, method-sensitivity, and subgroup displays; Supplementary Figures S4 and S5 provide the secondary supervised validation and SSL diagnostic displays.

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{figures/supplementary_robustness_age_adjusted.pdf}
\caption{Robustness analysis for age-range sensitivity and covariate-adjusted endpoint enrichment. (A) Highest-phenotype prevalence ratios in 2022--2023 ages 15--44 versus 15--49 years. (B) Survey-weighted adjusted odds ratios from one-vs-rest phenotype enrichment models.}
\label{fig:supp_age_adjusted}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{figures/supplementary_method_leakage_sensitivity.pdf}
\caption{Baseline-method and leakage-sensitivity analyses. (A) SSL phenotyping compared with raw PCA, MCA-style one-hot SVD, and selected-variable Bernoulli LCA baselines. (B) Maximum endpoint prevalence ratios for the primary endpoint-excluded encoder and a full-domain sensitivity encoder.}
\label{fig:supp_method_leakage}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth]{figures/supplementary_subgroup_robustness.pdf}
\caption{Subgroup robustness summary across age, race/ethnicity, poverty, insurance, and parity strata. Values summarize mean maximum endpoint prevalence ratios by subgroup; subgroup categories use public-use recodes, and full decoded endpoint-by-phenotype estimates are included in source data and Supplementary Table S7.}
\label{fig:supp_subgroup}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{figures/FIG9.png}
\caption{Secondary supervised validation diagnostics. (A) AUROC validation matrix for phenotype-only, SSL-embedding, and SSL-plus-phenotype summaries across validation endpoints. AUROC is reported as a secondary discrimination summary and is not the primary claim. (B) Feature-set AUPRC comparison for phenotype-only, SSL-embedding, and SSL-plus-phenotype summaries. These diagnostics support representation and enrichment assessment rather than diagnostic prediction.}
\label{fig:model_diagnostics}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{figures/FIG10.png}
\caption{SSL optimization and feature-missingness diagnostics. (A) Masked reconstruction loss across SSL training epochs, with rapid-descent, adjustment, and convergence phases, smoothed trend, and minimum-loss epoch annotation. (B) Distribution of training-cycle missingness among primary encoder features and retained candidate SSL features.}
\label{fig:ssl_diagnostics}
\end{figure}

\end{document}
"""


def main() -> None:
    copy_assets()
    write(LATEX_TABLES / "table1.tex", table1_tex())
    write(LATEX_TABLES / "table2.tex", table2_tex())
    write(LATEX_TABLES / "table3.tex", table3_tex())
    write(LATEX_TABLES / "table4.tex", table4_tex())
    write(LATEX_TABLES / "tableS1_cluster_selection.tex", supplementary_table_layout(supplementary_table_tex()))
    write(LATEX_TABLES / "tableS2_endpoint_enrichment_ci.tex", supplementary_table_layout(supplementary_endpoint_ci_table_tex()))
    write(LATEX_TABLES / "tableS3_age_sensitivity.tex", supplementary_table_layout(supplementary_age_sensitivity_table_tex()))
    write(LATEX_TABLES / "tableS4_adjusted_enrichment.tex", supplementary_table_layout(supplementary_adjusted_enrichment_table_tex()))
    write(LATEX_TABLES / "tableS5_baseline_methods.tex", supplementary_table_layout(supplementary_method_comparison_table_tex()))
    write(LATEX_TABLES / "tableS6_leakage_sensitivity.tex", supplementary_table_layout(supplementary_leakage_table_tex()))
    write(LATEX_TABLES / "tableS7_subgroup_robustness.tex", supplementary_table_layout(supplementary_subgroup_table_tex()))
    write(LATEX_TABLES / "tableS8_ever_pregnant.tex", supplementary_table_layout(supplementary_ever_pregnant_table_tex()))
    write(LATEX_TABLES / "tableS9_trivial_baseline.tex", supplementary_table_layout(supplementary_trivial_baseline_table_tex()))
    write(LATEX_TABLES / "tableS10_raw_feature_supervised.tex", supplementary_table_layout(supplementary_raw_feature_comparison_table_tex()))
    write(LATEX_TABLES / "tableS11_seed_sensitivity.tex", supplementary_table_layout(supplementary_seed_sensitivity_table_tex()))
    write(LATEX / "main.tex", build_main_tex())
    write(LATEX / "supplementary_information.tex", build_supplementary_tex())
    manifest = {
        "project": ROOT.name,
        "latex_root": str(LATEX),
        "main_tex": "main.tex",
        "supplementary_tex": "supplementary_information.tex",
        "springer_nature_template_source": str(SPRINGER_TEMPLATE),
        "template_files": SPRINGER_TEMPLATE_FILES,
        "figures": sorted(p.name for p in LATEX_FIGURES.glob("*")),
        "tables": sorted(p.name for p in LATEX_TABLES.glob("*.tex")),
        "source_data_files": len(list(SOURCE_DATA.glob("*.csv"))),
    }
    write(LATEX / "submission_package_manifest.json", json.dumps(manifest, indent=2))
    write(
        LATEX / "README_OVERLEAF.md",
        "Upload all files in this directory to Overleaf. Compile main.tex for the manuscript "
        "and supplementary_information.tex for the separate supplementary-information PDF. "
        "This package uses the official Springer Nature sn-jnl template files copied from "
        f"{SPRINGER_TEMPLATE}. "
        "It includes figure PDFs/PNGs, LaTeX table includes, and source-data CSV files. "
        "Raw NSFG individual-level public-use files are not redistributed.\n",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

