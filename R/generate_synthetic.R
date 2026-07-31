# ==============================================================================
# SCRIPT: 02_generate_synthetic_data.R
# PURPOSE: Generate Synthetic Data (SD) from each Original Data (OD) parquet
#          file using synthpop (cart method).
#          ** FULL DYNAMIC QUEUE (WORK STEALING) APPLIED **
# ==============================================================================

# 1. Setup & Imports
# ------------------------------------------------------------------------------
# Required packages are NOT auto-installed: installing into a system library
# needs root, and silently writing to /usr/local/lib/R is the wrong default for
# a reproducibility script. Install them once with  Rscript R/setup.R
local({
  need <- c("jsonlite", "synthpop", "arrow")
  miss <- need[!(need %in% rownames(installed.packages()))]
  if (length(miss)) {
    stop("missing R packages: ", paste(miss, collapse = ", "),
         "\n  install them with:\n    Rscript R/setup.R",
         "\n  library paths currently searched:\n    ",
         paste(.libPaths(), collapse = "\n    "), call. = FALSE)
  }
})
suppressWarnings(suppressPackageStartupMessages(library(jsonlite)))

# 2. Locate the repository, independently of the working directory
# ------------------------------------------------------------------------------
# Resolved from this script's own path, so the script can be run from anywhere
# (repo root, R/, or by absolute path). SYNTHCLUST_DATA overrides where the
# datasets live, matching src/synthclust/paths.py.
script_path <- local({
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grepl("^--file=", a)])
  if (length(f)) normalizePath(f[1]) else NA_character_
})
REPO <- if (!is.na(script_path)) dirname(dirname(script_path)) else normalizePath("..")
DATA_ROOT <- Sys.getenv("SYNTHCLUST_DATA", unset = REPO)

config_path <- file.path(REPO, "config.json")
if (!file.exists(config_path)) stop("config.json not found at: ", config_path)

config     <- fromJSON(config_path)
m_syn      <- config$simulation$m             # number of synthetic reps per OD rep
base_seed  <- config$simulation$random_seed_base

# Parquet codec for the outputs. Default is uncompressed: on this data ZSTD
# saves only ~2.4% (float64 noise is close to incompressible), and an `arrow`
# built without ZSTD support -- the common outcome when it falls back to a
# source build -- cannot read or write those files at all. The 2.4% is not
# worth a toolchain dependency. Override with:
#   export SYNTHCLUST_PARQUET_CODEC=zstd
PARQUET_CODEC <- Sys.getenv("SYNTHCLUST_PARQUET_CODEC", unset = "uncompressed")
local({
  # Fail now, not 10,000 files into the run. R arrow spells "no compression" as
  # "uncompressed" (pyarrow calls it "none"); accept either.
  valid <- c("uncompressed", "none", "snappy", "gzip", "zstd", "lz4", "brotli")
  if (!(PARQUET_CODEC %in% valid)) {
    stop("SYNTHCLUST_PARQUET_CODEC='", PARQUET_CODEC, "' is not recognised.\n",
         "  valid: ", paste(valid, collapse = ", "), call. = FALSE)
  }
  if (PARQUET_CODEC == "zstd" && !isTRUE(arrow::arrow_info()$capabilities[["zstd"]])) {
    stop("codec 'zstd' requested but this arrow build lacks ZSTD support.\n",
         "  run  Rscript R/setup.R  for the fix, or use the default",
         " (uncompressed).", call. = FALSE)
  }
})
if (PARQUET_CODEC == "none") PARQUET_CODEC <- "uncompressed"   # R arrow's spelling
cat(sprintf("[INFO] parquet codec: %s\n", PARQUET_CODEC))

cat(sprintf("[INFO] repo:      %s\n", REPO))
cat(sprintf("[INFO] data root: %s\n", DATA_ROOT))
cat(sprintf("[INFO] Synthetic reps per OD rep: %d (method = cart)\n", m_syn))

# 3. Discover OD files
# ------------------------------------------------------------------------------
input_dir  <- file.path(DATA_ROOT, "data", "original")
output_dir <- file.path(DATA_ROOT, "data", "synthetic")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

od_files <- sort(list.files(input_dir, pattern = "^OD_.*\\.parquet$", full.names = TRUE))
if (length(od_files) == 0) {
  stop("[ERROR] No OD parquet files found in: ", input_dir,
       "\n        Run 01_generate_original_data.R first.")
}

# Each OD file generates m_syn SD files
total_tasks <- length(od_files) * m_syn
cat(sprintf("[INFO] Found %d OD file(s) x %d syn reps = %d SD file(s) to generate.\n",
            length(od_files), m_syn, total_tasks))

# 4. Build Atomic Task Queue
# ------------------------------------------------------------------------------
# Worker processes. Override with SYNTHCLUST_WORKERS to match your machine;
# see "Adapting the parallelism to your hardware" in the README.
.w <- Sys.getenv("SYNTHCLUST_WORKERS")
NUM_CORES <- if (nzchar(.w)) max(1L, as.integer(.w)) else max(1L, parallel::detectCores() - 6L)

todo_dir  <- file.path(tempdir(), "sd_clust_tasks_todo")
doing_dir <- file.path(tempdir(), "sd_clust_tasks_doing")
unlink(todo_dir, recursive = TRUE); unlink(doing_dir, recursive = TRUE)
dir.create(todo_dir, showWarnings = FALSE)
dir.create(doing_dir, showWarnings = FALSE)

task_i <- 1L
set.seed(999)
shuffled_od <- sample(od_files)

for (od_path in shuffled_od) {
  for (syn_idx in seq_len(m_syn)) {
    task_data <- list(file = od_path, syn_idx = syn_idx)
    saveRDS(task_data, file.path(todo_dir, sprintf("task_%05d.rds", task_i)))
    task_i <- task_i + 1L
  }
}

cat(sprintf("[INFO] Dynamic Queue built. %d tasks ready for %d cores.\n\n",
            total_tasks, NUM_CORES))

# 5. Generate Independent Worker Script
# ------------------------------------------------------------------------------
worker_script <- file.path(tempdir(), "sd_clust_worker.R")
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
  "  library(jsonlite)",
  "  library(synthpop)",
  "  library(arrow)",
  "}))",
  "arrow::set_cpu_count(1)",
  "",
  sprintf("config <- fromJSON('%s')", config_path),
  "base_seed <- config$simulation$random_seed_base",
  sprintf("output_dir <- '%s'", output_dir),
  "",
  sprintf("full_od_files <- sort(list.files('%s',", input_dir),
  "                                  pattern = '^OD_.*[.]parquet$', full.names = TRUE))",
  "",
  "results <- list()",
  "writeLines('READY', progress_file)",
  "",
  "# WORK STEALING LOOP",
  "#",
  "# The queue is scanned in batches. Listing the whole todo directory on every",
  "# iteration costs O(queue size) per task: at 144,000 tasks a single listing is",
  "# ~36 ms, so 144,000 iterations spend over an hour just enumerating files.",
  "# Fetching a block of candidates and working through it amortises that away.",
  "batch <- character(0)",
  "repeat {",
  "  if (!length(batch)) {",
  "    batch <- list.files(todo_dir, full.names = TRUE)[seq_len(200)]",
  "    batch <- batch[!is.na(batch)]",
  "    if (!length(batch)) break",
  "  }",
  "",
  "  target_task <- batch[1]",
  "  batch <- batch[-1]",
  "  if (!file.exists(target_task)) next   # claimed by another worker",
  "  claimed_task <- file.path(doing_dir, basename(target_task))",
  "",
  "  if (file.rename(target_task, claimed_task)) {",
  "    task <- readRDS(claimed_task)",
  "    od_path  <- task$file",
  "    syn_idx  <- task$syn_idx",
  "    od_name  <- basename(od_path)",
  "",
  "    # Build SD output name: SD_cart_<scenario>_syn<idx>.parquet",
  "    scenario_tag <- sub('^OD_', '', sub('[.]parquet$', '', od_name))",
  "    sd_name <- sprintf('SD_cart_%s_syn%d', scenario_tag, syn_idx)",
  "",
  "    out_path <- file.path(output_dir, paste0(sd_name, '.parquet'))",
  "    if (file.exists(out_path)) {",
  "      # Already present: not regenerated. Reported separately so a run that",
  "      # only re-checks existing files cannot look like a successful synthesis.",
  "      results[[length(results) + 1L]] <- list(status = 'skipped', file = sd_name)",
  "      file.remove(claimed_task)",
  "      next",
  "    }",
  "",
  "    writeLines(paste('CART |', scenario_tag, 'syn', syn_idx), progress_file)",
  "",
  "    tryCatch({",
  "      od_full <- as.data.frame(read_parquet(od_path))",
  "      global_idx <- match(od_path, full_od_files)",
  "",
  "      x_cols <- grep('^X[0-9]+$', names(od_full), value = TRUE)",
  "      reps <- sort(unique(od_full$rep))",
  "",
  "      sd_list <- list()",
  "      for (r in reps) {",
  "        od_rep <- od_full[od_full$rep == r, ]",
  "        od_rep$rep <- NULL",
  "",
  "        # Stride must exceed the largest intended m. At the original",
  "        # 10000/100 stride, m > 100 made syn_idx overrun into the next",
  "        # replicate's range: rep 1 draw 200 and rep 2 draw 100 collided.",
  "        # 100000 slots per replicate, 10^7 per scenario, supports m <= 99999.",
  "        syn_seed <- base_seed + (global_idx * 10000000L) + (r * 100000L) + syn_idx",
  "",
  "        invisible(capture.output({",
  "          syn_obj <- suppressMessages(suppressWarnings(",
  "            syn(od_rep, method = 'cart', m = 1, seed = syn_seed,",
  "                print.flag = FALSE, proper = TRUE, cart.minbucket = 10)",
  "          ))",
  "        }))",
  "        sd <- syn_obj$syn",
  "        sd$rep <- as.integer(r)",
  "        sd_list[[length(sd_list) + 1L]] <- sd",
  "      }",
  "",
  "      combined <- do.call(rbind, sd_list)",
  "      # Write to a temporary and rename. rename() is atomic within a",
  "      # filesystem, so the final path never exists in a half-written state.",
  "      # Without this, killing the run mid-write leaves a truncated parquet",
  "      # that the resume check (file.exists) would accept and skip forever.",
  "      tmp_out <- paste0(out_path, '.tmp', Sys.getpid())",
  sprintf("      write_parquet(combined, tmp_out, compression = '%s')", PARQUET_CODEC),
  "      if (!file.rename(tmp_out, out_path)) {",
  "        unlink(tmp_out)",
  "        stop('could not rename temporary output to ', out_path)",
  "      }",
  "",
  "      results[[length(results) + 1L]] <- list(status = 'ok', file = sd_name)",
  "    }, error = function(e) {",
  "      results[[length(results) + 1L]] <<- list(status = 'error',",
  "                                                message = e$message, file = od_name)",
  "    })",
  "",
  "    file.remove(claimed_task)",
  "  }",
  "}",
  "",
  "writeLines('DONE', progress_file)",
  "saveRDS(results, result_file)"
)
writeLines(worker_code, worker_script)

# 6. Launch background workers
# ------------------------------------------------------------------------------
progress_files <- character(NUM_CORES)
result_files   <- character(NUM_CORES)

for (i in seq_len(NUM_CORES)) {
  progress_files[i] <- file.path(tempdir(), sprintf("sd_clust_prog_%02d.txt", i))
  result_files[i]   <- file.path(tempdir(), sprintf("sd_clust_res_%02d.rds", i))

  writeLines("STARTING", progress_files[i])
  if (file.exists(result_files[i])) file.remove(result_files[i])

  system2("Rscript", args = c(worker_script, progress_files[i], result_files[i],
                               todo_dir, doing_dir), wait = FALSE)
}

# 7. Live Unified Progress Display
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
  done_count  <- total_tasks - todo_count - doing_count

  pct     <- if (total_tasks > 0) as.integer(round(done_count / total_tasks * 100)) else 0
  bar     <- make_bar(done_count, total_tasks)
  elapsed <- as.integer(proc.time()[[3]] - start_ts)

  cat(sprintf("\r\033[2K[INFO] [%s] %3d%% (%d/%d) | %ds elapsed\n",
              bar, pct, done_count, total_tasks, elapsed))
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

# 8. Collect results
# ------------------------------------------------------------------------------
count   <- 0L
skipped <- 0L
errors  <- 0L
warns   <- character(0)

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
    else if (r$status == "skipped") skipped <- skipped + 1L
    else {
      errors <- errors + 1L
      warns <- c(warns, sprintf("  [WARN] %s: %s", r$file, r$message))
    }
  }
}

if (length(warns) > 0L) cat("\n", paste(warns, collapse = "\n"), "\n", sep = "")

elapsed_total <- proc.time()[[3]] - start_ts
cat(sprintf("\n[DONE] %d written, %d already present (skipped), %d errors.  Wall time: %.0fs\n",
            count, skipped, errors, elapsed_total))
if (count == 0L && skipped > 0L) {
  cat("\n[NOTE] Nothing was generated -- every output file already existed.\n")
  cat(sprintf("       Output directory: %s\n", output_dir))
  cat(sprintf("       config.json has m = %d, so %d files are expected.\n",
              m_syn, length(od_files) * m_syn))
  cat("       To regenerate: move the directory aside first, e.g.\n")
  cat(sprintf("         mv %s %s_old\n", output_dir, output_dir))
}
