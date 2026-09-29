# joc_prep/: Journal of Classification formatting kit (for v4)

Everything here is a **copy or an add-on**. `../main.tex` and `../supplementary.tex` are untouched.

| file | purpose |
|---|---|
| `sn-joc.bst` | sn-basic.bst with JoC changes: UPPERCASE surnames with initials in the reference list, all authors listed, "ed." for editions, no month, "et al." in labels. Author-year citations in the text stay in normal case. |
| `joc_bib.tex` | loads natbib `[authoryear,longnamesfirst]` + `sn-joc`. Use it **instead of** the `sn-basic` class option (see comment inside). |
| `joc_referee.tex` | 12 pt, double-spaced, single-column, A4 with 30 mm margins, for sn-jnl.cls |
| `blind.tex` | `\ifblind` switch: `\blindalt`, `\blindhide`, `\blindremoved`, `\repourl`; hides the author block and clears PDF author metadata |
| `supplementary_header_blind.tex` | replacement header (from `\documentclass` down to `\maketitle`) for supplementary.tex |
| `title_page.tex` | separate non-anonymous title page with Declarations placeholders |
| `cover_letter.md` | one-page cover letter draft (findings are placeholders) |
| `CHECKLIST.md` | JoC requirements with source quotes and status |
| `make_test_copies.py`, `build_joc.sh` | regenerate `test/*.tex` from ../main.tex and compile (`./build_joc.sh main_blind`) |

## Applying it to the real manuscript (when the authors decide to)

Replace line 20 of main.tex

    \documentclass[pdflatex,sn-basic]{sn-jnl}

with

    \documentclass[pdflatex,referee]{sn-jnl}
    \input{joc_referee}
    \input{joc_bib}
    \input{blind}

Then replace the GitHub `\url{...}` with `\repourl` and wrap identifying text in `\blindhide{...}`/`\blindalt{...}{...}`. `test/main_blind.tex` shows every edit. For a non-blind build, run `pdflatex '\def\SetBlind{false}\input{main_blind}'` (tested: `test/main_blind_off.pdf`).
