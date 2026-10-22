# make        : regenerate tables/figures from paper/data, build main.pdf
# make assets : only regenerate tables/figures
all: assets main.pdf
assets:
	cd .. && python scripts/paper_assets.py
main.pdf: main.tex sections/*.tex generated/*.tex references.bib macros.tex
	latexmk -pdf -interaction=nonstopmode main.tex
clean:
	latexmk -C
