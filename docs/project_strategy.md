# Project Strategy

## Working title

Reproductive life-course phenotyping in the National Survey of Family Growth: a
self-supervised temporal public-use survey study.

## Target journal

Primary target: **Reproductive Health**.

The manuscript should be framed for a reproductive-health audience first:
public-use NSFG survey phenotyping, reproductive life-course heterogeneity, and
endpoint enrichment. Self-supervised learning should be presented as the
technical method that enables the phenotyping workflow, not as the primary
clinical claim.

## Short rationale

NSFG directly covers pregnancy and birth histories, marriage and cohabitation,
infertility, contraception, family life, and reproductive health. The fast route
is therefore not to chase hospital outcomes, but to learn multivariable
life-course phenotypes that summarize reproductive timing, partnership history,
contraceptive exposure, fertility-service use, pregnancy intention, and adverse
pregnancy-history proxies.

## What makes this different from existing NSFG reports

Recent NCHS reports already describe single domains such as current
contraceptive status, family planning services, fertility services, and birth
expectations in 2022-2023. This project should not repeat those descriptive
analyses. The manuscript claim should be:

1. a leakage-controlled harmonized reproductive life-course matrix can be built
   from public NSFG files;
2. masked tabular self-supervised learning can compress hundreds of sparse and
   skip-patterned survey variables into respondent-level representations;
3. the learned representations identify interpretable life-course phenotypes;
4. phenotypes enrich clinically relevant public-health endpoints such as
   fertility-service use, contraceptive nonuse among pregnancy-risk respondents,
   unintended or mistimed pregnancy history, and adverse pregnancy-history
   proxies;
5. survey-weighted descriptive checks and conventional baselines are required so
   the AI contribution is not overstated.

## Main analysis unit

Primary unit: female respondent.

Pregnancy records will be summarized to respondent-level history features before
SSL:

- pregnancy count and live-birth count;
- age at first pregnancy and first live birth if available;
- number and proportion of pregnancies coded as live birth, miscarriage, induced
  abortion, stillbirth, or other outcome;
- recurrent unintended or mistimed pregnancy indicators;
- preterm/low-birthweight proxies among live births when public-use categories
  support them;
- prenatal-care and smoking indicators in recent pregnancies.

## Modeling plan

1. Harmonize respondent-level variables across cycles.
2. Derive pregnancy-history summaries and join them to respondent records.
3. Build domain blocks: demographics, socioeconomic status, partnership,
   reproductive timing, pregnancy history, contraception, fertility services,
   health behavior, and missingness/skip-pattern indicators.
4. Pretrain a masked tabular encoder on training cycles.
5. Select representation size, masking rate, and clustering `k` on a development
   cycle only.
6. Evaluate phenotypes and downstream risk enrichment on a held-out cycle.
7. Compare with PCA, multiple correspondence analysis if implemented, k-means on
   hand-engineered features, logistic regression, and gradient boosting.
8. Use survey-weighted descriptive phenotype profiles as a sensitivity layer.

## Recommended split

Fast paper:

- train/pretrain: 2011-2019 combined cycles;
- development/model selection: random split within 2022-2023 or cycle-aware
  2017-2019 if harmonization is completed first;
- final descriptive validation: held-out 2022-2023 respondents.

Safer paper:

- train/pretrain: 2011-2017;
- development: 2017-2019;
- temporal validation: 2022-2023.

The safer split is better for reviewers, but the fast split may be acceptable if
clearly labeled as internal temporal validation with public-use survey data.

## Candidate endpoints

Primary candidates to evaluate after codebook confirmation:

- ever fertility-service use or medically assisted conception/help to become
  pregnant;
- contraceptive nonuse or less-effective method use among respondents at risk of
  unintended pregnancy;
- any unintended or mistimed pregnancy history;
- recurrent unintended/mistimed pregnancy history;
- adverse pregnancy-history proxy among women with prior live birth, such as
  preterm-category or low-birthweight-category history;
- birth expectation discordance among parous or nulliparous respondents.

Do not make severe clinical-outcome claims. NSFG is a reproductive-health survey,
not an EHR or registry outcome dataset.

## Journal positioning

Primary target:

- Reproductive Health.

Fallback targets:

- BMC Women's Health if a faster, broader women's-health route is needed;
- BMC Medical Informatics and Decision Making only if the method contribution is
  foregrounded and the submission is repositioned for informatics reviewers;
- Contraception or Fertility and Sterility Science only if the clinical endpoint
  is narrowed and the survey design is handled rigorously.

Avoid claiming a Nature Communications-level AI result from this dataset alone.
The strength is public reproducibility plus reproductive life-course insight,
not scale or clinical deployment.
