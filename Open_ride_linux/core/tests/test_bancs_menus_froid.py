"""Lot BF2 : banc des menus à caches de rendu vides jugé à froid (banc r1097 du 26/11 : passage « chaud » d'ea1_lac
sur un HOME neuf, départ jugé à 150 ms alors que tout se compilait)."""

import importlib.util
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
mb = _load("menu_bench")


def test_render_caches_empty_without_saved_caches_or_with_empty_dirs(tmp_path: Path) -> None:
    assert mb.render_caches_empty(None)                      # pas de --caches-rendu : HOME neuf, tout à compiler
    saved = tmp_path / "caches"
    assert mb.render_caches_empty(saved)                      # dossier pas encore créé
    (saved / mb.RENDER_CACHES[0]).mkdir(parents=True)
    assert mb.render_caches_empty(saved)                      # dossiers sans fichier
    (saved / mb.RENDER_CACHES[0] / "pipelines.bin").write_bytes(b"x")
    assert not mb.render_caches_empty(saved)


def test_probe_paths_read_from_engine_arguments() -> None:
    cmd = ["godot", "--path", "engine", "--", "--perf-probe=/tmp/x/moteur.csv", "--test-mode"]
    assert mb.probe_paths(cmd) == [Path("/tmp/x/moteur.csv")]
    assert mb.probe_paths(["godot", "--test-mode"]) == []


def test_shaders_mark_round_trip_and_unknown_value(tmp_path: Path) -> None:
    assert pp.read_shaders_mark(tmp_path) is None
    pp.write_shaders_mark(tmp_path / "sortie", "froid")
    assert pp.read_shaders_mark(tmp_path / "sortie") == "froid"
    (tmp_path / "sortie" / pp.SHADERS_MARK).write_text("tiède\n", encoding="utf-8")
    assert pp.read_shaders_mark(tmp_path / "sortie") is None


def test_report_uses_the_bench_mark_unless_given(tmp_path: Path, monkeypatch) -> None:
    csv = tmp_path / "moteur.csv"
    csv.write_text("t_s;unix_s;fps;frame_p50_ms;frame_p99_ms;preset\n"
                   + "".join(f"{i}.0;{1_000_000 + i}.0;60.0;16.6;18.0;medium\n" for i in range(1, 40)), encoding="utf-8")
    seen = []
    real = pp.write_report

    def spy(rows, out, *args, **kw):
        seen.append(kw.get("shaders"))
        return real(rows, out, *args, **kw)

    monkeypatch.setattr(pp, "write_report", spy)
    assert pp.main(["report", str(csv), "--out", str(tmp_path / "a")]) == 0
    pp.write_shaders_mark(tmp_path, "froid")
    assert pp.main(["report", str(csv), "--out", str(tmp_path / "b")]) == 0
    assert pp.main(["report", str(csv), "--out", str(tmp_path / "c"), "--shaders", "chaud"]) == 0
    assert seen == ["chaud", "froid", "chaud"]


def test_cold_mark_judges_start_at_one_second() -> None:
    rows = [{"t_s": float(i), "fps": 60.0, "frame_p99_ms": 18.0, "frame_max_ms": 18.0, "preset": "medium"}
            for i in range(180)]
    rows[25]["frame_max_ms"] = 700.0      # départ, pipelines du décor compilés à froid
    start = {label.split(" : ")[1]: ok for ok, label, _ in pp.hitch_checks(rows, shaders="froid")}["départ"]
    assert start is True
