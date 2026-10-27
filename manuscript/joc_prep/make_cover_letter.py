"""Typeset cover_letter.md as cover_letter.pdf (no pandoc on the build machine).
Handles the small Markdown subset used in the letter: paragraphs, **bold**,
*italic*, '- ' bullet lists, [[placeholders]] (printed in red), and the
HTML comment at the top (dropped).  Run from manuscript/:
    python joc_prep/make_cover_letter.py
"""
import os, pathlib, re, subprocess
J = pathlib.Path(__file__).resolve().parent; M = J.parent
md = (J / "cover_letter.md").read_text()
md = re.sub(r"<!--.*?-->", "", md, flags=re.S).strip()

def inline(s):
    s = s.replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("#", r"\#").replace("_", r"\_")
    s = s.replace("×", r"$\times$").replace("⁻⁵", r"$^{-5}$").replace("⁻", r"$^{-}$")
    s = re.sub(r"\[\[(.*?)\]\]", lambda m: r"\textcolor{red}{[" + m.group(1) + "]}", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"\*(.+?)\*", r"\\emph{\1}", s)
    s = s.replace('"', "''")
    s = re.sub(r"(^|[\s({])''", r"\1``", s)
    return s

out = []; blocks = md.split("\n\n")
for b in blocks:
    lines = b.splitlines()
    if all(l.startswith("- ") for l in lines):
        out.append("\\begin{itemize}\\setlength{\\itemsep}{1pt}\\setlength{\\topsep}{2pt}\n" + "\n".join("\\item " + inline(l[2:]) for l in lines) + "\n\\end{itemize}")
    else:
        out.append("\\\\\n".join(inline(l) for l in lines))
tex = r"""\documentclass[10pt,a4paper]{article}
\pdfmapfile{=local.map}
\usepackage[utf8]{inputenc}
\usepackage[a4paper,margin=18mm,top=13mm,bottom=12mm]{geometry}
\usepackage{xcolor}
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
\pagestyle{empty}
\renewcommand\labelitemi{$\bullet$}
\begin{document}
""" + "\n\n".join(out) + "\n\\end{document}\n"
(M / "cover_letter.tex").write_text(tex)
env = dict(os.environ)
env.update(TEXINPUTS=f".:{M}//:/usr/share/texlive/texmf-dist/tex/latex//:/usr/share/texlive/texmf-dist/tex/generic//:",
           TEXFONTS=".:/usr/share/texlive/texmf-dist/fonts//:", TEXFORMATS=f".:{M}/texfmt:",
           TEXFONTMAPS=f".:{M}/texfmt/map//:/usr/share/texlive/texmf-dist/fonts/map//:",
           T1FONTS=".:/usr/share/texlive/texmf-dist/fonts/type1//:", TFMFONTS=".:/usr/share/texlive/texmf-dist/fonts/tfm//:",
           VFFONTS=".:/usr/share/texlive/texmf-dist/fonts/vf//:", ENCFONTS=".:/usr/share/texlive/texmf-dist/fonts/enc//:",
           TEXPSHEADERS=".:/usr/share/texlive/texmf-dist/fonts/type1//:/usr/share/texlive/texmf-dist/dvips//:")
for _ in range(2):
    subprocess.run(["timeout", "120", "pdftex", "-fmt=pdflatex", "-interaction=nonstopmode",
                    f"-cnf-line=pdftex.map={M}/texfmt/map/local.map", "cover_letter.tex"],
                   cwd=M, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pdf = M / "cover_letter.pdf"; assert pdf.exists()
(J / "cover_letter.pdf").write_bytes(pdf.read_bytes())
(M / "submission").mkdir(exist_ok=True); (M / "submission" / "cover_letter.pdf").write_bytes(pdf.read_bytes())
print("OK", J / "cover_letter.pdf")
