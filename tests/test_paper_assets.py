from scripts.paper_lib import figures, numbers, tables


def test_every_table_renders_and_missing_data_shows_tbd():
    for name, fn in tables.ALL.items():
        text = fn()
        assert "\\begin{table" in text and "\\end{table" in text, name
    assert "\\TBD" in tables.t_adaptive()   # no hardware trials in the repo


def test_numbers_define_all_macros():
    text = numbers.build()
    for macro in ("resStaticThrottled", "resShadePfive", "resGateSaving",
                  "simGateSaving", "simShiftGain"):
        assert f"\\newcommand{{\\{macro}}}" in text
    assert "\\%" in text and "%}" not in text.replace("\\%", "")  # escaped


def test_figure_names():
    assert set(figures.ALL) == {"f_sustained", "f_traces", "f_pareto", "f_gating"}
