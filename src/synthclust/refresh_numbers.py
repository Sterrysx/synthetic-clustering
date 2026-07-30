"""Recompute the design-dependent numbers in the manuscript and patch main.tex.

    uv run refresh-numbers            # report what would change
    uv run refresh-numbers --write    # apply

Why this exists: `m` appears in the manuscript as a raw count in several places
(the number of synthetic draws, the resulting number of original--synthetic
pairs) and the headline recovery rates depend on the full dataset. Changing `m`
in config.json invalidates all of them at once, and hand-editing invites the
kind of stale figure a reviewer catches. Every value below is derived from
config.json or measured from the results, never typed.

Only exact, unambiguous strings are replaced, and every substitution is counted
and reported. If an expected pattern is missing the script says so rather than
silently doing nothing.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

from synthclust.paths import CONFIG, FIDELITY_RESULTS, REPO

MAIN = REPO / "manuscript" / "main.tex"


def tex_int(n: int) -> str:
    """LaTeX thousands separator as used throughout the manuscript."""
    return f"{n:,}".replace(",", "{,}")


def measure():
    cfg = json.loads(Path(CONFIG).read_text())["simulation"]
    n_scen = 144
    pairs = n_scen * cfg["n"] * cfg["m"]

    d = pd.read_parquet(str(FIDELITY_RESULTS))
    if len(d) != pairs:
        raise SystemExit(
            f"fidelity table has {len(d):,} rows but config implies {pairs:,}. "
            "Has the metrics stage finished? Refusing to patch the manuscript."
        )

    vals = {"m": cfg["m"], "n": cfg["n"], "pairs": pairs}
    for a in ("km", "hc"):
        # v1: agreement with the planted k. v2: with k recovered on the original.
        vals[f"v1_{a}"] = (d[f"khat_syn_{a}_capped"] == d["k"]).mean()
        vals[f"v2_{a}"] = (d[f"khat_syn_{a}_capped"]
                           == d[f"khat_real_{a}_capped"]).mean()
        by = d.groupby("sep")
        vals[f"v1_{a}_by_sep"] = [
            (g[f"khat_syn_{a}_capped"] == g["k"]).mean() for _, g in by]
        vals[f"v2_{a}_by_sep"] = [
            (g[f"khat_syn_{a}_capped"] == g[f"khat_real_{a}_capped"]).mean()
            for _, g in by]
        vals[f"orig_{a}_by_sep"] = [
            (g[f"khat_real_{a}_capped"] == g["k"]).mean() for _, g in by]
    return vals


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the edits")
    args = ap.parse_args()

    v = measure()
    t = MAIN.read_text()

    # (pattern, replacement, label). Patterns are literal so a miss is visible.
    #
    # ORDER MATTERS: the compound arithmetic string contains the bare pair count,
    # so it must be rewritten BEFORE the standalone pair-count substitution --
    # otherwise that rewrite destroys the compound pattern and it reports MISSING.
    subs = [
        (rf"144 \times {v['n']} \times 100 = 72{{,}}000",
         rf"144 \times {v['n']} \times {v['m']} = {tex_int(v['pairs'])}",
         "design arithmetic"),
        (r"72{,}000", tex_int(v["pairs"]), "pair count"),
        (r"$m = 100$", f"$m = {v['m']}$", "m in Data generation"),
    ]
    report = []
    for old, new, label in subs:
        n = t.count(old)
        if n and old != new:
            t = t.replace(old, new)
        report.append((label, old, new, n))

    print(f"m = {v['m']}, pairs = {v['pairs']:,}\n")
    print("string substitutions:")
    for label, old, new, n in report:
        status = "MISSING" if n == 0 else f"{n}x"
        print(f"  {status:>8}  {label}: {old!r} -> {new!r}")

    print("\nrecomputed values (patch these by hand where prose differs):")
    print(f"  overall v1: k-means {v['v1_km']:.3f}  Ward {v['v1_hc']:.3f}")
    print(f"  overall v2: k-means {v['v2_km']:.3f}  Ward {v['v2_hc']:.3f}")
    for lab in ("v1", "v2", "orig"):
        for a in ("km", "hc"):
            xs = " ".join(f"{x:.3f}" for x in v[f"{lab}_{a}_by_sep"])
            print(f"  {lab:>4} {a} by sep: {xs}")

    if args.write:
        MAIN.write_text(t)
        print(f"\nwrote {MAIN}")
    else:
        print("\n(dry run; pass --write to apply)")


if __name__ == "__main__":
    main()
