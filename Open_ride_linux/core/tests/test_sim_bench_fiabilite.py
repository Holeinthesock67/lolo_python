"""Fiabilité du banc simulé (lot X35) : captures comptées après le chargement, images des captures hors
p99, couches du compilateur vérifiées avant de construire le monde, vitesse imposée au trainer simulé."""

import importlib.util
import sys
from pathlib import Path

import pytest

from openride_core import sim_scenarios

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sb = _load("sim_bench")
pp = sys.modules["perf_probe"]


def shot(tag: str, ok: bool = True, early: bool = False, delay: float | None = 0.4, retried: bool = False) -> dict:
    return {"tag": tag, "ok": ok, "early": early, "delay_s": delay if ok else None, "retried": retried}


# --- captures -----------------------------------------------------------------------------------

def test_captures_requested_while_loading_do_not_count():
    # Le faux échec du 28 octobre : « 49/51 », les deux manquantes demandées pendant le chargement.
    shots = [shot("t003", ok=False, early=True), shot("ev0_trainer_drop", ok=False, early=True)]
    shots += [shot(f"t{t:03d}") for t in range(8, 400, 8)]
    ok, msg = sb.capture_check(shots)
    assert ok is True
    assert msg.startswith("49/49 images enregistrées après le chargement (+2 avant, hors compte : 0 enregistrée(s))")


def test_missing_capture_after_loading_still_fails_and_retries_are_reported():
    shots = [shot("t008"), shot("t016", retried=True, delay=5.6), shot("t024", ok=False, retried=True)]
    ok, msg = sb.capture_check(shots)
    assert ok is False
    assert "2/3 images" in msg and "2 redemandée(s)" in msg and "5.60 s au pire" in msg
    assert sb.capture_check([])[0] is False


def test_shot_caption_tells_delay_retry_and_loading():
    assert sb.shot_timing(shot("t008", delay=0.25)) == " · réponse en 0.25 s"
    assert sb.shot_timing(shot("t003", ok=False, early=True, retried=True)) == (
        " · pas de réponse · redemandée · avant la fin du chargement")


# --- images des captures dans la sonde ------------------------------------------------------------

def test_probe_summary_counts_capture_frames_apart(tmp_path: Path):
    head = "t_s;unix_s;fps;frame_p50_ms;frame_p99_ms;frame_max_ms;capture;capture_max_ms;preset"
    rows = [head] + [f"{i + 1}.00;{1000 + i}.00;60.00;16.60;18.00;19.00;{3 if i % 15 == 0 else 0};"
                     f"{148.0 if i % 15 == 0 else 0.0:.2f};low" for i in range(60)]
    src = tmp_path / "moteur.csv"
    src.write_text("\n".join(rows) + "\n", encoding="utf-8")
    summary = pp.write_report(pp.read_engine_csv(src), tmp_path / "r")
    assert summary["stats"]["frame_max_ms"]["max"] == 19.0          # le pic de 148 ms n'est pas une saccade
    assert summary["captures"] == {"frames": 12, "max_ms": 148.0}
    assert "Images des captures d'écran mises à part : 12 (pire 148 ms)" in (tmp_path / "r" / "sonde.txt").read_text(
        encoding="utf-8")


def test_endurance_stutters_name_capture_spikes_apart():
    rows = [{"t_s": float(t), "fps": 60.0, "frame_max_ms": 20.0, "capture_max_ms": 150.0 if t % 60 == 0 else 0.0}
            for t in range(0, 900)]
    checks = {label: (ok, msg) for ok, label, msg in pp.endurance_checks(rows, real_window=True)}
    ok, msg = checks["endurance : saccades"]
    assert ok is True
    assert msg.startswith("0 seconde(s)") and "10 autre(s) due(s) aux captures d'écran" in msg


def test_old_probe_files_without_capture_columns_still_read(tmp_path: Path):
    src = tmp_path / "moteur.csv"
    src.write_text("t_s;unix_s;fps;frame_max_ms;preset\n1.00;1000.00;60.00;19.00;low\n", encoding="utf-8")
    summary = pp.summarize(pp.read_engine_csv(src))
    assert "captures" not in summary


# --- couches du compilateur ----------------------------------------------------------------------

def test_unknown_layer_is_named():
    assert sb.missing_layers(("route", "terrain", "roads"), ("route", "terrain", "buildings")) == ["roads"]
    assert sb.missing_layers(("route",), ("route", "terrain")) == []


def test_old_compiler_stops_the_bench_with_code_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sb, "compiler_problem", lambda wanted: "compilateur installé trop ancien : couche(s) roads "
                        "inconnue(s) ; réinstaller (`pip install -e compiler`)")
    with pytest.raises(SystemExit) as exc:
        sb.prepare_world("osm", tmp_path / "routes", tmp_path)
    assert exc.value.code == 2
    assert "ÉCHEC monde osm : compilateur installé trop ancien" in capsys.readouterr().err


def test_world_layers_come_from_the_world_scripts():
    assert sb.world_layers("osm")[:2] == ("route", "terrain") and "roads" in sb.world_layers("osm")
    assert "roads" not in sb.world_layers("village") and "buildings" in sb.world_layers("village")


def test_installed_compiler_knows_every_bench_layer():
    pytest.importorskip("openride_compiler")
    assert sb.compiler_problem(sb.world_layers("village")) == ""
    assert sb.compiler_problem(sb.world_layers("osm")) == ""


# --- vitesse imposée -------------------------------------------------------------------------------

def test_target_speed_is_the_rider_speed_strategy():
    # La puissance de la stratégie `vitesse` (sim_rider.py, lot X27) est vérifiée dans test_sim_rider.py.
    spec = sim_scenarios.validate({"trainer": {}, "rider": {"strategy": "vitesse", "speed_kmh": 35}})
    assert sim_scenarios.build_world(spec).trainer.rider.speed_kmh == 35.0
    with pytest.raises(sim_scenarios.SimScenarioError, match="entre 0 et 80"):
        sim_scenarios.validate({"rider": {"strategy": "vitesse", "speed_kmh": 0}})
    with pytest.raises(sim_scenarios.SimScenarioError, match="nombre attendu"):
        sim_scenarios.validate({"rider": {"strategy": "vitesse", "speed_kmh": "35"}})


def test_speed_check_on_journal_records():
    recs = [{"ts": 1000.0 + i, "speed": (i / 20 if i < 20 else 1.0) * 35 / 3.6} for i in range(60)]
    ok, msg = sb.speed_check(recs, 35.0)
    assert ok is True and msg.startswith("médiane 35.0 km/h sur 40 s")
    assert sb.speed_check([{"ts": 1000.0 + i, "speed": 21 / 3.6} for i in range(60)], 35.0)[0] is False
    assert sb.speed_check([], 35.0) == (False, "aucun échantillon de vitesse au journal")


def _args(**kw):
    base = dict(world="demo", workout=None, difficulty=None, duration=40.0, every=None, probe=False, speed_kmh=None)
    base.update(kw)
    return type("A", (), base)()


def test_bench_with_speed_rides_at_difficulty_100_with_a_written_scenario(tmp_path):
    spec = sim_scenarios.load_scenario("nominal")
    b = sb.Bench(_args(speed_kmh=35.0), "nominal", spec, {}, "nominal", tmp_path)
    assert b.difficulty == 100.0 and b.scenario_arg == ""
    assert b.spec["rider"] == {"strategy": "vitesse", "speed_kmh": 35.0}
    assert "rider" not in spec   # scénario d'origine intact
    with pytest.raises(SystemExit, match="difficulté 100 %"):
        sb.Bench(_args(speed_kmh=35.0, difficulty=50.0), "nominal", spec, {}, "nominal", tmp_path)
    assert sb.Bench(_args(), "nominal", spec, {"speed_kmh": 30}, "nominal", tmp_path).speed_kmh == 30
