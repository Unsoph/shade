# Paper workspace

Draft in LaTeX (plain `article`, two-column; swap the preamble in `main.tex`
for the target venue's template). Build: `make -C paper` (needs `pdflatex`,
`latexmk`, `bibtex`, and matplotlib for the figures). It compiles with no
hardware data: every owed item shows as a red **[TBD: ...]** and every missing
figure as a red dashed "PENDING HARDWARE DATA" box. Search for `TBD` and
`TODOcite` before submitting; there must be none left.

## Rules for this draft
- No number goes in by hand. Tables, figures and headline numbers are generated
  from `paper/data/` by `python scripts/paper_assets.py`.
- Simulation results carry the mark SIM and are never presented as device results.
- The abstract and intro contain *conditional* claims (throttled time down,
  5th-percentile FPS up). If the Pi data disagree, rewrite the claims, not the data.
- Every citation in `references.bib` was written from memory of well-known
  papers: check each entry (authors, pages, year) against the source. Papers
  marked `TODOcite` in `sections/related.tex` still have to be found and *read*.

## What produces each placeholder

| Placeholder (table/figure/macro) | Experiment | Command | File to drop in `paper/data/` |
|---|---|---|---|
| Table 1 rungs | E1 | `python scripts/benchmark.py --source <imgs> --threads 4 --frames 200 --out paper/data/e1_rungs.csv` and `python scripts/eval_agreement.py --images <imgs> --json paper/data/e1_quality.json` | `e1_rungs.csv`, `e1_quality.json` (rung names must match) |
| Fig. sustained | E2 | `python scripts/benchmark.py --rungs nominal --sustained 900 --out paper/data/e2_sustained.csv` | `e2_sustained.csv` |
| Table adaptive, Fig. traces, `\resStatic*`, `\resShade*` | E3 | `python scripts/trial.py --arm static-0 --minutes 30 --source <clip> --out paper/data/trials/static-0-run1.csv` (repeat per arm `static-0`, `static-3`, `shade`, `shade-gated`, `shade-forecast` and run number) | `trials/<arm>-run<k>.csv` (+ `.csv.db`) |
| Table swap | E4 | same trial runs (reads `swap_done` events from the `.db`) | `trials/*.db` |
| Table gating-real, `\resGateSaving`, `\resShiftGain` | E8 | `python scripts/eval_gating.py --video <clip> --every 4,8 --iou 0.5,0.75 > paper/data/e8_gating.txt` | `e8_gating.txt` |
| Table fidelity, `\resPlantR` | E7 | `python scripts/fit_plant.py paper/data/trials/shade-run1.csv --out paper/data/e7_plant.json` | `e7_plant.json` |
| Table sim, Fig. pareto, gating-synth | already real (simulation / offline) | `scripts/ablation.py`, `scripts/pareto.py`, `scripts/eval_gating.py` | `docs/results/`, `docs/gating_eval_output.txt` |

Then: `python scripts/paper_assets.py && make -C paper`.

## Experimental hygiene checklist (fill in `sections/setup.tex`)
- [ ] Same enclosure, cooler, PSU, ambient (log it) for all arms; randomise arm order; cool to baseline between runs
- [ ] >= 5 runs per arm, 30 min each; report mean and s.d.
- [ ] Commit hash, ORT version, OS/kernel recorded; models and calibration set described
- [ ] Clips: description, static-time fraction, licence; labels or agreement protocol stated
- [ ] Report failures and any arm where adaptation did not help
- [ ] Release data and scripts; archive with a DOI before submission
- [ ] Re-check every claim in abstract/intro against the final tables
