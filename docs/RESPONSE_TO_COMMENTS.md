# Response to reviewer comments

All 22 annotations in `clustering_paper_JC_DF.pdf` were legible and are
addressed below. Page numbers refer to the annotated PDF.

## Structural comments

| p. | Reviewer | Comment | What was done |
|---|---|---|---|
| 1 | Dani | Must be one title, not title + subtitle | Single title: *"Does Synthetic Data Preserve Cluster Structure? A Factorial Evaluation of Partitioning and Hierarchical Clustering on CART-Generated Data"* |
| 1 | Dani | Consider "partitioning clustering" instead of "K-Means" | Adopted in the framing — the paper now contrasts the *partitioning* and *hierarchical* paradigms, with $k$-means and Ward as their instances. Algorithm names kept where a specific algorithm is meant. |
| 2 | Jordi | Abstract to be revisited last | Rewritten to match the new structure. Still the piece most worth a final pass. |
| 2 | Dani | Drop specific algorithm keywords | Keywords now: Synthetic data, Cluster analysis, Statistical disclosure control, Analytical utility, Simulation study |
| 3 | Jordi | No table of contents in the final article | Removed |
| 3 | Jordi | Use the publisher's template | `main.tex` is written against Springer's `sn-jnl.cls` command set — see *Template* below |
| 3 | Jordi | Fewer subsections | 20 numbered headings reduced to 12 |
| 3 | Jordi | No subtitles in the Introduction | Introduction is now continuous prose, no subsections |
| 3, 7 | Jordi | §2 is a jumble: 2.1 → Discussion, 2.2 → Methods §3.2.2, 2.3 → Methods intro | Done exactly. Old §2 no longer exists: the clustering-as-resemblance-measure idea is a paragraph in the Discussion; the CART mechanism is Methods §2.3.2; the discrepancy framework opens Methods as §2.1 |
| 5 | Jordi | Reorganise the Introduction into five blocks | Done in the order given: synthetic data → clustering → need for synthetic data in clustering → utility concept → objectives |
| 5 | Jordi | Reorder objectives 1, 3, 2 | RQ1 number of groups, RQ2 geometry, RQ3 algorithm comparison |
| 5 | Jordi | The intro needs many references | 21 new references added, all verified against OpenAlex. See `refs_shortlist.md` — **these need your vetting** |
| 7 | Jordi | Methods structure is good | Kept |
| 9 | Jordi | "Reference data" or "Original data"? | Standardised on **original data** throughout (matches your OD/SD file naming) |
| 9 | Jordi | Add a table of scenarios and what each factor tests | Table 1, with a rationale column naming the hypothesis each factor probes |
| 9 | Jordi | State the number of repetitions and the software | Methods §2.5: 144 × 5 × 100 = 72,000 evaluations; `synthpop` in R, `scikit-learn` in Python |
| 10 | Jordi | Don't put "(Hungarian Algorithm)" in a title | Section is now "Evaluation metrics"; the Hungarian algorithm is described in the text |
| 10 | Jordi | Say how metrics are aggregated across repetitions | Methods §2.5 "Analysis and reporting": scenario means as the unit of replication, 95% intervals across scenarios, paired Wilcoxon for the algorithm comparison |
| 12 | Jordi | Rename "Cluster-Count Recovery" | Now "Number of groups" |
| 14 | Jordi | The algorithm comparison should come last | Now the final Results subsection (§3.5) |
| 17 | Jordi | "Silhouette Fidelity" shouldn't have its own title | Folded into §3.5 as a continuation |
| 18 | Jordi + Dani | "Discussion" rather than "Conclusions" | Renamed. The exemplar JoC article uses "Discussion and Conclusion" |

## Figure comments

| p. | Comment | What was done |
|---|---|---|
| 11 | Everything in Results must be introduced in Methods — explain the visualisation | Methods §2.5 states that $p=2$ scenarios are plotted directly with no dimensionality reduction |
| 11 | Explain each panel of Figs 1–2, especially why the lower-left is not separated | Both captions describe the row/column layout; §3.1 explains that at $\sigma=2$ the true groups genuinely overlap, so the algorithms find a clean vertical split rather than the true diagonal boundary |
| 11 | Match red/blue ↔ top/bottom between real and synthetic | Fixed. Labels are Hungarian-matched to the original partition and then oriented so cluster 0 is always the upper one — colour now tracks position in every panel |
| 13 | Figs 3 and 4 are near-duplicates; keep one | Old Fig 4 promoted to Fig 3 in the main text; old Fig 3 moved to supplementary as Fig S1 |
| 13 | Supplementary: $\hat{k}$ frequency table, real vs synthetic, by separation | Table S1. **Your intuition was right**: at $\sigma=10$ agreement is 98.3%, at $\sigma=0.1$ it drops to 68.2%, and the asymmetry is in the direction you guessed — the synthetic data collapse weak diffuse structure into fewer groups |
| 15 | Add dispersion to Fig 5 | Mean ± 95% interval bands, computed across the 144 scenario means |

## Template

**Resolved — the manuscript now compiles against Springer's real `sn-jnl.cls`.**
Both `main.tex` and `supplementary.tex` use `\documentclass[pdflatex,sn-basic]{sn-jnl}`
with the standard Springer preamble block, so what you are reading in `main.pdf`
is genuine Springer typography, not an emulation. The old `snfallback.sty` is gone.

**One caveat, and it matters.** Springer's own download page was unreachable
from this machine, so `sn-jnl.cls` and `sn-basic.bst` came from a third-party
GitHub mirror. The class identifies itself as the real generated file
(`\ProvidesClass{sn-jnl}`, 1,809 lines, docstripped from `classes.dtx`) and it
compiles the document with zero errors, but **you should replace it with the
official copy before submitting** — download the zip from Springer's LaTeX
author-support page, or open their template on Overleaf and export it. The
document body should not need any changes; just swap the class file.

Two smaller notes. The mirror did not carry `sn-mathphys-num.bst`, so the build
uses `sn-basic`; if Journal of Classification asks for the numbered mathphys
style, change the class option to `[pdflatex,sn-mathphys-num]` and drop that
`.bst` in from the official zip. And the `\pdfmapfile{=local.map}` line near the
top of each file is a workaround for a broken font-map index on this build
machine — delete it anywhere else.

For the structural model, the closest JoC precedent I found is Aschenbruck,
Szepannek & Wilhelm (2023), *Imputation Strategies for Clustering Mixed-Type
Data with Missing Values*, `10.1007/s00357-022-09422-y` — open access, a
simulation study of clustering methods. Its skeleton is: Introduction →
Method → Simulation Study (data simulation / evaluation aspects / execution /
results) → Application to a Real-world Problem → Discussion and Conclusion.
Two things to note: it has no table of contents, and it uses "Discussion and
Conclusion", both matching your comments. It also has a real-data application
section, which this paper does not — worth deciding whether to add one.

## Reproduction of the fidelity metrics — RESOLVED, but it needs a decision

**Short version: MCD and MVD in the report do not measure what the report says
they measure.** They compare the recovered partition against the *true labels
within the original data*. They never touch the synthetic data. I traced this
in `04_evaluate_clustering.ipynb`: cells 42, 44, 86 and 88 — the only cells that
compute centroid distance and variance difference — all begin with

```python
data_dir = "../data/original"
real_files = glob.glob(os.path.join(data_dir, "*.parquet"))
```

and then compare `calculate_centroids(X_scaled, true_labels)` against
`calculate_centroids(X_scaled, pred_km)`. The only cells in the notebook that
load anything from `data/synthetic` are 6, 8 and 79, and all three are
visualisation cells (the 2×3 grids and the PCA/t-SNE comparison).

So the report's MCD and MVD are **clustering-accuracy** measures — how well
$k$-means and Ward recover the planted groups in the original data. They are
not synthetic-data fidelity measures, and no sentence about CART can be
supported by them.

I verified this by reimplementing the notebook's definition exactly
(`verify_notebook_metric.py`) and running it over all 144 original datasets:

| | Paper | Notebook definition, reimplemented | Original-vs-synthetic |
|---|---|---|---|
| MCD $\sigma=0.1$, KM | 0.60 | 1.289 | 0.602 |
| MCD $\sigma=10$, KM | 0.19 | 0.012 | 0.090 |
| MVD $p=2$, KM | 0.15 | 0.344 | 0.064 |
| MVD $p=10$, KM | 0.67 | 0.964 | 0.393 |

Neither column reproduces the report exactly, so the printed numbers came from
some further variant I cannot recover from the notebook as saved — the cells
carry no stored output. **The exact provenance of the report's figures is
therefore still open**, and only you can close it. What is settled is that the
notebook's MCD and MVD do not involve synthetic data, so whatever produced the
printed numbers, it was not the code in this repository as it currently stands.

This leaves the rising MVD-vs-separation claim unexplained rather than
explained. Under the notebook's definition MVD measures recovery error, which
shrinks as groups separate; under the original-vs-synthetic definition it also
falls. Neither produces a rise. See the standardisation note below for a
hypothesis I tested and rejected.

**What the draft does.** It reports the original-vs-synthetic values
throughout, because those are the quantities the paper's argument actually
needs: the whole claim is about what synthesis does to structure, which
requires comparing original to synthetic. Every fidelity number in the current
`main.pdf` comes from `recompute.py`, which does exactly that, and is
internally consistent.

**What you need to decide.** If the intention all along was to measure
clustering accuracy on the original data, that is a legitimate quantity but it
belongs to a different paper — it says nothing about CART. If the intention was
synthetic fidelity, as the report's text states, then the report's numbers are
wrong and the draft's are right. I have assumed the latter. Please confirm
before submission, because these values appear in the abstract.

---

## Note on standardisation — a dead end, recorded so nobody retraces it

Before finding the definition mismatch above, I hypothesised that the report's
rising MVD-vs-separation came from computing an original-vs-synthetic MVD
without standardising. That hypothesis is testable and the arithmetic works:
unstandardised, MVD tracks absolute cluster spread, which grows with $\sigma$
by construction (no scaling gives 0.088, 0.033, 0.106, 0.152 across the four
separations — rising; scaler fit on the original and applied to both gives
0.077, 0.032, 0.017, 0.038 — falling).

**But it cannot be the explanation**, because it assumes the report computed an
original-vs-synthetic MVD in the first place, and the notebook does not. The
two explanations are not compatible and only the definition mismatch survives.
I mention it because an earlier draft of the manuscript's Limitations said
standardisation was the cause; that sentence has been rewritten. The Limitations
section now names both conventions — what the metrics compare, and how the two
datasets are put on a common scale — as things a replication must state, which
is true independently of which one produced the report's numbers.

## Left for you

1. **Confirm the MCD/MVD definition** (see above). The report's versions compare
   recovered partitions against true labels *within the original data* and never
   touch the synthetic data; the draft's versions compare original against
   synthetic. I believe the draft's is what the paper's argument requires, but
   this is your call and the numbers appear in the abstract.
2. The abstract deserves a final pass now that the structure is settled.
3. `refs_shortlist.md` lists all 22 candidate references with the abstract
   sentence justifying each. They are real and verified, but they are my
   selection, not yours — cut freely.
4. The biomedical skew is partly corrected. A second search pass aimed at
   official statistics added Matthews & Harel (2011, *Statistics Surveys*),
   Templ et al. (2017, *JSS*, the `simPop` package), Kokosi et al. (2022, on
   synthetic administrative data) and Lautrup et al. (2024, *ACM Computing
   Surveys*, on utility metrics for tabular synthesis) — marked **[stats]** in
   the shortlist. Reiter's own methodological papers surfaced repeatedly in the
   search but none had an abstract in OpenAlex, so they are not included; if
   you want a specific one cited, name it and I will add it.
5. Author order and affiliations are placeholders — Dani and Jordi are listed
   as co-authors with a single UPC affiliation each. Correct as needed.
6. Consider whether to add a real-data application section, as the JoC
   exemplar has.
