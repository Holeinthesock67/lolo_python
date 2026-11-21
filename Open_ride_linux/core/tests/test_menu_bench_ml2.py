"""Banc des menus, lot ML2 : longue liste de parcours (`parcours_copies`) et caches de rendu gardés (`--caches-rendu`)."""

import importlib.util
import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mb = _load("menu_bench")


def test_demo_copies_are_distinct_free_routes(tmp_path: Path) -> None:
    mb.write_demo_copies(tmp_path, 3)
    names = []
    for rid in ("copie-01", "copie-02", "copie-03"):
        manifest = json.loads((tmp_path / f"{rid}.world" / "manifest.json").read_text(encoding="utf-8"))
        names.append(manifest["name"])
        assert (tmp_path / f"{rid}.world" / "route.json").is_file()
        # parcours libres : pas d'étiquette de mode (ils restent dans la liste générale, lot GP13)
        assert "grandprix" not in (manifest.get("library") or {}).get("tags", [])
    assert names == ["Copie 01", "Copie 02", "Copie 03"]


def test_render_caches_round_trip(tmp_path: Path) -> None:
    run1, keep, run2 = tmp_path / "home1", tmp_path / "caches", tmp_path / "home2"
    shader = run1 / mb.RENDER_CACHES[0] / "SkyShaderRD"
    shader.mkdir(parents=True)
    (shader / "a.cache").write_bytes(b"compile")
    (run1 / ".cache" / "mesa_shader_cache").mkdir(parents=True)
    (run1 / "OpenRide").mkdir()
    (run1 / "OpenRide" / "config.toml").write_text("x", encoding="utf-8")
    keep.mkdir()
    assert mb.copy_render_caches(run1, keep) == 2
    assert mb.copy_render_caches(keep, run2) == 2
    assert (run2 / mb.RENDER_CACHES[0] / "SkyShaderRD" / "a.cache").read_bytes() == b"compile"
    assert not (keep / "OpenRide").exists()   # seulement les caches de rendu, rien du profil


def test_new_options_and_head_key() -> None:
    assert "parcours_copies" in mb.HEAD_KEYS
    src = (TESTS / "menu_bench.py").read_text(encoding="utf-8")
    assert '"--caches-rendu"' in src and '"--sonde"' in src
    doc = json.loads((TESTS / "menu_scenarios" / "liste_parcours.json").read_text(encoding="utf-8"))
    assert doc["parcours_copies"] >= 20
