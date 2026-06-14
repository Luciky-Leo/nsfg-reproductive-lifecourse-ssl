#!/usr/bin/env Rscript

# Standalone R panels for manual assembly.
# SOURCE_CODE_FIRST markers:
# PERSIST_SOURCE_CODE_FIRST_PROTOCOL; VISUAL_SPEC; PORTING_PROMPT;
# SOURCE_CODE_SNAPSHOT; source_code/; Reference visual.

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(ggplot2)
  library(patchwork)
  library(ComplexHeatmap)
  library(circlize)
  library(grid)
})

argv <- commandArgs(trailingOnly = FALSE)
file_arg <- argv[grepl("^--file=", argv)]
if (length(file_arg) == 0) {
  script_start <- normalizePath(getwd(), mustWork = TRUE)
} else {
  script_path <- sub("^--file=", "", file_arg[[1]])
  script_start <- normalizePath(dirname(script_path), mustWork = TRUE)
}

find_project_root <- function(start) {
  current <- normalizePath(start, mustWork = TRUE)
  while (TRUE) {
    if (
      file.exists(file.path(current, "data", "processed", "ssl_embeddings.csv.gz")) &&
      dir.exists(file.path(current, "results", "tables"))
    ) {
      return(current)
    }
    parent <- dirname(current)
    if (identical(parent, current)) {
      stop(sprintf("Could not locate project root from %s", start))
    }
    current <- parent
  }
}

root <- find_project_root(script_start)

processed <- file.path(root, "data", "processed")
tables_dir <- file.path(root, "results", "tables")
redraw <- file.path(root, "figure_redraw", "panelwise_persist_prism_20260605")
outputs <- file.path(redraw, "outputs")
intermediate <- file.path(redraw, "intermediate_tables")
dir.create(file.path(outputs, "F3A"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(outputs, "F3C"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(outputs, "F4"), recursive = TRUE, showWarnings = FALSE)
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

read_csv_base <- function(path) as_tibble(utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE))
read_tsv_base <- function(path) as_tibble(utils::read.delim(path, stringsAsFactors = FALSE, check.names = FALSE))
write_tsv_base <- function(x, path) utils::write.table(x, path, sep = "\t", row.names = FALSE, quote = FALSE, fileEncoding = "UTF-8")

theme_prism <- function(base_size = 7.2) {
  theme_minimal(base_size = base_size, base_family = "Arial") +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = grid_col, linewidth = 0.32),
      plot.title = element_text(color = ink, face = "bold", size = base_size + 0.8, hjust = 0),
      axis.title = element_text(color = ink, size = base_size),
      axis.text = element_text(color = ink, size = base_size - 0.5),
      legend.title = element_blank(),
      legend.text = element_text(size = base_size - 0.8),
      legend.position = "bottom",
      plot.margin = margin(3, 4, 3, 4),
      plot.background = element_rect(fill = "white", color = NA)
    )
}

save_panel <- function(plot, panel, stem, width, height) {
  outdir <- file.path(outputs, panel)
  png_path <- file.path(outdir, paste0(stem, ".png"))
  pdf_path <- file.path(outdir, paste0(stem, ".pdf"))
  svg_path <- file.path(outdir, paste0(stem, ".svg"))
  ggsave(png_path, plot, width = width, height = height, units = "in", dpi = 300, bg = "white")
  ggsave(pdf_path, plot, width = width, height = height, units = "in", bg = "white")
  grDevices::svg(svg_path, width = width, height = height)
  print(plot)
  grDevices::dev.off()
}

endpoint_label <- function(x) {
  recode(
    x,
    contraceptive_vulnerability = "Contraceptive vulnerability",
    fertility_service_or_loss_help = "Fertility/loss help",
    unintended_mistimed_pregnancy_history = "Mistimed/unwanted pregnancy",
    adverse_pregnancy_history_proxy = "Adverse pregnancy history",
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
    fertility_service_or_loss_help = "Fertility/loss help",
    unintended_mistimed_pregnancy_history = "Mistimed/unwanted pregnancy",
    adverse_pregnancy_history_proxy = "Adverse pregnancy proxy",
    impaired_fecundity_status = "Impaired fecundity",
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

render_f3a <- function() {
  embeddings <- read_csv_base(file.path(processed, "ssl_embeddings.csv.gz"))
  assignments <- read_csv_base(file.path(processed, "phenotype_assignments.csv.gz"))
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
  write_tsv_base(pca_df, file.path(intermediate, "F3A__v1__native_patchwork_pca_quad__input_mapped.tsv"))
  loadings <- as.data.frame(pca$rotation[, 1:2])
  loadings$feature <- rownames(loadings)
  loadings <- loadings %>%
    mutate(norm = sqrt(PC1^2 + PC2^2)) %>%
    arrange(desc(norm)) %>%
    slice_head(n = 3) %>%
    mutate(
      rank = row_number(),
      xend = PC1 * 15.0,
      yend = PC2 * 15.0,
      label_x = c(-2.55, -2.55, 1.70)[rank],
      label_y = c(4.65, 3.25, -2.55)[rank],
      label_text = gsub("^ssl_", "SSL ", feature)
    )
  scree <- tibble(index = seq_along(pca$sdev), variance = (pca$sdev^2) / sum(pca$sdev^2)) %>% slice_head(n = 10)

  p_top <- ggplot(pca_df, aes(PC1, color = phenotype, fill = phenotype)) +
    geom_density(alpha = 0.22, linewidth = 0.35) +
    scale_color_manual(values = phenotype_colors) +
    scale_fill_manual(values = phenotype_colors) +
    theme_prism() +
    theme(axis.title = element_blank(), axis.text = element_blank(), axis.ticks = element_blank(), legend.position = "none", panel.grid = element_blank())

  p_scatter <- ggplot(pca_df, aes(PC1, PC2, color = phenotype, fill = phenotype)) +
    geom_point(size = 0.46, alpha = 0.24, stroke = 0) +
    stat_ellipse(type = "norm", geom = "polygon", alpha = 0.06, color = NA) +
    stat_ellipse(type = "norm", linewidth = 0.45) +
    geom_segment(data = loadings, aes(x = 0, y = 0, xend = xend, yend = yend), inherit.aes = FALSE, arrow = arrow(length = unit(1.4, "mm")), color = "#545A66", linewidth = 0.35) +
    geom_segment(data = loadings, aes(x = xend, y = yend, xend = label_x, yend = label_y), inherit.aes = FALSE, color = "#9AA0AA", linewidth = 0.20) +
    geom_label(data = loadings, aes(x = label_x, y = label_y, label = label_text), inherit.aes = FALSE, size = 1.48, color = "#454A56", fill = "#FFFFFF", label.size = 0.10, label.padding = unit(0.38, "mm")) +
    scale_color_manual(values = phenotype_colors) +
    scale_fill_manual(values = phenotype_colors) +
    labs(x = "PC1", y = "PC2") +
    theme_prism() +
    theme(legend.position = "right")

  p_right <- ggplot(pca_df, aes(PC2, color = phenotype, fill = phenotype)) +
    geom_density(alpha = 0.22, linewidth = 0.35) +
    coord_flip() +
    scale_color_manual(values = phenotype_colors) +
    scale_fill_manual(values = phenotype_colors) +
    theme_prism() +
    theme(axis.title = element_blank(), axis.text = element_blank(), axis.ticks = element_blank(), legend.position = "none", panel.grid = element_blank())

  p_scree <- ggplot(scree, aes(index, variance * 100)) +
    geom_col(fill = light_blue, color = "white", width = 0.72) +
    geom_line(color = navy, linewidth = 0.45) +
    geom_point(color = navy, size = 1.0) +
    scale_x_continuous(breaks = c(1, 5, 10)) +
    labs(x = "PC", y = "Var., %") +
    theme_prism()

  top_row <- wrap_plots(list(p_top, p_scree), ncol = 2, widths = c(2.65, 0.88))
  bottom_row <- wrap_plots(list(p_scatter, p_right), ncol = 2, widths = c(2.65, 0.88))
  panel <- wrap_plots(list(top_row, bottom_row), ncol = 1, heights = c(0.48, 1.82))
  save_panel(panel, "F3A", "F3A__v1__native_patchwork_pca_quad", 5.4, 4.55)
}

render_f3c <- function() {
  metrics <- read_tsv_base(file.path(tables_dir, "k_selection_metrics_k2_8_prism.tsv"))
  write_tsv_base(metrics, file.path(intermediate, "F3C__v1__stability_metrics_patchwork__input_mapped.tsv"))
  metric_long <- metrics %>%
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
  p_heat <- ggplot(metric_long, aes(factor(k), metric, fill = score)) +
    geom_tile(color = "white", linewidth = 0.45) +
    geom_tile(data = metric_long %>% filter(k == 3), aes(factor(k), metric), fill = NA, color = navy, linewidth = 0.95) +
    scale_fill_gradient(low = pale_yellow, high = navy, limits = c(0, 1)) +
    labs(x = "Number of clusters", y = NULL) +
    theme_prism() +
    theme(panel.grid = element_blank(), legend.position = "right")
  p_sil <- ggplot(metrics, aes(k, silhouette)) +
    geom_line(color = navy, linewidth = 0.55) +
    geom_point(aes(fill = selected), shape = 21, size = 1.8, color = navy) +
    scale_fill_manual(values = c(`FALSE` = "white", `TRUE` = blue)) +
    scale_x_continuous(breaks = 2:8) +
    labs(x = "k", y = "Silhouette width") +
    theme_prism() +
    theme(legend.position = "none")
  p_ari <- ggplot(metrics, aes(k, bootstrap_ari_mean)) +
    geom_errorbar(aes(ymin = bootstrap_ari_mean - 1.96 * bootstrap_ari_sd, ymax = bootstrap_ari_mean + 1.96 * bootstrap_ari_sd), color = blue, width = 0.18, linewidth = 0.45) +
    geom_line(color = navy, linewidth = 0.55) +
    geom_point(aes(fill = selected), shape = 21, size = 1.8, color = navy) +
    scale_fill_manual(values = c(`FALSE` = "white", `TRUE` = blue)) +
    scale_x_continuous(breaks = 2:8) +
    labs(x = "k", y = "Bootstrap ARI") +
    theme_prism() +
    theme(legend.position = "none")
  bottom <- wrap_plots(list(p_sil, p_ari), ncol = 2, widths = c(1, 1.35))
  panel <- wrap_plots(list(p_heat, bottom), ncol = 1, heights = c(1.1, 0.85))
  save_panel(panel, "F3C", "F3C__v1__stability_metrics_patchwork", 4.8, 3.75)
}

render_f4 <- function() {
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
  write_tsv_base(as.data.frame(zmat) %>% mutate(variable = rownames(zmat), .before = 1), file.path(intermediate, "F4__v1__ComplexHeatmap_annotated__input_mapped.tsv"))

  test_counts <- assignments %>% filter(cycle == "2022_2023") %>% count(phenotype) %>% mutate(phenotype = paste0("P", phenotype), prevalence = n / sum(n))
  risk_bar <- enrichment %>% group_by(phenotype) %>% summarise(mean_pr = mean(prevalence_ratio, na.rm = TRUE), .groups = "drop") %>% mutate(phenotype = paste0("P", phenotype))
  domain_levels <- c("Demographic/social", "Partnership", "Sex/contraception", "Pregnancy history", "Fertility health", "Other/skip")
  domain_colors <- c("Demographic/social" = navy, "Partnership" = blue, "Sex/contraception" = light_blue, "Pregnancy history" = lilac, "Fertility health" = pale_yellow, "Other/skip" = "#C5CAD6")
  row_domain <- factor(prof$domain, levels = domain_levels)
  profile_type <- ifelse(apply(mat, 1, function(x) all(x >= -0.05 & x <= 1.05, na.rm = TRUE)), "Binary/proportion", "Continuous/count")
  endpoint_related <- ifelse(grepl("contraceptive|fertility|pregnancy|fecundity|adverse", tolower(prof$variable_label)), "Endpoint-proximal", "Profile input")
  top_anno <- HeatmapAnnotation(
    prevalence = anno_barplot(test_counts$prevalence, gp = gpar(fill = light_blue, col = NA), height = unit(7, "mm"), border = FALSE, axis = FALSE),
    mean_PR = anno_points(risk_bar$mean_pr, gp = gpar(col = navy), size = unit(1.5, "mm"), height = unit(5, "mm"), axis = FALSE),
    show_annotation_name = FALSE
  )
  left_anno <- rowAnnotation(
    Domain = row_domain,
    col = list(Domain = domain_colors),
    show_legend = FALSE,
    show_annotation_name = FALSE,
    width = unit(3, "mm")
  )
  right_anno <- rowAnnotation(
    Type = profile_type,
    Endpoint = endpoint_related,
    col = list(Type = c("Binary/proportion" = light_blue, "Continuous/count" = lilac), Endpoint = c("Endpoint-proximal" = navy, "Profile input" = "#D1D5DD")),
    show_legend = FALSE,
    show_annotation_name = FALSE,
    width = unit(5, "mm")
  )
  ht <- left_anno + Heatmap(
    zmat,
    name = "z profile",
    col = colorRamp2(c(-1.4, 0, 1.4), c(lilac, "white", navy)),
    top_annotation = top_anno,
    right_annotation = right_anno,
    cluster_rows = FALSE,
    cluster_columns = FALSE,
    row_names_gp = gpar(fontsize = 5.4),
    column_names_gp = gpar(fontsize = 6.5, fontface = "bold"),
    column_names_rot = 0,
    row_title = NULL,
    row_title_gp = gpar(fontsize = 5.5),
    heatmap_legend_param = list(title_gp = gpar(fontsize = 6.5), labels_gp = gpar(fontsize = 6)),
    column_title = "Survey-weighted phenotype profile",
    column_title_gp = gpar(fontsize = 7.5, fontface = "bold")
  )
  pdf_path <- file.path(outputs, "F4", "F4__v1__ComplexHeatmap_annotated.pdf")
  png_path <- file.path(outputs, "F4", "F4__v1__ComplexHeatmap_annotated.png")
  svg_path <- file.path(outputs, "F4", "F4__v1__ComplexHeatmap_annotated.svg")
  pdf(pdf_path, width = 4.8, height = 3.85)
  draw(ht, heatmap_legend_side = "right", annotation_legend_side = "right")
  dev.off()
  png(png_path, width = 1440, height = 1155, res = 300)
  draw(ht, heatmap_legend_side = "right", annotation_legend_side = "right")
  dev.off()
  svg(svg_path, width = 4.8, height = 3.85)
  draw(ht, heatmap_legend_side = "right", annotation_legend_side = "right")
  dev.off()
}

render_f3a()
render_f3c()
render_f4()
message("Panel-wise R redraw finished: F3A, F3C, F4")
