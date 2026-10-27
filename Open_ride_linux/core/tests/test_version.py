"""Lot O2 : un seul numéro de version pour le core, le compilateur et l'engine.

`VERSION` fait foi ; les `pyproject.toml`, `engine/project.godot` et la première section de
`CHANGELOG.md` doivent porter le même numéro. `scripts/bump-version.sh` est essayé dans une copie.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
FILES = ("VERSION", "core/pyproject.toml", "compiler/pyproject.toml", "engine/project.godot", "CHANGELOG.md")


def versions(root: Path) -> dict[str, str]:
    """Numéro lu dans chacun des fichiers, par chemin relatif."""
    out = {"VERSION": (root / "VERSION").read_text(encoding="utf-8").strip()}
    for f in ("core/pyproject.toml", "compiler/pyproject.toml"):
        out[f] = tomllib.loads((root / f).read_text(encoding="utf-8"))["project"]["version"]
    m = re.search(r'^config/version="([^"]*)"', (root / "engine/project.godot").read_text(encoding="utf-8"), re.M)
    out["engine/project.godot"] = m.group(1) if m else ""
    return out


def changelog_head(root: Path) -> str:
    for line in (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            return line
    return ""


def check(root: Path) -> None:
    v = versions(root)
    assert SEMVER.match(v["VERSION"]), f"VERSION : « {v['VERSION']} » n'est pas au format MAJEUR.MINEUR.CORRECTIF"
    for f, value in v.items():
        assert value == v["VERSION"], f"{f} porte « {value} », VERSION porte « {v['VERSION']} »"
    head = changelog_head(root)
    assert re.fullmatch(rf"## {re.escape(v['VERSION'])} – (Non publiée|\d{{4}}-\d{{2}}-\d{{2}})", head), (
        f"CHANGELOG.md : première section « {head} », attendu « ## {v['VERSION']} – Non publiée » ou une date")


def test_same_version_everywhere():
    check(ROOT)


def test_packages_report_the_version():
    import openride_core

    assert openride_core.__version__ == versions(ROOT)["VERSION"]
    compiler = pytest.importorskip("openride_compiler")
    assert compiler.__version__ == versions(ROOT)["VERSION"]


def test_ipc_versions_follow_the_file():
    from openride_core import __version__
    from openride_core.ipc_server import IpcServer

    sent = []
    srv = IpcServer.__new__(IpcServer)
    srv.send_raw = sent.append
    srv.send_hello_ack({})
    assert sent[0]["core_version"] == __version__
    gd = (ROOT / "engine/scripts/ipc_client.gd").read_text(encoding="utf-8")
    assert 'ProjectSettings.get_setting("application/config/version"' in gd
    assert '"engine_version": engine_version' in gd


def copy_tree(tmp_path: Path) -> Path:
    for f in (*FILES, "scripts/bump-version.sh"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, tmp_path / f)
    return tmp_path


@pytest.mark.parametrize("target", FILES[:4])
def test_one_changed_value_names_the_file(tmp_path, target):
    root = copy_tree(tmp_path)
    p = root / target
    p.write_text(p.read_text(encoding="utf-8").replace(versions(ROOT)["VERSION"], "9.9.9", 1), encoding="utf-8")
    with pytest.raises(AssertionError, match=re.escape(target)):
        check(root)


def test_bump_script(tmp_path):
    root = copy_tree(tmp_path)
    r = subprocess.run(["bash", str(root / "scripts/bump-version.sh"), "1.0.0"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    check(root)
    assert versions(root)["VERSION"] == "1.0.0"
    assert re.fullmatch(r"## 1\.0\.0 – \d{4}-\d{2}-\d{2}", changelog_head(root))
    # Les autres sections et dépendances ne bougent pas.
    assert tomllib.loads((root / "core/pyproject.toml").read_text())["project"]["dependencies"]


@pytest.mark.parametrize("bad", ["1.0", "v1.0.0", "1.0.0-rc1", "01.0.0", ""])
def test_bump_script_refuses_bad_numbers(tmp_path, bad):
    root = copy_tree(tmp_path)
    before = (root / "VERSION").read_text()
    r = subprocess.run(["bash", str(root / "scripts/bump-version.sh"), bad], capture_output=True, text=True)
    assert r.returncode == 2
    assert (root / "VERSION").read_text() == before


def test_command_line_versions(capsys):
    from openride_core import __version__
    from openride_core.__main__ import build_parser
    from openride_core.launcher import main as launcher_main

    with pytest.raises(SystemExit):
        build_parser().parse_args(["--version"])
    assert capsys.readouterr().out.strip() == f"openride-core {__version__}"
    assert launcher_main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"openride {__version__}"
