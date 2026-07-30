#!/bin/bash
# Compile the manuscript:  ./build.sh [main|supplementary]
#
# On a normal TeX Live install you do not need this script -- `latexmk -pdf
# main.tex` is enough. It exists because the machine this was written on has a
# broken TeX Live: the ls-R index is masked so kpathsea resolves nothing via the
# default paths, and no pdflatex.fmt ships with the Debian package. The explicit
# TEX* exports below work around that, and texfmt/ holds a locally built format
# plus a font map assembled from the installed amsfonts maps (see README).
set -e
M="$(cd "$(dirname "$0")" && pwd)"   # this directory (manuscript/)
W="$M"                                # texfmt/ lives alongside
export TEXINPUTS=".:$M//:/usr/share/texlive/texmf-dist/tex/latex//:/usr/share/texlive/texmf-dist/tex/generic//:"
export TEXFONTS=".:/usr/share/texlive/texmf-dist/fonts//:"
export TEXFORMATS=".:$W/texfmt:"
export BSTINPUTS=".:$M//:/usr/share/texlive/texmf-dist/bibtex/bst//:"
export BIBINPUTS=".:$M//:"
# The sandbox has no updmap-generated pdftex.map; point pdftex at a map
# assembled from the installed amsfonts/tex-gyre maps instead.
export TEXFONTMAPS=".:$W/texfmt/map//:/usr/share/texlive/texmf-dist/fonts/map//:"
export TEXPSHEADERS=".:/usr/share/texlive/texmf-dist/fonts/type1//:/usr/share/texlive/texmf-dist/dvips//:"
export T1FONTS=".:/usr/share/texlive/texmf-dist/fonts/type1//:"
export TFMFONTS=".:/usr/share/texlive/texmf-dist/fonts/tfm//:"
export VFFONTS=".:/usr/share/texlive/texmf-dist/fonts/vf//:"
export ENCFONTS=".:/usr/share/texlive/texmf-dist/fonts/enc//:"
cd "$M"
DOC=${1:-main}
pdftex -fmt=pdflatex -interaction=nonstopmode -cnf-line="pdftex.map=$W/texfmt/map/local.map" "$DOC.tex" > /dev/null 2>&1 || true
bibtex "$DOC" > /dev/null 2>&1 || true
pdftex -fmt=pdflatex -interaction=nonstopmode -cnf-line="pdftex.map=$W/texfmt/map/local.map" "$DOC.tex" > /dev/null 2>&1 || true
pdftex -fmt=pdflatex -interaction=nonstopmode -cnf-line="pdftex.map=$W/texfmt/map/local.map" "$DOC.tex" > "$DOC.build.log" 2>&1 || true
if [ -f "$DOC.pdf" ]; then
  echo "OK $DOC.pdf $(stat -c%s "$DOC.pdf") bytes"
  grep -c "Warning" "$DOC.log" 2>/dev/null | sed 's/^/warnings: /' || true
  grep -n "^!" "$DOC.log" | head -10 || true
else
  echo "FAILED"; grep -n "^!" "$DOC.log" | head -20
fi
