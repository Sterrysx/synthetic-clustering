"""Regenerate the manuscript figures (v5).

v5 changes (co-author decisions on the proposal report, items MI4, MA2-MA4 and
JoC checklist item 16):
  * every figure is drawn at the JoC maximum width of 4.8 in, with all text >= 7 pt;
  * Figs 1-2: axis ticks shown, no title baked into the image (the caption carries
    it), panels lettered (a)-(f); replicate 1 and synthetic draw 1 are shown;
  * Figs 3 and 6: categorical separation axis (the levels 0.1, 2, 6, 10 are not
    equally spaced) and the fixed candidate range {2,...,8};
  * Fig 6: 2 x 2 layout (rows: planted k / original k-hat; columns: Normal / Gamma),
    with the original-data recovery beside RR and the bootstrap null AG0 beside AG;
  * Figs 4-5: bootstrap floor (30 resamples of each original dataset, no CART step)
    drawn beside the observed values; Fig 4 adds the scale-free metrics MCD_sd and RVD;
  * Fig S1 (heatmap) under the fixed range; Fig S2 (strong scaling) redrawn at 4.8 in
    from results/scaling_timings.json.

Bands and error bars are mean +/- 1.96 SE of the scenario-level means. They
describe the spread across the design cells, not sampling uncertainty.
"""
import os
import json
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from scipy.optimize import linear_sum_assignment

from synthclust.paths import (ORIGINAL_DIR, SYNTHETIC_DIR, FIDELITY_RESULTS,
                              RESULTS_DIR, FIGURES_DIR, require)
OUT = str(FIGURES_DIR)
os.makedirs(OUT, exist_ok=True)

WIDTH = 4.8                       # JoC maximum figure width (in)
FS_BASE, FS_SMALL = 8, 7          # size ladder: labels 8 pt, ticks/legend/annotations 7 pt
BLUE, RED = "#3B6FB6", "#C0392B"
GREY = "#8A8A8A"
ALGOS = [("km", BLUE, "$k$-means"), ("hc", RED, "Ward")]
SEPS = [0.1, 2, 6, 10]
SCEN = ["sep", "p", "k", "rho", "distribution"]
RANGE = "full"                    # primary candidate range {2,...,8}
FIG_REP, FIG_DRAW = 1, 1          # replicate and synthetic draw shown in Figs 1-2


def style():
    plt.rcParams.update({
        "font.size": FS_BASE, "axes.labelsize": FS_BASE, "axes.titlesize": FS_BASE,
        "xtick.labelsize": FS_SMALL, "ytick.labelsize": FS_SMALL,
        "legend.fontsize": FS_SMALL, "axes.linewidth": 0.7,
        "xtick.major.width": 0.7, "ytick.major.width": 0.7,
        "pdf.fonttype": 42, "font.family": "serif"})


def save(fig, stem):
    fig.savefig(f"{OUT}/{stem}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}/{stem}.png", dpi=400, bbox_inches="tight")
    check_fonts(fig, stem)
    plt.close(fig)


def check_fonts(fig, stem):
    """Fail if any visible text is below 7 pt or the figure is wider than 4.8 in."""
    sizes = [t.get_fontsize() for t in fig.findobj(mpl.text.Text)
             if t.get_visible() and t.get_text().strip()]
    w = fig.get_size_inches()[0]
    assert min(sizes) >= 7 - 1e-9, f"{stem}: font below 7 pt ({min(sizes)})"
    assert w <= WIDTH + 1e-9, f"{stem}: width {w} in"
    print(f"  {stem}: width {w:.2f} in, font sizes {sorted(set(sizes))}")


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def sep_axis(ax, shade=True):
    """Categorical separation axis: positions 0..3 labelled 0.1, 2, 6, 10."""
    ax.set_xticks(range(len(SEPS)), [f"{s:g}" for s in SEPS])
    ax.set_xlim(-0.3, len(SEPS) - 0.7)
    if shade:
        ax.axvspan(-0.3, 1.5, color=GREY, alpha=0.10, lw=0, zorder=0)


def panel_letter(ax, letter, x=0.0, y=1.03):
    """Bold panel letter just above the top-left corner of the axes box."""
    ax.text(x, y, f"({letter})", transform=ax.transAxes, fontsize=FS_BASE,
            fontweight="bold", ha="left", va="bottom")


def scen_band(df, col, by):
    """Mean and 1.96*SE over scenario-level means, grouped by `by`."""
    g = df.groupby(SCEN)[col].mean().reset_index()
    a = g.groupby(by)[col].agg(["mean", "std", "count"])
    return a["mean"], 1.96 * a["std"] / np.sqrt(a["count"])


# ------------------------------------------------------------------ Figs 1-2
def align_labels(Xref, lab_ref, X, lab, k):
    """Relabel `lab` so that cluster j sits where cluster j of the reference sits."""
    cr = np.array([Xref[lab_ref == j].mean(axis=0) for j in range(k)])
    cs = np.array([X[lab == j].mean(axis=0) for j in range(k)])
    cost = np.linalg.norm(cr[:, None, :] - cs[None, :, :], axis=2)
    ri, ci = linear_sum_assignment(cost)
    remap = {int(c): int(r) for r, c in zip(ri, ci)}
    return np.array([remap[int(v)] for v in lab])


def orient(X, lab, k):
    """Make cluster 0 the upper one, so that colour tracks vertical position."""
    ymean = [X[lab == j][:, 1].mean() for j in range(k)]
    order = np.argsort(ymean)[::-1]
    remap = {int(o): i for i, o in enumerate(order)}
    return np.array([remap[int(v)] for v in lab])


def panel_grid(dist, stem):
    k, sep, p, rho = 2, 2, 2, 0.0
    tag = f"N1000_p{p}_k{k}_rho{rho:g}_sep{sep:g}_{dist}"
    od = pd.read_parquet(str(require(ORIGINAL_DIR / f"OD_{tag}.parquet")))
    sd = pd.read_parquet(str(require(SYNTHETIC_DIR / f"SD_cart_{tag}_syn{FIG_DRAW}.parquet")))
    feats = [c for c in od.columns if c.startswith("X")]
    Rr = od[od.rep == FIG_REP]
    Sr = sd[sd.rep == FIG_REP]
    sc = StandardScaler().fit(Rr[feats].values)
    Xr = sc.transform(Rr[feats].values)
    Xs = sc.transform(Sr[feats].values)
    true_r = orient(Xr, Rr["group"].astype(int).values - 1, k)
    true_s = align_labels(Xr, true_r, Xs, Sr["group"].astype(int).values - 1, k)
    km_r = orient(Xr, KMeans(k, n_init=10, random_state=42).fit_predict(Xr), k)
    hc_r = orient(Xr, AgglomerativeClustering(k).fit_predict(Xr), k)
    km_s = align_labels(Xr, km_r, Xs, KMeans(k, n_init=10, random_state=42).fit_predict(Xs), k)
    hc_s = align_labels(Xr, hc_r, Xs, AgglomerativeClustering(k).fit_predict(Xs), k)

    cmap = np.array([RED, BLUE])
    fig, axes = plt.subplots(2, 3, figsize=(WIDTH - 0.04, 3.3), sharex=True, sharey=True)
    cols = [(true_r, true_s), (km_r, km_s), (hc_r, hc_s)]
    letters = iter("abcdef")
    for i in range(2):
        for j, (lr, ls) in enumerate(cols):
            X, lab = (Xr, lr) if i == 0 else (Xs, ls)
            ax = axes[i, j]
            # (d): the synthetic `group` column is a CART prediction of the label from
            # the synthetic features, not a planted truth, so it is drawn in one colour.
            colours = "#1A1A1A" if (i == 1 and j == 0) else cmap[lab]
            ax.scatter(X[:, 0], X[:, 1], c=colours, s=2.0, lw=0, alpha=0.75, rasterized=True)
            ax.margins(0.05)
            for s in ax.spines.values():
                s.set_linewidth(0.6); s.set_color("#666666")
            ax.text(0.03, 0.97, f"({next(letters)})", transform=ax.transAxes, fontsize=FS_SMALL,
                    fontweight="bold", ha="left", va="top")
    for ax in axes[1]:
        ax.set_xlabel("$X_1$ (standardised)")
    for ax in axes[:, 0]:
        ax.set_ylabel("$X_2$ (standardised)")
    fig.tight_layout(h_pad=0.4, w_pad=0.4)
    save(fig, stem)


# ------------------------------------------------------------------ Fig 3
def fig_recovery_curves(d):
    """RR and AG against separation, by planted k (fixed range)."""
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.55), sharey=True)
    conv = [("k", "Planted $k$ (RR)"), ("khat_real_{a}_" + RANGE, "Original $\\hat{k}_R$ (AG)")]
    x = np.arange(len(SEPS))
    for pi, (ax, (ref_t, title)) in enumerate(zip(axes, conv)):
        for kk, ls in zip([2, 3, 4], ["-", "--", ":"]):
            sub = d[d.k == kk]
            for a, col, _ in ALGOS:
                ref = sub[ref_t.format(a=a)] if "{a}" in ref_t else sub[ref_t]
                hit = (sub[f"khat_syn_{a}_{RANGE}"] == ref).astype(float)
                g = hit.groupby(sub["sep"]).mean().reindex(SEPS)
                ax.plot(x, g.values, ls, color=col, lw=1.2, marker="o", ms=2.8)
        sep_axis(ax)
        ax.set_xlabel("Separation $\\sigma$")
        ax.set_title(f"$\\bf{{({'ab'[pi]})}}$  {title}", loc="left")
        despine(ax)
    axes[0].set_ylabel("Share of synthetic datasets")
    axes[0].set_ylim(-0.02, 1.05)
    h = [Line2D([], [], color=BLUE, lw=1.2, label="$k$-means"),
         Line2D([], [], color=RED, lw=1.2, label="Ward"),
         Line2D([], [], color=GREY, lw=1.2, ls="-", label="$k=2$"),
         Line2D([], [], color=GREY, lw=1.2, ls="--", label="$k=3$"),
         Line2D([], [], color=GREY, lw=1.2, ls=":", label="$k=4$")]
    axes[1].legend(handles=h, frameon=False, loc="lower right", ncol=2,
                   handlelength=1.8, columnspacing=0.8)
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_recovery")


# ------------------------------------------------------------------ Fig 4
def floor_table(boot):
    """Per-dataset floor (mean over the B resamples), in wide format km/hc."""
    f = boot.groupby(["p", "k", "rho", "sep", "distribution", "rep", "algo"])[
        ["mcd", "mvd", "dgini", "rvd", "mvd_pc", "mcd_sd"]].mean().reset_index()
    w = f.pivot_table(index=["p", "k", "rho", "sep", "distribution", "rep"], columns="algo").reset_index()
    w.columns = [c[0] if c[1] == "" else f"{c[0]}_{c[1]}" for c in w.columns]
    return w


def check_floor(fl, bs):
    o = bs["item2_geometric_floor"]["overall"]
    o3 = bs["item3_scale_free"]["overall"]
    for m in ("mcd", "mvd", "dgini"):
        for a in ("km", "hc"):
            v = fl.groupby(SCEN)[f"{m}_{a}"].mean().mean()
            assert abs(v - o[f"floor_{m}_{a}"]) < 1e-9, (m, a, v)
    for m in ("rvd", "mcd_sd"):
        for a in ("km", "hc"):
            v = fl.groupby(SCEN)[f"{m}_{a}"].mean().mean()
            assert abs(v - o3[f"floor_{m}_{a}"]) < 1e-9, (m, a, v)


def fig_fidelity_bands(rel, fl):
    """Observed metric (solid, band) and bootstrap floor (dashed) against separation."""
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH, 4.1), sharex=True)
    mets = [("mcd", "MCD"), ("mvd", "MVD"),
            ("mcd_sd", "MCD (within-SD units)"), ("rvd", "RVD")]
    x = np.arange(len(SEPS))
    for pi, (ax, (m, lbl)) in enumerate(zip(axes.ravel(), mets)):
        for a, col, _ in ALGOS:
            mu, ci = scen_band(rel, f"{m}_{a}", "sep")
            mu, ci = mu.reindex(SEPS), ci.reindex(SEPS)
            ax.plot(x, mu.values, "-o", color=col, ms=3, lw=1.2, zorder=3)
            ax.fill_between(x, (mu - ci).values, (mu + ci).values, color=col, alpha=0.18, lw=0, zorder=2)
            fmu, _ = scen_band(fl, f"{m}_{a}", "sep")
            ax.plot(x, fmu.reindex(SEPS).values, "--", color=col, lw=1.0, marker="o", ms=2.5,
                    mfc="white", zorder=3)
        sep_axis(ax, shade=False)
        ax.set_ylabel(lbl)
        ax.set_ylim(bottom=0)
        panel_letter(ax, "abcd"[pi])
        despine(ax)
    for ax in axes[1]:
        ax.set_xlabel("Separation $\\sigma$")
    h = [Line2D([], [], color=BLUE, lw=1.2, label="$k$-means"),
         Line2D([], [], color=RED, lw=1.2, label="Ward"),
         Line2D([], [], color=GREY, lw=1.2, marker="o", ms=3, label="CART synthetic"),
         Line2D([], [], color=GREY, lw=1.0, ls="--", marker="o", ms=2.5, mfc="white",
                label="bootstrap floor")]
    fig.legend(handles=h, frameon=False, loc="lower center", ncol=4, handlelength=2.0,
               columnspacing=1.0, bbox_to_anchor=(0.5, 0.0))
    axes[0, 1].text(0.98, 0.97, "lower = better", transform=axes[0, 1].transAxes,
                    fontsize=FS_SMALL, color=GREY, ha="right", va="top")
    fig.tight_layout(h_pad=0.6, w_pad=0.8, rect=[0, 0.05, 1, 1])
    save(fig, "fig_fidelity")


# ------------------------------------------------------------------ Fig 5
def fig_gini_mvd(rel, fl):
    """Bars: observed; hatched inner bar: bootstrap floor (the solid part above it is the excess)."""
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.4))
    w = 0.36
    panels = [(axes[0], "mvd", "p", [2, 5, 10], ["2", "5", "10"], "Dimensionality $p$", "MVD"),
              (axes[1], "dgini", "distribution", ["normal", "gamma"], ["Normal", "Gamma"],
               "Distribution family", "$\\Delta G$")]
    for pi, (ax, m, by, levels, labs, xl, yl) in enumerate(panels):
        for i, (a, col, name) in enumerate(ALGOS):
            mu, ci = scen_band(rel, f"{m}_{a}", by)
            fmu, _ = scen_band(fl, f"{m}_{a}", by)
            mu, ci, fmu = mu.reindex(levels), ci.reindex(levels), fmu.reindex(levels)
            xx = np.arange(len(levels)) + (i - 0.5) * w
            ax.bar(xx, mu.values, w, color=col, label=name, zorder=2)
            ax.bar(xx, fmu.values, w * 0.999, color="white", alpha=0.55, hatch="////",
                   edgecolor=col, lw=0.0, zorder=3)
            ax.errorbar(xx, mu.values, yerr=ci.values, fmt="none", ecolor="black",
                        elinewidth=0.8, capsize=2, zorder=4)
        ax.set_xticks(range(len(levels)), labs)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        panel_letter(ax, "ab"[pi])
        despine(ax)
    h = [Patch(facecolor=BLUE, label="$k$-means"), Patch(facecolor=RED, label="Ward"),
         Patch(facecolor="white", edgecolor=GREY, hatch="////", label="bootstrap floor")]
    axes[0].legend(handles=h, frameon=False, loc="upper left")
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig_balance")


# ------------------------------------------------------------------ Fig 6
def fig_distribution(d, boot):
    """Rows: planted k (RR, with original-data recovery) / original k-hat (AG, with AG0).
    Columns: Normal / Gamma. Fixed candidate range."""
    ds = d.groupby(SCEN + ["rep"]).first().reset_index()
    fig, axes = plt.subplots(2, 2, figsize=(WIDTH, 3.9), sharex=True, sharey="row")
    x = np.arange(len(SEPS))
    for ci_, (dist, dlab) in enumerate([("normal", "Normal"), ("gamma", "Gamma")]):
        sub, dsub = d[d.distribution == dist], ds[ds.distribution == dist]
        bsub = boot[boot.distribution == dist]
        for ri in range(2):
            ax = axes[ri, ci_]
            for a, col, _ in ALGOS:
                if ri == 0:
                    syn = (sub[f"khat_syn_{a}_{RANGE}"] == sub.k).groupby(sub.sep).mean()
                    ref = (dsub[f"khat_real_{a}_{RANGE}"] == dsub.k).groupby(dsub.sep).mean()
                else:
                    syn = (sub[f"khat_syn_{a}_{RANGE}"] == sub[f"khat_real_{a}_{RANGE}"]).groupby(sub.sep).mean()
                    ba = bsub[bsub.algo == a]
                    ref = (ba[f"khat_boot_{RANGE}"] == ba[f"khat_real_{RANGE}"]).groupby(ba.sep).mean()
                ax.plot(x, syn.reindex(SEPS).values, "-o", color=col, lw=1.2, ms=3, zorder=3)
                ax.plot(x, ref.reindex(SEPS).values, ":", color=col, lw=1.2, marker="o", ms=2.5,
                        mfc="white", zorder=3)
            sep_axis(ax)
            despine(ax)
            panel_letter(ax, "abcd"[2 * ri + ci_])
            if ri == 0:
                ax.set_title(dlab, loc="center")
            else:
                ax.set_xlabel("Separation $\\sigma$")
    axes[0, 0].set_ylabel("Share with $\\hat{k} = k$")
    axes[1, 0].set_ylabel("Share with $\\hat{k} = \\hat{k}_R$")
    axes[0, 0].set_ylim(0.0, 1.05)
    axes[1, 0].set_ylim(0.45, 1.02)
    h1 = [Line2D([], [], color=BLUE, lw=1.2, label="$k$-means"),
          Line2D([], [], color=RED, lw=1.2, label="Ward")]
    h2 = [Line2D([], [], color=GREY, lw=1.2, marker="o", ms=3, label="synthetic"),
          Line2D([], [], color=GREY, lw=1.2, ls=":", marker="o", ms=2.5, mfc="white",
                 label="original")]
    h3 = [Line2D([], [], color=GREY, lw=1.2, marker="o", ms=3, label="synthetic"),
          Line2D([], [], color=GREY, lw=1.2, ls=":", marker="o", ms=2.5, mfc="white",
                 label="bootstrap")]
    axes[0, 0].legend(handles=h1, frameon=False, loc="upper left")
    axes[0, 1].legend(handles=h2, frameon=False, loc="upper left")
    axes[1, 1].legend(handles=h3, frameon=False, loc="lower right")
    fig.tight_layout(h_pad=0.6, w_pad=0.6)
    save(fig, "fig_distribution")


# ------------------------------------------------------------------ supplementary
def fig_heatmap_supp(d):
    """Fig S1: recovery of the planted k by k x sep, fixed range."""
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.1), sharey=True)
    for ax, (a, _, name) in zip(axes, ALGOS):
        hit = (d[f"khat_syn_{a}_{RANGE}"] == d.k).astype(float)
        piv = hit.groupby([d.k, d.sep]).mean().unstack().reindex(columns=SEPS)
        im = ax.imshow(piv.values, cmap="viridis", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(SEPS)), [f"{c:g}" for c in SEPS])
        ax.set_yticks(range(len(piv.index)), piv.index)
        ax.set_xlabel("Separation $\\sigma$")
        ax.set_title(name)
        for i_ in range(piv.shape[0]):
            for j_ in range(piv.shape[1]):
                v = piv.values[i_, j_]
                ax.text(j_, i_, f"{v:.2f}", ha="center", va="center", fontsize=FS_SMALL,
                        color="white" if v < 0.55 else "black")
    axes[0].set_ylabel("Planted $k$")
    cb = fig.colorbar(im, ax=axes, fraction=0.04, pad=0.03)
    cb.set_label("Recovery rate RR", fontsize=FS_SMALL)
    cb.ax.tick_params(labelsize=FS_SMALL)
    save(fig, "figS_heatmap")


def fig_scaling_supp():
    """Fig S2: strong scaling of the model-selection workload (timings in seconds)."""
    t = json.load(open(require(RESULTS_DIR / "scaling_timings.json")))
    P = np.array(sorted(int(k) for k in t))
    T = np.array([t[str(p)] for p in P])
    S = T[0] / T
    E = 100 * S / P
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.2))
    ax = axes[0]
    ax.plot(P, P, ":", color=GREY, lw=1.0, label="linear")
    ax.plot(P, S, "-o", color=BLUE, ms=3, lw=1.2, label="measured")
    ax.set_ylabel("Speed-up $T_1/T_P$")
    ax.legend(frameon=False, loc="upper left")
    ax = axes[1]
    ax.axhline(100, ls=":", color=GREY, lw=1.0)
    ax.plot(P, E, "-o", color=BLUE, ms=3, lw=1.2)
    ax.set_ylabel("Parallel efficiency (%)")
    ax.set_ylim(0, 110)
    for pi, ax in enumerate(axes):
        ax.axvline(12, ls="--", color=RED, lw=0.9)
        ax.set_xticks([1, 4, 8, 12, 18, 24])
        ax.set_xlabel("Worker processes $P$")
        panel_letter(ax, "ab"[pi])
        despine(ax)
    axes[0].text(12.6, 1.2, "12 physical cores", rotation=90, color=RED, fontsize=FS_SMALL,
                 va="bottom", ha="left")
    fig.tight_layout(w_pad=1.0)
    save(fig, "figS_scaling")


def main():
    style()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(str(require(FIDELITY_RESULTS)))
    rel = pd.read_parquet(str(require(RESULTS_DIR / "relative_metrics.parquet")))
    boot = pd.read_parquet(str(require(RESULTS_DIR / "bootstrap_null.parquet")))
    bs = json.load(open(require(RESULTS_DIR / "bootstrap_summary.json")))
    fl = floor_table(boot)
    check_floor(fl, bs)
    panel_grid("normal", "fig_normal")
    panel_grid("gamma", "fig_gamma")
    fig_recovery_curves(d)
    fig_fidelity_bands(rel, fl)
    fig_gini_mvd(rel, fl)
    fig_distribution(d, boot)
    fig_heatmap_supp(d)
    fig_scaling_supp()
    print("figures written")


if __name__ == "__main__":
    main()
