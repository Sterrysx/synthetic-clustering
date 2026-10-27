"""Independent number check of the v5 manuscript (Phase 3).

Recomputes, from the stored per-row results only
    results/khat_fidelity_full.parquet   (720,000 original-synthetic pairs)
    results/bootstrap_null.parquet       (720 datasets x B=30 x 2 algorithms)
    results/relative_metrics.parquet     (scale-free metrics, 720,000 pairs)
    results/khat_fidelity_full_m100.parquet, results/scaling_timings.json
every number reported in the abstract, Sections 3-5 and the tables of
main.tex, and in the tables and table-related prose of supplementary.tex, and
compares it with the value printed in the manuscript.  It does not import
src/synthclust/v5_tables.py or read the summary JSON files, so it is
independent of the code that wrote the tables.

Run from anywhere:  python manuscript/joc_prep/verify_numbers.py
Writes manuscript/joc_prep/VERIFICATION.md and prints a one-line summary.
"""
import itertools, json, pathlib, re
import numpy as np, pandas as pd
from scipy import stats

J = pathlib.Path(__file__).resolve().parent
M = J.parent
R = M.parent / "results"
F = ["p", "k", "rho", "sep", "distribution"]
SEPS = [0.1, 2.0, 6.0, 10.0]

# ---------------------------------------------------------------- data
kf = pd.read_parquet(R / "khat_fidelity_full.parquet")
bn = pd.read_parquet(R / "bootstrap_null.parquet")
rm = pd.read_parquet(R / "relative_metrics.parquet")
assert len(kf) == 720_000 and len(rm) == 720_000 and len(bn) == 720 * 30 * 2

d = kf.copy()
for a in ["km", "hc"]:
    for r in ["full", "capped"]:
        d[f"rr_{a}_{r}"] = (d[f"khat_syn_{a}_{r}"] == d.k).astype(float)
        d[f"ag_{a}_{r}"] = (d[f"khat_syn_{a}_{r}"] == d[f"khat_real_{a}_{r}"]).astype(float)
        d[f"or_{a}_{r}"] = (d[f"khat_real_{a}_{r}"] == d.k).astype(float)
cnt = [c for c in d.columns if c[:3] in ("rr_", "ag_", "or_")]
S = d.groupby(F)[cnt + [f"{m}_{a}" for m in ("mcd", "mvd", "dgini", "sil_real", "sil_syn")
                         for a in ("km", "hc")]].mean().reset_index()
repl = d.groupby(F + ["rep"])[cnt].mean().reset_index()
kr = d.groupby(F + ["rep"])[[f"khat_real_{a}_{r}" for a in ("km", "hc")
                             for r in ("full", "capped")]].first().reset_index()

b = bn.copy()
for r in ["full", "capped"]:
    b[f"ag0_{r}"] = (b[f"khat_boot_{r}"] == b[f"khat_real_{r}"]).astype(float)
MET = ["mcd", "mvd", "dgini", "rvd", "mvd_pc", "mcd_sd"]
bd = b.groupby(F + ["rep", "algo"])[["ag0_full", "ag0_capped"] + MET + ["khat_real_full"]].mean().reset_index()
# bootstrap file's k-hat of the original must equal the fidelity file's
chk = bd.pivot_table(index=F + ["rep"], columns="algo", values="khat_real_full").reset_index().merge(kr, on=F + ["rep"])
assert (chk.km == chk.khat_real_km_full).all() and (chk.hc == chk.khat_real_hc_full).all()
bs = bd.groupby(F + ["algo"])[["ag0_full", "ag0_capped"] + MET].mean().reset_index()
bw = bs.pivot_table(index=F, columns="algo").reset_index()
bw.columns = [c[0] if c[1] == "" else f"fl_{c[0]}_{c[1]}" for c in bw.columns]
rms = rm.groupby(F)[[f"{m}_{a}" for m in MET for a in ("km", "hc")]].mean().reset_index()
rms.columns = [c if c in F else "o_" + c for c in rms.columns]
S = S.merge(bw, on=F).merge(rms, on=F)
assert len(S) == 144
for a in ("km", "hc"):
    assert np.allclose(S[f"mcd_{a}"], S[f"o_mcd_{a}"]) and np.allclose(S[f"mvd_{a}"], S[f"o_mvd_{a}"])
    S[f"ag0_{a}"] = S[f"fl_ag0_full_{a}"]
    S[f"ex_{a}"] = S[f"ag_{a}_full"] - S[f"ag0_{a}"]
    S[f"exc_{a}"] = S[f"ag_{a}_capped"] - S[f"fl_ag0_capped_{a}"]
    for m in MET:
        S[f"ex_{m}_{a}"] = S[f"o_{m}_{a}"] - S[f"fl_{m}_{a}"]


def wil(x, y):
    """scipy default Wilcoxon signed-rank on paired scenario means; differences
    rounded to 1e-12 so that floating-point noise does not break ties."""
    dd = np.round(np.asarray(x, float) - np.asarray(y, float), 12)
    r = stats.wilcoxon(dd)
    return dict(W=float(r.statistic), p=float(r.pvalue),
                pos=int((dd > 0).sum()), neg=int((dd < 0).sum()), tie=int((dd == 0).sum()))


def mean(df, col, **flt):
    for k_, v in flt.items():
        df = df[df[k_].isin(v) if isinstance(v, (list, tuple)) else df[k_] == v]
    return float(df[col].mean())


G = lambda **f: S.pipe(lambda s: s[np.logical_and.reduce([s[k_] == v for k_, v in f.items()])] if f else s)

# ---------------------------------------------------------------- tests
T = {}
T["RR"] = wil(S.rr_km_full, S.rr_hc_full); T["AG"] = wil(S.ag_km_full, S.ag_hc_full)
T["RRc"] = wil(S.rr_km_capped, S.rr_hc_capped); T["AGc"] = wil(S.ag_km_capped, S.ag_hc_capped)
T["AGnull_km"] = wil(S.ag_km_full, S.ag0_km); T["AGnull_hc"] = wil(S.ag_hc_full, S.ag0_hc)
T["null"] = wil(S.ag0_km, S.ag0_hc); T["ex"] = wil(S.ex_km, S.ex_hc); T["exc"] = wil(S.exc_km, S.exc_hc)
for dist in ("gamma", "normal"):
    s = G(distribution=dist)
    T[f"AG_{dist}"] = wil(s.ag_km_full, s.ag_hc_full); T[f"null_{dist}"] = wil(s.ag0_km, s.ag0_hc)
    T[f"ex_{dist}"] = wil(s.ex_km, s.ex_hc)
    for sp in SEPS:
        t = s[s.sep == sp]; T[f"AG_{dist}_{sp}"] = wil(t.ag_km_full, t.ag_hc_full)
for m in MET:
    T[f"obs_{m}"] = wil(S[f"o_{m}_km"], S[f"o_{m}_hc"]); T[f"floor_{m}"] = wil(S[f"fl_{m}_km"], S[f"fl_{m}_hc"])
    T[f"exdiff_{m}"] = wil(S[f"ex_{m}_km"], S[f"ex_{m}_hc"])
    for a in ("km", "hc"):
        T[f"cart_{m}_{a}"] = wil(S[f"o_{m}_{a}"], S[f"fl_{m}_{a}"])


def eta2(col, inter=False):
    """partial eta^2 in the balanced 3x4x3x2x2 design (x5 replicates) from
    orthogonal effect decomposition; identical to OLS with factor coding."""
    df = repl.copy(); y = df[col].values; gm = y.mean(); fitted = np.full(len(y), gm); SS = {}
    for f in F:
        e = df.groupby(f)[col].transform("mean") - gm; SS[f] = float((e ** 2).sum()); fitted = fitted + e
    if inter:
        for f1, f2 in itertools.combinations(F, 2):
            e = (df.groupby([f1, f2])[col].transform("mean") - df.groupby(f1)[col].transform("mean")
                 - df.groupby(f2)[col].transform("mean") + gm)
            SS[f"{f1}:{f2}"] = float((e ** 2).sum()); fitted = fitted + e
    rss = float(((y - fitted) ** 2).sum()); tss = float(((y - gm) ** 2).sum())
    return {"R2": 1 - rss / tss, **{k_: v / (v + rss) for k_, v in SS.items()}}


E = {c: eta2(c) for c in ("rr_km_full", "rr_hc_full", "ag_km_full", "ag_hc_full")}
E2 = {c: eta2(c, True) for c in ("ag_km_full", "ag_hc_full")}

# collapse cells, rho/p shares
o = kr.copy()
def collapse(a, r):
    t = o[o.k >= 3]
    cs = t.groupby(F)[f"khat_real_{a}_{r}"].apply(lambda x: bool((x == 2).all()))
    cells = set(cs[cs].index)
    Sk = S.set_index(F); k3 = Sk[Sk.index.get_level_values("k") >= 3]
    ins = k3[[i in cells for i in k3.index]][f"ag_{a}_{r}"].mean()
    out = k3[[i not in cells for i in k3.index]][f"ag_{a}_{r}"].mean()
    seps = {i[F.index("sep")] for i in cells}
    return dict(share2=float((t[f"khat_real_{a}_{r}"] == 2).mean()), n=len(cells), evals=len(cells) * 5000 / 720000,
                inside=float(ins), outside=float(out), maxsep=max(seps),
                p10=float((o[(o.p == 10) & (o.sep <= 2)][f"khat_real_{a}_{r}"] == 2).mean()))
COL = {(r, a): collapse(a, r) for r in ("full", "capped") for a in ("km", "hc")}
le2 = o[o.sep <= 2]
SH = {(rh, a): float((le2[le2.rho == rh][f"khat_real_{a}_full"] == 2).mean()) for rh in (0.0, 0.4) for a in ("km", "hc")}

def pairs(a):
    return kr.groupby(F)[f"khat_real_{a}_full"].apply(
        lambda x: np.mean([u == v for u, v in itertools.combinations(x.values, 2)])).rename(f"pair_{a}").reset_index()
S = S.merge(pairs("km"), on=F).merge(pairs("hc"), on=F)

same_rr = float(((d.khat_syn_km_full == d.k) == (d.khat_syn_hc_full == d.k)).mean())
se = lambda s: float(s.std(ddof=1) / np.sqrt(len(s)))

# contingency table S1
def cont(a):
    out = {}
    for sp in SEPS:
        t = d[d.sep == sp]
        ro, sy = t[f"khat_real_{a}_full"].clip(upper=5), t[f"khat_syn_{a}_full"].clip(upper=5)
        ct = pd.crosstab(ro, sy).reindex(index=[2, 3, 4, 5], columns=[2, 3, 4, 5], fill_value=0) / len(t) * 100
        lo = float((t[f"khat_syn_{a}_full"] < t[f"khat_real_{a}_full"]).mean() * 100)
        hi = float((t[f"khat_syn_{a}_full"] > t[f"khat_real_{a}_full"]).mean() * 100)
        out[sp] = (ct, float((t[f"khat_syn_{a}_full"] == t[f"khat_real_{a}_full"]).mean() * 100), lo, hi, len(t))
    return out
CT = {a: cont(a) for a in ("km", "hc")}

# m = 100 against m = 1000 (Supplementary Section S8)
k100 = pd.read_parquet(R / "khat_fidelity_full_m100.parquet")
def margins(df):
    dd = df.copy(); cols = []
    for a in ("km", "hc"):
        for r in ("full", "capped"):
            dd[f"rr_{a}_{r}"] = (dd[f"khat_syn_{a}_{r}"] == dd.k).astype(float)
            dd[f"ag_{a}_{r}"] = (dd[f"khat_syn_{a}_{r}"] == dd[f"khat_real_{a}_{r}"]).astype(float)
            cols += [f"rr_{a}_{r}", f"ag_{a}_{r}"]
    cols += [f"{m}_{a}" for m in ("mcd", "mvd", "dgini") for a in ("km", "hc")]
    out = {("all", c): dd[c].mean() for c in cols}
    for f in F:
        for lvl, row in dd.groupby(f)[cols].mean().iterrows():
            out.update({(f, lvl, c): row[c] for c in cols})
    return out
m1, m0 = margins(kf), margins(k100)
M100 = max(abs(m1[x] - m0[x]) for x in m1)
TIM = json.loads((R / "scaling_timings.json").read_text())
SP = {int(w): TIM["1"] / v for w, v in TIM.items()}

# ---------------------------------------------------------------- claims
# (where, value shown in the manuscript, recomputed value, kind)
# kind: 'd' decimal as printed; 'pct' printed as percentage; 'int'; 'p' two
# significant figures (a x 10^-b); 'W' test statistic; 'lt:<bound>' upper bound
C = []
def c(where, shown, val, kind="d"): C.append((where, shown, val, kind))

g = lambda col, **f: mean(S, col, **f)
A = {"km": "k-means", "hc": "Ward"}
# Abstract
c("Abstract", "0.84", g("ag_km_full")); c("Abstract", "0.81", g("ag_hc_full"))
c("Abstract", "0.81", g("ag_km_full", distribution="gamma")); c("Abstract", "0.73", g("ag_hc_full", distribution="gamma"))
c("Abstract", "0.87", g("ag_km_full", distribution="normal")); c("Abstract", "0.89", g("ag_hc_full", distribution="normal"))
# 3.2 Number of groups
for sp, (x, y) in zip(SEPS, [("0.247", "0.281"), ("0.288", "0.295"), ("0.810", "0.789"), ("0.954", "0.950")]):
    c(f"S3.2 RR sigma={sp:g}", x, g("rr_km_full", sep=sp)); c(f"S3.2 RR sigma={sp:g}", y, g("rr_hc_full", sep=sp))
c("S3.2 AG sigma=0.1", "0.684", g("ag_km_full", sep=0.1)); c("S3.2 AG sigma=0.1", "0.646", g("ag_hc_full", sep=0.1))
c("S3.2 AG sigma=10", "0.982", g("ag_km_full", sep=10.0)); c("S3.2 AG sigma=10", "0.975", g("ag_hc_full", sep=10.0))
c("S3.2 AG overall", "0.839", g("ag_km_full")); c("S3.2 AG overall", "0.811", g("ag_hc_full"))
c("S3.2 orig. recovery sigma=0.1", "0.233", g("or_km_full", sep=0.1)); c("S3.2 orig. recovery sigma=0.1", "0.294", g("or_hc_full", sep=0.1))
for kk, x in zip((2, 3, 4), ("0.819", "0.468", "0.437")): c(f"S3.2 RR k={kk} (k-means)", x, g("rr_km_full", k=kk))
c("S3.2 RR k>=3, sigma<=2, max", "0.12", float(S[(S.k >= 3) & (S.sep <= 2)].groupby(["k", "sep"])[["rr_km_full", "rr_hc_full"]].mean().max().max()))
c("S3.2 RR k>=3, sigma=10, min (exceeds)", "0.90", float(S[(S.k >= 3) & (S.sep == 10)].groupby("k")[["rr_km_full", "rr_hc_full"]].mean().min().min()), "gt:0.90")
for kk, x in zip((2, 3, 4), ("0.847", "0.838", "0.833")): c(f"S3.2 AG k={kk} (k-means)", x, g("ag_km_full", k=kk))
c("S3.2 eta2 RR sep", "0.565", E["rr_km_full"]["sep"]); c("S3.2 eta2 RR sep", "0.577", E["rr_hc_full"]["sep"])
c("S3.2 eta2 RR k", "0.287", E["rr_km_full"]["k"]); c("S3.2 eta2 RR k", "0.357", E["rr_hc_full"]["k"])
c("S3.2 eta2 AG sep", "0.245", E["ag_km_full"]["sep"]); c("S3.2 eta2 AG sep", "0.229", E["ag_hc_full"]["sep"])
c("S3.2 eta2 AG rho", "0.141", E["ag_km_full"]["rho"]); c("S3.2 eta2 AG rho", "0.075", E["ag_hc_full"]["rho"])
c("S3.2 eta2 AG distribution", "0.019", E["ag_km_full"]["distribution"]); c("S3.2 eta2 AG distribution", "0.105", E["ag_hc_full"]["distribution"])
c("S3.2 eta2 AG k (below)", "0.001", max(E["ag_km_full"]["k"], E["ag_hc_full"]["k"]), "lt:0.001")
c("S3.2 R2 main effects AG", "0.340", E["ag_km_full"]["R2"]); c("S3.2 R2 main effects AG", "0.349", E["ag_hc_full"]["R2"])
c("S3.2 R2 two-way AG", "0.606", E2["ag_km_full"]["R2"]); c("S3.2 R2 two-way AG", "0.605", E2["ag_hc_full"]["R2"])
c("S3.2 eta2 rho x sep", "0.282", E2["ag_km_full"]["rho:sep"]); c("S3.2 eta2 rho x sep", "0.179", E2["ag_hc_full"]["rho:sep"])
# Table 2 footnote
c("Table 2 note: collapse cells k-means", "22", COL[("full", "km")]["n"], "int"); c("Table 2 note: collapse cells Ward", "26", COL[("full", "hc")]["n"], "int")
c("Table 2 note: share of evaluations", "15.3", COL[("full", "km")]["evals"], "pct"); c("Table 2 note: share of evaluations", "18.1", COL[("full", "hc")]["evals"], "pct")
for a in ("km", "hc"):
    c(f"Table 2 note: AG inside ({A[a]})", {"km": "0.955", "hc": "0.929"}[a], COL[("full", a)]["inside"])
    c(f"Table 2 note: AG outside ({A[a]})", {"km": "0.799", "hc": "0.762"}[a], COL[("full", a)]["outside"])
c("Table 2 note: all collapse cells at sigma<=2", "2", max(COL[(r, a)]["maxsep"] for r in ("full", "capped") for a in ("km", "hc")), "le:2")
# 3.2 further patterns
c("S3.2 AG rho=0.4 vs 0 (k-means)", "0.925", g("ag_km_full", rho=0.4)); c("S3.2 AG rho=0.4 vs 0 (k-means)", "0.753", g("ag_km_full", rho=0.0))
c("S3.2 AG rho=0.4 vs 0 (Ward)", "0.877", g("ag_hc_full", rho=0.4)); c("S3.2 AG rho=0.4 vs 0 (Ward)", "0.744", g("ag_hc_full", rho=0.0))
c("S3.2 khatR=2, sigma<=2, rho=0.4", "91.1", SH[(0.4, "km")], "pct"); c("S3.2 khatR=2, sigma<=2, rho=0.4", "87.8", SH[(0.4, "hc")], "pct")
c("S3.2 khatR=2, sigma<=2, rho=0", "38.3", SH[(0.0, "km")], "pct"); c("S3.2 khatR=2, sigma<=2, rho=0", "62.2", SH[(0.0, "hc")], "pct")
ge6 = S[S.sep >= 6]
c("S3.2 AG sigma>=6 rho=0.4/0 (k-means)", "0.948", mean(ge6, "ag_km_full", rho=0.4)); c("S3.2 AG sigma>=6 rho=0.4/0 (k-means)", "0.960", mean(ge6, "ag_km_full", rho=0.0))
c("S3.2 AG sigma>=6 rho=0.4/0 (Ward)", "0.914", mean(ge6, "ag_hc_full", rho=0.4)); c("S3.2 AG sigma>=6 rho=0.4/0 (Ward)", "0.944", mean(ge6, "ag_hc_full", rho=0.0))
le2S = S[S.sep <= 2]
for pp, x in zip((2, 5, 10), ("0.536", "0.703", "0.839")): c(f"S3.2 Ward AG sigma<=2 p={pp}", x, mean(le2S, "ag_hc_full", p=pp))
c("S3.2 khatR=2 at p=10, sigma<=2", "80.8", COL[("full", "km")]["p10"], "pct"); c("S3.2 khatR=2 at p=10, sigma<=2", "90.0", COL[("full", "hc")]["p10"], "pct")
for pp, x, y in zip((2, 5, 10), ("0.976", "0.903", "0.899"), ("0.976", "0.853", "0.818")):
    c(f"S3.2 AG sigma=6 p={pp}", x, g("ag_km_full", sep=6.0, p=pp)); c(f"S3.2 AG sigma=6 p={pp} (Ward)", y, g("ag_hc_full", sep=6.0, p=pp))
# 3.3 null
c("S3.3 AG0 overall", "0.871", g("ag0_km")); c("S3.3 AG0 overall", "0.826", g("ag0_hc"))
c("S3.3 excess overall", "-0.032", g("ex_km")); c("S3.3 excess overall", "-0.016", g("ex_hc"))
for a, (n1, n2, n3, pv) in (("km", ("99", "10", "35", "1.1e-11")), ("hc", ("90", "30", "24", "4.8e-6"))):
    t = T[f"AGnull_{a}"]
    c(f"S3.3 AG below null ({A[a]})", n1, t["neg"], "int"); c(f"S3.3 AG above null ({A[a]})", n2, t["pos"], "int")
    c(f"S3.3 ties ({A[a]})", n3, t["tie"], "int"); c(f"S3.3 Wilcoxon p ({A[a]})", pv, t["p"], "p")
c("S3.3 bootstrap fails", "12.9", 1 - g("ag0_km"), "pct"); c("S3.3 bootstrap fails", "17.4", 1 - g("ag0_hc"), "pct")
c("S3.3 independent pairs", "0.801", g("pair_km")); c("S3.3 independent pairs", "0.767", g("pair_hc"))
# 3.4 geometry
c("S3.4 MCD sigma=0.1", "0.604", g("o_mcd_km", sep=0.1)); c("S3.4 MCD sigma=0.1", "0.859", g("o_mcd_hc", sep=0.1))
c("S3.4 MCD sigma=10", "0.090", g("o_mcd_km", sep=10.0)); c("S3.4 MCD sigma=10", "0.095", g("o_mcd_hc", sep=10.0))
c("S3.4 MVD sigma=0.1", "0.353", g("o_mvd_km", sep=0.1)); c("S3.4 MVD sigma=0.1", "0.613", g("o_mvd_hc", sep=0.1))
c("S3.4 MVD sigma=10", "0.112", g("o_mvd_km", sep=10.0)); c("S3.4 MVD sigma=10", "0.133", g("o_mvd_hc", sep=10.0))
c("S3.4 observed lower for k-means: MCD", "133", T["obs_mcd"]["neg"], "int"); c("S3.4 ... MVD", "144", T["obs_mvd"]["neg"], "int")
c("S3.4 ... Delta G", "138", T["obs_dgini"]["neg"], "int")
c("S3.4 obs. k-means vs Ward p (max of 3)", "1e-20", max(T[f"obs_{m}"]["p"] for m in ("mcd", "mvd", "dgini")), "lt:1e-20")
for m, (fk, ok, fh, oh) in (("mcd", ("0.222", "0.303", "0.403", "0.460")), ("mvd", ("0.150", "0.219", "0.324", "0.392")),
                            ("dgini", ("0.021", "0.030", "0.053", "0.061"))):
    c(f"S3.4 floor/observed {m}", fk, g(f"fl_{m}_km")); c(f"S3.4 floor/observed {m}", ok, g(f"o_{m}_km"))
    c(f"S3.4 floor/observed {m}", fh, g(f"fl_{m}_hc")); c(f"S3.4 floor/observed {m}", oh, g(f"o_{m}_hc"))
for m, x in (("mcd", "121"), ("mvd", "135"), ("dgini", "132")): c(f"S3.4 floor lower for k-means: {m}", x, T[f"floor_{m}"]["neg"], "int")
for m, (xk, xh) in (("mcd", ("144", "143")), ("mvd", ("144", "141")), ("dgini", ("144", "129"))):
    c(f"S3.4 positive CART excess {m} k-means", xk, T[f"cart_{m}_km"]["pos"], "int"); c(f"S3.4 positive CART excess {m} Ward", xh, T[f"cart_{m}_hc"]["pos"], "int")
c("S3.4 CART excess p (max of 6)", "1e-20", max(T[f"cart_{m}_{a}"]["p"] for m in ("mcd", "mvd", "dgini") for a in ("km", "hc")), "lt:1e-20")
for m, (xk, xh, pv) in (("mcd", ("0.081", "0.057", "8.8e-6")), ("mvd", ("0.069", "0.068", "0.973")), ("dgini", ("0.009", "0.008", "0.462"))):
    c(f"S3.4 excess {m}", xk, g(f"ex_{m}_km")); c(f"S3.4 excess {m}", xh, g(f"ex_{m}_hc")); c(f"S3.4 excess {m} p", pv, T[f"exdiff_{m}"]["p"], "p")
c("S3.4 MCDsd sigma=0.1", "0.605", g("o_mcd_sd_km", sep=0.1)); c("S3.4 MCDsd sigma=10", "0.189", g("o_mcd_sd_km", sep=10.0))
c("S3.4 MCDsd sigma=0.1 (Ward)", "0.860", g("o_mcd_sd_hc", sep=0.1)); c("S3.4 MCDsd sigma=10 (Ward)", "0.201", g("o_mcd_sd_hc", sep=10.0))
c("S3.4 MCDsd excess 'about'", "0.10", g("ex_mcd_sd_km")); c("S3.4 MCDsd excess 'about'", "0.08", g("ex_mcd_sd_hc"))
c("S3.4 RVD observed", "8.2", g("o_rvd_km"), "pct"); c("S3.4 RVD observed", "15.2", g("o_rvd_hc"), "pct")
c("S3.4 RVD floor (points)", "5.5", g("fl_rvd_km"), "pct"); c("S3.4 RVD floor (points)", "12.6", g("fl_rvd_hc"), "pct")
c("S3.4 RVD excess 'about 2.7 points'", "2.7", g("ex_rvd_km"), "pct")
c("S3.4 RVD excess", "0.027", g("ex_rvd_km")); c("S3.4 RVD excess", "0.026", g("ex_rvd_hc")); c("S3.4 RVD excess p", "0.891", T["exdiff_rvd"]["p"], "p")
for sp, xk, xh in zip(SEPS, ("0.022", "0.021", "0.030", "0.035"), ("0.015", "0.013", "0.036", "0.041")):
    c(f"S3.4 RVD excess sigma={sp:g}", xk, g("ex_rvd_km", sep=sp)); c(f"S3.4 RVD excess sigma={sp:g} (Ward)", xh, g("ex_rvd_hc", sep=sp))
for pp, (m_, lo, hi) in ((2, ("0.06", "0.04", "0.08")), (10, ("0.39", "0.32", "0.47"))):
    s = S[S.p == pp].o_mvd_km
    c(f"S3.4 MVD p={pp} (k-means)", m_, float(s.mean()), "d2"); c(f"S3.4 MVD p={pp} -1.96 SE", lo, float(s.mean() - 1.96 * se(s)), "d2")
    c(f"S3.4 MVD p={pp} +1.96 SE", hi, float(s.mean() + 1.96 * se(s)), "d2")
c("S3.4 MVD p=2 (Ward)", "0.13", g("o_mvd_hc", p=2)); c("S3.4 MVD p=10 (Ward)", "0.65", g("o_mvd_hc", p=10))
for pp, xk, xh, fk, ek, eh in zip((2, 5, 10), ("0.032", "0.040", "0.039"), ("0.067", "0.078", "0.065"), ("0.047", "0.144", "0.259"),
                                  ("0.008", "0.011", "0.013"), ("0.006", "0.010", "0.014")):
    c(f"S3.4 MVD/p p={pp}", xk, g("o_mvd_pc_km", p=pp)); c(f"S3.4 MVD/p p={pp} (Ward)", xh, g("o_mvd_pc_hc", p=pp))
    c(f"S3.4 MVD floor p={pp}", fk, g("fl_mvd_km", p=pp))
    c(f"S3.4 MVD/p excess p={pp}", ek, g("ex_mvd_pc_km", p=pp)); c(f"S3.4 MVD/p excess p={pp} (Ward)", eh, g("ex_mvd_pc_hc", p=pp))
c("S3.4 dG Normal/Gamma k-means", "0.028", g("o_dgini_km", distribution="normal")); c("S3.4 dG Normal/Gamma k-means", "0.032", g("o_dgini_km", distribution="gamma"))
c("S3.4 dG Normal/Gamma Ward", "0.057", g("o_dgini_hc", distribution="normal")); c("S3.4 dG Normal/Gamma Ward", "0.065", g("o_dgini_hc", distribution="gamma"))
# 3.5 distribution
for dist, xk, xh, ok, oh in (("normal", "86.2", "84.5", "90.0", "91.1"), ("gamma", "75.9", "73.2", "80.0", "78.9")):
    c(f"S3.5 RR sigma=6 {dist}", xk, g("rr_km_full", sep=6.0, distribution=dist), "pct"); c(f"S3.5 RR sigma=6 {dist} (Ward)", xh, g("rr_hc_full", sep=6.0, distribution=dist), "pct")
    c(f"S3.5 orig. recovery sigma=6 {dist}", ok, g("or_km_full", sep=6.0, distribution=dist), "pct"); c(f"S3.5 orig. recovery sigma=6 {dist} (Ward)", oh, g("or_hc_full", sep=6.0, distribution=dist), "pct")
for sp, nk, gk, nh, gh in ((0.1, "0.665", "0.702", "0.782", "0.511"), (2.0, "0.879", "0.648", "0.873", "0.603"),
                           (6.0, "0.947", "0.906", "0.924", "0.841"), (10.0, "0.983", "0.981", "0.982", "0.969")):
    c(f"S3.5/3.6 AG Normal sigma={sp:g}", nk, g("ag_km_full", sep=sp, distribution="normal")); c(f"S3.5/3.6 AG Gamma sigma={sp:g}", gk, g("ag_km_full", sep=sp, distribution="gamma"))
    c(f"S3.5/3.6 AG Normal sigma={sp:g} (Ward)", nh, g("ag_hc_full", sep=sp, distribution="normal")); c(f"S3.5/3.6 AG Gamma sigma={sp:g} (Ward)", gh, g("ag_hc_full", sep=sp, distribution="gamma"))
c("S3.5 Ward AG0 sigma=0.1 Gamma", "0.515", g("ag0_hc", sep=0.1, distribution="gamma")); c("S3.5 Ward AG0 sigma=0.1 Normal", "0.773", g("ag0_hc", sep=0.1, distribution="normal"))
gx = [g("ex_hc", sep=sp, distribution="gamma") for sp in SEPS]
c("S3.5 Ward Gamma excess, min", "-0.041", min(gx)); c("S3.5 Ward Gamma excess, max", "-0.004", max(gx))
c("S3.5 k-means AG0 Gamma sigma=0.1", "0.788", g("ag0_km", sep=0.1, distribution="gamma")); c("S3.5 k-means AG0 Gamma sigma=2", "0.726", g("ag0_km", sep=2.0, distribution="gamma"))
c("S3.5 k-means Gamma excess sigma=0.1", "-0.086", g("ex_km", sep=0.1, distribution="gamma")); c("S3.5 k-means Gamma excess sigma=2", "-0.078", g("ex_km", sep=2.0, distribution="gamma"))
c("S3.5 Normal excess", "-0.011", g("ex_km", distribution="normal")); c("S3.5 Normal excess (Ward)", "-0.012", g("ex_hc", distribution="normal"))
# 3.6 algorithms
c("S3.6 RR overall", "0.575", g("rr_km_full")); c("S3.6 RR overall", "0.579", g("rr_hc_full"))
c("S3.6 RR W", "3508.5", T["RR"]["W"], "W"); c("S3.6 RR p", "0.750", T["RR"]["p"], "p")
c("S3.6 same outcome (RR)", "92.0", same_rr, "pct")
c("S3.6 AG higher/lower/ties", "90", T["AG"]["pos"], "int"); c("S3.6 AG lower", "30", T["AG"]["neg"], "int"); c("S3.6 AG ties", "24", T["AG"]["tie"], "int")
c("S3.6 AG W", "2088.5", T["AG"]["W"], "W"); c("S3.6 AG p", "5.4e-5", T["AG"]["p"], "p")
c("S3.6 Gamma AG", "0.809", g("ag_km_full", distribution="gamma")); c("S3.6 Gamma AG", "0.731", g("ag_hc_full", distribution="gamma"))
c("S3.6 Gamma higher in", "59", T["AG_gamma"]["pos"], "int"); c("S3.6 Gamma p", "2.6e-6", T["AG_gamma"]["p"], "p")
for sp, pv in ((0.1, "0.002"), (6.0, "0.001"), (10.0, "0.006"), (2.0, "0.099")): c(f"S3.6 Gamma sigma={sp:g} p", pv, T[f"AG_gamma_{sp}"]["p"], "p")
c("S3.6 Normal AG", "0.869", g("ag_km_full", distribution="normal")); c("S3.6 Normal AG", "0.890", g("ag_hc_full", distribution="normal"))
c("S3.6 Normal p", "0.595", T["AG_normal"]["p"], "p"); c("S3.6 Normal sigma=0.1 p", "0.136", T["AG_normal_0.1"]["p"], "p")
c("S3.6 null W", "966", T["null"]["W"], "W"); c("S3.6 null p", "6.0e-5", T["null"]["p"], "p")
c("S3.6 Gamma AG0", "0.863", g("ag0_km", distribution="gamma")); c("S3.6 Gamma AG0", "0.750", g("ag0_hc", distribution="gamma")); c("S3.6 Gamma null p", "6.3e-7", T["null_gamma"]["p"], "p")
c("S3.6 Normal AG0", "0.880", g("ag0_km", distribution="normal")); c("S3.6 Normal AG0", "0.902", g("ag0_hc", distribution="normal")); c("S3.6 Normal null p", "0.900", T["null_normal"]["p"], "p")
c("S3.6 difference in excess", "-0.017", g("ex_km") - g("ex_hc")); c("S3.6 excess W", "2846", T["ex"]["W"], "W"); c("S3.6 excess p", "0.040", T["ex"]["p"], "p")
c("S3.6 Gamma difference in excess", "-0.034", g("ex_km", distribution="gamma") - g("ex_hc", distribution="gamma")); c("S3.6 Gamma excess p", "0.024", T["ex_gamma"]["p"], "p")
c("S3.6 Gamma diff. in excess sigma=0.1", "-0.082", g("ex_km", sep=0.1, distribution="gamma") - g("ex_hc", sep=0.1, distribution="gamma"))
c("S3.6 Gamma diff. in excess sigma=2", "-0.058", g("ex_km", sep=2.0, distribution="gamma") - g("ex_hc", sep=2.0, distribution="gamma"))
c("S3.6 Normal excess p", "0.640", T["ex_normal"]["p"], "p")
sil = {a: [g(f"sil_syn_{a}", sep=sp) - g(f"sil_real_{a}", sep=sp) for sp in SEPS] for a in ("km", "hc")}
c("S3.6 silhouette max |diff| (Ward, sigma=0.1)", "0.0125", max(abs(x) for v in sil.values() for x in v))
c("S3.6 silhouette max at Ward sigma=0.1", "0.0125", abs(sil["hc"][0]))
c("S3.6 silhouette k-means real/syn", "0.396", g("sil_real_km")); c("S3.6 silhouette k-means real/syn", "0.397", g("sil_syn_km"))
c("S3.6 silhouette Ward real/syn", "0.376", g("sil_real_hc")); c("S3.6 silhouette Ward real/syn", "0.377", g("sil_syn_hc"))
# Discussion (Section 4) -- repeats; listed so that every occurrence is covered
c("S4 first finding", "0.684/0.646/0.982/0.975", None, "repeat of S3.2")
c("S4 first finding", "0.247/0.281/0.954/0.950; 0.819/0.468/0.437", None, "repeat of S3.2")
c("S4 second finding", "0.839/0.811; 0.809/0.731; 0.869/0.890; AG0 0.871/0.826", None, "repeat of S3.3/S3.6")
c("S4 second finding: lost beyond resampling", "0.032", -g("ex_km")); c("S4 second finding: lost beyond resampling", "0.016", -g("ex_hc"))
c("S4 third finding: relative dispersion excess", "2.7", g("ex_rvd_km"), "pct")
c("S4/S3.2 collapse cells 'a sixth of the design'", "1/6", (COL[("full", "km")]["evals"] + COL[("full", "hc")]["evals"]) / 2, "approx:0.1667")
# Supplementary prose
c("Supp S2 exact agreement sigma=0.1/10 (k-means)", "68.4", CT["km"][0.1][1] / 100, "pct"); c("Supp S2", "98.2", CT["km"][10.0][1] / 100, "pct")
c("Supp S2 exact agreement sigma=0.1/10 (Ward)", "64.6", CT["hc"][0.1][1] / 100, "pct"); c("Supp S2", "97.5", CT["hc"][10.0][1] / 100, "pct")
c("Supp S2 lower estimate sigma=0.1 (k-means)", "15.2", CT["km"][0.1][2] / 100, "pct"); c("Supp S2 higher estimate", "16.4", CT["km"][0.1][3] / 100, "pct")
c("Supp S2 cell khatR>=5, khatS=2", "8.4", CT["km"][0.1][0].loc[5, 2] / 100, "pct")
for sp, xk, xh in ((0.1, "75.1", "67.6"), (2.0, "79.7", "75.9")):
    c(f"Supp Table S1 caption capped AG sigma={sp:g}", xk, g("ag_km_capped", sep=sp), "pct"); c(f"Supp Table S1 caption capped AG sigma={sp:g} (Ward)", xh, g("ag_hc_capped", sep=sp), "pct")
c("Supp Table S1 caption: capped vs fixed at sigma>=6 (pp)", "0.1", 100 * max(abs(g(f"ag_{a}_capped", sep=sp) - g(f"ag_{a}_full", sep=sp)) for a in ("km", "hc") for sp in (6.0, 10.0)), "le:0.1")
c("Supp Table S1 caption n per level", "180,000", CT["km"][0.1][4], "int")
c("Supp S3 capped Gamma AG", "0.833", g("ag_km_capped", distribution="gamma")); c("Supp S3 capped Gamma AG", "0.749", g("ag_hc_capped", distribution="gamma"))
c("Supp S3 capped Normal AG", "0.896", g("ag_km_capped", distribution="normal")); c("Supp S3 capped Normal AG", "0.898", g("ag_hc_capped", distribution="normal"))
c("Supp S3 capped AG0", "0.891", g("fl_ag0_capped_km")); c("Supp S3 capped AG0", "0.841", g("fl_ag0_capped_hc"))
c("Supp S3 capped difference in excess", "-0.009", g("exc_km") - g("exc_hc")); c("Supp S3 capped excess p", "0.204", T["exc"]["p"], "p")
c("Supp S3 'indistinguishable' = Table S2 capped RR p", "0.380", T["RRc"]["p"], "p")
c("Supp S8 m=100 vs m=1000 max |diff|", "0.0052", M100, "le:0.0052")
c("Supp Fig S2 speed-up 8 workers", "6.9", SP[8], "d1"); c("Supp Fig S2 efficiency 8", "87", SP[8] / 8, "pct0")
c("Supp Fig S2 efficiency 18", "56", SP[18] / 18, "pct0"); c("Supp Fig S2 efficiency 24", "45", SP[24] / 24, "pct0")
c("Supp S8 speed-up 18", "10.0", SP[18], "d1"); c("Supp S8 speed-up 12", "8.8", SP[12], "d1")


def decimals(s):
    m = re.search(r"\.(\d+)", s); return len(m.group(1)) if m else 0


def check(shown, val, kind):
    if val is None: return None, ""
    if kind == "d" or kind in ("d1", "d2"):
        dd = decimals(shown); v = float(shown)
        return abs(val - v) <= 0.5 * 10 ** -dd + 1e-9, f"{val:.{dd + 2}f}"
    if kind in ("pct", "pct0"):
        dd = decimals(shown); v = float(shown)
        return abs(100 * val - v) <= 0.5 * 10 ** -dd + 1e-9, f"{100 * val:.{dd + 2}f}%"
    if kind == "int": return int(round(val)) == int(shown.replace(",", "")), f"{val:g}"
    if kind == "W": return abs(val - float(shown)) < 1e-9, f"{val:g}"
    if kind == "p":
        v = float(shown)
        if "e" in shown:
            mant = shown.split("e")[0]; dd = decimals(mant); ex = int(shown.split("e")[1])
            return abs(val / 10 ** ex - float(mant)) <= 0.5 * 10 ** -dd + 1e-9, f"{val:.3g}"
        dd = decimals(shown); return abs(val - v) <= 0.5 * 10 ** -dd + 1e-9, f"{val:.4g}"
    if kind.startswith("lt:"): return val < float(kind[3:]), f"{val:.3g}"
    if kind.startswith("gt:"): return val > float(kind[3:]), f"{val:.4f}"
    if kind.startswith("le:"): return val <= float(kind[3:]) + 1e-12, f"{val:.4g}"
    if kind.startswith("approx:"): return abs(val - float(kind[7:])) < 0.02, f"{val:.4f}"
    raise ValueError(kind)


rows = []; nbad = 0; nchk = 0
for where, shown, val, kind in C:
    ok, rec = check(shown, val, kind)
    if ok is None: rows.append((where, shown, "--", "covered by the lines above")); continue
    nchk += 1; nbad += (not ok)
    rows.append((where, shown, rec, "OK" if ok else "MISMATCH"))

# ---------------------------------------------------------------- tables
TD = M / "tables"
def table_numbers(path):
    out = []
    for l in path.read_text().splitlines():
        if "\\\\" not in l or l.strip().startswith(("\\toprule", "\\midrule", "\\bottomrule")): continue
        row = []
        for cell in l.split("\\\\")[0].split("&"):
            cell = cell.strip()
            m2 = re.fullmatch(r"\$([+-])(\d+\.\d+)\$", cell)
            mc = re.fullmatch(r"\\multicolumn\{2\}\{c\}\{(.*)\}", cell)
            if mc: cell = mc.group(1)
            mt = re.search(r"([\d.]+)\\times10\^\{(-?\d+)\}", cell)
            if m2: row.append(float(m2.group(1) + m2.group(2)))
            elif mt: row.append(("p", float(mt.group(1)), int(mt.group(2))))
            elif re.fullmatch(r"\d+\.\d+", cell): row.append(float(cell))
        if row: out.append(row)
    return out

def cmp_table(fname, expected, pcols=()):
    got = table_numbers(TD / fname) if fname != "supp_table.tex" else None
    assert len(got) == len(expected), (fname, len(got), len(expected))
    n = 0; bad = []
    for i, (gr, er) in enumerate(zip(got, expected)):
        assert len(gr) == len(er), (fname, i, gr, er)
        for j, (x, y) in enumerate(zip(gr, er)):
            n += 1
            if isinstance(x, tuple):
                ok = abs(y / 10 ** x[2] - x[1]) <= 0.05 + 1e-9; shown = f"{x[1]}e{x[2]}"
            elif i == len(got) - 1 and fname == "tab_factors.tex" or (fname == "tab_floor.tex" and j == 6) or (fname == "tabS_range.tex" and i == len(got) - 2):
                ok = abs(y - x) <= 0.0005 + 1e-9; shown = f"{x}"
            elif fname == "tabS_range.tex" and i == len(got) - 3:
                ok = abs(y - x) < 1e-9; shown = f"{x}"
            else:
                ok = abs(y - x) <= 0.0005 + 1e-9; shown = f"{x}"
            if not ok: bad.append((i, j, shown, y))
    return n, bad

gcols = lambda m: [f"o_{m}_km", f"fl_{m}_km", f"ex_{m}_km", f"o_{m}_hc", f"fl_{m}_hc", f"ex_{m}_hc"]
TAB = {}
exp = []
for f in ["sep", "k", "p", "rho", "distribution"]:
    gg = S.groupby(f)[["rr_km_full", "rr_hc_full", "ag_km_full", "ag_hc_full"]].mean()
    if f == "distribution": gg = gg.loc[["normal", "gamma"]]
    exp += gg.values.tolist()
exp += [S[["rr_km_full", "rr_hc_full", "ag_km_full", "ag_hc_full"]].mean().tolist(), [T["RR"]["p"], T["AG"]["p"]]]
TAB["Table 2 (tab_factors.tex)"] = cmp_table("tab_factors.tex", exp)

def null_rows(cols):
    agk, agh, nk, nh = cols
    r = lambda s: [s[agk].mean(), s[nk].mean(), s[agk].mean() - s[nk].mean(), s[agh].mean(), s[nh].mean(), s[agh].mean() - s[nh].mean()]
    rows_ = [r(S[S.sep == sp]) for sp in SEPS] + [r(S[S.distribution == x]) for x in ("normal", "gamma")]
    rows_ += [r(S[(S.distribution == x) & (S.sep == sp)]) for x in ("normal", "gamma") for sp in SEPS]
    return rows_ + [r(S)]
TAB["Table 3 (tab_null.tex)"] = cmp_table("tab_null.tex", null_rows(("ag_km_full", "ag_hc_full", "ag0_km", "ag0_hc")))
TAB["Table S3 (tabS_null_capped.tex)"] = cmp_table("tabS_null_capped.tex", null_rows(("ag_km_capped", "ag_hc_capped", "fl_ag0_capped_km", "fl_ag0_capped_hc")))
TAB["Table 4 (tab_floor.tex)"] = cmp_table("tab_floor.tex", [S[gcols(m)].mean().tolist() + [T[f"exdiff_{m}"]["p"]] for m in ("mcd", "mvd", "dgini", "mcd_sd", "rvd")])
def strata(mets):
    out = []
    for m in mets:
        out += [S[S.sep == sp][gcols(m)].mean().tolist() for sp in SEPS]
        out += [S[S.distribution == x][gcols(m)].mean().tolist() for x in ("normal", "gamma")]
        out += [S[S.p == pp][gcols(m)].mean().tolist() for pp in (2, 5, 10)] + [S[gcols(m)].mean().tolist()]
    return out
TAB["Table S5 (tabS_floor.tex)"] = cmp_table("tabS_floor.tex", strata(["mcd", "mvd", "dgini"]))
TAB["Table S6 (tabS_scalefree.tex)"] = cmp_table("tabS_scalefree.tex", strata(["mvd_pc", "mcd_sd", "rvd"]))
cc = ["rr_km_full", "rr_hc_full", "ag_km_full", "ag_hc_full", "rr_km_capped", "rr_hc_capped", "ag_km_capped", "ag_hc_capped"]
exp = [S[S.sep == sp][cc].mean().tolist() for sp in SEPS] + [S[S.distribution == x][cc].mean().tolist() for x in ("normal", "gamma")]
exp += [S[cc].mean().tolist(), [T["RR"]["W"], T["AG"]["W"], T["RRc"]["W"], T["AGc"]["W"]],
        [T["RR"]["p"], T["AG"]["p"], T["RRc"]["p"], T["AGc"]["p"]],
        [g("ag0_km"), g("ag0_hc"), g("fl_ag0_capped_km"), g("fl_ag0_capped_hc")]]
TAB["Table S2 (tabS_range.tex)"] = cmp_table("tabS_range.tex", exp)
rb = lambda s: [s.ag_km_full.mean(), s.ag0_km.mean(), s.pair_km.mean(), s.ag_hc_full.mean(), s.ag0_hc.mean(), s.pair_hc.mean()]
TAB["Table S4 (tabS_baseline.tex)"] = cmp_table("tabS_baseline.tex", [rb(S[S.sep == sp]) for sp in SEPS] + [rb(S[S.distribution == x]) for x in ("normal", "gamma")] + [rb(S)])
exp = []
for r in ("full", "capped"):
    for a in ("km", "hc"):
        v = COL[(r, a)]; exp.append([v["share2"], v["evals"], v["inside"], v["outside"], v["p10"]])
TAB["Table S7 (tabS_collapse.tex), decimals"] = cmp_table("tabS_collapse.tex", exp)
# integer column of the collapse table
txt = (TD / "tabS_collapse.tex").read_text()
ints = [int(x) for x in re.findall(r"& (\d+) &", txt)]
TAB["Table S7 (tabS_collapse.tex), cell counts"] = (4, [] if ints == [COL[("full", "km")]["n"], COL[("full", "hc")]["n"], COL[("capped", "km")]["n"], COL[("capped", "hc")]["n"]] else [("counts", ints)])

# Table S1 (supp_table.tex): percentages of the k-hat cross-tabulation
st = (M / "supp_table.tex").read_text().splitlines()
cells = []
for l in st:
    m_ = re.match(r"^\s*(?:\\multirow\{4\}\{\*\}\{[\d.]+\})?\s*&\s*(?:\d|\$\\geq 5\$)\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*&\s*([\d.]+)", l)
    if m_: cells.append([float(x) for x in m_.groups()])
exact = [float(x) for x in re.findall(r"\\multirow\{4\}\{\*\}\{\$([\d.]+)\\%\$\}", "\n".join(st))]
mine = [row for a in ("km", "hc") for sp in SEPS for row in CT[a][sp][0].values.tolist()]
mine_exact = [CT[a][sp][1] for a in ("km", "hc") for sp in SEPS]
assert len(cells) == 32 and len(exact) == 8
bad_s1 = []; ties = []
for i, (x, y) in enumerate(zip(cells, mine)):
    for j, (u, w) in enumerate(zip(x, y)):
        if abs(u - w) > 0.05 + 1e-9: bad_s1.append((i, j, u, w))
        elif abs(abs(u - w) - 0.05) < 1e-9: ties.append((i, j, u, w))
bad_s1 += [("exact", i, u, w) for i, (u, w) in enumerate(zip(exact, mine_exact)) if abs(u - w) > 0.05 + 1e-9]
TAB["Table S1 (supp_table.tex)"] = (32 * 4 + 8, bad_s1)

# ---------------------------------------------------------------- report
nt = sum(v[0] for v in TAB.values()); ntb = sum(len(v[1]) for v in TAB.values())
lines = ["# VERIFICATION: independent number check of manuscript v5", "",
         "Generated by `manuscript/joc_prep/verify_numbers.py`. Every value is recomputed from the stored",
         "per-row files (`results/khat_fidelity_full.parquet`, `results/bootstrap_null.parquet`,",
         "`results/relative_metrics.parquet`, `results/khat_fidelity_full_m100.parquet`,",
         "`results/scaling_timings.json`). The script does not read `fullrange_summary.json`,",
         "`bootstrap_summary.json` or `v5_extra_numbers.json` and does not import `v5_tables.py`,",
         "so the check is independent of the code that produced the tables.", "",
         "Conventions reproduced: agreement proportions pooled over evaluations (equal to the mean of the",
         "144 scenario means, since the design is balanced); Wilcoxon signed-rank tests with scipy's default",
         "method on the 144 (or 72, or 18) paired scenario means, differences rounded to 1e-12; partial eta^2",
         "from the balanced main-effects (and two-way) decomposition of the 720 replicate-level proportions;",
         "bands = mean +/- 1.96 standard errors of the scenario means. A printed value passes when it equals",
         "the recomputed value rounded to the printed number of decimals (half-way ties accepted).", "",
         "## Summary", "",
         f"- Prose numbers (abstract, Sections 3-5, table notes, supplementary prose): **{nchk} checked, {nbad} mismatches** after the corrections below.",
         f"- Table cells (Tables 2-4 and S1-S7): **{nt} checked, {ntb} mismatches**.",
         "- Mismatches found and corrected in this pass (both now pass):",
         "  1. main.tex, Section 3.4 (MVD by dimensionality): the lower end of the k-means band at p = 2 was",
         "     printed as 0.05; the recomputed mean - 1.96 SE is 0.0447, i.e. 0.04. Corrected to `0.04--0.08`, and",
         "     the label `95% interval` replaced by `mean +/- 1.96 standard errors across scenarios`, which is",
         "     what Methods defines and what the figure shows (Methods states that these bands describe the",
         "     spread over the design, not sampling uncertainty).",
         "  2. supplementary.tex, Section S2: `15.2%` and `16.4%` are k-means values but the sentence did not",
         "     name the algorithm (Ward: 14.9% and 20.5%). `of k-means comparisons` added; numbers unchanged.",
         f"- Rounding ties (not errors): {len(ties)} cell(s) of Table S1 lie exactly half-way between two printed values" + (": " + "; ".join(f"row {i}, col {j}: printed {u}, exact {w:.4f}" for i, j, u, w in ties) if ties else "") + ". Left unchanged.",
         "- Not recomputable from the stored results (carried from v4 and reported here as unverified):",
         "  the wall-clock figures in Supplementary Table S9 and Section S8 (1.24 h synthesis, 3.6 h clustering,",
         "  1.9 s versus 84.5 s thread-pinning benchmark, 21 GB, 5.6 h bound). The 4.44 h fidelity stage matches",
         "  `results/logs/05_fidelity.log` (15,991 s); the 363 s and 745 s match `results/bootstrap_results.md`;",
         "  9.3 h = 1.24 + 3.6 + 4.44 h and the unit costs (6.2 ms, 18 ms, 1.4 ms) follow arithmetically.",
         "  Design constants (144 scenarios, 720,000 evaluations, 60,000 pairs per point, 36/48/72 scenarios",
         "  per stratum, B = 30) were checked against the parquet row counts only.", "",
         "## Tables", "", "| Table | cells checked | mismatches |", "|---|---|---|"]
for k_, (n, bad) in TAB.items():
    lines.append(f"| {k_} | {n} | {len(bad)}{(' ' + str(bad)) if bad else ''} |")
lines += ["", "## Prose numbers", "", "| Location | Printed | Recomputed | Status |", "|---|---|---|---|"]
lines += [f"| {w} | {s} | {r} | {st_} |" for w, s, r, st_ in rows]
(J / "VERIFICATION.md").write_text("\n".join(lines) + "\n")
print(f"prose {nchk} checked, {nbad} mismatches; tables {nt} cells, {ntb} mismatches; S1 ties {len(ties)}")
