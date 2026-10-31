"""Traces importées depuis le menu des parcours (lot O23) : candidats, copie sans écrasement, compilation
dans un processus à part et réponses IPC `route_imports` / `route_import`."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from openride_core import route_import
from test_contract_ipc import assert_valid
from openride_core.config import Config
from openride_core.ipc_server import LIST_MESSAGE_TYPES
from openride_core.session import CoreSession
from openride_core.mock_driver import MockDriver
from openride_core.input_providers import NullProvider

GPX = """<?xml version="1.0"?>
<gpx version="1.1" creator="test"><trk><name>Essai</name><trkseg>
<trkpt lat="45.0" lon="6.0"><ele>500</ele></trkpt>
<trkpt lat="45.001" lon="6.0"><ele>505</ele></trkpt>
</trkseg></trk></gpx>
"""


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / "Téléchargements").mkdir(parents=True)
    (home / "Bureau").mkdir()
    return home


def test_candidates_list_tracks_only(tmp_path):
    home, gpx_dir = _home(tmp_path), tmp_path / "GPX"
    (home / "Téléchargements" / "col.gpx").write_text(GPX)
    (home / "Téléchargements" / "Activité.fit.gz").write_bytes(b"x")
    (home / "Téléchargements" / "seuil.zwo").write_text("<workout_file/>")
    (home / "Bureau" / "export.zip").write_bytes(b"PK")
    gpx_dir.mkdir()
    (gpx_dir / "col.gpx").write_text(GPX)
    items = route_import.import_candidates(home, gpx_dir)
    files = {it["file"]: it for it in items}
    assert set(files) == {"col.gpx", "Activité.fit.gz", "export.zip"}
    assert files["col.gpx"]["imported"] and not files["export.zip"]["imported"]
    assert files["export.zip"]["source"] == "Bureau"


def test_copy_never_overwrites_and_skips_identical(tmp_path):
    home, gpx_dir = _home(tmp_path), tmp_path / "GPX"
    src = home / "Téléchargements" / "Ma Sortie.gpx"
    src.write_text(GPX)
    first = route_import.copy_track(src, gpx_dir)
    assert first["created"] and first["file"] == "Ma Sortie.gpx"
    again = route_import.copy_track(src, gpx_dir)
    assert not again["created"] and again["path"] == first["path"]
    other = home / "Bureau" / "ma-sortie.fit"
    other.write_bytes(b"autre contenu")
    second = route_import.copy_track(other, gpx_dir)
    assert second["created"] and second["file"] == "ma-sortie_2.fit"   # même identifiant « ma-sortie » sinon
    assert not list(gpx_dir.glob(".*.tmp"))


@pytest.mark.parametrize("name,data,why", [("trace.txt", b"x", "format inconnu"), ("vide.gpx", b"", "vide")])
def test_copy_refuses(tmp_path, name, data, why):
    src = tmp_path / name
    src.write_bytes(data)
    with pytest.raises(route_import.RouteImportError) as exc:
        route_import.copy_track(src, tmp_path / "GPX")
    assert exc.value.code == "route_invalid" and why in str(exc.value)


class Capture:
    def __init__(self, server):
        self.frames: list[dict] = []
        server.send_raw = self.frames.append
        server.send_error = lambda code, message: self.frames.append({"type": "error", "code": code, "message": message})

    def of(self, typ):
        return [f for f in self.frames if f.get("type") == typ]


DEMO_WORLD = Path(__file__).resolve().parents[2] / "engine" / "demo" / "demo.world"


def _fake_compiler(tmp_path: Path, ok: bool) -> list[str]:
    """Faux `build-all` : copie le parcours de démonstration pour chaque trace (manifeste pointé sur elle), ou échoue."""
    script = tmp_path / "fake_compiler.py"
    script.write_text(f"""
import hashlib, json, shutil, sys
from pathlib import Path
sys.path.insert(0, {str(Path(route_import.__file__).parent.parent)!r})
from openride_core.catalog import _normalize_name, track_stem
args = sys.argv[1:]
routes = Path(args[args.index("--routes-dir") + 1]); gpx = Path(args[args.index("--gpx-dir") + 1])
if not {ok!r}:
    print("openride-compiler : erreur (" + next(gpx.iterdir()).name + ") : trace sans points")
    sys.exit(2)
for f in gpx.iterdir():
    rid = _normalize_name(track_stem(f.name)[0])
    w = routes / (rid + ".world")
    shutil.rmtree(w, ignore_errors=True); shutil.copytree({str(DEMO_WORLD)!r}, w)
    m = json.loads((w / "manifest.json").read_text())
    m["source"] = {{"gpx": f.name, "gpx_sha256": hashlib.sha256(f.read_bytes()).hexdigest()}}
    (w / "manifest.json").write_text(json.dumps(m))
print("Résumé : 1 compilé(s)")
""")
    return [sys.executable, str(script), "build-all"]


def _session(tmp_path, monkeypatch, ok=True):
    from openride_core import fit_export
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    s = CoreSession(Config(), driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes")
    s.import_home = _home(tmp_path)
    s.gpx_dir = tmp_path / "GPX"
    s.compiler_cmd = _fake_compiler(tmp_path, ok)
    (s.import_home / "Téléchargements" / "Col Test.gpx").write_text(GPX)
    return s, Capture(s.server)


async def _drain(s):
    for _ in range(400):
        await asyncio.sleep(0.01)
        if not s._bg_tasks:
            return


def test_ipc_list_then_import_compiles(tmp_path, monkeypatch):
    async def scenario():
        s, cap = _session(tmp_path, monkeypatch)
        s._on_command("list_route_imports", {}, 1)
        await _drain(s)
        (lst,) = cap.of("route_imports")
        assert lst["request_cmd_id"] == 1 and lst["items"][0]["file"] == "Col Test.gpx"
        s._on_command("import_route", {"path": lst["items"][0]["path"]}, 2)
        await _drain(s)
        phases = [m["phase"] for m in cap.of("route_import")]
        assert phases == ["compiling", "done"], cap.frames
        done = cap.of("route_import")[-1]
        assert done["route_id"] == "col-test" and done["created"] and done["request_cmd_id"] == 2
        assert (tmp_path / "GPX" / "Col Test.gpx").is_file()
        # Deuxième import de la même trace : rien à copier ni à compiler.
        s._on_command("import_route", {"path": lst["items"][0]["path"]}, 3)
        await _drain(s)
        last = cap.of("route_import")[-1]
        assert last["phase"] == "done" and not last["created"] and last["request_cmd_id"] == 3
        assert [m["phase"] for m in cap.of("route_import") if m["request_cmd_id"] == 3] == ["done"]
        for frame in cap.of("route_imports") + cap.of("route_import"):
            assert_valid(frame)
    asyncio.run(scenario())


def test_ipc_refusals(tmp_path, monkeypatch):
    async def scenario():
        s, cap = _session(tmp_path, monkeypatch, ok=False)
        s._on_command("import_route", {"path": "/etc/passwd"}, 1)   # pas proposé par la liste
        await _drain(s)
        assert cap.of("error")[-1]["code"] == "route_invalid" and "list_route_imports" in cap.of("error")[-1]["message"]
        s._on_command("list_route_imports", {}, 2)
        await _drain(s)
        path = cap.of("route_imports")[-1]["items"][0]["path"]
        s._on_command("import_route", {"path": path}, 3)
        await _drain(s)
        err = cap.of("error")[-1]
        assert err["code"] == "route_invalid" and "trace sans points" in err["message"]
        s.state.session_state = "RUNNING"
        s._on_command("list_route_imports", {}, 4)
        assert cap.of("error")[-1]["code"] == "busy"
    asyncio.run(scenario())


def test_route_imports_is_a_list_message():
    assert "route_imports" in LIST_MESSAGE_TYPES
    doc = (Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc" / "route_import.schema.json")
    assert json.loads(doc.read_text(encoding="utf-8"))["properties"]["type"]["const"] == "route_import"
