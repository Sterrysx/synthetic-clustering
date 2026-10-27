"""Supplementary table: replication with n = 50 original datasets and m = 100 draws.

Reads results/bootstrap_summary.json (n = 5, m = 1000; the main article) and
results/n50_m100/bootstrap_summary.json (copied from the separate n = 50 working copy,
docs/RERUN_n50_m100.md). Writes manuscript/tables/tabS_n50.tex.
"""
import json, os
B = {5: json.load(open("results/bootstrap_summary.json")),
     50: json.load(open("results/n50_m100/bootstrap_summary.json"))}
f3 = lambda x: f"{x:.3f}".replace("-", "$-$")
def pv(p):
    if p >= 0.001:
        return f"{p:.3f}"
    m, e = f"{p:.1e}".split("e")
    return f"${m}\\times10^{{{int(e)}}}$"
def cnt(n, grp):
    c = B[n]["item1_count_null"]["full"]
    return c["overall"] if grp == "all" else c["by_distribution"][f"distribution={grp}"]
def wil(n, grp, test):
    return B[n]["item1_count_null"]["full"]["wilcoxon_144_scenario_means"][grp][test]["p"]
def geo(n):
    return B[n]["item2_geometric_floor"]["overall"]
def gwil(n, m):
    return B[n]["item2_geometric_floor"]["wilcoxon_144_scenario_means"][m]["excess_km_vs_excess_hc"]["p"]
def rvd(n):
    return B[n]["item3_scale_free"]["overall"]
def rwil(n):
    return B[n]["item3_scale_free"]["wilcoxon_144_scenario_means"]["rvd"]["excess_km_vs_excess_hc"]["p"]
rows = []
for grp, lab in (("all", "all"), ("gamma", "Gamma"), ("normal", "Normal")):
    rows.append((f"AG ({lab})", lambda n, g=grp: (cnt(n, g)["ag_km"], cnt(n, g)["ag_hc"], wil(n, g, "AG_km_vs_AG_hc"))))
    rows.append((f"AG excess ({lab})",
                 lambda n, g=grp: (cnt(n, g)["ex_km"], cnt(n, g)["ex_hc"], wil(n, g, "excess_km_vs_excess_hc"))))
for m, lab in (("mcd", "MCD"), ("mvd", "MVD"), ("dgini", r"$\Delta G$")):
    rows.append((f"{lab} excess", lambda n, m=m: (geo(n)[f"ex_{m}_km"], geo(n)[f"ex_{m}_hc"], gwil(n, m))))
rows.append(("RVD excess", lambda n: (rvd(n)["ex_rvd_km"], rvd(n)["ex_rvd_hc"], rwil(n))))
L = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
     r" & \multicolumn{3}{c}{$n = 5$, $m = 1000$} & \multicolumn{3}{c}{$n = 50$, $m = 100$} \\",
     r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
     r"Quantity & $k$-means & Ward & $p$ & $k$-means & Ward & $p$ \\", r"\midrule"]
for i, (lab, fn) in enumerate(rows):
    a, b = fn(5), fn(50)
    L.append(f"{lab} & {f3(a[0])} & {f3(a[1])} & {pv(a[2])} & {f3(b[0])} & {f3(b[1])} & {pv(b[2])} \\\\")
    if i in (5,):
        L.append(r"\addlinespace")
L += [r"\bottomrule", r"\end{tabular}"]
open("manuscript/tables/tabS_n50.tex", "w").write("\n".join(L) + "\n")
print("\n".join(L))
