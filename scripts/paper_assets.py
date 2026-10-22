"""Regenerate every table and figure of the paper from paper/data/.

    python scripts/paper_assets.py          # then: make -C paper

Real inputs (see paper/README.md for what produces each file):
  paper/data/e1_rungs.csv, e1_quality.json, e2_sustained.csv,
  paper/data/trials/<arm>-run<k>.csv (+ .db), e7_plant.json, e8_gating.txt
Anything absent becomes a red \\TBD or a "PENDING HARDWARE DATA" figure.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.paper_lib import figures, numbers, tables  # noqa: E402


def main() -> int:
    (ROOT / "paper" / "generated").mkdir(parents=True, exist_ok=True)
    (ROOT / "paper" / "figures").mkdir(parents=True, exist_ok=True)
    for name, fn in tables.ALL.items():
        (ROOT / "paper" / "generated" / f"{name}.tex").write_text(fn())
    (ROOT / "paper" / "generated" / "numbers.tex").write_text(numbers.build())
    for name, fn in figures.ALL.items():
        fn()
    pending = sum("TBD" in p.read_text() for p in (ROOT / "paper/generated").glob("t_*.tex"))
    print(f"Wrote {len(tables.ALL)} tables and {len(figures.ALL)} figures; "
          f"{pending} tables still contain TBD cells.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
