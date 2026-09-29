"""Bootstrap null for count agreement, bootstrap floor for geometric fidelity,
scale-free dispersion metrics, collapse cells and fixed-range main numbers.

Stages (run from the repository root; PYTHONPATH=src or an installed package):

    python -m synthclust.bootstrap_null boot     --B 30 --workers 16
    python -m synthclust.bootstrap_null relative --draws 1000 --workers 16
    python -m synthclust.bootstrap_null summarize --reviewer-floor <floor.parquet>
    python -m synthclust.bootstrap_null tables

boot      For each of the 720 original datasets (144 scenarios x 5 replicates)
          draw B nonparametric bootstrap resamples (N rows with replacement).
          Resample b of unit (scenario index s, replicate r) uses
              numpy.random.default_rng([BASE_SEED, s, r, b]).integers(0, N, N)
          with BASE_SEED = 20260929 and s the position of the scenario in the
          canonical grid order p x k x rho x sep x distribution (the same order
          as recompute_metrics.main). The SAME resample is used for both
          algorithms. The StandardScaler is fitted on the ORIGINAL replicate and
          applied unchanged; because the transform is row-wise this equals
          resampling the rows of the scaled original. For every resample and
          algorithm: the silhouette scan of recompute_metrics.sil_scan (k-hat
          under the full 2..8 and capped 2..min(k+3,8) ranges) and the fixed-k
          fidelity metrics of recompute_metrics.compare (MCD, MVD, dG), plus
          RVD, MVD/p and MCD in within-component SD units.
          Output: results/bootstrap_null.parquet, one row per
          dataset x resample x algorithm (720 x B x 2 rows).

relative  Recompute the fixed-k partitions for the synthetic draws (all m draws
          by default) to obtain RVD = mean_j |v_S/v_R - 1| (needs v_R and v_S
          separately, which the stored table does not carry), MVD/p and MCD in
          SD units. MCD, MVD and dG are recomputed on the same code path and
          checked against the stored khat_fidelity_full.parquet.
          Output: results/relative_metrics.parquet, one row per pair.

summarize Items 1-5 of the analysis. Writes results/fullrange_summary.json
          (item 5, all count numbers of the manuscript under the full range, and
          the capped range for cross-checking), results/bootstrap_summary.json
          (items 1-4).
tables    Renders both JSON files as markdown tables
          (results/bootstrap_results_tables.md).

Checkpointing: one shard per (scenario, replicate) unit under
results/.partial_bootstrap_null/ and results/.partial_relative_metrics/
(written atomically by checkpoint.ScenarioStore; git-ignored). A killed run
resumes; --restart discards the shards of that stage only.

Definitions
  within-component SD s_w: pooled within-PLANTED-group SD per coordinate in the
      scaled space of the original replicate,
      s_w = sqrt( sum_i ||x_i - mu_{g(i)}||^2 / (N p) ).
  MCD_sd = MCD / s_w;  MVD_pc = MVD / p;
  RVD = mean over aligned clusters of |v_S / v_R - 1|  (v = mean squared
      distance to the centroid, as in recompute_metrics.partition_stats).
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"

import argparse
import itertools
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from synthclust import recompute_metrics as rm
from synthclust.checkpoint import ScenarioStore
from synthclust.paths import RESULTS_DIR, FIDELITY_RESULTS

BASE_SEED = 20260929
ALGOS = rm.ALGOS
KEYS = ["p", "k", "rho", "sep", "distribution", "rep"]
SCEN = KEYS[:-1]
GRID_SCEN = list(itertools.product([2, 5, 10], [2, 3, 4], [0.0, 0.4],
                                   [0.1, 2, 6, 10], ["normal", "gamma"]))
BOOT_OUT = RESULTS_DIR / "bootstrap_null.parquet"
REL_OUT = RESULTS_DIR / "relative_metrics.parquet"


# ----------------------------------------------------------------------------
# shared helpers
# ----------------------------------------------------------------------------
def load_original(p, k, rho, sep, dist, rep):
    tag = rm.scenario_tag(p, k, rho, sep, dist)
    od = pd.read_parquet(os.path.join(rm.OD, f"OD_{tag}.parquet"))
    feats = [c for c in od.columns if c.startswith("X")]
    Rr = od[od["rep"] == rep]
    sc = StandardScaler().fit(Rr[feats].values)
    Xr = sc.transform(Rr[feats].values)
    g = Rr["group"].values
    ss = 0.0
    for lev in np.unique(g):
        pts = Xr[g == lev]
        ss += float(((pts - pts.mean(axis=0)) ** 2).sum())
    s_w = float(np.sqrt(ss / (Xr.shape[0] * Xr.shape[1])))
    return tag, feats, sc, Xr, s_w


def reference(Xr, k, a):
    """Original partition at the planted k, exactly as recompute_metrics.run_unit."""
    lr = rm.fit(Xr, k, a)
    cr, vr, sr = rm.partition_stats(Xr, lr, k)
    return (cr, vr, sr, float(silhouette_score(Xr, lr)))


def compare_ext(ref, Xs, k, algo, with_sil=True):
    """recompute_metrics.compare, extended with RVD.

    The MCD / MVD / dG / silhouette lines are identical to rm.compare (checked
    by --selftest); RVD is added from the same aligned v_R, v_S.
    """
    cr, vr, sr, silr = ref
    ls = rm.fit(Xs, k, algo)
    cs, vs, ss = rm.partition_stats(Xs, ls, k)
    cost = np.nan_to_num(np.linalg.norm(cr[:, None, :] - cs[None, :, :], axis=2), nan=1e9)
    ri, ci = linear_sum_assignment(cost)
    mcd = float(np.nanmean(cost[ri, ci]))
    mvd = float(np.nanmean(np.abs(vr[ri] - vs[ci])))
    dg = abs(rm.gini(sr) - rm.gini(ss))
    rvd = float(np.nanmean(np.abs(vs[ci] / vr[ri] - 1.0)))
    sils = float(silhouette_score(Xs, ls)) if with_sil else np.nan
    return mcd, mvd, dg, rvd, silr, sils


def unit_list(reps=rm.REPS):
    return [(s, *g, r) for s, g in enumerate(GRID_SCEN) for r in reps]


def utag(u):
    return rm.unit_tag(*u[1:])


def run_pool(fn, todo, workers, label):
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, u): u for u in todo}
        for i, f in enumerate(as_completed(futs), 1):
            f.result()
            if i % 24 == 0 or i == len(todo):
                el = time.time() - t0
                print(f"[{label}] {i}/{len(todo)} units  {el:.0f}s  "
                      f"eta={el / i * (len(todo) - i):.0f}s", flush=True)


# ----------------------------------------------------------------------------
# stage 1/2: bootstrap resamples
# ----------------------------------------------------------------------------
def boot_unit(u, B):
    s, p, k, rho, sep, dist, rep = u
    tag, feats, sc, Xr, s_w = load_original(p, k, rho, sep, dist, rep)
    N = Xr.shape[0]
    cap = min(k + 3, rm.KMAX)
    refs, kr = {}, {}
    for a in ALGOS:
        scan = rm.sil_scan(Xr, a)
        kr[a] = (rm.argmax_upto(scan, rm.KMAX), rm.argmax_upto(scan, cap))
        refs[a] = reference(Xr, k, a)
    rows = []
    for b in range(B):
        rng = np.random.default_rng([BASE_SEED, s, rep, b])
        idx = rng.integers(0, N, N)
        Xb = Xr[idx]
        n_unique = int(np.unique(idx).size)
        for a in ALGOS:
            scan = rm.sil_scan(Xb, a)
            mcd, mvd, dg, rvd, silr, sils = compare_ext(refs[a], Xb, k, a)
            rows.append(dict(p=p, k=k, rho=rho, sep=sep, distribution=dist, rep=rep,
                             scen_idx=s, b=b, algo=a, n_unique=n_unique,
                             khat_real_full=kr[a][0], khat_real_capped=kr[a][1],
                             khat_boot_full=rm.argmax_upto(scan, rm.KMAX),
                             khat_boot_capped=rm.argmax_upto(scan, cap),
                             mcd=mcd, mvd=mvd, dgini=dg, rvd=rvd,
                             mvd_pc=mvd / p, mcd_sd=mcd / s_w, s_w=s_w,
                             sil_real=silr, sil_boot=sils))
    return rows


def _boot_store(u, B):
    store = ScenarioStore(RESULTS_DIR, "bootstrap_null")
    store.save(utag(u), boot_unit(u, B))
    return utag(u)


class _BootJob:
    def __init__(self, B):
        self.B = B

    def __call__(self, u):
        return _boot_store(u, self.B)


def stage_boot(args):
    store = ScenarioStore(RESULTS_DIR, "bootstrap_null")
    if args.restart:
        store.discard()
        store = ScenarioStore(RESULTS_DIR, "bootstrap_null")
    store.clear_stale_temporaries()
    units = unit_list()
    if args.limit:
        units = units[:args.limit]
    todo = [u for u in units if not store.has(utag(u))]
    print(f"[boot] B={args.B}  units={len(units)}  todo={len(todo)}", flush=True)
    if todo:
        run_pool(_BootJob(args.B), todo, args.workers, "boot")
    if args.limit:
        return
    assert store.count() == len(units), "incomplete; rerun to resume"
    df = store.load_all().sort_values(["scen_idx", "rep", "b", "algo"]).reset_index(drop=True)
    assert len(df) == len(units) * args.B * len(ALGOS), df.shape
    df.to_parquet(BOOT_OUT, index=False)
    print("[boot] wrote", BOOT_OUT, df.shape, flush=True)


# ----------------------------------------------------------------------------
# stage 3: relative metrics on synthetic draws
# ----------------------------------------------------------------------------
def rel_unit(u, draws):
    s, p, k, rho, sep, dist, rep = u
    tag, feats, sc, Xr, s_w = load_original(p, k, rho, sep, dist, rep)
    refs = {a: reference(Xr, k, a) for a in ALGOS}
    rows = []
    for m in range(1, draws + 1):
        sp = os.path.join(rm.SD, f"SD_cart_{tag}_syn{m}.parquet")
        Sr = pd.read_parquet(sp, columns=feats + ["rep"])
        Sr = Sr[Sr["rep"] == rep]
        Xs = sc.transform(Sr[feats].values)
        rec = dict(p=p, k=k, rho=rho, sep=sep, distribution=dist, rep=rep, syn_idx=m, s_w=s_w)
        for a in ALGOS:
            mcd, mvd, dg, rvd, _, _ = compare_ext(refs[a], Xs, k, a, with_sil=False)
            rec.update({f"mcd_{a}": mcd, f"mvd_{a}": mvd, f"dgini_{a}": dg,
                        f"rvd_{a}": rvd, f"mvd_pc_{a}": mvd / p, f"mcd_sd_{a}": mcd / s_w})
        rows.append(rec)
    return rows


class _RelJob:
    def __init__(self, draws):
        self.draws = draws

    def __call__(self, u):
        store = ScenarioStore(RESULTS_DIR, "relative_metrics")
        store.save(utag(u), rel_unit(u, self.draws))
        return utag(u)


def stage_relative(args):
    store = ScenarioStore(RESULTS_DIR, "relative_metrics")
    if args.restart:
        store.discard()
        store = ScenarioStore(RESULTS_DIR, "relative_metrics")
    store.clear_stale_temporaries()
    units = unit_list()
    if args.limit:
        units = units[:args.limit]
    todo = [u for u in units if not store.has(utag(u))]
    print(f"[relative] draws={args.draws}  units={len(units)}  todo={len(todo)}", flush=True)
    if todo:
        run_pool(_RelJob(args.draws), todo, args.workers, "relative")
    if args.limit:
        return
    assert store.count() == len(units), "incomplete; rerun to resume"
    df = store.load_all().sort_values(KEYS + ["syn_idx"]).reset_index(drop=True)
    assert len(df) == len(units) * args.draws, df.shape
    df.to_parquet(REL_OUT, index=False)
    print("[relative] wrote", REL_OUT, df.shape, flush=True)


# ----------------------------------------------------------------------------
# self-test: extended compare == reference compare; k-hat_R == stored table
# ----------------------------------------------------------------------------
def selftest(args):
    d = pd.read_parquet(FIDELITY_RESULTS)
    for u in [unit_list()[i] for i in (0, 357, 719)]:
        s, p, k, rho, sep, dist, rep = u
        tag, feats, sc, Xr, s_w = load_original(p, k, rho, sep, dist, rep)
        Sr = pd.read_parquet(os.path.join(rm.SD, f"SD_cart_{tag}_syn1.parquet"))
        Xs = sc.transform(Sr[Sr.rep == rep][feats].values)
        row = d[(d.p == p) & (d.k == k) & (d.rho == rho) & (d.sep == sep)
                & (d.distribution == dist) & (d.rep == rep) & (d.syn_idx == 1)].iloc[0]
        for a in ALGOS:
            ref = reference(Xr, k, a)
            c0 = rm.compare(ref, Xs, k, a)
            c1 = compare_ext(ref, Xs, k, a)
            assert np.allclose([c0[0], c0[1], c0[2], c0[4]], [c1[0], c1[1], c1[2], c1[5]])
            assert np.allclose([c0[0], c0[1], c0[2]],
                               [row[f"mcd_{a}"], row[f"mvd_{a}"], row[f"dgini_{a}"]]), (u, a)
        print("selftest ok", utag(u), flush=True)


# ----------------------------------------------------------------------------
# summaries (items 1-5)
# ----------------------------------------------------------------------------
RANGES = ("full", "capped")
FACTOR_ORDER = ["sep", "k", "p", "rho", "distribution"]


def _lvl(v):
    if isinstance(v, (float, np.floating)) and float(v).is_integer():
        return str(int(v))
    return str(v)


def _wil(x, y=None):
    """Paired / one-sample Wilcoxon signed-rank (scipy default zero_method='wilcox')."""
    from scipy import stats
    x = np.asarray(x, float)
    dl = x if y is None else x - np.asarray(y, float)
    # scenario means built along different aggregation paths differ by ~1e-16;
    # round so that exact ties are ties and signed ranks do not depend on the path
    dl = np.round(dl, 12)
    out = dict(n=int(dl.size), n_pos=int((dl > 0).sum()), n_neg=int((dl < 0).sum()),
               n_zero=int((dl == 0).sum()), mean_diff=float(dl.mean()),
               median_diff=float(np.median(dl)))
    if out["n_pos"] + out["n_neg"] == 0:
        out.update(W=None, p=None)
    else:
        r = stats.wilcoxon(dl)
        out.update(W=float(r.statistic), p=float(r.pvalue))
    return out


def _by(ds, cols, by):
    """Means of `cols` by one factor, a tuple of factors, or overall (by=None)."""
    if by is None:
        return {c: float(ds[c].mean()) for c in cols}
    g = ds.groupby(list(by) if isinstance(by, tuple) else by)[cols].mean()
    out = {}
    for idx, row in g.iterrows():
        if isinstance(by, tuple):
            key = ",".join(f"{f}={_lvl(v)}" for f, v in zip(by, idx))
        else:
            key = f"{by}={_lvl(idx)}"
        out[key] = {c: float(row[c]) for c in cols}
    return out


def _eta2(ds, y, interactions):
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    X = ds[SCEN + [y]].copy()
    for f in SCEN:
        X[f] = X[f].astype(str)
    rhs = "C(p) + C(k) + C(rho) + C(sep) + C(distribution)"
    if interactions:
        rhs = f"({rhs})**2"
    m = smf.ols(f"{y} ~ {rhs}", data=X).fit()
    a = anova_lm(m, typ=2)
    ssr = float(a.loc["Residual", "sum_sq"])
    eta = {}
    for term, row in a.iterrows():
        if term == "Residual":
            continue
        name = term.replace("C(", "").replace(")", "")
        eta[name] = float(row["sum_sq"] / (row["sum_sq"] + ssr))
    return dict(partial_eta2=eta, R2=float(m.rsquared), R2_adj=float(m.rsquared_adj),
                df_resid=float(m.df_resid))


def count_block(d, r):
    """All count numbers of the manuscript for candidate range r."""
    df = d[KEYS].copy()
    for a in ALGOS:
        ks, kr = d[f"khat_syn_{a}_{r}"], d[f"khat_real_{a}_{r}"]
        df[f"rr_{a}"] = (ks == d["k"]).astype(float)
        df[f"ag_{a}"] = (ks == kr).astype(float)
        df[f"orig_{a}"] = (kr == d["k"]).astype(float)
    cols = [f"{m}_{a}" for m in ("rr", "ag") for a in ALGOS]
    ocols = [f"orig_{a}" for a in ALGOS]
    ds = df.groupby(KEYS).mean().reset_index()
    sc = df.groupby(SCEN).mean().reset_index()
    out = {"overall": _by(ds, cols, None)}
    out["by_factor"] = {f: _by(ds, cols, f) for f in FACTOR_ORDER}
    out["by_k_x_sep"] = _by(ds, cols, ("k", "sep"))
    out["by_distribution_x_sep"] = _by(ds, cols, ("distribution", "sep"))
    out["original_recovery"] = {
        "overall": _by(ds, ocols, None), "by_sep": _by(ds, ocols, "sep"),
        "by_distribution": _by(ds, ocols, "distribution"),
        "by_distribution_x_sep": _by(ds, ocols, ("distribution", "sep")),
        "by_k_x_sep": _by(ds, ocols, ("k", "sep"))}
    out["wilcoxon_km_vs_hc_144_scenarios"] = {
        "RR": _wil(sc["rr_km"], sc["rr_hc"]), "AG": _wil(sc["ag_km"], sc["ag_hc"])}
    out["same_outcome_share"] = {
        "RR": float((df["rr_km"] == df["rr_hc"]).mean()),
        "AG": float((df["ag_km"] == df["ag_hc"]).mean())}
    out["eta2_main_effects"] = {c: _eta2(ds, c, False) for c in cols}
    out["eta2_main_plus_2way"] = {c: _eta2(ds, c, True) for c in cols}
    out["by_rho_and_p_at_sep6"] = {f: _by(ds[ds.sep == 6], cols, f) for f in ("rho", "p")}
    out["by_rho_and_p_at_sep_le2"] = {f: _by(ds[ds.sep <= 2], cols, f) for f in ("rho", "p")}
    # S4 reference: pairs of independent original datasets of a scenario with equal k-hat_R
    first = d.groupby(KEYS).first().reset_index()
    pr = []
    for key, g in first.groupby(SCEN):
        rec = dict(zip(SCEN, key))
        for a in ALGOS:
            v = g[f"khat_real_{a}_{r}"].values
            eq = [v[i] == v[j] for i in range(len(v)) for j in range(i + 1, len(v))]
            rec[f"pair_{a}"] = float(np.mean(eq))
        pr.append(rec)
    pr = pd.DataFrame(pr)
    out["independent_original_pairs_same_khat"] = {
        "overall": _by(pr, ["pair_km", "pair_hc"], None),
        "by_sep": _by(pr, ["pair_km", "pair_hc"], "sep")}
    return out, ds, sc


def summarize(args):
    d = pd.read_parquet(FIDELITY_RESULTS)
    assert len(d) == 720_000, d.shape
    full = {"_description": (
        "Item 5: count numbers regenerated from results/khat_fidelity_full.parquet. "
        "'full' = candidate range 2..8 (primary); 'capped' = 2..min(k+3,8) (as in v4, "
        "for cross-checking). rr_* = share k-hat_S == planted k; ag_* = share "
        "k-hat_S == k-hat_R; orig_* = share of original datasets with k-hat_R == k. "
        "Marginal means are over the 720 dataset-level proportions (equivalently over "
        "evaluations: every dataset has 1000 draws). Wilcoxon: scipy.stats.wilcoxon "
        "on the 144 scenario-level means, zero_method='wilcox' (ties dropped); W is "
        "the smaller signed-rank sum; n_pos = scenarios with k-means > Ward. "
        "partial eta^2 = SS_term/(SS_term+SS_resid), type-II SS (balanced design) "
        "from OLS on the 720 dataset-level proportions, factors categorical.")}
    ds_r = {}
    for r in RANGES:
        full[r], ds_r[r], _ = count_block(d, r)
    (RESULTS_DIR / "fullrange_summary.json").write_text(json.dumps(full, indent=1))
    print("[summarize] wrote fullrange_summary.json", flush=True)

    # ---------------- item 1: bootstrap null for count agreement --------------
    bo = pd.read_parquet(BOOT_OUT)
    first = d.groupby(KEYS).first().reset_index()
    chk = bo.merge(first[KEYS + [f"khat_real_{a}_{r}" for a in ALGOS for r in RANGES]],
                   on=KEYS)
    mism = {f"{a}_{r}": int((chk[chk.algo == a][f"khat_real_{r}"]
                             != chk[chk.algo == a][f"khat_real_{a}_{r}"]).sum() // args.B)
            for a in ALGOS for r in RANGES}
    S = {"B": int(bo.b.nunique()), "base_seed": BASE_SEED,
         "khat_R_recomputed_vs_stored_mismatching_datasets": mism}
    item1 = {}
    for r in RANGES:
        rows = []
        for a in ALGOS:
            ba = chk[chk.algo == a]
            t = ba.assign(ag0=(ba[f"khat_boot_{r}"] == ba[f"khat_real_{a}_{r}"]).astype(float),
                          rr0=(ba[f"khat_boot_{r}"] == ba["k"]).astype(float))
            t = t.groupby(KEYS)[["ag0", "rr0"]].mean().rename(
                columns={"ag0": f"ag0_{a}", "rr0": f"rr0_{a}"})
            rows.append(t)
        b1 = ds_r[r].set_index(KEYS)[[f"ag_{a}" for a in ALGOS] + [f"rr_{a}" for a in ALGOS]]
        b1 = b1.join(rows[0]).join(rows[1]).reset_index()
        for a in ALGOS:
            b1[f"ex_{a}"] = b1[f"ag_{a}"] - b1[f"ag0_{a}"]
        b1["ex_diff"] = b1["ex_km"] - b1["ex_hc"]
        cols = ["ag_km", "ag0_km", "ex_km", "ag_hc", "ag0_hc", "ex_hc", "ex_diff",
                "rr0_km", "rr0_hc"]
        blk = {"overall": _by(b1, cols, None)}
        for f in ("sep", "distribution", ("sep", "distribution"), "k", "p", "rho"):
            blk["by_" + ("_x_".join(f) if isinstance(f, tuple) else f)] = _by(b1, cols, f)
        sc = b1.groupby(SCEN)[cols].mean().reset_index()
        tests = {}
        subsets = {"all": sc, "normal": sc[sc.distribution == "normal"],
                   "gamma": sc[sc.distribution == "gamma"]}
        for s_ in (0.1, 2, 6, 10):
            for dist in ("normal", "gamma"):
                subsets[f"sep={_lvl(s_)},{dist}"] = sc[(sc.sep == s_) & (sc.distribution == dist)]
            subsets[f"sep={_lvl(s_)}"] = sc[sc.sep == s_]
        for name, sub in subsets.items():
            tests[name] = {"excess_km_vs_excess_hc": _wil(sub.ex_km, sub.ex_hc),
                           "AG_km_vs_AG_hc": _wil(sub.ag_km, sub.ag_hc),
                           "AG0_km_vs_AG0_hc": _wil(sub.ag0_km, sub.ag0_hc),
                           "excess_km_vs_0": _wil(sub.ex_km),
                           "excess_hc_vs_0": _wil(sub.ex_hc)}
        blk["wilcoxon_144_scenario_means"] = tests
        item1[r] = blk
    S["item1_count_null"] = item1

    # ---------------- item 2: geometric floor ----------------
    mets = ["mcd", "mvd", "dgini"]
    obs = d.groupby(KEYS)[[f"{m}_{a}" for m in mets for a in ALGOS]].mean()
    fl = bo.pivot_table(index=KEYS, columns="algo", values=mets + ["rvd", "mvd_pc", "mcd_sd"],
                        aggfunc="mean")
    fl.columns = [f"floor_{m}_{a}" for m, a in fl.columns]
    g2 = obs.join(fl).reset_index()
    for m in mets:
        for a in ALGOS:
            g2[f"ex_{m}_{a}"] = g2[f"{m}_{a}"] - g2[f"floor_{m}_{a}"]
    cols2 = [f"{pre}{m}_{a}" for m in mets for a in ALGOS for pre in ("floor_", "", "ex_")]
    item2 = {"overall": _by(g2, cols2, None), "by_sep": _by(g2, cols2, "sep"),
             "by_distribution": _by(g2, cols2, "distribution"),
             "by_p": _by(g2, cols2, "p")}
    sc2 = g2.groupby(SCEN)[cols2].mean().reset_index()
    t2 = {}
    for m in mets:
        t2[m] = {f"excess_{a}_vs_0": _wil(sc2[f"ex_{m}_{a}"]) for a in ALGOS}
        t2[m]["excess_km_vs_excess_hc"] = _wil(sc2[f"ex_{m}_km"], sc2[f"ex_{m}_hc"])
        t2[m]["observed_km_vs_observed_hc"] = _wil(sc2[f"{m}_km"], sc2[f"{m}_hc"])
        t2[m]["floor_km_vs_floor_hc"] = _wil(sc2[f"floor_{m}_km"], sc2[f"floor_{m}_hc"])
    item2["wilcoxon_144_scenario_means"] = t2
    item2["ratio_observed_to_floor_overall"] = {
        f"{m}_{a}": float(g2[f"{m}_{a}"].mean() / g2[f"floor_{m}_{a}"].mean())
        for m in mets for a in ALGOS}
    if args.reviewer_floor and os.path.exists(args.reviewer_floor):
        rv = pd.read_parquet(args.reviewer_floor)
        mm = g2.merge(rv, on=KEYS)
        cmp_ = {}
        for m, rmn in (("mcd", "bmcd"), ("mvd", "bmvd"), ("dgini", "bdg")):
            for a in ALGOS:
                x, y = mm[f"floor_{m}_{a}"], mm[f"{rmn}_{a}"]
                cmp_[f"{m}_{a}"] = dict(ours=float(x.mean()), reviewer=float(y.mean()),
                                        ratio_ours_to_reviewer=float(x.mean() / y.mean()),
                                        pearson_r_720=float(np.corrcoef(x, y)[0, 1]),
                                        mean_abs_diff=float(np.abs(x - y).mean()))
                cmp_[f"{m}_{a}"]["by_sep"] = {
                    _lvl(s_): [float(x[mm.sep == s_].mean()), float(y[mm.sep == s_].mean())]
                    for s_ in (0.1, 2, 6, 10)}
        item2["reviewer_floor_comparison"] = cmp_
    S["item2_geometric_floor"] = item2

    # ---------------- item 3: scale-free metrics ----------------
    rel = pd.read_parquet(REL_OUT)
    ver = {}
    rs = rel.merge(d[KEYS + ["syn_idx"] + [f"{m}_{a}" for m in mets for a in ALGOS]],
                   on=KEYS + ["syn_idx"], suffixes=("", "_stored"))
    for m in mets:
        for a in ALGOS:
            ver[f"{m}_{a}_max_abs_diff"] = float(np.abs(rs[f"{m}_{a}"] - rs[f"{m}_{a}_stored"]).max())
    rmets = ["rvd", "mvd_pc", "mcd_sd"]
    obs3 = rel.groupby(KEYS)[[f"{m}_{a}" for m in rmets for a in ALGOS]].mean()
    g3 = obs3.join(fl[[f"floor_{m}_{a}" for m in rmets for a in ALGOS]]).reset_index()
    for m in rmets:
        for a in ALGOS:
            g3[f"ex_{m}_{a}"] = g3[f"{m}_{a}"] - g3[f"floor_{m}_{a}"]
    cols3 = [f"{pre}{m}_{a}" for m in rmets for a in ALGOS for pre in ("floor_", "", "ex_")]
    item3 = {"n_pairs": int(len(rel)), "draws_per_dataset": int(rel.syn_idx.nunique()),
             "verification_vs_stored": ver,
             "overall": _by(g3, cols3, None), "by_sep": _by(g3, cols3, "sep"),
             "by_distribution": _by(g3, cols3, "distribution"), "by_p": _by(g3, cols3, "p"),
             "by_k": _by(g3, cols3, "k")}
    sc3 = g3.groupby(SCEN)[cols3].mean().reset_index()
    t3 = {}
    for m in rmets:
        t3[m] = {f"excess_{a}_vs_0": _wil(sc3[f"ex_{m}_{a}"]) for a in ALGOS}
        t3[m]["excess_km_vs_excess_hc"] = _wil(sc3[f"ex_{m}_km"], sc3[f"ex_{m}_hc"])
        t3[m]["observed_km_vs_observed_hc"] = _wil(sc3[f"{m}_km"], sc3[f"{m}_hc"])
    item3["wilcoxon_144_scenario_means"] = t3
    S["item3_scale_free"] = item3

    # ---------------- item 4: collapse cells ----------------
    item4 = {"definitions": {
        "khatR2_dataset": "original dataset with k-hat_R = 2",
        "collapse_scenario": ("scenario in which >= 90% of its 5 original datasets have "
                              "k-hat_R = 2 (with n = 5 this means all 5)"),
        "collapse_dataset_strict": ("original dataset with k-hat_R = 2 AND k-hat_S = 2 in "
                                    ">= 90% of its 1000 synthetic draws"),
        "_k>=3": "same, restricted to planted k >= 3, where k-hat = 2 is an under-estimate"}}
    for r in RANGES:
        blk = {}
        for a in ALGOS:
            t = d[KEYS].copy()
            t["r2"] = d[f"khat_real_{a}_{r}"] == 2
            t["s2"] = d[f"khat_syn_{a}_{r}"] == 2
            t["ag"] = d[f"khat_syn_{a}_{r}"] == d[f"khat_real_{a}_{r}"]
            dd = t.groupby(KEYS).agg(r2=("r2", "first"), s2=("s2", "mean"),
                                     ag=("ag", "mean")).reset_index()
            dd["strict"] = dd.r2 & (dd.s2 >= 0.9)
            scn = dd.groupby(SCEN).agg(r2=("r2", "mean"), ag=("ag", "mean")).reset_index()
            scn["cell"] = scn.r2 >= 0.9
            dd = dd.merge(scn[SCEN + ["cell"]], on=SCEN)
            res = {}
            for lab, sub_d, sub_s in (("all_k", dd, scn), ("k>=3", dd[dd.k >= 3], scn[scn.k >= 3])):
                res[lab] = {
                    "share_datasets_khatR2": float(sub_d.r2.mean()),
                    "share_scenarios_collapse_cell": float(sub_s.cell.mean()),
                    "n_scenarios_collapse_cell": int(sub_s.cell.sum()),
                    "share_datasets_strict": float(sub_d.strict.mean()),
                    "share_of_720000_evals_in_collapse_cells": float(sub_d.cell.sum() / 720),
                    "share_of_720000_evals_in_strict_datasets": float(sub_d.strict.sum() / 720),
                    "AG_inside_collapse_cells": float(sub_d[sub_d.cell].ag.mean()) if sub_d.cell.any() else None,
                    "AG_outside_collapse_cells": float(sub_d[~sub_d.cell].ag.mean()),
                    "by_sep": {_lvl(s_): {"khatR2": float(sub_d[sub_d.sep == s_].r2.mean()),
                                          "cell": float(sub_s[sub_s.sep == s_].cell.mean()),
                                          "strict": float(sub_d[sub_d.sep == s_].strict.mean())}
                               for s_ in (0.1, 2, 6, 10)},
                    "by_p": {_lvl(p_): {"khatR2": float(sub_d[sub_d.p == p_].r2.mean()),
                                        "cell": float(sub_s[sub_s.p == p_].cell.mean()),
                                        "strict": float(sub_d[sub_d.p == p_].strict.mean())}
                             for p_ in (2, 5, 10)},
                    "by_sep_x_p": {f"sep={_lvl(s_)},p={p_}": {
                        "khatR2": float(sub_d[(sub_d.sep == s_) & (sub_d.p == p_)].r2.mean()),
                        "cell": float(sub_s[(sub_s.sep == s_) & (sub_s.p == p_)].cell.mean())}
                        for s_ in (0.1, 2, 6, 10) for p_ in (2, 5, 10)},
                    "p10_sep_le2_khatR2": float(sub_d[(sub_d.p == 10) & (sub_d.sep <= 2)].r2.mean()),
                }
            blk[a] = res
        item4[r] = blk
    S["item4_collapse"] = item4
    (RESULTS_DIR / "bootstrap_summary.json").write_text(json.dumps(S, indent=1))
    print("[summarize] wrote bootstrap_summary.json", flush=True)


# ----------------------------------------------------------------------------
# markdown tables (numbers copied from the two JSON files, never typed)
# ----------------------------------------------------------------------------
def _f(x, nd=3):
    if x is None:
        return "--"
    if isinstance(x, str):
        return x
    if isinstance(x, (int, np.integer)):
        return str(x)
    if abs(x) != 0 and abs(x) < 1e-3:
        return f"{x:.1e}"
    return f"{x:.{nd}f}"


def _tab(header, rows):
    s = "| " + " | ".join(header) + " |\n|" + "|".join(["---"] * len(header)) + "|\n"
    for r in rows:
        s += "| " + " | ".join(r) + " |\n"
    return s + "\n"


def _pv(p):
    return "--" if p is None else (f"{p:.2e}" if p < 1e-3 else f"{p:.3f}")


def _wrow(name, w):
    return [name, str(w["n"]), str(w["n_pos"]), str(w["n_neg"]), str(w["n_zero"]),
            _f(w["mean_diff"], 4), _f(w["W"], 1) if w["W"] is not None else "--", _pv(w["p"])]


WH = ["comparison", "n", "n(+)", "n(-)", "ties", "mean diff", "W", "p"]


def tables_md():
    F = json.loads((RESULTS_DIR / "fullrange_summary.json").read_text())
    S = json.loads((RESULTS_DIR / "bootstrap_summary.json").read_text())
    out = {}
    # ---- item 1
    s = ""
    for r in RANGES:
        I = S["item1_count_null"][r]
        s += f"#### Item 1, {r} range ({'primary' if r == 'full' else 'secondary'})\n\n"
        cols = ["ag_km", "ag0_km", "ex_km", "ag_hc", "ag0_hc", "ex_hc", "ex_diff"]
        hdr = ["stratum", "AG km", "AG0 km", "excess km", "AG Ward", "AG0 Ward",
               "excess Ward", "excess km - Ward"]
        rows = [["overall"] + [_f(I["overall"][c]) for c in cols]]
        keys = ["by_sep", "by_distribution", "by_sep_x_distribution", "by_k", "by_p", "by_rho"]
        if r == "capped":
            keys = ["by_sep", "by_distribution", "by_sep_x_distribution"]
        for kk in keys:
            for lev, v in I[kk].items():
                rows.append([lev] + [_f(v[c]) for c in cols])
        s += _tab(hdr, rows)
        T = I["wilcoxon_144_scenario_means"]
        names = list(T) if r == "full" else ["all", "normal", "gamma"]
        wr = []
        for nm in names:
            for tn in ("AG_km_vs_AG_hc", "excess_km_vs_excess_hc", "AG0_km_vs_AG0_hc",
                       "excess_km_vs_0", "excess_hc_vs_0"):
                if r == "full" and nm not in ("all", "normal", "gamma") and tn.endswith("vs_0"):
                    continue
                wr.append(_wrow(f"{nm}: {tn}", T[nm][tn]))
        s += "Paired / one-sample Wilcoxon signed-rank on scenario means " \
             "(n(+) = scenarios where the first term is larger):\n\n" + _tab(WH, wr)
    out["item1"] = s
    # ---- item 2
    I = S["item2_geometric_floor"]
    s = ""
    hdr = ["stratum", "metric", "floor km", "obs km", "excess km", "floor Ward", "obs Ward",
           "excess Ward"]
    rows = []
    for m in ("mcd", "mvd", "dgini"):
        def rr(lab, v):
            return [lab, m] + [_f(v[f"{pre}{m}_{a}"]) for a in ALGOS
                               for pre in ("floor_", "", "ex_")]
        rows.append(rr("overall", I["overall"]))
        for kk in ("by_sep", "by_distribution", "by_p"):
            for lev, v in I[kk].items():
                rows.append(rr(lev, v))
    s += _tab(hdr, rows)
    s += "Ratio observed / floor (overall means): " + ", ".join(
        f"{k_} {v:.2f}" for k_, v in I["ratio_observed_to_floor_overall"].items()) + "\n\n"
    wr = []
    for m, T in I["wilcoxon_144_scenario_means"].items():
        for tn, w in T.items():
            wr.append(_wrow(f"{m}: {tn}", w))
    s += _tab(WH, wr)
    if "reviewer_floor_comparison" in I:
        rows = []
        for k_, v in I["reviewer_floor_comparison"].items():
            rows.append([k_, _f(v["ours"]), _f(v["reviewer"]), _f(v["ratio_ours_to_reviewer"]),
                         _f(v["pearson_r_720"]), _f(v["mean_abs_diff"])] +
                        [f"{_f(a_)} / {_f(b_)}" for a_, b_ in v["by_sep"].values()])
        s += "Comparison with the reviewer's provisional floor (720 datasets):\n\n" + _tab(
            ["metric", "ours", "reviewer", "ratio", "Pearson r", "mean |diff|",
             "sep 0.1 ours/rev", "sep 2", "sep 6", "sep 10"], rows)
    out["item2"] = s
    # ---- item 3
    I = S["item3_scale_free"]
    s = (f"Pairs used: {I['n_pairs']} ({I['draws_per_dataset']} draws per original dataset). "
         "Recomputed vs stored, max |diff|: " + ", ".join(
             f"{k_} {v:.1e}" for k_, v in I["verification_vs_stored"].items()) + "\n\n")
    rows = []
    for m in ("rvd", "mvd_pc", "mcd_sd"):
        def rr(lab, v):
            return [lab, m] + [_f(v[f"{pre}{m}_{a}"]) for a in ALGOS
                               for pre in ("floor_", "", "ex_")]
        rows.append(rr("overall", I["overall"]))
        for kk in ("by_sep", "by_distribution", "by_p", "by_k"):
            for lev, v in I[kk].items():
                rows.append(rr(lev, v))
    s += _tab(hdr, rows)
    wr = []
    for m, T in I["wilcoxon_144_scenario_means"].items():
        for tn, w in T.items():
            wr.append(_wrow(f"{m}: {tn}", w))
    s += _tab(WH, wr)
    out["item3"] = s
    # ---- item 4
    I = S["item4_collapse"]
    s = "Definitions: " + "; ".join(f"**{k_}**: {v}" for k_, v in I["definitions"].items()) + "\n\n"
    rows = []
    for r in RANGES:
        for a in ALGOS:
            for lab in ("all_k", "k>=3"):
                v = I[r][a][lab]
                rows.append([r, a, lab, _f(v["share_datasets_khatR2"]),
                             f"{_f(v['share_scenarios_collapse_cell'])} ({v['n_scenarios_collapse_cell']})",
                             _f(v["share_datasets_strict"]),
                             _f(v["share_of_720000_evals_in_collapse_cells"]),
                             _f(v["share_of_720000_evals_in_strict_datasets"]),
                             _f(v["AG_inside_collapse_cells"]), _f(v["AG_outside_collapse_cells"]),
                             _f(v["p10_sep_le2_khatR2"])])
    s += ("Shares in columns 4-6 are of the subset's datasets / scenarios (720/144 for all_k, "
          "480/96 for k>=3); columns 7-8 are shares of ALL 720,000 evaluations.\n\n")
    s += _tab(["range", "algo", "subset", "datasets k-hat_R=2", "collapse scenarios (n)",
               "strict datasets", "evals in collapse cells", "evals in strict datasets",
               "AG inside cells", "AG outside cells", "k-hat_R=2 at p=10, sep<=2"], rows)
    rows = []
    for r in RANGES:
        for a in ALGOS:
            v = I[r][a]["all_k"]["by_sep_x_p"]
            rows.append([r, a] + [f"{_f(x['khatR2'], 2)} / {_f(x['cell'], 2)}" for x in v.values()])
    s += ("Share of datasets with k-hat_R = 2 / share of scenarios that are collapse cells, "
          "by sep x p (all k):\n\n" + _tab(["range", "algo"] + list(
              I["full"]["km"]["all_k"]["by_sep_x_p"].keys()), rows))
    out["item4"] = s
    # ---- item 5
    s = ""
    for r in RANGES:
        B5 = F[r]
        s += f"#### Item 5, {r} range\n\n"
        cols = ["rr_km", "rr_hc", "ag_km", "ag_hc"]
        rows = []
        for f in FACTOR_ORDER:
            for lev, v in B5["by_factor"][f].items():
                rows.append([lev] + [_f(v[c]) for c in cols])
        rows.append(["overall"] + [_f(B5["overall"][c]) for c in cols])
        s += "Table 2 analogue:\n\n" + _tab(["level", "RR km", "RR Ward", "AG km", "AG Ward"], rows)
        if r == "capped":
            continue
        for kk, lab in (("by_k_x_sep", "k x sep (Fig. 3)"),
                        ("by_distribution_x_sep", "distribution x sep (Fig. 6)")):
            rows = [[lev] + [_f(v[c]) for c in cols] for lev, v in B5[kk].items()]
            s += f"{lab}:\n\n" + _tab(["cell", "RR km", "RR Ward", "AG km", "AG Ward"], rows)
        O = B5["original_recovery"]
        rows = [["overall", _f(O["overall"]["orig_km"]), _f(O["overall"]["orig_hc"])]]
        for kk in ("by_sep", "by_distribution", "by_distribution_x_sep"):
            rows += [[lev, _f(v["orig_km"]), _f(v["orig_hc"])] for lev, v in O[kk].items()]
        s += "Original-data recovery, share k-hat_R == k:\n\n" + _tab(["stratum", "km", "Ward"], rows)
        W = B5["wilcoxon_km_vs_hc_144_scenarios"]
        s += _tab(WH, [_wrow("RR km vs Ward", W["RR"]), _wrow("AG km vs Ward", W["AG"])])
        s += (f"Same outcome (both algorithms succeed or both fail): RR "
              f"{B5['same_outcome_share']['RR']:.4f}, AG {B5['same_outcome_share']['AG']:.4f}.\n\n")
        P = B5["independent_original_pairs_same_khat"]
        s += (f"Independent original pairs with equal k-hat_R: km {P['overall']['pair_km']:.3f}, "
              f"Ward {P['overall']['pair_hc']:.3f}; by sep " + "; ".join(
                  f"{lev}: {v['pair_km']:.3f}/{v['pair_hc']:.3f}" for lev, v in P["by_sep"].items())
              + ".\n\n")
        for kk, lab in (("eta2_main_effects", "main effects"),
                        ("eta2_main_plus_2way", "main effects + all two-way interactions")):
            E = B5[kk]
            terms = list(E["rr_km"]["partial_eta2"].keys())
            rows = [[t] + [_f(E[c]["partial_eta2"][t]) for c in cols] for t in terms]
            rows.append(["R^2"] + [_f(E[c]["R2"]) for c in cols])
            s += f"Partial eta^2, {lab} (720 dataset-level proportions):\n\n" + _tab(
                ["term", "RR km", "RR Ward", "AG km", "AG Ward"], rows)
        for kk, lab in (("by_rho_and_p_at_sep6", "sep = 6"), ("by_rho_and_p_at_sep_le2", "sep <= 2")):
            rows = []
            for f in ("rho", "p"):
                rows += [[lev] + [_f(v[c]) for c in cols] for lev, v in B5[kk][f].items()]
            s += f"By rho and p at {lab}:\n\n" + _tab(["level", "RR km", "RR Ward", "AG km", "AG Ward"], rows)
    out["item5"] = s
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["boot", "relative", "summarize", "tables", "selftest"])
    ap.add_argument("--B", type=int, default=30, help="bootstrap resamples per dataset")
    ap.add_argument("--draws", type=int, default=1000,
                    help="synthetic draws per original dataset for RVD (relative stage)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0, help="first N units only (testing)")
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--reviewer-floor", default="",
                    help="optional parquet of a provisional floor (bmcd_*, bmvd_*, bdg_*) "
                         "to compare against (summarize stage)")
    args = ap.parse_args()
    if args.stage == "boot":
        stage_boot(args)
    elif args.stage == "relative":
        stage_relative(args)
    elif args.stage == "selftest":
        selftest(args)
    elif args.stage == "tables":
        T = tables_md()
        txt = "".join(f"### {k_}\n\n{v}" for k_, v in T.items())
        (RESULTS_DIR / "bootstrap_results_tables.md").write_text(txt)
        print("[tables] wrote bootstrap_results_tables.md", flush=True)
    else:
        summarize(args)


if __name__ == "__main__":
    main()
