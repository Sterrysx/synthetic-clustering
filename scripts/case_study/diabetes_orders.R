# Case study robustness: the six orders in which the three variables can be
# synthesised (clinical class always last), same settings and seeds as
# diabetes_synth.R. The order glucose-insulin-sspg is diabetes_synthetic.csv;
# the other five are written as diabetes_synthetic_<order>.csv.
suppressPackageStartupMessages({library(rrcov); library(synthpop)})
args <- commandArgs(trailingOnly = TRUE)
M    <- if (length(args)) as.integer(args[1]) else 1000L
BASE <- 20260930L
out  <- file.path("results", "case_study")
data(diabetes, package = "rrcov")
od0  <- diabetes[, c("glucose", "insulin", "sspg", "group")]
# the first entry re-creates diabetes_synthetic.csv as a reproducibility check
perm <- list(c("glucose","insulin","sspg"), c("glucose","sspg","insulin"), c("insulin","glucose","sspg"), c("insulin","sspg","glucose"),
             c("sspg","glucose","insulin"), c("sspg","insulin","glucose"))
for (v in perm) {
  od <- od0[, c(v, "group")]
  sd <- vector("list", M)
  for (m in seq_len(M)) {
    invisible(capture.output({
      s <- suppressMessages(suppressWarnings(
        syn(od, method = "cart", m = 1, seed = BASE + m, print.flag = FALSE,
            proper = TRUE, cart.minbucket = 10)))
    }))
    x <- s$syn[, c("glucose", "insulin", "sspg", "group")]; x$syn <- m; sd[[m]] <- x
  }
  f <- file.path(out, sprintf("diabetes_synthetic_%s.csv", paste(v, collapse = "-")))
  write.csv(do.call(rbind, sd), f, row.names = FALSE)
  cat(f, "\n")
}
