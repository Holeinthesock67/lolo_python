"""Contrôle « sol au-dessus de la route » sur les parcours du PC (scripts/controle_sol_route.py, 20 novembre)."""

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("controle_sol_route", ROOT / "scripts" / "controle_sol_route.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["controle_sol_route"] = mod
    spec.loader.exec_module(mod)
    return mod


cs = _load()


def _world(path: Path, parts: int = 0) -> Path:
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(json.dumps({"format": "openride-world"}), encoding="utf-8")
    if parts:
        (path / "route").mkdir()
        for k in range(parts):
            (path / "route" / f"part_{k}.json").write_text("{}", encoding="utf-8")
    return path


def test_installed_worlds_skip_velodrome_and_broken(tmp_path):
    routes = tmp_path / "routes"
    _world(routes / "demo.world")
    _world(routes / "demo-recif.world")
    _world(routes / "velodrome-250.world")
    (routes / "vide.world").mkdir()
    assert [p.name for p in cs.installed_worlds(routes)] == ["demo-recif.world", "demo.world"]
    assert cs.installed_worlds(tmp_path / "absent") == []


def test_latest_sessions_newest_first_with_route(tmp_path):
    seances = tmp_path / "seances"
    old = _world(seances / "ow-20261118-0700.world", parts=2)
    new = _world(seances / "ow-20261120-0700.world", parts=1)
    _world(seances / "ow-20261121-0700.world")              # séance sans route écrite : ignorée
    os.utime(old, (1_000, 1_000))
    os.utime(new, (2_000, 2_000))
    assert cs.latest_sessions(seances, 3) == [new, old]
    assert cs.latest_sessions(seances, 1) == [new]
    assert cs.latest_sessions(seances, 0) == []


def test_nothing_to_check_or_no_godot(tmp_path, monkeypatch):
    out = tmp_path / "sortie"
    assert cs.main(["--out", str(out), "--routes", str(tmp_path / "r"), "--seances", str(tmp_path / "s")]) == 2
    assert "rien à contrôler" in (out / "resume.txt").read_text(encoding="utf-8")
    w = _world(tmp_path / "demo.world")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert cs.main(["--out", str(out), "--godot", str(tmp_path / "pas-de-godot"), str(w)]) == 2
    assert "Godot introuvable" in (out / "resume.txt").read_text(encoding="utf-8")
    g = home / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64"
    g.parent.mkdir(parents=True)
    g.write_text("")
    assert cs.find_godot(tmp_path / "pas-de-godot") == g
