#!/bin/bash
# Journal of Classification submission builds (v5).
#
#   ./build_submission.sh blind    -> submission/main_blind.pdf
#   ./build_submission.sh suppblind-> submission/supplementary_blind.pdf
#   ./build_submission.sh title    -> submission/title_page.pdf
#   ./build_submission.sh named    -> submission/main_named.pdf
#                                     (+ submission/supplementary_named.pdf)
#   ./build_submission.sh diff     -> submission/main_diff_v4_v5.pdf
#   ./build_submission.sh check    -> anonymity + metadata checks on the blind PDFs
#   ./build_submission.sh all      -> all of the above, then check
#
# main.tex and supplementary.tex are single sources with two switches,
# \SetReferee (JoC referee layout, joc_prep/joc_referee.tex) and \SetBlind
# (joc_prep/blind.tex); each target only sets them on the command line and
# picks a -jobname, so no source file is copied or modified.  Auxiliary files
# stay in manuscript/ under the job name; the finished PDFs are copied to
# submission/.
#
# The TEX* exports repeat those of ./build.sh (broken kpathsea on the build
# machine).  On a normal TeX Live install they are unnecessary; the
# equivalent commands are listed in joc_prep/README.md.
set -e
M="$(cd "$(dirname "$0")" && pwd)"
W="$M"
export TEXINPUTS=".:$M//:/usr/share/texlive/texmf-dist/tex/latex//:/usr/share/texlive/texmf-dist/tex/generic//:"
export TEXFONTS=".:/usr/share/texlive/texmf-dist/fonts//:"
export TEXFORMATS=".:$W/texfmt:"
export BSTINPUTS=".:$M:/usr/share/texlive/texmf-dist/bibtex/bst//:"
export BIBINPUTS=".:$M:"
export TEXFONTMAPS=".:$W/texfmt/map//:/usr/share/texlive/texmf-dist/fonts/map//:"
export TEXPSHEADERS=".:/usr/share/texlive/texmf-dist/fonts/type1//:/usr/share/texlive/texmf-dist/dvips//:"
export T1FONTS=".:/usr/share/texlive/texmf-dist/fonts/type1//:"
export TFMFONTS=".:/usr/share/texlive/texmf-dist/fonts/tfm//:"
export VFFONTS=".:/usr/share/texlive/texmf-dist/fonts/vf//:"
export ENCFONTS=".:/usr/share/texlive/texmf-dist/fonts/enc//:"
cd "$M"
mkdir -p submission
OUT="$M/submission"

tex() {  # tex <jobname> <tex code>
  timeout 300 pdftex -fmt=pdflatex -interaction=nonstopmode \
    -cnf-line="pdftex.map=$W/texfmt/map/local.map" -jobname="$1" "$2" > /dev/null 2>&1 || true
}
job() {  # job <jobname> <tex code> : pdflatex, bibtex, pdflatex x2, report
  local J="$1" C="$2" T0
  T0=$(date +%s)
  tex "$J" "$C"; bibtex "$J" > "$J.bibtex.log" 2>&1 || true; tex "$J" "$C"; tex "$J" "$C"
  if [ -f "$J.pdf" ] && [ "$(stat -c %Y "$J.pdf")" -ge "$T0" ]; then
    cp "$J.pdf" "$OUT/$J.pdf"
    echo "OK $J.pdf pages=$(pdfinfo "$J.pdf" | awk '/^Pages/{print $2}')" \
         "undefined=$(grep -c 'undefined' "$J.log" || true)" \
         "overfull=$(grep -c 'Overfull' "$J.log" || true)" \
         "bibtex_warnings=$(grep -c '^Warning--' "$J.blg" 2>/dev/null || true)"
    grep -n "^!" "$J.log" | head -5 || true
  else
    echo "FAILED $J"; grep -n "^!" "$J.log" | head -20
  fi
}

blind()     { job main_blind '\def\SetReferee{}\def\SetBlind{true}\input{main}'; }
suppblind() { job supplementary_blind '\def\SetReferee{}\def\SetBlind{true}\input{supplementary}'; }
named()     { job main_named '\def\SetBlind{false}\input{main}'
              job supplementary_named '\def\SetBlind{false}\input{supplementary}'; }
title()     { job title_page '\input{joc_prep/title_page}'; }
latexdiff_v4_v5() {
  # old = _backup_v4/main.tex (v4), new = main.tex (v5).  The v5 abstract
  # (abstract.tex) is inlined into a temporary copy so that it is compared
  # word by word; the v5 tables are \input from tables/ and, like every
  # tabular, are marked as whole blocks (PICTUREENV) because latexdiff markup
  # inside alignments does not compile.  Typeset in the named, normal layout
  # with the v5 figures.
  python3 - <<'PY'
import pathlib
s = pathlib.Path('main.tex').read_text()
a = pathlib.Path('abstract.tex').read_text()
a = ''.join(l for l in a.splitlines(True) if not l.startswith('%')).rstrip().rstrip('%')
assert s.count(r'\abstract{\input{abstract}}') == 1
pathlib.Path('main_v5_for_diff.tex').write_text(s.replace(r'\abstract{\input{abstract}}', r'\abstract{' + a + '}'))
PY
  latexdiff --type=UNDERLINE --math-markup=whole \
    --config="PICTUREENV=(?:picture|DIFnomarkup|tabular)[\w\d*@]*" \
    --exclude-textcmd="section,subsection,subsubsection,paragraph" --append-textcmd="abstract,keywords" \
    _backup_v4/main.tex main_v5_for_diff.tex > main_diff_v4_v5.tex 2> main_diff_v4_v5.latexdiff.log
  job main_diff_v4_v5 '\def\SetBlind{false}\input{main_diff_v4_v5}'
}
check() {
  # Identifying strings that must not occur in the anonymised PDFs.  Author
  # surnames also occur legitimately in the reference list (third-person
  # self-citations chen2025, vidiella2025); every hit is printed with its page
  # so that it can be judged.
  local PAT='Farr(e|é)s|Oriol|Cort(e|é)s|Xinnuo|CHEN, X\.|Chen, X\.|Chen \(2025|Chen, 2025|L(o|ó|Ó)pez|L.{1,3}PEZ|Vidiella|Fern(a|á)ndez|Victoria|Jordi|Daniel|UPC|Polit(e|è)cnica|Catalunya|Bachelor|University College|UCL|CUNEF|Sterry|github|our previous|direct access|anonymous\.4open'
  export LC_ALL=C.UTF-8
  for f in main_blind supplementary_blind; do
    echo "== $f: PDF Info dictionary"
    pdfinfo "$OUT/$f.pdf" | grep -E '^(Title|Subject|Keywords|Author|Creator|Producer|CreationDate|ModDate):' || true
    echo "== $f: identifying strings (page: line)"
    n=$(pdfinfo "$OUT/$f.pdf" | awk '/^Pages/{print $2}')
    for ((p=1; p<=n; p++)); do
      pdftotext -layout -f $p -l $p "$OUT/$f.pdf" - | grep -n -i -E "$PAT" | sed "s/^/  p$p: /" || true
    done
    echo "== $f: raw-byte search (metadata, embedded file names)"
    strings "$OUT/$f.pdf" | grep -i -E 'sterry|/home/|github|PTEX' | head -5 || true
  done
}

case "${1:-all}" in
  blind) blind ;; suppblind) suppblind ;; title) title ;; named) named ;;
  diff) latexdiff_v4_v5 ;; check) check ;;
  all) blind; suppblind; title; named; latexdiff_v4_v5; check ;;
  *) echo "usage: $0 [blind|suppblind|title|named|diff|check|all]"; exit 1 ;;
esac
