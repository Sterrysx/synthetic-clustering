"""Table 5 (case study): every number of the diabetes comparison, from diabetes_summary.json."""
import json, os
S = json.load(open(os.path.join("results", "case_study", "diabetes_summary.json")))
A = S["algos"]
f3 = lambda x: f"{x:.3f}".replace("-", "$-$")
rows = [("AG", "ag"), ("ARI", "ari"), ("MCD", "mcd"), ("MVD", "mvd"), (r"$\Delta G$", "dgini"), ("RVD", "rvd")]
L = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
     r" & \multicolumn{3}{c}{$k$-means} & \multicolumn{3}{c}{Ward} \\",
     r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
     r"Metric & Synthetic & Bootstrap & Excess & Synthetic & Bootstrap & Excess \\", r"\midrule"]
for lab, m in rows:
    c = []
    for a in ("km", "hc"):
        e = A[a][m]; c += [f3(e["syn"]), f3(e["boot"]), f3(e["excess"])]
    L.append(f"{lab} & " + " & ".join(c) + r" \\")
    if m == "ari":
        L.append(r"\addlinespace")
L.append(r"\addlinespace")
c = []
for a in ("km", "hc"):
    e = A[a]["ari_clin"]; c += [f3(e["syn"]), f3(e["boot"]), f3(e["excess"])]
L.append(r"ARI (clinical) & " + " & ".join(c) + r" \\")
L += [r"\bottomrule", r"\end{tabular}"]
open(os.path.join("manuscript", "tables", "tab_case.tex"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
