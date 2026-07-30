"""Recompute k-hat recovery and Hungarian-aligned fidelity metrics on the FULL design.

The saved clustering_results.parquet stores only the binary success flags plus
silhouette / intra-distance columns: it has no MCD, MVD, Gini or k-hat column.
This script recomputes those from the raw original and synthetic parquet files.

Differences from the earlier recompute.py:
  * ALL m synthetic draws per replicate, not a subsample of 16
    -> 144 scenarios x 5 replicates x m draws aligned pairs (720,000 at m = 1000),
       matching the evaluation count of the original study exactly.

The unit of work, and so of checkpointing, is one (scenario, replicate): 720 units
rather than 144 whole scenarios. That costs nothing -- the original-data partition is
already reused per replicate, not per scenario -- and it cuts what a kill can destroy
from ~43 min of compute to ~9 min, which is the difference between resuming and
starting over.
  * The silhouette scan is stored per candidate k, so BOTH k_max conventions
    are derived from one pass:
       khat_*_full   argmax over k in 2..8              (symmetric search)
       khat_*_capped argmax over k in 2..min(k_true+3,8) (the original pipeline's rule)
  * The original-data partition is computed ONCE per (replicate, algorithm)
    and reused across all 100 draws, instead of being refitted per draw.

Scaling convention: the StandardScaler is fit on the original data and applied
unchanged to the synthetic data, so MCD and MVD are expressed in a single
coordinate system (REVISION_NOTES.md section 3.2). This is load-bearing: the
alternative conventions, and why omitting standardisation makes MVD appear to
rise with separation, are set out in section 3.3.

Note that the ORIGINAL pipeline scales each dataset independently
(clustering_utils.py calls StandardScaler().fit_transform on every array), so
this script deliberately differs from it. The silhouette columns are unaffected
-- per-feature standardisation leaves silhouette essentially invariant -- but
MCD and MVD are not, since they are distances in the scaled space.
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"

import argparse, itertools, json, time
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from scipy.optimize import linear_sum_assignment

from synthclust.paths import (ORIGINAL_DIR, SYNTHETIC_DIR, FIDELITY_RESULTS,
                              RESULTS_DIR, CONFIG, require)
# NOTE: this module defines its own scenario_tag() below (it doubles as the OD
# filename stem), so only the store is imported here. Importing checkpoint's
# scenario_tag as well would be shadowed by the local definition and the two
# spell rho differently ("0" vs "0.0") -- a silent resume failure.
from synthclust.checkpoint import ScenarioStore
OD = str(ORIGINAL_DIR)
SD = str(SYNTHETIC_DIR)
with open(CONFIG) as _f:
    _cfg = json.load(_f)["simulation"]
N_SYN = _cfg["m"]                       # synthetic draws per original replicate
REPS = list(range(1, _cfg["n"] + 1))    # original replicates
KMIN, KMAX = 2, 8
ALGOS = ("km", "hc")


def fit(X, k, algo):
    if algo == "km":
        m = KMeans(n_clusters=k, n_init=10, random_state=42)
        return m.fit_predict(X)
    return AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)


def sil_scan(X, algo):
    """Average silhouette width for every candidate k in KMIN..KMAX."""
    out = {}
    for k in range(KMIN, KMAX + 1):
        try:
            out[k] = float(silhouette_score(X, fit(X, k, algo)))
        except Exception:
            out[k] = -np.inf
    return out


def argmax_upto(scan, kmax):
    best_k, best_s = KMIN, -np.inf
    for k in range(KMIN, kmax + 1):
        if scan[k] > best_s:
            best_s, best_k = scan[k], k
    return best_k


def gini(sizes):
    n = np.asarray(sizes, float)
    if n.sum() == 0:
        return 0.0
    return float(np.abs(n[:, None] - n[None, :]).sum() / (2 * len(n) * n.sum()))


def partition_stats(X, lab, k):
    cen, var, size = [], [], []
    for j in range(k):
        m = lab == j
        if not m.any():
            cen.append(np.full(X.shape[1], np.nan)); var.append(np.nan); size.append(0)
            continue
        pts = X[m]
        c = pts.mean(axis=0)
        cen.append(c)
        var.append(float(np.mean(((pts - c) ** 2).sum(axis=1))))
        size.append(int(m.sum()))
    return np.array(cen), np.array(var), np.array(size)


def compare(ref, Xs, k, algo):
    """Fidelity of one synthetic dataset against a cached original partition."""
    cr, vr, sr, silr = ref
    ls = fit(Xs, k, algo)
    cs, vs, ss = partition_stats(Xs, ls, k)
    cost = np.nan_to_num(np.linalg.norm(cr[:, None, :] - cs[None, :, :], axis=2), nan=1e9)
    ri, ci = linear_sum_assignment(cost)
    return (float(np.nanmean(cost[ri, ci])),
            float(np.nanmean(np.abs(vr[ri] - vs[ci]))),
            abs(gini(sr) - gini(ss)),
            silr,
            float(silhouette_score(Xs, ls)))


def scenario_tag(p, k, rho, sep, dist):
    r = "0.4" if rho == 0.4 else "0"
    s = {0.1: "0.1", 2: "2", 6: "6", 10: "10"}[sep]
    return f"N1000_p{p}_k{k}_rho{r}_sep{s}_{dist}"


def unit_tag(p, k, rho, sep, dist, rep) -> str:
    """Shard key for one (scenario, replicate) unit.

    Built on the local scenario_tag -- which doubles as the OD filename stem -- so
    that save and lookup cannot drift apart (see tests/test_checkpoint.py).
    """
    return f"{scenario_tag(p, k, rho, sep, dist)}_rep{rep}"


def run_unit(args):
    p, k, rho, sep, dist, rep = args
    tag = scenario_tag(p, k, rho, sep, dist)
    od_path = os.path.join(OD, f"OD_{tag}.parquet")
    if not os.path.exists(od_path):
        return []
    od = pd.read_parquet(od_path)
    feats = [c for c in od.columns if c.startswith("X")]
    cap = min(k + 3, KMAX)

    Rr = od[od["rep"] == rep]
    if Rr.empty:
        return []
    sc = StandardScaler().fit(Rr[feats].values)
    Xr = sc.transform(Rr[feats].values)

    # --- original data: computed once, reused for all m draws of this replicate ---
    r_scan, r_ref = {}, {}
    for a in ALGOS:
        r_scan[a] = sil_scan(Xr, a)
        lr = fit(Xr, k, a)
        cr, vr, sr = partition_stats(Xr, lr, k)
        r_ref[a] = (cr, vr, sr, float(silhouette_score(Xr, lr)))

    base = dict(p=p, k=k, rho=rho, sep=sep, distribution=dist, rep=rep)
    for a in ALGOS:
        base[f"khat_real_{a}_full"] = argmax_upto(r_scan[a], KMAX)
        base[f"khat_real_{a}_capped"] = argmax_upto(r_scan[a], cap)

    rows = []
    for m in range(1, N_SYN + 1):
        sp = os.path.join(SD, f"SD_cart_{tag}_syn{m}.parquet")
        if not os.path.exists(sp):
            continue
        Sr = pd.read_parquet(sp, columns=feats + ["rep"])
        Sr = Sr[Sr["rep"] == rep]
        if Sr.empty:
            continue
        Xs = sc.transform(Sr[feats].values)
        rec = dict(base, syn_idx=m)
        for a in ALGOS:
            s_scan = sil_scan(Xs, a)
            rec[f"khat_syn_{a}_full"] = argmax_upto(s_scan, KMAX)
            rec[f"khat_syn_{a}_capped"] = argmax_upto(s_scan, cap)
            mcd, mvd, dg, silr, sils = compare(r_ref[a], Xs, k, a)
            rec.update({f"mcd_{a}": mcd, f"mvd_{a}": mvd, f"dgini_{a}": dg,
                        f"sil_real_{a}": silr, f"sil_syn_{a}": sils})
        rows.append(rec)
    return rows


def drop_legacy_shards(store) -> int:
    """Delete shards that predate the per-replicate split. Returns how many.

    Those hold a whole scenario and are keyed with no _rep suffix, so they satisfy
    no unit lookup and are not skipped by the merge: load_all() would concatenate
    them on top of the recomputed units and double those rows. Called at startup AND
    immediately before merging, because a concurrent process still running the old
    code can drop one in at any point in between -- which is exactly what a detached
    worker pool from an earlier run does.
    """
    legacy = [p for p in store.dir.glob("*.parquet") if "_rep" not in p.stem]
    for p in legacy:
        p.unlink()
    return len(legacy)


def _run_and_store(g):
    """Compute one (scenario, replicate) unit and checkpoint it immediately.

    Called in a worker process, so the shard is on disk the moment the unit
    finishes -- not held until the whole stage completes.
    """
    store = ScenarioStore(RESULTS_DIR, "metrics")
    tag = unit_tag(*g)
    rows = run_unit(g)
    if not rows:
        # Inputs missing -- do NOT checkpoint, so a later run retries it.
        return tag, 0
    store.save(tag, rows)
    return tag, len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--restart", action="store_true",
                    help="discard checkpoints and recompute every scenario")
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()

    # One unit per (scenario, replicate): 144 x 5 = 720.
    grid = list(itertools.product([2, 5, 10], [2, 3, 4], [0.0, 0.4],
                                  [0.1, 2, 6, 10], ["normal", "gamma"], REPS))

    store = ScenarioStore(RESULTS_DIR, "metrics")
    if args.restart:
        store.discard()
        store = ScenarioStore(RESULTS_DIR, "metrics")
    stale = store.clear_stale_temporaries()
    if stale:
        print(f"cleared {stale} stale temporary file(s)", flush=True)

    n = drop_legacy_shards(store)
    if n:
        print(f"removed {n} scenario-level shard(s) predating the per-replicate "
              f"split; those units will be recomputed", flush=True)

    todo = [g for g in grid if not store.has(unit_tag(*g))]
    done_already = len(grid) - len(todo)
    if done_already:
        print(f"resuming: {done_already}/{len(grid)} units already checkpointed",
              flush=True)
    if not todo:
        print("all units present; merging", flush=True)

    t0 = time.time()
    empty = []
    if todo:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(_run_and_store, g): g for g in todo}
            for i, f in enumerate(as_completed(futs), 1):
                tag, n = f.result()          # re-raise worker exceptions
                if n == 0:
                    empty.append(tag)
                if i % 8 == 0 or i == len(todo):
                    el = time.time() - t0
                    print(f"{i}/{len(todo)} units  {el:.0f}s  "
                          f"eta={el/i*(len(todo)-i):.0f}s", flush=True)

    if empty:
        print(f"\nWARNING: {len(empty)} unit(s) produced no rows -- their "
              f"synthetic data is missing. Not checkpointed; rerun after "
              f"synthesis completes. First few: {empty[:3]}", flush=True)

    n = drop_legacy_shards(store)
    if n:
        print(f"\nWARNING: removed {n} scenario-level shard(s) that appeared DURING "
              f"this run -- a concurrent process is running the pre-split code. "
              f"Excluded from the merge; check for a detached worker pool.",
              flush=True)

    df = store.load_all()
    if len(df) == 0:
        raise SystemExit("no rows produced -- has synthesis finished?")

    # An incomplete run must NOT write FIDELITY_RESULTS, and must NOT discard its
    # shards. make guards this stage on an mtime comparison against
    # clustering_results.parquet, so a partial file written here would be newer,
    # `make all` would skip the stage, and the manuscript would be built from
    # partial data -- silently. Discarding the shards on top of that would also
    # throw away the completed units, making "rerun to finish" impossible.
    if store.count() < len(grid):
        partial = FIDELITY_RESULTS.with_suffix(".partial.parquet")
        df.to_parquet(str(partial))
        raise SystemExit(
            f"\nINCOMPLETE: {store.count()}/{len(grid)} units. Wrote {partial.name} "
            f"for inspection; {FIDELITY_RESULTS.name} left untouched and "
            f"{len(grid) - store.count()} unit(s) kept on disk. Rerun to finish.")

    df.to_parquet(str(FIDELITY_RESULTS))
    store.discard()
    print("DONE", df.shape, f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
