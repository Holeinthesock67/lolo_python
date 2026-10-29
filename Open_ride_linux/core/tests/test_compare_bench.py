"""Comparateur avant/après (lot X14) et référence de performance."""

import importlib.util
import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pp = _load("perf_probe")
cb = _load("compare_bench")
ref = _load("perf_reference")

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def bench(root: Path, fps: float, p99: float = 18.0, scen: str = "nominal", preset: str = "medium",
          shots=("000_t008.png",)) -> Path:
    d = root / scen
    (d / "sonde").mkdir(parents=True)
    head = "t_s;unix_s;fps;frame_p99_ms;gpu_ms;draw_calls;primitives;preset"
    lines = [head] + [f"{i}.00;{1000 + i}.00;{20.0 if i < 15 else fps:.2f};{p99:.2f};8.00;400;1400000;{preset}"
                      for i in range(60)]
    (d / "sonde" / "sonde.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s in shots:
        (d / s).write_bytes(PNG)
    return root


def test_noise_is_same_and_ten_percent_drop_is_worse():
    assert cb.verdict(60.0, 59.0, True, 3.0) == ("pareil", -1.6666666666666667)
    assert cb.verdict(60.0, 54.0, True, 3.0)[0] == "moins bien"
    assert cb.verdict(20.0, 18.0, False, 3.0)[0] == "mieux"
    assert cb.verdict(0.0, 0.0, False, 3.0) == ("pareil", 0.0)


def test_compare_two_benches_pairs_captures_and_writes_report(tmp_path):
    before = bench(tmp_path / "avant", 60.0, shots=("000_t008.png", "001_t023.png"))
    after = bench(tmp_path / "apres", 54.0, shots=("000_t008.png", "002_fin.png"))
    assert cb.main([str(before), str(after)]) == 1
    page = (after / "comparaison" / "comparaison.html").read_text(encoding="utf-8")
    assert "Captures (1 paires)" in page and "nominal/000_t008.png" in page
    assert "Sans pendant de l'autre côté : nominal/001_t023.png, nominal/002_fin.png" in page
    rows = (after / "comparaison" / "ecarts.csv").read_text(encoding="utf-8").splitlines()
    assert "nominal;fps;60.000;54.000;-10.0;moins bien" in rows
    assert "nominal;p99_ms;18.000;18.000;+0.0;pareil" in rows


def test_warmup_is_ignored_in_bench_medians(tmp_path):
    side = cb.load_side(bench(tmp_path / "a", 60.0), 20.0)
    assert side.entries["nominal"]["fps"] == 60.0 and side.presets["nominal"] == "medium"


def test_showcases_compare_view_by_view(tmp_path):
    for name, tris in (("avant", 100000), ("apres", 130000)):
        d = tmp_path / name
        d.mkdir()
        (d / "vitrine.csv").write_text("vue;préréglage;qualite_appliquee;triangles;appels_dessin;objets\n"
                                       f"route;medium;medium;{tris};300;200\n", encoding="utf-8")
        (d / "route_medium.png").write_bytes(PNG)
    assert cb.main([str(tmp_path / "avant"), str(tmp_path / "apres")]) == 1
    rows = (tmp_path / "apres" / "comparaison" / "ecarts.csv").read_text(encoding="utf-8")
    assert "route / medium;triangles;100000.000;130000.000;+30.0;moins bien" in rows
    assert "route / medium;draw_calls;300.000;300.000;+0.0;pareil" in rows


def test_different_kinds_or_nothing_in_common_is_code_2(tmp_path):
    bench(tmp_path / "a", 60.0)
    v = tmp_path / "v"
    v.mkdir()
    (v / "vitrine.csv").write_text("vue;préréglage;triangles\nroute;low;1\n", encoding="utf-8")
    assert cb.main([str(tmp_path / "a"), str(v)]) == 2
    bench(tmp_path / "b", 60.0, scen="autre")
    assert cb.main([str(tmp_path / "a"), str(tmp_path / "b")]) == 2
    assert cb.main([str(tmp_path / "a"), str(tmp_path / "rien")]) == 2


def test_reference_alerts_on_fps_drop_and_p99_rise():
    reference = {"runs": {"village/medium": {"metrics": {"fps": 60.0, "p99_ms": 18.0}, "preset": "medium"}}}
    ok = {"runs": {"village/medium": {"metrics": {"fps": 58.0, "p99_ms": 18.8}, "preset": "medium"}}}
    assert ref.alerts(ok, reference) == []
    bad = {"runs": {"village/medium": {"metrics": {"fps": 55.0, "p99_ms": 19.5}, "preset": "low"}}}
    found = ref.alerts(bad, reference)
    assert len(found) == 3 and "−8.3 %" in found[0] and "+1.5 ms" in found[1] and "préréglage appliqué low" in found[2]


def test_reference_compare_and_update(tmp_path, capsys):
    run = tmp_path / "passage"
    run.mkdir()
    result = {"date": "2026-10-28 10:00", "native": True,
              "runs": {"demo/low": {"metrics": {"fps": 60.0, "p99_ms": 17.0}, "preset": "low"}}}
    (run / "resultat.json").write_text(json.dumps(result), encoding="utf-8")
    reference = tmp_path / "perf" / "reference.json"
    assert ref.main(["--reference", str(reference), "compare", str(run)]) == 0
    assert "Pas de référence" in capsys.readouterr().out
    assert ref.main(["--reference", str(reference), "update", str(run)]) == 0
    result["runs"]["demo/low"]["metrics"]["fps"] = 50.0
    (run / "resultat.json").write_text(json.dumps(result), encoding="utf-8")
    assert ref.main(["--reference", str(reference), "compare", str(run)]) == 1
    assert "[ÉCHEC] demo/low : images/s 60.0 → 50.0" in capsys.readouterr().out
    result["native"] = False   # sous Xvfb : en INFO
    (run / "resultat.json").write_text(json.dumps(result), encoding="utf-8")
    assert ref.main(["--reference", str(reference), "compare", str(run)]) == 0
    assert ref.main(["--reference", str(reference), "update", str(run)]) == 0
    assert len(list(reference.parent.glob("reference-*.json"))) == 1   # ancienne référence gardée


def test_bench_command_is_the_simulated_bench_with_probe(tmp_path):
    cmd = ref.bench_command("godot", "village", "medium", 30, tmp_path, False)
    assert cmd[1].endswith("sim_bench.py") and "--probe" in cmd and "--native" not in cmd
    assert cmd[cmd.index("--quality") + 1] == "medium" and cmd[cmd.index("--world") + 1] == "village"
