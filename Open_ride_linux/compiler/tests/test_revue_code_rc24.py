"""Lot RC24, contenus et packs (revue de code, vague 4, K4-01, K4-02, K4-05), côté compilateur."""

from __future__ import annotations

import json
import socket
import threading
import urllib.request
from pathlib import Path

import pytest

from openride_compiler import demo_biomes
from openride_compiler.route_pack import INSTALLED_FILE, install_pack
from openride_compiler.theme import DEFAULT_THEME_PATH
from openride_compiler.theme_packs import INSTALL_MARK, enforce_library_limit, install_theme

from test_route_library import track_text

GB = 1024 ** 3


def _dir(root: Path, name: str, size: int, theme_json: bool = True, mark: bool = False) -> Path:
    d = root / name
    d.mkdir(parents=True)
    if theme_json:
        (d / "theme.json").write_text("{}", encoding="utf-8")
    if mark:
        (d / INSTALL_MARK).write_text("", encoding="utf-8")
    with (d / "gros.bin").open("wb") as f:       # fichier creux
        f.truncate(size)
    return d


# --- K4-01 : ménage de la bibliothèque des thèmes ------------------------------------------------

def test_cleanup_only_removes_packs_installed_by_theme_install(tmp_path: Path) -> None:
    themes = tmp_path / "Themes"
    _dir(themes, "brouillon", 2 * GB, theme_json=False)          # dossier de travail
    _dir(themes, "fait-main", 2 * GB)                            # thème fait à la main, le plus ancien
    _dir(themes, "installe", 2 * GB, mark=True)
    removed = enforce_library_limit(themes, 5 * GB, keep=set())
    assert removed == ["installe"]
    assert sorted(p.name for p in themes.iterdir()) == ["brouillon", "fait-main"]


def test_cleanup_refuses_a_folder_that_is_not_a_theme_library(tmp_path: Path) -> None:
    home = tmp_path / "OpenRide"
    for name in ("Activities", "Cache", "Themes"):
        _dir(home, name, 3 * GB, mark=True)
    assert enforce_library_limit(home, 5 * GB, keep=set()) == []
    assert sorted(p.name for p in home.iterdir()) == ["Activities", "Cache", "Themes"]


def test_install_theme_marks_the_pack(tmp_path: Path) -> None:
    src = tmp_path / "neuf"
    src.mkdir()
    theme = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8")) | {"name": "neuf"}
    (src / "theme.json").write_text(json.dumps(theme), encoding="utf-8")
    name, _ = install_theme(source=src, themes_dir=tmp_path / "Themes", config_path=tmp_path / "absente.toml")
    assert (tmp_path / "Themes" / name / INSTALL_MARK).is_file()


# --- K4-05 : réinstallation forcée d'un pack -----------------------------------------------------

def test_forced_reinstall_keeps_hand_added_files(tmp_path: Path) -> None:
    src = tmp_path / "source"
    src.mkdir()
    (src / "alpe.gpx").write_text(track_text(600.0), encoding="utf-8")
    (src / "vieux.gpx").write_text(track_text(700.0), encoding="utf-8")
    gpx_dir = tmp_path / "GPX"
    _, _, target = install_pack(src, gpx_dir, name="cols")
    assert sorted(json.loads((target / INSTALLED_FILE).read_text())) == ["alpe.gpx", "vieux.gpx"]
    (target / "alpe.segments.toml").write_text("# segments écrits à la main\n", encoding="utf-8")
    (target / "ma-sortie.gpx").write_text(track_text(800.0), encoding="utf-8")
    (src / "vieux.gpx").unlink()                         # la nouvelle version du pack n'a plus cette trace
    install_pack(src, gpx_dir, name="cols", force=True)
    names = sorted(p.name for p in target.iterdir() if not p.name.startswith("."))
    assert names == ["alpe.gpx", "alpe.segments.toml", "ma-sortie.gpx"]      # « vieux » venait du pack : parti
    assert (target / "alpe.segments.toml").read_text(encoding="utf-8").startswith("# segments")


def test_forced_reinstall_over_a_pack_without_list_keeps_everything(tmp_path: Path) -> None:
    src = tmp_path / "source"
    src.mkdir()
    (src / "alpe.gpx").write_text(track_text(600.0), encoding="utf-8")
    old = tmp_path / "GPX" / "cols"                      # pack installé avant ce lot : pas de liste
    old.mkdir(parents=True)
    (old / "alpe.gpx").write_text("ancien", encoding="utf-8")
    (old / "perso.gpx").write_text(track_text(800.0), encoding="utf-8")
    install_pack(src, tmp_path / "GPX", name="cols", force=True)
    assert sorted(p.name for p in old.iterdir() if not p.name.startswith(".")) == ["alpe.gpx", "perso.gpx"]
    assert (old / "alpe.gpx").read_text(encoding="utf-8") != "ancien"


# --- K4-02 : la coupure du réseau ne vaut que pour le fil qui compile -----------------------------

def test_network_block_is_limited_to_the_compiling_thread(tmp_path: Path) -> None:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    port = server.getsockname()[1]
    other = tmp_path / "autre.txt"
    other.write_text("vrai contenu", encoding="utf-8")
    seen: dict[str, object] = {}

    def other_thread() -> None:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=5).close()
            s = socket.socket()
            s.connect(("127.0.0.1", port))
            s.close()
            seen["urlopen"] = urllib.request.urlopen(other.as_uri()).read()
            seen["ok"] = True
        except Exception as exc:  # noqa: BLE001 - rapporté par l'assertion
            seen["error"] = exc

    try:
        with demo_biomes._offline_compiler(b'{"elements": []}', lambda x, z: 0 * x, tmp_path / "cache"):
            t = threading.Thread(target=other_thread)
            t.start()
            t.join(10)
            with pytest.raises(OSError, match="réseau interdit"):
                socket.create_connection(("127.0.0.1", port), timeout=5)
            with pytest.raises(OSError, match="réseau interdit"):
                socket.socket().connect(("127.0.0.1", port))
            assert urllib.request.urlopen("http://overpass.invalid/").read() == b'{"elements": []}'
        assert seen.get("ok") is True, seen
        assert seen["urlopen"] == b"vrai contenu"
        socket.create_connection(("127.0.0.1", port), timeout=5).close()     # tout est rétabli à la sortie
    finally:
        server.close()
