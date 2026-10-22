"""LaTeX cell formatting shared by the table generators."""

import statistics as st

TBD = r"\TBD{}"


def num(x, digits: int = 1) -> str:
    return TBD if x is None else f"{x:.{digits}f}"


def mean_sd(values: list[float], digits: int = 1) -> str:
    if not values:
        return TBD
    if len(values) == 1:
        return f"{values[0]:.{digits}f}"
    return f"{st.mean(values):.{digits}f}$\\pm${st.stdev(values):.{digits}f}"


def table(caption: str, label: str, header: list[str], rows: list[list[str]],
          note: str = "", wide: bool = False) -> str:
    env = "table*" if wide else "table"
    cols = "l" + "r" * (len(header) - 1)
    body = "\n".join(" & ".join(r) + r" \\" for r in rows)
    foot = f"\n\\par\\smallskip\\footnotesize {note}" if note else ""
    return (f"\\begin{{{env}}}[t]\n\\centering\\small\n"
            f"\\caption{{{caption}}}\\label{{{label}}}\n"
            f"\\begin{{tabular}}{{{cols}}}\n\\toprule\n"
            f"{' & '.join(header)} \\\\\n\\midrule\n{body}\n\\bottomrule\n"
            f"\\end{{tabular}}{foot}\n\\end{{{env}}}\n")
