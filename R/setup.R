# Install the R packages the generation scripts need.
#
#   Rscript R/setup.R
#
# Installs into your personal library, creating it if necessary. Never touches
# the system library, so no root is needed. Run once per machine.
#
# Non-interactive Rscript will NOT offer to create a personal library the way an
# interactive R session does -- it just fails with "lib is not writable". That is
# why this script computes and creates the path explicitly.

# Resolve the repo from this script's own path, so it works from any directory
# (same convention as the generation scripts). SYNTHCLUST_DATA relocates the
# datasets without moving the code.
.args <- commandArgs(trailingOnly = FALSE)
.f <- grep("^--file=", .args, value = TRUE)
REPO <- if (length(.f)) {
  dirname(dirname(normalizePath(sub("^--file=", "", .f[1]))))
} else {
  normalizePath("..")
}
DATA_ROOT <- Sys.getenv("SYNTHCLUST_DATA", unset = REPO)

lib <- Sys.getenv("R_LIBS_USER")
if (!nzchar(lib) || lib == "NULL") {
  lib <- file.path(
    "~", "R",
    paste0(R.version$platform, "-library"),
    paste(R.version$major,
          strsplit(R.version$minor, ".", fixed = TRUE)[[1]][1],
          sep = ".")
  )
}
lib <- path.expand(lib)

if (!dir.exists(lib)) {
  dir.create(lib, recursive = TRUE, showWarnings = FALSE)
  cat("created personal library:", lib, "\n")
}
if (file.access(lib, 2) != 0) {
  stop("personal library is not writable: ", lib, call. = FALSE)
}
.libPaths(c(lib, .libPaths()))

cat("installing into:", lib, "\n\n")

needed <- c("jsonlite", "mvtnorm", "arrow", "synthpop")
missing <- needed[!(needed %in% rownames(installed.packages()))]

if (!length(missing)) {
  cat("all packages already present\n")
} else {
  cat("missing:", paste(missing, collapse = ", "), "\n\n")
  install.packages(missing, lib = lib, repos = "https://cloud.r-project.org")
}

cat("\n--- result ---\n")
still <- needed[!(needed %in% rownames(installed.packages()))]
for (p in needed) {
  cat(sprintf("  %-10s %s\n", p,
              if (p %in% still) "MISSING" else
                as.character(packageVersion(p, lib.loc = .libPaths()))))
}

# A minimal arrow build (the default when it falls back to source without
# libarrow) lacks some parquet codecs and fails only at READ time with
# "Support for codec 'x' not built".
#
# The test is empirical: actually read an existing dataset file. Checking a
# hardcoded codec is wrong -- this project writes uncompressed parquet by
# default, so demanding zstd support would block a setup that works fine.
if (!("arrow" %in% still)) {
  cat("\n--- arrow parquet support ---\n")
  caps <- tryCatch(arrow::arrow_info()$capabilities,
                   error = function(e) NULL)
  if (!is.null(caps)) {
    for (cc in c("uncompressed", "snappy", "gzip", "zstd")) {
      if (cc %in% names(caps)) cat(sprintf("  %-14s %s\n", cc, caps[[cc]]))
    }
  }

  # Read a real file if any dataset exists yet. This is the only check that
  # matters: it exercises whatever codec the data on disk actually uses.
  probe <- character(0)
  for (d in c(file.path(DATA_ROOT, "data", "original"),
              file.path(DATA_ROOT, "data", "synthetic"))) {
    if (dir.exists(d)) {
      f <- head(list.files(d, pattern = "\\.parquet$", full.names = TRUE), 1)
      if (length(f)) probe <- c(probe, f)
    }
  }

  if (!length(probe)) {
    cat("  no dataset files yet -- codec support will be exercised on first read\n")
  } else {
    for (f in probe) {
      res <- tryCatch({
        d <- arrow::read_parquet(f)
        sprintf("OK (%d rows)", nrow(d))
      }, error = function(e) paste("FAILED:", conditionMessage(e)))
      cat(sprintf("  read %-22s %s\n", basename(dirname(f)), res))
      if (grepl("^FAILED", res)) {
        cat("\n  arrow cannot read this project's parquet files.\n")
        if (grepl("codec", res)) {
          codec <- sub(".*codec '([^']+)'.*", "\\1", res)
          cat(sprintf("  The missing codec is '%s'. Two options:\n\n", codec))
          cat(sprintf(
            "  1. Convert the data to uncompressed (fast, ~4%% more disk):\n"))
          cat("       uv run convert-codec --codec uncompressed\n")
          cat("       uv run convert-codec --codec uncompressed --synthetic\n\n")
          cat("  2. Rebuild arrow with full codec support:\n")
          cat("       Rscript -e 'Sys.setenv(LIBARROW_MINIMAL=\"false\");",
              "install.packages(\"arrow\", repos=\"https://cloud.r-project.org\")'\n")
          cat("     If that still builds minimal:",
              "sudo apt install libarrow-dev libparquet-dev\n")
        }
        quit(status = 1)
      }
    }
  }
}

if (length(still)) {
  cat("\nStill missing:", paste(still, collapse = ", "), "\n")
  cat("'arrow' sometimes needs system libraries to build from source. On Debian\n")
  cat("or Ubuntu try:  sudo apt install libcurl4-openssl-dev libssl-dev\n")
  cat("then re-run this script.\n")
  quit(status = 1)
}

# Record the exact software versions and the canonical R citation. The
# manuscript has to state these (reviewer request), and citation() is the only
# authoritative source for how to cite R itself.
cat("\n--- versions for the manuscript ---\n")
cat(sprintf("  %s\n", R.version.string))
cat(sprintf("  platform  %s\n", R.version$platform))
for (p in needed) {
  if (!(p %in% still)) {
    cat(sprintf("  %-10s %s\n", p,
                as.character(packageVersion(p, lib.loc = .libPaths()))))
  }
}
cat("\n--- how to cite R (from citation()) ---\n")
print(utils::citation(), style = "text")
cat("\n--- how to cite synthpop ---\n")
if (!("synthpop" %in% still)) print(utils::citation("synthpop"), style = "text")

cat("\nReady. Next:  Rscript R/generate_synthetic.R\n")
