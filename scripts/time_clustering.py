"""Measure the wall time of the clustering stage.

Why this exists: `run-clustering` prints its own elapsed time, but its live
dashboard needs an `mp.Manager()` socket, which is not permitted in every
execution environment. This harness runs the SAME per-file computation over the
SAME task list with the SAME worker count, dropping only the progress dashboard,
so the reported wall time is comparable to a production run.

It measures; it does not write results. `results/clustering_results.parquet` is
untouched. Use `run-clustering` to regenerate results.

    python scripts/time_clustering.py
"""
import glob
import os
import re
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import multiprocessing as mp

from synthclust import run_clustering as rc
from synthclust.paths import ORIGINAL_DIR, SYNTHETIC_DIR

_SD = re.compile(
    r"SD_cart_(N\d+_p(\d+)_k(\d+)_rho[\d.]+_sep[\d.]+_\w+?)_syn\d+\.parquet"
)

_OD = {os.path.basename(f): f for f in glob.glob(str(ORIGINAL_DIR / "*.parquet"))}


def time_one(fp):
    """Run one SD file's computation, mirroring `_process_one_sd`.

    Returns the number of (replicate) evaluations performed.
    """
    import pandas as pd
    from sklearn.preprocessing import StandardScaler

    from synthclust.clustering_utils import (calculate_quality_metrics,
                                             detect_optimal_k)

    m = _SD.match(os.path.basename(fp))
    if not m:
        return 0
    tag, p_val, k_truth = m.group(1), int(m.group(2)), int(m.group(3))
    od_fp = _OD.get(f"OD_{tag}.parquet")
    if od_fp is None:
        return 0

    x_cols = [f"X{i}" for i in range(1, p_val + 1)]
    k_max = min(k_truth + 3, 8)
    od_df = pd.read_parquet(od_fp)
    sd_df = pd.read_parquet(fp)
    od_groups = {r: g for r, g in od_df.groupby("rep")}

    n = 0
    for rep, sd_grp in sd_df.groupby("rep"):
        if rep not in od_groups:
            continue
        X_sd = StandardScaler().fit_transform(sd_grp[x_cols].values)
        X_od = StandardScaler().fit_transform(od_groups[rep][x_cols].values)
        detect_optimal_k(X_sd, method="kmeans", k_max=k_max)
        detect_optimal_k(X_sd, method="hierarchical", k_max=k_max)
        for X in (X_od, X_sd):
            calculate_quality_metrics(X, k_truth, "kmeans")
            calculate_quality_metrics(X, k_truth, "hierarchical")
        n += 1
    return n


def main():
    sd_files = sorted(glob.glob(str(SYNTHETIC_DIR / "*.parquet")))
    if not sd_files:
        raise SystemExit(f"no synthetic files under {SYNTHETIC_DIR}")
    print(f"[info] {len(sd_files):,} SD files, {len(_OD)} OD files, "
          f"{rc.N_WORKERS} workers", flush=True)

    t0 = time.time()
    done = evals = 0
    with mp.Pool(processes=rc.N_WORKERS) as pool:
        for got in pool.imap_unordered(time_one, sd_files, chunksize=16):
            done += 1
            evals += got
            if done % 5000 == 0:
                el = time.time() - t0
                print(f"[prog] {done:,}/{len(sd_files):,} files  {el:.0f}s  "
                      f"eta={(len(sd_files) - done) * el / done:.0f}s", flush=True)

    el = time.time() - t0
    print(f"[DONE] {evals:,} evaluations in {el:.1f}s "
          f"({evals / el:,.0f} evals/sec, {rc.N_WORKERS} workers)", flush=True)


if __name__ == "__main__":
    main()
