"""Lot O23 : traces importées depuis le menu des parcours et compilées sans relancer OpenRide."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import jsonschema
import pytest

from openride_core import route_import
from openride_core.catalog import list_routes
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
STUB = [sys.executable, str(Path(__file__).parent / "data" / "stub_compiler.py")]
GPX = '<?xml version="1.0"?><gpx version="1.1"><trk><trkseg><trkpt lat="45.0" lon="6.0"/></trkseg></trk></gpx>\n'


def assert_valid(msg: dict) -> None:
    schema = json.loads((IPC_DIR / f"{msg['type']}.schema.json").read_text(encoding="utf-8"))
    errors = [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(msg)]
    assert not errors, f"{msg['type']} invalide : {errors}"


def test_candidates_formats_order_and_already_imported(tmp_path: Path):
    home, gpx_dir = tmp_path / "home", tmp_path / "GPX"
    (home / "Téléchargements").mkdir(parents=True)
    (home / "Bureau").mkdir()
    gpx_dir.mkdir()
    old = home / "Téléchargements" / "Col.gpx"
    old.write_text(GPX, encoding="utf-8")
    os.utime(old, (1_000_000, 1_000_000))
    (home / "Bureau" / "sortie.fit.gz").write_bytes(b"\x1f\x8b fit")
    (home / "Bureau" / "notes.txt").write_text("pas une trace", encoding="utf-8")
    (home / "Téléchargements" / "sous").mkdir()
    (home / "Téléchargements" / "sous" / "cache.gpx").write_text(GPX, encoding="utf-8")
    items = route_import.import_candidates(home, gpx_dir)
    assert [(i["file"], i["source"], i["imported"]) for i in items] == [
        ("sortie.fit.gz", "Bureau", False), ("Col.gpx", "Téléchargements", False)]
    (gpx_dir / "deja.gpx").write_text(GPX, encoding="utf-8")   # même contenu, autre nom : déjà importée
    assert route_import.import_candidates(home, gpx_dir)[1]["imported"] is True


def test_copy_never_overwrites_and_skips_identical(tmp_path: Path):
    gpx_dir, routes = tmp_path / "GPX", tmp_path / "routes"
    src = tmp_path / "Col.gpx"
    src.write_text(GPX, encoding="utf-8")
    first = route_import.copy_track(src, gpx_dir, routes)
    assert first == {"path": str(gpx_dir / "Col.gpx"), "file": "Col.gpx", "created": True}
    assert route_import.copy_track(src, gpx_dir, routes)["created"] is False
    other = tmp_path / "col.fit"   # même identifiant normalisé (« col »), autre contenu
    other.write_bytes(b"autre contenu")
    second = route_import.copy_track(other, gpx_dir, routes)
    assert second["file"] == "col_2.fit" and second["created"] is True
    (routes / "rando.world").mkdir(parents=True)   # nom déjà pris par un parcours compilé
    third = tmp_path / "Rando.gpx"
    third.write_text(GPX.replace("6.0", "6.1"), encoding="utf-8")
    assert route_import.copy_track(third, gpx_dir, routes)["file"] == "Rando_2.gpx"
    assert sorted(p.name for p in gpx_dir.iterdir()) == ["Col.gpx", "Rando_2.gpx", "col_2.fit"]


@pytest.mark.parametrize("name,content,code", [("vide.gpx", b"", "route_invalid"),
                                               ("notes.txt", b"x", "route_invalid")])
def test_copy_refuses_empty_or_unknown(tmp_path: Path, name, content, code):
    src = tmp_path / name
    src.write_bytes(content)
    with pytest.raises(route_import.RouteImportError) as exc:
        route_import.copy_track(src, tmp_path / "GPX", tmp_path / "routes")
    assert exc.value.code == code
    assert not (tmp_path / "GPX").exists()


def test_compiler_override_for_benches(monkeypatch):
    """`OPENRIDE_COMPILER` remplace le compilateur (doublure du banc des menus) ; préfixe sans sous-commande."""
    monkeypatch.setenv("OPENRIDE_COMPILER", "python3 '/a b/stub_compiler.py'")
    assert route_import.compiler_prefix() == ["python3", "/a b/stub_compiler.py"]


def test_build_cmd_and_error_line():
    assert route_import.build_cmd(["openride-compiler"], Path("/g/a.gpx"), Path("/r"), True) == [
        "openride-compiler", "build", "/g/a.gpx", "--out", "/r", "--force"]
    assert route_import.last_error_line("Lecture…\nerreur : trace vide\n\n") == "erreur : trace vide"


def make_session(tmp_path: Path, port: int) -> tuple[CoreSession, list[dict]]:
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", workouts_dir=tmp_path / "Workouts")
    s.import_home = tmp_path / "home"
    s.gpx_dir = tmp_path / "GPX"
    s.route_compiler_cmd = STUB
    sent: list[dict] = []
    s.server.send_raw = lambda m, max_size=None: sent.append(m)   # type: ignore[method-assign]
    return s, sent


def test_session_imports_compiles_and_lists_without_restart(tmp_path: Path):
    """list_route_imports, import_route puis route_import_status `done` : le parcours est prêt tout de suite."""
    (tmp_path / "home" / "Downloads").mkdir(parents=True)
    (tmp_path / "home" / "Downloads" / "Mon Col.gpx").write_text(GPX, encoding="utf-8")
    (tmp_path / "home" / "Downloads" / "casse.gpx").write_text("pas une trace", encoding="utf-8")
    s, sent = make_session(tmp_path, 5786)

    async def run(name: str, args: dict, cmd_id: int) -> list[dict]:
        mark = len(sent)
        s._on_command(name, args, cmd_id)
        while s._bg_tasks:
            await asyncio.sleep(0.01)
        return sent[mark:]

    async def scenario() -> None:
        refused = await run("import_route", {"path": str(tmp_path / "home" / "Downloads" / "Mon Col.gpx")}, 1)
        assert refused[0]["type"] == "error" and refused[0]["code"] == "route_invalid"
        listing = await run("list_route_imports", {}, 2)
        files = {i["file"]: i["path"] for i in listing[0]["items"]}
        assert listing[0]["type"] == "route_imports" and set(files) == {"Mon Col.gpx", "casse.gpx"}
        done = await run("import_route", {"path": files["Mon Col.gpx"]}, 3)
        failed = await run("import_route", {"path": files["casse.gpx"]}, 4)
        again = await run("import_route", {"path": files["Mon Col.gpx"]}, 5)   # déjà importée et compilée
        for m in listing + done + failed + again:
            assert_valid(m)
        last = done[-1]
        assert last["state"] == "done" and last["route_id"] == "mon-col" and last["created"] is True
        assert last["request_cmd_id"] == 3 and last["file"] == "Mon Col.gpx"
        assert failed[-1]["state"] == "failed" and "aucun point de trace" in failed[-1]["message"]
        assert again[-1]["state"] == "done" and again[-1]["created"] is False
        s.state.session_state = "RUNNING"
        busy = await run("list_route_imports", {}, 6)
        assert busy[0]["code"] == "busy"

    asyncio.run(scenario())
    ready = {e.id: e.status for e in list_routes(routes_root=tmp_path / "routes", gpx_dir=tmp_path / "GPX")}
    assert ready["mon-col"] == "ready"
    assert "casse" not in ready   # trace refusée : copie retirée, rien n'est ajouté à la liste
    assert sorted(p.name for p in (tmp_path / "GPX").iterdir()) == ["Mon Col.gpx"]


def test_second_import_during_compilation_is_busy(tmp_path: Path):
    s, sent = make_session(tmp_path, 5788)
    s._route_import_offer = {"/a.gpx", "/b.gpx"}
    s._route_import = {"source": "/a.gpx", "state": "compiling", "file": "a.gpx", "started": 0.0, "cmd_id": 1}
    s._on_command("import_route", {"path": "/b.gpx"}, 2)
    s._on_command("import_route", {"path": "/a.gpx"}, 1)   # copie renvoyée : état en cours
    assert sent[0]["code"] == "busy"
    assert sent[1]["type"] == "route_import_status" and sent[1]["state"] == "compiling"
