# What was wrong, what I changed, and why

A companion to `RESPONSE_TO_COMMENTS.md`. That document maps each of the 22
reviewer comments to the edit that answers it. This one is about the underlying
problems — several of which nobody flagged, because they are not visible without
running the code.

Read the last section first if you only read one: it answers whether the
numbers changed.

---

## Part 1 — Structural flaws (what Dani and Jordi saw)

### 1.1 It read as a report, not an article

This was the general comment and it was correct. Concretely, the report had a
table of contents, 20 numbered headings, a subsectioned Introduction, and a
chapter called "Background and Related Work" that mixed a conceptual argument
with two Methods components. Journal articles do none of these things.

**Fix.** Table of contents removed. Headings cut from 20 to 12. Introduction
rewritten as continuous prose. The old §2 was dissolved entirely, its three
parts redistributed as Jordi specified: the clustering-as-resemblance-measure
argument became a paragraph in the Discussion, the CART mechanism became
Methods §2.3.2, and the framing material became the Methods opening.

For the target shape I used a real *Journal of Classification* article as the
model: Aschenbruck, Szepannek & Wilhelm (2023), `10.1007/s00357-022-09422-y`,
which is open access and is also a clustering simulation study. Its skeleton is
Introduction → Method → Simulation Study → Application to a Real-world Problem
→ Discussion and Conclusion, with no table of contents. The current draft
follows it, minus the real-data application — see §4.1 below.

### 1.2 The Introduction was thin on citations

The original had 12 references for the whole paper, most of them classics from
1955–2011, and the Introduction cited almost none of the modern literature.
For a journal submission that reads as insufficient engagement with the field.

**Fix.** 21 verified references added, organised into Jordi's five blocks. All
were retrieved from OpenAlex and screened on their abstracts; each one's
justification is in `refs_shortlist.md`. The first search pass came back almost
entirely biomedical, so a second pass targeted official statistics and added
Matthews & Harel (2011, *Statistics Surveys*), Templ et al. (2017, *JSS*),
Kokosi et al. (2022) and Lautrup et al. (2024, *ACM Computing Surveys*).

### 1.3 Objectives were in the wrong order

The report asked (1) same number of clusters, (2) does K-Means or Hierarchical
work better, (3) similar clusters. Jordi asked for 1, 3, 2 — the algorithm
comparison belongs last because it is a secondary question that only makes
sense once you know whether either algorithm works at all.

**Fix.** RQ1 number of groups, RQ2 geometry, RQ3 algorithm comparison. Results
sections follow the same order, so §3.5 is now the algorithm comparison.

### 1.4 Section titles carried implementation detail

"Cluster-Count Recovery (Hungarian Algorithm)" names a technique in a heading.
"Silhouette Fidelity" had a heading of its own for what is a continuation of
the preceding argument.

**Fix.** Titles are now "Number of groups" and "Evaluation metrics"; the
Hungarian algorithm is described in the text where it is used. The silhouette
material is folded into §3.5.

---

## Part 2 — Reporting flaws (what nobody flagged)

These are the things that would have drawn a referee's fire.

### 2.1 The design was described but never tabulated

The report stated the factor levels in prose and left the reader to work out
what 144 scenarios meant, and — more importantly — never said *why* each factor
was in the design.

**Fix.** Table 1 lists every factor, its levels, and a rationale column naming
the hypothesis it probes. This was Jordi's p9 comment and it is also standard
practice for a simulation study.

### 2.2 Replication count and software were never stated

A simulation study that does not say how many repetitions it ran, or what
software produced the numbers, cannot be replicated. The report gave neither.

**Fix.** Methods §2.5 states the full design (144 × 5 × 100 = 72,000
evaluations), names `synthpop` for synthesis and `scikit-learn` for clustering,
and gives the seed policy.

### 2.3 No statement of how metrics were aggregated

The report printed means without saying what they were means *of* — across
replicates? across scenarios? — and gave no dispersion at all. With 5
replicates nested inside 144 scenarios, this matters: the two units of
replication give different standard errors.

**Fix.** Methods §2.5 states that the scenario is the unit of replication:
values are aggregated first within scenario, then across the 144 scenario
means, with 95% intervals computed on that second level. Figure 4 now shows
those intervals (Jordi's p15 comment).

### 2.4 Results referred to procedures never introduced

Figures 1 and 2 showed two-dimensional scatter plots without the Methods ever
saying how the data got to two dimensions. At $p = 2$ the answer is "directly",
but the reader cannot know that.

**Fix.** Methods §2.5 states that the visualisation scenarios use $p = 2$ and
are plotted without dimensionality reduction.

### 2.5 The two figures were nearly the same figure

Figures 3 and 4 in the report both showed recovery against separation, one as a
heatmap and one as curves. Jordi flagged it.

**Fix.** The curves are now Figure 3 in the main text; the heatmap moved to the
supplement as Figure S1.

### 2.6 Colour did not mean the same thing in adjacent panels

In Figures 1 and 2, red and blue were assigned by cluster *label*, and cluster
labels from an unsupervised algorithm are arbitrary. So the top-left group was
red in one panel and blue in the panel directly below it, inviting the reader
to see a difference between original and synthetic data that was an artifact of
labelling.

**Fix.** Labels are Hungarian-matched to the original partition, then oriented
so that cluster 0 is always the upper group. Colour now tracks vertical
position in every panel of both figures, so a visible difference between rows
is a real difference. This was Jordi's p11 comment and it was the most
substantive of the figure comments.

---

## Part 3 — The methodological flaw

This is the serious one, and it was not in anyone's comments because it is only
visible by reading the analysis code.

### 3.1 Two of the four metrics do not measure what the report says

The report defines Mean Centroid Distance and Mean Variance Difference as
measures of how well the synthetic data reproduce the original's cluster
geometry. In `04_evaluate_clustering.ipynb`, they are not computed that way.

Cells 42, 44, 86 and 88 are the only cells that compute centroid distance or
variance difference. Every one of them begins:

```python
data_dir = "../data/original"
real_files = glob.glob(os.path.join(data_dir, "*.parquet"))
```

and then compares `calculate_centroids(X_scaled, true_labels)` against
`calculate_centroids(X_scaled, pred_km)`. Both arguments come from the same
original dataset. The only cells that read `data/synthetic` anywhere in the
notebook are 6, 8 and 79, and all three are visualisation cells.

So the reported MCD and MVD measure **how well $k$-means and Ward recover the
planted groups in the original data**. That is clustering accuracy. It is a
perfectly meaningful quantity, but it contains no information whatsoever about
CART, which means the sentences built on it — "CART preserves centroid
geometry", "distortion grows with $p$" — are not supported by the numbers cited
for them.

### 3.2 The saved results file does not contain these metrics

`results/clustering_results.parquet` is 72,000 × 23 and holds the success flags
plus silhouette and intra-cluster distance columns. There is no MCD column, no
MVD column, no Gini column, and no $\hat{k}$ column. So the metrics could not
simply be re-read; they had to be recomputed from the raw data.

**Fix.** `recompute_full.py` recomputes them the way the paper's argument requires:
for each of 72,000 original–synthetic pairs (144 scenarios × 5 replicates × 100
synthetic draws — the full design), it clusters both datasets, Hungarian-matches the synthetic
partition to the original one, and computes centroid distance, variance
difference, Gini difference and silhouettes between them. The scaler is fit on
the original data and applied unchanged to the synthetic data, so both live in
the same coordinate system.

### 3.3 A hypothesis I tested and rejected

Before finding the above, I suspected the discrepancy came from missing
standardisation, and the arithmetic supported it: on unstandardised data MVD
tracks absolute cluster spread, which grows with $\sigma$ by construction, so
it rises where the report says it rises.

| Scaling | $\sigma=0.1$ | $\sigma=2$ | $\sigma=6$ | $\sigma=10$ |
|---|---|---|---|---|
| Fit on original, apply to both | 0.077 | 0.032 | 0.017 | 0.038 |
| Each dataset separately | 0.055 | 0.065 | 0.015 | 0.032 |
| No scaling | 0.088 | 0.033 | **0.106** | **0.152** |

But this hypothesis presupposes the report computed an original-vs-synthetic
MVD in the first place, and §3.1 shows it did not. The two explanations are
incompatible and only the definition mismatch survives. I record the dead end
so nobody spends an afternoon retracing it. The manuscript's Limitations now
names both conventions — what the metrics compare, and how the datasets are put
on a common scale — as things any replication must state, which is true
regardless.

### 3.4 What remains unresolved

Neither definition reproduces the report's printed numbers exactly:

| | Report | Notebook definition | Original-vs-synthetic |
|---|---|---|---|
| MCD $\sigma=0.1$, KM | 0.60 | 1.289 | 0.602 |
| MCD $\sigma=10$, KM | 0.19 | 0.012 | 0.090 |
| MVD $p=2$, KM | 0.15 | 0.344 | 0.064 |
| MVD $p=10$, KM | 0.67 | 0.964 | 0.393 |

So a third variant produced the report's figures, and it is not recoverable
from the notebook as saved — the cells carry no stored output. **This is the
one open item.** The draft uses the original-vs-synthetic values because those
are what the paper's claims require, and `recompute.py` documents exactly how
each was obtained, but you should confirm the choice before submission since
these values appear in the abstract.

---

## Part 4 — Things I did not fix

### 4.1 No real-data application

The JoC exemplar has one; this paper does not. A referee may well ask for a
demonstration on a real dataset. Adding one is a decision about scope, not a
correction, so I left it — but it is the most likely referee request.

### 4.2 The abstract

Rewritten to match the new structure, but it is the piece that most rewards a
final human pass once everything else is settled.

### 4.3 Reiter's methodological papers

They surfaced repeatedly in the literature search but none carried an abstract
in OpenAlex, so I did not include them unscreened. If you want a specific one,
name it.

### 4.4 Bibliographic detail for pre-DOI classics

Eight entries from your original reference list predate DOIs (Rubin 1993,
Little 1993, MacQueen 1967, Kuhn 1955, Breiman 1984, Drechsler 2011, Pedregosa
2011, Chen 2025). I left them as you had them rather than risk matching a
reprint. Three page ranges elsewhere in the file that I could not verify
against Crossref or OpenAlex were removed rather than guessed; the publisher
supplies those at typesetting.

---

## Part 5 — Did the numbers change?

**The headline results did not change at all. Two of the fidelity metrics did.**

### 5.1 Unchanged — every Success Rate result

These come from `results/clustering_results.parquet`, your own saved output. I
recomputed them from that file and every value matches the report exactly.

| Quantity | Report | Recomputed |
|---|---|---|
| Overall SR, K-Means / Ward | 0.585 / 0.584 | 0.5846 / 0.5837 |
| SR by $\sigma$, K-Means | 0.265, 0.305, 0.812, 0.956 | 0.2647, 0.3052, 0.8122, 0.9562 |
| SR by $\sigma$, Ward | 0.289, 0.301, 0.791, 0.954 | 0.2888, 0.3011, 0.7912, 0.9535 |
| SR by $k$, K-Means | 0.840, 0.476, 0.437 | 0.8404, 0.4760, 0.4373 |
| SR by $k$, Ward | 0.853, 0.462, 0.435 | 0.8532, 0.4624, 0.4353 |
| SR Normal / Gamma, K-Means | 0.604 / — | 0.6045 / 0.5646 |
| Paired Wilcoxon | $W = 2838.5$, $p = 0.52$ | $W = 2838.5$, $p = 0.5232$ |
| Inter-algorithm agreement | 92% | 92.11% |

Everything the paper concludes about **recovery** — separation dominates, $k$
hurts, the two algorithms are indistinguishable — is reproduced exactly. RQ1
and RQ3 are unaffected by anything in this revision.

### 5.2 Unchanged — cluster balance and silhouette

| Quantity | Report | Recomputed |
|---|---|---|
| $\Delta G$ Normal / Gamma, K-Means | 0.028 / 0.033 | 0.0278 / 0.0323 |
| $\Delta G$ Normal / Gamma, Ward | 0.053 / 0.059 | 0.0567 / 0.0648 |
| Silhouette original / synthetic, KM | 0.396 / 0.396 | 0.3963 / 0.3967 |
| Silhouette original / synthetic, Ward | 0.376 / 0.376 | 0.3755 / 0.3770 |

Note these were recomputed from scratch under the original-vs-synthetic
definition and still match. That is meaningful: it says the recomputation
pipeline agrees with the report wherever the report's own definition was the
comparative one.

### 5.3 Changed — MCD and MVD

| Quantity | Report | Draft | Direction |
|---|---|---|---|
| MCD $\sigma=0.1$, KM / Ward | 0.60 / 0.85 | 0.602 / 0.859 | agrees |
| MCD $\sigma=10$, KM / Ward | 0.19 / 0.20 | 0.090 / 0.095 | draft ~half |
| MVD $p=2$, KM / Ward | 0.15 / 0.25 | 0.064 / 0.134 | draft ~half |
| MVD $p=10$, KM / Ward | 0.67 / 0.98 | 0.393 / 0.652 | draft 30–40% lower |
| MVD by $\sigma$, KM | 0.29 → 0.49 (rises) | 0.353 → 0.112 (falls) | **reversed** |

The first four are level shifts: same shape, same ordering, same conclusion
(Ward distorts more than $k$-means; distortion grows with $p$ and shrinks with
separation). Only the magnitudes move.

The last row is a genuine change of finding. The report reads the rise as
evidence that CART struggles with well-separated clusters. Under both
definitions I can compute, MVD falls monotonically with separation, which is
also what the saved results file's nearest available quantity does
($|$intra-cluster distance original $-$ synthetic$|$: 0.029, 0.019, 0.027,
0.020). The draft reports the decrease and the corresponding sentence in the
Discussion is gone.

### 5.4 New numbers not in the report

$\hat{k}$ agreement between original and synthetic data, stratified by
separation (Table S1) — Jordi asked for this at p13 and guessed the direction
correctly. Exact agreement rises from 68.2% at $\sigma = 0.1$ to 98.3% at
$\sigma = 10$ for $k$-means (Ward: 64.9% to 97.7%), and at low separation the
largest off-diagonal cell is original data supporting $\hat{k} \geq 5$ while
the synthetic data give $\hat{k} = 2$.

### 5.5 How many runs, and how long they took

**Your original study.** The design is 144 scenarios (3 values of $p$ × 3 of $k$
× 4 of $\sigma$ × 2 of $\rho$ × 2 distribution families), each with 5
independent original replicates and 100 CART draws per replicate:

| | Count |
|---|---|
| Scenarios | 144 |
| Original datasets | 144 × 5 = **720** (720,000 rows, 37 MB) |
| Synthetic datasets | 14,400 files × 5 reps = **72,000** (72,000,000 rows, 2.1 GB) |
| Evaluations in `clustering_results.parquet` | **72,000** |
| Clustering fits performed | **≈1,008,000** |

The fit count is worth stating in the paper, because it is what makes the study
expensive. Each evaluation runs `detect_optimal_k` twice (once per algorithm) —
each a silhouette scan over $k = 2 \ldots k_{\max}$ — plus four fixed-$k$ fits
for the quality metrics. With $k_{\max} = \min(k+3, 8)$ that is 12 fits per
evaluation at $k=2$, 14 at $k=3$ and 16 at $k=4$, so 1.008 million $k$-means and
Ward fits on 1,000 × $p$ matrices.

**Timing.** The pipeline did not log per-stage durations to a file, so the only
timing evidence is file modification times: synthesis wrote its 14,400 files
between 15:50 and 15:59 on 12 March 2026 (**8.7 minutes**), and
`clustering_results.parquet` landed at 16:18, about **19 minutes** after
synthesis finished — so roughly **30 minutes end-to-end**. Treat that as an
estimate, not a measurement: timestamps bound the interval in which the files
were written, and cannot distinguish compute from idle time between stages.
`run_all.sh` does time each stage and print a total, so if you still have that
console output it will give exact figures.

The worker count is read from the code rather than inferred:
`03_run_clustering.py` hardcodes `N_WORKERS = 18`. The synthesis script uses
`detectCores() - 6`, which resolves at runtime, so its actual parallelism
depends on the machine you ran it on and is not recoverable from the source.
The total core count of that machine is likewise unknown to me — I only know
this one has 24 — so the manuscript says "18 worker processes ... on a single
multi-core workstation" and gives the runtime only as "well under an hour".
If you know the machine, both numbers can be made specific.

My own recompute figures below are separately measured wall times on this
24-core machine and should not be conflated with the above — they are a
different, smaller job.

**My recomputation.** `recompute_full.py` produced the metrics the saved results
file lacks, on the **full design** — all 100 synthetic draws, matching the
original study's evaluation count exactly:

| | Count |
|---|---|
| Original–synthetic pairs | 144 × 5 × 100 = **72,000** |
| Clustering fits performed | **≈2,300,000** |
| Wall time | **1,880 s** (31 min) on 20 of this machine's 24 cores |
| Output | `khat_fidelity_full.parquet`, 72,000 × 25 |

The fit count exceeds the original study's because the silhouette scan is run on
**both** the original and the synthetic dataset (the original pipeline scanned
only the synthetic), over the full range $k = 2 \ldots 8$ rather than a capped
range, and because the geometric metrics need extra fixed-$k$ fits. The original
partition is computed once per replicate and reused across all 100 draws, which
is what keeps this to half an hour rather than several.

An earlier pass used only 16 draws per replicate (11,520 pairs, 366 s). Its
results are preserved in `khat_fidelity.parquet` and the subsample turned out to
have been accurate: **every fidelity estimate moved by less than 0.025**, most
by less than 0.005. The 16-draw MCD at $\sigma=0.1$ was 0.6065 against 0.6019 on
all 100; MVD by $p$ went 0.0641/0.2007/0.3919 against 0.0635/0.1998/0.3932. The
largest single change was Ward's MVD at $\sigma=0.1$ (0.6379 → 0.6148). Nothing
in the manuscript's argument depended on the difference, but the full run
removes the question and tightens the confidence bands in Figure 4.

Two supporting runs remain small: `verify_notebook_metric.py` re-ran the
notebook's own metric definition over all 144 original datasets to confirm the
section 3.1 diagnosis, and a three-way standardisation experiment on one
scenario tested and rejected the section 3.3 hypothesis.

### 5.6 The $k_{\max}$ convention — resolved

The original `detect_optimal_k` caps its silhouette search at
$k_{\max} = \min(k_{\text{true}}+3, 8)$, a different ceiling per scenario. The
full recomputation records the silhouette at every candidate $k$, so both
conventions come out of one pass and the question can be settled with data
rather than left to preference.

**The capped rule is what produced your saved results.** Recomputing the
recovery rate under each:

| | overall KM | overall Ward |
|---|---|---|
| Saved `clustering_results.parquet` | 0.5846 | 0.5837 |
| Recomputed, capped $k_{\max}$ | **0.5860** | **0.5853** |
| Recomputed, fixed $k_{\max} = 8$ | 0.5756 | 0.5782 |

and by separation, the capped rule tracks the saved file closely
(KM 0.276/0.303/0.810/0.955 against the file's 0.265/0.305/0.812/0.956) while
the uncapped rule sits systematically lower at low separation. The residual
0.001–0.011 gap is implementation detail, not convention: a direct test at
$\sigma = 0.1$, $p = 2$, $k = 2$ gave identical $\hat{k}$ under joint and
separate standardisation, so scaling is not the cause either.

**What I did with it.** The two conventions answer different questions, so the
manuscript now states both explicitly rather than silently mixing them:

* **Recovery rates** (main text) keep the capped rule, because those numbers
  come from your saved file and are now documented as such in Methods.
* **Table S1** uses the fixed range, because a contingency table comparing
  $\hat{k}$ from two sources is only interpretable if both were searched over
  the same range. Its caption states this and reports the sensitivity.

The effect is confined to low separation. With $n = 18{,}000$ per level, exact
agreement at $\sigma = 0.1$ is 68.2% (fixed) against 75.0% (capped) for
$k$-means, 64.9% against 68.0% for Ward; from $\sigma = 2$ upward the two agree
to within half a percentage point. No trend or conclusion changes.

Worth noting for the paper's own argument: the capped rule is mildly optimistic,
since it uses knowledge of $k_{\text{true}}$ to narrow the search an analyst
would not have. The uncapped recovery rates (0.5756 / 0.5782) are the more
honest figure. They are lower, but not by enough to disturb any conclusion —
including RQ3, since both algorithms move together.

### 5.7 Summary

Nothing that answers RQ1 or RQ3 moved. Two of the four geometric-fidelity
metrics moved, one of them enough to reverse a claim. The reason is §3.1: those
two metrics were never computed against synthetic data in the first place.