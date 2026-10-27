"""Fig. 7 (case study): original vs one CART synthetic draw, and distribution of k-hat.

(a) original diabetes data, glucose area vs SSPG, by clinical class;
(b) synthetic draw 1 (single colour: its class column is a CART prediction, as in Figs 1-2);
(c) silhouette-selected k-hat over the m = 1000 synthetic draws (filled) and the
    B = 1000 bootstrap resamples (open).
"""
import os
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from synthclust.make_figures import style, check_fonts, WIDTH, ALGOS, FS_SMALL

IN = os.path.join("results", "case_study")
OUT = os.path.join("manuscript", "figures")
DRAW = 1
od = pd.read_csv(os.path.join(IN, "diabetes_original.csv"))
sd = pd.read_csv(os.path.join(IN, "diabetes_synthetic.csv"))
sd = sd[sd.syn == DRAW]
d = pd.read_csv(os.path.join(IN, "diabetes_draws.csv"))
d["kc"] = d.khat.clip(upper=4)
style()
fig = plt.figure(figsize=(WIDTH, 2.05))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.95], wspace=0.12)
a1 = fig.add_subplot(gs[0]); a2 = fig.add_subplot(gs[1], sharex=a1, sharey=a1); a3 = fig.add_subplot(gs[2])
CL = [("normal", "Normal", "o", "#BDBDBD"), ("chemical", "Chemical", "^", "#6F6F6F"), ("overt", "Overt", "s", "#111111")]
for g, lab, mk, col in CL:
    s = od[od.group == g]
    a1.scatter(s.glucose, s.sspg, s=7, marker=mk, c=col, lw=0, label=lab)
a2.scatter(sd.glucose, sd.sspg, s=7, marker="o", c="#3A3A3A", lw=0, alpha=0.8)
a1.set_ylabel("SSPG (mg/100 ml)")
for ax in (a1, a2):
    ax.set_xlabel("Glucose area")
    ax.margins(0.05)
plt.setp(a2.get_yticklabels(), visible=False)
a1.legend(loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=3, frameon=False, handletextpad=0.05,
           columnspacing=0.8, borderaxespad=0.1, markerscale=1.2)
w = 0.19
for j, (al, col, lab) in enumerate(ALGOS):
    for i, (kind, fill) in enumerate([("syn", True), ("boot", False)]):
        s = d[(d.algo == al) & (d.kind == kind)].kc.value_counts(normalize=True).reindex([2, 3, 4], fill_value=0)
        x = np.arange(3) + (j * 2 + i - 1.5) * w
        a3.bar(x, s.values, w * 0.92, color=col if fill else "white", edgecolor=col, lw=0.8)
a3.set_xticks(range(3), ["2", "3", r"$\geq 4$"])
a3.set_xlabel(r"Selected $\hat k$")
a3.set_ylabel("Share")
a3.yaxis.set_label_position("right"); a3.yaxis.tick_right()
a3.set_ylim(0, 0.8); a3.margins(x=0.04)
for ax, L in [(a1, "(a)"), (a2, "(b)"), (a3, "(c)")]:
    ax.text(0.03, 0.97, L, transform=ax.transAxes, fontsize=FS_SMALL, fontweight="bold", ha="left", va="top")
    for s_ in ("top",):
        ax.spines[s_].set_visible(False)
a1.spines["right"].set_visible(False); a2.spines["right"].set_visible(False); a3.spines["left"].set_visible(False)
h = [Patch(fc=c, ec=c, label=l) for _, c, l in ALGOS] + \
    [Patch(fc="k", ec="k", label="CART synthetic"), Patch(fc="white", ec="k", label="bootstrap")]
fig.legend(handles=h, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.01),
           handlelength=1.0, columnspacing=0.9)
fig.subplots_adjust(bottom=0.34)
fig.savefig(os.path.join(OUT, "fig_diabetes.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(OUT, "fig_diabetes.png"), dpi=400, bbox_inches="tight")
check_fonts(fig, "fig_diabetes")
r = fig.canvas.get_renderer()
T = [(t, t.get_window_extent(r)) for t in fig.findobj(matplotlib.text.Text) if t.get_visible() and t.get_text().strip()]
ov = [(a.get_text(), b.get_text()) for i, (a, ba) in enumerate(T) for b, bb in T[i + 1:] if ba.overlaps(bb)]
print("overlaps", ov)
