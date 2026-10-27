"""Supplementary table: case study under the six synthesis orders (from diabetes_summary*.json)."""
import json, os
ORD = ["glucose-insulin-sspg", "glucose-sspg-insulin", "insulin-glucose-sspg",
       "insulin-sspg-glucose", "sspg-glucose-insulin", "sspg-insulin-glucose"]
NAME = {"glucose": "G", "insulin": "I", "sspg": "S"}
f3 = lambda x: f"{x:.3f}".replace("-", "$-$")
L = [r"\begin{tabular}{llrrrrrrr}", r"\toprule",
     r"Order & Method & AG & \multicolumn{6}{c}{Excess over the bootstrap null} \\",
     r"\cmidrule(lr){4-9}",
     r" & & & AG & ARI & MCD & MVD & $\Delta G$ & RVD \\", r"\midrule"]
for i, o in enumerate(ORD):
    S = json.load(open(os.path.join("results", "case_study",
                                    "diabetes_summary.json" if i == 0 else f"diabetes_summary_{o}.json")))
    lab = "--".join(NAME[v] for v in o.split("-")) + (" (main text)" if i == 0 else "")
    for j, (a, an) in enumerate((("km", "$k$-means"), ("hc", "Ward"))):
        e = S["algos"][a]
        L.append(f"{lab if j == 0 else ''} & {an} & {f3(e['ag']['syn'])} & " +
                 " & ".join(f3(e[m]["excess"]) for m in ("ag", "ari", "mcd", "mvd", "dgini", "rvd")) + r" \\")
    if i < len(ORD) - 1:
        L.append(r"\addlinespace")
L += [r"\bottomrule", r"\end{tabular}"]
open(os.path.join("manuscript", "tables", "tabS_orders.tex"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
