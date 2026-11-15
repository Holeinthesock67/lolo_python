"""Lot EP1 : séance verrouillée au lancement (`run --autostart --seance FICHIER`)."""

import asyncio
import json

import pytest

from openride_core import __main__ as cli
from openride_core import fit_export, seance_file, velodrome
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.input_providers import NullProvider
from openride_core.ipc_server import IpcServer
from openride_core.mock_driver import MockDriver
from openride_core.session import AutostartError, CoreSession


@pytest.fixture
def routes(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    root = tmp_path / "routes"
    write_world(root, "col", 3000.0)
    velodrome.write_velodrome(root)
    return root


def make_session(tmp_path, routes, port, bots=None):
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    cfg.depart.mode = "immediat"
    return CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], bots=bots,
                       journal_dir=tmp_path / "journal", routes_root=routes, workouts_dir=tmp_path / "wk")


def run_until_first_state(s: CoreSession, commands):
    seen = []

    def capture(state):
        d = state.to_dict() if hasattr(state, "to_dict") else dict(vars(state))
        d["_rogue"], d["_track"], d["_bots"] = s.rogue is not None, s.track_event is not None, list(s.bots)
        seen.append(d)
        s.stop_event.set()

    s.server.send_state = capture   # type: ignore[method-assign]
    asyncio.run(s.run(autostart=True, commands=commands))
    return seen[0]


def test_short_options_are_the_same_list_as_a_file():
    assert seance_file.from_options("col", "sweet", "wtf") == [
        ("select_route", {"route_id": "col"}), ("select_workout", {"workout_id": "sweet"}),
        ("start", {"mode": "wtf"})]
    assert seance_file.from_options() == [("select_route", {"route_id": "demo"}), ("start", {})]


@pytest.mark.parametrize("cmds, why", [
    ([], "non vide"),
    ([{"cmd": "start", "args": []}], "objet"),
    ([{"cmd": "end_session"}, {"cmd": "start"}], "ne prépare pas"),
    ([{"cmd": "select_route", "args": {"route_id": "col"}}], "finit par 'start'"),
    ([{"cmd": "start"}, {"cmd": "start"}], "une seule fois"),
])
def test_bad_lists_are_refused(cmds, why):
    with pytest.raises(seance_file.SeanceError, match=why):
        seance_file.check(cmds)


def test_file_is_read(tmp_path):
    f = tmp_path / "s.json"
    f.write_text(json.dumps({"id": "x", "but": "pente", "commandes": [
        {"cmd": "select_route", "args": {"route_id": "col"}}, {"cmd": "start", "args": {"bots": []}}]}))
    assert seance_file.load(f) == [("select_route", {"route_id": "col"}), ("start", {"bots": []})]
    f.write_text("{")
    with pytest.raises(seance_file.SeanceError, match="illisible"):
        seance_file.load(f)


def test_locked_free_ride_drops_command_line_bots(tmp_path, routes):
    """`bots: []` dans la fiche : aucun bot, même si la ligne de commande ou la partie d'avant en avait."""
    from openride_core.bots import ConstantPowerBot

    s = make_session(tmp_path, routes, 7300, bots=[ConstantPowerBot(200.0)])
    st = run_until_first_state(s, [("select_route", {"route_id": "col"}), ("start", {"bots": []})])
    assert st["route_id"] == "col" and st["session_state"] == "RUNNING"
    assert st["_bots"] == []


def test_locked_velodrome_event(tmp_path, routes):
    s = make_session(tmp_path, routes, 7310)
    st = run_until_first_state(s, [
        ("select_route", {"route_id": velodrome.TRACK_ID}),
        ("start", {"mode": "track", "track": {"event": "elimination", "opponents": 4}})])
    assert st["session_state"] == "RUNNING" and st["route_id"] == velodrome.TRACK_ID
    assert st["_track"]


def test_locked_rogue_run(tmp_path, routes):
    s = make_session(tmp_path, routes, 7320)
    st = run_until_first_state(s, [
        ("start_run", {"objective": "threshold", "duration_min": 30, "seed": 7}), ("start", {})])
    assert st["session_state"] == "RUNNING" and st["_rogue"]


def test_refused_command_stops_the_core(tmp_path, routes):
    """Une épreuve de piste hors vélodrome : le core le dit et s'arrête, rien ne part à moitié réglé."""
    s = make_session(tmp_path, routes, 7330)
    with pytest.raises(AutostartError, match="refusée à « start »"):
        asyncio.run(s.run(autostart=True, commands=[
            ("select_route", {"route_id": "col"}), ("start", {"mode": "track", "track": {"event": "scratch"}})]))
    assert s._rec is None


def test_unknown_route_is_refused_before_ipc(tmp_path, routes, monkeypatch):
    s = make_session(tmp_path, routes, 7340)
    started = []
    monkeypatch.setattr(s.server, "start", lambda: started.append(True))
    with pytest.raises(AutostartError, match="inexistant"):
        asyncio.run(s.run(autostart=True, commands=[("select_route", {"route_id": "inexistant"}), ("start", {})]))
    assert not started


def test_cli_seance_excludes_route(tmp_path, capsys):
    f = tmp_path / "s.json"
    f.write_text(json.dumps({"commandes": [{"cmd": "start"}]}))
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "--trainer", "mock", "--autostart", "--seance", str(f), "--route", "col"])
    assert exc.value.code == 2 and "--seance exclut --route" in capsys.readouterr().err


def test_cli_seance_needs_autostart(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "--trainer", "mock", "--seance", str(tmp_path / "s.json")])
    assert exc.value.code == 2 and "--seance demande --autostart" in capsys.readouterr().err


def test_cli_bad_file_returns_1_without_ports(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    started = []
    monkeypatch.setattr(IpcServer, "start", lambda self: started.append(True))
    f = tmp_path / "s.json"
    f.write_text("pas du json")
    code = cli.main(["run", "--config", str(tmp_path / "config.toml"), "--trainer", "mock", "--input", "none",
                     "--autostart", "--seance", str(f)])
    assert code == 1 and not started and "illisible" in capsys.readouterr().err
