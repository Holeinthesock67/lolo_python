"""Séances guidées sur le HomeTrainer (tools/seance_guidee.py) : parcours, consignes, entraînement."""

from __future__ import annotations

import json

from openride_core.route import load_world
from openride_core.tools import seance_guidee as sg
from openride_core.workout import list_workouts, load_workout


def _write(tmp_path):
    dirs = (tmp_path / "routes", tmp_path / "Essais", tmp_path / "Workouts")
    return dirs, sg.write_all(*dirs, terrain=False)


def test_write_all_routes_cues_and_workout(tmp_path):
    (routes, essais, workouts), written = _write(tmp_path)
    assert len(written) == 5
    for name, length_m, cues, _ in sg.SESSIONS:
        world = load_world(routes / f"{name}.world")
        assert world.route.length_m == length_m
        data = json.loads((essais / f"{name}.consignes.json").read_text(encoding="utf-8"))
        assert len(data["cues"]) == len(cues)
    infos = list_workouts(workouts)
    assert [i.id for i in infos] == [sg.ERG_WORKOUT]


def test_cues_fit_in_the_session_and_warn_only_with_something_to_prepare():
    for _, _, cues, minutes in sg.SESSIONS:
        times = [c[0] for c in cues]
        assert times == sorted(times) and times[0] == 0
        assert times[-1] < minutes * 60
        assert len(set(times)) == len(times)
        for cue in sg.cues_json(cues)["cues"]:
            assert cue["text"] and cue["duration_s"] > 0
            assert ("warn_s" in cue) == ("prepare" in cue)
            if "warn_s" in cue:
                assert cue["at_s"] - cue["warn_s"] >= 0


def test_erg_cues_match_the_workout(tmp_path):
    (_, _, workouts), _ = _write(tmp_path)
    workout = load_workout(workouts / f"{sg.ERG_WORKOUT}.zwo")
    assert workout.duration_s == 13 * 60
    starts, t = [], 0.0
    for block in workout.blocks:
        starts.append((t, block))
        t += block.duration_s

    def block_at(at_s):
        return next(b for s, b in reversed(starts) if s <= at_s)

    pause = next(c for c in sg.ERG_CUES if "pause" in c[1])
    assert block_at(pause[0]).type == "interval_off"          # pause en récupération, pas en plein effort
    beep = next(c for c in sg.ERG_CUES if "bip" in c[1])
    assert any(0 < s - beep[0] <= 20 for s, _ in starts)      # annoncé juste avant un changement de bloc


def test_remove_all_cleans_up(tmp_path):
    dirs, _ = _write(tmp_path)
    (dirs[2] / "autre.zwo").write_text("garde", encoding="utf-8")
    removed = sg.remove_all(*dirs)
    assert len(removed) == 5
    assert not any((dirs[0]).iterdir()) and not any(dirs[1].iterdir())
    assert [p.name for p in dirs[2].iterdir()] == ["autre.zwo"]
    assert sg.remove_all(*dirs) == []


def test_materiel_writes_nothing(tmp_path, capsys):
    args = ["--materiel", "--routes-dir", str(tmp_path / "r"), "--essais-dir", str(tmp_path / "e"),
            "--workouts-dir", str(tmp_path / "w")]
    assert sg.main(args) == 0
    assert "ceinture" in capsys.readouterr().out
    assert not any(tmp_path.iterdir())
