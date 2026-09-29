#!/bin/bash
# Compile a test copy inside joc_prep/:   ./build_joc.sh <docname-without-.tex>
# Same environment workaround as ../build.sh (broken kpathsea on the build
# machine); on a normal TeX Live install `latexmk -pdf <doc>.tex` run from this
# folder with TEXINPUTS=.:..: is enough.  Search order: joc_prep/ first (so
# sn-joc.bst and the snippets win), then manuscript/ (sn-jnl.cls, refs.bib,
# figures/, local.map), then the system tree.
set -e
J="$(cd "$(dirname "$0")" && pwd)"   # joc_prep/
M="$(cd "$J/.." && pwd)"             # manuscript/
export TEXINPUTS=".:$J:$M:/usr/share/texlive/texmf-dist/tex/latex//:/usr/share/texlive/texmf-dist/tex/generic//:"
export TEXFONTS=".:/usr/share/texlive/texmf-dist/fonts//:"
export TEXFORMATS=".:$M/texfmt:"
export BSTINPUTS=".:$J:$M:/usr/share/texlive/texmf-dist/bibtex/bst//:"
export BIBINPUTS=".:$J:$M:"
export TEXFONTMAPS=".:$M:$M/texfmt/map//:/usr/share/texlive/texmf-dist/fonts/map//:"
export TEXPSHEADERS=".:/usr/share/texlive/texmf-dist/fonts/type1//:/usr/share/texlive/texmf-dist/dvips//:"
export T1FONTS=".:/usr/share/texlive/texmf-dist/fonts/type1//:"
export TFMFONTS=".:/usr/share/texlive/texmf-dist/fonts/tfm//:"
export VFFONTS=".:/usr/share/texlive/texmf-dist/fonts/vf//:"
export ENCFONTS=".:/usr/share/texlive/texmf-dist/fonts/enc//:"
DOC=${1:?usage: build_joc.sh doc}
cd "$J/test"
run() { pdftex -fmt=pdflatex -interaction=nonstopmode -cnf-line="pdftex.map=$M/texfmt/map/local.map" "$DOC.tex" > /dev/null 2>&1 || true; }
run; bibtex "$DOC" > "$DOC.bibtex.log" 2>&1 || true; run; run
if [ -f "$DOC.pdf" ]; then
  echo "OK $DOC.pdf pages=$(pdfinfo "$DOC.pdf" | awk '/^Pages/{print $2}')"
  grep -n "^!" "$DOC.log" | head -10 || true
  grep -c "Overfull" "$DOC.log" | sed 's/^/overfull boxes: /' || true
  grep -i "error\|warning" "$DOC.blg" | head -5 || true
else
  echo "FAILED"; grep -n "^!" "$DOC.log" | head -20
fi
