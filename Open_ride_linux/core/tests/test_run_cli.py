"""Lot J1 : `openride-core run --autostart --route ID --workout ID`."""

import asyncio
import shutil
from pathlib import Path

import pytest

from openride_core import __main__ as cli
from openride_core import fit_export, route
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.input_providers import NullProvider
from openride_core.ipc_server import IpcServer
from openride_core.mock_driver import MockDriver
from openride_core.session import AutostartError, CoreSession

WORKOUTS_SRC = Path(__file__).resolve().parents[1] / "workouts"


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Parcours `col` (3 km) et entraînements dans des dossiers temporaires."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    routes = tmp_path / "routes"
    write_world(routes, "col", 3000.0)
    workouts = tmp_path / "Workouts"
    workouts.mkdir()
    shutil.copy(WORKOUTS_SRC / "sweet_spot_3x10.zwo", workouts)
    (workouts / "casse.zwo").write_text("<workout_file><workout>", encoding="utf-8")
    return routes, workouts


def make_session(tmp_path, dirs, port):
    routes, workouts = dirs
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    return CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()],
                       journal_dir=tmp_path / "journal", routes_root=routes, workouts_dir=workouts)


def first_state(s: CoreSession, **run_kwargs):
    """Lance `run(autostart=True, ...)` et renvoie la première trame `state` envoyée."""
    frames = []

    def capture(state):
        frames.append(state.to_dict() if hasattr(state, "to_dict") else dict(vars(state)))
        s.stop_event.set()

    s.server.send_state = capture   # type: ignore[method-assign]
    asyncio.run(s.run(autostart=True, **run_kwargs))
    return frames[0]


def test_autostart_on_chosen_route(tmp_path, dirs):
    s = make_session(tmp_path, dirs, 6100)
    st = first_state(s, route_id="col")
    assert st["route_id"] == "col"
    assert st["session_state"] == "RUNNING"
    assert st["route_length_m"] == pytest.approx(route.load_world(dirs[0] / "col.world").route.length_m)
    assert st["mode"] == "SIM"


def test_autostart_with_workout_is_erg_from_start(tmp_path, dirs):
    s = make_session(tmp_path, dirs, 6110)
    st = first_state(s, route_id="col", workout_id="sweet_spot_3x10")
    assert st["mode"] == "ERG"
    assert st["erg"]["workout_name"]


@pytest.mark.parametrize("kwargs", [
    {"route_id": "inexistant"},
    {"route_id": "../col"},
    {"route_id": "col", "workout_id": "casse"},
    {"route_id": "col", "workout_id": "absent"},
])
def test_autostart_refused_before_ipc(tmp_path, dirs, monkeypatch, kwargs):
    s = make_session(tmp_path, dirs, 6120)
    started = []
    monkeypatch.setattr(s.server, "start", lambda: started.append(True))
    with pytest.raises(AutostartError):
        asyncio.run(s.run(autostart=True, **kwargs))
    assert not started and s.state.session_state == "IDLE"


@pytest.mark.parametrize("extra", [["--route", "inexistant"], ["--workout", "inexistant_j1"]])
def test_main_returns_1_without_opening_ports(tmp_path, monkeypatch, capsys, extra):
    monkeypatch.setattr(route, "ROUTES_DIR", tmp_path / "routes")
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    started = []
    monkeypatch.setattr(IpcServer, "start", lambda self: started.append(True))
    code = cli.main(["run", "--config", str(tmp_path / "config.toml"), "--trainer", "mock",
                     "--input", "none", "--autostart", *extra])
    assert code == 1 and not started
    assert "refusé" in capsys.readouterr().err


@pytest.mark.parametrize("extra", [["--route", "col"], ["--workout", "sweet_spot_3x10"]])
def test_route_and_workout_need_autostart(capsys, extra):
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "--trainer", "mock", *extra])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "demande --autostart" in err and extra[0] in err
