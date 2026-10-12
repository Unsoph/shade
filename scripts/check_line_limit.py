"""Fail if any source file exceeds the project's line limit (CLAUDE.md)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 150
SKIP = {".git", "__pycache__", ".venv", "venv", "models", "logs", "benchmarks"}
SUFFIXES = {".py", ".yaml", ".yml"}


def offenders(root: Path = ROOT, limit: int = LIMIT):
    for path in sorted(root.rglob("*")):
        if path.suffix in SUFFIXES and not SKIP & set(path.relative_to(root).parts):
            n = len(path.read_text().splitlines())
            if n > limit:
                yield path.relative_to(root), n


def main() -> int:
    bad = list(offenders())
    for path, n in bad:
        print(f"{path}: {n} lines (limit {LIMIT})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
