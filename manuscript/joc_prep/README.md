# joc_prep/: Journal of Classification submission kit (integrated in v5)

Since v5 the files in this folder are **used by the real build**: `../main.tex` and
`../supplementary.tex` read `joc_bib.tex` (and hence `sn-joc.bst`), `blind.tex` and, in the
referee layout, `joc_referee.tex`. `sn-jnl.cls` is not modified.

## Build commands

Run from `manuscript/`. The finished PDFs are copied to `manuscript/submission/`.

| command | output | what it is |
|---|---|---|
| `./build_submission.sh blind` | `submission/main_blind.pdf` | anonymised manuscript for review: referee layout (12 pt, double-spaced, single column, A4, 30 mm margins), JoC reference style, no author block, anonymous repository placeholder, identifying clause hidden, declarations pointing to the title page, empty PDF metadata |
| `./build_submission.sh suppblind` | `submission/supplementary_blind.pdf` | the supplementary material, same layout and anonymisation |
| `./build_submission.sh title` | `submission/title_page.pdf` | separate, non-anonymous title page: five authors and affiliations, abstract, corresponding-author and Declarations placeholders (red `TO COMPLETE`) |
| `./build_submission.sh named` | `submission/main_named.pdf`, `submission/supplementary_named.pdf` | named version in the normal sn-jnl layout, for circulating to the co-authors |
| `./build_submission.sh diff` | `submission/main_diff_v4_v5.pdf` | latexdiff of `_backup_v4/main.tex` (v4) against `main.tex` (v5), named layout |
| `./build_submission.sh check` | (stdout) | PDF Info dictionary of the blind PDFs and a page-by-page search for identifying strings |
| `./build_submission.sh all` | all of the above | |

`./build.sh main` and `./build.sh supplementary` still work and give the named, normal-layout
version (identical to `main_named.pdf`).

### How the switches work

`main.tex` and `supplementary.tex` are single sources. Two macros, defined on the command line
before the file is read, select the variant:

    \def\SetReferee{}     referee layout (joc_referee.tex); otherwise the normal sn-jnl layout
    \def\SetBlind{true}   anonymised (blind.tex); the default in main.tex is \SetBlind{false}

On a normal TeX Live installation (no build-machine workarounds) the four PDFs are, from
`manuscript/`:

    pdflatex -jobname=main_blind '\def\SetReferee{}\def\SetBlind{true}\input{main}'
    bibtex main_blind
    pdflatex -jobname=main_blind '\def\SetReferee{}\def\SetBlind{true}\input{main}'   # twice
    # likewise: supplementary_blind (…\input{supplementary}), main_named ('\def\SetBlind{false}\input{main}')
    pdflatex joc_prep/title_page      # (jobname title_page; run twice)

The `\pdfmapfile{=local.map}` line in the preambles is a build-machine workaround and should be
deleted elsewhere. `build_submission.sh` repeats the `TEX*` environment of `build.sh` for the same
reason.

### Anonymisation in the source

- Author block: left untouched in `main.tex`; `blind.tex` swallows `\author`/`\affil` and prints
  "Author details removed for anonymous review".
- Repository: `\repourl` prints `\realrepourl` (GitHub) or `\anonrepourl`
  (`https://anonymous.4open.science/r/XXXX`, **placeholder until the mirror exists**).
- `\blindhide{, to which we have direct access}` in Future work.
- Declarations: `\blindalt{Given on the separate title page ...}{[To be completed ...]}` for
  Funding, Competing interests and Author contributions.
- PDF metadata: Title, Author, Subject, Keywords, Creator, Producer and dates are empty; no
  trailer ID and no `/PTEX.*` keys (`\pdfsuppressptexinfo=-1`).
- Not anonymised (authors to decide): third-person citations of `chen2025` (a co-author's UPC
  bachelor's thesis) and `vidiella2025` (co-authored by V. López).
- The `.tex` sources still contain the author names (comments, author block). Upload the PDFs
  for review, or strip comments before uploading any source.

## Files

| file | purpose |
|---|---|
| `sn-joc.bst` | sn-basic.bst with JoC changes: UPPERCASE surnames with initials, all authors listed, "ed." for editions, no month, "et al." in labels |
| `joc_bib.tex` | natbib `[authoryear,longnamesfirst]` + `\bibliographystyle{joc_prep/sn-joc}` (first citation of 3+ authors in full) |
| `joc_referee.tex` | 12 pt, double-spaced, single-column, A4 with 30 mm margins, for sn-jnl.cls |
| `blind.tex` | `\ifblind` switch: `\blindalt`, `\blindhide`, `\blindremoved`, `\repourl`; author block and PDF metadata |
| `title_page.tex` | separate non-anonymous title page (reads `../abstract.tex`) |
| `cover_letter.md`, `cover_letter.pdf` | cover letter with the v5 findings; administrative placeholders remain in `[[...]]` |
| `CHECKLIST.md` | JoC requirements with source quotes and status against the v5 blind build |
| `verify_numbers.py`, `VERIFICATION.md` | independent recomputation of every number in the abstract, Sections 3-5 and all tables from the stored parquet files, and its report |
| `supplementary_header_blind.tex`, `make_test_copies.py`, `build_joc.sh`, `test/` | **superseded** v4-era test copies (generated from the v4 text); kept for reference only |
| `joc_guidelines.txt` | plain-text extract of the JoC submission guidelines (fetched 2026-09-29) |
