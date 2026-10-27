"""
Purpose: Partition-level agreement (ARI) between original and synthetic data without
         record matching, for every original dataset of the simulation, with its
         bootstrap null. Supplementary analysis requested by the co-authors (Oct 2026).
Usage:   PYTHONPATH=src python -m synthclust.ari_null run --workers 20
         PYTHONPATH=src python -m synthclust.ari_null summarize
         PYTHONPATH=src python -m synthclust.ari_null table

Definition (Dudoit & Fridlyand 2002; Tibshirani & Walther 2005 use the same transfer):
  L_R  = partition of the original dataset X_R by algorithm a at the planted k
  L_S  = each point of X_R assigned to the nearest cluster mean of the partition of
         the synthetic dataset X_S by a at the same k
  ARI  = adjusted Rand index between L_R and L_S, on the same N original points.
No correspondence between original and synthetic records is needed, and ARI is
invariant to how the clusters are labelled. ARI0 is the same quantity with X_S
replaced by a bootstrap resample of X_R, using the resamples of bootstrap_null.py
(seed [20260929, s, r, b]). "ceiling" is ARI between L_R and the assignment of X_R to
its own cluster means: 1 for k-means, below 1 for Ward.
Outputs: results/ari_pairs.parquet (one row per original-synthetic pair),
         results/ari_boot.parquet, results/ari_summary.json
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"
import argparse, json
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from synthclust import recompute_metrics as rm
from synthclust import bootstrap_null as bn
from synthclust.checkpoint import ScenarioStore
from synthclust.paths import RESULTS_DIR

PAIRS_OUT = RESULTS_DIR / "ari_pairs.parquet"
BOOT_OUT = RESULTS_DIR / "ari_boot.parquet"
SUMM_OUT = RESULTS_DIR / "ari_summary.json"
B = 30


def nearest(Xr, X, lab, k):
    cen = np.array([X[lab == j].mean(axis=0) for j in range(k) if np.any(lab == j)])
    return ((Xr[:, None, :] - cen[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)


def unit(u):
    s, p, k, rho, sep, dist, rep = u
    tag, feats, sc, Xr, _ = bn.load_original(p, k, rho, sep, dist, rep)
    base = dict(p=p, k=k, rho=rho, sep=sep, distribution=dist, rep=rep)
    ref, ceil = {}, {}
    for a in rm.ALGOS:
        ref[a] = rm.fit(Xr, k, a)
        ceil[a] = adjusted_rand_score(ref[a], nearest(Xr, Xr, ref[a], k))
    pairs = []
    for m in range(1, rm.N_SYN + 1):
        Sr = pd.read_parquet(os.path.join(rm.SD, f"SD_cart_{tag}_syn{m}.parquet"),
                             columns=feats + ["rep"])
        Xs = sc.transform(Sr.loc[Sr["rep"] == rep, feats].values)
        rec = dict(base, syn_idx=m)
        for a in rm.ALGOS:
            rec[f"ari_{a}"] = adjusted_rand_score(ref[a], nearest(Xr, Xs, rm.fit(Xs, k, a), k))
        pairs.append(rec)
    boot = []
    N = Xr.shape[0]
    for b in range(B):
        idx = np.random.default_rng([bn.BASE_SEED, s, rep, b]).integers(0, N, N)
        Xb = Xr[idx]
        rec = dict(base, b=b)
        for a in rm.ALGOS:
            rec[f"ari0_{a}"] = adjusted_rand_score(ref[a], nearest(Xr, Xb, rm.fit(Xb, k, a), k))
            rec[f"ceiling_{a}"] = ceil[a]
        boot.append(rec)
    return pairs, boot


class _Job:
    def __call__(self, u):
        pairs, boot = unit(u)
        ScenarioStore(RESULTS_DIR, "ari_pairs").save(bn.utag(u), pairs)
        ScenarioStore(RESULTS_DIR, "ari_boot").save(bn.utag(u), boot)
        return bn.utag(u)


def run(args):
    sp, sb = ScenarioStore(RESULTS_DIR, "ari_pairs"), ScenarioStore(RESULTS_DIR, "ari_boot")
    sp.clear_stale_temporaries(); sb.clear_stale_temporaries()
    units = bn.unit_list()
    if args.limit:
        units = units[:args.limit]
    todo = [u for u in units if not (sp.has(bn.utag(u)) and sb.has(bn.utag(u)))]
    print(f"[ari] units={len(units)} todo={len(todo)}", flush=True)
    if todo:
        bn.run_pool(_Job(), todo, args.workers, "ari")
    if args.limit:
        return
    P = sp.load_all().sort_values(bn.KEYS + ["syn_idx"]).reset_index(drop=True)
    Q = sb.load_all().sort_values(bn.KEYS + ["b"]).reset_index(drop=True)
    assert len(P) == len(units) * rm.N_SYN and len(Q) == len(units) * B, (P.shape, Q.shape)
    P.to_parquet(PAIRS_OUT, index=False); Q.to_parquet(BOOT_OUT, index=False)
    print("[ari] wrote", PAIRS_OUT, P.shape, BOOT_OUT, Q.shape, flush=True)


def summarize(args):
    P, Q = pd.read_parquet(PAIRS_OUT), pd.read_parquet(BOOT_OUT)
    S = bn.SCEN
    ds = (P.groupby(bn.KEYS)[["ari_km", "ari_hc"]].mean()
          .join(Q.groupby(bn.KEYS)[["ari0_km", "ari0_hc", "ceiling_km", "ceiling_hc"]].mean()))
    sc = ds.groupby(S).mean().reset_index()
    for a in rm.ALGOS:
        sc[f"ex_{a}"] = sc[f"ari_{a}"] - sc[f"ari0_{a}"]
    cols = [f"{x}_{a}" for x in ("ari", "ari0", "ex", "ceiling") for a in rm.ALGOS]
    out = {"_description": __doc__.split("Outputs:")[0].strip(),
           "n_pairs": int(len(P)), "n_boot": int(len(Q)), "B": B,
           "overall": sc[cols].mean().to_dict()}
    for f in ("distribution", "sep", "k", "p", "rho"):
        out[f"by_{f}"] = {str(g): v[cols].mean().to_dict() for g, v in sc.groupby(f)}
    out["by_sep_x_distribution"] = {f"{g[0]},{g[1]}": v[cols].mean().to_dict()
                                    for g, v in sc.groupby(["sep", "distribution"])}
    W = {}
    for lab, sub in (("all", sc), ("normal", sc[sc.distribution == "normal"]),
                     ("gamma", sc[sc.distribution == "gamma"])):
        W[lab] = {"ari_km_vs_hc": bn._wil(sub.ari_km, sub.ari_hc),
                  "ari0_km_vs_hc": bn._wil(sub.ari0_km, sub.ari0_hc),
                  "excess_km_vs_hc": bn._wil(sub.ex_km, sub.ex_hc),
                  "excess_km_vs_0": bn._wil(sub.ex_km), "excess_hc_vs_0": bn._wil(sub.ex_hc)}
    out["wilcoxon_144_scenario_means"] = W
    json.dump(out, open(SUMM_OUT, "w"), indent=2, default=float)
    print("[ari] wrote", SUMM_OUT, flush=True)


def table(args):
    """Supplementary table from ari_summary.json -> manuscript/tables/tabS_ari.tex."""
    A = json.load(open(SUMM_OUT))
    W = A["wilcoxon_144_scenario_means"]
    f3 = lambda x: (f"{x:.3f}" if round(x, 3) != 0 else "0.000").replace("-", "$-$")
    def pv(p):
        if p >= 0.001:
            return f"{p:.3f}"
        m, e = f"{p:.1e}".split("e")
        return f"${m}\\times10^{{{int(e)}}}$"
    L = [r"\begin{tabular}{lrrrrrrr}", r"\toprule",
         r" & \multicolumn{3}{c}{$k$-means} & \multicolumn{4}{c}{Ward} \\",
         r"\cmidrule(lr){2-4}\cmidrule(lr){5-8}",
         r"Stratum & ARI & ARI$_0$ & Excess & ARI & ARI$_0$ & Excess & Ceiling \\", r"\midrule"]
    def row(lab, v):
        return (f"{lab} & {f3(v['ari_km'])} & {f3(v['ari0_km'])} & {f3(v['ex_km'])} & "
                f"{f3(v['ari_hc'])} & {f3(v['ari0_hc'])} & {f3(v['ex_hc'])} & {f3(v['ceiling_hc'])} \\\\")
    L.append(row("All scenarios", A["overall"]))
    L.append(r"\addlinespace")
    for g, lab in (("normal", "Normal"), ("gamma", "Gamma")):
        L.append(row(lab, A["by_distribution"][g]))
    L.append(r"\addlinespace")
    for g in ("0.1", "2.0", "6.0", "10.0"):
        L.append(row(f"$\\sigma = {float(g):g}$", A["by_sep"][g]))
    L += [r"\bottomrule", r"\end{tabular}"]
    out = os.path.join(os.path.dirname(RESULTS_DIR), "manuscript", "tables", "tabS_ari.tex")
    open(out, "w").write("\n".join(L) + "\n")
    print("[ari] wrote", out, "| excess km vs hc p:",
          {k: pv(v["excess_km_vs_hc"]["p"]) for k, v in W.items()}, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["run", "summarize", "table"])
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    {"run": run, "summarize": summarize, "table": table}[a.stage](a)


if __name__ == "__main__":
    main()
