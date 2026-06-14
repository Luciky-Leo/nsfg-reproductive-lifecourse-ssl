#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(patchwork)
  library(scales)
})

argv <- commandArgs(trailingOnly = FALSE)
file_arg <- argv[grepl("^--file=", argv)]
if (length(file_arg) == 0) {
  root <- normalizePath(getwd(), mustWork = TRUE)
} else {
  script_path <- sub("^--file=", "", file_arg[[1]])
  root <- normalizePath(file.path(dirname(script_path), ".."), mustWork = TRUE)
}
processed <- file.path(root, "data", "processed")
tables_dir <- file.path(root, "results", "tables")
figures_dir <- file.path(root, "results", "figures")
manuscript_tables <- file.path(root, "manuscript", "tables")
dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(manuscript_tables, recursive = TRUE, showWarnings = FALSE)

theme_nsfg <- function(base_size = 10) {
  theme_minimal(base_size = base_size) +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = "#E6E6E6", linewidth = 0.35),
      plot.title = element_blank(),
      legend.title = element_blank(),
      legend.position = "bottom",
      axis.title = element_text(color = "#222222"),
      axis.text = element_text(color = "#222222"),
      plot.tag = element_text(face = "bold", size = base_size + 3),
      plot.margin = margin(8, 10, 8, 10)
    )
}

weighted_mean <- function(y, w) {
  y <- suppressWarnings(as.numeric(y))
  w <- suppressWarnings(as.numeric(w))
  keep <- !is.na(y) & !is.na(w)
  if (!any(keep) || sum(w[keep]) == 0) return(NA_real_)
  sum(y[keep] * w[keep]) / sum(w[keep])
}

endpoint_label <- function(x) {
  recode(
    x,
    contraceptive_vulnerability = "Contraceptive vulnerability",
    fertility_service_or_loss_help = "Fertility or loss help",
    unintended_mistimed_pregnancy_history = "Mistimed/unwanted pregnancy",
    adverse_pregnancy_history_proxy = "Adverse pregnancy proxy",
    impaired_fecundity_status = "Impaired fecundity",
    .default = x
  )
}

variable_label <- function(x) {
  recode(
    x,
    age_analysis = "Age",
    parity = "Parity",
    preg_n_records = "Pregnancy records",
    has_pregnancy_record = "Any pregnancy record",
    poverty = "Poverty-income ratio",
    contraceptive_vulnerability = "Contraceptive vulnerability",
    fertility_service_or_loss_help = "Fertility or loss help",
    unintended_mistimed_pregnancy_history = "Mistimed/unwanted pregnancy",
    adverse_pregnancy_history_proxy = "Adverse pregnancy proxy",
    impaired_fecundity_status = "Impaired fecundity",
    .default = x
  )
}

save_plot <- function(plot, stem, width, height) {
  ggsave(file.path(figures_dir, paste0(stem, ".pdf")), plot, width = width, height = height, units = "in", bg = "white")
  ggsave(file.path(figures_dir, paste0(stem, ".png")), plot, width = width, height = height, units = "in", dpi = 320, bg = "white")
}

matrix <- read_csv(file.path(processed, "nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz"), show_col_types = FALSE)
endpoints <- read_csv(file.path(processed, "nsfg_endpoint_labels.csv.gz"), show_col_types = FALSE)
assignments <- read_csv(file.path(processed, "phenotype_assignments.csv.gz"), show_col_types = FALSE)
pca <- read_csv(file.path(processed, "ssl_pca_coordinates.csv.gz"), show_col_types = FALSE)
audit <- read_csv(file.path(tables_dir, "ssl_feature_audit.csv"), show_col_types = FALSE)
endpoint_defs <- read_csv(file.path(tables_dir, "endpoint_definitions.csv"), show_col_types = FALSE)
cluster_metrics <- read_csv(file.path(tables_dir, "cluster_selection_metrics.csv"), show_col_types = FALSE)
profile <- read_csv(file.path(tables_dir, "phenotype_profiles_test_weighted.csv"), show_col_types = FALSE)
enrichment <- read_csv(file.path(tables_dir, "endpoint_enrichment_by_phenotype_test.csv"), show_col_types = FALSE)
supervised <- read_csv(file.path(tables_dir, "supervised_validation_metrics.csv"), show_col_types = FALSE)
training_curve <- read_csv(file.path(tables_dir, "ssl_training_curve.csv"), show_col_types = FALSE)
matrix_summary <- read_csv(file.path(tables_dir, "harmonized_matrix_summary.csv"), show_col_types = FALSE)

split_map <- c(
  "2011_2013" = "Training/pretraining",
  "2013_2015" = "Training/pretraining",
  "2015_2017" = "Training/pretraining",
  "2017_2019" = "Development/model selection",
  "2022_2023" = "Temporal validation"
)
endpoint_cols <- setdiff(names(endpoints), c("caseid", "cycle"))

merged <- matrix %>%
  left_join(endpoints, by = c("caseid", "cycle")) %>%
  mutate(analysis_split = factor(split_map[cycle], levels = unique(split_map)))

table1_base <- merged %>%
  group_by(analysis_split) %>%
  summarise(
    n_respondents = n(),
    weighted_mean_age = weighted_mean(age_analysis, analysis_weight),
    weighted_mean_parity = weighted_mean(parity, analysis_weight),
    weighted_pregnancy_record_prevalence = weighted_mean(has_pregnancy_record, analysis_weight),
    .groups = "drop"
  )
table1_endpoints <- merged %>%
  group_by(analysis_split) %>%
  summarise(across(all_of(endpoint_cols), ~ weighted_mean(.x, analysis_weight)), .groups = "drop")
table1 <- table1_base %>% left_join(table1_endpoints, by = "analysis_split")
write_csv(table1, file.path(manuscript_tables, "table1_cohort_characteristics.csv"))

table2 <- bind_rows(
  tibble(
    domain_or_endpoint = "Primary SSL input features",
    definition = "Endpoint-direct variables excluded; top nonconstant features selected by training-cycle completeness and variance.",
    n_features = as.character(sum(audit$used_in_primary_encoder)),
    leakage_control = "Direct endpoint regex excluded before encoder fitting."
  ),
  endpoint_defs %>%
    transmute(
      domain_or_endpoint = endpoint,
      definition = positive_definition,
      n_features = "",
      leakage_control = direct_feature_regex
    )
)
write_csv(table2, file.path(manuscript_tables, "table2_variables_endpoints.csv"))

table3 <- profile %>%
  select(variable, phenotype, weighted_mean) %>%
  pivot_wider(names_from = phenotype, values_from = weighted_mean, names_prefix = "P")
write_csv(table3, file.path(manuscript_tables, "table3_phenotype_profiles.csv"))

table4_top <- enrichment %>%
  group_by(endpoint) %>%
  arrange(desc(prevalence_ratio), .by_group = TRUE) %>%
  slice(1) %>%
  ungroup() %>%
  rename(
    top_phenotype = phenotype,
    top_n = n,
    top_events = events,
    top_weighted_prevalence = weighted_prevalence,
    top_prevalence_ratio = prevalence_ratio,
    top_risk_difference = risk_difference
  )
table4_best <- supervised %>%
  group_by(endpoint) %>%
  arrange(desc(auprc), .by_group = TRUE) %>%
  slice(1) %>%
  ungroup() %>%
  rename(best_feature_set = feature_set)
table4 <- table4_top %>% left_join(table4_best, by = "endpoint")
write_csv(table4, file.path(manuscript_tables, "table4_endpoint_enrichment_model_metrics.csv"))

# Figure 1: integrated workflow.
box_df <- tibble(
  x = c(0.09, 0.27, 0.45, 0.63, 0.81, 0.22, 0.50, 0.78),
  y = c(0.80, 0.80, 0.80, 0.80, 0.80, 0.37, 0.37, 0.37),
  w = c(0.12, 0.16, 0.16, 0.16, 0.18, 0.26, 0.28, 0.28),
  h = c(0.16, 0.16, 0.16, 0.16, 0.16, 0.28, 0.28, 0.28),
  label = c(
    "CDC/NCHS\nNSFG public-use\nfemale files",
    "2011-2017\ntraining and SSL\npretraining",
    "2017-2019\ndevelopment and\nphenotype selection",
    "2022-2023\ntemporal validation\nlabels used once",
    "Validation endpoints\ncontraception, fertility help,\npregnancy history, fecundity",
    "Respondent-level\nlife-course matrix\nrespondent + pregnancy summaries",
    "Masked tabular\nself-supervised encoder\nmixed feature masking + reconstruction",
    "Phenotype discovery\nPCA + k-means centroids\nrisk enrichment evaluation"
  ),
  color = c("#2E5EAA", "#2E5EAA", "#E87528", "#777777", "#4E9B50", "#2E5EAA", "#E87528", "#4E9B50")
)
arrow_df <- tibble(
  x = c(0.15, 0.35, 0.53, 0.71, 0.31, 0.64),
  y = c(0.80, 0.80, 0.80, 0.80, 0.37, 0.37),
  xend = c(0.19, 0.37, 0.55, 0.72, 0.36, 0.68),
  yend = c(0.80, 0.80, 0.80, 0.80, 0.37, 0.37)
)
fig1 <- ggplot() +
  geom_rect(
    data = box_df,
    aes(xmin = x - w / 2, xmax = x + w / 2, ymin = y - h / 2, ymax = y + h / 2, color = color),
    fill = "white", linewidth = 0.9, radius = unit(0.08, "in")
  ) +
  geom_segment(
    data = arrow_df,
    aes(x = x, y = y, xend = xend, yend = yend),
    linewidth = 0.8, color = "#333333", arrow = arrow(length = unit(0.16, "in"))
  ) +
  geom_segment(aes(x = 0.27, y = 0.69, xend = 0.22, yend = 0.52), color = "#777777", linewidth = 0.7, arrow = arrow(length = unit(0.12, "in"))) +
  geom_segment(aes(x = 0.50, y = 0.52, xend = 0.50, yend = 0.50), color = "#777777", linewidth = 0.7, arrow = arrow(length = unit(0.12, "in"))) +
  geom_text(data = box_df, aes(x = x, y = y, label = label, color = color), size = 3.4, lineheight = 1.08, fontface = "bold") +
  scale_color_identity() +
  coord_cartesian(xlim = c(0.01, 0.99), ylim = c(0.12, 0.94), expand = FALSE) +
  theme_void() +
  theme(plot.margin = margin(12, 12, 12, 12))
save_plot(fig1, "figure1_workflow", 13.5, 5.2)

# Figure 2: cohort structure and missingness.
cycle_lab <- c(
  "2011_2013" = "2011-2013",
  "2013_2015" = "2013-2015",
  "2015_2017" = "2015-2017",
  "2017_2019" = "2017-2019",
  "2022_2023" = "2022-2023"
)
summary_long <- matrix_summary %>%
  mutate(cycle_label = factor(cycle_lab[cycle], levels = cycle_lab)) %>%
  mutate(pregnancy_record_prevalence = respondents_with_pregnancy / respondents)
p2a <- ggplot(summary_long, aes(cycle_label, respondents, fill = cycle_label)) +
  geom_col(width = 0.72, show.legend = FALSE) +
  geom_text(aes(label = comma(respondents)), vjust = -0.35, size = 3.0) +
  scale_fill_manual(values = c("#2E5EAA", "#2E5EAA", "#2E5EAA", "#E87528", "#777777")) +
  scale_y_continuous(labels = comma, expand = expansion(mult = c(0, 0.12))) +
  labs(x = NULL, y = "Respondents") +
  theme_nsfg()
p2b <- ggplot(summary_long, aes(cycle_label, pregnancy_record_prevalence, group = 1)) +
  geom_line(color = "#2E5EAA", linewidth = 0.8) +
  geom_point(color = "#2E5EAA", size = 2.3) +
  scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, 0.75)) +
  labs(x = NULL, y = "With pregnancy records") +
  theme_nsfg()
used_features <- audit %>% filter(used_in_primary_encoder) %>% pull(feature)
missing_df <- matrix %>%
  filter(cycle == "2022_2023") %>%
  select(any_of(used_features)) %>%
  summarise(across(everything(), ~ mean(is.na(.x)))) %>%
  pivot_longer(everything(), names_to = "feature", values_to = "missingness") %>%
  arrange(desc(missingness)) %>%
  slice_head(n = 24) %>%
  mutate(feature = factor(feature, levels = rev(feature)))
p2c <- ggplot(missing_df, aes(missingness, feature)) +
  geom_col(fill = "#8AAED8", width = 0.72) +
  scale_x_continuous(labels = percent_format(accuracy = 1), limits = c(0, max(0.01, max(missing_df$missingness) * 1.10))) +
  labs(x = "Missing or skipped", y = NULL) +
  theme_nsfg(base_size = 8)
fig2 <- (p2a | p2b | p2c) + plot_annotation(tag_levels = "A")
save_plot(fig2, "figure2_matrix_missingness", 13.2, 4.8)

# Figure 3: embeddings and phenotype discovery.
pca_test <- pca %>%
  filter(cycle == "2022_2023") %>%
  left_join(assignments, by = c("caseid", "cycle")) %>%
  mutate(phenotype = factor(paste0("P", phenotype), levels = paste0("P", sort(unique(assignments$phenotype)))))
phenotype_counts <- pca_test %>% count(phenotype)
pal <- c(P0 = "#3B6FB6", P1 = "#E6862E", P2 = "#4E9B50", P3 = "#8D6AB8")
p3a <- ggplot(pca_test, aes(pc1, pc2, color = phenotype)) +
  geom_point(size = 0.9, alpha = 0.62) +
  scale_color_manual(values = pal) +
  labs(x = "PC1", y = "PC2") +
  theme_nsfg()
p3b <- ggplot(phenotype_counts, aes(phenotype, n, fill = phenotype)) +
  geom_col(width = 0.72, show.legend = FALSE) +
  geom_text(aes(label = comma(n)), vjust = -0.35, size = 3.0) +
  scale_fill_manual(values = pal) +
  scale_y_continuous(labels = comma, expand = expansion(mult = c(0, 0.12))) +
  labs(x = NULL, y = "Respondents") +
  theme_nsfg()
cluster_long <- cluster_metrics %>%
  select(k, silhouette, bootstrap_ari_mean) %>%
  pivot_longer(-k, names_to = "metric", values_to = "value") %>%
  mutate(metric = recode(metric, silhouette = "Silhouette", bootstrap_ari_mean = "Bootstrap ARI"))
p3c <- ggplot(cluster_long, aes(k, value, color = metric)) +
  geom_line(linewidth = 0.8) +
  geom_point(size = 2.1) +
  geom_vline(xintercept = 3, color = "#555555", linetype = "dashed", linewidth = 0.45) +
  scale_x_continuous(breaks = sort(unique(cluster_metrics$k))) +
  scale_y_continuous(limits = c(0, 1.05)) +
  scale_color_manual(values = c("Silhouette" = "#3B6FB6", "Bootstrap ARI" = "#E6862E")) +
  labs(x = "Number of clusters", y = "Metric value") +
  theme_nsfg()
fig3 <- (p3a | p3b | p3c) + plot_annotation(tag_levels = "A")
save_plot(fig3, "figure3_embedding_phenotypes", 13.2, 4.8)

# Figure 4: phenotype interpretation.
plot_profile <- profile %>%
  mutate(
    phenotype = factor(paste0("P", phenotype), levels = paste0("P", sort(unique(phenotype)))),
    variable_label = variable_label(variable)
  ) %>%
  group_by(variable) %>%
  mutate(
    z_mean = mean(weighted_mean, na.rm = TRUE),
    z_sd = sd(weighted_mean, na.rm = TRUE),
    z = if_else(is.na(z_sd) | z_sd == 0, 0, (weighted_mean - z_mean) / z_sd)
  ) %>%
  ungroup()
row_order <- c(
  "Age", "Parity", "Pregnancy records", "Any pregnancy record", "Poverty-income ratio",
  "Contraceptive vulnerability", "Fertility or loss help", "Mistimed/unwanted pregnancy",
  "Adverse pregnancy proxy", "Impaired fecundity"
)
plot_profile$variable_label <- factor(plot_profile$variable_label, levels = rev(row_order))
fig4 <- ggplot(plot_profile, aes(phenotype, variable_label, fill = z)) +
  geom_tile(color = "white", linewidth = 0.8) +
  scale_fill_gradient2(low = "#2E5EAA", mid = "white", high = "#E87528", midpoint = 0, name = "Standardized\nprofile") +
  labs(x = "Temporal-validation phenotype", y = NULL) +
  theme_nsfg(base_size = 10) +
  theme(panel.grid = element_blank(), legend.position = "right")
save_plot(fig4, "figure4_phenotype_profiles", 7.4, 4.8)

# Figure 5: enrichment and secondary supervised validation.
enrichment_plot <- enrichment %>%
  mutate(
    phenotype = factor(paste0("P", phenotype), levels = paste0("P", sort(unique(phenotype)))),
    endpoint_label = factor(endpoint_label(endpoint), levels = rev(endpoint_label(unique(endpoint))))
  )
p5a <- ggplot(enrichment_plot, aes(prevalence_ratio, endpoint_label, color = phenotype)) +
  geom_vline(xintercept = 1, color = "#777777", linetype = "dashed", linewidth = 0.5) +
  geom_point(position = position_dodge(width = 0.55), size = 2.4) +
  scale_color_manual(values = pal) +
  scale_x_continuous(limits = c(0, max(4.4, max(enrichment_plot$prevalence_ratio) * 1.08))) +
  labs(x = "Weighted prevalence ratio", y = NULL) +
  theme_nsfg()
supervised_plot <- supervised %>%
  mutate(
    endpoint_label = factor(endpoint_label(endpoint), levels = rev(endpoint_label(unique(endpoint)))),
    feature_set = factor(feature_set, levels = c("Phenotype only", "SSL embedding", "SSL + phenotype"))
  )
p5b <- ggplot(supervised_plot, aes(auprc_enrichment, endpoint_label, fill = feature_set)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.66) +
  scale_fill_manual(values = c("Phenotype only" = "#777777", "SSL embedding" = "#3B6FB6", "SSL + phenotype" = "#E6862E")) +
  labs(x = "AUPRC / baseline prevalence", y = NULL) +
  theme_nsfg()
fig5 <- (p5a | p5b) + plot_annotation(tag_levels = "A")
save_plot(fig5, "figure5_risk_enrichment", 12.0, 5.0)

# Supplementary Figure S1.
pS1a <- ggplot(training_curve, aes(epoch, masked_mse)) +
  geom_line(color = "#3B6FB6", linewidth = 0.8) +
  geom_point(color = "#3B6FB6", size = 1.6) +
  labs(x = "Epoch", y = "Masked reconstruction MSE") +
  theme_nsfg()
audit_plot <- audit %>%
  mutate(used = ifelse(used_in_primary_encoder, "Used in encoder", "Available but unused"))
pS1b <- ggplot(audit_plot, aes(missing_train, fill = used)) +
  geom_density(alpha = 0.55, color = NA) +
  scale_x_continuous(labels = percent_format(accuracy = 1)) +
  scale_fill_manual(values = c("Used in encoder" = "#E6862E", "Available but unused" = "#777777")) +
  labs(x = "Training-cycle missingness", y = "Density") +
  theme_nsfg()
figS1 <- (pS1a | pS1b) + plot_annotation(tag_levels = "A")
save_plot(figS1, "figureS1_ssl_diagnostics", 10.8, 4.5)

mapping <- paste(
  "# Panel Visual Mapping",
  "",
  "| Figure | Analysis runtime | Render runtime | Env | Source data | Reproduction command |",
  "|---|---|---|---|---|---|",
  "| Figure 1 | Current source tables | R/ggplot2 | Windows R 4.6.0 with ggplot2/patchwork | results/tables/*.csv and data/processed/*.csv.gz | Rscript scripts/make_current_tables_and_figures.R |",
  "| Figure 2 | Current harmonized matrix and feature audit | R/ggplot2 | Windows R 4.6.0 with ggplot2/patchwork | data/processed/nsfg_2011_2023_harmonized_lifecourse_matrix.csv.gz; results/tables/harmonized_matrix_summary.csv; results/tables/ssl_feature_audit.csv | Rscript scripts/make_current_tables_and_figures.R |",
  "| Figure 3 | Current SSL PCA coordinates and phenotype assignments | R/ggplot2 | Windows R 4.6.0 with ggplot2/patchwork | data/processed/ssl_pca_coordinates.csv.gz; data/processed/phenotype_assignments.csv.gz; results/tables/cluster_selection_metrics.csv | Rscript scripts/make_current_tables_and_figures.R |",
  "| Figure 4 | Current survey-weighted phenotype profiles | R/ggplot2 | Windows R 4.6.0 with ggplot2 | results/tables/phenotype_profiles_test_weighted.csv | Rscript scripts/make_current_tables_and_figures.R |",
  "| Figure 5 | Current endpoint enrichment and supervised validation metrics | R/ggplot2 | Windows R 4.6.0 with ggplot2/patchwork | results/tables/endpoint_enrichment_by_phenotype_test.csv; results/tables/supervised_validation_metrics.csv | Rscript scripts/make_current_tables_and_figures.R |",
  "| Figure S1 | Current SSL training curve and feature audit | R/ggplot2 | Windows R 4.6.0 with ggplot2/patchwork | results/tables/ssl_training_curve.csv; results/tables/ssl_feature_audit.csv | Rscript scripts/make_current_tables_and_figures.R |",
  "",
  sep = "\n"
)
writeLines(mapping, file.path(root, "panel_visual_mapping.md"))

message("Current tables and figures regenerated from current source tables.")
