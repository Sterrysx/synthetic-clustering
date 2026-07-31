# Does synthetic data preserve cluster structure?

A factorial evaluation of partitioning and hierarchical clustering on
CART-generated data.

Companion code for the manuscript in `manuscript/`. 144 scenarios crossing
cluster count, separation, dimensionality, correlation and distribution family;
72,000 original–synthetic dataset pairs; recovery of the number of groups plus
three geometric-fidelity metrics.

## Install

Requires [uv](https://docs.astral.sh/uv/) and, for data generation only, R.

```bash
uv sync                 # creates .venv and installs the package
```

The R scripts need `jsonlite`, `mvtnorm`, `arrow` and `synthpop`. Install once:

```bash
Rscript R/setup.R
```

This creates your personal R library if it does not exist and installs there —
no root, and the system library is left alone. A bare
`Rscript -e 'install.packages(...)'` does **not** work here: non-interactive R
will not offer to create a personal library the way an interactive session does,
so it targets `/usr/local/lib/R/site-library` and fails with *"lib is not
writable"*.

**`arrow` must be built with ZSTD support.** The parquet datasets are
ZSTD-compressed, and a minimal `arrow` build — what you get when the source
install cannot find `libarrow` — fails only at read time with *"Support for codec
'zstd' not built"*. `R/setup.R` checks for this and tells you what to do. The fix:

```bash
Rscript -e 'Sys.setenv(LIBARROW_MINIMAL="false", ARROW_WITH_ZSTD="ON");
            install.packages("arrow", repos="https://cloud.r-project.org")'
```

If it still builds minimal, install the system library first
(`sudo apt install libarrow-dev libparquet-dev`) and reinstall. `arrow` may also
need `libcurl4-openssl-dev` and `libssl-dev` to build at all.

To check an existing install: `Rscript -e 'arrow::arrow_info()$capabilities'`.

**If you cannot get a ZSTD-capable `arrow`**, convert the datasets instead —
pyarrow ships every codec, so the Python side is unaffected either way:

```bash
uv run convert-codec --check          # report current codecs
uv run convert-codec                  # zstd -> uncompressed, in place, ~2 s
export SYNTHCLUST_PARQUET_CODEC=uncompressed   # so new files match
```

Costs little disk, because float64 noise barely compresses — measured over every
file: `data/original` 38.0 → 39.7 MB (+4.4%), `data/synthetic` 2.12 → 2.17 GB
(+2.4%), projecting to 21.2 → 21.8 GB at m = 1000. The conversion is lossless
and idempotent — each file is
rewritten via a temporary and verified against the original before replacing it.

The generation scripts check for these packages and stop with a pointer to
`R/setup.R` if any are missing; they never install anything themselves.

Both R scripts resolve the repository from their own path, so they can be run
from any working directory.

## Running the whole pipeline

```bash
make all          # setup -> data -> clustering -> metrics -> figures -> PDFs
make status       # what exists now
make help         # all targets
make verify       # check every parquet is readable and complete
```

`make all` skips stages whose outputs are already present and current, so it is
safe to re-run after an interruption. `make setup` runs every time (it is
idempotent, and it is what catches an `arrow` build missing a needed codec).

**Every stage is resumable.** Kill any of them and re-run `make all`; work
already finished is kept.

| stage | unit of progress | on restart |
|---|---|---|
| `original` | one dataset file | skips files that exist |
| `synthetic` | one dataset file | skips files that exist |
| `cluster` | one design scenario (144) | skips checkpointed scenarios |
| `metrics` | one design scenario (144) | skips checkpointed scenarios |

Synthesis writes each dataset to a temporary and renames it — rename is atomic,
so a kill cannot leave a half-written file that the skip check would later
accept. The analysis stages write a per-scenario shard into
`results/.partial_<stage>/` as each scenario finishes, then merge the shards into
the final parquet and delete the directory. Worst case you lose the scenarios
that were in flight, not the stage.

Two things the checkpointing deliberately refuses to do:

- **It never records an empty scenario.** An empty result means the inputs were
  missing (typically synthesis had not reached that scenario yet), not that the
  work is done — recording it would skip that scenario permanently and silently
  drop it from the merged output. Such scenarios are reported and retried.
- **It warns rather than pretending completeness.** If fewer than 144 scenarios
  are present at merge time you get an explicit `PARTIAL result` warning.

Force a clean recomputation with `--restart`:

```bash
uv run recompute-metrics --restart
uv run run-clustering --restart
```

Wall times from the completed m = 1000 run (18 workers, Ryzen 9 9900X):
synthesis 1.24 h, clustering ~2.0 h, metrics 4.44 h, total ~7.6 h. See
"Adapting the parallelism to your hardware" below for what is measured and what
is extrapolated.

Results carry a `results/.design-m<M>` stamp. Changing `m` invalidates it and
forces the analysis stages to rerun, so results from a previous `m` cannot be
silently mistaken for current ones.

## Changing the number of synthetic draws (m)

`m` is read from `config.json` by every stage, so change it in one place:

```json
"m": 1000
```

Then regenerate — the existing datasets are for the old `m` and are not reused.
Move them aside first rather than deleting:

```bash
mv data/synthetic data/synthetic_m100
make all
```

Or stage by stage, with the estimates from above:

```bash
Rscript R/generate_synthetic.R      # 1.24 h, 21 GB at m = 1000
uv run run-clustering               # ~2.0 h
uv run recompute-metrics            # 4.44 h
```

Costs scale linearly in `m`: at `m = 1000` expect **~7.7 h total** and 21 GB of
synthetic data (144,000 files). See the estimate provenance above — these are
per-unit costs measured on this machine and multiplied out, not timings from a
completed `m = 1000` run.

**The seed stride was widened for `m > 100`.** The original formula reserved 100
seed slots per replicate, so at `m = 1000` a draw's seed collided with a
different replicate's draw (rep 1 draw 200 and rep 2 draw 100 both got 10316) —
96% of draws at `m = 1000` shared a seed with another draw. The stride is now
`10^7` per scenario and `10^5` per replicate, supporting `m` up to 99,999. This
changes every seed, so datasets regenerated now will **not** be bit-identical to
the committed `results/*.parquet`, which came from the original `m = 100` run.

## Data

The generated datasets are 2.1 GB (144 original + 14,400 synthetic parquet
files) and are **not** committed. Three ways to get them, cheapest first:

1. **You may not need them.** `results/clustering_results.parquet` and
   `results/khat_fidelity_full.parquet` are committed and contain every number
   in the manuscript. Rebuilding the figures, the supplementary table or the PDFs
   needs only those two files — the raw datasets are not read.
2. **Point at an existing copy.** `data/` here is a symlink to the original
   study directory. If you move things, either repoint it or set:
   ```bash
   export SYNTHCLUST_DATA=/path/containing/data/
   ```
   The target must contain `data/original/` and `data/synthetic/`.
3. **Regenerate** with the two R scripts (step 1–2 below). Deterministic:
   `config.json` fixes `random_seed_base = 16`, so you get the same datasets.
   Needs R with `synthpop`, `arrow`, `mvtnorm`, `jsonlite`, and ~2.2 GB free.

## Reproduce

Start at whichever step you have inputs for. **With this repository as shipped,
step 5 works immediately** — everything above it is already done.

| | step | command | needs | runtime |
|---|---|---|---|---|
| 1 | 144 original datasets | `Rscript R/generate_original.R` | R + packages | ~1 min |
| 2 | 14,400 synthetic datasets | `Rscript R/generate_synthetic.R` | step 1 | ~9 min |
| 3 | recovery of the number of groups | `uv run run-clustering` | steps 1–2 | ~20 min |
| 4 | fidelity metrics, both $k_{\max}$ rules | `uv run recompute-metrics` | steps 1–2 | **31 min** |
| 5 | figures + supplementary table | `uv run make-figures`<br>`uv run make-supp-table` | `results/*.parquet` | ~5 s |
| 6 | the PDFs | `cd manuscript && ./build.sh main`<br>`./build.sh supplementary` | step 5 | ~10 s |

Steps 3 and 4 are independent of each other; both read the datasets and neither
reads the other's output. Step 5 reads only the two committed parquet files.

Runtimes measured on a 24-core workstation: step 4 at 1,880 s over 20 worker
processes is the only substantial one. Steps 1–3 are quoted from the original
study's file timestamps rather than measured directly, so treat them as
approximate. Step 2 writes 2.1 GB.

## Layout

```
config.json                    the design grid (N, p, k, rho, sep, m, seeds)
R/
  generate_original.R          144 OD datasets from the factorial design
  generate_synthetic.R         14,400 SD datasets via synthpop CART
src/synthclust/
  paths.py                     filesystem layout, SYNTHCLUST_DATA override
  clustering_utils.py          detect_optimal_k, quality metrics
  run_clustering.py            72,000 evaluations -> clustering_results.parquet
  recompute_metrics.py         MCD, MVD, dGini, silhouette, both k_max rules
  make_figures.py              the seven manuscript figures
manuscript/
  main.tex supplementary.tex   the article
  refs.bib                     31 references
  sn-jnl.cls sn-basic.bst      Springer Nature class (see caveat below)
  supp_table.tex               generated by `uv run make-supp-table`
  figures/                     7 figures as pdf + png
  build.sh                     three-pass pdftex + bibtex
results/
  clustering_results.parquet   72,000 x 23  recovery results
  khat_fidelity_full.parquet   72,000 x 25  fidelity metrics, both k_max rules
docs/
  REVISION_NOTES.md            every flaw found in the first draft and its fix
  RESPONSE_TO_COMMENTS.md      comment-by-comment reply to the reviewers
  CODE_STRUCTURE.md            what changed from the original pipeline and why
  refs_shortlist.md            22 screened reference candidates
  verify_notebook_metric.py    forensic: reproduces the superseded metric
```

## Adapting the parallelism to your hardware

Every stage is embarrassingly parallel over design units, so the pipeline scales
with cores and needs no configuration to run correctly — only to run *well* on a
machine unlike the one used here.

**One knob, everywhere.** `SYNTHCLUST_WORKERS` sets the worker count for all four
stages (both R generators, the clustering evaluation, and the fidelity metrics):

```bash
SYNTHCLUST_WORKERS=8 make all        # 8 workers throughout
uv run recompute-metrics --workers 8 # or per-stage, for the Python stages
```

Unset, each stage defaults to roughly two below the detected core count. That is
a reasonable default on a dedicated machine and too aggressive on a laptop you
are also using.

**Memory is the real constraint, not cores.** Ward's linkage and the silhouette
both need the pairwise distance structure, so each worker holds
$O(N^2)$ doubles: about 8 MB per worker at `N = 1000`, but 800 MB at
`N = 10000`. Raising `N` while keeping the worker count fixed is what runs a
machine out of memory. Budget roughly

```
workers x (N/1000)^2 x 8 MB
```

and leave headroom. At the default `N = 1000` this is negligible and you can use
every core.

**Reference timings.** On an AMD Ryzen 9 9900X (12 cores / 24 threads, 46 GiB)
with 18 workers, at `m = 1000`:

| stage | wall time | evidence |
|---|---|---|
| synthetic data (144,000 datasets) | 1.24 h | interval over which outputs were written |
| clustering (720,000 pairs) | ~2.0 h | extrapolated from a directly timed 0.88 s/dataset |
| fidelity metrics (1.15e7 fits) | 4.44 h | instrumented, direct measurement |
| **total** | **~7.6 h** | |

Scaling is linear in `m` and in the number of scenarios, and quadratic in `N`.
At `m = 100` the whole pipeline takes about a tenth as long and reproduces every
reported estimate to within 0.025 — useful for a smoke test before committing to
the full run. Disk: 21 GB of synthetic Parquet at `m = 1000`, 2.1 GB at `m = 100`.

**If a stage dies, just re-run it.** Generation skips datasets that already
exist; the two analysis stages checkpoint each of the 720 (scenario, replicate)
units and resume from the last completed one. Nothing is lost but the units in
flight.

## Two things to know

**The metrics come from two different scripts, deliberately.**
`run_clustering.py` (unchanged from the original study) produces the recovery
rates. `recompute_metrics.py` produces the geometric-fidelity metrics, which the
original pipeline never saved. The two use different `k_max` conventions and
different standardisation; both are documented in
`docs/REVISION_NOTES.md` sections 3.2 and 5.6, and `recompute_metrics.py`'s
docstring states its own convention. Read that before comparing numbers across
the two files.

**`sn-jnl.cls` came from a third-party mirror.** Springer's own download page was
unreachable when this was assembled, so the class was fetched from a GitHub
mirror. It compiles correctly, but **replace it with the official copy from
Springer before submitting**. If the journal requires numbered mathphys style,
switch to `\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}` and obtain
`sn-mathphys-num.bst`.

`manuscript/build.sh` and `manuscript/texfmt/` are workarounds for a broken TeX
Live install on the machine this was written on. On a normal install,
`latexmk -pdf main.tex` is enough and both can be deleted.
