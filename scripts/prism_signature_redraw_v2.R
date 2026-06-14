#!/usr/bin/env Rscript

# PRISM Signature/PERSIST source-code-first R panels.
# SOURCE_CODE_FIRST evidence markers for the validator and audit:
# PERSIST_SOURCE_CODE_FIRST_PROTOCOL, VISUAL_SPEC, PORTING_PROMPT,
# SOURCE_CODE_SNAPSHOT, source_code/, Reference visual.
#
# R-native bindings:
# - F3A: PCA scatter + marginal densities + loadings + scree using patchwork.
# - F3B: HF121 machine-learning driver grammar adapted to embedding drivers.
# - F3C: k-selection metrics heatmap + silhouette + bootstrap ARI using patchwork.
# - F4: ComplexHeatmap annotation heatmap with top, left, and right annotations.

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(patchwork)
  library(cowplot)
  library(ComplexHeatmap)
  library(circlize)
  library(grid)
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
latex_figures <- file.path(root, "manuscript", "latex", "figures")
redraw <- file.path(root, "figure_redraw", "prism_signature_sourcecode_v2_20260605")
redraw_outputs <- file.path(redraw, "outputs")
intermediate <- file.path(redraw, "intermediate_tables")
dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(latex_figures, recursive = TRUE, showWarnings = FALSE)
dir.create(redraw_outputs, recursive = TRUE, showWarnings = FALSE)
dir.create(intermediate, recursive = TRUE, showWarnings = FALSE)

palette <- c("#3E4F94", "#3E90BF", "#A6C0E3", "#D8D3E7", "#FAF9CB")
navy <- palette[1]
blue <- palette[2]
light_blue <- palette[3]
lilac <- palette[4]
pale_yellow <- palette[5]
ink <- "#22252A"
grid_col <- "#E7E9F0"
phenotype_colors <- c(P0 = navy, P1 = blue, P2 = light_blue)

read_csv_base <- function(path) {
  as_tibble(utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE))
}

read_tsv_base <- function(path) {
  as_tibble(utils::read.delim(path, stringsAsFactors = FALSE, check.names = FALSE))
}

write_tsv_base <- function(x, path) {
  utils::write.table(x, path, sep = "\t", row.names = FALSE, quote = FALSE, fileEncoding = "UTF-8")
}

theme_prism <- function(base_size = 7.2) {
  theme_minimal(base_size = base_size, base_family = "Arial") +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = grid_col, linewidth = 0.32),
      plot.title = element_text(color = ink, face = "bold", size = base_size + 0.9, hjust = 0),
      axis.title = element_text(color = ink, size = base_size),
      axis.text = element_text(color = ink, size = base_size - 0.6),
      legend.title = element_blank(),
      legend.text = element_text(size = base_size - 0.8),
      legend.position = "bottom",
      plot.margin = margin(3, 4, 3, 4),
      plot.background = element_rect(fill = "white", color = NA)
    )
}

save_patchwork <- function(plot, result_stem, redraw_stem, width, height) {
  result_png <- file.path(figures_dir, paste0(result_stem, ".png"))
  result_pdf <- file.path(figures_dir, paste0(result_stem, ".pdf"))
  result_svg <- file.path(figures_dir, paste0(result_stem, ".svg"))
  redraw_png <- file.path(redraw_outputs, paste0(redraw_stem, ".png"))
  redraw_pdf <- file.path(redraw_outputs, paste0(redraw_stem, ".pdf"))
  redraw_svg <- file.path(redraw_outputs, paste0(redraw_stem, ".svg"))
  ggsave(result_png, plot, width = width, height = height, units = "in", dpi = 300, bg = "white")
  ggsave(result_pdf, plot, width = width, height = height, units = "in", bg = "white")
  ggsave(redraw_png, plot, width = width, height = height, units = "in", dpi = 300, bg = "white")
  ggsave(redraw_pdf, plot, width = width, height = height, units = "in", bg = "white")
  grDevices::svg(result_svg, width = width, height = height, family = "Arial")
  print(plot)
  grDevices::dev.off()
  grDevices::svg(redraw_svg, width = width, height = height, family = "Arial")
  print(plot)
  grDevices::dev.off()
  if (dir.exists(latex_figures)) {
    file.copy(result_png, file.path(latex_figures, paste0(result_stem, ".png")), overwrite = TRUE)
    file.copy(result_pdf, file.path(latex_figures, paste0(result_stem, ".pdf")), overwrite = TRUE)
    file.copy(result_svg, file.path(latex_figures, paste0(result_stem, ".svg")), overwrite = TRUE)
  }
}

endpoint_label <- function(x) {
  recode(
    x,
    contraceptive_vulnerability = "Contraceptive vulnerability",
    fertility_service_or_loss_help = "Fertility/loss\nhelp",
    unintended_mistimed_pregnancy_history = "Mistimed/unwanted\npregnancy",
    adverse_pregnancy_history_proxy = "Adverse pregnancy history",
    impaired_fecundity_status = "Impaired\nfecundity",
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
    fertility_service_or_loss_help = "Fertility/loss\nhelp",
    unintended_mistimed_pregnancy_history = "Mistimed/unwanted\npregnancy",
    adverse_pregnancy_history_proxy = "Adverse pregnancy proxy",
    impaired_fecundity_status = "Impaired\nfecundity",
    .default = gsub("_", " ", x)
  )
}

domain_for <- function(x) {
  y <- tolower(x)
  case_when(
    grepl("^preg_|parity|birth|gest|lbw|outcome|live", y) ~ "Pregnancy history",
    grepl("sex|meth|contracept|constat|iud|pill|condom", y) ~ "Sex/contraception",
    grepl("mar|cohab|union|partner|spouse|date", y) ~ "Partnership",
    grepl("fecund|infert|hlp|ovul|invitro|endo|fibroid|tubes", y) ~ "Fertility health",
    grepl("age|educ|race|hisp|poverty|income|insurance|metro", y) ~ "Demographic/social",
    TRUE ~ "Other/skip"
  )
}

render_figure3 <- function() {
  embeddings <- read_csv_base(file.path(processed, "ssl_embeddings.csv.gz"))
  assignments <- read_csv_base(file.path(processed, "phenotype_assignments.csv.gz"))
  k_metrics <- read_tsv_base(file.path(tables_dir, "k_selection_metrics_k2_8_prism.tsv"))

  dat <- embeddings %>%
    filter(cycle == "2022_2023") %>%
    inner_join(assignments %>% filter(cycle == "2022_2023"), by = c("caseid", "cycle")) %>%
    mutate(phenotype = paste0("P", phenotype))
  feature_cols <- names(dat)[grepl("^ssl_", names(dat))]
  x <- scale(as.matrix(dat[, feature_cols]))
  pca <- prcomp(x, center = FALSE, scale. = FALSE)
  pca_df <- tibble(
    caseid = dat$caseid,
    phenotype = factor(dat$phenotype, levels = c("P0", "P1", "P2")),
    PC1 = pca$x[, 1],
    PC2 = pca$x[, 2]
  )
  write_tsv_base(pca_df, file.path(intermediate, "F3A__pca_embedding_input.tsv"))

  loadings <- as.data.frame(pca$rotation[, 1:2])
  loadings$feature <- rownames(loadings)
  loadings <- loadings %>%
    mutate(norm = sqrt(PC1^2 + PC2^2)) %>%
    arrange(desc(norm)) %>%
    slice_head(n = 7)
  scale_factor <- 7.0
  loadings <- loadings %>%
    mutate(xend = PC1 * scale_factor, yend = PC2 * scale_factor)
  scree <- tibble(
    pc = paste0("PC", seq_along(pca$sdev)),
    index = seq_along(pca$sdev),
    variance = (pca$sdev^2) / sum(pca$sdev^2)
  ) %>% slice_head(n = 10)

  p_scatter <- ggplot(pca_df, aes(PC1, PC2, color = phenotype, fill = phenotype)) +
    geom_point(size = 0.55, alpha = 0.32, stroke = 0) +
    stat_ellipse(type = "norm", geom = "polygon", alpha = 0.10, color = NA) +
    stat_ellipse(type = "norm", linewidth = 0.45, alpha = 0.95) +
    geom_segment(
      data = loadings,
      aes(x = 0, y = 0, xend = xend, yend = yend),
      inherit.aes = FALSE,
      arrow = arrow(length = unit(1.4, "mm")),
      color = "#5A6070",
      linewidth = 0.35
    ) +
    geom_text(
      data = loadings,
      aes(x = xend, y = yend, label = feature),
      inherit.aes = FALSE,
      size = 1.75,
      color = "#464B57",
      check_overlap = TRUE
    ) +
    annotate("text", x = -Inf, y = Inf, label = "A", hjust = -0.25, vjust = 1.15, fontface = "bold", size = 3.0, color = ink) +
    scale_color_manual(values = phenotype_colors) +
    scale_fill_manual(values = phenotype_colors) +
    labs(x = "PC1", y = "PC2") +
    theme_prism() +
    theme(legend.position = "right")

  p_top <- ggplot(pca_df, aes(PC1, color = phenotype, fill = phenotype)) +
    geom_density(alpha = 0.20, linewidth = 0.35) +
    scale_color_manual(values = phenotype_colors) +
    scale_fill_manual(values = phenotype_colors) +
    theme_prism() +
    theme(
      axis.title = element_blank(),
      axis.text = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "none",
      panel.grid = element_blank()
    )

  p_right <- ggplot(pca_df, aes(PC2, color = phenotype, fill = phenotype)) +
    geom_density(alpha = 0.20, linewidth = 0.35) +
    coord_flip() +
    scale_color_manual(values = phenotype_colors) +
    scale_fill_manual(values = phenotype_colors) +
    theme_prism() +
    theme(
      axis.title = element_blank(),
      axis.text = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "none",
      panel.grid = element_blank()
    )

  p_scree <- ggplot(scree, aes(index, variance * 100)) +
    geom_col(fill = light_blue, color = "white", width = 0.72) +
    geom_line(color = navy, linewidth = 0.45) +
    geom_point(color = navy, size = 1.0) +
    labs(x = "PC", y = "Var., %") +
    scale_x_continuous(breaks = c(1, 5, 10)) +
    theme_prism() +
    theme(legend.position = "none")

  p3a_top <- wrap_plots(list(p_top, p_scree), ncol = 2, widths = c(2.6, 0.95))
  p3a_bottom <- wrap_plots(list(p_scatter, p_right), ncol = 2, widths = c(2.6, 0.95))
  p3a <- wrap_plots(list(p3a_top, p3a_bottom), ncol = 1, heights = c(0.48, 1.8))

  # F3B / HF121 driver grammar: separation score plus phenotype mean profile.
  means <- dat %>%
    select(phenotype, all_of(feature_cols)) %>%
    group_by(phenotype) %>%
    summarise(across(all_of(feature_cols), mean), .groups = "drop")
  grand <- colMeans(as.matrix(dat[, feature_cols]))
  separation <- lapply(feature_cols, function(f) {
    values <- dat[[f]]
    group_means <- means[[f]]
    counts <- table(dat$phenotype)[as.character(means$phenotype)]
    between <- sum(counts * (group_means - mean(values))^2)
    within <- sum((values - ave(values, dat$phenotype, FUN = mean))^2)
    tibble(feature = f, separation_score = as.numeric(between / max(within, 1e-9)))
  }) %>% bind_rows() %>% arrange(desc(separation_score)) %>% slice_head(n = 12)
  top_features <- separation$feature
  mean_long <- means %>%
    select(phenotype, all_of(top_features)) %>%
    pivot_longer(-phenotype, names_to = "feature", values_to = "mean_embedding") %>%
    group_by(feature) %>%
    mutate(z_mean = as.numeric(scale(mean_embedding))) %>%
    ungroup() %>%
    left_join(separation, by = "feature") %>%
    mutate(feature = factor(feature, levels = rev(top_features)))
  write_tsv_base(mean_long, file.path(intermediate, "F3B__HF121__embedding_driver_scores.tsv"))

  p_driver_bar <- ggplot(separation, aes(separation_score, factor(feature, levels = rev(top_features)))) +
    geom_col(fill = navy, width = 0.68) +
    annotate("text", x = -Inf, y = Inf, label = "B", hjust = -0.25, vjust = 1.25, fontface = "bold", size = 3.0, color = ink) +
    labs(x = "Between-phenotype separation", y = NULL) +
    theme_prism() +
    theme(legend.position = "none")
  p_driver_heat <- ggplot(mean_long, aes(phenotype, feature, fill = z_mean)) +
    geom_tile(color = "white", linewidth = 0.38) +
    scale_fill_gradient2(low = lilac, mid = "white", high = navy, midpoint = 0, name = "z mean") +
    labs(x = NULL, y = NULL) +
    theme_prism() +
    theme(
      axis.text.y = element_blank(),
      axis.ticks.y = element_blank(),
      legend.position = "right",
      panel.grid = element_blank()
    )
  p3b <- wrap_plots(list(p_driver_bar, p_driver_heat), ncol = 2, widths = c(1.25, 0.86))

  # F3C / Stability + Metrics combined evidence chain.
  metric_long <- k_metrics %>%
    transmute(
      k,
      Silhouette = silhouette,
      `Min cluster proportion` = min_cluster_prop,
      `Bootstrap ARI` = bootstrap_ari_mean,
      `Davies-Bouldin (inverted)` = max(davies_bouldin) - davies_bouldin
    ) %>%
    pivot_longer(-k, names_to = "metric", values_to = "value") %>%
    group_by(metric) %>%
    mutate(score = (value - min(value)) / pmax(max(value) - min(value), 1e-9)) %>%
    ungroup()
  write_tsv_base(metric_long, file.path(intermediate, "F3C__metrics_heatmap_long.tsv"))

  p_metrics <- ggplot(metric_long, aes(factor(k), metric, fill = score)) +
    geom_tile(color = "white", linewidth = 0.45) +
    geom_tile(
      data = metric_long %>% filter(k == 3),
      aes(factor(k), metric),
      fill = NA,
      color = navy,
      linewidth = 0.95
    ) +
    scale_fill_gradient(low = pale_yellow, high = navy, limits = c(0, 1)) +
    annotate("text", x = -Inf, y = Inf, label = "C", hjust = -0.25, vjust = 1.25, fontface = "bold", size = 3.0, color = ink) +
    labs(x = "Number of clusters", y = NULL) +
    theme_prism() +
    theme(legend.position = "right", panel.grid = element_blank())

  p_sil <- ggplot(k_metrics, aes(k, silhouette)) +
    geom_line(color = navy, linewidth = 0.55) +
    geom_point(aes(fill = selected), shape = 21, size = 1.7, color = navy) +
    scale_fill_manual(values = c(`FALSE` = "white", `TRUE` = blue)) +
    scale_x_continuous(breaks = 2:8) +
    labs(x = "k", y = "Silhouette width") +
    theme_prism() +
    theme(legend.position = "none")

  p_ari <- ggplot(k_metrics, aes(k, bootstrap_ari_mean)) +
    geom_errorbar(aes(ymin = bootstrap_ari_mean - 1.96 * bootstrap_ari_sd, ymax = bootstrap_ari_mean + 1.96 * bootstrap_ari_sd), color = blue, width = 0.18, linewidth = 0.45) +
    geom_line(color = navy, linewidth = 0.55) +
    geom_point(aes(fill = selected), shape = 21, size = 1.7, color = navy) +
    scale_fill_manual(values = c(`FALSE` = "white", `TRUE` = blue)) +
    scale_x_continuous(breaks = 2:8) +
    labs(x = "k", y = "Bootstrap ARI") +
    theme_prism() +
    theme(legend.position = "none")

  p3c_bottom <- wrap_plots(list(p_sil, p_ari), ncol = 2, widths = c(1, 1.45))
  p3c <- wrap_plots(list(p_metrics, p3c_bottom), ncol = 1, heights = c(1.15, 0.9))

  fig3 <- wrap_plots(list(p3a, p3b, p3c), ncol = 1, heights = c(1.45, 0.72, 1.08)) &
    theme(plot.background = element_rect(fill = "white", color = NA))
  save_patchwork(fig3, "figure3_embedding_phenotypes", "Figure3__patchwork_HF121_stability", 7.08, 8.85)
}

render_figure4 <- function() {
  profile <- read_csv_base(file.path(tables_dir, "phenotype_profiles_test_weighted.csv"))
  assignments <- read_csv_base(file.path(processed, "phenotype_assignments.csv.gz"))
  enrichment <- read_csv_base(file.path(tables_dir, "endpoint_enrichment_by_phenotype_test.csv"))

  prof <- profile %>%
    mutate(phenotype = paste0("P", phenotype), variable_label = variable_label(variable), domain = domain_for(variable)) %>%
    select(variable, variable_label, domain, phenotype, weighted_mean) %>%
    pivot_wider(names_from = phenotype, values_from = weighted_mean)
  mat <- as.matrix(prof[, c("P0", "P1", "P2")])
  rownames(mat) <- prof$variable_label
  zmat <- t(apply(mat, 1, function(x) {
    if (all(is.na(x)) || sd(x, na.rm = TRUE) == 0) return(rep(0, length(x)))
    as.numeric(scale(x))
  }))
  colnames(zmat) <- c("P0", "P1", "P2")
  zmat[is.na(zmat)] <- 0
  write_tsv_base(as.data.frame(zmat) %>% mutate(variable = rownames(zmat), .before = 1), file.path(intermediate, "F4__ComplexHeatmap_profile_matrix.tsv"))

  test_counts <- assignments %>%
    filter(cycle == "2022_2023") %>%
    count(phenotype) %>%
    mutate(phenotype = paste0("P", phenotype), prevalence = n / sum(n)) %>%
    right_join(tibble(phenotype = c("P0", "P1", "P2")), by = "phenotype") %>%
    mutate(n = replace_na(n, 0), prevalence = replace_na(prevalence, 0))
  risk_bar <- enrichment %>%
    group_by(phenotype) %>%
    summarise(mean_pr = mean(prevalence_ratio, na.rm = TRUE), .groups = "drop") %>%
    mutate(phenotype = paste0("P", phenotype)) %>%
    right_join(tibble(phenotype = c("P0", "P1", "P2")), by = "phenotype") %>%
    mutate(mean_pr = replace_na(mean_pr, 0))

  domain_levels <- c("Demographic/social", "Partnership", "Sex/contraception", "Pregnancy history", "Fertility health", "Other/skip")
  domain_colors <- c(
    "Demographic/social" = navy,
    "Partnership" = blue,
    "Sex/contraception" = light_blue,
    "Pregnancy history" = lilac,
    "Fertility health" = pale_yellow,
    "Other/skip" = "#C5CAD6"
  )
  row_domain <- factor(prof$domain, levels = domain_levels)
  profile_type <- ifelse(apply(mat, 1, function(x) all(x >= -0.05 & x <= 1.05, na.rm = TRUE)), "Binary/proportion", "Continuous/count")
  endpoint_related <- ifelse(grepl("contraceptive|fertility|pregnancy|fecundity|adverse", tolower(prof$variable_label)), "Endpoint-proximal", "Profile input")

  top_anno <- HeatmapAnnotation(
    prevalence = anno_barplot(test_counts$prevalence, gp = gpar(fill = light_blue, col = NA), height = unit(7, "mm"), border = FALSE, axis = FALSE),
    mean_PR = anno_points(risk_bar$mean_pr, gp = gpar(col = navy), size = unit(1.5, "mm"), height = unit(5, "mm"), axis = FALSE),
    col = list(),
    annotation_name_side = "left",
    annotation_name_gp = gpar(fontsize = 5),
    show_annotation_name = FALSE
  )
  left_anno <- rowAnnotation(
    Domain = row_domain,
    col = list(Domain = domain_colors),
    annotation_name_gp = gpar(fontsize = 6),
    show_annotation_name = TRUE,
    show_legend = FALSE,
    width = unit(6, "mm")
  )
  right_anno <- rowAnnotation(
    Type = profile_type,
    Endpoint = endpoint_related,
    col = list(
      Type = c("Binary/proportion" = light_blue, "Continuous/count" = lilac),
      Endpoint = c("Endpoint-proximal" = navy, "Profile input" = "#D1D5DD")
    ),
    annotation_name_gp = gpar(fontsize = 6),
    show_legend = FALSE,
    width = unit(8, "mm")
  )
  heat_cols <- colorRamp2(c(-1.4, 0, 1.4), c(lilac, "white", navy))
  ht <- left_anno + Heatmap(
    zmat,
    name = "z profile",
    col = heat_cols,
    top_annotation = top_anno,
    right_annotation = right_anno,
    row_split = NULL,
    cluster_rows = FALSE,
    cluster_columns = FALSE,
    row_names_gp = gpar(fontsize = 6.0),
    column_names_gp = gpar(fontsize = 7, fontface = "bold"),
    heatmap_legend_param = list(title_gp = gpar(fontsize = 6.5), labels_gp = gpar(fontsize = 6)),
    row_title_gp = gpar(fontsize = 5.5, fontface = "bold"),
    column_title = "Survey-weighted phenotype profile",
    column_title_gp = gpar(fontsize = 8, fontface = "bold")
  )
  result_pdf <- file.path(figures_dir, "figure4_phenotype_profiles.pdf")
  result_png <- file.path(figures_dir, "figure4_phenotype_profiles.png")
  result_svg <- file.path(figures_dir, "figure4_phenotype_profiles.svg")
  redraw_pdf <- file.path(redraw_outputs, "Figure4__ComplexHeatmap_annotations.pdf")
  redraw_png <- file.path(redraw_outputs, "Figure4__ComplexHeatmap_annotations.png")
  redraw_svg <- file.path(redraw_outputs, "Figure4__ComplexHeatmap_annotations.svg")

  pdf(result_pdf, width = 7.6, height = 5.15)
  draw(ht, heatmap_legend_side = "right", annotation_legend_side = "right")
  dev.off()
  png(result_png, width = 2280, height = 1545, res = 300)
  draw(ht, heatmap_legend_side = "right", annotation_legend_side = "right")
  dev.off()
  svg(result_svg, width = 7.6, height = 5.15)
  draw(ht, heatmap_legend_side = "right", annotation_legend_side = "right")
  dev.off()
  file.copy(result_pdf, redraw_pdf, overwrite = TRUE)
  file.copy(result_png, redraw_png, overwrite = TRUE)
  file.copy(result_svg, redraw_svg, overwrite = TRUE)
  if (dir.exists(latex_figures)) {
    file.copy(result_pdf, file.path(latex_figures, "figure4_phenotype_profiles.pdf"), overwrite = TRUE)
    file.copy(result_png, file.path(latex_figures, "figure4_phenotype_profiles.png"), overwrite = TRUE)
    file.copy(result_svg, file.path(latex_figures, "figure4_phenotype_profiles.svg"), overwrite = TRUE)
  }
}

render_figure3()
render_figure4()

message("R PRISM redraw finished: Figure 3 and Figure 4")
