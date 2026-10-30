"""Bibliothèque des thèmes et installation depuis une adresse (lot U15) : `theme-install https://…`
servi par un petit serveur HTTPS local (seul accès réseau des tests), refus de HTTP et des archives
invalides sans rien copier, réseau absent, plafond `[render] theme_library_gb` qui retire le pack le moins
récemment utilisé et jamais le thème choisi."""

from __future__ import annotations

import functools
import http.server
import json
import shutil
import socket
import ssl
import subprocess
import threading
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from openride_compiler.cli import main
from openride_compiler.errors import CompileError
from openride_compiler.theme import DEFAULT_THEME_PATH
from openride_compiler.theme_packs import (
    DEFAULT_LIBRARY_GB,
    USE_FILE,
    enforce_library_limit,
    install_theme,
    library_limit_bytes,
    list_themes,
    read_theme_use,
)

GB = 1024 ** 3


def _theme_zip(path: Path, name: str, valid: bool = True) -> Path:
    theme = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
    theme["name"] = name
    if not valid:
        theme["version"] = 42
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{name}/theme.json", json.dumps(theme))
    return path


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:   # pas de bruit dans la sortie des tests
        pass


@pytest.fixture(scope="module")
def https_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, Path, ssl.SSLContext]]:
    """Serveur HTTPS local (certificat auto-signé de 127.0.0.1) : (adresse de base, dossier servi, contexte client)."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl absent : pas de certificat de test")
    root = tmp_path_factory.mktemp("https")
    served = root / "www"
    served.mkdir()
    cert, key = root / "cert.pem", root / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                   check=True, capture_output=True)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(served)))
    srv_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    srv_ctx.load_cert_chain(cert, key)
    server.socket = srv_ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = ssl.create_default_context(cafile=str(cert))
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}", served, client
    finally:
        server.shutdown()


def test_install_from_https_address(https_server, tmp_path: Path) -> None:
    base, served, ctx = https_server
    _theme_zip(served / "pack-cc0.zip", "Pack CC0 Essai")
    themes = tmp_path / "Themes"
    name, _ = install_theme(f"{base}/pack-cc0.zip", themes_dir=themes, config_path=tmp_path / "absente.toml",
                            ssl_context=ctx)
    assert name == "pack-cc0-essai"
    assert (themes / name / "theme.json").is_file()


def test_invalid_archive_from_address_is_refused_and_nothing_copied(https_server, tmp_path: Path) -> None:
    base, served, ctx = https_server
    _theme_zip(served / "mauvais.zip", "Mauvais", valid=False)
    (served / "pas-un-zip.zip").write_text("<html>page d'erreur</html>", encoding="utf-8")
    themes = tmp_path / "Themes"
    with pytest.raises(CompileError, match="invalide"):
        install_theme(f"{base}/mauvais.zip", themes_dir=themes, ssl_context=ctx)
    with pytest.raises(CompileError, match="archive .zip"):
        install_theme(f"{base}/pas-un-zip.zip", themes_dir=themes, ssl_context=ctx)
    with pytest.raises(CompileError, match="injoignable"):
        install_theme(f"{base}/absent.zip", themes_dir=themes, ssl_context=ctx)
    assert not themes.exists() or not any(themes.iterdir())


def test_http_and_other_schemes_are_refused(tmp_path: Path) -> None:
    for url in ("http://127.0.0.1/pack.zip", "ftp://exemple.org/pack.zip", "https:///pack.zip"):
        with pytest.raises(CompileError, match="https:// seulement"):
            install_theme(url, themes_dir=tmp_path / "Themes")
    assert not (tmp_path / "Themes").exists()


def test_no_network_gives_a_clear_refusal(tmp_path: Path) -> None:
    with socket.socket() as s:   # port libre, fermé aussitôt : connexion refusée
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(CompileError, match="réseau absent"):
        install_theme(f"https://127.0.0.1:{port}/pack.zip", themes_dir=tmp_path / "Themes")


def test_cli_installs_from_address(https_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    base, served, ctx = https_server
    _theme_zip(served / "cli.zip", "Depuis La Ligne")
    # Contexte par défaut d'urllib, ouvreur global reconstruit (il garde le contexte de sa création).
    monkeypatch.setattr(ssl, "_create_default_https_context", lambda *a, **k: ctx)
    monkeypatch.setattr(urllib.request, "_opener", None)
    assert main(["theme-install", f"{base}/cli.zip", "--themes-dir", str(tmp_path / "Themes")]) == 0
    assert "depuis-la-ligne" in capsys.readouterr().out


def _sparse_pack(themes: Path, name: str, size: int) -> Path:
    d = themes / name
    d.mkdir(parents=True)
    (d / "theme.json").write_text("{}", encoding="utf-8")
    with (d / "textures.bin").open("wb") as f:   # fichier creux : la taille compte, le disque non
        f.truncate(size)
    return d


def test_library_over_limit_removes_least_recently_used(tmp_path: Path) -> None:
    themes = tmp_path / "Themes"
    for name in ("ancien", "choisi", "recent"):
        _sparse_pack(themes, name, int(1.75 * GB))
    (themes / USE_FILE).write_text(json.dumps({"choisi": "2026-01-01T08:00:00", "ancien": "2026-03-01T08:00:00",
                                               "recent": "2026-10-29T08:00:00"}), encoding="utf-8")
    # 5,25 Go pour 5 Go : le moins récent après le thème choisi part, rien d'autre.
    removed = enforce_library_limit(themes, library_limit_bytes(tmp_path / "absente.toml"), keep={"choisi"})
    assert removed == ["ancien"]
    assert sorted(p.name for p in themes.iterdir() if p.is_dir()) == ["choisi", "recent"]
    assert enforce_library_limit(themes, 5 * GB, keep={"choisi"}) == []


def test_install_keeps_library_under_limit_and_reports_it(tmp_path: Path) -> None:
    themes = tmp_path / "Themes"
    for name in ("vieux", "actif"):
        _sparse_pack(themes, name, int(2.6 * GB))
    (themes / USE_FILE).write_text(json.dumps({"vieux": "2026-05-01T08:00:00", "actif": "2026-04-01T08:00:00"}),
                                   encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text('[render]\ntheme = "actif"\ntheme_library_gb = 5\n', encoding="utf-8")
    pack = tmp_path / "nouveau"
    pack.mkdir()
    (pack / "theme.json").write_text(json.dumps(json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
                                                | {"name": "nouveau"}), encoding="utf-8")
    name, messages = install_theme(pack, themes_dir=themes, config_path=config)
    assert name == "nouveau"
    assert sorted(p.name for p in themes.iterdir() if p.is_dir()) == ["actif", "nouveau"]
    assert any("« vieux » retiré" in m for m in messages)


def test_library_limit_from_config(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    assert library_limit_bytes(tmp_path / "absente.toml") == int(DEFAULT_LIBRARY_GB * GB)
    for text, gb in (("theme_library_gb = 12", 12), ("theme_library_gb = 0.2", 1), ("theme_library_gb = 400", 50),
                     ('theme_library_gb = "beaucoup"', DEFAULT_LIBRARY_GB), ("theme_library_gb = true", DEFAULT_LIBRARY_GB)):
        cfg.write_text(f"[render]\n{text}\n", encoding="utf-8")
        assert library_limit_bytes(cfg) == int(gb * GB), text


def test_theme_list_shows_last_use(tmp_path: Path) -> None:
    themes = tmp_path / "Themes"
    _sparse_pack(themes, "date", 10)
    (themes / USE_FILE).write_text(json.dumps({"date": "2026-10-29T08:00:00"}), encoding="utf-8")
    assert read_theme_use(themes) == {"date": "2026-10-29T08:00:00"}
    listed = {t["name"]: t for t in list_themes(themes_dir=themes, config_path=tmp_path / "absente.toml")}
    assert listed["date"]["last_used"] == "2026-10-29T08:00:00"
    (themes / USE_FILE).write_text("pas du json", encoding="utf-8")
    assert read_theme_use(themes) == {}

