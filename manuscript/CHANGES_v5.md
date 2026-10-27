# Manuscript v5: changes from v4

Repository: `synthetic-clustering` (now at `~/Desktop/personal/academic/research/synthetic-clustering`;
the folder was moved during this session, see "Deviations"). v4 files are backed up in
`manuscript/_backup_v4/` (main.tex, supplementary.tex, refs.bib, supp_table.tex, figures/,
make_figures.py, and the v4 PDFs).

Line numbers refer to the v5 `manuscript/main.tex` (M) or `manuscript/supplementary.tex` (S).
Every number in v5 is read from `results/fullrange_summary.json`, `results/bootstrap_summary.json`
or `results/v5_extra_numbers.json` (new, written by `src/synthclust/v5_tables.py` from the stored
parquet files). All tables of results are generated into `manuscript/tables/*.tex` by
`v5_tables.py`; nothing in them is typed by hand.

Build: `./build.sh main` (31 pp., 0 undefined references, 0 overfull boxes) and
`./build.sh supplementary` (12 pp., 0 undefined references, 0 overfull boxes). Every page of both
PDFs was rendered and inspected.

## Deviations and open items

* **Repository moved mid-session.** Between my turns the folder `~/Desktop/academic` was moved to
  `~/Desktop/personal/academic` (not by me). All v5 files were already written and are intact at
  the new location; the final builds were run there. The `data` symlink still points to the old
  path (`~/Desktop/academic/research/ml-research/clustering/data`) and is now dangling, so
  `make_figures.py` can no longer regenerate Figs 1-2 until the link is updated (the other figures
  only need `results/`). Other files in `manuscript/` (`build.sh`, `sn-jnl.cls`, `sn-basic.bst`,
  `local.map`, `texfmt/`) were modified by someone else between 13:28 and 14:32; I did not touch them.
* **MI5, "test with independent seeds": not done.** The seeding policy is stated (M 400-421) and
  the shared `random_state = 42` is listed as a limitation (M 1203-1204), but no rerun with
  independent seeds was performed.
* **Not implemented, as instructed (not yet decided):** rerun with n = 50 / m = 100 (MA7), ARI
  (MA8), privacy / DCR metrics (MO4), real-data case study (MO7). No placeholders were added. The
  v4 Future-work mention of the adjusted Rand index and of the wearable dataset was kept as it was.
* **[Superseded in Phase 3, see end of file.] Blinding and referee format (B1, B2) not applied to main.tex.** main.tex/supplementary.tex
  remain the non-blind sn-basic build. The v4 identifying items are still present (author block,
  GitHub URL M 1360, "to which we have direct access" M 1258). `joc_prep/make_test_copies.py`
  derives the blind copies from main.tex by string edits and has not been rerun against v5; it may
  need its patterns updated.
* **Book chapters (JoC #12):** `johnson1987` chap. 4 was checked against the publisher's table of
  contents ("Multivariate Normal and Related Distributions"). `breiman1984` chap. 8 ("Regression
  Trees") is from my knowledge of the book and was not checked against a source; please confirm.
* **Benchmark package not updated.** `synthetic-clustering-benchmark/README.md` still calls the
  capped range "the paper's primary rule" and says AG "isolates the effect of synthesis"; it
  should be aligned with v5 before release.
* **New files** (besides the deliverables): `src/synthclust/v5_tables.py`,
  `results/v5_extra_numbers.json`, `results/scaling_timings.json` (copy of the stored timing
  artifact `scaling.json` used by the v4 scaling figure), `manuscript/tables/` (9 fragments),
  `manuscript/figures/figS_scaling.{pdf,png}`. The old `figures/fig_scaling.{pdf,png}` is no
  longer referenced and was left in place. `src/synthclust/recompute_metrics.py`: stale docstring
  (l. 22, "all 100 draws") corrected (MI2).
* Monte Carlo caveat carried from the bootstrap analysis: AG0 rests on B = 30 resamples per
  dataset (scenario-level SE up to about 0.04); the km-vs-Ward excess comparisons (p = 0.040
  overall, 0.024 Gamma) are described as modest evidence in the text (M 1033-1035).

## Co-author comment IDs

| ID | Decision | What was changed | Where |
|---|---|---|---|
| H1 | Do | Headline rewritten to combine Jordi's practical point and Dani's methodological point: k-means reproduces the original number of groups more often than Ward (0.839 vs 0.811), on Gamma (0.809 vs 0.731; significant at sigma = 0.1, 6, 10, not at 2) and not on Normal (0.869 vs 0.890); the bootstrap null (AG0 0.871 vs 0.826) shows this is the stability of k-means' k-hat, not smaller CART damage (excess -0.032 vs -0.016; km loses slightly more, p = 0.040, Gamma only). | Abstract M 75-87; Sect. 3.6 M 997-1037; Discussion finding 2 M 1075-1092; Conclusions M 1326-1337 |
| H2 | Do, B = 30 | Geometric floor (B = 30) reported for MCD, MVD, dG (and RVD, MCD_sd) with excess; "shows less geometric distortion" removed from the abstract; B stated in Methods. Excess is not smaller for k-means (MCD 0.081 vs 0.057, p = 8.8e-6; MVD 0.069 vs 0.068; dG 0.009 vs 0.008). | Methods 2.5 M 542-570; Sect. 3.4 M 817-938; Table 4 M 877-893; Figs 4-5 |
| H3 | Do | Gamma/Ward penalty presented as instability of the silhouette estimate: Ward's AG0 on Gamma at sigma = 0.1 is 0.515 (AG 0.511); Gamma excess for Ward between -0.041 and -0.004; the CART-specific Gamma loss is larger for k-means at sigma <= 2 (-0.086, -0.078). | Sect. 3.5 M 955-982; Table 3; Fig. 6(c,d) |
| B1 | Do | Applied in Phase 3 (see end of file): `\SetBlind` switch via `joc_prep/blind.tex`; `submission/main_blind.pdf`, `supplementary_blind.pdf`, `title_page.pdf`. | build_submission.sh |
| B2 | Do | Abstract cut to 135 words (v4: 147). Referee/12 pt layout applied in Phase 3 (`\SetReferee` via `joc_prep/joc_referee.tex`; main_blind.pdf 47 pp.). | abstract.tex; build_submission.sh |
| B3 | Do | Appendices A and B moved to the supplement (S7, S8). Main text now ends with references (31 pp. in the sn-basic layout, no appendices). | S 278-470 |
| MA1 | Do | Every "AG isolates the effect of synthesis" sentence removed (v4 l. 396, 554, 754, 789 and Supp. S2); AG now defined as removing the planted-k failure but not the sampling instability of k-hat; each method is compared with its own bootstrap null AG0. | M 459-470, 669-680, 787-816; S 71-80 |
| MA2 | Do | Floor and excess for every geometric metric (Table 4, Supp. Tables S5-S6; dashed lines in Fig. 4, hatched bars in Fig. 5). | M 817-938; S 199-245 |
| MA3 | Do | Scale-free metrics RVD and MCD_sd (and MVD/p) defined and reported; the incorrect claim that dispersion distortion declines with separation replaced (RVD excess grows: km 0.022, 0.021, 0.030, 0.035); Limitations paragraph on scaling rewritten (neither convention is free of sigma). | M 523-540, 844-861, 1210-1232; Fig. 4(c,d) |
| MA4 | Do | Fixed range {2,...,8} primary throughout (Table 2, Figs 3, 6, S1, eta^2, all Sect. 3 numbers, Discussion, abstract); capped range moved to Supp. S3 (Tables S2-S3). | M 441-450, 669-786, Table 2; S 115-161 |
| MA5 | Minimal | One sentence plus Table 2 footnote a on collapse cells (22/96 k-means, 26/96 Ward scenarios with k >= 3; 15.3% and 18.1% of evaluations; AG 0.955/0.929 inside vs 0.799/0.762 outside); Supp. S6 table. Identifiability index deferred. | M 757-763, 781-783; S 247-276 |
| MA6 | Do (rewrite) | rho effect re-read as collapse (k-hat_R = 2 at sigma <= 2 for 91.1%/87.8% of datasets at rho = 0.4 vs 38.3%/62.2% at rho = 0; at sigma >= 6 AG is lower at rho = 0.4: 0.948 vs 0.960, 0.914 vs 0.944); dimensionality effect reinstated (at sigma = 6 AG falls with p: 0.976, 0.903, 0.899 km; 0.976, 0.853, 0.818 Ward); eta^2 ranking qualified by R^2 (0.340/0.349 main effects; 0.606/0.605 with two-way interactions). | M 730-742, 765-786 |
| MA7 | Discuss | Not implemented. Limitations now state that the Wilcoxon tests and bands are computed across a designed grid; bands relabelled as spread across scenarios. | M 581-584, 1204-1207 |
| MA8 | Defer | Not implemented. | - |
| MA9 | Future research | ctree and larger minimum leaf sizes moved to Future work. | M 1243-1246 |
| MA10 | Future research, fix wording | "structurally different/distinct" removed (Introduction and Relation to previous work now say that Ward shares the WCSS criterion); Gaussian mixtures with BIC (fraley2002, scrucca2016) in Future work. | M 180-183, 1125-1127, 1246-1249; S 305-309 |
| MO1 | At submission | No change (Declarations placeholders kept). | M 1348-1365 |
| MO2 | Minimal | Supplementary wording "a fresh sample from the same population" replaced: centroids are redrawn per replicate, so independent pairs differ in centroid geometry; pairs baseline kept as a secondary column. Methods also state that centroids are redrawn for every original dataset. | S 163-186; M 295-296 |
| MO3 | Do (with Victoria) | Conclusions paragraph toned down; each changed sentence carries a `% VL-EDIT` comment: contribution presented as empirical; "can be measured" replaced (k and sigma are properties of an unknown partition); "without modification" replaced by the two required adaptations; uncited "correlations above 0.95" and "skewness considerably higher" reworded as possibilities. **Needs V. Lopez's approval.** | M 1283-1316 |
| MO4 | Defer | Not implemented. | - |
| MO5 | Do | Stability paragraph inserted in Relation to previous work (edited: ties Ben-David et al. to the collapse cells, states that calibration changes the algorithm comparison); short Introduction paragraph from stability_paragraph.tex; woo2009 cited to separate cluster-based (general) utility from downstream clustering utility. 17 lit_refs.bib entries added to refs.bib (only those cited). | M 187-192, 1128-1134, 1157-1181 |
| MO6 | Defer | Claims scoped to the grid in Limitations (rho <= 0.4, one Gamma shape, N = 1000, equal sizes); unequal sizes and stronger correlations in Future work. | M 1185-1189, 1249-1250 |
| MO7 | Discuss / Do | Not implemented (not yet decided per task). | - |
| MI1 | Do | Abstract precision: separate k-means/Ward values, "close to neutral" removed. | M 75-87 |
| MI2 | Do | "has closed" at sigma = 10 replaced by residual Ward gap (0.982 vs 0.969); silhouette "within +-0.012" replaced by "at most 0.0125 (Ward, sigma = 0.1)"; Milligan (1980) support softened in Sect. 2.2 and Relation to previous work; recompute_metrics.py docstring fixed. | M 962-963, 1042-1043, 279-282, 1145-1148 |
| MI3 | Do | Expected directions of each factor stated in Methods; the Results sentence on the "prior expectation that a hierarchical method would be more robust" removed. | M 357-367 |
| MI4 | Do | Figs 1-2: ticks, no baked-in titles, panel letters, replicate 1 / draw 1 stated in caption; Figs 3 and 6: categorical sigma axis, fixed range; Fig. 6 redesigned 2 x 2 with original-data recovery beside RR and AG0 beside AG. | Figs 1-6; M 636-667, 726-744, 983-995 |
| MI5 | Do | Software versions (R 4.3, synthpop 1.9.2, mvtnorm 1.4.2, arrow 25.0.0, rpart 4.1.24 used for bit-for-bit regeneration; Python 3.12, scikit-learn 1.9.0, numpy 2.5.1, scipy 1.18.0, pandas 3.0.5, pyarrow 25.0.0) and seeding policy, including the en_US.UTF-8 collation dependence of the synthetic seeds and the bootstrap seeds. Independent-seed test not done (Deviations). | M 400-421, 563-567 |
| MI6 | Do (short title) | Title: "Cluster Analysis of CART-Synthesised Data: A Factorial Simulation of k-Means and Ward's Linkage" (no ranking). Keywords: Synthetic data, CART synthesis, synthpop, k-means, Ward's linkage, Number of clusters, Cluster stability, Bootstrap null. | M 58-59, 89-90 |
| P1 | Revise plan | Step 1 (re-analysis of stored results) implemented; no rerun. | - |
| D1 | Done | Author order unchanged. | M 61-65 |
| D2 | Done | Affiliation unchanged; VL-EDIT markers for her paragraph. | M 72, 1283-1316 |
| D3 | Done | vidiella2025 kept as 2025. | refs.bib |

## JoC checklist items (content)

| # | Item | What was changed | Where |
|---|---|---|---|
| 2 | Abstract <= 150 words | 135 words (LaTeX stripped, $k$ counted as a word). | M 75-87 |
| 3 | Keywords | More specific keywords (8). | M 89-90 |
| 9 | Editions | No edition field added: drechsler2011, johnson1987 and breiman1984 each have a single edition (the CART book was later reprinted, not re-edited). | refs.bib |
| 12 | Chapter for book citations | `\citep[chap.~4]{johnson1987}` (Cholesky construction), `\citep[chap.~8]{breiman1984}` (regression trees; please confirm, see Deviations). The Appendix-B citation of breiman1984 moved to the Table S8 caption as a general source. | M 305, 377 |
| 13 | No abbreviated titles; arXiv | murtagh2017 and ullmann2022: "WIREs" expanded to "Wiley Interdisciplinary Reviews: Data Mining and Knowledge Discovery"; mullner2011 changed from `@article` with journal "arXiv preprint" to `@misc` with eprint; macqueen1967 changed to `@inproceedings` with booktitle, publisher and address. | refs.bib |
| 14 | Data matrix | N x p data matrix **X**_R with rows **x**_i defined at the start of Methods, with the label vector **g** and synthetic matrix **X**_S; D_R/D_S notation replaced. | M 225-244 |
| 15 | Bold vectors/matrices | `\bx`, `\bX`, `\bmu`, `\bg`, `\bR` macros; x_i, mu_j, mu_j^R/S, X_R, X_S, R bold throughout main and supplement. | M 47-52 and throughout; S 20-21, 199-310 |
| 16 | Figures 4.8 in, >= 7 pt | All figures redrawn at <= 4.8 in (4.60-4.80 in measured on the PDFs) and included at natural size; all text 7 or 8 pt (checked in code by `check_fonts`). | make_figures.py |
| 17 | Table reflow | Appendix B cost table (now Table S8) reflowed with a p-column; no overfull boxes in either build. | S 331-350 |

## Numbers changed from v4 (old -> new)

All count results changed because the primary candidate range changed from {2,...,min(k+3,8)} to
{2,...,8}; geometric metrics at the planted k are unchanged, and new floor/null values are
additions rather than changes.

### Abstract
* AG range "0.75 to 0.98" (k-means only) -> removed; overall AG "0.864 versus 0.823" -> "0.84 versus 0.81";
  new: Gamma 0.81 vs 0.73, Normal 0.87 vs 0.89. Word count 147 -> 135.

### Table 2 (marginal means; capped -> fixed range)
| Table 2 row | RR k-means | RR Ward | AG k-means | AG Ward |
|---|---|---|---|---|
| sep=0.1 | 0.272 -> 0.247 | 0.296 -> 0.281 | 0.751 -> 0.684 | 0.676 -> 0.646 |
| sep=2 | 0.304 -> 0.288 | 0.307 -> 0.295 | 0.797 -> 0.764 | 0.759 -> 0.738 |
| sep=6 | 0.810 (unchanged) | 0.789 (unchanged) | 0.926 (unchanged) | 0.882 (unchanged) |
| sep=10 | 0.954 (unchanged) | 0.950 (unchanged) | 0.983 -> 0.982 | 0.976 -> 0.975 |
| k=2 | 0.843 -> 0.819 | 0.860 -> 0.846 | 0.885 -> 0.847 | 0.841 -> 0.817 |
| k=3 | 0.473 -> 0.468 | 0.459 -> 0.455 | 0.863 -> 0.838 | 0.812 -> 0.803 |
| k=4 | 0.439 -> 0.437 | 0.437 -> 0.435 | 0.844 -> 0.833 | 0.816 -> 0.811 |
| p=2 | 0.616 -> 0.605 | 0.623 -> 0.613 | 0.843 -> 0.817 | 0.770 -> 0.756 |
| p=5 | 0.561 -> 0.554 | 0.569 -> 0.563 | 0.866 -> 0.849 | 0.819 -> 0.806 |
| p=10 | 0.578 -> 0.565 | 0.564 -> 0.560 | 0.884 -> 0.851 | 0.880 -> 0.870 |
| rho=0 | 0.571 -> 0.553 | 0.578 -> 0.567 | 0.800 -> 0.753 | 0.763 -> 0.744 |
| rho=0.4 | 0.599 -> 0.597 | 0.592 -> 0.590 | 0.929 -> 0.925 | 0.884 -> 0.877 |
| distribution=gamma | 0.565 -> 0.557 | 0.561 -> 0.554 | 0.833 -> 0.809 | 0.749 -> 0.731 |
| distribution=normal | 0.604 -> 0.593 | 0.610 -> 0.604 | 0.896 -> 0.869 | 0.898 -> 0.890 |
| overall | 0.585 -> 0.575 | 0.585 -> 0.579 | 0.864 -> 0.839 | 0.823 -> 0.811 |
* Wilcoxon p row (new): RR 0.750, AG 5.4e-5.

### Section 3.2 (Number of groups)
* Original-data recovery at sigma = 0.1: 0.289 (k-means) / 0.306 (Ward) -> 0.233 / 0.294.
* Partial eta^2, RR: sigma 0.55 / 0.57 -> 0.565 / 0.577; k 0.31 / 0.37 -> 0.287 / 0.357.
* Partial eta^2, AG: sigma 0.20 / 0.21 -> 0.245 / 0.229; rho 0.10 / 0.07 -> 0.141 / 0.075;
  distribution 0.03 / 0.10 -> 0.019 / 0.105; k "below 0.01" -> "below 0.001". New: R^2 0.340 / 0.349,
  with interactions 0.606 / 0.605, rho x sigma 0.282 / 0.179.
* Correlated vs uncorrelated AG (k-means): 0.929 vs 0.800 -> 0.925 vs 0.753 (Ward new: 0.877 vs 0.744).
* k-hat_R = 2 at p = 10, sigma <= 2: "87-90% (k-means)" (capped) -> 80.8% (k-means), 90.0% (Ward).
* "exceed 0.90 once sigma = 10" (unchanged); "almost never recovered" now quantified (at most 0.12).
* Independent-pairs baseline 0.816 / 0.772 -> 0.801 / 0.767 (now Sect. 3.3, secondary).
* "synthetic dataset agrees with its parent more often than a fresh sample" -> removed; replaced by
  AG below AG0 in 99 (k-means) and 90 (Ward) of 144 scenarios.

### Section 3.3 (Geometric fidelity) - unchanged observed values, removed claims
* MCD 0.60/0.86 -> 0.09/0.10 and MVD 0.35/0.61 -> 0.11/0.13 now quoted to three decimals
  (0.604/0.859 -> 0.090/0.095; 0.353/0.613 -> 0.112/0.133); same data.
* Removed: "the intervals overlap at sigma >= 6", "Each synthesised coordinate therefore contributes a
  similar amount of dispersion distortion", "k-means ... geometrically more conservative estimator
  under synthesis", "cluster sizes of a k-means partition fluctuate less under synthesis"
  (now "under resampling, and hence also under synthesis").

### Section 3.4 / 3.5 (Distribution family)
* RR at sigma = 6, Ward: 84.6% vs 73.3% -> 84.5% vs 73.2% (k-means 86.2% vs 75.9% and original-data
  recovery 90.0/80.0, 91.1/78.9 unchanged).
* Ward AG, Normal vs Gamma: sigma = 0.1 0.806 vs 0.545 -> 0.782 vs 0.511; sigma = 2 0.878 vs 0.639 ->
  0.873 vs 0.603.
* k-means AG, Normal vs Gamma: sigma = 0.1 0.765 vs 0.737 -> 0.665 vs 0.702; sigma = 2 0.888 vs 0.707
  -> 0.879 vs 0.648. sigma = 6 values unchanged (0.947/0.906; 0.924/0.841).
* sigma = 10: "has closed" -> Ward 0.982 vs 0.969, k-means 0.983 vs 0.981.

### Section 3.6 (Agreement between algorithms)
* RR overall 0.585 / 0.585 -> 0.575 / 0.579; Wilcoxon W = 3300, p = 0.39 -> W = 3508.5, p = 0.750.
* AG overall 0.864 / 0.823 -> 0.839 / 0.811; "higher in 95 of 144 (24 ties)" -> "90 higher, 30 lower,
  24 ties"; W = 1665, p < 0.001 -> W = 2088.5, p = 5.4e-5 (tie-corrected).
* Same outcome 92.0% (unchanged).
* Silhouette difference "within +-0.012" -> "at most 0.0125 in absolute value"; means 0.396/0.397 and
  0.376/0.377 unchanged.

### Discussion
* Finding 1: AG "0.75 to 0.98" -> 0.684 / 0.646 to 0.982 / 0.975; RR "roughly 0.27 to above 0.95" ->
  0.247 / 0.281 to 0.954 / 0.950; "k = 2, 0.84 ... k >= 3 below 0.48" -> 0.819 vs 0.468 and 0.437.
* Finding 2: "0.585 versus 0.585; p = 0.39" -> removed from the Discussion (kept in 3.6 with new values);
  "0.864 versus 0.823; p < 0.001" -> 0.839 vs 0.811, plus Gamma/Normal and AG0 values.

### Supplementary material
* Table S2 (range sensitivity): fixed-range RR Wilcoxon p 0.76 -> 0.750; capped RR p 0.39 -> 0.380
  (W 3294.5 new); capped AG "< 0.001" -> 2.7e-7 (W 1665.5). The table now also has distribution rows,
  W values and AG0.
* Supp. S2 text: capped-range comparison values (75.1/67.6, 79.7/75.9) unchanged; the direction of the
  sentence reversed (fixed range is now the main one).
* Old Table S3 (independent-pairs baseline, capped) -> Table S4 (fixed range, with AG0):
| Independent-pairs baseline | k-means | Ward |
|---|---|---|
| sep=0.1 | 0.817 -> 0.792 | 0.681 -> 0.667 |
| sep=2 | 0.750 -> 0.714 | 0.728 -> 0.722 |
| sep=6 | 0.764 -> 0.764 | 0.758 -> 0.758 |
| sep=10 | 0.933 -> 0.933 | 0.922 -> 0.922 |
| distribution=gamma | 0.760 -> 0.749 | 0.675 -> 0.665 |
| distribution=normal | 0.872 -> 0.853 | 0.869 -> 0.869 |
| overall | 0.816 -> 0.801 | 0.772 -> 0.767 |
  AG columns change as in Table 2 (e.g. sigma = 0.1: 0.751/0.676 -> 0.684/0.646).
* Fig. S1 heatmap (v4 from `clustering_results.parquet` success_*, capped; v5 fixed range from the
  fidelity table):
| Fig. S1 cell (k, sigma) | k-means | Ward |
|---|---|---|
| 2, 0.1 | 0.64 -> 0.61 | 0.70 -> 0.69 |
| 2, 2 | 0.77 -> 0.72 | 0.77 -> 0.75 |
| 2, 6 | 0.96 (unchanged) | 0.95 (unchanged) |
| 2, 10 | 0.99 (unchanged) | 0.99 (unchanged) |
| 3, 0.1 | 0.14 -> 0.12 | 0.13 -> 0.11 |
| 3, 2 | 0.09 (unchanged) | 0.09 (unchanged) |
| 3, 6 | 0.75 -> 0.74 | 0.72 -> 0.71 |
| 3, 10 | 0.92 (unchanged) | 0.91 (unchanged) |
| 4, 0.1 | 0.01 (unchanged) | 0.04 (unchanged) |
| 4, 2 | 0.06 (unchanged) | 0.05 (unchanged) |
| 4, 6 | 0.73 (unchanged) | 0.71 (unchanged) |
| 4, 10 | 0.95 (unchanged) | 0.95 (unchanged) |
* Former Appendix B (now S8): "reproduces every estimate reported here to within 0.025" -> "every
  marginal mean of Table 2 (both ranges) and every overall and marginal mean of MCD, MVD and dG differs
  by at most 0.0052" (recomputed from `khat_fidelity_full_m100.parquet`); CART synthesis
  invocations 1.44 x 10^5 -> 7.2 x 10^5 and unit cost 31 ms/dataset -> 6.2 ms/dataset (the
  1.44 x 10^5 counted output files, each holding one draw for all five replicates; wall time 1.24 h
  unchanged).

## Phase 3 (submission packaging and verification, 2026-09-29)

* **B1/B2 now applied in the real build.** `main.tex` and `supplementary.tex` read
  `joc_prep/joc_bib.tex` (JoC reference style, `joc_prep/sn-joc.bst`) and `joc_prep/blind.tex` in
  every build, and `joc_prep/joc_referee.tex` when `\SetReferee` is defined. `./build_submission.sh`
  produces `submission/main_blind.pdf` (47 pp.), `supplementary_blind.pdf` (17 pp.),
  `title_page.pdf`, `main_named.pdf` (31 pp.), `supplementary_named.pdf` and `main_diff_v4_v5.pdf`;
  commands in `joc_prep/README.md`. `sn-jnl.cls` and `build.sh` are unchanged.
* Source edits for blinding: `\blindhide{, to which we have direct access}`; `\repourl` in Code
  availability; `\blindalt` for Funding, Competing interests, Author contributions. The abstract
  moved to `abstract.tex` (read by `main.tex` and `joc_prep/title_page.tex`). `\unboldmath` added to
  the abstract font in the normal layout (sn-jnl's `\boldmath` leak).
* **Number check** (`joc_prep/verify_numbers.py`, report `joc_prep/VERIFICATION.md`): 298 prose
  numbers and 907 table cells recomputed from the parquet files. Fixed: Sect. 3.4, k-means MVD band
  at p = 2 printed 0.05-0.08, recomputed 0.04-0.08 (and "95% interval" relabelled as
  mean +/- 1.96 SE across scenarios); Supp. S2, "15.2% ... 16.4%" now says these are k-means values.

## Addendum (29 Sep 2026, final pass)

* **Repository move.** The `data` symlink now points to
  `~/Desktop/personal/academic/research/ml-research/clustering/data`
  (144 original and 144,000 synthetic files resolve). No other file referred to the old path.
* **MI5, independent seeds (done).** `scripts/checks_v5/seed_test.py`: refitting k-means on the
  synthetic data with independent seeds (replicate 1, draws 1-20, all 144 scenarios; 2,880 pairs)
  leaves k-hat_S unchanged in 95.7% of pairs; AG 0.832 -> 0.831; MCD 0.304 -> 0.303,
  MVD 0.222 -> 0.220, dG 0.0301 -> 0.0302. Stated in Methods (Software and seeds); the
  limitation sentence now points to it. Log: `results/logs/v5check_seed_test.json`.
* **Book chapter.** Breiman et al. (1984) chap. 8 = "Regression Trees" (confirmed on the
  Taylor & Francis chapter page, doi:10.1201/9781315139470-8). Johnson (1987) chap. 4 was already confirmed.
* **Wall-clock figures (Supplementary S8, Table S9).** Synthesis 1.24 h (file write interval,
  recomputed: 1.240 h), 21 GB (21,783,214,150 bytes) and fidelity 4.44 h (log) confirmed.
  Clustering stage re-measured on a new random sample of 3,000 inputs with 18 workers:
  358 s -> 4.8 h extrapolated (v4: 3.6 h); the table now gives 3.6-4.8 h and a total of
  9.3-10.5 h. The unverifiable 5.6 h timestamp bound was removed. Thread pinning re-measured
  (`scripts/checks_v5/thread_bench.py`): 5.9 s pinned vs 52.3 s unpinned (factor 8.8; v4 text:
  1.9 s vs 84.5 s, factor 44, not reproducible and replaced). Logs in `results/logs/v5check_*.json`.
* **Benchmark README.** Full range {2,...,8} stated as primary, capped range as sensitivity; the
  sentence that AG isolates synthesis replaced by the bootstrap-null reading; bands relabelled as
  mean +/- 1.96 SE over the designed grid.
* **Rerun n = 50, m = 100.** Agreed by D. Fernández; runbook in `docs/RERUN_n50_m100.md`
  (separate working copy, so the m = 1000 results are not overwritten). Not run yet.

## Addendum 2 (30 Sep 2026): real-data case study integrated

Approved by Dani and Jordi (Jordi preferred diabetes; asked to note that Reaven & Miller 1979 find three groups).

* New Section "Case study: diabetes data" (\label{sec:case}) between Results and Discussion, with Fig. `fig_diabetes`.
  rrcov::diabetes (the mclust copy has shifted column names), m = 1000 CART draws, B = 1000 bootstrap null.
  Code: `scripts/case_study/{diabetes_synth.R, diabetes_analysis.py, diabetes_figure.py}`; results in `results/case_study/`.
* Reaven & Miller comparison: PRIM-9 boomerang, Friedman & Rubin (1967) nearest-mean clustering with k = 3 fixed and
  starting values from an earlier study; here the silhouette prefers k = 2 narrowly (0.571 vs 0.547; Ward 0.567 vs 0.544).
* Knock-on edits: abstract (+1 sentence, 146 words), end of Introduction, Limitations (real data, small N),
  Future work ("second and larger real-data test"), Conclusions (`% CS-EDIT`, for Victoria with the VL-EDITs),
  Data availability. New references: reaven1979, friedman1967, todorov2009 (CrossRef-checked).
* Case-study prose numbers checked against `results/case_study/diabetes_summary.json`. The first check flagged the Ward
  silhouette at k = 3 (0.543 in the JSON vs 0.544 in the text) because the JSON stored the silhouette scan rounded to
  4 decimals (0.5435). Recomputed unrounded value 0.54352 -> 0.544, so the text is correct; the JSON now stores the
  scan unrounded (all other metrics identical on re-run). All other case-study numbers match.
* Pages: main_blind 49 (limit 50; case study pp. 30-32, references from p. 41), main_named 33.
* Backup of the pre-integration sources: `_backup_v5_precase/`.

## Addendum 3 (27 Oct 2026): co-author comments on the case study and abstract

Source: Dani's annotated PDF (36 comments) and Jordi's (2, abstract); e-mails of Dani and Jordi.

* Abstract: Jordi's rewording merged to 150 words (his version was 175; JoC limit 150).
* Keywords: "Number of clusters" removed, "Bootstrap null" -> "Bootstrap" (Dani).
* D. Fernández affiliation -> IRIS, UPC (new \affil[5]; J. Cortés kept on DEIO until confirmed).
* Declarations (named build and title page): Dani's funding text; competing interests set to Springer's
  standard "no relevant financial or non-financial interests" (to be confirmed by all five). Other authors'
  funding still TODO.
* Case study rewritten with Dani's edits, except: "pairwise correlated" -> glucose area and SSPG r = 0.77
  (insulin-SSPG r = 0.01); "five recorded measurements" -> "five variables in the distributed data"
  (R&M recorded six); "about equally unstable" -> k-means slightly more stable (AG0 0.667 vs 0.637,
  McNemar 86 vs 56, p = 0.015); "larger magnitudes" -> "mostly larger" (MVD k-means 0.051 < 0.069 in the
  simulation); hats on k kept (k-hat = silhouette-selected, as in the rest of the paper).
* New: ARI by nearest-centroid transfer (Dani's proposal; Dudoit & Fridlyand 2002, Tibshirani & Walther
  2005) with bootstrap null, Ward ceiling 0.955, and ARI against the clinical classes.
  `scripts/case_study/diabetes_analysis.py` (all previous case-study numbers unchanged on re-run).
* New Table 5 (`tables/tab_case.tex`, `diabetes_table.py`) holds every case-study number; Fig. 7 rebuilt:
  (a) original, (b) one synthetic draw (Dani's scatter), (c) k-hat distribution. Old Fig. 7b (four
  metrics on one axis, Dani's scale comment) dropped.
* Six synthesis orders (`diabetes_orders.R`, `diabetes_orders_table.py`): Supplementary S11, Table S11.
  Default order reproduced bit for bit.
* ARI over the full simulation (`src/synthclust/ari_null.py`, 720,000 pairs + 21,600 resamples, ~19 min
  on 20 workers): Supplementary S10, Table S10.
* Group-balance figure moved to Supplementary S9 (Fig. S3) for space.
* Pages: main_blind 50 (limit 50), main_named 34, supplementary_blind 21, supplementary_named 16.
* Checks: verify_numbers.py 298 prose / 907 cells, 0 mismatches; every number in the new case-study
  section and S10-S11 matched to the results JSON files (one fix: Ward ceiling 0.954 -> 0.955).
* Build note: the sandbox TeX could not read texfmt/pdflatex.fmt (different pdftex build); a format was
  rebuilt for this session only and removed afterwards.
* Backup of the sources before this round: `_backup_v5_preDJ/`.

## Addendum 4 (27 Oct 2026): author decisions applied, official class, cover letter

Decisions (Oriol, for the authors): n = 50 run goes to the supplement; Chen (2025) anonymised in the blind
version; ARI scope as is; page count left at the limit; pending declarations assumed fine.

* `sn-jnl.cls`, `sn-basic.bst`: Springer Nature's official copies (template package, December 2024 version).
  The official class adds space around lists; to stay at 50 pages the tables are now `[!tbp]` (with `[t]` the
  referee layout had pushed Tables 2-5 to the end of the document; they now sit next to their text).
* Blind version cites `anon2025` ("Anonymous (2025), details omitted for double-anonymous review") instead of
  the Chen thesis (`\blindalt`), three citations; named version unchanged.
* Affiliations: J. Cortés [2,5] (DEIO and IRIS, UPC); D. Fernández [5] (IRIS). Funding: D. Fernández's
  statement only (no other funding to declare); competing interests: none (all authors). TODOs removed.
* New Supplementary S12 (Table S12, `scripts/checks_v5/n50_table.py`, inputs copied to `results/n50_m100/`):
  n = 5/m = 1000 vs n = 50/m = 100. Main text: "modest evidence" sentence replaced by the replication
  (difference in excess -0.018, p = 1.2e-5); Delta G "equal" -> "nearly equal" (p = 0.002 at n = 50);
  Discussion "equal or nearly equal"; Limitations sentence on B = 30 now cites the replication.
* Dimensionality / group-balance paragraphs condensed (confidence intervals and floor values per p dropped;
  they are in Fig. S3 and Table S5).
* Cover letter (`joc_prep/cover_letter.md`): case-study bullet, n = 50 replication in the scope paragraph,
  "beyond the single case study" for real data, anonymised thesis citation, competing interests, IRIS
  affiliations. Now 2 pages. Remaining placeholders: date, editor, corresponding author.
* Pages: main_blind 50, supplementary_blind 23, main_named 34, supplementary_named 17, cover letter 2.
