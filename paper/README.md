# Publication Package

LaTeX sources for the Explaintool HHGR paper, poster, and presentation.

## Structure

```
paper/
├── paper.tex           # IEEEtran conference paper (main document)
├── abstract.tex        # Abstract
├── introduction.tex    # Introduction & contributions
├── methodology.tex     # HHGR methodology & metrics
├── experiments.tex     # Dataset, baselines, ablations, setup
├── results.tex         # Results tables and discussion
├── future-work.tex     # Future work & reproducibility
├── references.bib      # BibTeX bibliography
├── poster/
│   └── poster.tex      # A0 portrait research poster (beamerposter)
└── presentation/
    └── slides.tex      # Conference slides (beamer)
```

## Build

Requires a LaTeX distribution with `IEEEtran`, `beamer`, and `beamerposter`
packages.

```bash
# Paper
pdflatex paper.tex && bibtex paper && pdflatex paper.tex && pdflatex paper.tex

# Poster
cd poster && pdflatex poster.tex

# Presentation
cd presentation && pdflatex slides.tex
```

## Figures

All figures referenced in the paper (architecture, hierarchy tree, KG example,
evaluation charts) are generated programmatically:

```bash
python -m eval.cli --out evaluation
```

The figures are written to `evaluation/figures/*.svg` and `*.png` and are
embeddable in the LaTeX sources. Run `scripts/reproduce.sh` to regenerate
everything from scratch.
