"""Tests des entraînements au format GoldenCheetah `.erg` / `.mrc` (lot O9)."""

import asyncio
import logging
from pathlib import Path

import pytest
from test_workout import make_session, run

from openride_core import ipc_lists
from openride_core.tools import workouts as tools
from openride_core.workout import (
    ErgController,
    WorkoutError,
    list_workouts,
    load_workout,
    parse_workout,
    workout_path,
)
from openride_core.workout_formats import parse_erg, to_mrc

BUILTIN = Path(__file__).resolve().parents[1] / "workouts"

ERG_200 = """[COURSE HEADER]
VERSION = 2
UNITS = ENGLISH
DESCRIPTION = Palier 200 W
FTP = 250
MINUTES WATTS
[END COURSE HEADER]
[COURSE DATA]
0.00\t200
10.00\t200
[END COURSE DATA]
"""

# Marche à 5 min, rampe de 5 à 10 min, palier ; fins de ligne Windows, casse libre, tabulations
# et espaces mêlés, clé d'en-tête inconnue.
MRC_STEPS = ("[course header]\r\nVERSION = 2\r\nUNITS = ENGLISH\r\nDESCRIPTION = Marches et rampe\r\n"
             "MOOD = bon\r\nminutes percent\r\n[end course header]\r\n[COURSE DATA]\r\n"
             "0.00 50\r\n5.00\t50\r\n5.00   80\r\n10.00\t100\r\n15.00 100\r\n[END COURSE DATA]\r\n")

ZWO_SAME = """<workout_file><name>x</name><sportType>bike</sportType><workout>
<SteadyState Duration="300" Power="0.5"/><Ramp Duration="300" PowerLow="0.8" PowerHigh="1.0"/>
<SteadyState Duration="300" Power="1.0"/></workout></workout_file>"""


def targets(workout, ftp, seconds):
    erg = ErgController(workout, ftp)
    out = []
    for _ in range(seconds):
        out.append(erg.target_w)
        erg.step(1.0)
    return out


def test_mrc_matches_zwo_every_second():
    mrc = parse_erg(MRC_STEPS, "m", percent=True)
    zwo = parse_workout(ZWO_SAME, "z")
    assert [b.type for b in mrc.blocks] == ["steady", "ramp", "steady"]
    a, b = targets(mrc, 250.0, 900), targets(zwo, 250.0, 900)
    assert max(abs(x - y) for x, y in zip(a, b)) <= 1


def test_builtin_mrc_matches_builtin_zwo():
    mrc = load_workout(BUILTIN / "sweet_spot_3x10_gc.mrc")
    zwo = load_workout(BUILTIN / "sweet_spot_3x10.zwo")
    assert mrc.duration_s == zwo.duration_s == 3600.0
    a, b = targets(mrc, 250.0, 3600), targets(zwo, 250.0, 3600)
    assert max(abs(x - y) for x, y in zip(a, b)) <= 1
    assert mrc.texts[0] == (600.0, "Premier bloc sweet spot : 90 % de la FTP", 10.0)


@pytest.mark.parametrize("ftp", [150.0, 250.0, 400.0])
def test_erg_watts_ignore_ftp(ftp):
    w = parse_erg(ERG_200, "p")
    assert w.blocks[0].absolute and w.blocks[0].start_frac is None
    erg = ErgController(w, ftp)
    assert erg.target_w == 200 and erg.fraction() == pytest.approx(200 / ftp)
    erg.change_bias(5)                        # biais du Click : +10 %
    assert erg.target_w == 220


def test_erg_relative_uses_header_ftp():
    w = parse_erg(ERG_200, "p", relative=True)
    assert w.blocks[0].start_frac == pytest.approx(0.8) and not w.blocks[0].absolute
    assert ErgController(w, 300.0).target_w == 240


def test_steps_and_ramps_start_middle_end():
    w = parse_erg(MRC_STEPS, "m", percent=True)
    erg = ErgController(w, 200.0)
    checks = {0: 100, 150: 100, 299: 100, 302: 160, 450: 180, 599: 200, 750: 200, 899: 200}
    t = 0
    for at, expected in sorted(checks.items()):
        erg.step(at - t)
        t = at
        assert erg.target_w == pytest.approx(expected, abs=1), at
    # Changement de bloc lissé en 2 s (marche 100 -> 160 W à 300 s).
    erg2 = ErgController(w, 200.0)
    erg2.step(301.0)
    assert 100 < erg2.target_w < 160


def test_absolute_blocks_smooth_and_next_target():
    text = ERG_200.replace("10.00\t200\n", "10.00\t200\n10.00\t300\n12.00\t300\n")
    w = parse_erg(text, "p")
    erg = ErgController(w, 100.0)
    assert erg.next_target_w == 300
    erg.step(601.0)                           # 1 s dans le second bloc : moitié du lissage
    assert erg.target_w == 250
    erg.step(2.0)
    assert erg.target_w == 300


@pytest.mark.parametrize("body, message", [
    ("", "COURSE DATA] absente"),
    ("[COURSE DATA]\n0 100\n[END COURSE DATA]\n", "au moins deux points"),
    ("[COURSE DATA]\n0 100\n5 100\n4 100\n[END COURSE DATA]\n", "ligne 4 : temps décroissant"),
    ("[COURSE DATA]\n0 100\n5 -10\n[END COURSE DATA]\n", "ligne 3 : cible négative"),
    ("[COURSE DATA]\n0 100\n400 100\n[END COURSE DATA]\n", "ligne 3 : 400 min dépasse"),
    ("[COURSE DATA]\n0 100\n5 abc\n[END COURSE DATA]\n", "ligne 3 : la cible n'est pas un nombre"),
    ("[COURSE DATA]\n0 100\n5\n[END COURSE DATA]\n", "ligne 3 : deux colonnes"),
    ("[COURSE DATA]\n0 100\n5 100\n", "non fermée"),
    ("[COURSE DATA]\n0 100\n0 120\n[END COURSE DATA]\n", "durée totale nulle"),
    ("[COURSE DATA]\n0 2500\n5 2500\n[END COURSE DATA]\n", "ligne 2 : cible 2500 W"),
    ("0 100\n", "ligne 1 : texte hors de toute section"),
])
def test_malformed_erg(body, message):
    with pytest.raises(WorkoutError, match=message):
        parse_erg(body, "x")


def test_malformed_mrc_and_header():
    with pytest.raises(WorkoutError, match="ligne 3 : cible 400 % de la FTP"):
        parse_erg("[COURSE DATA]\n0 100\n5 400\n[END COURSE DATA]\n", "x", percent=True)
    with pytest.raises(WorkoutError, match="attend MINUTES PERCENT"):
        parse_erg(ERG_200, "x", percent=True)
    with pytest.raises(WorkoutError, match="clé FTP absente"):
        parse_erg(ERG_200.replace("FTP = 250\n", ""), "x", relative=True)


def test_unknown_header_key_is_debug(caplog):
    with caplog.at_level(logging.DEBUG, logger="workout"):
        parse_erg(MRC_STEPS, "m", percent=True)
    assert any("MOOD" in r.getMessage() and r.levelno == logging.DEBUG for r in caplog.records)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_latin1_file(tmp_path):
    p = tmp_path / "accents.erg"
    p.write_bytes(ERG_200.replace("Palier 200 W", "Échauffement doux").encode("latin-1"))
    assert load_workout(p).name == "Échauffement doux"


def test_discovery_and_conflicts(tmp_path, caplog):
    (tmp_path / "a.zwo").write_text(ZWO_SAME, encoding="utf-8")
    (tmp_path / "a.erg").write_text(ERG_200, encoding="utf-8")
    (tmp_path / "b.erg").write_text(ERG_200, encoding="utf-8")
    (tmp_path / "c.MRC").write_text(MRC_STEPS, encoding="utf-8")
    (tmp_path / "d.erg").write_text("[COURSE DATA]\n0 100\n[END COURSE DATA]\n", encoding="utf-8")
    (tmp_path / "e.txt").write_text("rien", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="workout"):
        infos = list_workouts(tmp_path)
    assert [i.id for i in infos] == ["a", "b", "c", "d"]
    assert infos[0].name == "x"                               # le .zwo gagne
    assert any("a.zwo, a.erg" in r.getMessage() for r in caplog.records)
    assert not infos[3].selectable and "deux points" in infos[3].error
    assert workout_path(tmp_path, "a").suffix == ".zwo"
    assert workout_path(tmp_path, "b").suffix == ".erg"
    assert workout_path(tmp_path, "c").name == "c.MRC"
    with pytest.raises(WorkoutError, match="introuvable"):
        workout_path(tmp_path, "e")


def test_ipc_profile_converts_absolute_watts(tmp_path):
    (tmp_path / "p.erg").write_text(ERG_200, encoding="utf-8")
    info = list_workouts(tmp_path)[0]
    assert ipc_lists.workout_info_to_dict(info, 250.0)["profile"] == [[600.0, 0.8, 0.8]]
    msgs = ipc_lists.build_workouts_messages(1, tmp_path, ftp_w=200.0)
    assert msgs[0]["items"][0]["profile"] == [[600.0, 1.0, 1.0]]


def test_tools_check_list_and_install(tmp_path, capsys):
    p = tmp_path / "p.erg"
    p.write_text(ERG_200, encoding="utf-8")
    assert tools.main(["check", str(p), "--ftp", "250"]) == 0
    out = capsys.readouterr().out
    assert "200 W (absolu)" in out and "NP 200 W" in out
    dest = tmp_path / "inst"
    assert tools.main(["install", "--dir", str(dest)]) == 0
    names = sorted(x.name for x in dest.iterdir())
    assert "tempo_2x15.erg" in names and "sweet_spot_3x10_gc.mrc" in names
    dest2 = tmp_path / "inst2"
    assert tools.main(["install", "--dir", str(dest2), "--erg-relative"]) == 0
    assert (dest2 / "tempo_2x15.mrc").is_file() and not (dest2 / "tempo_2x15.erg").exists()
    rel = load_workout(dest2 / "tempo_2x15.mrc")
    orig = load_workout(BUILTIN / "tempo_2x15.erg")
    a, b = targets(rel, 250.0, 3000), targets(orig, 250.0, 3000)   # FTP de l'en-tête : 250 W
    assert max(abs(x - y) for x, y in zip(a, b)) <= 1
    assert tools.main(["list", "--dir", str(dest)]) == 0
    assert "tempo_2x15" in capsys.readouterr().out


def test_to_mrc_round_trip():
    w = parse_erg(MRC_STEPS, "m", percent=True)
    back = parse_erg(to_mrc(w, 1.0), "m", percent=True)
    a, b = targets(back, 250.0, 900), targets(w, 250.0, 900)
    assert max(abs(x - y) for x, y in zip(a, b)) <= 1


@pytest.fixture
def erg_dir(tmp_path):
    d = tmp_path / "workouts"
    d.mkdir()
    (d / "palier.erg").write_text(ERG_200, encoding="utf-8")
    (d / "casse.erg").write_text("[COURSE DATA]\n0 100\n[END COURSE DATA]\n", encoding="utf-8")
    return d


def test_session_runs_erg_and_refuses_invalid(tmp_path, monkeypatch, erg_dir):
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, erg_dir, port=5990)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "casse"}, 2)
        assert errors[-1][0] == "workout_invalid" and "deux points" in errors[-1][1]
        s._on_command("select_workout", {"workout_id": "palier"}, 3)
        s._on_command("start", {}, 4)
        run(s, 1.0)
        assert s.state.mode == "ERG" and s.state.erg["target_w"] == 200
        assert driver.target_power_w == 200
    asyncio.run(scenario())


def test_session_erg_chosen_after_a_finished_session(tmp_path, monkeypatch, erg_dir):
    """Le menu envoie select_workout avant select_route : après une séance, le core est en FINISHED."""
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, erg_dir, port=5992)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run(s, 0.5)
        s._on_command("select_workout", {"workout_id": "palier"}, 3)
        assert errors[-1][0] == "busy" and s._workout is None   # refusé pendant la séance, et signalé
        s._on_command("end_session", {"save": False}, 4)
        run(s, 0.5)
        assert s.state.session_state == "FINISHED"
        s._on_command("select_workout", {"workout_id": "palier"}, 5)
        s._on_command("select_route", {"route_id": "demo"}, 6)
        s._on_command("start", {}, 7)
        run(s, 1.0)
        assert s.state.mode == "ERG" and s.state.erg["target_w"] == 200
        assert driver.target_power_w == 200
        s._on_command("end_session", {"save": False}, 8)
        run(s, 0.5)
        s._on_command("select_workout", {"workout_id": None}, 9)   # retour au SIM après une séance ERG
        s._on_command("select_route", {"route_id": "demo"}, 10)
        s._on_command("start", {}, 11)
        run(s, 0.5)
        assert s.state.mode == "SIM" and s.state.erg is None
    asyncio.run(scenario())
