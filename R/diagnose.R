# Time ONE synthesis task and report any error in full.
#
#   Rscript R/diagnose.R
#
# One task = one (OD file, syn_idx) pair = 5 syn() calls (one per replicate)
# = one output parquet. Multiply the reported per-task time by
# 144 * m / n_workers to get the expected wall time of a full run.

suppressWarnings(suppressPackageStartupMessages({
  library(jsonlite); library(synthpop); library(arrow)
}))

script_path <- local({
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grepl("^--file=", a)])
  if (length(f)) normalizePath(f[1]) else NA_character_
})
REPO <- if (!is.na(script_path)) dirname(dirname(script_path)) else normalizePath("..")
DATA_ROOT <- Sys.getenv("SYNTHCLUST_DATA", unset = REPO)

cat("repo      :", REPO, "\n")
cat("data root :", DATA_ROOT, "\n")
cat("SYNTHCLUST_DATA env:",
    if (nzchar(Sys.getenv("SYNTHCLUST_DATA"))) Sys.getenv("SYNTHCLUST_DATA") else "(unset)", "\n")

cfg <- fromJSON(file.path(REPO, "config.json"))
cat("config m  :", cfg$simulation$m, "\n\n")

in_dir  <- file.path(DATA_ROOT, "data", "original")
out_dir <- file.path(DATA_ROOT, "data", "synthetic")
cat("input  dir:", in_dir,  "exists =", dir.exists(in_dir),  "\n")
cat("output dir:", out_dir, "exists =", dir.exists(out_dir),
    "writable =", dir.exists(out_dir) && file.access(out_dir, 2) == 0, "\n")
cat("output dir currently holds", length(list.files(out_dir)), "files\n\n")

od_files <- sort(list.files(in_dir, pattern = "^OD_.*[.]parquet$", full.names = TRUE))
if (!length(od_files)) stop("no OD files in ", in_dir)
cat("OD files found:", length(od_files), "\n")

# Pick the largest scenario (p=10) -- the slowest case, so the estimate is conservative.
target <- grep("p10", od_files, value = TRUE)[1]
if (is.na(target)) target <- od_files[1]
cat("using:", basename(target), "\n\n")

od_full <- as.data.frame(read_parquet(target))
cat("dims:", nrow(od_full), "x", ncol(od_full),
    "| columns:", paste(names(od_full), collapse = ", "), "\n")
reps <- sort(unique(od_full$rep))
cat("replicates:", paste(reps, collapse = ", "), "\n\n")

cat("--- timing 5 syn() calls (one task) ---\n")
t_task <- system.time({
  for (r in reps) {
    od_rep <- od_full[od_full$rep == r, ]
    od_rep$rep <- NULL
    t1 <- system.time({
      res <- tryCatch({
        invisible(capture.output({
          s <- suppressMessages(suppressWarnings(
            syn(od_rep, method = "cart", m = 1, seed = 12345 + r,
                print.flag = FALSE, proper = TRUE, cart.minbucket = 10)
          ))
        }))
        "ok"
      }, error = function(e) paste("ERROR:", conditionMessage(e)))
    })
    cat(sprintf("  rep %d: %5.2f s  %s\n", r, t1[["elapsed"]], res))
    if (startsWith(res, "ERROR")) quit(status = 1)
  }
})
per_task <- t_task[["elapsed"]]
cat(sprintf("\none task (5 reps): %.1f s\n", per_task))

cat("\n--- write test ---\n")
probe <- file.path(out_dir, ".diagnose_probe.parquet")
w <- tryCatch({
  write_parquet(od_full, probe)
  sz <- file.size(probe); file.remove(probe)
  sprintf("ok, %.0f KB", sz / 1024)
}, error = function(e) paste("ERROR:", conditionMessage(e)))
cat("  write_parquet:", w, "\n")

cat("\n--- projected wall time ---\n")
for (nw in c(6, 12, 18)) {
  for (m in unique(c(100, cfg$simulation$m))) {
    tasks <- length(od_files) * m
    cat(sprintf("  m=%-5d %2d workers: %6.1f h  (%d tasks)\n",
                m, nw, tasks * per_task / nw / 3600, tasks))
  }
}
cat("\nNote: p=10 is the slowest scenario, so these are upper bounds.\n")
