# Case study: CART synthesis of the Reaven & Miller (1979) diabetes data.
# Uses rrcov::diabetes (the mclust copy has its columns shifted: its "glucose"
# is fasting plasma glucose, "insulin" is the glucose area, "sspg" the insulin area).
# Variables: glucose, insulin, sspg (the three used by Reaven & Miller), with the
# clinical class appended last in the synthesis sequence, as in the simulation.
# Output: results/case_study/diabetes_original.csv, diabetes_synthetic.csv (m draws, long).
suppressPackageStartupMessages({library(rrcov); library(synthpop)})
args <- commandArgs(trailingOnly = TRUE)
M    <- if (length(args)) as.integer(args[1]) else 1000L
BASE <- 20260930L
out  <- file.path("results", "case_study")
dir.create(out, showWarnings = FALSE, recursive = TRUE)
data(diabetes, package = "rrcov")
od <- diabetes[, c("glucose", "insulin", "sspg", "group")]
write.csv(od, file.path(out, "diabetes_original.csv"), row.names = FALSE)
t0 <- Sys.time()
sd <- vector("list", M)
for (m in seq_len(M)) {
  invisible(capture.output({
    s <- suppressMessages(suppressWarnings(
      syn(od, method = "cart", m = 1, seed = BASE + m, print.flag = FALSE,
          proper = TRUE, cart.minbucket = 10)))
  }))
  x <- s$syn; x$syn <- m; sd[[m]] <- x
}
sd <- do.call(rbind, sd)
write.csv(sd, file.path(out, "diabetes_synthetic.csv"), row.names = FALSE)
info <- list(M = M, base_seed = BASE, n = nrow(od), seconds = as.numeric(difftime(Sys.time(), t0, units = "secs")),
             R = R.version.string, synthpop = as.character(packageVersion("synthpop")),
             rpart = as.character(packageVersion("rpart")), rrcov = as.character(packageVersion("rrcov")))
jsonlite::write_json(info, file.path(out, "diabetes_synth_info.json"), auto_unbox = TRUE, pretty = TRUE)
cat(sprintf("%d draws, %.0f s\n", M, info$seconds))
