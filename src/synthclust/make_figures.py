"""Regenerate the manuscript figures addressing the reviewers' comments.

p11 Jordi: (2) explain each panel of Figs 1-2; (3) match the red/blue <-> top/bottom
           correspondence between real and synthetic panels.
p15 Jordi: add a dispersion measure to the points of Fig 5.
p13 Jordi: Figs 3 and 4 are near-duplicates -> keep 4, move 3 to supplementary.
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from scipy.optimize import linear_sum_assignment

from synthclust.paths import (ORIGINAL_DIR, SYNTHETIC_DIR, CLUSTERING_RESULTS,
                              FIDELITY_RESULTS, FIGURES_DIR, require)
OUT = str(FIGURES_DIR)
os.makedirs(OUT, exist_ok=True)

BLUE, RED = "#3B6FB6", "#C0392B"
GREY = "#8A8A8A"


def align_labels(Xref, lab_ref, X, lab, k):
    """Relabel `lab` so cluster j sits where cluster j of the reference sits.

    Comment (3): without this the colours are assigned by arbitrary label order,
    so the same spatial cluster can be red in the real panel and blue in the
    synthetic one. Matching on centroid position makes the two rows comparable.
    """
    cr = np.array([Xref[lab_ref == j].mean(axis=0) for j in range(k)])
    cs = np.array([X[lab == j].mean(axis=0) for j in range(k)])
    cost = np.linalg.norm(cr[:, None, :] - cs[None, :, :], axis=2)
    ri, ci = linear_sum_assignment(cost)
    remap = {int(c): int(r) for r, c in zip(ri, ci)}
    return np.array([remap[int(v)] for v in lab])


def orient(X, lab, k):
    """Make cluster 0 the upper one, so colour tracks vertical position."""
    ymean = [X[lab == j][:, 1].mean() for j in range(k)]
    order = np.argsort(ymean)[::-1]
    remap = {int(o): i for i, o in enumerate(order)}
    return np.array([remap[int(v)] for v in lab])


def panel_grid(dist, fname, title):
    k, sep, p, rho = 2, 2, 2, 0.0
    tag = f"N1000_p{p}_k{k}_rho{rho:g}_sep{sep:g}_{dist}"
    od = pd.read_parquet(str(ORIGINAL_DIR / f"OD_{tag}.parquet"))
    sd = pd.read_parquet(str(SYNTHETIC_DIR / f"SD_cart_{tag}_syn1.parquet"))
    feats = [c for c in od.columns if c.startswith("X")]
    rep = 1
    Rr = od[od.rep == rep]
    Sr = sd[sd.rep == rep]
    sc = StandardScaler().fit(Rr[feats].values)
    Xr = sc.transform(Rr[feats].values)
    Xs = sc.transform(Sr[feats].values)
    true_r = Rr["group"].astype(int).values - 1
    true_s = Sr["group"].astype(int).values - 1

    true_r = orient(Xr, true_r, k)
    km_r = orient(Xr, KMeans(k, n_init=10, random_state=42).fit_predict(Xr), k)
    hc_r = orient(Xr, AgglomerativeClustering(k).fit_predict(Xr), k)
    true_s = align_labels(Xr, true_r, Xs, true_s, k)
    km_s = align_labels(Xr, km_r, Xs, KMeans(k, n_init=10, random_state=42).fit_predict(Xs), k)
    hc_s = align_labels(Xr, hc_r, Xs, AgglomerativeClustering(k).fit_predict(Xs), k)

    cmap = np.array([RED, BLUE])
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 4.8), sharex=True, sharey=True)
    cols = [("True groups", true_r, true_s),
            ("$k$-means partition", km_r, km_s),
            ("Ward partition", hc_r, hc_s)]
    for j, (cname, lr, ls) in enumerate(cols):
        for i, (X, lab) in enumerate([(Xr, lr), (Xs, ls)]):
            ax = axes[i, j]
            # Bottom-left panel (synthetic "true groups") is drawn in a single
            # neutral colour on purpose. The synthetic `group` column is a CART
            # prediction of the label from the synthetic features, not a planted
            # ground truth, so there is no bijective correspondence with the
            # original groups; colouring it would present a model output as
            # ground truth (reviewer request, Jordi p9).
            if i == 1 and j == 0:
                colours = "#1A1A1A"
            else:
                colours = cmap[lab]
            ax.scatter(X[:, 0], X[:, 1], c=colours, s=3.2, lw=0, alpha=0.75, rasterized=True)
            ax.set_xticks([]); ax.set_yticks([])
            ax.margins(0.05)
            if i == 0:
                ax.set_title(cname, fontsize=8)
    axes[0, 0].set_ylabel("Original", fontsize=8)
    axes[1, 0].set_ylabel("Synthetic", fontsize=8)
    for ax in axes.ravel():
        for s in ax.spines.values():
            s.set_linewidth(0.6); s.set_color("#666666")
    fig.suptitle(title, fontsize=9, y=0.98)
    fig.supxlabel("$X_1$ (standardised)", fontsize=7.5, y=0.03)
    fig.supylabel("$X_2$ (standardised)", fontsize=7.5, x=0.02)
    fig.tight_layout(rect=[0.03, 0.03, 1, 0.96])
    fig.savefig(f"{OUT}/{fname}", dpi=400, bbox_inches="tight")
    plt.close(fig)
    return fname


def fig_fidelity_bands(d):
    """Fig 5 with dispersion (comment p15): mean +/- 95% CI over scenario means."""
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    for ax, (metric, lbl) in zip(axes, [("mcd", "Mean centroid distance"),
                                        ("mvd", "Mean variance difference")]):
        for algo, col, name in [("km", BLUE, "$k$-means"), ("hc", RED, "Ward")]:
            g = d.groupby(["sep", "p", "k", "rho", "distribution"])[f"{metric}_{algo}"].mean().reset_index()
            agg = g.groupby("sep")[f"{metric}_{algo}"].agg(["mean", "std", "count"])
            ci = 1.96 * agg["std"] / np.sqrt(agg["count"])
            x = agg.index.values
            ax.plot(x, agg["mean"], "-o", color=col, ms=4, lw=1.4, label=name, zorder=3)
            ax.fill_between(x, agg["mean"] - ci, agg["mean"] + ci, color=col, alpha=0.18, lw=0, zorder=2)
        ax.set_xlabel("Cluster separation $\\sigma$", fontsize=8)
        ax.set_ylabel(lbl, fontsize=8)
        ax.set_xticks([0.1, 2, 6, 10])
        ax.tick_params(labelsize=7)
        ax.margins(0.06)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].legend(frameon=False, fontsize=7.5, loc="upper right")
    axes[0].text(0.02, 0.02, "lower = better", transform=axes[0].transAxes,
                 fontsize=6.5, color=GREY, ha="left")
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig_fidelity.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/fig_fidelity.png", dpi=400, bbox_inches="tight")
    plt.close(fig)


def fig_recovery_curves(d):
    """Cluster-count recovery under both reference conventions.

    Reviewer request (Jordi and Dani, 2026-07-30): report both references in the
    number-of-clusters section only.

      (a) v1, agreement with the planted k of the simulation.
      (b) v2, agreement with the k a clustering algorithm recovers from the
          ORIGINAL data.

    Both panels are computed from the fidelity table so the two conventions rest
    on identical rows. v1 here reproduces `success_*` in clustering_results.parquet
    to within 0.002; that file is not used, to keep the panels strictly paired.
    """
    n_pairs = len(d)
    conv = [("khat_syn_{a}_capped", "k",
             "(a) versus the planted number of groups"),
            ("khat_syn_{a}_capped", "khat_real_{a}_capped",
             "(b) versus the number recovered from the original data")]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0), sharey=True)
    for ax, (syn_t, ref_t, title) in zip(axes, conv):
        for kk, ls in zip([2, 3, 4], ["-", "--", ":"]):
            sub = d[d.k == kk]
            for a, col in [("km", BLUE), ("hc", RED)]:
                ref = sub[ref_t.format(a=a)] if "{a}" in ref_t else sub[ref_t]
                hit = (sub[syn_t.format(a=a)] == ref).astype(float)
                g = hit.groupby(sub["sep"]).mean()
                ax.plot(g.index, g.values, ls, color=col, lw=1.3, marker="o", ms=3)
        ax.axvspan(0, 2, color=GREY, alpha=0.10, lw=0, zorder=0)
        ax.set_xlabel("Cluster separation $\\sigma$", fontsize=8)
        ax.set_xticks([0.1, 2, 6, 10])
        ax.set_title(title, fontsize=8, loc="left")
        ax.tick_params(labelsize=7)
        ax.text(1.0, 1.10, "clusters overlap", fontsize=6.5, color=GREY,
                ha="center", va="center")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Cluster-count agreement", fontsize=8)
    axes[0].set_ylim(-0.02, 1.18)

    from matplotlib.lines import Line2D
    h = [Line2D([], [], color=BLUE, lw=1.3, label="$k$-means"),
         Line2D([], [], color=RED, lw=1.3, label="Ward"),
         Line2D([], [], color=GREY, lw=1.3, ls="-", label="$k=2$"),
         Line2D([], [], color=GREY, lw=1.3, ls="--", label="$k=3$"),
         Line2D([], [], color=GREY, lw=1.3, ls=":", label="$k=4$")]
    axes[1].legend(handles=h, frameon=False, fontsize=6.8, loc="lower right",
                   ncol=2)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig_recovery.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/fig_recovery.png", dpi=400, bbox_inches="tight")
    plt.close(fig)
    return n_pairs


def fig_heatmap_supp(df):
    """Former Fig 3 -> supplementary (comment p13)."""
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.6))
    for ax, (algo, name) in zip(axes, [("kmeans", "$k$-means"), ("hc", "Ward")]):
        piv = df.groupby(["k", "sep"])[f"success_{algo}"].mean().unstack()
        im = ax.imshow(piv.values, cmap="viridis", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(piv.columns)), [f"{c:g}" for c in piv.columns], fontsize=7)
        ax.set_yticks(range(len(piv.index)), piv.index, fontsize=7)
        ax.set_xlabel("Separation $\\sigma$", fontsize=8)
        ax.set_title(name, fontsize=8)
        for a in range(piv.shape[0]):
            for b in range(piv.shape[1]):
                v = piv.values[a, b]
                ax.text(b, a, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                        color="white" if v < 0.55 else "black")
    axes[0].set_ylabel("True cluster count $k$", fontsize=8)
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label("Recovery rate", fontsize=7.5); cb.ax.tick_params(labelsize=6.5)
    fig.savefig(f"{OUT}/figS_heatmap.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/figS_heatmap.png", dpi=400, bbox_inches="tight")
    plt.close(fig)


def fig_distribution(df):
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for dist, ls in [("normal", "-"), ("gamma", "--")]:
        for algo, col, name in [("kmeans", BLUE, "$k$-means"), ("hc", RED, "Ward")]:
            g = df[df.distribution == dist].groupby("sep")[f"success_{algo}"].mean()
            ax.plot(g.index, g.values, ls, color=col, lw=1.3, marker="o", ms=3)
    ax.set_xlabel("Cluster separation $\\sigma$", fontsize=8)
    ax.set_ylabel("Cluster-count recovery rate", fontsize=8)
    ax.set_xticks([0.1, 2, 6, 10]); ax.tick_params(labelsize=7)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], color=BLUE, lw=1.3, label="$k$-means"),
         Line2D([], [], color=RED, lw=1.3, label="Ward"),
         Line2D([], [], color=GREY, lw=1.3, ls="-", label="Normal"),
         Line2D([], [], color=GREY, lw=1.3, ls="--", label="Gamma")]
    ax.legend(handles=h, frameon=False, fontsize=6.8, loc="upper left", ncol=2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig_distribution.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/fig_distribution.png", dpi=400, bbox_inches="tight")
    plt.close(fig)


def fig_gini_mvd(d):
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    ax = axes[0]
    w = 0.35
    for i, (algo, col, name) in enumerate([("km", BLUE, "$k$-means"), ("hc", RED, "Ward")]):
        g = d.groupby(["p"])[f"mvd_{algo}"].agg(["mean", "sem"])
        x = np.arange(len(g)) + (i - 0.5) * w
        ax.bar(x, g["mean"], w, yerr=1.96 * g["sem"], color=col, label=name,
               error_kw=dict(lw=0.8, capsize=2))
    ax.set_xticks(range(3), ["2", "5", "10"], fontsize=7)
    ax.set_xlabel("Dimensionality $p$", fontsize=8)
    ax.set_ylabel("Mean variance difference", fontsize=8)
    ax.legend(frameon=False, fontsize=7.5)
    ax = axes[1]
    for i, (algo, col, name) in enumerate([("km", BLUE, "$k$-means"), ("hc", RED, "Ward")]):
        g = d.groupby(["distribution"])[f"dgini_{algo}"].agg(["mean", "sem"]).reindex(["normal", "gamma"])
        x = np.arange(len(g)) + (i - 0.5) * w
        ax.bar(x, g["mean"], w, yerr=1.96 * g["sem"], color=col, label=name,
               error_kw=dict(lw=0.8, capsize=2))
    ax.set_xticks(range(2), ["Normal", "Gamma"], fontsize=7)
    ax.set_xlabel("Distribution family", fontsize=8)
    ax.set_ylabel("Cluster-balance error $|\\Delta G|$", fontsize=8)
    for a in axes:
        a.tick_params(labelsize=7)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig_balance.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/fig_balance.png", dpi=400, bbox_inches="tight")
    plt.close(fig)


def main():
    plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.7,
                         "xtick.major.width": 0.7, "ytick.major.width": 0.7,
                         "pdf.fonttype": 42, "font.family": "serif"})
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(str(CLUSTERING_RESULTS))
    d = pd.read_parquet(str(FIDELITY_RESULTS))
    panel_grid("normal", "fig_normal.pdf", "Normal (spherical) components")
    panel_grid("normal", "fig_normal.png", "Normal (spherical) components")
    panel_grid("gamma", "fig_gamma.pdf", "Gamma (right-skewed) components")
    panel_grid("gamma", "fig_gamma.png", "Gamma (right-skewed) components")
    n_pairs = fig_recovery_curves(d)   # both conventions, from the fidelity table
    print(f"  fig_recovery: {n_pairs:,} pairs")
    fig_heatmap_supp(df)
    fig_fidelity_bands(d)
    fig_distribution(df)
    fig_gini_mvd(d)
    print("figures written")


if __name__ == "__main__":
    main()
