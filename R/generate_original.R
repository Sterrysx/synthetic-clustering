# ==============================================================================
# SCRIPT: 01_generate_original_data.R
# PURPOSE: Generate Original Data (OD) for a clustering simulation using
#          parameters from config.json.
#          ** FULL DYNAMIC QUEUE (WORK STEALING) APPLIED **
#          Outputs zstd-compressed Parquet files, one per scenario.
# ==============================================================================

# 1. Setup & Imports
# ------------------------------------------------------------------------------
# Required packages are NOT auto-installed. Install them once with
#   Rscript R/setup.R
local({
  need <- c("jsonlite", "mvtnorm", "arrow")
  miss <- need[!(need %in% rownames(installed.packages()))]
  if (length(miss)) {
    stop("missing R packages: ", paste(miss, collapse = ", "),
         "\n  install them with:\n    Rscript R/setup.R",
         "\n  library paths currently searched:\n    ",
         paste(.libPaths(), collapse = "\n    "), call. = FALSE)
  }
})
suppressWarnings(suppressPackageStartupMessages({
  library(jsonlite)
  library(mvtnorm)
  library(parallel)
  library(arrow)
}))

# 2. Locate the repository, independently of the working directory
# ------------------------------------------------------------------------------
script_path <- local({
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grepl("^--file=", a)])
  if (length(f)) normalizePath(f[1]) else NA_character_
})
REPO <- if (!is.na(script_path)) dirname(dirname(script_path)) else normalizePath("..")
DATA_ROOT <- Sys.getenv("SYNTHCLUST_DATA", unset = REPO)

config_path <- file.path(REPO, "config.json")
if (!file.exists(config_path)) stop("config.json not found at: ", config_path)

cat(sprintf("[INFO] repo:      %s\n", REPO))
cat(sprintf("[INFO] data root: %s\n", DATA_ROOT))

# Parquet codec -- see the note in generate_synthetic.R. Default uncompressed so
# a minimal `arrow` build (no ZSTD) can read the output.
PARQUET_CODEC <- Sys.getenv("SYNTHCLUST_PARQUET_CODEC", unset = "uncompressed")

config <- fromJSON(config_path)

N_val      <- config$simulation$N
n_real     <- config$simulation$n           # number of repetitions per scenario
base_seed  <- config$simulation$random_seed_base

p_vals     <- config$parameters$p
k_vals     <- config$parameters$k
sep_vals   <- config$parameters$separation
rho_vals   <- config$parameters$rho

# Parse distribution configurations
dist_configs_raw <- config$parameters$distribution
if (is.data.frame(dist_configs_raw)) {
  dist_configs <- lapply(1:nrow(dist_configs_raw), function(i) as.list(dist_configs_raw[i, , drop = FALSE]))
} else if (is.list(dist_configs_raw)) {
  dist_configs <- dist_configs_raw
} else {
  dist_configs <- list(list(name = "normal"))
}

dist_names <- sapply(dist_configs, function(x) {
  if (is.list(x) && "name" %in% names(x)) x$name
  else if (is.data.frame(x) && "name" %in% names(x)) x$name[1]
  else "unknown"
})

# 3. Helper: Centroid Generation
# ------------------------------------------------------------------------------
centroid.generation <- function(k, p, separation) {
  centroids <- matrix(NA, nrow = k, ncol = p)
  centroids[1, ] <- rep(0, p)
  if (k > 1) {
    for (i in 2:k) {
      tries <- 0
      repeat {
        vec <- rnorm(p)
        vec <- vec / sqrt(sum(vec^2)) * separation
        dists <- sqrt(rowSums((centroids[1:(i-1), , drop = FALSE] -
                                 matrix(vec, nrow = i-1, ncol = p, byrow = TRUE))^2))
        if (all(dists >= separation)) { centroids[i, ] <- vec; break }
        tries <- tries + 1
        if (tries > 1000) stop(paste("Could not generate separated centroids for k=", k, "p=", p))
      }
    }
  }
  centroids
}

# 4. Build scenario grid (No iteration explosion — reps are inside the worker)
# ------------------------------------------------------------------------------
param_grid <- expand.grid(
  p        = p_vals,
  k        = k_vals,
  sep      = sep_vals,
  rho      = rho_vals,
  dist_idx = seq_along(dist_configs),
  stringsAsFactors = FALSE
)

# SHUFFLE so heavy combos (large p, large k) are spread evenly across cores
set.seed(base_seed)
param_grid <- param_grid[sample(nrow(param_grid)), ]
rownames(param_grid) <- NULL
n_scenarios <- nrow(param_grid)

cat(sprintf("[INFO] Parameter grid: %d unique scenarios (x %d reps each).\n",
            n_scenarios, n_real))
cat(sprintf("[INFO] Distributions: %s\n", paste(dist_names, collapse = ", ")))

# 5. Prepare directories
# ------------------------------------------------------------------------------
output_dir <- file.path(DATA_ROOT, "data", "original")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

NUM_CORES <- max(1L, detectCores() - 6L)

# 6. Build Atomic Task Queue
# ------------------------------------------------------------------------------
todo_dir  <- file.path(tempdir(), "od_clust_tasks_todo")
doing_dir <- file.path(tempdir(), "od_clust_tasks_doing")
unlink(todo_dir, recursive = TRUE); unlink(doing_dir, recursive = TRUE)
dir.create(todo_dir, showWarnings = FALSE)
dir.create(doing_dir, showWarnings = FALSE)

set.seed(base_seed)
param_grid$scenario_seed <- sample.int(.Machine$integer.max, n_scenarios)

for (i in seq_len(n_scenarios)) {
  row <- param_grid[i, ]
  dist_cfg  <- dist_configs[[row$dist_idx]]
  dist_name <- dist_names[row$dist_idx]

  scenario_key <- sprintf("OD_N%d_p%d_k%d_rho%s_sep%s_%s",
                          N_val, row$p, row$k, row$rho, row$sep, dist_name)

  task_data <- list(
    scenario_key = scenario_key,
    N            = as.integer(N_val),
    p_cur        = as.integer(row$p),
    k_cur        = as.integer(row$k),
    sep_cur      = row$sep,
    rho_cur      = row$rho,
    dist_config  = dist_cfg,
    dist_name    = dist_name,
    seed         = row$scenario_seed,
    n_reps       = n_real
  )
  saveRDS(task_data, file.path(todo_dir, sprintf("task_%05d.rds", i)))
}

cat(sprintf("[INFO] Dynamic Queue built. %d scenario tasks ready for %d cores.\n\n",
            n_scenarios, NUM_CORES))

# 7. Generate Independent Worker Script
# ------------------------------------------------------------------------------
worker_script <- file.path(tempdir(), "od_clust_worker.R")
worker_code <- c(
  "args <- commandArgs(trailingOnly = TRUE)",
  "progress_file <- args[1]",
  "result_file <- args[2]",
  "todo_dir <- args[3]",
  "doing_dir <- args[4]",
  "",
  "Sys.setenv(OMP_NUM_THREADS = '1')",
  "Sys.setenv(OPENBLAS_NUM_THREADS = '1')",
  "Sys.setenv(MKL_NUM_THREADS = '1')",
  "",
  "suppressWarnings(suppressPackageStartupMessages({",
  "  library(mvtnorm)",
  "  library(arrow)",
  "}))",
  "arrow::set_cpu_count(1)",
  "",
  sprintf("output_dir <- '%s'", output_dir),
  "results <- list()",
  "writeLines('READY', progress_file)",
  "",
  "# Helper: centroid generation",
  "centroid.generation <- function(k, p, separation) {",
  "  centroids <- matrix(NA, nrow = k, ncol = p)",
  "  centroids[1, ] <- rep(0, p)",
  "  if (k > 1) {",
  "    for (i in 2:k) {",
  "      tries <- 0",
  "      repeat {",
  "        vec <- rnorm(p)",
  "        vec <- vec / sqrt(sum(vec^2)) * separation",
  "        dists <- sqrt(rowSums((centroids[1:(i-1), , drop = FALSE] -",
  "                                 matrix(vec, nrow = i-1, ncol = p, byrow = TRUE))^2))",
  "        if (all(dists >= separation)) { centroids[i, ] <- vec; break }",
  "        tries <- tries + 1",
  "        if (tries > 1000) stop(paste('Cannot generate centroids k=', k, 'p=', p))",
  "      }",
  "    }",
  "  }",
  "  centroids",
  "}",
  "",
  "# Helper: data generation for one rep",
  "generate_one <- function(N, p, rho, sep, k, dist_config, dist_name) {",
  "  centroids <- centroid.generation(k, p, sep)",
  "  R <- matrix(rho, nrow = p, ncol = p); diag(R) <- 1",
  "  base_n <- floor(N / k); remainder <- N %% k",
  "  csizes <- rep(base_n, k)",
  "  if (remainder > 0) csizes[1:remainder] <- csizes[1:remainder] + 1",
  "",
  "  if (dist_name == 'normal') {",
  "    clusters <- lapply(1:k, function(i) rmvnorm(csizes[i], mean = centroids[i,], sigma = R))",
  "  } else if (dist_name == 'gamma') {",
  "    shape_p <- dist_config$shape; rate_p <- dist_config$rate",
  "    clusters <- lapply(1:k, function(i) {",
  "      gd <- matrix(rgamma(csizes[i] * p, shape = shape_p, rate = rate_p), nrow = csizes[i], ncol = p)",
  "      gd <- scale(gd)",
  "      gd <- gd %*% chol(R)",
  "      sweep(gd, 2, centroids[i,], '+')",
  "    })",
  "  } else { stop(paste('Unknown distribution:', dist_name)) }",
  "",
  "  data <- do.call(rbind, clusters)",
  "  df <- as.data.frame(data); colnames(df) <- paste0('X', 1:p)",
  "  df$group <- factor(rep(1:k, times = csizes))",
  "  df",
  "}",
  "",
  "# WORK STEALING LOOP",
  "repeat {",
  "  available_tasks <- list.files(todo_dir, full.names = TRUE)",
  "  if (length(available_tasks) == 0L) break",
  "",
  "  target_task <- available_tasks[1]",
  "  claimed_task <- file.path(doing_dir, basename(target_task))",
  "",
  "  if (suppressWarnings(file.rename(target_task, claimed_task))) {",
  "    task <- readRDS(claimed_task)",
  "",
  "    out_path <- file.path(output_dir, paste0(task$scenario_key, '.parquet'))",
  "    if (file.exists(out_path)) {",
  "      results[[length(results) + 1L]] <- list(status = 'ok', file = task$scenario_key)",
  "      file.remove(claimed_task)",
  "      next",
  "    }",
  "",
  "    writeLines(paste('OD |', sub('^OD_', '', task$scenario_key)), progress_file)",
  "",
  "    tryCatch({",
  "      set.seed(task$seed)",
  "      rep_list <- vector('list', task$n_reps)",
  "",
  "      for (r in seq_len(task$n_reps)) {",
  "        df <- generate_one(task$N, task$p_cur, task$rho_cur, task$sep_cur,",
  "                           task$k_cur, task$dist_config, task$dist_name)",
  "        df$rep <- as.integer(r)",
  "        rep_list[[r]] <- df",
  "      }",
  "",
  "      combined <- do.call(rbind, rep_list)",
  sprintf("      write_parquet(combined, out_path, compression = '%s', chunk_size = task$N)",
          PARQUET_CODEC),
  "",
  "      results[[length(results) + 1L]] <- list(status = 'ok', file = task$scenario_key)",
  "      file.remove(claimed_task)",
  "    }, error = function(e) {",
  "      results[[length(results) + 1L]] <<- list(status = 'error',",
  "                                                message = e$message, file = task$scenario_key)",
  "    })",
  "  }",
  "}",
  "",
  "writeLines('DONE', progress_file)",
  "saveRDS(results, result_file)"
)
writeLines(worker_code, worker_script)

# 8. Launch background workers
# ------------------------------------------------------------------------------
progress_files <- character(NUM_CORES)
result_files   <- character(NUM_CORES)

for (i in seq_len(NUM_CORES)) {
  progress_files[i] <- file.path(tempdir(), sprintf("od_clust_prog_%02d.txt", i))
  result_files[i]   <- file.path(tempdir(), sprintf("od_clust_res_%02d.rds", i))

  writeLines("STARTING", progress_files[i])
  if (file.exists(result_files[i])) file.remove(result_files[i])

  system2("Rscript", args = c(worker_script, progress_files[i], result_files[i],
                               todo_dir, doing_dir), wait = FALSE)
}

# 9. Live Unified Progress Display
# ------------------------------------------------------------------------------
BAR_WIDTH <- 40L

make_bar <- function(done, total) {
  if (total == 0L) return(strrep("-", BAR_WIDTH))
  filled <- as.integer(round(done / total * BAR_WIDTH))
  paste0(strrep("=", filled), strrep("-", BAR_WIDTH - filled))
}

start_ts <- proc.time()[[3]]

cat(sprintf("Global Progress: [ Waiting... ]\n"))
cat(strrep("-", 80), "\n")
for (i in seq_len(NUM_CORES)) {
  cat(sprintf("   Core %-3d : STARTING\033[K\n", i))
}

repeat {
  Sys.sleep(0.5)

  cat(sprintf("\033[%dA", NUM_CORES + 2L))

  todo_count  <- length(list.files(todo_dir))
  doing_count <- length(list.files(doing_dir))
  done_count  <- n_scenarios - todo_count - doing_count

  pct     <- if (n_scenarios > 0) as.integer(round(done_count / n_scenarios * 100)) else 0
  bar     <- make_bar(done_count, n_scenarios)
  elapsed <- as.integer(proc.time()[[3]] - start_ts)

  cat(sprintf("\r\033[2K[INFO] [%s] %3d%% (%d/%d) | %ds elapsed\n",
              bar, pct, done_count, n_scenarios, elapsed))
  cat(strrep("-", 80), "\n")

  n_finish <- 0L

  for (i in seq_len(NUM_CORES)) {
    status <- "WAITING"
    if (file.exists(progress_files[i])) {
      lines <- readLines(progress_files[i], warn = FALSE)
      if (length(lines) > 0) status <- lines[1]
    }
    if (file.exists(result_files[i])) {
      status <- "DONE"; n_finish <- n_finish + 1L
    }
    if (nchar(status) > 65) status <- paste0(substr(status, 1, 62), "...")
    cat(sprintf("\r\033[2K   Core %-3d : %s\n", i, status))
  }

  if (n_finish == NUM_CORES) break
}

# 10. Collect results
# ------------------------------------------------------------------------------
count  <- 0L
errors <- 0L
warns  <- character(0)

for (i in seq_len(NUM_CORES)) {
  res_file <- result_files[i]
  if (!file.exists(res_file)) {
    errors <- errors + 1L
    warns <- c(warns, sprintf("  [FATAL] Core %d crashed entirely without saving output.", i))
    next
  }
  task_results <- readRDS(res_file)
  for (r in task_results) {
    if (r$status == "ok") count <- count + 1L
    else {
      errors <- errors + 1L
      warns <- c(warns, sprintf("  [WARN] OD | %s: %s", r$file, r$message))
    }
  }
}

if (length(warns) > 0L) cat("\n", paste(warns, collapse = "\n"), "\n", sep = "")

elapsed_total <- proc.time()[[3]] - start_ts
cat(sprintf("\n[DONE] %d scenario file(s) written, %d errors. Wall time: %.0fs\n",
            count, errors, elapsed_total))
