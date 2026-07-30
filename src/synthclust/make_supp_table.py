"""Build the supplementary k-hat agreement table (Table S1) from the fidelity results.

Rows are k-hat recovered from the original data, columns k-hat from the synthetic
data, cells percentages of all comparisons at that separation. Estimates of five
or more groups are pooled for display, but the agreement column is computed on
unpooled values.

CONV selects the k_max convention: "full" (fixed 2..8, symmetric for both data
sources -- what the table uses) or "capped" (min(k+3, 8), the per-scenario rule
the main-text recovery rates use). See REVISION_NOTES.md section 5.6.
"""
import pandas as pd

from synthclust.paths import FIDELITY_RESULTS, REPO, require

CONV = "full"
SEPS = [0.1, 2, 6, 10]


def build(conv: str = CONV) -> str:
    d = pd.read_parquet(require(FIDELITY_RESULTS, "run: uv run recompute-metrics"))
    out = [r"\begin{tabular}{llrrrrr}", r"\toprule",
           r" & & \multicolumn{4}{c}{$\hat{k}$ recovered from synthetic data (\%)} & Exact \\",
           r"\cmidrule(lr){3-6}",
           r"$\sigma$ & $\hat{k}$ (original) & 2 & 3 & 4 & $\geq 5$ & agreement \\",
           r"\midrule"]
    for algo, label in [("km", r"\textit{$k$-means}"), ("hc", r"\textit{Ward}")]:
        out.append(rf"\multicolumn{{7}}{{l}}{{{label}}} \\")
        for sep in SEPS:
            s = d[d.sep == sep]
            R, S = s[f"khat_real_{algo}_{conv}"], s[f"khat_syn_{algo}_{conv}"]
            agree, n = (R == S).mean(), len(s)
            Rp, Sp = R.clip(upper=5), S.clip(upper=5)
            for i, rl in enumerate([2, 3, 4, 5]):
                cells = [f"{((Rp == rl) & (Sp == cl)).sum() / n * 100:.1f}"
                         for cl in [2, 3, 4, 5]]
                rlab = r"$\geq 5$" if rl == 5 else str(rl)
                first = rf"\multirow{{4}}{{*}}{{{sep:g}}}" if i == 0 else ""
                ag = rf"\multirow{{4}}{{*}}{{${agree * 100:.1f}\%$}}" if i == 0 else ""
                out.append(f"{first} & {rlab} & " + " & ".join(cells) + f" & {ag} \\\\")
            if not (algo == "hc" and sep == 10):
                out.append(r"\addlinespace")
        if algo == "km":
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


def main():
    dest = REPO / "manuscript" / "supp_table.tex"
    dest.write_text(build())
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
