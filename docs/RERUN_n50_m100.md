# Rerun with n = 50 original datasets and m = 100 synthetic draws per scenario

Agreed by Daniel Fernández (co-author reply, 29 Sep 2026). The design keeps the
same number of synthetic-versus-original pairs as the current run
(144 × 50 × 100 = 720,000), so compute and disk are similar:

* wall time about 9.3–10.5 h on the reference machine with 18 workers
  (Supplementary Table S9), plus about 1 h for the bootstrap null (363 s on 16 workers for 720 original datasets; ×10 for 7,200)
  (720 → 7,200 original datasets × B = 30);
* disk about 22 GB of synthetic Parquet (the current `data/` is 23 GB; 175 GB free
  on the Desktop volume at the time of writing).

**Do not run it in place.** `config.json`, `results/` and `data/` are shared
by every stage, so running in the current checkout would overwrite the m = 1000
results the manuscript is built on. Use a separate copy.

```bash
cd ~/Desktop/personal/academic/research
# 1. separate working copy without data or results
rsync -a --exclude data --exclude results --exclude .venv \
      synthetic-clustering/ synthetic-clustering-n50/
cd synthetic-clustering-n50
mkdir -p results
# 2. design: n = 50 replicates, m = 100 draws (everything else unchanged)
python - <<'EOF'
import json; c = json.load(open("config.json"))
c["simulation"]["n"] = 50; c["simulation"]["m"] = 100
json.dump(c, open("config.json", "w"), indent=2)
EOF
# 3. data outside the repo, as for the main run
export SYNTHCLUST_DATA=~/Desktop/personal/academic/research/ml-research/clustering-n50
mkdir -p "$SYNTHCLUST_DATA"
ln -sfn "$SYNTHCLUST_DATA/data" data
# 4. full pipeline (generation, synthesis, clustering, fidelity, figures)
make all            # or: python scripts/pipeline.py --watch
# 5. bootstrap null and scale-free metrics on the new design
PYTHONPATH=src python -m synthclust.bootstrap_null boot --B 30 --workers 16
PYTHONPATH=src python -m synthclust.bootstrap_null relative --draws 100 --workers 16
PYTHONPATH=src python -m synthclust.bootstrap_null summarize
PYTHONPATH=src python -m synthclust.bootstrap_null tables
```

Notes

* Synthetic seeds are `16 + g·10^7 + r·10^5 + m`; with r ≤ 50 and m ≤ 100 there
  are no collisions. Run the R stages under the `en_US.UTF-8` locale (the scenario
  index g follows R's locale-dependent sort; see the Methods).
* Afterwards the manuscript can either replace the n = 5 design or report the
  n = 50 run as a robustness check; that is an author decision.

## Scheduled run

Steps 1–3 were done on 29 Sep 2026 (`synthetic-clustering-n50/`, data under
`ml-research/clustering-n50/`). `synthetic-clustering-n50/run_night.sh` runs steps 4–5
to completion (about 11 h), started by cron at 01:00 on 30 Sep. If it is interrupted,
starting the script again resumes from the checkpoints (`STOP_AT=09:00` gives an
optional clean stop). Afterwards, `bootstrap_null summarize/tables` still assume 720
datasets (the `/720` shares, the n = 5 wording) and must be adapted before they are run.
