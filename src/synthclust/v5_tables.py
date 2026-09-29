"""Numbers and LaTeX table fragments for manuscript v5.

Everything is read from stored results; nothing is typed by hand:
  results/fullrange_summary.json   (count results, fixed and capped range)
  results/bootstrap_summary.json   (bootstrap null, geometric floor, scale-free metrics, collapse)
  results/khat_fidelity_full.parquet (720,000 pairs; used for the few extra numbers below)
  results/bootstrap_null.parquet   (43,200 bootstrap rows)

Outputs
  results/v5_extra_numbers.json     extra numbers quoted in the v5 text
  manuscript/tables/*.tex           table fragments \\input by main.tex / supplementary.tex

Run:  PYTHONPATH=src python -m synthclust.v5_tables
"""
import json
import itertools
import numpy as np
import pandas as pd
from synthclust.paths import RESULTS_DIR, REPO

TAB = REPO / "manuscript" / "tables"
TAB.mkdir(parents=True, exist_ok=True)
FR = json.load(open(RESULTS_DIR / "fullrange_summary.json"))
BS = json.load(open(RESULTS_DIR / "bootstrap_summary.json"))
SCEN = ["p", "k", "rho", "sep", "distribution"]
SEPS = [0.1, 2, 6, 10]


def f3(x):
    return f"{x:.3f}"


def signed(x):
    return f"${x:+.3f}$" if abs(x) >= 0.0005 else "$0.000$"


def pfmt(p):
    if p < 1e-3:
        e = int(np.floor(np.log10(p)))
        m = p / 10 ** e
        return f"${m:.1f}\\times10^{{{e}}}$"
    return f"{p:.3f}"


# ------------------------------------------------------------------ extra numbers
def extra_numbers():
    d = pd.read_parquet(RESULTS_DIR / "khat_fidelity_full.parquet")
    out = {}
    # dataset-level table (one row per original dataset)
    ds = d.groupby(SCEN + ["rep"]).agg(
        khR_km=("khat_real_km_full", "first"), khR_hc=("khat_real_hc_full", "first"),
        khR_km_c=("khat_real_km_capped", "first"), khR_hc_c=("khat_real_hc_capped", "first")
    ).reset_index()
    lo = ds[ds.sep <= 2]
    out["sep_le2_share_khatR2_by_rho_full"] = {
        f"rho={r:g}": {a: float((g[f"khR_{a}"] == 2).mean()) for a in ("km", "hc")}
        for r, g in lo.groupby("rho")}
    out["sep_le2_share_khatR2_by_rho_capped"] = {
        f"rho={r:g}": {a: float((g[f"khR_{a}_c"] == 2).mean()) for a in ("km", "hc")}
        for r, g in lo.groupby("rho")}
    # AG at sep >= 6 by rho (full range)
    hi = d[d.sep >= 6]
    out["sep_ge6_AG_by_rho_full"] = {
        f"rho={r:g}": {a: float((g[f"khat_syn_{a}_full"] == g[f"khat_real_{a}_full"]).mean())
                       for a in ("km", "hc")} for r, g in hi.groupby("rho")}
    # silhouette at planted k: mean difference synthetic - original by sep
    sil = {}
    for a in ("km", "hc"):
        diff = d[f"sil_syn_{a}"] - d[f"sil_real_{a}"]
        sil[a] = {"by_sep": {f"{s:g}": float(v) for s, v in diff.groupby(d.sep).mean().items()},
                  "real_mean": float(d[f"sil_real_{a}"].mean()),
                  "syn_mean": float(d[f"sil_syn_{a}"].mean())}
        sil[a]["max_abs_by_sep"] = float(max(abs(v) for v in sil[a]["by_sep"].values()))
    out["silhouette"] = sil
    # independent original pairs with equal k-hat_R, by distribution and by sep (both ranges)
    pairs = {}
    for rng, suf in (("full", ""), ("capped", "_c")):
        rows = []
        for key, g in ds.groupby(SCEN):
            rec = dict(zip(SCEN, key))
            for a in ("km", "hc"):
                v = g[f"khR_{a}{suf}"].values
                pr = [v[i] == v[j] for i, j in itertools.combinations(range(len(v)), 2)]
                rec[a] = float(np.mean(pr))
            rows.append(rec)
        pr = pd.DataFrame(rows)
        pairs[rng] = {
            "overall": {a: float(pr[a].mean()) for a in ("km", "hc")},
            "by_sep": {f"sep={s:g}": {a: float(g[a].mean()) for a in ("km", "hc")}
                       for s, g in pr.groupby("sep")},
            "by_distribution": {f"distribution={s}": {a: float(g[a].mean()) for a in ("km", "hc")}
                                for s, g in pr.groupby("distribution")},
        }
    out["independent_pairs"] = pairs
    # fixed-range recovery heatmap (share k-hat_S == k by k x sep)
    out["rr_k_x_sep_full"] = {
        f"k={k},sep={s:g}": {a: float((g[f"khat_syn_{a}_full"] == g.k).mean()) for a in ("km", "hc")}
        for (k, s), g in d.groupby(["k", "sep"])}
    # m = 100 run versus m = 1000: largest absolute difference in any marginal mean of
    # Table 2 (RR, AG, both ranges) and of the overall/marginal geometric means
    b = pd.read_parquet(RESULTS_DIR / "khat_fidelity_full_m100.parquet")
    cols = []
    for dd in (d, b):
        for rng in ("full", "capped"):
            for a in ("km", "hc"):
                dd[f"rr_{a}_{rng}"] = (dd[f"khat_syn_{a}_{rng}"] == dd.k).astype(float)
                dd[f"ag_{a}_{rng}"] = (dd[f"khat_syn_{a}_{rng}"] == dd[f"khat_real_{a}_{rng}"]).astype(float)
    cols = [c for c in d.columns if c.startswith(("rr_", "ag_"))] + \
        [f"{m}_{a}" for m in ("mcd", "mvd", "dgini") for a in ("km", "hc")]
    diffs = [float((d[cols].mean() - b[cols].mean()).abs().max())]
    for fac in ["sep", "k", "p", "rho", "distribution"]:
        diffs.append(float((d.groupby(fac)[cols].mean() - b.groupby(fac)[cols].mean()).abs().max().max()))
    out["m100_vs_m1000_max_abs_diff_marginal_means"] = max(diffs)
    out["m100_rows"] = int(len(b))
    out["n_pairs"] = int(len(d))
    return out


# ------------------------------------------------------------------ table fragments
def tab_factors():
    """Table 2: RR and AG by factor, fixed range {2..8}."""
    bf = FR["full"]["by_factor"]
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r" & & \multicolumn{2}{c}{Planted $k$ (RR)} & \multicolumn{2}{c}{Original $\hat{k}_R$ (AG)} \\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}",
             r"Factor & Level & $k$-means & Ward & $k$-means & Ward \\", r"\midrule"]
    blocks = [("Separation $\\sigma$", "sep", [("0.1", "sep=0.1", "$0.1$\\textsuperscript{a}"),
                                               ("2", "sep=2", "$2$\\textsuperscript{a}"),
                                               ("6", "sep=6", "$6$"), ("10", "sep=10", "$10$")]),
              ("Number of groups $k$", "k", [(None, "k=2", "$2$"), (None, "k=3", "$3$"), (None, "k=4", "$4$")]),
              ("Dimensionality $p$", "p", [(None, "p=2", "$2$"), (None, "p=5", "$5$"), (None, "p=10", "$10$")]),
              ("Correlation $\\rho$", "rho", [(None, "rho=0", "$0$"), (None, "rho=0.4", "$0.4$")]),
              ("Distribution $F$", "distribution", [(None, "distribution=normal", "Normal"),
                                                   (None, "distribution=gamma", "Gamma")])]
    for bi, (name, fac, levels) in enumerate(blocks):
        for li, (_, key, lab) in enumerate(levels):
            v = bf[fac][key]
            first = name if li == 0 else ""
            lines.append(f"{first} & {lab} & {f3(v['rr_km'])} & {f3(v['rr_hc'])} & "
                         f"{f3(v['ag_km'])} & {f3(v['ag_hc'])} \\\\")
        if bi < len(blocks) - 1:
            lines.append(r"\addlinespace")
    o = FR["full"]["overall"]
    w = FR["full"]["wilcoxon_km_vs_hc_144_scenarios"]
    lines += [r"\midrule",
              f"Overall & & {f3(o['rr_km'])} & {f3(o['rr_hc'])} & {f3(o['ag_km'])} & {f3(o['ag_hc'])} \\\\",
              f"Wilcoxon $p$ & & \\multicolumn{{2}}{{c}}{{{pfmt(w['RR']['p'])}}} & "
              f"\\multicolumn{{2}}{{c}}{{{pfmt(w['AG']['p'])}}} \\\\",
              r"\bottomrule", r"\end{tabular}"]
    (TAB / "tab_factors.tex").write_text("\n".join(lines) + "\n")


def tab_null(rng="full", fname="tab_null.tex"):
    """Table 3 / S-table: AG, bootstrap null AG0 and excess, by sep and distribution."""
    c = BS["item1_count_null"][rng]
    lines = [r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & \multicolumn{3}{c}{$k$-means} & \multicolumn{3}{c}{Ward} \\",
             r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
             r"Stratum & Level & AG & AG$_0$ & Excess & AG & AG$_0$ & Excess \\", r"\midrule"]

    def row(first, lab, v):
        return (f"{first} & {lab} & {f3(v['ag_km'])} & {f3(v['ag0_km'])} & {signed(v['ex_km'])} & "
                f"{f3(v['ag_hc'])} & {f3(v['ag0_hc'])} & {signed(v['ex_hc'])} \\\\")
    for i, s in enumerate(SEPS):
        lines.append(row("Separation $\\sigma$" if i == 0 else "", f"${s:g}$", c["by_sep"][f"sep={s:g}"]))
    lines.append(r"\addlinespace")
    for i, (dist, lab) in enumerate([("normal", "Normal"), ("gamma", "Gamma")]):
        lines.append(row("Distribution $F$" if i == 0 else "", lab, c["by_distribution"][f"distribution={dist}"]))
    lines.append(r"\addlinespace")
    for dist, lab in [("normal", "Normal"), ("gamma", "Gamma")]:
        for i, s in enumerate(SEPS):
            v = c["by_sep_x_distribution"][f"sep={s:g},distribution={dist}"]
            lines.append(row(f"{lab}, $\\sigma$" if i == 0 else "", f"${s:g}$", v))
        lines.append(r"\addlinespace")
    lines[-1] = r"\midrule"
    lines.append(row("Overall", "", c["overall"]))
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / fname).write_text("\n".join(lines) + "\n")


def tab_floor_overall():
    """Table 4: observed, bootstrap floor and excess for all geometric metrics (overall)."""
    g2 = BS["item2_geometric_floor"]
    g3 = BS["item3_scale_free"]
    w2 = g2["wilcoxon_144_scenario_means"]
    w3 = g3["wilcoxon_144_scenario_means"]
    rows = [("MCD", "mcd", g2, w2), ("MVD", "mvd", g2, w2), ("$\\Delta G$", "dgini", g2, w2),
            ("MCD$_{\\mathrm{sd}}$", "mcd_sd", g3, w3), ("RVD", "rvd", g3, w3)]
    lines = [r"\begin{tabular}{lrrrrrrr}", r"\toprule",
             r" & \multicolumn{3}{c}{$k$-means} & \multicolumn{3}{c}{Ward} & Excess \\",
             r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
             r"Metric & Observed & Floor & Excess & Observed & Floor & Excess & $p$ \\", r"\midrule"]
    for i, (lab, m, g, w) in enumerate(rows):
        o = g["overall"]
        lines.append(f"{lab} & {f3(o[f'{m}_km'])} & {f3(o[f'floor_{m}_km'])} & {f3(o[f'ex_{m}_km'])} & "
                     f"{f3(o[f'{m}_hc'])} & {f3(o[f'floor_{m}_hc'])} & {f3(o[f'ex_{m}_hc'])} & "
                     f"{pfmt(w[m]['excess_km_vs_excess_hc']['p'])} \\\\")
        if i == 2:
            lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "tab_floor.tex").write_text("\n".join(lines) + "\n")


def tab_floor_strata():
    """Supplementary: floor/observed/excess by sep, distribution and p for every metric."""
    g2 = BS["item2_geometric_floor"]
    g3 = BS["item3_scale_free"]
    groups = {"tabS_floor.tex": [("MCD", "mcd", g2), ("MVD", "mvd", g2), ("$\\Delta G$", "dgini", g2)],
              "tabS_scalefree.tex": [("MVD$/p$", "mvd_pc", g3), ("MCD$_{\\mathrm{sd}}$", "mcd_sd", g3),
                                     ("RVD", "rvd", g3)]}
    strata = ([("$\\sigma=" + f"{s:g}$", "by_sep", f"sep={s:g}") for s in SEPS] +
              [("Normal", "by_distribution", "distribution=normal"),
               ("Gamma", "by_distribution", "distribution=gamma")] +
              [(f"$p={p}$", "by_p", f"p={p}") for p in (2, 5, 10)] +
              [("Overall", None, None)])
    for fname, mets in groups.items():
        _floor_block(fname, mets, strata)


def _floor_block(fname, mets, strata):
    lines = [r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & \multicolumn{3}{c}{$k$-means} & \multicolumn{3}{c}{Ward} \\",
             r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
             r"Metric & Stratum & Obs. & Floor & Excess & Obs. & Floor & Excess \\", r"\midrule"]
    for mi, (lab, m, g) in enumerate(mets):
        for si, (slab, grp, key) in enumerate(strata):
            o = g["overall"] if grp is None else g[grp][key]
            lines.append(f"{lab if si == 0 else ''} & {slab} & {f3(o[f'{m}_km'])} & {f3(o[f'floor_{m}_km'])} & "
                         f"{f3(o[f'ex_{m}_km'])} & {f3(o[f'{m}_hc'])} & {f3(o[f'floor_{m}_hc'])} & "
                         f"{f3(o[f'ex_{m}_hc'])} \\\\")
        if mi < len(mets) - 1:
            lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / fname).write_text("\n".join(lines) + "\n")


def tab_range():
    """Supplementary: capped-range sensitivity (RR, AG by sep; both ranges; tie-corrected Wilcoxon)."""
    lines = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
             r" & \multicolumn{4}{c}{$\hat{k} \in \{2,\dots,8\}$ (main text)} & "
             r"\multicolumn{4}{c}{$\hat{k} \in \{2,\dots,\min(k+3,8)\}$} \\",
             r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
             r" & \multicolumn{2}{c}{RR} & \multicolumn{2}{c}{AG} & \multicolumn{2}{c}{RR} & \multicolumn{2}{c}{AG} \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}",
             r"Stratum & $k$-m. & Ward & $k$-m. & Ward & $k$-m. & Ward & $k$-m. & Ward \\", r"\midrule"]
    keys = [(f"$\\sigma={s:g}$", "sep", f"sep={s:g}") for s in SEPS] + \
           [("Normal", "distribution", "distribution=normal"), ("Gamma", "distribution", "distribution=gamma")]
    for i, (lab, fac, key) in enumerate(keys):
        a = FR["full"]["by_factor"][fac][key]
        b = FR["capped"]["by_factor"][fac][key]
        lines.append(f"{lab} & {f3(a['rr_km'])} & {f3(a['rr_hc'])} & {f3(a['ag_km'])} & {f3(a['ag_hc'])} & "
                     f"{f3(b['rr_km'])} & {f3(b['rr_hc'])} & {f3(b['ag_km'])} & {f3(b['ag_hc'])} \\\\")
        if i == 3:
            lines.append(r"\addlinespace")
    a, b = FR["full"]["overall"], FR["capped"]["overall"]
    lines += [r"\midrule",
              f"Overall & {f3(a['rr_km'])} & {f3(a['rr_hc'])} & {f3(a['ag_km'])} & {f3(a['ag_hc'])} & "
              f"{f3(b['rr_km'])} & {f3(b['rr_hc'])} & {f3(b['ag_km'])} & {f3(b['ag_hc'])} \\\\"]
    wa, wb = FR["full"]["wilcoxon_km_vs_hc_144_scenarios"], FR["capped"]["wilcoxon_km_vs_hc_144_scenarios"]
    cells = []
    for w in (wa, wb):
        for m in ("RR", "AG"):
            cells.append(f"\\multicolumn{{2}}{{c}}{{{w[m]['W']:g}}}")
    lines.append("Wilcoxon $W$ & " + " & ".join(cells) + r" \\")
    cells = []
    for w in (wa, wb):
        for m in ("RR", "AG"):
            cells.append(f"\\multicolumn{{2}}{{c}}{{{pfmt(w[m]['p'])}}}")
    lines.append("Wilcoxon $p$ & " + " & ".join(cells) + r" \\")
    # bootstrap null row (overall) for both ranges
    cn = BS["item1_count_null"]
    lines.append(r"\addlinespace")
    lines.append(f"AG$_0$ (bootstrap) & & & {f3(cn['full']['overall']['ag0_km'])} & "
                 f"{f3(cn['full']['overall']['ag0_hc'])} & & & {f3(cn['capped']['overall']['ag0_km'])} & "
                 f"{f3(cn['capped']['overall']['ag0_hc'])} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "tabS_range.tex").write_text("\n".join(lines) + "\n")


def tab_collapse():
    """Supplementary: collapse cells, both algorithms, both ranges."""
    c = BS["item4_collapse"]
    lines = [r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & Datasets & Collapse & Evaluations & \multicolumn{2}{c}{AG} & $\hat{k}_R=2$, \\",
             r"\cmidrule(lr){6-7}",
             r"Range & Algorithm & $\hat{k}_R=2$ & cells & in cells & inside & outside & $p{=}10$, $\sigma{\le}2$ \\",
             r"\midrule"]
    for ri, (rng, rlab) in enumerate([("full", "fixed"), ("capped", "capped")]):
        for ai, (a, alab) in enumerate([("km", "$k$-means"), ("hc", "Ward")]):
            v = c[rng][a]["k>=3"]
            vall = c[rng][a]["all_k"]
            lines.append(f"{rlab if ai == 0 else ''} & {alab} & {f3(v['share_datasets_khatR2'])} & "
                         f"{v['n_scenarios_collapse_cell']} & {f3(v['share_of_720000_evals_in_collapse_cells'])} & "
                         f"{f3(v['AG_inside_collapse_cells'])} & {f3(v['AG_outside_collapse_cells'])} & "
                         f"{f3(vall['p10_sep_le2_khatR2'])} \\\\")
        if ri == 0:
            lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "tabS_collapse.tex").write_text("\n".join(lines) + "\n")


def tab_baseline(extra):
    """Supplementary: AG, bootstrap null AG0 and the independent-pairs baseline (secondary)."""
    cn = BS["item1_count_null"]["full"]
    pr = extra["independent_pairs"]["full"]
    lines = [r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & \multicolumn{3}{c}{$k$-means} & \multicolumn{3}{c}{Ward} \\",
             r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}",
             r"Stratum & Level & AG & AG$_0$ & Pairs & AG & AG$_0$ & Pairs \\", r"\midrule"]
    keys = [("Separation $\\sigma$" if i == 0 else "", f"${s:g}$", "by_sep", f"sep={s:g}") for i, s in enumerate(SEPS)] + \
           [("Distribution $F$", "Normal", "by_distribution", "distribution=normal"),
            ("", "Gamma", "by_distribution", "distribution=gamma")]
    for i, (first, lab, grp, key) in enumerate(keys):
        v = cn[grp][key]
        q = pr[grp][key]
        lines.append(f"{first} & {lab} & {f3(v['ag_km'])} & {f3(v['ag0_km'])} & {f3(q['km'])} & "
                     f"{f3(v['ag_hc'])} & {f3(v['ag0_hc'])} & {f3(q['hc'])} \\\\")
        if i == 3:
            lines.append(r"\addlinespace")
    v, q = cn["overall"], pr["overall"]
    lines += [r"\midrule",
              f"Overall & & {f3(v['ag_km'])} & {f3(v['ag0_km'])} & {f3(q['km'])} & "
              f"{f3(v['ag_hc'])} & {f3(v['ag0_hc'])} & {f3(q['hc'])} \\\\",
              r"\bottomrule", r"\end{tabular}"]
    (TAB / "tabS_baseline.tex").write_text("\n".join(lines) + "\n")


def main():
    extra = extra_numbers()
    # consistency checks against the stored summaries
    fp = FR["full"]["independent_original_pairs_same_khat"]["overall"]
    assert abs(extra["independent_pairs"]["full"]["overall"]["km"] - fp["pair_km"]) < 1e-12
    assert abs(extra["independent_pairs"]["full"]["overall"]["hc"] - fp["pair_hc"]) < 1e-12
    cp = FR["capped"]["independent_original_pairs_same_khat"]["overall"]
    assert abs(extra["independent_pairs"]["capped"]["overall"]["km"] - cp["pair_km"]) < 1e-12
    for key, v in FR["full"]["by_k_x_sep"].items():
        assert abs(extra["rr_k_x_sep_full"][key]["km"] - v["rr_km"]) < 1e-12, key
    json.dump(extra, open(RESULTS_DIR / "v5_extra_numbers.json", "w"), indent=1)
    tab_factors()
    tab_null("full", "tab_null.tex")
    tab_null("capped", "tabS_null_capped.tex")
    tab_floor_overall()
    tab_floor_strata()
    tab_range()
    tab_collapse()
    tab_baseline(extra)
    print(json.dumps(extra, indent=1))


if __name__ == "__main__":
    main()
