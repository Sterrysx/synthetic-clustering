"""
Case study: k-means and Ward on CART-synthesised diabetes data (Reaven & Miller 1979).

Same metrics as the simulation, computed with the simulation's own functions
(synthclust.recompute_metrics / synthclust.bootstrap_null):
  k-hat by silhouette over k = 2..8; RR = P(k-hat = 3 clinical classes);
  AG = P(k-hat_S = k-hat_R); MCD, MVD, dGini, RVD at k = 3 after Hungarian alignment;
  ARI at k = 3 between the original partition and the real points assigned to the
  nearest synthetic centroid (and the same against the clinical classes).
Each is compared with a nonparametric bootstrap null (B draws of the original rows),
as in the manuscript. Scaling: StandardScaler fitted on the original, applied to all.
Usage: PYTHONPATH=src python scripts/case_study/diabetes_analysis.py [--B 1000] [--workers 20]
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[v] = "1"
import argparse, json, time
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor
from sklearn.preprocessing import StandardScaler
from scipy.stats import binomtest
from sklearn.metrics import adjusted_rand_score
from synthclust import recompute_metrics as rm
from synthclust.bootstrap_null import reference, compare_ext

OUT = os.path.join("results", "case_study")
FEATS = ["glucose", "insulin", "sspg"]
K_CLIN = 3
SEED = 20260930
_G = {}


def _init(Xr, refs, ref_lab, clin):
    _G["Xr"], _G["refs"], _G["lab"], _G["clin"] = Xr, refs, ref_lab, clin


def transfer(X, a):
    """Partition of the REAL points induced by a partition of X (synthetic or bootstrap).

    Fit algorithm a with k = 3 on X, take its cluster means, and assign every real
    point to the nearest one (Euclidean, in the original's standardised space).
    No correspondence between real and synthetic records is needed: both labelings
    are on the same N real points, and ARI ignores how the clusters are named.
    """
    lab = rm.fit(X, K_CLIN, a)
    cen = np.array([X[lab == j].mean(axis=0) for j in range(K_CLIN) if np.any(lab == j)])
    d = ((_G["Xr"][:, None, :] - cen[None, :, :]) ** 2).sum(axis=2)
    return d.argmin(axis=1)


def _one(job):
    kind, i, X = job
    rows = []
    for a in rm.ALGOS:
        scan = rm.sil_scan(X, a)
        mcd, mvd, dg, rvd, silr, sils = compare_ext(_G["refs"][a], X, K_CLIN, a)
        tl = transfer(X, a)
        rows.append(dict(kind=kind, draw=i, algo=a, khat=rm.argmax_upto(scan, rm.KMAX),
                         mcd=mcd, mvd=mvd, dgini=dg, rvd=rvd, sil=sils,
                         ari=adjusted_rand_score(_G["lab"][a], tl),
                         ari_clin=adjusted_rand_score(_G["clin"], tl),
                         n_unique=int(np.unique(X, axis=0).shape[0])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--synth", default="diabetes_synthetic.csv",
                    help="synthetic draws (e.g. one per variable ordering)")
    ap.add_argument("--tag", default="", help="suffix for the output files")
    a = ap.parse_args()
    od = pd.read_csv(os.path.join(OUT, "diabetes_original.csv"))
    sd = pd.read_csv(os.path.join(OUT, a.synth))
    sc = StandardScaler().fit(od[FEATS].values)
    Xr = sc.transform(od[FEATS].values)
    refs = {al: reference(Xr, K_CLIN, al) for al in rm.ALGOS}
    ref_lab = {al: rm.fit(Xr, K_CLIN, al) for al in rm.ALGOS}
    clin = od.group.astype("category").cat.codes.values
    # ceiling: real points assigned to the nearest ORIGINAL centroid (1 for k-means,
    # whose partition is a nearest-centroid one; below 1 for Ward)
    ceil = {}
    for al in rm.ALGOS:
        cen = np.array([Xr[ref_lab[al] == j].mean(axis=0) for j in range(K_CLIN)])
        nl = ((Xr[:, None, :] - cen[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        ceil[al] = dict(ari_ceiling=float(adjusted_rand_score(ref_lab[al], nl)),
                        ari_clin_original=float(adjusted_rand_score(clin, ref_lab[al])))
    orig = {}
    for al in rm.ALGOS:
        scan = rm.sil_scan(Xr, al)
        orig[al] = dict(khat=rm.argmax_upto(scan, rm.KMAX), scan=scan)
    rng = np.random.default_rng(SEED)
    N = len(Xr)
    jobs = [("syn", m, sc.transform(g[FEATS].values)) for m, g in sd.groupby("syn")]
    jobs += [("boot", b, Xr[rng.integers(0, N, N)]) for b in range(a.B)]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(Xr, refs, ref_lab, clin)) as ex:
        rows = [r for rs in ex.map(_one, jobs, chunksize=8) for r in rs]
    d = pd.DataFrame(rows)
    for al in rm.ALGOS:
        d.loc[d.algo == al, "khat_real"] = orig[al]["khat"]
    d["ag"] = (d.khat == d.khat_real).astype(int)
    d["rr"] = (d.khat == K_CLIN).astype(int)
    d.to_csv(os.path.join(OUT, f"diabetes_draws{a.tag}.csv"), index=False)

    # exact-match (privacy-free descriptive) and duplicate checks
    orig_rows = set(map(tuple, od[FEATS].values))
    share_copied = float(np.mean([tuple(r) in orig_rows for r in sd[FEATS].values]))

    summ = dict(synth_file=a.synth, n=N, m=int(sd.syn.nunique()), B=a.B, seconds=round(time.time() - t0, 1),
                share_synthetic_rows_identical_to_an_original_row=share_copied,
                class_sizes=od.group.value_counts().to_dict(), algos={})
    for al in rm.ALGOS:
        S = d[(d.algo == al) & (d.kind == "syn")].sort_values("draw")
        Bt = d[(d.algo == al) & (d.kind == "boot")]
        e = dict(khat_original=int(orig[al]["khat"]),
                 sil_scan_original={int(k): float(v) for k, v in orig[al]["scan"].items()},
                 khat_dist_syn=S.khat.value_counts(normalize=True).sort_index().round(4).to_dict(),
                 khat_dist_boot=Bt.khat.value_counts(normalize=True).sort_index().round(4).to_dict())
        e.update(ceil[al])
        for met in ("ag", "rr", "mcd", "mvd", "dgini", "rvd", "ari", "ari_clin"):
            s, b = S[met].values, Bt[met].values
            e[met] = dict(syn=float(s.mean()), boot=float(b.mean()), excess=float(s.mean() - b.mean()),
                          se_syn=float(s.std(ddof=1) / np.sqrt(len(s))),
                          se_boot=float(b.std(ddof=1) / np.sqrt(len(b))))
        summ["algos"][al] = e
    # paired k-means vs Ward on the same synthetic draws (exact McNemar on AG)
    K = d[(d.kind == "syn") & (d.algo == "km")].sort_values("draw").ag.values
    H = d[(d.kind == "syn") & (d.algo == "hc")].sort_values("draw").ag.values
    n10, n01 = int(((K == 1) & (H == 0)).sum()), int(((K == 0) & (H == 1)).sum())
    summ["mcnemar_ag_km_vs_hc"] = dict(km_only=n10, hc_only=n01,
                                       p=float(binomtest(n10, n10 + n01).pvalue) if n10 + n01 else 1.0)
    # paired k-means vs Ward on the bootstrap resamples (exact McNemar on AG0)
    K = d[(d.kind == "boot") & (d.algo == "km")].sort_values("draw").ag.values
    H = d[(d.kind == "boot") & (d.algo == "hc")].sort_values("draw").ag.values
    n10, n01 = int(((K == 1) & (H == 0)).sum()), int(((K == 0) & (H == 1)).sum())
    summ["mcnemar_ag0_km_vs_hc"] = dict(km_only=n10, hc_only=n01,
                                        p=float(binomtest(n10, n10 + n01).pvalue) if n10 + n01 else 1.0)
    json.dump(summ, open(os.path.join(OUT, f"diabetes_summary{a.tag}.json"), "w"), indent=2, default=float)
    print(json.dumps({al: {m: round(summ["algos"][al][m]["syn"], 3) for m in ("ag", "rr", "mcd")}
                      for al in rm.ALGOS}), summ["seconds"])


if __name__ == "__main__":
    main()
