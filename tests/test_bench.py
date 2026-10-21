import csv
import importlib.util
from pathlib import Path

from src.bench.matching import iou, load_yolo_labels, match, prf
from src.bench.stats import percentile, summarize
from src.inference.detection import Detection

ROOT = Path(__file__).resolve().parent.parent


def det(x1, y1, x2, y2, cid=0, conf=0.9):
    return Detection(x1, y1, x2, y2, conf, cid, "x")


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([], 95) == 0.0
    assert percentile([5], 99) == 5


def test_summarize_fps():
    s = summarize([100.0, 100.0], detect_every=2)
    assert s["det_fps"] == 10.0 and s["eff_fps"] == 20.0 and s["std_ms"] == 0
    assert summarize([]) == {"n": 0}


def test_iou_and_match():
    a = det(0, 0, 10, 10)
    assert iou(a, a) == 1.0
    assert iou(a, det(20, 20, 30, 30)) == 0.0
    assert match([a], [det(0, 0, 10, 10)]) == (1, 0, 0)
    assert match([a], [det(0, 0, 10, 10, cid=1)]) == (0, 1, 1)  # class matters
    assert match([a, a], [a]) == (1, 1, 0)                       # one-to-one


def test_prf():
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)
    p, r, f = prf(2, 2, 0)
    assert (p, r) == (0.5, 1.0) and abs(f - 2 / 3) < 1e-9


def test_load_yolo_labels(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("0 0.5 0.5 0.5 0.5\n")
    (d,) = load_yolo_labels(f, 100, 200)
    assert (d.x1, d.y1, d.x2, d.y2) == (25, 50, 75, 150)


def test_benchmark_script_fake(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "benchmark", ROOT / "scripts" / "benchmark.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / "b.csv"
    assert mod.main(["--fake", "--frames", "3", "--warmup", "1",
                     "--rungs", "nominal,small-320", "--out", str(out)]) == 0
    rows = list(csv.DictReader(open(out)))
    assert [r["rung"] for r in rows] == ["nominal", "small-320"]
    assert float(rows[0]["p50_ms"]) > float(rows[1]["p50_ms"])


def test_pareto_drops_dominated_rungs():
    spec = importlib.util.spec_from_file_location(
        "build_ladder", ROOT / "scripts" / "build_ladder.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = [
        {"name": "a", "eff_fps": 5, "quality": 1.0, "p95_ms": 200},
        {"name": "b", "eff_fps": 9, "quality": 0.9, "p95_ms": 120},
        {"name": "c", "eff_fps": 8, "quality": 0.8, "p95_ms": 130},  # dominated by b
        {"name": "d", "eff_fps": 14, "quality": 0.6, "p95_ms": 70},
    ]
    assert [r["name"] for r in mod.pareto(rows)] == ["a", "b", "d"]
