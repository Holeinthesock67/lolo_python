"""Tests des raccourcis de bureau `.desktop`, de l'icône SVG et de `scripts/install-desktop.sh` (lots L8 et N14)."""

from __future__ import annotations

import configparser
import os
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
DESKTOP_IN = ROOT_DIR / "scripts" / "desktop" / "openride.desktop.in"
ICON_SVG = ROOT_DIR / "scripts" / "desktop" / "openride.svg"
INSTALL_SH = ROOT_DIR / "scripts" / "install-desktop.sh"
ENTRIES = ("openride", "openride-release", "openride-update")


def _read_desktop(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # type: ignore[assignment]
    cp.read(path, encoding="utf-8")
    return cp


def _find_bash() -> str | None:
    if sys.platform == "win32":
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        return str(git_bash) if git_bash.is_file() else None
    return shutil.which("bash")


def _to_shell_path(bash_bin: str, p: Path) -> str:
    if sys.platform == "win32":
        res = subprocess.run(
            [bash_bin, "-c", 'cygpath -u "$1"', "_", str(p)],
            capture_output=True, text=True, check=True,
        )
        return res.stdout.strip()
    return str(p)


def test_desktop_template_valid_configparser():
    """Critère 2 : le modèle se lit par configparser ([Desktop Entry], clés obligatoires, Terminal=false)."""
    assert DESKTOP_IN.is_file()
    cp = _read_desktop(DESKTOP_IN)
    assert "Desktop Entry" in cp.sections()
    sec = cp["Desktop Entry"]
    for key in ("Type", "Name", "Comment", "Exec", "Icon", "Terminal", "Categories", "StartupWMClass"):
        assert key in sec and sec[key].strip(), f"clé manquante ou vide : {key}"
    assert sec["Type"] == "Application"
    assert sec["Name"] == "OpenRide"
    assert sec["Exec"] == "@OPENRIDE@"
    assert sec["Icon"] == "openride"
    assert sec["Terminal"] == "false"
    assert "Game;" in sec["Categories"] and "Sports;" in sec["Categories"]
    assert sec["StartupWMClass"] == "OpenRide Engine"


def test_install_and_uninstall_desktop_script(tmp_path: Path):
    """Critère 3 : installation, idempotence, désinstallation et erreur sans openride dans le PATH."""
    bash_bin = _find_bash()
    if not bash_bin:
        pytest.skip("bash non disponible")

    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir()
    fake_openride = fake_bin_dir / "openride"
    fake_openride.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_openride.chmod(fake_openride.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    prefix_dir = tmp_path / "share"
    empty_home = tmp_path / "home"
    empty_home.mkdir()

    sh_script = _to_shell_path(bash_bin, INSTALL_SH)
    sh_prefix = _to_shell_path(bash_bin, prefix_dir)
    sh_bin_dir = _to_shell_path(bash_bin, fake_bin_dir)
    sh_home = _to_shell_path(bash_bin, empty_home)
    expected_exec = _to_shell_path(bash_bin, fake_openride)

    env = os.environ.copy()
    env["HOME"] = sh_home
    env["PATH"] = f"{sh_bin_dir}:/usr/bin:/bin"

    # 1) Première installation.
    r1 = subprocess.run(
        [bash_bin, sh_script, "--prefix", sh_prefix],
        env=env, capture_output=True, text=True, check=False,
    )
    assert r1.returncode == 0, r1.stderr
    desktop_out = prefix_dir / "applications" / "openride.desktop"
    icon_out = prefix_dir / "icons" / "hicolor" / "scalable" / "apps" / "openride.svg"
    assert desktop_out.is_file() and icon_out.is_file()
    first_desktop_bytes = desktop_out.read_bytes()
    first_icon_bytes = icon_out.read_bytes()

    cp = _read_desktop(desktop_out)
    assert cp["Desktop Entry"]["Exec"] == expected_exec
    apps = prefix_dir / "applications"
    assert sorted(p.name for p in apps.glob("*.desktop")) == sorted(f"{e}.desktop" for e in ENTRIES)
    release = _read_desktop(apps / "openride-release.desktop")["Desktop Entry"]
    assert release["Exec"] == f"{expected_exec} --release-trainer" and release["Terminal"] == "false"
    update = _read_desktop(apps / "openride-update.desktop")["Desktop Entry"]
    assert update["Exec"].endswith("/scripts/update.sh") and "@" not in update["Exec"]

    # 2) Deuxième installation de suite : résultat identique.
    r2 = subprocess.run(
        [bash_bin, sh_script, "--prefix", sh_prefix],
        env=env, capture_output=True, text=True, check=False,
    )
    assert r2.returncode == 0, r2.stderr
    assert desktop_out.read_bytes() == first_desktop_bytes
    assert icon_out.read_bytes() == first_icon_bytes

    # 3) Désinstallation : retire exactement les fichiers OpenRide installés.
    r3 = subprocess.run(
        [bash_bin, sh_script, "--uninstall", "--prefix", sh_prefix],
        env=env, capture_output=True, text=True, check=False,
    )
    assert r3.returncode == 0, r3.stderr
    assert not desktop_out.exists() and not icon_out.exists()
    assert not list(prefix_dir.rglob("*openride*"))

    # 4) Sans openride dans le PATH ni ~/.local/bin : code 1 et message en français.
    env_no_bin = env.copy()
    env_no_bin["PATH"] = "/usr/bin:/bin"
    r4 = subprocess.run(
        [bash_bin, sh_script, "--prefix", sh_prefix],
        env=env_no_bin, capture_output=True, text=True, check=False,
    )
    assert r4.returncode == 1
    assert "introuvable" in r4.stderr.lower()


def test_svg_icon_and_desktop_file_validate(tmp_path: Path):
    """Critère 4 : icône XML/SVG valide < 8 Ko ; desktop-file-validate sans erreur s'il est installé."""
    assert ICON_SVG.is_file()
    size = ICON_SVG.stat().st_size
    assert 0 < size < 8192
    tree = ET.parse(ICON_SVG)
    root = tree.getroot()
    assert root.tag.endswith("svg")

    validator = shutil.which("desktop-file-validate")
    if not validator:
        pytest.skip("desktop-file-validate non installé")
    for entry in ENTRIES:
        rendered = tmp_path / f"{entry}.desktop"
        template = DESKTOP_IN.with_name(f"{entry}.desktop.in").read_text(encoding="utf-8")
        rendered.write_text(template.replace("@OPENRIDE@", "/usr/bin/env").replace("@UPDATE@", "/usr/bin/env"),
                            encoding="utf-8")
        res = subprocess.run([validator, str(rendered)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, res.stdout + res.stderr


def test_shellcheck_install_script():
    """Critère 5 : shellcheck sans avertissement sur install-desktop.sh s'il est installé."""
    sc = shutil.which("shellcheck")
    if not sc:
        pytest.skip("shellcheck non installé")
    scripts = [str(INSTALL_SH), str(INSTALL_SH.with_name("install.sh")), str(INSTALL_SH.with_name("update.sh"))]
    res = subprocess.run([sc, *scripts], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stdout + res.stderr
