"""Scénarios du banc simulé et appuis joués (lot X33) : scénarios lisibles, clés connues, vérifications
tirées des scénarios sur des journaux fabriqués, cas négatifs. Sans Godot : `sim_bench_inputs.py` est pur."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import pytest

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(ENGINE_TESTS))

import sim_bench  # noqa: E402
import sim_bench_inputs as si  # noqa: E402
from openride_core import powerups  # noqa: E402

T0 = 1_000_000.0


def _records(spec: list[tuple[float, int, float, int]]) -> list[dict]:
    """(t, biais, cible, bloc) -> lignes `record` du journal de séance, une par seconde."""
    return [{"kind": "record", "ts": T0 + t, "erg_bias_pct": b, "target_w": w, "block": blk, "speed": 9.0}
            for t, b, w, blk in spec]


@pytest.mark.parametrize("name", sorted(sim_bench.bench_scenarios()))
def test_every_bench_scenario_resolves(name: str) -> None:
    sname, spec, settings, _ = sim_bench.resolve_scenario(name)
    assert sname == name and isinstance(spec.get("events", []), list)
    for x in settings["inputs"]:
        assert set(x) <= si.INPUT_KEYS
    for x in settings["expect"]:
        assert set(x) <= si.EXPECT_KEYS


def test_biome_scenarios_force_known_biomes() -> None:
    """Lot U17 : un scénario `biome_<id>` par biome mesuré, chacun forçant un biome du thème par défaut ;
    les six du premier jalon (U-Q5) sont là."""
    theme = json.loads((ENGINE_TESTS.parent / "themes" / "default" / "theme.json").read_text(encoding="utf-8"))
    names = [n for n in sim_bench.bench_scenarios() if n.startswith("biome_")]
    for name in names:
        _, _, settings, _ = sim_bench.resolve_scenario(name)
        assert settings["biome"] == name.removeprefix("biome_") and settings["biome"] in theme["biomes"]
    first = {"temperate_grassland", "temperate_forest", "farmland", "alpine", "mediterranean", "coast"}
    assert first <= {n.removeprefix("biome_") for n in names}


def test_x33_scenarios_cover_the_recipes() -> None:
    _, spec, settings, _ = sim_bench.resolve_scenario("serie_t")
    presses = [e for e in spec["events"] if e["action"] == "press"]
    assert presses and all(e["button"] == "Z" for e in presses)      # Z au Click simulé, chemin Bluetooth
    assert settings["powerups"]["obtain"]["arch_every_m"] == 1000
    refs = {x.get("recette") for x in settings["expect"]}
    assert {"T11 §1", "T11 §2", "T11 §3"} <= refs
    _, spec, settings, _ = sim_bench.resolve_scenario("erg_boutons")
    keys = [x["key"] for x in settings["inputs"] if "key" in x]
    buttons = [x["button"] for x in settings["inputs"] if "button" in x]
    assert {"Equal", "Minus", "PageUp", "PageDown", "Z", "Y", "Escape"} <= set(keys)
    assert {"+", "-", "Z", "Y"} <= set(buttons) and settings["workout"] == "erg_court"
    assert {x["recette"] for x in settings["inputs"]} == {"J7 au Click", "J7 au clavier"}
    assert any(x.get("journal") == "powerup" and x.get("max") == 0 for x in settings["expect"])
    _, _, settings, _ = sim_bench.resolve_scenario("course_bots")
    assert len(settings["bot_profiles"]) == 4


def test_powerups_table_is_valid_toml_for_the_core(tmp_path: Path) -> None:
    text = sim_bench.toml_text({"obtain": {"arch_every_m": 1000, "per_segment": True}})
    assert tomllib.loads(text) == {"obtain": {"arch_every_m": 1000, "per_segment": True}}
    (tmp_path / "powerups.toml").write_text(text, encoding="utf-8")
    assert powerups.load_table(tmp_path / "powerups.toml").arch_every_m == 1000


@pytest.mark.parametrize("bad, msg", [
    ([{"t": 1, "key": "Z", "button": "Z"}], "l'un des deux"),
    ([{"t": 1}], "l'un des deux"),
    ([{"t": 1, "button": "Q"}], "inconnu"),
    ([{"t": 1, "key": "Y", "state": "STOPPED"}], "PAUSED ou RUNNING"),
    ([{"t": 1, "key": "Y", "couleur": 1}], "inconnue"),
    ([{"t": -1, "key": "Y"}], "temps"),
    ([{"t": 1, "key": "Equal", "bias": 2.5}], "entier"),
])
def test_bad_inputs_are_named(bad: list, msg: str) -> None:
    with pytest.raises(si.InputsError, match=msg):
        si.validate_inputs(bad)


@pytest.mark.parametrize("bad, msg", [
    ([{"journal": "segment", "log": "core", "motif": "x"}], "une seule"),
    ([{"log": "gpu", "motif": "x"}], "core ou engine"),
    ([{"file": "OpenRide/records.json"}], "contains"),
    ([{"widget": "x", "seuil": 2}], "inconnue"),
])
def test_bad_expectations_are_named(bad: list, msg: str) -> None:
    with pytest.raises(si.InputsError, match=msg):
        si.validate_expect(bad)


def test_click_buttons_become_press_events() -> None:
    inputs = si.validate_inputs([{"t": 9, "key": "Z"}, {"t": 5, "button": "+", "duration_s": 1.2, "bias": 10}])
    assert [x["t"] for x in inputs] == [5, 9]
    assert si.click_events(inputs) == [{"t": 5.0, "action": "press", "button": "+", "duration_s": 1.2}]


def test_bias_block_and_pause_checks_pass_on_a_good_journal() -> None:
    rows = _records([(68, 0, 250, 2), (69, 0, 250, 2), (72, 2, 255, 2), (73, 2, 255, 2),
                     (88, 2, 255, 2), (90, 2, 255, 3), (91, 2, 255, 3)])
    rows.append({"kind": "event", "ts": T0 + 101.2, "event": "pause"})
    inputs = si.validate_inputs([
        {"t": 70, "key": "Equal", "hold_ms": 150, "bias": 2, "recette": "J7 c"},
        {"t": 88.5, "button": "Z", "block": 1},
        {"t": 101, "key": "Y", "state": "PAUSED"},
    ])
    checks = si.input_checks(inputs, rows, T0, ["Equal", "Y"])
    assert all(ok for ok, _, _ in checks), checks
    assert checks[0][1].startswith("[J7 c] touche Equal 150 ms à 70 s")
    assert "rapport 1.020" in checks[1][2]


def test_keyboard_cut_from_the_core_fails_on_the_key_presses() -> None:
    """Critère 2 : l'engine joue la touche (« key done ») mais n'envoie pas `input_event` : le biais ne bouge pas."""
    rows = _records([(68, 0, 250, 2), (69, 0, 250, 2), (72, 0, 250, 2), (73, 0, 250, 2)])
    checks = si.input_checks(si.validate_inputs([{"t": 70, "key": "Equal", "bias": 2}]), rows, T0, ["Equal"])
    assert [ok for ok, _, _ in checks] == [True, False]
    assert "biais +0 → +0 %" in checks[1][2]


def test_wrong_ratio_missing_samples_and_unplayed_key_fail() -> None:
    rows = _records([(68, 0, 250, 2), (69, 0, 250, 2), (72, 2, 270, 2)])
    ok, _, measure = si.input_checks(si.validate_inputs([{"t": 70, "button": "+", "bias": 2}]), rows, T0, [])[0]
    assert not ok and "attendu 1.020" in measure
    ok, _, measure = si.input_checks(si.validate_inputs([{"t": 200, "button": "+", "bias": 2}]), rows, T0, [])[0]
    assert not ok and "pas d'échantillon" in measure
    checks = si.input_checks(si.validate_inputs([{"t": 70, "key": "Z"}]), rows, T0, [])
    assert checks == [(False, "touche Z à 70 s : touche jouée par l'engine", "aucun « key done »")]
    rows = _records([(68, 0, 250, 2), (69, 0, 250, 2), (72, 2, 150, 3)])
    ok, _, measure = si.input_checks(si.validate_inputs([{"t": 70, "button": "+", "bias": 2}]), rows, T0, [])[0]
    assert not ok and "bloc changé" in measure


def test_expectations_on_journal_logs_screen_and_files(tmp_path: Path) -> None:
    rows = [{"kind": "segment", "segment_id": "climb1", "pr": True}, {"kind": "powerup", "ts": T0 + 20, "powerup": "aero"}]
    rows += _records([(t, 0, 0, 0) for t in range(10, 40)])
    (tmp_path / "OpenRide").mkdir()
    (tmp_path / "OpenRide" / "records.json").write_text(json.dumps({"demo": {"climb1": []}}), encoding="utf-8")
    shots = [{"file": "001.png", "widgets": {"bonus_held": "Z : Aéro"}}, {"file": "002.png", "widgets": {}}]
    expect = si.validate_expect([
        {"journal": "segment", "where": {"segment_id": "climb1"}, "recette": "T11 §1"},
        {"journal": "segment", "where": {"segment_id": "sprint1"}},
        {"journal": "powerup", "max": 0},
        {"log": "engine", "motif": r"\[test\] event_sound kind=", "min": 1},
        {"widget": "bonus_held", "contains": "Aéro"},
        {"file": "OpenRide/records.json", "contains": ["climb1", "sprint1"]},
        {"bonus_speed": 15},
    ])
    checks = si.expect_checks(expect, rows, "", "[test] event_sound kind=segment_pr\n", shots, tmp_path, T0)
    assert [ok for ok, _, _ in checks] == [True, False, False, True, True, False, None]
    assert checks[0][1].startswith("[T11 §1] ")
    assert checks[2][2] == "1 (au plus 0 attendu)"
    assert checks[5][2] == "manque sprint1"
    assert "aero à 20 s : 32.4 → 32.4 km/h" in checks[6][2]


def test_keys_done_reads_the_engine_log() -> None:
    log = "[test] key done=Equal shift=false hold_ms=150\nautre\n[test] key done=PageUp shift=false hold_ms=150\n"
    assert si.keys_done(log) == ["Equal", "PageUp"]
