# Code structure: before and after

## First, a correction to the framing

I did **not** rewrite your pipeline, and it would be wrong to tell Jordi I did.
Three of your four stages are untouched and still load-bearing:

* `01_generate_original_data.R` — still the only source of the 144 OD datasets
* `02_generate_synthetic_data.R` — still the only source of the 14,400 SD datasets
* `03_run_clustering.py` — still produces `clustering_results.parquet`, which is
  **still where every Success Rate in the paper comes from**, including the
  headline 0.585 / 0.584

What actually got replaced is **one stage**: the evaluation layer. That
notebook — 57 code cells, 7,462 lines — is now two scripts totalling 436 lines.
That is a real and large consolidation, but it is a quarter of the pipeline, not
the whole thing. The rest of this document is scoped to that claim.

---

## Current structure

### Your pipeline (unchanged, still required)

```
~/Desktop/academic/ml-research/clustering/
├── config/config.json                        18 lines   design grid
├── 01_generate_OD/
│   └── 01_generate_original_data.R          369 lines   144 OD datasets
├── 02_generate_SD/
│   └── 02_generate_synthetic_data.R         276 lines   14,400 SD datasets (CART)
├── 03_clustering_analysis/
│   ├── 03_run_clustering.py                 423 lines   72,000 evaluations
│   └── clustering_utils.py                   64 lines   detect_optimal_k, metrics
├── run_all.sh                               253 lines   stage driver + timing
├── data/original/     144 parquet    (37 MB)
├── data/synthetic/  14,400 parquet   (2.1 GB)
└── results/clustering_results.parquet  (72,000 x 23)
```

### Replaced

```
└── 04_evaluation/
    └── 04_evaluate_clustering.ipynb       8,574 file lines
                                           7,462 code lines
                                             116 cells (57 code + 59 markdown)
```

### What replaces it

```
<workspace>/
├── recompute_full.py            188 lines   metrics -> khat_fidelity_full.parquet
├── makefigs.py                  248 lines   all 7 figures -> manuscript/figures/
├── verify_notebook_metric.py     55 lines   forensic: reproduces the old definition
├── build.sh                      33 lines   LaTeX build (3-pass + bibtex)
└── manuscript/
    ├── main.tex                 811 lines   the article
    ├── supplementary.tex         91 lines
    ├── supp_table.tex            50 lines   generated, not hand-written
    ├── refs.bib                 380 lines   32 entries, 24 with verified DOIs
    ├── sn-jnl.cls  / sn-basic.bst           Springer class (third-party mirror)
    ├── figures/                  14 files   7 figures x {pdf, png}
    └── README.md                 52 lines   how to build
```

---

## The evaluation layer, before and after

| | Notebook | Scripts |
|---|---|---|
| Files | 1 | 2 (+1 forensic) |
| Code lines | 7,462 | 436 |
| Units | 57 cells, order-dependent | 2 entry points |
| Reads data from disk | 14 separate times | once per dataset, single pass |
| Re-fits clustering models | 12 separate cells | 1 cached fit per (replicate, algorithm) |
| Calls `StandardScaler` | 13 separate times | 1 convention, stated in the docstring |
| Figure-producing cells | 43 | 7 named functions |
| Stored outputs | **0 of 57 cells** | deterministic parquet + PDFs |
| Reproducible by rerunning | no | `python recompute_full.py && python makefigs.py` |

**17x fewer lines** for the same stage.

### Why it shrank

Not by cleverness — by removing repetition the notebook format encourages.

1. **One pass instead of fourteen.** The notebook re-read parquet from disk in 14
   cells and re-fitted clustering models in 12. Each computed what it needed and
   discarded it. `recompute_full.py` walks each scenario once, fits the original
   partition **once per (replicate, algorithm)** and reuses it across all 100
   synthetic draws. That single change is most of the 1,880-second runtime for
   72,000 pairs — the notebook's structure would have refitted the original side
   100 times over.

2. **Metrics computed where they are defined.** MCD, MVD, ΔG, silhouette and both
   k̂ conventions now come out of one function, in one row per pair, into one
   parquet. In the notebook they were spread over cells 42–115, with aggregation
   cells reading the output of earlier cells by variable name.

3. **Figures as functions, not cells.** 43 plotting cells became 7 functions
   sharing one style block and one colour palette. `fig_recovery`, `fig_fidelity`,
   `fig_balance`, `fig_distribution`, `panel_grid` (x2), `fig_heatmap_supp`.

4. **The scan is done once.** `sil_scan` records the silhouette at every candidate
   *k*, so both k_max conventions — the capped `min(k+3, 8)` and the fixed 8 —
   fall out of the same pass instead of needing a second run.

### What the rewrite fixed, not just shortened

The reason to rewrite at all was not line count.

* **A definitional bug.** Cells 42, 44, 86 and 88 — every cell computing centroid
  distance or variance difference — begin `data_dir = "../data/original"` and
  compare a recovered partition against the **planted labels of the same
  dataset**. No synthetic data is loaded. Those metrics measured clustering
  accuracy, not synthetic fidelity, so no statement about CART could rest on
  them. Only cells 6, 8 and 79 read `data/synthetic` at all, and all three are
  visualisation.
* **Metrics that did not exist.** `clustering_results.parquet` has no MCD, MVD,
  Gini or k̂ column. Those numbers had no saved provenance.
* **Nothing was reproducible.** 0 of 57 code cells carry stored output, so the
  printed values in the report cannot be traced to any execution.
* **A silent convention mix.** `detect_optimal_k` caps its search at
  `min(k_true + 3, 8)`; the supplementary analysis wants a fixed range. Both are
  now computed and labelled instead of one being assumed.

---

## What is genuinely new (not a replacement)

| File | Purpose |
|---|---|
| `khat_fidelity_full.parquet` | 72,000 x 25 — the metrics the pipeline never saved |
| `manuscript/` | the article itself: 18 pages, Springer class, 31 references |
| `REVISION_NOTES.md` | every flaw found and what was done about it |
| `RESPONSE_TO_COMMENTS.md` | comment-by-comment reply to Jordi and Dani |
| `comments.txt` | the 22 PDF annotations, extracted and attributed |
| `refs_shortlist.md` | 22 candidate references with screening decisions |
| `khat_agreement.csv` | k̂ agreement, both comparators, by separation |

---

## Suggested repo layout for the GitHub link

Jordi asked for a reduced repo — article analysis only, Chinua's TFG material
removed. Flat, four stages, no numbered-directory-per-file:

```
synthetic-clustering/
├── README.md
├── config.json
├── R/
│   ├── generate_original.R
│   └── generate_synthetic.R
├── python/
│   ├── run_clustering.py
│   ├── clustering_utils.py
│   ├── recompute_metrics.py       (recompute_full.py)
│   └── make_figures.py            (makefigs.py)
├── manuscript/
│   ├── main.tex  supplementary.tex  refs.bib
│   └── figures/
└── results/
    ├── clustering_results.parquet
    └── khat_fidelity_full.parquet
```

Data directories stay out (2.1 GB); the README gives the two commands that
regenerate them. `verify_notebook_metric.py` also stays out — it exists to
document a bug in code that will not be in the repo.
