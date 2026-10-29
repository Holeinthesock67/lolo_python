"""Saccades et temps de démarrage (lot X15) : fichiers de l'engine fabriqués, résumé et rapport."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "engine" / "tests" / "perf_probe.py"
spec = importlib.util.spec_from_file_location("perf_probe", SCRIPT)
pp = importlib.util.module_from_spec(spec)
sys.modules["perf_probe"] = pp
spec.loader.exec_module(pp)

SAC_HEAD = "t_s;unix_s;frame_ms;distance_m;cause;steps"


def engine_dir(tmp_path, saccades, tasks=(), startup="Démarrage : première image jouable à 8421 ms"):
    d = tmp_path / "moteur"
    d.mkdir()
    (d / "moteur.csv").write_text("t_s;unix_s;fps;frame_max_ms;preset\n1.00;1000.00;60.00;45.00;low\n", encoding="utf-8")
    (d / "saccades.csv").write_text("\n".join([SAC_HEAD, *saccades]) + "\n", encoding="utf-8")
    (d / "taches.csv").write_text("\n".join(["t_s;kind;id;ms", *tasks]) + "\n", encoding="utf-8")
    if startup is not None:
        (d / "demarrage.txt").write_text(startup + "\n", encoding="utf-8")
    return d


def test_causes_counted_and_worst_first(tmp_path):
    rows = [f"{i}.0;1000.0;{35 + i:.1f};{100 * i:.1f};tuile;tuile near:{i}:0 {20 + i:.1f}" for i in range(25)]
    rows += ["30.0;1030.0;180.0;3000.0;osm;osm 4 150.0 | tuile near:9:9 3.0", "31.0;1031.0;60.0;3100.0;inconnue;"]
    st = pp.stall_summary(pp.read_stalls(engine_dir(tmp_path, rows)))
    assert st["count"] == 27 and st["startup_ms"] == 8421.0
    assert list(st["causes"]) == ["tuile", "osm", "inconnue"]
    assert st["causes"]["tuile"]["count"] == 25 and st["causes"]["tuile"]["worst_ms"] == 59.0
    assert len(st["top"]) == pp.STALL_TOP and st["top"][0]["cause"] == "osm" and st["top"][1]["frame_ms"] == 60.0


def test_background_task_durations_per_kind(tmp_path):
    tasks = [f"1.0;arbres;{i}:0;{10 + i:.2f}" for i in range(10)] + ["2.0;osm;3;250.00"]
    st = pp.stall_summary(pp.read_stalls(engine_dir(tmp_path, [], tasks)))
    assert st["count"] == 0 and st["tasks"]["osm"] == {"count": 1, "p50": 250.0, "p99": 250.0, "max": 250.0}
    assert st["tasks"]["arbres"]["count"] == 10 and st["tasks"]["arbres"]["max"] == 19.0


def test_report_lists_stalls_and_startup(tmp_path):
    d = engine_dir(tmp_path, ["5.0;1005.0;92.0;512.0;arbres;arbres near:1:2 70.0"], ["5.0;near;1:2;41.00"])
    out = tmp_path / "rapport"
    summary = pp.write_report(pp.read_engine_csv(d / "moteur.csv"), out, engine_dir=d)
    text = (out / "sonde.txt").read_text(encoding="utf-8")
    assert "première image jouable à 8.4 s" in text and "Saccades (images de plus de 33 ms) : 1" in text
    assert "arbres : arbres near:1:2 70.0" in text and "512 m" in text
    assert summary["stalls"]["causes"]["arbres"]["count"] == 1
    assert (out / "saccades.csv").is_file() and (out / "demarrage.txt").is_file()


def test_older_engine_without_files_and_no_startup(tmp_path):
    assert pp.read_stalls(tmp_path) is None
    st = pp.stall_summary(pp.read_stalls(engine_dir(tmp_path, [], startup=None)))
    assert st["startup_ms"] is None and "pas de première image jouable" in pp.stall_text(st)


def test_report_command_reads_the_engine_folder(tmp_path, capsys):
    d = engine_dir(tmp_path, ["5.0;1005.0;40.0;10.0;capture;"])
    assert pp.main(["report", str(d / "moteur.csv"), "--out", str(tmp_path / "r")]) == 0
    assert "capture" in capsys.readouterr().out
